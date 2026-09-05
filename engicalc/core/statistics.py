"""Describing measured data, and fitting a line through it.

Every lab report needs the same few numbers - how many readings, the mean,
the spread, and if there are two columns, the line through them and how well
it fits. Doing that by hand is tedious and the standard deviation is easy to
get subtly wrong.

Two distinctions this is careful about, because both are marked and both are
commonly muddled:

* **Sample against population standard deviation.** Measurements are a sample
  of what the apparatus could have produced, so the divisor is n-1, not n.
  Both are reported, with the sample one first, because quoting the wrong one
  is a real and invisible error.
* **R² is not a measure of correctness.** It says how much of the variation
  the line accounts for, not whether a line was the right thing to fit. A
  curve through the same points can give a high R² and a wrong model, so the
  residuals are reported too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import sympy as sp

from .display import fmt_number
from .parsing import ParseError, parse_number

_SPLIT = re.compile(r"[,;\t]| {2,}| (?=-?[\d.])")


@dataclass
class Columns:
    """One or two columns of numbers read from pasted text."""

    x: list = field(default_factory=list)
    y: list = field(default_factory=list)

    @property
    def paired(self) -> bool:
        return bool(self.y) and len(self.y) == len(self.x)


def parse_columns(text: str) -> Columns:
    """Read one or two columns out of typed or pasted text.

    One number a line is a set of readings. Two is a relationship. A header
    row is skipped rather than treated as an error, because pasting one out
    of a spreadsheet is the normal thing to do.
    """
    xs: list = []
    ys: list = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [p for p in _SPLIT.split(line) if p and p.strip()]
        try:
            values = [float(parse_number(p)) for p in parts]
        except Exception:                             # noqa: BLE001
            if number == 1:
                continue                              # a header row
            raise ParseError(
                f"Line {number} is not a number: {raw!r}") from None
        if not values:
            continue
        xs.append(values[0])
        if len(values) > 1:
            ys.append(values[1])

    if not xs:
        raise ParseError("No numbers here.")
    if ys and len(ys) != len(xs):
        raise ParseError(
            "Some lines have two values and some have one, so the columns do "
            "not pair up.")
    return Columns(xs, ys)


@dataclass
class Description:
    """The usual summary of one column of readings."""

    count: int
    mean: float
    median: float
    sample_sd: float
    population_sd: float
    minimum: float
    maximum: float
    total: float

    @property
    def spread(self) -> float:
        return self.maximum - self.minimum

    @property
    def standard_error(self) -> float:
        """How well the mean itself is pinned down by this many readings."""
        return self.sample_sd / np.sqrt(self.count) if self.count else 0.0

    def rows(self) -> list:
        """``(label, value, note)`` for display, in the order they are read."""
        return [
            ("readings", self.count, ""),
            ("mean", self.mean, ""),
            ("median", self.median, "the middle reading"),
            ("standard deviation", self.sample_sd,
             "sample, divisor n-1 - measurements are a sample"),
            ("population sd", self.population_sd,
             "divisor n; only if these are the whole population"),
            ("standard error", self.standard_error,
             "how well the mean itself is pinned down"),
            ("smallest", self.minimum, ""),
            ("largest", self.maximum, ""),
            ("range", self.spread, ""),
            ("sum", self.total, ""),
        ]


def describe(values) -> Description:
    data = np.asarray(list(values), dtype=float)
    if data.size == 0:
        raise ParseError("No readings to describe.")
    return Description(
        count=int(data.size),
        mean=float(np.mean(data)),
        median=float(np.median(data)),
        # ddof=1 is the sample standard deviation. numpy defaults to 0, which
        # is the population one and the wrong default for measurements.
        sample_sd=float(np.std(data, ddof=1)) if data.size > 1 else 0.0,
        population_sd=float(np.std(data)),
        minimum=float(np.min(data)),
        maximum=float(np.max(data)),
        total=float(np.sum(data)))


@dataclass
class Fit:
    """A straight line through paired readings, and how well it fits."""

    slope: float
    intercept: float
    r: float
    r_squared: float
    slope_error: float
    intercept_error: float
    residuals: list
    count: int

    @property
    def worst_residual(self) -> float:
        return float(np.max(np.abs(self.residuals))) if len(self.residuals) \
            else 0.0

    def equation(self):
        x = sp.Symbol("x")
        return sp.Float(self.slope) * x + sp.Float(self.intercept)

    def as_text(self) -> str:
        sign = "+" if self.intercept >= 0 else "-"
        return (f"y = {fmt_number(self.slope, 6)} x {sign} "
                f"{fmt_number(abs(self.intercept), 6)}")

    def rows(self) -> list:
        return [
            ("slope", self.slope, f"+/- {fmt_number(self.slope_error, 4)}"),
            ("intercept", self.intercept,
             f"+/- {fmt_number(self.intercept_error, 4)}"),
            ("R squared", self.r_squared,
             "how much of the variation the line accounts for"),
            ("correlation r", self.r, ""),
            ("worst residual", self.worst_residual,
             "the furthest any reading sits from the line"),
        ]


def fit_line(xs, ys) -> Fit:
    """Least-squares straight line, with the uncertainty on its coefficients."""
    x = np.asarray(list(xs), dtype=float)
    y = np.asarray(list(ys), dtype=float)
    if x.size != y.size:
        raise ParseError("The two columns are different lengths.")
    if x.size < 2:
        raise ParseError("Two points at least are needed to fit a line.")
    if np.allclose(x, x[0]):
        raise ParseError(
            "Every x is the same, so there is no line to fit - only a "
            "vertical one, which this cannot express.")

    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residuals = y - predicted

    total_variation = float(np.sum((y - np.mean(y)) ** 2))
    unexplained = float(np.sum(residuals ** 2))
    r_squared = 1.0 - unexplained / total_variation if total_variation else 1.0
    correlation = float(np.corrcoef(x, y)[0, 1]) if x.size > 1 else 0.0

    # Standard errors of the coefficients: the residual variance shared out
    # over the spread in x. With two points the line is exact and there is no
    # spare information to estimate an uncertainty from.
    degrees = x.size - 2
    if degrees > 0:
        residual_variance = unexplained / degrees
        spread = float(np.sum((x - np.mean(x)) ** 2))
        slope_error = float(np.sqrt(residual_variance / spread))
        intercept_error = float(np.sqrt(
            residual_variance * (1.0 / x.size + np.mean(x) ** 2 / spread)))
    else:
        slope_error = intercept_error = 0.0

    return Fit(float(slope), float(intercept), correlation, float(r_squared),
               slope_error, intercept_error, residuals.tolist(), int(x.size))
