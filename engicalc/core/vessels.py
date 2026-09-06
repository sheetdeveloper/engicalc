"""Pressure vessels: cylinders and spheres, thin walled and thick.

The thin-walled answers are two of the most useful lines in the subject:

    cylinder    hoop = p r / t        along = p r / 2t
    sphere      both  = p r / 2t

A cylinder is twice as stressed round its circumference as along its length,
which is why a sausage splits lengthways and why the seam weld on a boiler
drum is the one that matters. A sphere at the same pressure and thickness
carries half the stress of a cylinder, which is why gas is stored in spheres
and why nobody makes a spherical pipe.

Those hold while the wall is thin enough that the stress does not vary much
through it. When it is not, the hoop stress at the bore is higher than the
thin formula says and the radial stress is not nought - it is minus the
pressure - and Lame's equations give both properly:

    sigma_r = A - B/r^2        sigma_theta = A + B/r^2

The two constants come from the pressure at each surface. Everything here
gives both answers and the difference between them, because the interesting
question is not what the thick answer is but at what thickness the thin one
stops being good enough.

Newtons and millimetres throughout, so a pressure in N/mm^2 - which is a
megapascal, and near enough ten bar - gives a stress in N/mm^2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .mohr import tresca_of, von_mises_of
from .parsing import ParseError

#: The wall-to-radius ratio below which the thin-walled answer is normally
#: accepted. It is a convention rather than a discovery, and this reports
#: the real error rather than leaning on it.
THIN_ENOUGH = 0.1


class VesselError(ParseError):
    """Raised when a vessel cannot be worked out."""


@dataclass
class Vessel:
    """A cylinder or a sphere under pressure, inside and out."""

    inner_radius: float           # mm
    thickness: float              # mm
    pressure: float               # N/mm^2, inside
    outside_pressure: float = 0.0  # N/mm^2
    shape: str = "cylinder"       # or "sphere"
    closed: bool = True           # do the ends carry the pressure?
    yield_stress: float = 0.0     # N/mm^2, if there is one

    def check(self) -> None:
        if self.inner_radius <= 0:
            raise VesselError("A vessel has to have a bore.")
        if self.thickness <= 0:
            raise VesselError("A wall has to have a thickness.")
        if self.shape not in ("cylinder", "sphere"):
            raise VesselError("A vessel here is a cylinder or a sphere.")

    @property
    def outer_radius(self) -> float:
        return self.inner_radius + self.thickness

    @property
    def mean_radius(self) -> float:
        return self.inner_radius + self.thickness / 2.0

    @property
    def ratio(self) -> float:
        """Wall over radius, which is the only thing that decides thin."""
        return self.thickness / self.mean_radius

    # -- the thin-walled answers -------------------------------------------
    @property
    def thin_hoop(self) -> float:
        net = self.pressure - self.outside_pressure
        share = 1.0 if self.shape == "cylinder" else 2.0
        return net * self.mean_radius / (share * self.thickness)

    @property
    def thin_along(self) -> float:
        """Along the axis.

        A sphere has no axis, so it is the same both ways.
        """
        if self.shape == "sphere":
            return self.thin_hoop
        if not self.closed:
            # An open-ended cylinder - a pipe with expansion joints, a gun
            # barrel - carries nothing along its length at all.
            return 0.0
        net = self.pressure - self.outside_pressure
        return net * self.mean_radius / (2.0 * self.thickness)

    # -- Lame, which is the honest one --------------------------------------
    def _constants(self) -> tuple:
        inner, outer = self.inner_radius, self.outer_radius
        power = 2 if self.shape == "cylinder" else 3
        first, second = inner ** power, outer ** power
        bottom = second - first
        if bottom <= 0:
            raise VesselError("The outside has to be bigger than the bore.")
        along = (self.pressure * first - self.outside_pressure * second)
        return along / bottom, ((self.pressure - self.outside_pressure)
                                * first * second / bottom)

    def hoop_at(self, radius: float) -> float:
        """Hoop stress at a radius, from Lame."""
        first, second = self._constants()
        if self.shape == "cylinder":
            return first + second / radius ** 2
        return first + second / (2.0 * radius ** 3)

    def radial_at(self, radius: float) -> float:
        """Radial stress at a radius. Minus the pressure at the bore."""
        first, second = self._constants()
        power = 2 if self.shape == "cylinder" else 3
        return first - second / radius ** power

    @property
    def along(self) -> float:
        """The stress along the axis, which the ends put there."""
        if self.shape == "sphere":
            return 0.0        # a sphere has no separate axial stress
        if not self.closed:
            return 0.0
        return self._constants()[0]

    def principals_at(self, radius: float) -> tuple:
        """The three principal stresses, which at any radius are the axes.

        A vessel is the tidiest triaxial state there is: hoop, radial and
        axial are already principal, because there is no shear on any of
        those planes by symmetry.
        """
        if self.shape == "sphere":
            hoop = self.hoop_at(radius)
            return hoop, hoop, self.radial_at(radius)
        return self.hoop_at(radius), self.along, self.radial_at(radius)

    def equivalent_at(self, radius: float) -> tuple:
        """(Tresca, von Mises) at a radius."""
        return (tresca_of(*self.principals_at(radius)),
                von_mises_of(*self.principals_at(radius)))

    # -- what comes out -----------------------------------------------------
    def profile(self, points: int = 120) -> tuple:
        """(radius, hoop, radial) through the wall, for drawing."""
        step = self.thickness / (points - 1)
        radii = [self.inner_radius + step * index for index in range(points)]
        return (radii, [self.hoop_at(r) for r in radii],
                [self.radial_at(r) for r in radii])

    def rows(self) -> list:
        self.check()
        bore = self.inner_radius
        tresca, mises = self.equivalent_at(bore)
        rows = [
            ("outside radius", self.outer_radius, "mm"),
            ("wall over mean radius", self.ratio, ""),
            ("thin wall: hoop stress", self.thin_hoop, "N/mm^2"),
            ("thin wall: stress along", self.thin_along, "N/mm^2"),
            ("Lame: hoop at the bore", self.hoop_at(bore), "N/mm^2"),
            ("Lame: hoop at the outside", self.hoop_at(self.outer_radius),
             "N/mm^2"),
            ("Lame: radial at the bore", self.radial_at(bore), "N/mm^2"),
            ("Lame: stress along", self.along, "N/mm^2"),
            ("Tresca at the bore", tresca, "N/mm^2"),
            ("von Mises at the bore", mises, "N/mm^2"),
        ]
        if self.thin_hoop:
            rows.append(("thin wall understates the hoop by",
                         (self.hoop_at(bore) / self.thin_hoop - 1.0) * 100.0,
                         "%"))
        if self.yield_stress > 0:
            rows.append(("factor on Tresca",
                         self.yield_stress / tresca if tresca else
                         float("inf"), ""))
            rows.append(("factor on von Mises",
                         self.yield_stress / mises if mises else
                         float("inf"), ""))
        return rows

    def notes(self) -> list:
        self.check()
        said = []
        error = ((self.hoop_at(self.inner_radius) / self.thin_hoop - 1.0)
                 * 100.0 if self.thin_hoop else 0.0)
        if self.ratio > THIN_ENOUGH:
            said.append(
                f"The wall is {self.ratio:.2f} of the mean radius, which is "
                f"past the tenth where the thin-walled answer is normally "
                f"accepted. It understates the hoop stress at the bore by "
                f"{error:.1f}% here.")
        else:
            said.append(
                f"Thin walled at {self.ratio:.3f} of the mean radius: the "
                f"simple answer is {error:+.2f}% from Lame's.")

        if self.shape == "cylinder" and self.closed:
            said.append(
                "A cylinder is twice as stressed round as along, which is "
                "why a seam that runs lengthways is the one that matters "
                "and why a sausage splits the way it does.")
        if self.shape == "cylinder":
            sphere = Vessel(inner_radius=self.inner_radius,
                            thickness=self.thickness,
                            pressure=self.pressure, shape="sphere")
            said.append(
                f"A sphere of the same bore and wall would see "
                f"{sphere.thin_hoop:.4g} N/mm2 rather than "
                f"{self.thin_hoop:.4g} - half of it - which is why gas is "
                f"stored in spheres.")
        if self.yield_stress > 0:
            _tresca, mises = self.equivalent_at(self.inner_radius)
            if mises > self.yield_stress:
                said.append(
                    f"von Mises at the bore is {mises:.4g} N/mm2 against a "
                    f"yield of {self.yield_stress:.4g}. The bore yields "
                    f"first and it yields from the inside out.")
        return said


def thickness_for(pressure: float, inner_radius: float, allowable: float,
                  shape: str = "cylinder") -> float:
    """The wall a vessel needs, from the thin-walled equation.

    Turned round rather than iterated, and deliberately the thin-walled one
    - it is what a first sizing uses, and this then says how far out it is
    once the number has been put back in.
    """
    if allowable <= 0:
        raise VesselError("The allowable stress has to be positive.")
    share = 1.0 if shape == "cylinder" else 2.0
    # hoop = p r_mean / (share t) with r_mean = ri + t/2, solved for t.
    return pressure * inner_radius / (share * allowable
                                      - pressure / 2.0)
