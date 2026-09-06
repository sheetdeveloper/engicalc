"""Shear force, bending moment and axial force along a beam.

The two diagrams every statics course is built on, and the ones people draw
wrong most often - not because the arithmetic is hard but because the
bookkeeping is: which way the reactions point, where the shear crosses zero,
whether the moment closes back to zero at the far end.

Everything here is worked from the loads by summing along the beam, so the
diagrams and the numbers beside them cannot disagree. Three checks come free
and are worth having: the shear, the moment and the axial force all have to
return to zero at the end of a beam in equilibrium, and if they do not, the
reactions were wrong rather than the drawing.

Sign convention: upward loads and reactions positive, sagging internal
moment positive, applied couples anticlockwise positive, tension positive,
distances measured from the left-hand end.

Two of those pull in opposite directions and it matters: an anticlockwise
couple applied to the left of a section hogs that section, so a couple enters
the internal moment with its sign turned round. Adding the two as though they
agreed put 30 kN m at the free end of a cantilever, where there is nothing
left to bend it.

The supports go where you put them and are whatever kind you say. A beam
held in from its ends has an overhang, the shear in the overhang is not
zero, and the moment over the support is hogging - the case worth drawing
and the one a fixed pair of supports at the ends cannot show. Which support
is the pin decides which part of the beam an inclined load pulls and which
part it pushes, so it is asked rather than assumed.

What this cannot do is say so. Everything here comes out of equilibrium, and
equilibrium settles a beam with two simple supports or one built-in end and
nothing more. A propped cantilever, a beam on three supports, two pins
sharing a thrust - all real, all common, none of them solvable without the
deflections as well. Each is refused by name.
"""

from __future__ import annotations

import math
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
    """A load at one place. Downward is negative, as drawn.

    ``along`` is the component in the direction of the beam, positive
    towards the far end, and is zero for the ordinary vertical load. An
    inclined force has both components and the axial one has to go
    somewhere: it is carried to the pinned support and shows up as a step
    in the axial force diagram.
    """

    position: float
    magnitude: float
    along: float = 0.0


def inclined(position: float, size: float, degrees: float) -> PointLoad:
    """A force of *size* leaning at *degrees* to the beam, pressing into it.

    Ninety degrees is straight down, which is the ordinary case, and zero is
    a pure push along the beam towards the far end. Angles past ninety lean
    back towards the near end, so every direction is covered by one number
    and there is no second sign convention to remember.
    """
    angle = math.radians(degrees)
    across, along = -size * math.sin(angle), size * math.cos(angle)
    # Snapped, because cos(90 degrees) is 6e-17 rather than nought and a
    # thread of axial force that thin is arithmetic, not statics. Left as it
    # was, every ordinary vertical load drew an axial force diagram of its
    # own rounding error.
    limit = abs(size) * 1e-12
    return PointLoad(position,
                     0.0 if abs(across) < limit else across,
                     0.0 if abs(along) < limit else along)


@dataclass
class Distributed:
    """A load spread from *start* to *end*, per unit length.

    Uniform unless *end_magnitude* is given, in which case it ramps
    straight from one intensity to the other - the triangle liquid pressure
    puts on a wall, or the trapezoid a sloping roof puts on a purlin.
    """

    start: float
    end: float
    magnitude: float
    end_magnitude: float | None = None

    @property
    def span(self) -> float:
        return self.end - self.start

    @property
    def finish(self) -> float:
        """The intensity at the far end - the same one if it is uniform."""
        return (self.magnitude if self.end_magnitude is None
                else self.end_magnitude)

    @property
    def slope(self) -> float:
        """How fast the intensity changes, per unit length."""
        return (0.0 if abs(self.span) < 1e-15
                else (self.finish - self.magnitude) / self.span)

    def force(self) -> float:
        """The whole load, which is the area under it."""
        return (self.magnitude + self.finish) / 2.0 * self.span

    def moment_about_left(self) -> float:
        """Its moment about the left-hand end of the beam.

        Written out rather than taken as force times centroid, because a
        trapezoid whose two ends are equal and opposite has no force and
        still has a moment, and force-times-centroid cannot say that.
        """
        length, start = self.span, self.start
        first, rate = self.magnitude, self.slope
        return (first * length ** 2 / 2.0 + rate * length ** 3 / 3.0
                + start * first * length + start * rate * length ** 2 / 2.0)


@dataclass
class Moment:
    """A couple applied at one place. Anticlockwise positive."""

    position: float
    magnitude: float


@dataclass
class Support:
    """One support, and what it is able to hold.

    A roller holds the beam up. A pin holds it up and holds it back along
    its length. A built-in end does both and stops it turning as well.

    The difference is not decoration: under an inclined load, which support
    is the pin decides which part of the beam is in tension and which in
    compression.
    """

    position: float
    kind: str = "roller"

    @property
    def holds_along(self) -> bool:
        return self.kind in ("pin", "fixed")

    @property
    def holds_turning(self) -> bool:
        return self.kind == "fixed"


@dataclass
class Beam:
    """A beam, its supports and what is on it."""

    length: float
    #: Where it is held up, and by what. Plain numbers are taken the way
    #: they always were - the left-hand one a pin and the rest rollers, or
    #: a built-in end on a cantilever - so a beam described as two distances
    #: still means what it used to.
    supports: list = field(default_factory=list)
    loads: list = field(default_factory=list)
    kind: str = "simply supported"

    @property
    def held(self) -> list:
        """The supports, sorted, with plain numbers given their usual kind."""
        made = [place for place in self.supports
                if isinstance(place, Support)]
        plain = [Support(float(place),
                         "fixed" if self.kind == "cantilever" else "roller")
                 for place in self.supports
                 if not isinstance(place, Support)]
        if plain and self.kind != "cantilever":
            # The convention when nothing was said: the left-hand support is
            # the pin, the other free to slide.
            min(plain, key=lambda s: s.position).kind = "pin"
        return sorted(made + plain, key=lambda s: s.position)

    def check(self) -> None:
        if self.length <= 0:
            raise BeamError("A beam has to have a length.")
        for support in self.held:
            if not -1e-9 <= support.position <= self.length + 1e-9:
                raise BeamError(
                    f"A support at {support.position:g} m is off the end of "
                    f"a {self.length:g} m beam.")
        for load in self.loads:
            places = ([load.position] if hasattr(load, "position")
                      else [load.start, load.end])
            for place in places:
                if not -1e-9 <= place <= self.length + 1e-9:
                    raise BeamError(
                        f"Something is loaded at {place:g} m, which is off "
                        f"the end of a {self.length:g} m beam.")
            if isinstance(load, Distributed) and load.end < load.start - 1e-12:
                raise BeamError(
                    f"A spread load from {load.start:g} m to {load.end:g} m "
                    f"runs backwards.")



@dataclass
class Diagram:
    """The shear, moment and axial force along the beam, and their peaks."""

    x: np.ndarray
    shear: np.ndarray
    moment: np.ndarray
    axial: np.ndarray | None = None
    reactions: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def _peak(self, values) -> tuple:
        index = int(np.argmax(np.abs(values)))
        return float(self.x[index]), float(values[index])

    @property
    def max_shear(self) -> tuple:
        return self._peak(self.shear)

    @property
    def max_moment(self) -> tuple:
        return self._peak(self.moment)

    @property
    def max_axial(self) -> tuple:
        if self.axial is None:
            return 0.0, 0.0
        return self._peak(self.axial)

    def rows(self) -> list:
        at_shear, shear = self.max_shear
        at_moment, moment = self.max_moment
        rows = [(f"reaction at {place:g} m", value, "N")
                for place, value in sorted(
                    (p, v) for p, v in self.reactions.items()
                    if not isinstance(p, str))]
        rows += [(_reaction_label(place), value,
                  "N m" if "moment" in place else "N")
                 for place, value in sorted(
                     (p, v) for p, v in self.reactions.items()
                     if isinstance(p, str))]
        rows += [("largest shear", shear, f"N, at {at_shear:g} m"),
                 ("largest moment", moment, f"N m, at {at_moment:g} m")]
        at_axial, axial = self.max_axial
        if axial:
            rows.append(("largest axial force", axial,
                         f"N, at {at_axial:g} m "
                         f"({'tension' if axial > 0 else 'compression'})"))
        return rows


def _reaction_label(key: str) -> str:
    """`moment at 1` reads as what it is when it is written out."""
    for prefix, said in (("moment at ", "fixing moment at"),
                         ("axial at ", "axial reaction at")):
        if key.startswith(prefix):
            return f"{said} {key[len(prefix):]} m"
    return key


def _totals(beam: Beam) -> tuple:
    """The load on the beam summed up: force, moment about x = 0, axial."""
    total_load = 0.0
    total_moment = 0.0            # about the left-hand end
    total_along = 0.0
    for load in beam.loads:
        if isinstance(load, PointLoad):
            total_load += load.magnitude
            total_moment += load.magnitude * load.position
            total_along += load.along
        elif isinstance(load, Distributed):
            total_load += load.force()
            total_moment += load.moment_about_left()
        elif isinstance(load, Moment):
            total_moment += load.magnitude
    return total_load, total_moment, total_along


def _reactions(beam: Beam) -> dict:
    """Solve the supports from equilibrium.

    Three equations - the forces sum to zero across and along, and the
    moments about a point sum to zero - which is exactly enough for two
    supports one of which is pinned, or for one support that is built in.
    """
    total_load, total_moment, total_along = _totals(beam)
    held = beam.held
    built_in = [support for support in held if support.holds_turning]
    simple = [support for support in held if not support.holds_turning]

    # Which support takes the thrust. More than one and equilibrium cannot
    # say how they share it, which only matters when there is a thrust.
    holding = [support for support in held if support.holds_along]
    if total_along and len(holding) > 1:
        raise BeamError(
            "Two supports that both hold the beam back along its length "
            "share the thrust between them in a way equilibrium cannot "
            "settle. Make one of them a roller.")
    if total_along and not holding:
        raise BeamError(
            "Nothing holds the beam back along its length, so a force "
            "leaning at an angle would push it off its supports. Make one "
            "of them a pin.")

    if built_in:
        if len(built_in) > 1 or simple:
            raise BeamError(
                "A beam built in at one end and held anywhere else has more "
                "unknowns than equilibrium has equations - it is statically "
                "indeterminate, and these diagrams are worked from "
                "equilibrium alone. Make the built-in end a pin, or take "
                "the other support away.")
        wall = built_in[0].position
        # The wall carries whatever is left over: force, moment and thrust.
        found = {wall: -total_load,
                 f"moment at {wall:g}": -(total_moment - total_load * wall)}
        if total_along:
            found[f"axial at {wall:g}"] = -total_along
        return found

    if len(simple) < 2:
        raise BeamError(
            "A beam resting on one support is a mechanism - it turns about "
            "it rather than carrying anything. Hold it in a second place, "
            "or build the end in.")
    if len(simple) > 2:
        raise BeamError(
            f"{len(simple)} supports is more than equilibrium can solve "
            f"for; two is the most a statically determinate beam has. "
            f"Continuous beams need the deflections as well.")
    left, right = simple[0].position, simple[1].position
    if abs(right - left) < 1e-12:
        raise BeamError("The two supports are in the same place.")
    # Moments about the left support.
    right_reaction = -(total_moment - total_load * left) / (right - left)
    left_reaction = -total_load - right_reaction
    found = {left: left_reaction, right: right_reaction}
    if total_along:
        found[f"axial at {holding[0].position:g}"] = -total_along
    return found


def analyse(beam: Beam) -> Diagram:
    """Work the shear, moment and axial force out along the beam."""
    beam.check()
    reactions = _reactions(beam)
    x = np.linspace(0.0, beam.length, POINTS)
    shear = np.zeros_like(x)
    moment = np.zeros_like(x)
    thrust = np.zeros_like(x)     # forces along the beam, summed from the left

    def apply_force(at: float, size: float) -> None:
        past = x >= at - 1e-12
        shear[past] += size
        moment[past] += size * (x[past] - at)

    for place, value in reactions.items():
        if isinstance(place, str):          # the wall's fixing moment
            continue
        apply_force(float(place), value)
    built_in = [support for support in beam.held if support.holds_turning]
    if built_in:
        wall = built_in[0].position
        fixing = reactions.get(f"moment at {wall:g}", 0.0)
        # Turned round: the couple is anticlockwise-positive, the moment
        # being accumulated is sagging-positive, and the wall hogs the beam.
        moment[x >= wall - 1e-12] -= fixing
    for place, value in reactions.items():
        if isinstance(place, str) and place.startswith("axial at "):
            thrust[x >= float(place[len("axial at "):]) - 1e-12] += value

    for load in beam.loads:
        if isinstance(load, PointLoad):
            apply_force(load.position, load.magnitude)
            if load.along:
                thrust[x >= load.position - 1e-12] += load.along
        elif isinstance(load, Moment):
            moment[x >= load.position - 1e-12] -= load.magnitude
        elif isinstance(load, Distributed):
            # Integrated along the part of the beam it covers, rather than
            # lumped at its centre - lumping gives the right reactions and
            # the wrong shape between them.
            #
            # `covered` is how much of the load lies left of the section and
            # `reach` is how far the section is beyond where the load began.
            # They are the same while the section is inside the load and part
            # ways once it is past the end of it, which is exactly where the
            # moment used to go wrong: a load over part of a beam went on
            # accumulating as though the section were still under it, and the
            # diagram finished at 80 kN m on a beam that closes at zero.
            covered = np.clip(x - load.start, 0.0, max(load.span, 0.0))
            reach = np.maximum(x - load.start, 0.0)
            first, rate = load.magnitude, load.slope
            shear += first * covered + rate * covered ** 2 / 2.0
            moment += (first * (reach * covered - covered ** 2 / 2.0)
                       + rate * (reach * covered ** 2 / 2.0
                                 - covered ** 3 / 3.0))

    axial = -thrust               # tension positive, taking the left portion
    diagram = Diagram(x=x, shear=shear, moment=moment, axial=axial,
                      reactions=reactions)

    # All three have to come back to zero at the far end of a beam in
    # equilibrium. If they do not, the reactions were wrong, and saying so
    # is more use than a drawing that looks plausible.
    scale = max(float(np.max(np.abs(shear))), 1.0)
    if abs(shear[-1]) > CLOSES * scale:
        diagram.notes.append(
            f"The shear does not close to zero at the end - it finishes at "
            f"{shear[-1]:.4g} N. The beam is not in equilibrium as described.")
    scale = max(float(np.max(np.abs(moment))), 1.0)
    if not built_in and abs(moment[-1]) > CLOSES * scale:
        diagram.notes.append(
            f"The moment does not close to zero at the end - it finishes at "
            f"{moment[-1]:.4g} N m.")
    scale = max(float(np.max(np.abs(axial))), 1.0)
    if abs(axial[-1]) > CLOSES * scale:
        diagram.notes.append(
            f"The axial force does not close to zero at the end - it "
            f"finishes at {axial[-1]:.4g} N.")
    return diagram
