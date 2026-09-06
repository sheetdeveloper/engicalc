"""The Moody chart: friction factor against Reynolds number.

The chart a pipe or duct calculation is read off, and the one this app's own
duct example has been quietly using a single curve from. It is three
regimes, and which one you are in matters more than the number:

* below about 2300 the flow is laminar and the friction factor is 64/Re
  exactly - a straight line on log-log paper, with no roughness in it at
  all, because a laminar flow does not feel the wall's texture;
* above about 4000 it is turbulent, and the factor comes from Colebrook,
  which has the friction factor on both sides and has to be solved rather
  than evaluated;
* between the two nothing is reliable. The transition is not a curve, it is
  a region where the answer depends on the pipe's history, and a chart that
  draws a line through it is drawing something nobody can predict.

Colebrook is solved here rather than approximated. The Swamee-Jain and
Haaland forms are within about 2% and are what a spreadsheet usually uses,
but iterating costs nothing on a modern machine and 2% of a pressure drop is
not nothing when it is the number a fan is picked from.
"""

from __future__ import annotations

import math

import numpy as np

from .parsing import ParseError

#: Where laminar flow stops being reliable, and where turbulent starts.
LAMINAR_LIMIT = 2300.0
TURBULENT_START = 4000.0

#: Relative roughnesses the chart is drawn with - the family of curves on a
#: printed Moody chart.
ROUGHNESSES = (0.0, 1e-6, 1e-5, 5e-5, 1e-4, 2e-4, 4e-4, 6e-4, 1e-3,
               2e-3, 4e-3, 6e-3, 1e-2, 1.5e-2, 2e-2, 3e-2, 4e-2, 5e-2)

#: Absolute roughness in metres for materials a duct or pipe is made of.
MATERIALS = {
    "drawn tubing, glass": 1.5e-6,
    "commercial steel": 4.5e-5,
    "galvanised steel": 1.5e-4,
    "cast iron": 2.6e-4,
    "concrete, smooth": 3.0e-4,
    "riveted steel": 3.0e-3,
    "flexible duct": 3.0e-3,
}


class MoodyError(ParseError):
    """Raised when a friction factor cannot be found."""


def laminar(reynolds: float) -> float:
    """64/Re. Exact, and the roughness does not enter it."""
    if reynolds <= 0:
        raise MoodyError("The Reynolds number has to be greater than zero.")
    return 64.0 / reynolds


def colebrook(reynolds: float, relative_roughness: float,
              tolerance: float = 1e-12, limit: int = 100) -> float:
    """Solve Colebrook for the Darcy friction factor.

    The friction factor appears on both sides, so it is found by putting a
    guess in and putting the answer back until it stops moving. The
    fully-rough value is the starting point, which is where the equation
    ends up at high Reynolds numbers and is close enough that this converges
    in a handful of passes.
    """
    if reynolds <= 0:
        raise MoodyError("The Reynolds number has to be greater than zero.")
    if relative_roughness < 0:
        raise MoodyError("Roughness cannot be less than nothing.")

    if relative_roughness > 0:
        guess = 1.0 / (-2.0 * math.log10(relative_roughness / 3.7)) ** 2
    else:
        guess = 0.02
    for _ in range(limit):
        root = math.sqrt(guess)
        right = -2.0 * math.log10(relative_roughness / 3.7
                                  + 2.51 / (reynolds * root))
        nearer = 1.0 / right ** 2
        if abs(nearer - guess) <= tolerance * max(guess, 1e-12):
            return nearer
        guess = nearer
    raise MoodyError(
        f"Colebrook did not settle for Re = {reynolds:g} and a relative "
        f"roughness of {relative_roughness:g}.")


def friction_factor(reynolds: float, relative_roughness: float = 0.0) -> tuple:
    """(factor, which regime, a note) for this flow.

    The regime is returned because it is the part worth knowing. Between
    2300 and 4000 the answer is an estimate whatever anyone quotes, and
    saying so is more use than a number that looks as firm as the others.
    """
    if reynolds <= 0:
        raise MoodyError("The Reynolds number has to be greater than zero.")
    if reynolds < LAMINAR_LIMIT:
        return laminar(reynolds), "laminar", ""
    if reynolds < TURBULENT_START:
        # Interpolated across the gap so a plotted line is continuous, and
        # flagged, because nothing here is dependable.
        low = laminar(LAMINAR_LIMIT)
        high = colebrook(TURBULENT_START, relative_roughness)
        fraction = ((reynolds - LAMINAR_LIMIT)
                    / (TURBULENT_START - LAMINAR_LIMIT))
        return (low + fraction * (high - low), "transitional",
                "Between about 2300 and 4000 the flow may be either, and "
                "which it is depends on the pipe rather than on the numbers. "
                "Treat this as an estimate; design either side of it.")
    return colebrook(reynolds, relative_roughness), "turbulent", ""


def curve(relative_roughness: float, start: float = 600.0,
          stop: float = 1e8, points: int = 400) -> tuple:
    """One roughness line across the chart, as (Re, factor) arrays."""
    reynolds = np.logspace(math.log10(start), math.log10(stop), points)
    factors = []
    for value in reynolds:
        try:
            factors.append(friction_factor(float(value),
                                           relative_roughness)[0])
        except MoodyError:
            factors.append(float("nan"))
    return reynolds, np.array(factors)


def relative_roughness(absolute: float, diameter: float) -> float:
    """Roughness as a fraction of the bore, which is what the chart uses."""
    if diameter <= 0:
        raise MoodyError("The diameter has to be greater than zero.")
    return absolute / diameter
