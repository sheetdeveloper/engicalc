"""Solving a set of equations together, whatever order they are written in.

This is the idea worth taking from EES. A calculation is rarely a chain that
runs one way: a duct sizing has friction depending on velocity, velocity on
area, and the friction factor on the Reynolds number that depends on both.
Written as a set, none of that needs untangling by hand - you state what is
true and the solver finds the values that make all of it true at once.

The most useful thing EES tells you is not the answer but the **count**:
three equations and four unknowns has no single answer, and saying so is more
help than any number would be. So that check comes first and is phrased in
terms of what to do about it.

Symbolically first, numerically second. An exact answer is worth having when
one exists - it rearranges, it can be read - and the numerical fallback is
there for the implicit cases that have no closed form, which in engineering
is most of the interesting ones.

Every answer is substituted back into the original equations and the residual
reported. A numerical solve that converged on the wrong branch looks exactly
like one that worked until you check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from .display import fmt, fmt_number
from .engine import CalcResult
from .parsing import ParseError, parse_input, symbols_in
from .steps import Step

#: Starting points tried in turn when the symbolic solver finds nothing.
#: Spread over several orders of magnitude and both signs, because a
#: dimensionless group and a pressure in pascals are not the same size.
GUESSES = (1.0, 0.5, 2.0, 10.0, 0.1, 100.0, -1.0, 1000.0, 0.01)

#: Anything bigger and the answer does not satisfy the equations it came
#: from. Relative, not absolute - see :func:`_residuals`.
RESIDUAL_LIMIT = 1e-6


@dataclass
class Parsed:
    """The equations, what is unknown in them, and what is allowed."""

    equations: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    given: dict = field(default_factory=dict)
    #: Inequalities written on lines of their own. They say which of the
    #: answers is wanted, not what the answer is.
    bounds: list = field(default_factory=list)

    @property
    def freedom(self) -> int:
        """Unknowns minus equations. Zero is a set with one answer.

        Bounds are not counted. A bound cannot make an under-determined set
        solvable - `T > 0` rules answers out, it does not pin one down - and
        counting it as an equation would say a set was ready when it is not.
        """
        return len(self.unknowns) - len(self.equations)


def parse_set(text: str, given: dict | None = None) -> Parsed:
    """Read a block of equations, one per line or separated by ';'.

    Lines starting with ``#`` are notes and are ignored, so a sheet can carry
    its own explanation.
    """
    given = {k: v for k, v in (given or {}).items()
             if str(v).strip() != ""}
    equations = []
    bounds = []
    for chunk in re.split(r"[;\n]+", text or ""):
        line = chunk.strip()
        if not line or line.startswith("#"):
            continue
        # Declared first, or "Re" parses as R times e and the equation is
        # quietly about different quantities than the one typed.
        try:
            parsed = parse_input(line, extra_symbols=symbols_in(text)).expr
        except ParseError as exc:
            # A range written the way it is written on paper. Python cannot
            # chain comparisons into one relation, and the message it gives
            # mentions neither ranges nor what to do instead.
            if line.count("<") + line.count(">") > 1:
                raise ParseError(
                    f"{line!r} is a range, and it needs writing as two "
                    "lines - one for each end:\n"
                    f"    {line.split('<')[1].strip() if '<' in line else 'x'}"
                    " > (the lower end)\n"
                    f"    {line.split('<')[1].strip() if '<' in line else 'x'}"
                    " < (the upper end)") from exc
            raise
        if isinstance(parsed, sp.Rel) and not isinstance(parsed, sp.Eq):
            # An inequality is a bound on the answer, not an equation to be
            # satisfied. Turning it into `Eq(thing, 0)` - which is what used
            # to happen to anything that was not an equation - gives False,
            # which has no left hand side and crashed.
            bounds.append(parsed)
            continue
        if isinstance(parsed, (sp.logic.boolalg.BooleanTrue,
                               sp.logic.boolalg.BooleanFalse)):
            raise ParseError(
                f"{line!r} works out to just true or false, so there is "
                "nothing to solve in it. A range needs writing as two lines "
                "- `T > 0` and `T < 1000` - rather than as `0 < T < 1000`.")
        if not isinstance(parsed, sp.Eq):
            # "x + y - 10" on its own means it is zero.
            parsed = sp.Eq(parsed, 0)
        equations.append(parsed)

    if not equations:
        raise ParseError("No equations here.")

    substitutions = {}
    for name, value in given.items():
        try:
            substitutions[sp.Symbol(name)] = sp.sympify(str(value))
        except Exception as exc:                      # noqa: BLE001
            raise ParseError(f"Could not read the value for {name}: {exc}") \
                from exc
    if substitutions:
        equations = [e.subs(substitutions) for e in equations]

    if substitutions:
        bounds = [b.subs(substitutions) for b in bounds]
    # A name that appears only in a bound is not an unknown - `T > 0` on its
    # own does not introduce anything to solve for.
    unknowns = sorted({s for e in equations for s in e.free_symbols},
                      key=lambda s: s.name)
    return Parsed(equations, unknowns, given, bounds)



def _fractional_power(parsed: Parsed) -> bool:
    """True when an unknown is raised to something other than a whole number.

    That is the shape that sends sp.solve into a Groebner basis, which can
    take unbounded time and cannot be interrupted. An integer power - `1/A`
    is A to the minus one - is not this, and solves exactly without trouble.
    """
    unknowns = set(parsed.unknowns)
    for equation in parsed.equations:
        for power in equation.atoms(sp.Pow):
            if not (power.base.free_symbols & unknowns):
                continue
            if not power.exp.is_Integer:
                return True
    return False

@dataclass
class SweepRow:
    """One value of the swept name, and what the set gave for it."""

    value: float
    result: object = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(getattr(self.result, "results", None))

    def get(self, name: str):
        """The value of *name* in this row, or None if it has none."""
        if not self.ok:
            return None
        for symbol, found in self.result.results[0].items():
            if str(symbol) != name:
                continue
            try:
                return float(sp.N(found))
            except (TypeError, ValueError):
                # Genuinely complex, so there is no point on a graph for it.
                return None
        return None


def free_names(text: str, given: dict | None = None) -> list:
    """The names a set of equations does not pin down.

    A set with one name free is one that can be swept, which is why this is
    worth asking separately from solving.
    """
    parsed = parse_set(text, given)
    if parsed.freedom <= 0:
        # Already pinned down. Fixing anything else would over-determine it,
        # so there is nothing here to sweep however the equations are shaped.
        return []

    # A name the equations work *out* is the subject of one of them. What is
    # left is what they take as input, and that is what there is any point
    # sweeping.
    subjects = {equation.lhs.name for equation in parsed.equations
                if equation.lhs.is_Symbol}
    inputs = [s.name for s in parsed.unknowns if s.name not in subjects]
    # If nothing is written as `name = ...` then no name is more an input
    # than any other, and any of them can be the one that is fixed.
    return inputs or [s.name for s in parsed.unknowns]


def sweep(text: str, variable: str, values, given: dict | None = None) -> list:
    """Solve the set once for each value of *variable*.

    Each solve starts from the equations as written rather than from the
    last answer. That is slower, and it is right: a set with more than one
    solution can jump between them as the swept value moves, and carrying
    the previous answer forward would smooth over exactly that.
    """
    name = (variable or "").strip()
    if not name:
        raise ParseError("Say which name to sweep.")
    rows = []
    for value in values:
        line = f"{name} = {value}"
        try:
            rows.append(SweepRow(float(value),
                                 result=solve_set(f"{text}\n{line}", given)))
        except ParseError as exc:
            rows.append(SweepRow(float(value), error=str(exc)))
        except Exception as exc:                      # noqa: BLE001
            rows.append(SweepRow(float(value), error=str(exc)))
    return rows


def spread(start: float, stop: float, steps: int) -> list:
    """*steps* values from *start* to *stop*, both ends included."""
    if steps < 2:
        return [float(start)]
    span = (float(stop) - float(start)) / (steps - 1)
    return [float(start) + span * index for index in range(steps)]


def sweep_table(rows: list, names: list) -> tuple:
    """(headings, rows) for a table of a sweep, ready to show or export."""
    headings = ["value"] + list(names)
    out = []
    for row in rows:
        if not row.ok:
            out.append([row.value] + [row.error or "no solution"]
                       + [""] * (len(names) - 1))
            continue
        out.append([row.value] + [row.get(name) for name in names])
    return headings, out


def _residuals(equations: list, answer: dict) -> list:
    """How far each equation is from being satisfied, relative to its size.

    A residual only means something next to the numbers that produced it.
    A Reynolds number comes out around 500,000, and asking that equation to
    balance to an absolute 1e-6 is asking for twelve significant figures -
    more than double precision carries. The check would then call a perfectly
    good answer wrong, which is worse than not checking at all.

    So each residual is divided by the size of the terms it came from. The
    scale never drops below one, so a small equation still has to satisfy the
    absolute test: x - 1 = 0 does not get an easier time for being small.
    """
    out = []
    for equation in equations:
        try:
            lhs = complex(sp.N(equation.lhs.subs(answer)))
            rhs = complex(sp.N(equation.rhs.subs(answer)))
            scale = max(1.0, abs(lhs), abs(rhs))
            out.append(abs(lhs - rhs) / scale)
        except Exception:                             # noqa: BLE001
            out.append(float("nan"))
    return out


#: How small an imaginary part has to be, next to the real one, to be
#: rounding rather than an answer.
IMAGINARY_DUST = 1e-9


def _tidy(answer: dict) -> dict:
    """Drop imaginary parts that are only floating point dust.

    nsolve can return `738.82 - 4.9e-18*I` for a number that is real. That
    is not a complex answer, it is a real one with dust on it, and it should
    not reach the screen looking like that. A genuinely complex answer is
    left alone: a set of equations is allowed to have them, and quietly
    making one real would be a worse fault than showing the dust.
    """
    cleaned = {}
    for name, value in answer.items():
        try:
            number = sp.N(value)
            real, imaginary = float(sp.re(number)), float(sp.im(number))
        except (TypeError, ValueError):
            cleaned[name] = value
            continue
        scale = max(abs(real), 1.0)
        cleaned[name] = sp.Float(real) \
            if abs(imaginary) < IMAGINARY_DUST * scale else value
    return cleaned


def within(answer: dict, bounds: list) -> bool:
    """True when *answer* satisfies every bound.

    A bound that cannot be decided - because it mentions something the
    answer does not fix - is treated as satisfied. Discarding an answer over
    a bound nobody can evaluate would be worse than showing it.
    """
    for bound in bounds:
        try:
            verdict = bound.subs(answer)
            if verdict is sp.false or verdict is False:
                return False
            if isinstance(verdict, sp.Rel):
                value = sp.simplify(verdict.lhs - verdict.rhs)
                if not value.is_number:
                    continue          # cannot be decided; let it pass
                if verdict.func(value, 0) is sp.false:
                    return False
        except Exception:                             # noqa: BLE001
            continue
    return True


def _guess_from(bounds: list, unknowns: list) -> list:
    """Starting points suggested by the bounds, tried before the usual ones.

    A bound says roughly where the answer is, which is exactly what an
    iterative solver wants to be told. `T > 300` starts it somewhere useful
    rather than at 1.
    """
    hints = {}
    for bound in bounds:
        for symbol in bound.free_symbols:
            if symbol not in unknowns:
                continue
            other = sp.simplify(bound.rhs if bound.lhs == symbol
                                else bound.lhs)
            if other.is_number:
                edge = float(other)
                hints[symbol] = edge * 1.1 + 1.0 if edge >= 0 else edge * 0.9
    return hints


def _numeric(parsed: Parsed, result: CalcResult):
    """Try nsolve from several starting points. None if none of them land."""
    expressions = [e.lhs - e.rhs for e in parsed.equations]
    hints = _guess_from(parsed.bounds, set(parsed.unknowns))
    for guess in GUESSES:
        start = [hints.get(symbol, guess) for symbol in parsed.unknowns]
        try:
            found = sp.nsolve(expressions, parsed.unknowns, start, dict=True)
        except Exception:                             # noqa: BLE001
            continue
        answer = found[0] if isinstance(found, list) else dict(
            zip(parsed.unknowns, found))
        if not answer:
            continue
        answer = _tidy(answer)
        if not within(answer, parsed.bounds):
            continue                  # a root, but not one that is allowed
        worst = max(_residuals(parsed.equations, answer), default=0.0)
        if worst <= RESIDUAL_LIMIT:
            result.steps.append(Step(
                "Solved numerically",
                detail=f"No closed form, so found by iteration from a "
                       f"starting guess of {fmt_number(guess)}."))
            return answer
    return None


def solve_set(text: str, given: dict | None = None) -> CalcResult:
    """Solve a set of equations together. Returns a :class:`CalcResult`."""
    parsed = parse_set(text, given)
    result = CalcResult(operation="system", input_text=text.strip(),
                        variable=", ".join(s.name for s in parsed.unknowns))

    names = ", ".join(s.name for s in parsed.unknowns) or "nothing"
    result.steps.append(Step(
        f"{len(parsed.equations)} equation"
        + ("s" if len(parsed.equations) != 1 else "")
        + f", {len(parsed.unknowns)} unknown"
        + ("s" if len(parsed.unknowns) != 1 else ""),
        detail=f"Unknown: {names}"))
    for index, equation in enumerate(parsed.equations, 1):
        result.steps.append(Step(f"Equation {index}", expr=equation))

    # The count, before any attempt to solve. This is the diagnostic worth
    # having: it says what to do, which no answer could.
    if parsed.freedom > 0:
        missing = parsed.freedom
        count = len(parsed.equations)
        result.result_text = (
            f"Not enough to go on: {len(parsed.unknowns)} unknowns and only "
            f"{count} equation{'s' if count != 1 else ''}.")
        result.warnings.append(
            f"Give {missing} more equation{'s' if missing > 1 else ''}, or fix "
            f"{missing} of the unknowns to a value. As it stands there is a "
            "whole family of answers rather than one.")
        return result

    answer = None
    solutions = []
    if _fractional_power(parsed):
        # Straight to iteration. Asking for an exact answer here means a
        # Groebner basis, which can take unbounded time and cannot be
        # stopped once it has started - see the note on _fractional_power.
        result.steps.append(Step(
            "Solved by iteration",
            detail="An unknown is raised to a fractional power, so there is "
                   "no exact answer worth waiting for - this is found "
                   "numerically instead."))
        answer = _numeric(parsed, result)
    else:
        try:
            solutions = sp.solve(parsed.equations, parsed.unknowns, dict=True)
        except Exception as exc:                      # noqa: BLE001
            result.warnings.append(f"The exact solver gave up ({exc}).")

        allowed = [a for a in solutions if within(a, parsed.bounds)]
        excluded = len(solutions) - len(allowed)
        if excluded:
            result.steps.append(Step(
                f"Ruled out by the bounds: {excluded} of {len(solutions)}",
                detail="They satisfy the equations but not what was said "
                       "about the answer."))
        if allowed:
            answer = allowed[0]
            if len(allowed) > 1:
                result.warnings.append(
                    f"{len(allowed)} sets of values satisfy these "
                    "equations; the first is shown. The others are just as "
                    "valid - which one is wanted is a question about the "
                    "problem, not the algebra. A bound like `x > 0` on a "
                    "line of its own will narrow it.")
        elif solutions:
            result.warnings.append(
                f"All {len(solutions)} solutions were ruled out by the "
                "bounds. Either a bound is wrong or the set has no answer "
                "that satisfies them.")
        if not allowed:
            # Nothing exact survived, so try iteration - which honours the
            # bounds too, and starts from them.
            answer = _numeric(parsed, result)

    if not answer:
        result.result_text = "No solution found."
        if parsed.freedom < 0:
            result.warnings.append(
                f"There are {-parsed.freedom} more equations than unknowns. "
                "If they disagree even slightly there is nothing that "
                "satisfies all of them at once.")
        else:
            result.warnings.append(
                "Neither the exact solver nor iteration from several starting "
                "points found values that satisfy all of these at once.")
        return result

    ordered = sorted(answer.items(), key=lambda pair: str(pair[0]))
    result.results = [answer]
    result.result_text = "\n".join(f"{key} = {fmt(value)}"
                                   for key, value in ordered)
    result.numeric = []
    for _key, value in ordered:
        try:
            result.numeric.append(float(sp.N(value)))
        except (TypeError, ValueError):
            result.numeric.append(None)
    try:
        result.latex = r",\quad ".join(
            sp.latex(sp.Eq(key, value)) for key, value in ordered)
    except Exception:                                 # noqa: BLE001
        result.latex = ""

    result.steps.append(Step("Values that satisfy all of them",
                             detail=result.result_text))

    # Substituted back in, always. A numerical solve that converged on the
    # wrong branch looks exactly like one that worked until this is checked.
    residuals = _residuals(parsed.equations, answer)
    worst = max(residuals, default=0.0)
    if worst <= RESIDUAL_LIMIT:
        result.steps.append(Step(
            "Checked",
            detail="Substituted back into every equation; all satisfied."
            if worst == 0 else
            f"Substituted back into every equation; the worst is out by "
            f"{fmt_number(worst * 100)}% of the size of its own terms."))
    else:
        result.warnings.append(
            f"These values do not satisfy the equations - the worst is out by "
            f"{fmt_number(worst * 100)}% of the size of its own terms. Treat "
            "the answer as wrong rather than approximate.")
    return result
