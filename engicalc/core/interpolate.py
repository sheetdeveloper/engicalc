"""Reading a value between the rows of a table.

Steam tables, pump curves, material property charts - the number you want is
almost never one of the rows, and the arithmetic to get between them is easy
to fumble under time pressure. This does it, and shows the working, because
in a report the working is the part that gets marked.

Everything returns a :class:`core.engine.CalcResult`, so the history, the
plotter and the Excel exporter all handle it without knowing what it is.

Two things it is deliberately fussy about:

* **Extrapolation is called out, loudly.** Reading past the end of a steam
  table is not interpolation, it is a guess, and a silent one is dangerous.
* **The bracketing rows are named.** Any hand check starts by asking which
  two rows were used, so the answer says so before it says anything else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import sympy as sp

from .display import fmt_number
from .engine import CalcResult
from .parsing import ParseError, parse_number
from .steps import Step

METHODS = ["linear", "polynomial", "nearest"]


@dataclass
class Table:
    """A column of x values and the y values that go with them."""

    xs: list = field(default_factory=list)
    ys: list = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.xs)

    @property
    def span(self) -> tuple:
        return (min(self.xs), max(self.xs)) if self.xs else (0.0, 0.0)

    def sorted(self) -> "Table":
        if not self.xs:
            return Table([], [])
        pairs = sorted(zip(self.xs, self.ys))
        return Table([p[0] for p in pairs], [p[1] for p in pairs])


_SPLIT = re.compile(r"[,;\t]| {2,}| (?=-?\d)")


def parse_table(text: str) -> Table:
    """Read a two-column table out of typed or pasted text.

    Accepts what actually arrives on the clipboard: two columns out of Excel
    (tab separated), a CSV, or two numbers a line typed by hand. A header row
    is skipped rather than treated as an error, because pasting one is the
    normal thing to do.
    """
    xs: list = []
    ys: list = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [p for p in _SPLIT.split(line) if p and p.strip()]
        if len(parts) < 2:
            raise ParseError(
                f"Line {line_number} has one value; two are needed: {raw!r}")
        try:
            x = float(parse_number(parts[0]))
            y = float(parse_number(parts[1]))
        except Exception:                            # noqa: BLE001
            if line_number == 1:
                continue                             # a header row - skip it
            raise ParseError(
                f"Line {line_number} is not a pair of numbers: {raw!r}") from None
        xs.append(x)
        ys.append(y)

    if len(xs) < 2:
        raise ParseError("At least two points are needed to interpolate.")
    if len(set(xs)) != len(xs):
        raise ParseError(
            "Two rows share the same x value, so there is no single answer "
            "between them.")
    return Table(xs, ys).sorted()


def _bracket(table: Table, at: float) -> tuple:
    """The two rows either side of *at*, and whether it is outside the table."""
    xs = table.xs
    if at <= xs[0]:
        return 0, 1, at < xs[0]
    if at >= xs[-1]:
        return len(xs) - 2, len(xs) - 1, at > xs[-1]
    upper = int(np.searchsorted(xs, at))
    return upper - 1, upper, False


def _linear(table: Table, at: float, result: CalcResult) -> float:
    low, high, outside = _bracket(table, at)
    x1, y1 = table.xs[low], table.ys[low]
    x2, y2 = table.xs[high], table.ys[high]
    slope = (y2 - y1) / (x2 - x1)
    value = y1 + slope * (at - x1)

    where = "beyond the end of the table" if outside else "between"
    result.steps.append(Step(
        f"The two rows {where}",
        detail=f"({fmt_number(x1)}, {fmt_number(y1)})  and  "
               f"({fmt_number(x2)}, {fmt_number(y2)})"))
    result.steps.append(Step(
        "Straight line between them",
        detail="y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)"))
    result.steps.append(Step(
        "Substitute",
        detail=f"y = {fmt_number(y1)} + ({fmt_number(at)} - {fmt_number(x1)})"
               f" * ({fmt_number(y2)} - {fmt_number(y1)})"
               f" / ({fmt_number(x2)} - {fmt_number(x1)})"))
    result.steps.append(Step(
        "Gradient over that interval",
        detail=f"{fmt_number(slope)} per unit x"))
    return value


def _nearest(table: Table, at: float, result: CalcResult) -> float:
    index = int(np.argmin([abs(x - at) for x in table.xs]))
    result.steps.append(Step(
        "Nearest row",
        detail=f"({fmt_number(table.xs[index])}, "
               f"{fmt_number(table.ys[index])})"))
    return table.ys[index]


def _polynomial(table: Table, at: float, degree: int,
                result: CalcResult) -> float:
    highest = len(table) - 1
    if degree > highest:
        result.warnings.append(
            f"A degree {degree} curve needs {degree + 1} points; using "
            f"degree {highest} instead.")
        degree = highest
    coefficients = np.polyfit(np.array(table.xs, dtype=float),
                              np.array(table.ys, dtype=float), degree)

    x = sp.Symbol("x")
    expression = sum(sp.Float(float(c)) * x ** (degree - i)
                     for i, c in enumerate(coefficients))
    expression = sp.nsimplify(expression, rational=False)
    result.expression = expression
    result.steps.append(Step(f"Least-squares fit of degree {degree}",
                             expr=sp.Eq(sp.Symbol("y"), expression)))

    fitted = np.polyval(coefficients, np.array(table.xs, dtype=float))
    residual = float(np.max(np.abs(fitted - np.array(table.ys, dtype=float))))
    result.steps.append(Step(
        "Worst gap between the curve and the data",
        detail=f"{fmt_number(residual)}"
               + ("  - the curve passes through every point"
                  if residual < 1e-9 else "")))
    return float(np.polyval(coefficients, at))


def interpolate(table: Table, at, method: str = "linear",
                degree: int = 3) -> CalcResult:
    """Find y at *at*, by *method*. Returns a :class:`CalcResult`."""
    if method not in METHODS:
        raise ParseError(f"Unknown method {method!r}.")
    if len(table) < 2:
        raise ParseError("At least two points are needed to interpolate.")

    value_at = float(parse_number(str(at)))
    table = table.sorted()
    low, high = table.span

    result = CalcResult(operation="interpolate",
                        input_text=f"{method} interpolation at x = "
                                   f"{fmt_number(value_at)}",
                        variable="x", plottable=True)
    result.steps.append(Step(
        f"{len(table)} points, x from {fmt_number(low)} to {fmt_number(high)}"))

    if value_at < low or value_at > high:
        result.warnings.append(
            f"x = {fmt_number(value_at)} is outside the data "
            f"({fmt_number(low)} to {fmt_number(high)}). This is "
            "extrapolation, not interpolation - the answer is a guess beyond "
            "where the numbers came from, and should not be trusted without "
            "a reason to believe the trend continues.")

    if method == "linear":
        value = _linear(table, value_at, result)
    elif method == "nearest":
        value = _nearest(table, value_at, result)
    else:
        value = _polynomial(table, value_at, degree, result)

    result.numeric = [value]
    result.results = [sp.Float(value)]
    result.result_text = f"y = {fmt_number(value)}  at  x = {fmt_number(value_at)}"
    # Formatted, not sp.latex'd: a Float prints as 92.0 and 75.9040000000000,
    # and neither the input nor the answer has that many figures behind it.
    result.latex = (r"y\left(" + fmt_number(value_at) + r"\right) = "
                    + fmt_number(value))
    result.assumptions = {"method": method, "at": value_at,
                          "points": len(table)}
    # Written out rather than drawn: sp.Float renders as 75.9040000000000,
    # and a trailing wall of zeros reads as precision that is not there.
    result.steps.append(Step("Answer", detail=f"y = {fmt_number(value)}"))
    return result


def reverse(table: Table, y_value, result_method: str = "linear") -> CalcResult:
    """The other direction: given y, find the x that produces it.

    Only meaningful where the data is monotonic - a curve that turns has more
    than one x for the same y, and the answer says so rather than picking one
    quietly.
    """
    table = table.sorted()
    target = float(parse_number(str(y_value)))
    ys = table.ys

    crossings = []
    for index in range(len(ys) - 1):
        low, high = ys[index], ys[index + 1]
        if (low - target) * (high - target) <= 0 and low != high:
            fraction = (target - low) / (high - low)
            crossings.append(table.xs[index] + fraction *
                             (table.xs[index + 1] - table.xs[index]))

    result = CalcResult(operation="interpolate",
                        input_text=f"x where y = {fmt_number(target)}",
                        variable="y", plottable=True)
    if not crossings:
        result.result_text = (f"No x in this table gives y = "
                              f"{fmt_number(target)}.")
        result.warnings.append(
            f"y = {fmt_number(target)} is outside the range of the data "
            f"({fmt_number(min(ys))} to {fmt_number(max(ys))}).")
        return result

    if len(crossings) > 1:
        result.warnings.append(
            f"The data crosses y = {fmt_number(target)} {len(crossings)} "
            "times, so there is more than one answer. All are listed.")
    result.numeric = crossings
    result.results = [sp.Float(c) for c in crossings]
    result.result_text = "\n".join(
        f"x = {fmt_number(c)}" for c in crossings)
    result.steps.append(Step(
        "Rows where the data crosses that value",
        detail=", ".join(f"x = {fmt_number(c)}" for c in crossings)))
    return result
