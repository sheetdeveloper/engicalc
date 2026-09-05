"""Trendlines through paired readings, and an honest way to compare them.

The shapes are the ones a spreadsheet offers, because those are the ones
people already reach for: a straight line, a polynomial, and the three that
are fitted by straightening them out first - exponential, logarithmic and
power.

**R squared is measured on the original readings for every shape here**, and
that is a deliberate difference from Excel. An exponential is fitted by
taking logs of y and fitting a line to those, and the obvious thing is to
report the R squared of that straight line - which is what Excel does. But
that number describes how well a line fits the *logs*, not how well the curve
fits the readings, and it is usually flattering: taking logs squashes the
large residuals that matter most. Two shapes scored that way cannot be
compared at all, because the numbers are measured against different things.

Since the whole point of offering six shapes is to pick between them, each
one is scored by how far its curve actually lands from the readings. A fit
that misses badly can then score below zero, which is not a bug - it means
the curve is a worse description than a flat line through the mean, and that
is worth being told.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import sympy as sp

from .display import fmt_number
from .parsing import ParseError

#: The most terms a polynomial is offered with. Past this a fit is chasing
#: the noise rather than the shape - it will pass closer to every reading and
#: tell you less about what happens between them.
MAX_ORDER = 6


@dataclass
class Curve:
    """One fitted shape, and how far it lands from the readings."""

    key: str
    name: str
    coefficients: list = field(default_factory=list)
    r_squared: float = 0.0
    residuals: list = field(default_factory=list)
    expression: sp.Expr | None = None
    #: Why this shape could not be fitted, if it could not. A curve that
    #: cannot be fitted is still listed - "needs every y above zero" is more
    #: use than the shape quietly not appearing.
    refused: str = ""

    @property
    def ok(self) -> bool:
        return not self.refused

    @property
    def worst_residual(self) -> float:
        return float(np.max(np.abs(self.residuals))) if len(self.residuals) \
            else 0.0

    def predict(self, xs):
        """The fitted y for each x, for drawing the curve."""
        if self.expression is None:
            return np.full(len(xs), np.nan)
        function = sp.lambdify(sp.Symbol("x"), self.expression, "numpy")
        with np.errstate(all="ignore"):
            return np.asarray(function(np.asarray(xs, dtype=float)),
                              dtype=float)

    #: Significant figures a coefficient is shown to. A least-squares fit
    #: does not know them to more than this, and printing fifteen implies
    #: a precision the readings never had.
    FIGURES = 6

    def shown(self, figures: int = 0):
        """The expression with its coefficients rounded, for reading.

        Display only - :meth:`predict` keeps every figure, so the drawn
        curve and the residuals are unaffected.
        """
        if self.expression is None:
            return None
        figures = figures or self.FIGURES
        return self.expression.xreplace({
            number: sp.Float(number, figures)
            for number in self.expression.atoms(sp.Float)})

    def as_text(self) -> str:
        if self.refused:
            return f"{self.name}: {self.refused}"
        return f"y = {sp.sstr(self.shown())}"

    def rows(self) -> list:
        if self.refused:
            return [(self.name, "", self.refused)]
        return [
            (self.name, self.r_squared,
             f"R squared - {self.as_text()}"),
        ]


def _r_squared(y, predicted) -> float:
    """How much of the variation in *y* the curve accounts for.

    Measured against the readings themselves, never against a straightened
    out version of them - see the note at the top of this module.
    """
    y = np.asarray(y, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if not np.all(np.isfinite(predicted)):
        return float("nan")
    total = float(np.sum((y - np.mean(y)) ** 2))
    unexplained = float(np.sum((y - predicted) ** 2))
    if total == 0.0:
        return 1.0 if unexplained == 0.0 else float("nan")
    return 1.0 - unexplained / total


def _finish(curve: Curve, x, y) -> Curve:
    predicted = curve.predict(x)
    curve.residuals = (np.asarray(y, dtype=float) - predicted).tolist()
    curve.r_squared = _r_squared(y, predicted)
    return curve


def _clean(xs, ys):
    x = np.asarray(list(xs), dtype=float)
    y = np.asarray(list(ys), dtype=float)
    if x.size != y.size:
        raise ParseError("The two columns are different lengths.")
    if x.size < 2:
        raise ParseError("Two points at least are needed to fit anything.")
    return x, y


def _polynomial(x, y, order: int) -> Curve:
    name = {1: "Linear", 2: "Quadratic", 3: "Cubic"}.get(
        order, f"Polynomial, order {order}")
    curve = Curve(key=f"poly{order}", name=name)
    if x.size < order + 1:
        curve.refused = (f"needs {order + 1} readings at least; "
                         f"there are {x.size}")
        return curve
    if np.allclose(x, x[0]):
        curve.refused = "every x is the same, so there is no curve to fit"
        return curve
    coefficients = np.polyfit(x, y, order)
    symbol = sp.Symbol("x")
    expression = sum(sp.Float(float(c)) * symbol ** (order - index)
                     for index, c in enumerate(coefficients))
    curve.coefficients = [float(c) for c in coefficients]
    curve.expression = sp.expand(expression)
    return _finish(curve, x, y)


def _exponential(x, y) -> Curve:
    """y = a e^(bx), fitted by taking logs of y."""
    curve = Curve(key="exponential", name="Exponential")
    if np.any(y <= 0):
        curve.refused = ("needs every y above zero - a curve of this shape "
                         "never reaches zero, so it cannot pass through one")
        return curve
    slope, intercept = np.polyfit(x, np.log(y), 1)
    symbol = sp.Symbol("x")
    curve.coefficients = [float(np.exp(intercept)), float(slope)]
    curve.expression = sp.Float(float(np.exp(intercept))) * sp.exp(
        sp.Float(float(slope)) * symbol)
    return _finish(curve, x, y)


def _logarithmic(x, y) -> Curve:
    """y = a ln(x) + b."""
    curve = Curve(key="logarithmic", name="Logarithmic")
    if np.any(x <= 0):
        curve.refused = "needs every x above zero, since ln(x) has no value there"
        return curve
    slope, intercept = np.polyfit(np.log(x), y, 1)
    symbol = sp.Symbol("x")
    curve.coefficients = [float(slope), float(intercept)]
    curve.expression = (sp.Float(float(slope)) * sp.log(symbol)
                        + sp.Float(float(intercept)))
    return _finish(curve, x, y)


def _power(x, y) -> Curve:
    """y = a x^b, fitted by taking logs of both."""
    curve = Curve(key="power", name="Power")
    if np.any(x <= 0) or np.any(y <= 0):
        curve.refused = ("needs every x and y above zero, since both are "
                         "logged to straighten the curve out")
        return curve
    slope, intercept = np.polyfit(np.log(x), np.log(y), 1)
    symbol = sp.Symbol("x")
    curve.coefficients = [float(np.exp(intercept)), float(slope)]
    curve.expression = sp.Float(float(np.exp(intercept))) * symbol ** sp.Float(
        float(slope))
    return _finish(curve, x, y)


#: Everything on offer, in the order a spreadsheet lists them.
KINDS = ("linear", "quadratic", "cubic", "exponential", "logarithmic",
         "power")


def fit_curve(kind: str, xs, ys, order: int = 2) -> Curve:
    """Fit one named shape. ``kind`` is one of :data:`KINDS`, or ``polyN``."""
    x, y = _clean(xs, ys)
    if kind == "linear":
        return _polynomial(x, y, 1)
    if kind == "quadratic":
        return _polynomial(x, y, 2)
    if kind == "cubic":
        return _polynomial(x, y, 3)
    if kind.startswith("poly"):
        wanted = int(kind[4:] or order)
        if not 1 <= wanted <= MAX_ORDER:
            raise ParseError(f"A polynomial of order {wanted} is not offered; "
                             f"1 to {MAX_ORDER} are.")
        return _polynomial(x, y, wanted)
    if kind == "exponential":
        return _exponential(x, y)
    if kind == "logarithmic":
        return _logarithmic(x, y)
    if kind == "power":
        return _power(x, y)
    raise ParseError(f"There is no {kind!r} trendline.")


def fit_all(xs, ys) -> list:
    """Every shape, best fit first, with the ones that cannot be fitted last.

    Ranked by R squared measured on the readings, so the ordering means
    something across shapes - which is the whole reason for measuring it that
    way. See the note at the top of this module.
    """
    curves = [fit_curve(kind, xs, ys) for kind in KINDS]

    def rank(curve):
        if not curve.ok:
            return (2, 0.0)
        if not np.isfinite(curve.r_squared):
            return (1, 0.0)
        return (0, -curve.r_squared)

    return sorted(curves, key=rank)


def comparison_rows(curves) -> list:
    """(name, R squared, equation) for every shape, for a table."""
    rows = []
    for curve in curves:
        if not curve.ok:
            rows.append((curve.name, "", curve.refused))
        elif not np.isfinite(curve.r_squared):
            rows.append((curve.name, "", "could not be scored"))
        else:
            rows.append((curve.name, curve.r_squared,
                         f"y = {sp.sstr(curve.shown())}"))
    return rows


def best(curves):
    """The best-fitting shape, or None when none of them could be fitted."""
    for curve in curves:
        if curve.ok and np.isfinite(curve.r_squared):
            return curve
    return None
