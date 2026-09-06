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
