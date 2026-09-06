"""Reading a tensile test: the numbers a stress-strain curve is run for.

A tensile test produces a few hundred pairs of readings and four or five
numbers anybody actually wants from them - the stiffness, the stress it
yields at, the most it will take, and how far it stretches before it breaks.
Getting those off a printed curve means laying a ruler on the straight part
and reading where a line crosses it, which is exactly the sort of measuring
by eye a computer should be doing.

Two things here are worth stating because they are where the judgement is.

**Where the straight part ends is found rather than assumed.** The elastic
modulus is the slope of the initial straight run, and how much of the curve
counts as straight is the whole question - take too little and the slope is
noise, take too much and the yield rounds it off. The longest run of points
that a straight line still fits properly is used, which is what laying a
ruler on it amounts to.

**The offset yield is where the curve crosses a line, not where it bends.**
There is no corner on most curves to find. The convention is a line of the
elastic slope shifted along by 0.2% strain; where the data first crosses it
is the proof stress. That crossing is interpolated between the two readings
either side rather than rounded to the nearer one, since the readings are
usually further apart than the precision being quoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .parsing import ParseError

#: The offset a proof stress is quoted at, as a strain. 0.2% is the usual
#: one; 0.1% and 0.5% are also used and the caller can ask for either.
DEFAULT_OFFSET = 0.002

#: How well a straight line has to fit a run of points for that run to count
#: as the elastic region.
STRAIGHT_ENOUGH = 0.9995

#: The fewest points a slope may be taken from. Two points always lie on a
#: line, so a modulus from two readings says nothing about whether the
#: material has a straight part at all.
MINIMUM_POINTS = 5


class TensileError(ParseError):
    """Raised when a curve cannot be read."""


@dataclass
class Tensile:
    """What a stress-strain curve says about the material."""

    strain: np.ndarray
    stress: np.ndarray
    modulus: float = 0.0            # the slope of the straight part
    elastic_points: int = 0         # how much of the curve counted as straight
    proportional_limit: float = 0.0
    offset: float = DEFAULT_OFFSET
    proof_stress: float = float("nan")
    proof_strain: float = float("nan")
    ultimate: float = 0.0
    ultimate_strain: float = 0.0
    fracture: float = 0.0
    fracture_strain: float = 0.0
    resilience: float = 0.0         # area under the elastic part
    toughness: float = 0.0          # area under the whole curve
    notes: list = field(default_factory=list)

    @property
    def elongation(self) -> float:
        """Percent elongation at fracture."""
        return self.fracture_strain * 100.0

    def rows(self) -> list:
        """(name, value, unit) for a table, in the order a report wants."""
        return [
            ("Young's modulus", self.modulus, "same units as stress"),
            ("proportional limit", self.proportional_limit, "stress"),
            (f"proof stress ({self.offset * 100:g}% offset)",
             self.proof_stress, "stress"),
            ("strain at proof", self.proof_strain, "-"),
            ("ultimate tensile strength", self.ultimate, "stress"),
            ("strain at ultimate", self.ultimate_strain, "-"),
            ("fracture stress", self.fracture, "stress"),
            ("elongation at fracture", self.elongation, "%"),
            ("resilience", self.resilience, "stress x strain"),
            ("toughness", self.toughness, "stress x strain"),
        ]


def _r_squared(x, y, slope: float, intercept: float) -> float:
    predicted = slope * x + intercept
    total = float(np.sum((y - np.mean(y)) ** 2))
    if total == 0.0:
        return 1.0
    return 1.0 - float(np.sum((y - predicted) ** 2)) / total


def elastic_region(strain, stress) -> tuple:
    """(slope, intercept, how many points) for the initial straight run.

    Grown from the start while a straight line still fits properly. This is
    what laying a ruler along the first part of the curve amounts to, and it
    is the one judgement in the whole reading: too few points and the slope
    is noise, too many and the yield rounds it off.
    """
    count = len(strain)
    if count < MINIMUM_POINTS:
        raise TensileError(
            f"{count} readings is not enough to find a straight part; "
            f"{MINIMUM_POINTS} at least are needed.")

    best = None
    for last in range(MINIMUM_POINTS, count + 1):
        x, y = strain[:last], stress[:last]
        if np.allclose(x, x[0]):
            continue
        slope, intercept = np.polyfit(x, y, 1)
        if _r_squared(x, y, slope, intercept) >= STRAIGHT_ENOUGH:
            best = (float(slope), float(intercept), last)
        elif best is not None:
            # It was straight and has stopped being straight. Growing the
            # window further only drags the line into the curve.
            break
    if best is None:
        raise TensileError(
            "No part of this curve is straight enough to take a modulus "
            "from. Check the columns are strain then stress, and that the "
            "readings start from zero load.")
    return best


def _crossing(strain, stress, line) -> tuple:
    """Where the curve first crosses *line*, interpolated between readings.

    The readings are usually further apart than the precision being quoted,
    so rounding to the nearer one would throw away more than the
    interpolation could.
    """
    difference = stress - line
    for index in range(1, len(difference)):
        if difference[index - 1] > 0 >= difference[index]:
            before, after = difference[index - 1], difference[index]
            span = before - after
            fraction = before / span if span else 0.0
            x = strain[index - 1] + fraction * (strain[index]
                                                - strain[index - 1])
            y = stress[index - 1] + fraction * (stress[index]
                                                - stress[index - 1])
            return float(x), float(y)
    return float("nan"), float("nan")


def read_curve(strain, stress, offset: float = DEFAULT_OFFSET) -> Tensile:
    """Read a stress-strain curve. Strain is a ratio, stress whatever unit."""
    x = np.asarray(list(strain), dtype=float)
    y = np.asarray(list(stress), dtype=float)
    if x.size != y.size:
        raise TensileError("The two columns are different lengths.")
    if x.size < MINIMUM_POINTS:
        raise TensileError(
            f"{x.size} readings is not enough; {MINIMUM_POINTS} at least.")
    if np.any(np.diff(x) < 0):
        raise TensileError(
            "The strain goes backwards somewhere. The readings need to be "
            "in the order they were taken, with strain increasing.")

    result = Tensile(strain=x, stress=y, offset=offset)
    slope, intercept, points = elastic_region(x, y)
    result.modulus = slope
    result.elastic_points = points
    result.proportional_limit = float(y[points - 1])

    # The offset line: the elastic slope, shifted along by the offset strain.
    offset_line = slope * (x - offset) + intercept
    result.proof_strain, result.proof_stress = _crossing(x, y, offset_line)
    if result.proof_stress != result.proof_stress:          # nan
        result.notes.append(
            f"The curve never crosses the {offset * 100:g}% offset line, so "
            "there is no proof stress to quote. Either the test stopped "
            "inside the elastic region or the material has no yield to find.")

    peak = int(np.argmax(y))
    result.ultimate = float(y[peak])
    result.ultimate_strain = float(x[peak])
    result.fracture = float(y[-1])
    result.fracture_strain = float(x[-1])
    if peak == len(y) - 1:
        result.notes.append(
            "The highest stress is the last reading, so the specimen had not "
            "started to neck when the test stopped - the ultimate strength "
            "is at least this and may be more.")

    # Areas under the curve: energy per unit volume, by the trapezium rule.
    elastic = slice(0, points)
    result.resilience = float(np.trapezoid(y[elastic], x[elastic])) \
        if hasattr(np, "trapezoid") else float(np.trapz(y[elastic], x[elastic]))
    result.toughness = float(np.trapezoid(y, x)) \
        if hasattr(np, "trapezoid") else float(np.trapz(y, x))
    return result


def from_load_extension(extension, load, length: float, area: float,
                        offset: float = DEFAULT_OFFSET) -> Tensile:
    """Read a curve recorded as extension and load rather than strain and stress.

    Which is how a machine actually records it: millimetres and newtons. The
    gauge length and the cross-section turn one into the other.
    """
    if length <= 0 or area <= 0:
        raise TensileError(
            "The gauge length and the cross-sectional area both have to be "
            "greater than zero - they are what turn extension into strain "
            "and load into stress.")
    strain = np.asarray(list(extension), dtype=float) / float(length)
    stress = np.asarray(list(load), dtype=float) / float(area)
    return read_curve(strain, stress, offset)
