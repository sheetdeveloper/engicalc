"""Turn SymPy objects into the notation an engineer expects to read.

SymPy's own ``sstr`` gives ``Eq(2*x**2 - 5*x - 3, 0)``; this module gives
``2*x^2 - 5*x - 3 = 0``. Purely cosmetic - nothing here is parsed back.
"""

from __future__ import annotations

import sympy as sp


def fmt(expr) -> str:
    """Format *expr* for display in the window."""
    if expr is None:
        return ""
    if isinstance(expr, str):
        return expr
    if isinstance(expr, (list, tuple)):
        return ", ".join(fmt(e) for e in expr)
    if isinstance(expr, dict):
        return ", ".join(f"{fmt(k)} = {fmt(v)}" for k, v in expr.items())
    if not isinstance(expr, sp.Basic):
        return str(expr)

    # A Float prints all fifteen of the digits it is carrying, so a limit
    # typed as -1.6 comes back as -1.60000000000000. None of those zeros are
    # information, and they make a worked solution look like a machine
    # readout rather than an answer.
    if isinstance(expr, sp.Float):
        return fmt_number(expr)

    if isinstance(expr, sp.Equality):
        return f"{fmt(expr.lhs)} = {fmt(expr.rhs)}"
    if isinstance(expr, sp.Rel):
        return f"{fmt(expr.lhs)} {expr.rel_op} {fmt(expr.rhs)}"
    if isinstance(expr, sp.Derivative):
        variable = expr.variables[0]
        order = len(expr.variables)
        lead = f"d/d{variable}" if order == 1 else f"d^{order}/d{variable}^{order}"
        return f"{lead} [ {fmt(expr.expr)} ]"
    if isinstance(expr, sp.Integral):
        limits = expr.limits[0]
        variable = limits[0]
        if len(limits) == 3:
            return (f"integral from {fmt(limits[1])} to {fmt(limits[2])} of "
                    f"[ {fmt(expr.function)} ] d{variable}")
        return f"integral of [ {fmt(expr.function)} ] d{variable}"
    if isinstance(expr, sp.Limit):
        function, variable, point = expr.args[0], expr.args[1], expr.args[2]
        direction = expr.args[3] if len(expr.args) > 3 else ""
        return (f"lim {variable} -> {fmt(point)}{direction} "
                f"[ {fmt(function)} ]")
    return sp.sstr(expr).replace("**", "^")


def fmt_set(solution) -> str:
    """An inequality's answer, written the way it is read.

    SymPy's own text for these is ``Union(Interval.open(-oo, -2),
    Interval.open(2, oo))``. An engineer reads ``(-inf, -2) or (2, inf)``.
    Square brackets where the endpoint is included, round where it is not,
    which is the same convention every textbook uses.
    """
    if solution is None:
        return ""
    if isinstance(solution, sp.Interval):
        left = "(" if solution.left_open else "["
        right = ")" if solution.right_open else "]"
        return f"{left}{fmt(solution.start)}, {fmt(solution.end)}{right}"
    if isinstance(solution, sp.Union):
        return "  or  ".join(fmt_set(part) for part in solution.args)
    if isinstance(solution, sp.FiniteSet):
        return "{" + ", ".join(fmt(part) for part in solution.args) + "}"
    if solution is sp.S.EmptySet or solution == sp.S.EmptySet:
        return "no solution"
    if solution == sp.S.Reals:
        return "all real numbers"
    if isinstance(solution, sp.Complement):
        whole, removed = solution.args
        return f"{fmt_set(whole)} except {fmt_set(removed)}"
    return fmt(solution)


def fmt_number(value, digits: int = 10) -> str:
    """Format a numeric value without a trailing wall of zeros."""
    try:
        number = sp.N(value, digits)
        if number.is_real:
            as_float = float(number)
            if as_float == int(as_float) and abs(as_float) < 1e15:
                return str(int(as_float))
            return f"{as_float:.{digits}g}"
        return str(number)
    except Exception:  # noqa: BLE001
        return str(value)
