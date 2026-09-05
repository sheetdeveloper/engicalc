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
    """The equations, and what is unknown in them."""

    equations: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    given: dict = field(default_factory=dict)

    @property
    def freedom(self) -> int:
        """Unknowns minus equations. Zero is a set with one answer."""
        return len(self.unknowns) - len(self.equations)


def parse_set(text: str, given: dict | None = None) -> Parsed:
    """Read a block of equations, one per line or separated by ';'.

    Lines starting with ``#`` are notes and are ignored, so a sheet can carry
    its own explanation.
    """
    given = {k: v for k, v in (given or {}).items()
             if str(v).strip() != ""}
    equations = []
    for chunk in re.split(r"[;\n]+", text or ""):
        line = chunk.strip()
        if not line or line.startswith("#"):
            continue
        # Declared first, or "Re" parses as R times e and the equation is
        # quietly about different quantities than the one typed.
        parsed = parse_input(line, extra_symbols=symbols_in(text)).expr
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

    unknowns = sorted({s for e in equations for s in e.free_symbols},
                      key=lambda s: s.name)
    return Parsed(equations, unknowns, given)



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


def _numeric(parsed: Parsed, result: CalcResult):
    """Try nsolve from several starting points. None if none of them land."""
    expressions = [e.lhs - e.rhs for e in parsed.equations]
    for guess in GUESSES:
        try:
            found = sp.nsolve(expressions, parsed.unknowns,
                              [guess] * len(parsed.unknowns), dict=True)
        except Exception:                             # noqa: BLE001
            continue
        answer = found[0] if isinstance(found, list) else dict(
            zip(parsed.unknowns, found))
        if not answer:
            continue
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

        if solutions:
            answer = solutions[0]
            if len(solutions) > 1:
                result.warnings.append(
                    f"{len(solutions)} sets of values satisfy these "
                    "equations; the first is shown. The others are just as "
                    "valid - which one is wanted is a question about the "
                    "problem, not the algebra.")
        else:
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
