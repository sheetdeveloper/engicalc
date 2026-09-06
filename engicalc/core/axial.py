"""Bars held at both ends, and what heating them does.

A bar that is free to move and a bar that is not are different problems,
and the second is the one that catches people out. Heat a steel bar lying
on a bench and it gets longer and carries no force. Heat the same bar
between two walls and it gets no longer at all and carries a force that
does not depend on how long it is - a metre or a kilometre, the stress is
the same, because the strain that was prevented is the same.

Two arrangements, which are the two ways bars are put together:

**In series** - a stepped bar, or several bars end to end, each with its own
size and material, with loads applied where they meet. One redundant if
both ends are held, none if one end is free.

**In parallel** - a bolt through a sleeve, a concrete column with steel in
it, three hangers carrying one beam. They share the load in proportion to
their stiffnesses and they all stretch by the same amount, which is the
condition that makes it solvable.

The gap is worth having rather than assuming zero. A bar left a millimetre
short of the wall carries nothing until it has grown that millimetre, and
then behaves as if it were held - so the answer is genuinely one thing or
the other, and which one is not decided by the person setting the problem.

Everything is in newtons and millimetres, so a modulus is in N/mm2, an area
in mm2 and a stress in N/mm2. Expansion coefficients are in millionths per
kelvin, which is how they are quoted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .parsing import ParseError


class AxialError(ParseError):
    """Raised when a bar arrangement cannot be worked out."""


#: How a support behaves. The three are genuinely different and conflating
#: any two of them gives a wrong answer that looks reasonable:
#:
#:   fixed   attached to it. It can pull as well as push, so the end goes
#:           nowhere whatever happens.
#:   free    nothing there. The bar moves as much as it likes and heating
#:           it puts no force in it at all.
#:   wall    something it can only push against. It carries nothing until
#:           the bar has grown far enough to touch, and nothing again if
#:           the load would pull the bar away from it.
HELD = ("fixed", "free", "wall")


@dataclass
class Bar:
    """One length of one material with one cross-section."""

    length: float                  # mm
    area: float                    # mm^2
    modulus: float                 # N/mm^2
    expansion: float = 0.0         # 1e-6 / K
    rise: float = 0.0              # K, this bar's own temperature change
    name: str = ""

    def check(self) -> None:
        if self.length <= 0:
            raise AxialError(f"{self.label()}: the length has to be more "
                             f"than zero.")
        if self.area <= 0:
            raise AxialError(f"{self.label()}: the area has to be more than "
                             f"zero.")
        if self.modulus <= 0:
            raise AxialError(f"{self.label()}: the modulus has to be more "
                             f"than zero.")

    def label(self) -> str:
        return self.name or "bar"

    @property
    def stiffness(self) -> float:
        """AE/L - the force it takes to stretch this bar by one millimetre."""
        return self.area * self.modulus / self.length

    @property
    def free_growth(self) -> float:
        """How much longer it would get if nothing were stopping it."""
        return self.expansion * 1e-6 * self.rise * self.length

    def stretch(self, force: float) -> float:
        """How much longer it gets carrying *force*, heating included."""
        return force / self.stiffness + self.free_growth

    def stress(self, force: float) -> float:
        return force / self.area


@dataclass
class Series:
    """Bars end to end, with loads where they meet.

    Joints are numbered from zero at the left. Bar *i* runs from joint *i*
    to joint *i+1*, and ``loads[j]`` is the force applied at joint *j*,
    positive to the right. The two ends are supports.
    """

    bars: list
    loads: list = field(default_factory=list)
    left: str = "fixed"
    right: str = "fixed"
    #: How far the right-hand end is from a wall before it touches it.
    #: Only means anything when that end is a wall; an end that is fixed
    #: is attached to where it already is.
    gap: float = 0.0

    def check(self) -> None:
        if not self.bars:
            raise AxialError("There are no bars yet.")
        for bar in self.bars:
            bar.check()
        for end in (self.left, self.right):
            if end not in HELD:
                raise AxialError(f"A support is fixed or free, not {end!r}.")
        if self.left == "free" and self.right in ("free", "wall"):
            raise AxialError(
                "Nothing is holding it. A wall can only push, so a bar with "
                "a free end and a wall at the other would move off rather "
                "than carry anything. Fix one of them.")
        if self.gap < 0:
            raise AxialError(
                "A gap is how far the end is from the wall, so it is not "
                "negative. A bar already pressed against a wall is one with "
                "no gap and a force in it.")
        if self.gap and self.right != "wall":
            raise AxialError(
                "A gap only means something against a wall. An end that is "
                "fixed is attached to where it already is, and one that is "
                "free never touches anything.")

    def _applied(self) -> list:
        """The loads, padded out to one per joint."""
        wanted = len(self.bars) + 1
        given = list(self.loads) + [0.0] * wanted
        return given[:wanted]

    def _forces_from(self, reaction: float) -> list:
        """The force in each bar, given the reaction at the left end.

        Tension positive, and *reaction* is what the left support pushes
        the bar with, rightwards. Push the left end right while the right
        end is held and the bar is in compression, which is why the sign
        goes the way it does - and why a heated bar between two walls
        comes out negative.
        """
        loads = self._applied()
        forces, running = [], -reaction
        for index in range(len(self.bars)):
            running -= loads[index]
            forces.append(running)
        return forces

    def _movement(self, reaction: float) -> float:
        """How far the right-hand end moves, for a given left reaction."""
        return sum(bar.stretch(force) for bar, force
                   in zip(self.bars, self._forces_from(reaction)))

    def _closing(self, wanted: float) -> float:
        """The left reaction that leaves the right end at *wanted*.

        The movement is linear in the reaction - every bar is - so this is
        one division rather than a search.
        """
        free_end = self._movement(0.0)
        flexibility = self._movement(1.0) - free_end
        if abs(flexibility) < 1e-15:
            raise AxialError(
                "The bars are infinitely stiff, so no arrangement of forces "
                "moves the end to where it has to be.")
        return (wanted - free_end) / flexibility

    def solve(self) -> "Answer":
        self.check()
        loads = self._applied()

        if self.right == "free" or self.left == "free":
            # One end carries nothing, so statics alone gives it.
            reaction = -sum(loads) if self.right == "free" else 0.0
            touching = False
            note = ("One end is free, so the bars move as much as they like "
                    "and heating them puts no force in them at all.")
        elif self.right == "wall":
            # A wall can only push, so the question is whether the end
            # arrives at it. Asked of the bar with that support taken
            # away - which means the *right* reaction is nothing, not the
            # left one, or the released bar would not be in equilibrium.
            released = -sum(loads)
            free_end = self._movement(released)
            if free_end <= self.gap + 1e-12:
                reaction = released
                touching = False
                if free_end < -1e-12:
                    note = (f"The end moves {-free_end:.4g} mm away from the "
                            f"wall, so the wall carries nothing at all.")
                else:
                    note = (f"The end moves {free_end:.4g} mm and the wall "
                            f"is {self.gap:.4g} mm away, so it never gets "
                            f"there. Nothing is restraining it.")
            else:
                reaction = self._closing(self.gap)
                touching = True
                note = ""
        else:
            # Attached at both ends, so the end goes nowhere at all - it
            # can be pulled back as readily as pushed. One redundant, and
            # releasing the right support and putting back the force that
            # closes the gap is the whole of the force method.
            reaction = self._closing(0.0)
            touching = True
            note = ""

        forces = self._forces_from(reaction)
        stretches = [bar.stretch(force)
                     for bar, force in zip(self.bars, forces)]
        movement = [0.0]
        for one in stretches:
            movement.append(movement[-1] + one)
        return Answer(bars=self.bars, forces=forces, stretches=stretches,
                      movement=movement, reactions=(reaction,
                                                    -reaction - sum(loads)),
                      touching=touching, note=note)


@dataclass
class Parallel:
    """Bars side by side, sharing one load and stretching together.

    A bolt through a sleeve, a concrete column with reinforcement in it,
    three hangers under one beam. The condition that makes it solvable is
    that they all end up the same length, so the stiff one takes most of
    the load and the one that wants to grow most gets pushed back by the
    others.
    """

    bars: list
    load: float = 0.0

    def check(self) -> None:
        if not self.bars:
            raise AxialError("There are no bars yet.")
        for bar in self.bars:
            bar.check()
        lengths = {round(bar.length, 9) for bar in self.bars}
        if len(lengths) > 1:
            raise AxialError(
                "Bars side by side have to start the same length, or they "
                "are not sharing anything. Different lengths in one load "
                "path is the series arrangement.")

    def solve(self) -> "Answer":
        self.check()
        # Sum of forces is the load, and every bar ends the same length.
        # Writing each force as k(delta - growth) and adding them gives the
        # movement straight out, with no matrix needed.
        total = sum(bar.stiffness for bar in self.bars)
        wanted = self.load + sum(bar.stiffness * bar.free_growth
                                 for bar in self.bars)
        movement = wanted / total
        forces = [bar.stiffness * (movement - bar.free_growth)
                  for bar in self.bars]
        note = ""
        if any(bar.rise for bar in self.bars) and abs(self.load) < 1e-12:
            # The interesting case: no load at all, and forces anyway.
            pulling = [bar.label() for bar, force in zip(self.bars, forces)
                       if force > 0]
            pushing = [bar.label() for bar, force in zip(self.bars, forces)
                       if force < 0]
            if pulling and pushing:
                note = (f"No load on it, and forces in it anyway. "
                        f"{', '.join(pushing)} would grow more than the rest "
                        f"and {', '.join(pulling)} holds it back, so one is "
                        f"in compression and the other in tension and they "
                        f"add to nothing.")
        return Answer(bars=self.bars, forces=forces,
                      stretches=[movement] * len(self.bars),
                      movement=[movement], reactions=(-self.load, 0.0),
                      touching=True, note=note)


@dataclass
class Answer:
    """What came out, in the order it is worth reading."""

    bars: list
    forces: list
    stretches: list
    movement: list
    reactions: tuple
    touching: bool
    note: str = ""

    def stresses(self) -> list:
        return [bar.stress(force)
                for bar, force in zip(self.bars, self.forces)]

    def rows(self) -> list:
        rows = []
        for index, bar in enumerate(self.bars):
            name = bar.name or f"bar {index + 1}"
            rows.append((f"{name}: force", self.forces[index], "N"))
            rows.append((f"{name}: stress", self.stresses()[index], "N/mm^2"))
            rows.append((f"{name}: change in length", self.stretches[index],
                         "mm"))
        rows.append(("reaction, left", self.reactions[0], "N"))
        rows.append(("reaction, right", self.reactions[1], "N"))
        return rows


def restrained_stress(modulus: float, expansion: float, rise: float) -> float:
    """The stress in a bar that is heated and not allowed to grow.

    E alpha dT, and no length in it anywhere - which is the whole point.
    A metre or a kilometre, the strain that was prevented is the same and
    so is the stress.
    """
    return modulus * expansion * 1e-6 * rise


def free_length(length: float, expansion: float, rise: float) -> float:
    """What the bar would grow to if nothing stopped it."""
    return length * (1.0 + expansion * 1e-6 * rise)
