"""Shear force and bending moment along a beam.

The two diagrams every statics course is built on, and the ones people draw
wrong most often - not because the arithmetic is hard but because the
bookkeeping is: which way the reactions point, where the shear crosses zero,
whether the moment closes back to zero at the far end.

Everything here is worked from the loads by summing along the beam, so the
diagrams and the numbers beside them cannot disagree. Two checks come free
and are worth having: the shear and the moment both have to return to zero
at the end of a beam in equilibrium, and if they do not, the reactions were
wrong rather than the drawing.

Sign convention: upward loads and reactions positive, sagging internal
moment positive, applied couples anticlockwise positive, distances measured
from the left-hand end.

Those last two pull in opposite directions and it matters: an anticlockwise
couple applied to the left of a section hogs that section, so a couple enters
the internal moment with its sign turned round. Adding the two as though they
agreed put 30 kN m at the free end of a cantilever, where there is nothing
left to bend it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .parsing import ParseError

#: How many points the diagrams are worked out at. Enough that a
#: parabola under a distributed load reads as a curve.
POINTS = 601

#: How far from zero the closing shear or moment may be, relative to the
#: largest value on the diagram, before something is wrong.
CLOSES = 1e-6


class BeamError(ParseError):
    """Raised when a beam cannot be worked out."""


@dataclass
class PointLoad:
    """A load at one place. Downward is negative, as drawn."""

    position: float
    magnitude: float


@dataclass
class Distributed:
    """A load spread evenly from *start* to *end*, per unit length."""

    start: float
    end: float
    magnitude: float


@dataclass
class Moment:
    """A couple applied at one place. Anticlockwise positive."""

    position: float
    magnitude: float


@dataclass
class Beam:
    """A beam, its supports and what is on it."""

    length: float
    #: Where it is held up. Two for simply supported; one, at the wall, for
    #: a cantilever.
    supports: list = field(default_factory=list)
    loads: list = field(default_factory=list)
    kind: str = "simply supported"

    def check(self) -> None:
        if self.length <= 0:
            raise BeamError("A beam has to have a length.")
        for load in self.loads:
            places = ([load.position] if hasattr(load, "position")
                      else [load.start, load.end])
            for place in places:
                if not -1e-9 <= place <= self.length + 1e-9:
                    raise BeamError(
                        f"Something is loaded at {place:g} m, which is off "
                        f"the end of a {self.length:g} m beam.")


@dataclass
class Diagram:
    """The shear and moment along the beam, and what they peak at."""

    x: np.ndarray
    shear: np.ndarray
    moment: np.ndarray
    reactions: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def max_shear(self) -> tuple:
        index = int(np.argmax(np.abs(self.shear)))
        return float(self.x[index]), float(self.shear[index])

    @property
    def max_moment(self) -> tuple:
        index = int(np.argmax(np.abs(self.moment)))
        return float(self.x[index]), float(self.moment[index])

    def rows(self) -> list:
        at_shear, shear = self.max_shear
        at_moment, moment = self.max_moment
        rows = [(f"reaction at {place:g} m", value, "N")
                for place, value in sorted(self.reactions.items())]
        rows += [("largest shear", shear, f"N, at {at_shear:g} m"),
                 ("largest moment", moment, f"N m, at {at_moment:g} m")]
        return rows


def _reactions(beam: Beam) -> dict:
    """Solve the supports from equilibrium.

    Two equations - the forces sum to zero and the moments about a point
    sum to zero - which is exactly enough for two supports, or for one
    support that also carries a moment.
    """
    total_load = 0.0
    total_moment = 0.0            # about the left-hand end
    for load in beam.loads:
        if isinstance(load, PointLoad):
            total_load += load.magnitude
            total_moment += load.magnitude * load.position
        elif isinstance(load, Distributed):
            span = load.end - load.start
            force = load.magnitude * span
            total_load += force
            total_moment += force * (load.start + span / 2.0)
        elif isinstance(load, Moment):
            total_moment += load.magnitude

    if beam.kind == "cantilever":
        if len(beam.supports) != 1:
            raise BeamError("A cantilever is held at one place.")
        wall = beam.supports[0]
        # The wall carries whatever is left over, force and moment both.
        return {wall: -total_load, f"moment at {wall:g}": -(
            total_moment - total_load * wall)}

    if len(beam.supports) != 2:
        raise BeamError(
            "A simply supported beam rests on two supports; say where they "
            "are.")
    left, right = sorted(beam.supports)
    if abs(right - left) < 1e-12:
        raise BeamError("The two supports are in the same place.")
    # Moments about the left support.
    right_reaction = -(total_moment - total_load * left) / (right - left)
    left_reaction = -total_load - right_reaction
    return {left: left_reaction, right: right_reaction}


def analyse(beam: Beam) -> Diagram:
    """Work the shear and moment out along the beam."""
    beam.check()
    reactions = _reactions(beam)
    x = np.linspace(0.0, beam.length, POINTS)
    shear = np.zeros_like(x)
    moment = np.zeros_like(x)

    def apply_force(at: float, size: float) -> None:
        past = x >= at - 1e-12
        shear[past] += size
        moment[past] += size * (x[past] - at)

    for place, value in reactions.items():
        if isinstance(place, str):          # the wall's fixing moment
            continue
        apply_force(float(place), value)
    if beam.kind == "cantilever":
        wall = beam.supports[0]
        fixing = reactions.get(f"moment at {wall:g}", 0.0)
        # Turned round: the couple is anticlockwise-positive, the moment
        # being accumulated is sagging-positive, and the wall hogs the beam.
        moment[x >= wall - 1e-12] -= fixing

    for load in beam.loads:
        if isinstance(load, PointLoad):
            apply_force(load.position, load.magnitude)
        elif isinstance(load, Moment):
            moment[x >= load.position - 1e-12] -= load.magnitude
        elif isinstance(load, Distributed):
            # Integrated along the part of the beam it covers, rather than
            # lumped at its centre - lumping gives the right reactions and
            # the wrong shape between them.
            inside = (x > load.start) & (x <= load.end)
            covered = np.clip(x - load.start, 0.0, load.end - load.start)
            shear += load.magnitude * covered
            moment += load.magnitude * covered ** 2 / 2.0
            del inside

    diagram = Diagram(x=x, shear=shear, moment=moment, reactions=reactions)

    # Both have to come back to zero at the far end of a beam in
    # equilibrium. If they do not, the reactions were wrong, and saying so
    # is more use than a drawing that looks plausible.
    scale = max(float(np.max(np.abs(shear))), 1.0)
    if abs(shear[-1]) > CLOSES * scale:
        diagram.notes.append(
            f"The shear does not close to zero at the end - it finishes at "
            f"{shear[-1]:.4g} N. The beam is not in equilibrium as described.")
    scale = max(float(np.max(np.abs(moment))), 1.0)
    if beam.kind != "cantilever" and abs(moment[-1]) > CLOSES * scale:
        diagram.notes.append(
            f"The moment does not close to zero at the end - it finishes at "
            f"{moment[-1]:.4g} N m.")
    return diagram
