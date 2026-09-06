"""Columns: when a strut stops carrying load by being strong enough.

A short column fails by squashing and a long one fails by bending sideways
long before it squashes. The second is the one that catches people out,
because it happens at a load the material could carry twice over and it
happens suddenly.

Euler settles the long case exactly:

    P = pi^2 E I / Le^2

and the whole subject is knowing where it stops applying. Euler is derived
for a perfectly straight column of perfectly uniform material loaded
perfectly down its axis. Below a slenderness of about pi root(E/sigma_y) it
predicts a stress higher than the material can reach at all, which is not a
conservative error - it is an answer for a column that would have squashed
before it got there.

So three curves are given rather than one. Euler, which is right at the
slender end and nonsense at the stocky end; the material's own yield, which
is right at the stocky end and nonsense at the slender end; and Perry-
Robertson between them, which is the shape every steel code uses and which
allows for the column being slightly bent to begin with. Real columns follow
the third.

Everything here is in newtons and millimetres, to match the section module -
so a second moment in mm^4 and a modulus in N/mm^2 give a load in newtons.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .parsing import ParseError

#: How much of the length actually bends, for each way of holding the ends.
#: Theoretical values. Codes use higher ones for real construction, because
#: a joint drawn as fixed is never quite fixed - a fixed-fixed column is
#: usually designed at 0.65 rather than 0.5.
END_CONDITIONS = {
    "pinned both ends": 1.0,
    "fixed both ends": 0.5,
    "fixed one end, pinned the other": 0.6992,
    "fixed one end, free at the other": 2.0,
}

#: Robertson's constant in the Perry-Robertson formula. It stands for the
#: column not being straight to begin with, and it is why a real column
#: never reaches either of the two curves it sits between.
ROBERTSON = 0.003


class BucklingError(ParseError):
    """Raised when a column cannot be worked out."""


@dataclass
class Column:
    """A strut, and the three answers for what it will carry."""

    area: float                 # mm^2
    second_moment: float        # mm^4, about the axis it bends about
    length: float               # mm
    modulus: float = 210e3      # N/mm^2
    yield_stress: float = 275.0  # N/mm^2
    ends: str = "pinned both ends"
    load: float = 0.0           # N, what it is being asked to carry

    def check(self) -> None:
        if self.area <= 0 or self.second_moment <= 0:
            raise BucklingError("A column needs an area and a stiffness.")
        if self.length <= 0:
            raise BucklingError("A column has to have a length.")
        if self.modulus <= 0 or self.yield_stress <= 0:
            raise BucklingError(
                "The modulus and the yield stress both have to be positive.")
        if self.ends not in END_CONDITIONS:
            raise BucklingError(
                f"'{self.ends}' is not one of the ways of holding the ends: "
                + ", ".join(END_CONDITIONS))

    @property
    def factor(self) -> float:
        """K: how much of the length is free to bend."""
        return END_CONDITIONS[self.ends]

    @property
    def effective_length(self) -> float:
        return self.factor * self.length

    @property
    def radius_of_gyration(self) -> float:
        return math.sqrt(self.second_moment / self.area)

    @property
    def slenderness(self) -> float:
        """Le/r, which is the only thing about the shape that matters here.

        Two columns with the same slenderness behave the same way whatever
        they are made of and whatever section they are - which is why the
        whole subject is drawn against this one number.
        """
        self.check()
        return self.effective_length / self.radius_of_gyration

    @property
    def transition(self) -> float:
        """The slenderness where Euler's answer first reaches yield.

        Below it Euler predicts a stress the material cannot reach, so
        below it Euler is not merely inaccurate - it is describing a
        failure that cannot happen.
        """
        return math.pi * math.sqrt(self.modulus / self.yield_stress)

    # -- the three curves ---------------------------------------------------
    def euler_stress(self, slenderness: float = None) -> float:
        ratio = self.slenderness if slenderness is None else slenderness
        if ratio <= 0:
            return float("inf")
        return math.pi ** 2 * self.modulus / ratio ** 2

    def perry_stress(self, slenderness: float = None) -> float:
        """Perry-Robertson: the curve real columns follow.

        It is what you get by assuming the column starts slightly bent, so
        that bending and squashing happen together from the first newton
        rather than the column staying straight until it suddenly does not.
        """
        ratio = self.slenderness if slenderness is None else slenderness
        elastic = self.euler_stress(ratio)
        if not math.isfinite(elastic):
            return self.yield_stress
        bend = ROBERTSON * ratio
        middle = (self.yield_stress + (bend + 1.0) * elastic) / 2.0
        inside = middle ** 2 - self.yield_stress * elastic
        below = middle + math.sqrt(max(inside, 0.0))
        # Written as the conjugate rather than as `middle - sqrt(...)`,
        # which is how it is always quoted and which subtracts two very
        # large nearly equal numbers on a stocky column: at a slenderness
        # near nothing the elastic stress is 1e18 and the product under the
        # root is sixteen orders below m^2, so the answer came out 256
        # where it has to be the yield stress. This form only ever adds.
        if below <= 0:
            return self.yield_stress
        return self.yield_stress * elastic / below

    def rankine_stress(self, slenderness: float = None) -> float:
        """Rankine-Gordon: the two failures added as if they were resistances.

        1/P = 1/P_squash + 1/P_Euler, which is older and cruder than
        Perry-Robertson and has the merit of being obviously right at both
        ends. It is still what a lot of courses teach first.
        """
        ratio = self.slenderness if slenderness is None else slenderness
        constant = self.yield_stress / (math.pi ** 2 * self.modulus)
        return self.yield_stress / (1.0 + constant * ratio ** 2)

    # -- what it will carry -------------------------------------------------
    @property
    def euler_load(self) -> float:
        return self.euler_stress() * self.area

    @property
    def squash_load(self) -> float:
        return self.yield_stress * self.area

    @property
    def perry_load(self) -> float:
        return self.perry_stress() * self.area

    @property
    def rankine_load(self) -> float:
        return self.rankine_stress() * self.area

    @property
    def regime(self) -> str:
        """Which end of the subject this column is at."""
        ratio = self.slenderness
        if ratio < 0.5 * self.transition:
            return "stocky - it will squash rather than buckle"
        if ratio < 1.2 * self.transition:
            return "in between - neither curve describes it on its own"
        return "slender - Euler governs and it will buckle elastically"

    def curve(self, points: int = 240) -> tuple:
        """(slenderness, Euler, yield, Perry-Robertson) for drawing."""
        top = max(2.5 * self.transition, 1.4 * self.slenderness, 200.0)
        ratios = [top * (index + 1) / points for index in range(points)]
        return (ratios,
                [self.euler_stress(r) for r in ratios],
                [self.yield_stress for _r in ratios],
                [self.perry_stress(r) for r in ratios])

    def rows(self) -> list:
        self.check()
        rows = [
            ("effective length", self.effective_length / 1000.0, "m"),
            ("radius of gyration", self.radius_of_gyration, "mm"),
            ("slenderness Le/r", self.slenderness, ""),
            ("slenderness where Euler reaches yield", self.transition, ""),
            ("squash load", self.squash_load / 1000.0, "kN"),
            ("Euler load", self.euler_load / 1000.0, "kN"),
            ("Rankine-Gordon load", self.rankine_load / 1000.0, "kN"),
            ("Perry-Robertson load", self.perry_load / 1000.0, "kN"),
            ("Perry-Robertson stress", self.perry_stress(), "N/mm^2"),
        ]
        if self.load > 0:
            rows.append(("factor against Perry-Robertson",
                         self.perry_load / self.load, ""))
        return rows

    def notes(self) -> list:
        self.check()
        said = [f"Slenderness {self.slenderness:.0f}: {self.regime}."]

        if self.slenderness < self.transition:
            said.append(
                f"Euler gives {self.euler_stress():.0f} N/mm2 here, which is "
                f"more than the {self.yield_stress:.0f} N/mm2 the material "
                f"can reach at all - so below a slenderness of "
                f"{self.transition:.0f} it is not a safe answer but a "
                f"meaningless one.")
        if self.load > 0:
            factor = self.perry_load / self.load
            if factor < 1.0:
                said.append(
                    f"It will not carry {self.load / 1000.0:.4g} kN. "
                    f"Perry-Robertson puts it at "
                    f"{self.perry_load / 1000.0:.4g} kN.")
            elif factor < 1.5:
                said.append(
                    f"A factor of {factor:.2f} on the buckling load is not "
                    f"much for a column. Buckling gives no warning and no "
                    f"reserve past the peak.")
        if self.ends == "fixed one end, free at the other":
            said.append(
                "A column free at one end is twice as slender as its length "
                "suggests, which is why a free-standing post is the worst "
                "case of the four.")
        return said


def slenderness_for(load: float, area: float, modulus: float,
                    yield_stress: float) -> float:
    """The most slender a column may be and still carry *load*.

    Solved on the Perry-Robertson curve by bisection, because that curve
    cannot be turned round algebraically - which is the one inconvenience
    of using the curve real columns follow.
    """
    if load <= 0:
        raise BucklingError("The load has to be positive.")
    column = Column(area=area, second_moment=1.0, length=1.0,
                    modulus=modulus, yield_stress=yield_stress)
    if column.perry_stress(1e-6) * area < load:
        raise BucklingError(
            "Even a stocky column of that area cannot carry it - the "
            "material would squash first, whatever the length.")
    low, high = 1e-6, 1000.0
    for _step in range(200):
        middle = 0.5 * (low + high)
        if column.perry_stress(middle) * area > load:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)
