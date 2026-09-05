"""Translate a SymPy expression into a live Excel formula string.

This is what makes the exported workbook *formula driven* rather than a dump of
numbers: ``m*c*(T2 - T1)`` becomes ``=v_m*v_c*(v_T2-v_T1)`` where each ``v_*``
is a defined name pointing at an input cell, so editing an input recalculates
the sheet.

Only functions that Excel *and* LibreOffice both understand are emitted (see the
project README): no dynamic-array functions, nothing post-2007.
"""

from __future__ import annotations

import re

import sympy as sp
from sympy.printing.str import StrPrinter

# Excel reserves single letters C, c, R and r as names, and anything that looks
# like a cell reference (A1, XFD1048576) is illegal too. Prefixing sidesteps all
# of it and keeps the formulas readable.
NAME_PREFIX = "v_"

GREEK = {
    "alpha": "alpha", "beta": "beta", "gamma": "gamma", "delta": "delta",
    "epsilon": "epsilon", "theta": "theta", "lambda": "lambda_", "mu": "mu",
    "nu": "nu", "xi": "xi", "rho": "rho", "sigma": "sigma", "tau": "tau",
    "phi": "phi", "omega": "omega",
}

FUNCTION_MAP = {
    "sin": "SIN", "cos": "COS", "tan": "TAN",
    "asin": "ASIN", "acos": "ACOS", "atan": "ATAN",
    "sinh": "SINH", "cosh": "COSH", "tanh": "TANH",
    "asinh": "ASINH", "acosh": "ACOSH", "atanh": "ATANH",
    "exp": "EXP", "Abs": "ABS", "sign": "SIGN", "sqrt": "SQRT",
    "factorial": "FACT", "erf": "ERF", "erfc": "ERFC",
    "Min": "MIN", "Max": "MAX", "gamma": "EXP(GAMMALN(%s))",
}

UNSUPPORTED = object()


class ExcelFormulaError(ValueError):
    """Raised when an expression has no faithful Excel equivalent."""


def excel_name(symbol_name: str, prefix: str = NAME_PREFIX) -> str:
    """Turn a SymPy symbol name into a legal Excel defined name."""
    s = str(symbol_name)
    s = GREEK.get(s, s)
    s = re.sub(r"[^0-9A-Za-z_]", "_", s)
    if not s:
        s = "x"
    return f"{prefix}{s}"


class ExcelPrinter(StrPrinter):
    """StrPrinter subclass that emits Excel syntax."""

    def __init__(self, symbol_map: dict | None = None, prefix: str = NAME_PREFIX,
                 settings=None):
        super().__init__(settings)
        self.symbol_map = symbol_map or {}
        self.prefix = prefix

    # -- atoms ------------------------------------------------------------
    def _print_Symbol(self, expr):
        return self.symbol_map.get(expr.name, excel_name(expr.name, self.prefix))

    def _print_Float(self, expr):
        return repr(float(expr))

    def _print_Rational(self, expr):
        if expr.q == 1:
            return str(expr.p)
        return f"({expr.p}/{expr.q})"

    def _print_Half(self, expr):
        return "(1/2)"

    def _print_Pi(self, expr):
        return "PI()"

    def _print_Exp1(self, expr):
        return "EXP(1)"

    def _print_Infinity(self, expr):
        raise ExcelFormulaError("Excel has no representation for infinity.")

    def _print_ImaginaryUnit(self, expr):
        raise ExcelFormulaError("Complex numbers are not exported to Excel.")

    # -- operators --------------------------------------------------------
    def _print_Pow(self, expr, rational=False):
        base, exp = expr.base, expr.exp
        if exp is sp.S.NegativeOne:
            return f"(1/{self._print(base)})"
        if exp == sp.Rational(1, 2):
            return f"SQRT({self._print(base)})"
        if exp == sp.Rational(-1, 2):
            return f"(1/SQRT({self._print(base)}))"
        if exp.is_negative:
            return f"(1/({self._print(base)})^({self._print(-exp)}))"
        return f"({self._print(base)})^({self._print(exp)})"

    def _print_Mul(self, expr):
        # Keep SymPy's numerator/denominator split so the formula reads naturally.
        num, den = sp.fraction(expr)
        if den != 1:
            return f"({self._pr_flat(num)}/({self._pr_flat(den)}))"
        return self._pr_flat(expr)

    def _pr_flat(self, expr):
        """Print a product without introducing a division."""
        if not expr.is_Mul:
            s = self._print(expr)
            return f"({s})" if expr.is_Add else s

        negative = False
        factors = expr.as_ordered_factors()
        if factors and factors[0] is sp.S.NegativeOne:
            negative = True
            factors = factors[1:]
        parts = []
        for arg in factors:
            s = self._print(arg)
            if arg.is_Add:
                s = f"({s})"
            parts.append(s)
        out = "*".join(parts) if parts else "1"
        return ("-" + out) if negative else out

    def _print_Add(self, expr, order=None):
        terms = expr.as_ordered_terms()
        out = self._print(terms[0])
        for t in terms[1:]:
            s = self._print(t)
            out += s if s.startswith("-") else "+" + s
        return out

    # -- functions --------------------------------------------------------
    def _print_log(self, expr):
        if len(expr.args) == 2:
            return f"LOG({self._print(expr.args[0])},{self._print(expr.args[1])})"
        return f"LN({self._print(expr.args[0])})"

    def _print_atan2(self, expr):
        # SymPy atan2(y, x); Excel ATAN2(x, y).
        y, x = expr.args
        return f"ATAN2({self._print(x)},{self._print(y)})"

    def _print_floor(self, expr):
        return f"FLOOR({self._print(expr.args[0])},1)"

    def _print_ceiling(self, expr):
        return f"CEILING({self._print(expr.args[0])},1)"

    def _print_Mod(self, expr):
        return f"MOD({self._print(expr.args[0])},{self._print(expr.args[1])})"

    def _print_Piecewise(self, expr):
        out = ""
        closers = 0
        for value, cond in expr.args:
            if cond is sp.true:
                out += self._print(value)
                break
            out += f"IF({self._print(cond)},{self._print(value)},"
            closers += 1
        else:
            out += "NA()"
        return out + ")" * closers

    def _print_Relational(self, expr):
        op = {"==": "=", "!=": "<>"}.get(expr.rel_op, expr.rel_op)
        return f"{self._print(expr.lhs)}{op}{self._print(expr.rhs)}"

    def _print_Function(self, expr):
        name = expr.func.__name__
        mapped = FUNCTION_MAP.get(name)
        args = ",".join(self._print(a) for a in expr.args)
        if mapped is None:
            raise ExcelFormulaError(
                f"No Excel equivalent for function '{name}'.")
        if "%s" in mapped:
            return mapped % args
        return f"{mapped}({args})"


def to_excel_formula(expr, symbol_map: dict | None = None,
                     prefix: str = NAME_PREFIX, leading_equals: bool = True) -> str:
    """Return an Excel formula string for *expr*.

    ``symbol_map`` optionally maps symbol names to explicit cell references
    (``{"m": "$B$4"}``) instead of defined names.
    """
    printer = ExcelPrinter(symbol_map=symbol_map, prefix=prefix)
    body = printer.doprint(sp.sympify(expr))
    body = body.replace(" ", "")
    return ("=" + body) if leading_equals else body


def can_export(expr) -> bool:
    try:
        to_excel_formula(expr)
        return True
    except (ExcelFormulaError, Exception):  # noqa: BLE001
        return False
