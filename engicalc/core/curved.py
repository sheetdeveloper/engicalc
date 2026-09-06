"""Bending a bar that was curved to start with.

A crane hook, a C-clamp, the link of a chain, the frame of a punch press.
Bend a straight beam and the stress goes linearly across the depth with
nothing at the centroid. Bend a curved one and neither is true.

The reason is short. When the bar rotates through a small angle, every
fibre changes length by the same amount - but the fibres on the inside of
the curve were shorter to begin with, so the same change is a bigger
strain. Stress goes as strain, so the stress is higher on the inside than
the linear answer says and lower on the outside, and it is a hyperbola in
the radius rather than a straight line in the depth.

Two consequences, and they are what the tab exists to show:

**The neutral axis is not at the centroid.** It moves in toward the centre
of curvature, to the radius where the area divided by the radius averages
out - and that shift, small as it is, is the whole of the difference.

**The inside stress can be far higher than a straight-beam calculation
gives.** For a hook whose radius is about the depth of its section it is
half as much again, and it is the inside that a hook is judged on. Using
My/I there is not conservative; it is optimistic, which is the wrong
direction to be wrong in.

As the radius grows the two answers converge, and this says by how much.
Past about eight times the depth the difference is a couple of per cent and
the straight-beam formula is what anybody would use.

The formulation is Winkler's. Everything is in newtons and millimetres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .parsing import ParseError
from .sections import SectionError


class CurvedError(ParseError):
    """Raised when a curved bar cannot be worked out."""


#: Past this ratio of radius to depth the curved and straight answers are
#: within a couple of per cent, and the tab says so rather than leaving
#: somebody to work out whether the extra arithmetic bought anything.
STRAIGHT_ENOUGH = 8.0


@dataclass
class Curved:
    """A curved bar of a given section, bent and possibly pulled as well.

    ``radius`` is to the centroid of the section, and ``moment`` is
    positive when it tends to straighten the bar - which is what a load on
    a crane hook does, and which puts the inside fibre into tension.
    ``normal`` is a direct force through the centroid, positive in tension;
    a hook has one and a pure bending example does not.
    """

    section: object
    radius: float
    moment: float = 0.0
    normal: float = 0.0

    def check(self) -> None:
        found = self.section.properties()
        depth = found.bounds[3] - found.bounds[2]
        inner = self.radius - (found.cy - found.bounds[2])
        if self.radius <= 0:
            raise CurvedError("The radius has to be more than zero.")
        if inner <= 0:
            raise CurvedError(
                f"With a radius of {self.radius:g} to the centroid, the "
                f"inside of a section {depth:g} deep would be at or past "
                f"the centre of curvature. The radius has to be more than "
                f"half the depth.")

    # -- the geometry ------------------------------------------------------
    def properties(self) -> "Answer":
        self.check()
        found = self.section.properties()
        area = found.area
        try:
            over_radius = self.section.over_radius(self.radius)
        except SectionError as exc:
            raise CurvedError(str(exc)) from exc
        if over_radius <= 0:
            raise CurvedError(
                "The section integrates to nothing over the radius, which "
                "means the holes take away more than the shape puts in.")

        neutral = area / over_radius
        shift = self.radius - neutral
        inner = self.radius - (found.cy - found.bounds[2])
        outer = self.radius + (found.bounds[3] - found.cy)
        depth = outer - inner

        if shift <= 0:
            raise CurvedError(
                "The neutral axis came out at or outside the centroid, "
                "which cannot happen on a real section - it always moves "
                "toward the centre of curvature. Check the section.")

        return Answer(curved=self, area=area, second=found.ixx,
                      neutral=neutral, shift=shift, inner=inner,
                      outer=outer, depth=depth,
                      centroid_y=found.cy, bounds=found.bounds)


@dataclass
class Answer:
    """A curved bar worked out, and the straight answer beside it."""

    curved: Curved
    area: float
    second: float
    neutral: float
    shift: float
    inner: float
    outer: float
    depth: float
    centroid_y: float
    bounds: tuple

    @property
    def slenderness(self) -> float:
        """Radius over depth. How curved it actually is."""
        return self.curved.radius / self.depth

    def stress_at(self, radius: float) -> float:
        """The stress in the fibre at *radius*, bending and direct.

        Winkler: sigma = M (R_n - r) / (A e r), with the direct force
        added on. Nothing here is linear in the depth, which is the point.
        """
        if radius <= 0:
            raise CurvedError("A fibre cannot be at a radius of nothing.")
        bending = (self.curved.moment * (self.neutral - radius)
                   / (self.area * self.shift * radius))
        return bending + self.curved.normal / self.area

    def straight_at(self, radius: float) -> float:
        """What a straight-beam calculation would have said there.

        Kept beside the real answer rather than left to be worked out
        somewhere else, because the whole question a curved-beam
        calculation answers is how much this one is wrong by.
        """
        away = radius - self.curved.radius
        return (-self.curved.moment * away / self.second
                + self.curved.normal / self.area)

    @property
    def inner_stress(self) -> float:
        return self.stress_at(self.inner)

    @property
    def outer_stress(self) -> float:
        return self.stress_at(self.outer)

    def factor(self, radius: float) -> float:
        """How many times the straight-beam answer the real one is."""
        straight = self.straight_at(radius)
        if abs(straight) < 1e-12:
            return float("nan")
        return self.stress_at(radius) / straight

    def profile(self, steps: int = 200) -> tuple:
        """(radii, real stresses, straight-beam stresses) across the depth."""
        radii = [self.inner + (self.outer - self.inner) * i / (steps - 1)
                 for i in range(steps)]
        return (radii, [self.stress_at(r) for r in radii],
                [self.straight_at(r) for r in radii])

    # -- what the numbers add up to ---------------------------------------
    def balances(self) -> tuple:
        """(net force, moment about the centroid, and the scale of both).

        The scale is the total of the pushing and the pulling, ignoring
        which way each goes. It is there because the first two are
        differences of large numbers that nearly cancel - on a beam in
        pure bending two hundred kilonewtons of tension cancels two
        hundred of compression - and a residual of a few thousandths of a
        newton is only meaningful said against that.

        The check that the distribution is the right one rather than
        merely a plausible curve: the stresses have to carry exactly the
        direct force that was applied and exactly the moment, and neither
        is put in by hand. Integrated over the real section, so a hole or
        a flange counts the way it actually does.

        About the centroid, not the neutral axis. About the neutral axis a
        direct force has a moment of its own - it acts at the centroid,
        which is not there - so the answer would come back short by N
        times the shift, correctly and confusingly. About the centroid it
        is exactly the moment that was asked for, whatever else is going
        on.
        """
        offset = self.curved.radius - self.centroid_y
        low, high = self.bounds[2], self.bounds[3]
        steps = 4000
        step = (high - low) / steps
        force = moment = scale = 0.0
        for index in range(steps):
            level = low + (index + 0.5) * step
            width = self.section_width(level)
            if width <= 0:
                continue
            radius = offset + level
            area = width * step
            stress = self.stress_at(radius)
            force += stress * area
            moment += stress * (self.curved.radius - radius) * area
            scale += abs(stress) * area
        return force, moment, scale

    def section_width(self, level: float) -> float:
        return self.curved.section.width_at(level)

    def rows(self) -> list:
        rows = [
            ("area", self.area, "mm^2"),
            ("radius to the centroid", self.curved.radius, "mm"),
            ("radius to the neutral axis", self.neutral, "mm"),
            ("the neutral axis moves in by", self.shift, "mm"),
            ("inner radius", self.inner, "mm"),
            ("outer radius", self.outer, "mm"),
            ("radius over depth", self.slenderness, ""),
            ("stress, inside fibre", self.inner_stress, "N/mm^2"),
            ("stress, outside fibre", self.outer_stress, "N/mm^2"),
            ("straight beam, inside", self.straight_at(self.inner),
             "N/mm^2"),
            ("straight beam, outside", self.straight_at(self.outer),
             "N/mm^2"),
        ]
        for where, radius in (("inside", self.inner), ("outside", self.outer)):
            factor = self.factor(radius)
            if factor == factor:
                rows.append((f"times straight, {where}", factor, ""))
        return rows

    def notes(self) -> list:
        said = []
        biggest = max((abs(self.inner_stress), "inside"),
                      (abs(self.outer_stress), "outside"))[1]
        inner_factor = self.factor(self.inner)
        if inner_factor == inner_factor and inner_factor > 1.02:
            said.append(
                f"The inside fibre carries {inner_factor:.2f} times what a "
                f"straight-beam calculation gives, and it is the worst "
                f"stressed of the two. Using M y / I there is not "
                f"conservative - it is optimistic.")
        if self.slenderness > STRAIGHT_ENOUGH:
            said.append(
                f"The radius is {self.slenderness:.1f} times the depth, so "
                f"the curved and straight answers are within a couple of "
                f"per cent of each other and there is little in it.")
        else:
            said.append(
                f"The radius is {self.slenderness:.1f} times the depth. "
                f"The neutral axis has moved {self.shift:.4g} mm in from "
                f"the centroid, and the stress across the section is a "
                f"hyperbola rather than a straight line.")
        said.append(f"The {biggest} fibre is the one to size on.")
        return said
