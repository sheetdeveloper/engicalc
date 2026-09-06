"""Mohr's circle: the same stress state seen from every angle.

A stress state written on one set of axes is the same state written on any
other, and the circle is what makes that obvious - every pair of axes is a
point on it, the principal stresses are where it crosses the axis, and the
worst shear is its radius. Drawing it is how the relationship stops being
three formulae to memorise.

All of it is exact. There is no fitting here and nothing iterative: the
centre is the average direct stress, the radius follows from Pythagoras, and
the angles come straight out of an arctangent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def tresca_of(first: float, second: float, third: float = 0.0) -> float:
    """The largest difference between any two of three principal stresses.

    Between *any* two, which is the part people drop. A state with both
    in-plane stresses the same sign is governed by the larger of them
    against the third, not by the gap between the two.
    """
    return max(first, second, third) - min(first, second, third)


def von_mises_of(first: float, second: float, third: float = 0.0) -> float:
    """The equivalent stress, from the sum of the squared differences.

    Written in full rather than in the plane stress form, because the plane
    stress form is this with a zero substituted and a vessel does not have
    a zero to substitute.
    """
    return math.sqrt(((first - second) ** 2 + (second - third) ** 2
                      + (third - first) ** 2) / 2.0)


#: The two rosettes anybody uses, and the angles their gauges sit at.
ROSETTES = {
    "rectangular, 0-45-90": (0.0, 45.0, 90.0),
    "delta, 0-60-120": (0.0, 60.0, 120.0),
}


def strains_from_rosette(readings, angles) -> tuple:
    """(ex, ey, gxy) from three gauge readings at three angles.

    Solved as a three-by-three system. The two special formulae quoted for
    the two common rosettes are this with those angles substituted and the
    algebra done, so doing it this way covers a rosette at any angles at all
    and cannot disagree with them.
    """
    if len(readings) != 3 or len(angles) != 3:
        raise ValueError("A rosette has three gauges at three angles.")
    rows, wanted = [], []
    for strain, degrees in zip(readings, angles):
        angle = math.radians(degrees)
        rows.append([math.cos(angle) ** 2, math.sin(angle) ** 2,
                     math.sin(angle) * math.cos(angle)])
        wanted.append(float(strain))
    try:
        across, up, shear = np.linalg.solve(np.array(rows),
                                            np.array(wanted))
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Those three angles do not settle the strain - two of the "
            "gauges are measuring the same direction, so the third reading "
            "has nothing to work against.") from exc
    return float(across), float(up), float(shear)


def stress_from_strain(across: float, up: float, shear: float,
                       modulus: float, poisson: float) -> "Mohr":
    """Hooke's law in two dimensions, which is not Hooke's law in one.

    Pulling a plate along x makes it thinner along y, so the stress along x
    depends on the strain along y as well as the strain along x. Using E on
    its own instead of E/(1 - nu^2) gives an answer about ten per cent light
    and entirely plausible.
    """
    if modulus <= 0:
        raise ValueError("The modulus has to be positive.")
    if not -1.0 < poisson < 0.5:
        raise ValueError(
            "Poisson's ratio runs from just above -1 to 0.5; a material at "
            "0.5 does not change volume at all and nothing is past it.")
    factor = modulus / (1.0 - poisson * poisson)
    return Mohr(sigma_x=factor * (across + poisson * up),
                sigma_y=factor * (up + poisson * across),
                tau_xy=modulus / (2.0 * (1.0 + poisson)) * shear)


def from_rosette(readings, angles, modulus: float,
                 poisson: float) -> "Mohr":
    """The stress state three gauges at three angles are reporting."""
    across, up, shear = strains_from_rosette(readings, angles)
    return stress_from_strain(across, up, shear, modulus, poisson)


def principal_strains(across: float, up: float, shear: float) -> tuple:
    """(larger, smaller, angle in degrees) - Mohr's circle for strain.

    The same construction as for stress, with one difference that catches
    everybody: the circle is drawn against half the shear strain, not the
    whole of it. Engineering shear strain is the whole change of angle and
    the tensor quantity is half of it.
    """
    middle = (across + up) / 2.0
    radius = math.hypot((across - up) / 2.0, shear / 2.0)
    return (middle + radius, middle - radius,
            0.5 * math.degrees(math.atan2(shear, across - up)))


@dataclass
class Mohr:
    """A plane stress state, and everything the circle says about it."""

    sigma_x: float
    sigma_y: float
    tau_xy: float

    @property
    def centre(self) -> float:
        """The average direct stress - where the circle sits on the axis."""
        return (self.sigma_x + self.sigma_y) / 2.0

    @property
    def radius(self) -> float:
        """Half the difference, and the shear, by Pythagoras."""
        return math.hypot((self.sigma_x - self.sigma_y) / 2.0, self.tau_xy)

    @property
    def sigma_1(self) -> float:
        """The larger principal stress."""
        return self.centre + self.radius

    @property
    def sigma_2(self) -> float:
        """The smaller principal stress."""
        return self.centre - self.radius

    @property
    def tau_max(self) -> float:
        """The largest shear in the plane - the radius, by definition."""
        return self.radius

    @property
    def theta_p(self) -> float:
        """Degrees to turn the axes to reach the principal directions.

        Halved because a turn of the axes moves twice as far round the
        circle - which is the whole trick of the construction and the thing
        people most often drop.
        """
        difference = self.sigma_x - self.sigma_y
        if abs(difference) < 1e-15 and abs(self.tau_xy) < 1e-15:
            return 0.0
        return math.degrees(math.atan2(2.0 * self.tau_xy, difference)) / 2.0

    @property
    def theta_s(self) -> float:
        """Degrees to the planes of greatest shear - 45 from the principals."""
        return self.theta_p - 45.0

    def at_angle(self, degrees: float) -> tuple:
        """(direct, shear) on axes turned *degrees* from the originals."""
        angle = math.radians(2.0 * degrees)
        return (self.centre
                + (self.sigma_x - self.sigma_y) / 2.0 * math.cos(angle)
                + self.tau_xy * math.sin(angle),
                -(self.sigma_x - self.sigma_y) / 2.0 * math.sin(angle)
                + self.tau_xy * math.cos(angle))

    def circle(self, points: int = 361) -> tuple:
        """The circle itself, as (direct, shear) arrays for drawing."""
        angles = np.linspace(0.0, 2.0 * math.pi, points)
        return (self.centre + self.radius * np.cos(angles),
                self.radius * np.sin(angles))

    # -- is it too much? ---------------------------------------------------
    @property
    def sigma_3(self) -> float:
        """The third principal stress, which for plane stress is nought.

        Worth writing down rather than leaving implied. Both criteria below
        are three-dimensional, and the whole difference between the plane
        stress forms and the general ones is remembering that the missing
        one is zero rather than absent.
        """
        return 0.0

    @property
    def tresca(self) -> float:
        """The largest difference between any two principal stresses.

        Not between the two in the plane - between any two of the three,
        and the third is zero. That is the part people drop: a state with
        both principal stresses the same sign is governed by the larger of
        them against zero, not by the gap between them.
        """
        return tresca_of(self.sigma_1, self.sigma_2, self.sigma_3)

    @property
    def von_mises(self) -> float:
        """The equivalent stress: root of the sum of the squared differences.

        For plane stress this is sqrt(s1^2 - s1 s2 + s2^2), which is the
        form usually quoted, but it is written out in full here because the
        full form is the one that is actually true and the plane stress form
        is it with a zero substituted.
        """
        return von_mises_of(self.sigma_1, self.sigma_2, self.sigma_3)

    def factors(self, yield_stress: float) -> dict:
        """How far each criterion says this state is from yielding."""
        if yield_stress <= 0:
            raise ValueError("The yield stress has to be positive.")
        return {
            "Tresca": yield_stress / self.tresca if self.tresca else
            float("inf"),
            "von Mises": yield_stress / self.von_mises if self.von_mises
            else float("inf"),
        }

    def failure_rows(self, yield_stress: float = 0.0) -> list:
        rows = [("Tresca equivalent stress", self.tresca, ""),
                ("von Mises equivalent stress", self.von_mises, "")]
        if yield_stress > 0:
            found = self.factors(yield_stress)
            rows.append(("factor on Tresca", found["Tresca"], ""))
            rows.append(("factor on von Mises", found["von Mises"], ""))
        return rows

    def failure_notes(self, yield_stress: float = 0.0) -> list:
        said = []
        if self.von_mises > 0:
            gap = self.tresca / self.von_mises
            said.append(
                f"Tresca is {gap:.3f} times von Mises here. It is never "
                f"less, which is what makes it the safe one to use, and "
                f"never more than 1.155 times - at pure shear, where the "
                f"two disagree most.")
        if yield_stress > 0:
            found = self.factors(yield_stress)
            if found["Tresca"] < 1.0:
                said.append(
                    f"Tresca says it has already yielded: an equivalent "
                    f"stress of {self.tresca:.4g} against a yield of "
                    f"{yield_stress:.4g}.")
            elif found["von Mises"] < 1.0:
                said.append(
                    f"von Mises says it has yielded and Tresca does not, "
                    f"which puts it between the two criteria - the band "
                    f"where the answer depends on which one you believe.")
        return said

    def tresca_locus(self, yield_stress: float) -> tuple:
        """The hexagon, in principal stress space.

        Six sides because there are six ways for two of the three principal
        stresses to be the extreme pair, and the third being zero is what
        makes the corners.
        """
        corners = [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
                   (-1.0, 0.0), (-1.0, -1.0), (0.0, -1.0), (1.0, 0.0)]
        return ([x * yield_stress for x, _y in corners],
                [y * yield_stress for _x, y in corners])

    def mises_locus(self, yield_stress: float, points: int = 361) -> tuple:
        """The ellipse through the hexagon's corners.

        s1^2 - s1 s2 + s2^2 = sy^2 is an ellipse at forty-five degrees, and
        it is drawn by walking that angle rather than solved for, because
        the parametric form is exact and a solved one has two branches.
        """
        first, second = [], []
        for index in range(points):
            angle = 2.0 * math.pi * index / (points - 1)
            # The ellipse's own axes lie along s1 = s2 and s1 = -s2.
            along = math.sqrt(2.0) * yield_stress * math.cos(angle)
            across = math.sqrt(2.0 / 3.0) * yield_stress * math.sin(angle)
            first.append((along + across) / math.sqrt(2.0))
            second.append((along - across) / math.sqrt(2.0))
        return first, second

    def rows(self) -> list:
        return [
            ("sigma 1", self.sigma_1, "the larger principal stress"),
            ("sigma 2", self.sigma_2, "the smaller principal stress"),
            ("tau max", self.tau_max, "largest shear in this plane"),
            ("centre", self.centre, "average direct stress"),
            ("radius", self.radius, ""),
            ("theta to principal", self.theta_p, "degrees"),
            ("theta to max shear", self.theta_s, "degrees"),
        ]
