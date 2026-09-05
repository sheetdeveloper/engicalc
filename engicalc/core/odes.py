"""Differential equations, written the way they are written on paper.

A beam's deflection, a transient cooling curve, the current in an RC circuit
and a vibrating mass are all differential equations, and none of them could
be typed into this app before: ``y' = y`` did not parse at all.

Input is prime notation - ``y' = y``, ``y'' + 4y = 0`` - because that is what
a textbook uses. Initial conditions go in separately as ``y(0)=90, y'(0)=0``,
and they matter: without them the answer carries arbitrary constants and is a
family of curves rather than the one the apparatus actually followed.

Two things here exist because of what goes wrong without them:

* **Every bare name is declared as a symbol.** ``E*I*y'' = M`` is the beam
  equation, and left to the ordinary parser ``E`` is Euler's number and ``I``
  is the square root of minus one. The answer then contains ``exp(-1)`` and an
  imaginary unit, and is quietly, thoroughly wrong.
* **``y^(n) = g(x)`` is integrated here rather than by SymPy.** That is the
  beam equation again, and free fall. SymPy's ``dsolve`` recurses into itself
  on that shape and never returns - even ``y'' = -9.81`` with no conditions at
  all exhausts the stack.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp

from .display import fmt
from .engine import CalcResult
from .parsing import SAFE_FUNCTIONS, ParseError, parse_input
from .steps import Step

# y'' before y', or the second derivative is read as two first ones.
_PRIMES = [("''''", 4), ("'''", 3), ("''", 2), ("'", 1)]

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


@dataclass
class Condition:
    """``y'(0) = 20``: how many primes, where, and what it equals."""

    primes: int
    at: object
    value: object


def _prepare(text: str, function: str, variable: str) -> str:
    """Turn prime notation into something the parser can read.

    ``y'' + 4y = 0`` becomes ``Derivative(y(x), x, 2) + 4*y(x) = 0``. The
    order matters: the two-prime form has to be replaced before the one-prime
    form, or the second derivative comes out as two first derivatives.
    """
    out = text
    for marks, order in _PRIMES:
        pattern = re.escape(function) + re.escape(marks) + r"(?!')"
        replacement = (f"Derivative({function}({variable}), {variable}"
                       + (f", {order})" if order > 1 else ")"))
        out = re.sub(pattern, replacement, out)

    # A bare y means y(x). Not \by\b: there is no word boundary between a
    # digit and a letter, so "4y" - which is how anyone writes it - would be
    # left as a bare symbol and the equation would come out wrong rather than
    # failing. Instead: not preceded by an identifier character, and not
    # followed by one or by an opening bracket, so "xy", "y2" and the
    # "y(x)" just written are all left alone.
    out = re.sub(rf"(?<![A-Za-z_]){re.escape(function)}"
                 rf"(?![A-Za-z_0-9]|\s*\()",
                 f"{function}({variable})", out)
    return out


def _locals(text: str, function: str, variable: str) -> dict:
    """Declare every bare name as a plain symbol.

    Without this, `E` and `I` in the beam equation are Euler's number and the
    imaginary unit, and the answer comes back containing exp(-1) - wrong, and
    wrong in a way that still looks like an answer. The formula library does
    the same thing for the same reason.
    """
    names = {function: sp.Function(function), variable: sp.Symbol(variable)}
    for name in set(_IDENTIFIER.findall(text)):
        if name in names or name in SAFE_FUNCTIONS or name == "Derivative":
            continue
        names[name] = sp.Symbol(name)
    return names


def parse_ode(text: str, function: str = "y", variable: str = "x") -> sp.Eq:
    """Read ``y' = y`` and the like into a SymPy equation."""
    if not text or not text.strip():
        raise ParseError("Nothing to solve.")
    prepared = _prepare(text, function, variable)
    parsed = parse_input(prepared,
                         extra_symbols=_locals(prepared, function, variable))
    equation = parsed.expr
    if not isinstance(equation, sp.Eq):
        equation = sp.Eq(equation, 0)
    if not equation.atoms(sp.Derivative):
        raise ParseError(
            f"There is no derivative here - write {function}' for the first "
            f"derivative, {function}'' for the second.")
    return equation


def parse_conditions(text: str, function: str = "y") -> list:
    """Read ``y(0)=90, y'(0)=0`` into a list of :class:`Condition`.

    Kept as plain numbers rather than SymPy objects: a derivative condition
    becomes a ``Subs`` once substituted, and reading the point back out of one
    of those is fiddly enough to get wrong - which it was.
    """
    found: list = []
    if not text or not text.strip():
        return found

    for piece in re.split(r"[,;]", text):
        piece = piece.strip()
        if not piece:
            continue
        match = re.match(rf"^{re.escape(function)}(')*\s*\(\s*([^)]+?)\s*\)\s*"
                         r"=\s*(.+)$", piece)
        if not match:
            raise ParseError(
                f"Could not read the condition {piece!r}. They look like "
                f"{function}(0) = 1 or {function}'(0) = 0.")
        try:
            at = sp.sympify(match.group(2))
            value = sp.sympify(match.group(3))
        except Exception as exc:                      # noqa: BLE001
            raise ParseError(f"Could not read {piece!r}: {exc}") from exc
        found.append(Condition(len(match.group(1) or ""), at, value))
    return found


def _as_ics(conditions: list, function: str, variable: str) -> dict:
    """The conditions in the shape ``dsolve`` wants."""
    f = sp.Function(function)
    x = sp.Symbol(variable)
    ics = {}
    for condition in conditions:
        if condition.primes == 0:
            ics[f(condition.at)] = condition.value
        else:
            ics[f(x).diff(x, condition.primes).subs(x, condition.at)] = \
                condition.value
    return ics


def _plain_integration(equation: sp.Eq, function: str, variable: str,
                       conditions: list):
    """Solve ``y^(n) = g(x)`` by integrating, because SymPy will not.

    This is the beam equation - ``EI y'' = M(x)`` - and free fall. SymPy's
    dsolve recurses into itself on this shape and never returns, so even
    ``y'' = -9.81`` with no conditions blows the stack.

    Returns the solution, or None if the equation is not of this shape.
    """
    x = sp.Symbol(variable)
    f = sp.Function(function)(x)

    derivatives = equation.atoms(sp.Derivative)
    if len(derivatives) != 1:
        return None
    derivative = next(iter(derivatives))
    if derivative.expr != f:
        return None
    order = len(derivative.variables)

    # Rearrange for the derivative itself. Solving rather than subtracting
    # handles a coefficient - EI y'' = M is the form this exists for - and
    # says at once whether anything else in the equation involves y.
    try:
        rearranged = sp.solve(equation.lhs - equation.rhs, derivative)
    except Exception:                                 # noqa: BLE001
        return None
    if len(rearranged) != 1:
        return None
    right = sp.simplify(rearranged[0])
    if right.has(f) or right.has(sp.Derivative):
        return None

    # Integrate all the way down first, then add the constants. Adding one
    # after each integration hands it to the next integration as well, so
    # C1 x becomes C1 x^2 / 2 and the conditions can no longer be satisfied.
    expression = right
    for _ in range(order):
        expression = sp.integrate(expression, x)

    constants = [sp.Symbol(f"C{index + 1}") for index in range(order)]
    for index, constant in enumerate(constants):
        expression = expression + constant * x ** (order - index - 1)

    if conditions:
        wanted = [sp.Eq(sp.diff(expression, x, c.primes).subs(x, c.at), c.value)
                  for c in conditions]
        found = sp.solve(wanted, constants, dict=True)
        if found:
            expression = expression.subs(found[0])

    return sp.Eq(f, sp.expand(sp.simplify(expression)))


def solve_ode(text: str, function: str = "y", variable: str = "x",
              conditions: str = "") -> CalcResult:
    """Solve an ODE, with initial conditions if any were given."""
    equation = parse_ode(text, function, variable)
    x = sp.Symbol(variable)
    f = sp.Function(function)(x)

    result = CalcResult(operation="ode", input_text=text, variable=variable,
                        plottable=True)
    order = max((len(d.variables) for d in equation.atoms(sp.Derivative)),
                default=1)
    result.steps.append(Step(f"Order {order} differential equation",
                             expr=equation))

    parsed_conditions = parse_conditions(conditions, function)
    if parsed_conditions:
        result.steps.append(Step(
            "Conditions",
            detail=", ".join(
                f"{function}{chr(39) * c.primes}({fmt(c.at)}) = {fmt(c.value)}"
                for c in parsed_conditions)))

    solution = _plain_integration(equation, function, variable,
                                  parsed_conditions)
    if solution is None:
        ics = _as_ics(parsed_conditions, function, variable)
        try:
            solution = sp.dsolve(equation, f, ics=ics) if ics \
                else sp.dsolve(equation, f)
        except RecursionError as exc:
            raise ParseError(
                "SymPy could not solve this one - its solver recurses without "
                "finishing on this shape of equation.") from exc
        except NotImplementedError as exc:
            raise ParseError(
                f"SymPy has no method for this equation. ({exc})") from exc
        except Exception as exc:                      # noqa: BLE001
            raise ParseError(f"Could not solve it: {exc}") from exc

    if isinstance(solution, list):
        result.warnings.append(
            f"{len(solution)} solutions; showing the first.")
        solution = solution[0]

    result.results = [solution]
    result.expression = solution.rhs if isinstance(solution, sp.Eq) else None
    result.result_text = fmt(solution)
    result.latex = sp.latex(solution)

    free = result.expression.free_symbols if result.expression is not None \
        else set()
    constants = sorted((s for s in free if re.fullmatch(r"C\d+", s.name)),
                       key=lambda s: s.name)
    if constants:
        names = ", ".join(s.name for s in constants)
        plural = "s" if len(constants) > 1 else ""
        result.warnings.append(
            f"This is the general solution - {names} could be anything. Give "
            f"{len(constants)} condition{plural} such as {function}(0) = 1 to "
            "pin down the one curve your problem actually follows.")
        result.steps.append(Step("General solution", expr=solution))
    else:
        result.steps.append(Step("Particular solution", expr=solution))

    return result
