"""Torsion of circular shafts.

The other half of what a shaft does. A beam carries load across itself and a
shaft carries it round itself, and the two calculations look alike enough
that the same person does both: a stress that is largest at the surface and
falls linearly to nothing at the centre, and a deflection - a twist - that is
the torque times the length over the stiffness.

    tau = T r / J        theta = T L / (G J)        P = T omega

The reason this is a module of its own rather than four lines in the formula
library is the middle of a shaft. Torque is usually known as power at a
speed, the stress is wanted at the surface but the twist over the length,
and a hollow shaft carries nearly as much as a solid one at a fraction of
the weight - which is the point of the whole subject and is not visible in
any one of the equations.

One thing this deliberately refuses. The polar second moment of area is the
torsion constant *for a circular section and nothing else*. A square bar's
resistance to twist is not the sum of its two second moments, and using it
that way overstates the stiffness by about forty per cent. Non-circular
sections warp when they twist, which is a different theory; this says so
rather than returning a number from the wrong one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .parsing import ParseError

#: Torsional yield taken as a share of tensile yield, on the maximum shear
#: stress criterion. Tresca says a half; von Mises says 0.577. The lower is
#: the safe one to compare against and is what most codes use.
SHEAR_YIELD_SHARE = 0.5


class TorsionError(ParseError):
    """Raised when a shaft cannot be worked out."""


def polar_second_moment(outer: float, inner: float = 0.0) -> float:
    """J for a round bar or tube, about its own axis.

    pi(D^4 - d^4)/32. The fourth power is the whole story of shaft design:
    the metal near the axis is doing almost nothing, which is why a tube is
    so much better per kilogram than a bar.
    """
    if outer <= 0:
        raise TorsionError("A shaft has to have a diameter.")
    if inner < 0 or inner >= outer:
        raise TorsionError(
            "The bore has to be smaller than the shaft it is in.")
    return math.pi * (outer ** 4 - inner ** 4) / 32.0


@dataclass
class Shaft:
    """A round shaft in torsion, solid or hollow.

    Everything in metres, pascals and newton metres.
    """

    outer: float
    inner: float = 0.0
    length: float = 1.0
    modulus: float = 80e9          # G, and 80 GPa is steel
    torque: float = 0.0
    allowable: float = 0.0         # allowable shear stress, if there is one

    def check(self) -> None:
        if self.length <= 0:
            raise TorsionError("A shaft has to have a length.")
        if self.modulus <= 0:
            raise TorsionError("The modulus of rigidity has to be positive.")

    @property
    def j(self) -> float:
        return polar_second_moment(self.outer, self.inner)

    @property
    def area(self) -> float:
        return math.pi * (self.outer ** 2 - self.inner ** 2) / 4.0

    @property
    def polar_modulus(self) -> float:
        """J/r: torque per unit of surface stress, which is what sizes it."""
        return self.j / (self.outer / 2.0)

    def stress_at(self, radius: float) -> float:
        """Shear stress at a radius from the axis.

        Linear, and nothing at all at the centre.
        """
        return self.torque * radius / self.j

    @property
    def max_stress(self) -> float:
        return self.stress_at(self.outer / 2.0)

    @property
    def twist(self) -> float:
        """Angle of twist over the whole length, in radians."""
        self.check()
        return self.torque * self.length / (self.modulus * self.j)

    @property
    def stiffness(self) -> float:
        """Torque per radian, which is what a shaft is in a drivetrain."""
        self.check()
        return self.modulus * self.j / self.length

    def profile(self, points: int = 60) -> tuple:
        """(radius, shear stress) from the bore to the surface, for drawing."""
        start = self.inner / 2.0
        stop = self.outer / 2.0
        step = (stop - start) / max(points - 1, 1)
        radii = [start + step * index for index in range(points)]
        return radii, [self.stress_at(r) for r in radii]

    # -- what comes out of it ----------------------------------------------
    def rows(self) -> list:
        self.check()
        rows = [
            ("polar second moment J", self.j * 1e12, "mm^4"),
            ("polar section modulus J/r", self.polar_modulus * 1e9, "mm^3"),
            ("cross-sectional area", self.area * 1e6, "mm^2"),
            ("largest shear stress", self.max_stress / 1e6, "N/mm^2"),
            ("at the bore", self.stress_at(self.inner / 2.0) / 1e6,
             "N/mm^2"),
            ("angle of twist", math.degrees(self.twist), "degrees"),
            ("twist per metre", math.degrees(self.twist) / self.length,
             "deg/m"),
            ("torsional stiffness", self.stiffness / 1000.0, "kN m/rad"),
        ]
        if self.allowable > 0:
            rows.append(("factor on the allowable stress",
                         self.allowable / self.max_stress
                         if self.max_stress else float("inf"), ""))
        return rows

    def notes(self) -> list:
        said = []
        if self.allowable > 0 and self.max_stress > self.allowable:
            said.append(
                f"{self.max_stress / 1e6:.1f} N/mm2 is past the "
                f"{self.allowable / 1e6:.1f} N/mm2 allowed. The shaft needs "
                f"to be bigger, or the torque smaller.")
        if self.inner > 0:
            # The point of the whole subject, in one number.
            solid = Shaft(outer=self.outer, inner=0.0, length=self.length,
                          modulus=self.modulus, torque=self.torque)
            said.append(
                f"Hollow, it carries {self.j / solid.j:.0%} of what the same "
                f"outside diameter would carry solid, for "
                f"{self.area / solid.area:.0%} of the weight - which is why "
                f"drive shafts are tubes.")
        turn = math.degrees(self.twist) / self.length
        if turn > 1.0:
            said.append(
                f"It twists {turn:.2f} degrees per metre. A degree per metre "
                f"is the usual limit for a shaft carrying power; past that "
                f"the stiffness governs the size rather than the stress.")
        return said


# --------------------------------------------------------------------------
# Power, which is how a torque is usually known
# --------------------------------------------------------------------------
def torque_from_power(power: float, rpm: float) -> float:
    """T = P/omega, with the speed given the way a nameplate gives it."""
    if rpm == 0:
        raise TorsionError(
            "At a standstill there is no power however much torque there "
            "is, so the torque cannot be got back out of it.")
    return power / (2.0 * math.pi * rpm / 60.0)


def power_from_torque(torque: float, rpm: float) -> float:
    return torque * 2.0 * math.pi * rpm / 60.0


# --------------------------------------------------------------------------
# Sizing one
# --------------------------------------------------------------------------
def diameter_for_stress(torque: float, allowable: float,
                        bore_ratio: float = 0.0) -> float:
    """The smallest outside diameter whose surface stress is within bounds.

    *bore_ratio* is the bore as a fraction of the outside diameter, so 0 is
    solid and 0.6 is a fairly thin tube. Solved rather than iterated: the
    fourth power comes out as a cube root and there is nothing implicit
    about it.
    """
    if allowable <= 0:
        raise TorsionError("The allowable stress has to be positive.")
    if not 0.0 <= bore_ratio < 1.0:
        raise TorsionError("The bore is a fraction of the outside diameter.")
    # tau = 16 T / (pi D^3 (1 - k^4))
    return (16.0 * abs(torque)
            / (math.pi * allowable * (1.0 - bore_ratio ** 4))) ** (1.0 / 3.0)


def diameter_for_twist(torque: float, length: float, modulus: float,
                       allowable_twist: float,
                       bore_ratio: float = 0.0) -> float:
    """The smallest outside diameter that twists no more than allowed.

    *allowable_twist* in radians over the whole length.
    """
    if allowable_twist <= 0 or modulus <= 0 or length <= 0:
        raise TorsionError(
            "The length, the modulus and the allowable twist all have to be "
            "positive.")
    # theta = 32 T L / (pi G D^4 (1 - k^4))
    return (32.0 * abs(torque) * length
            / (math.pi * modulus * allowable_twist
               * (1.0 - bore_ratio ** 4))) ** 0.25


# --------------------------------------------------------------------------
# Shafts held at both ends
# --------------------------------------------------------------------------
def shared_torque(torque: float, first_length: float,
                  second_length: float) -> tuple:
    """How a torque applied part way along splits between two fixed ends.

    Statically indeterminate - two unknown reactions and one equation - and
    settled the same way a propped beam is: the two halves twist by the same
    amount at the point they meet, because they are the same piece of metal.
    That gives T1 L1 = T2 L2 and the split falls out inversely with length.

    Returns (torque carried to the near end, to the far end).
    """
    if first_length <= 0 or second_length <= 0:
        raise TorsionError("Both parts of the shaft need a length.")
    total = first_length + second_length
    # The near end takes the larger share when the torque is applied close
    # to it, which is the way round people get wrong.
    return (torque * second_length / total, torque * first_length / total)
