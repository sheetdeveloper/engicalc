"""Turn SymPy objects into the notation an engineer expects to read.

SymPy's own ``sstr`` gives ``Eq(2*x**2 - 5*x - 3, 0)``; this module gives
``2*x^2 - 5*x - 3 = 0``. Purely cosmetic - nothing here is parsed back.
"""

from __future__ import annotations

import re

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


_DIFFERENCE = re.compile(r"^d([A-Z])(\d*)$")


def symbol_names(expr) -> dict:
    """How each symbol should be drawn, for ``sp.latex(symbol_names=...)``.

    A variable named ``dT`` means a change in temperature and is written
    ``ΔT`` everywhere outside a keyboard. The name has to stay ``dT`` - it is
    what the parser and the formula data use - so the difference is made at
    the point of drawing.

    Deliberately narrow: ``d`` followed by a capital. ``delta`` is left alone
    because in this library it means a deflection, the lowercase δ, which is
    a different quantity and not a difference at all.
    """
    names = {}
    try:
        symbols = expr.free_symbols
    except AttributeError:
        return names
    for symbol in symbols:
        match = _DIFFERENCE.match(symbol.name)
        if match:
            letter, index = match.groups()
            names[symbol] = (r"\Delta " + letter
                             + (f"_{{{index}}}" if index else ""))
    return names


def latex(expr, **kwargs) -> str:
    """``sp.latex`` with the difference symbols drawn as Δ."""
    kwargs.setdefault("symbol_names", symbol_names(expr))
    return sp.latex(expr, **kwargs)


_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "lambda_": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Alpha": "Α", "Beta": "Β", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ",
    "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Phi": "Φ",
    "Psi": "Ψ", "Omega": "Ω",
}
_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def unicode_symbol(name: str) -> str:
    """A variable's name written the way it is read: rho -> ρ, dT -> ΔT.

    For places that show a bare name in a plain label - the symbol column of
    the formula library, say - where a rendered image would be heavy and
    would not line up in a table.
    """
    if not name:
        return ""
    text = str(name)

    match = _DIFFERENCE.match(text)
    if match:
        letter, index = match.groups()
        return "Δ" + letter + index.translate(_SUBSCRIPT)

    base, separator, index = text.partition("_")
    if not index and not separator:
        # A trailing number is a subscript: T1 is read as T-one.
        stripped = base.rstrip("0123456789")
        if stripped and stripped != base and stripped not in _GREEK:
            base, index = stripped, base[len(stripped):]
    letter = _GREEK.get(base, base)
    if index.isdigit():
        return letter + index.translate(_SUBSCRIPT)
    if index:
        # Unicode has no full subscript alphabet, so tau_max would come out
        # as "taumax" - the underscore is doing real work and stays.
        return letter + "_" + _GREEK.get(index, index)
    return letter


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
