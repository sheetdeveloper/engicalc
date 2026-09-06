"""Straight-line motion: the three diagrams and the equations behind them.

Distance, velocity and acceleration against time are one thing seen three
ways, and the whole subject is the two facts joining them: the slope of the
velocity curve is the acceleration, and the area under it is the distance.
Drawn separately those are two more graphs to remember. Drawn one above the
other with the same time axis they are hard to miss, which is the reason for
drawing them together.

Two ways in. The five constant-acceleration quantities - distance, starting
velocity, final velocity, acceleration, time - are related by equations that
let any three settle the other two, and that is the exercise every course
sets. But a real movement has stages: something speeds up, runs at speed,
and slows down again. So a motion here is a list of stages, each of constant
acceleration, and the one-stage case is just the shortest list.

Everything is worked forwards from the start, stage by stage, so the
diagrams and the numbers beside them come from the same arithmetic and
cannot disagree.

Signs: forwards is positive, and a velocity that goes negative means it has
turned round rather than that something has gone wrong. Distance travelled
and displacement are then different numbers, and both are reported - the odd
one out being the case where they differ, which is exactly when it matters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .parsing import ParseError

#: How near zero a divisor has to be before dividing by it means nothing.
TINY = 1e-12

#: The five quantities, and what each one is called.
QUANTITIES = {
    "s": "distance",
    "u": "starting velocity",
    "v": "final velocity",
    "a": "acceleration",
    "t": "time",
}


class MotionError(ParseError):
    """Raised when a movement cannot be worked out."""


# --------------------------------------------------------------------------
# One stage of constant acceleration
# --------------------------------------------------------------------------
def solve_suvat(**given) -> tuple:
    """Given three of s, u, v, a, t, work out the other two.

    Returns (values, working) - the five quantities, and a line per equation
    saying which one was used and what it gave, because on this subject the
    equation used is most of the answer.

    Done by applying the four equations in turn until nothing new comes out,
    rather than by ten special cases. The equations are the same four
    whichever three you happen to know, and writing them once is the only
    way they stay the same four.
    """
    known = {name: float(value) for name, value in given.items()
             if value is not None and name in QUANTITIES}
    if len(known) < 3:
        missing = 3 - len(known)
        raise MotionError(
            f"Three of the five are needed and {len(known)} were given. "
            f"Say {missing} more.")

    working = []
    ambiguous = None
    for _pass in range(6):
        before = len(known)
        s, u, v, a, t = (known.get(x) for x in "suvat")

        # v = u + a t
        if v is None and None not in (u, a, t):
            known["v"] = u + a * t
            working.append(("v = u + a t", "v", known["v"]))
        elif u is None and None not in (v, a, t):
            known["u"] = v - a * t
            working.append(("u = v - a t", "u", known["u"]))
        elif a is None and None not in (u, v, t) and abs(t) > TINY:
            known["a"] = (v - u) / t
            working.append(("a = (v - u) / t", "a", known["a"]))
        elif t is None and None not in (u, v, a) and abs(a) > TINY:
            known["t"] = (v - u) / a
            working.append(("t = (v - u) / a", "t", known["t"]))

        s, u, v, a, t = (known.get(x) for x in "suvat")

        # s = (u + v) t / 2
        if s is None and None not in (u, v, t):
            known["s"] = (u + v) * t / 2.0
            working.append(("s = (u + v) t / 2", "s", known["s"]))
        elif t is None and None not in (s, u, v) and abs(u + v) > TINY:
            known["t"] = 2.0 * s / (u + v)
            working.append(("t = 2 s / (u + v)", "t", known["t"]))
        elif v is None and None not in (s, u, t) and abs(t) > TINY:
            known["v"] = 2.0 * s / t - u
            working.append(("v = 2 s / t - u", "v", known["v"]))
        elif u is None and None not in (s, v, t) and abs(t) > TINY:
            known["u"] = 2.0 * s / t - v
            working.append(("u = 2 s / t - v", "u", known["u"]))

        s, u, v, a, t = (known.get(x) for x in "suvat")

        # s = u t + a t^2 / 2
        if s is None and None not in (u, a, t):
            known["s"] = u * t + a * t * t / 2.0
            working.append(("s = u t + a t^2 / 2", "s", known["s"]))
        elif a is None and None not in (s, u, t) and abs(t) > TINY:
            known["a"] = 2.0 * (s - u * t) / (t * t)
            working.append(("a = 2 (s - u t) / t^2", "a", known["a"]))
        elif u is None and None not in (s, a, t) and abs(t) > TINY:
            known["u"] = s / t - a * t / 2.0
            working.append(("u = s / t - a t / 2", "u", known["u"]))

        s, u, v, a, t = (known.get(x) for x in "suvat")

        # v^2 = u^2 + 2 a s
        if v is None and None not in (u, a, s):
            square = u * u + 2.0 * a * s
            if square < 0:
                raise MotionError(
                    "v^2 = u^2 + 2 a s comes out negative, so no real final "
                    "velocity fits those three. Check the signs: an "
                    "acceleration that opposes the motion is negative.")
            root = math.sqrt(square)
            # Two roots, and the physical one is the one that takes a
            # positive time to reach. If both do, that is a real ambiguity
            # in what was asked rather than something to decide quietly.
            fits = [candidate for candidate in (root, -root)
                    if abs(a) <= TINY or (candidate - u) / a >= -TINY]
            if not fits:
                fits = [root]
            known["v"] = fits[0]
            if len(fits) > 1 and abs(fits[0] - fits[1]) > TINY:
                ambiguous = fits
            working.append(("v = sqrt(u^2 + 2 a s)", "v", known["v"]))
        elif u is None and None not in (v, a, s):
            square = v * v - 2.0 * a * s
            if square < 0:
                raise MotionError(
                    "u^2 = v^2 - 2 a s comes out negative, so no real "
                    "starting velocity fits those three.")
            known["u"] = math.sqrt(square)
            working.append(("u = sqrt(v^2 - 2 a s)", "u", known["u"]))
        elif a is None and None not in (u, v, s) and abs(s) > TINY:
            known["a"] = (v * v - u * u) / (2.0 * s)
            working.append(("a = (v^2 - u^2) / (2 s)", "a", known["a"]))
        elif s is None and None not in (u, v, a) and abs(a) > TINY:
            known["s"] = (v * v - u * u) / (2.0 * a)
            working.append(("s = (v^2 - u^2) / (2 a)", "s", known["s"]))

        if len(known) == 5:
            break
        if len(known) == before:
            break

    if len(known) < 5:
        still = ", ".join(name for name in QUANTITIES if name not in known)
        raise MotionError(
            f"Those three do not settle the rest - {still} could be "
            f"anything. That happens when one of them is zero: with no "
            f"acceleration the time cannot be got out of a velocity change "
            f"that never happens.")
    return known, working, ambiguous


# --------------------------------------------------------------------------
# A movement in stages
# --------------------------------------------------------------------------
@dataclass
class Phase:
    """One stage of constant acceleration.

    Give any two of duration, acceleration, end velocity and distance. The
    velocity it starts at comes from the stage before it, which is what
    makes this a stage rather than a separate problem.
    """

    label: str = ""
    duration: float | None = None
    acceleration: float | None = None
    end_velocity: float | None = None
    distance: float | None = None

    def given(self) -> dict:
        return {name: value for name, value in
                (("t", self.duration), ("a", self.acceleration),
                 ("v", self.end_velocity), ("s", self.distance))
                if value is not None}


@dataclass
class Leg:
    """A stage with nothing left unknown about it."""

    label: str
    start_time: float
    duration: float
    start_velocity: float
    end_velocity: float
    acceleration: float
    distance: float
    start_position: float

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    @property
    def end_position(self) -> float:
        return self.start_position + self.distance

    def turning_point(self) -> float | None:
        """When it stops and goes back, if it does so within this stage."""
        if abs(self.acceleration) <= TINY:
            return None
        when = -self.start_velocity / self.acceleration
        return when if TINY < when < self.duration - TINY else None

    def travelled(self) -> float:
        """Ground covered, which is not the same as ground gained.

        A stage that stops and comes back has a displacement smaller than
        the distance travelled, and on a braking problem that is the whole
        question.
        """
        turn = self.turning_point()
        if turn is None:
            return abs(self.distance)
        out = abs(self.start_velocity * turn
                  + self.acceleration * turn * turn / 2.0)
        rest = self.duration - turn
        back = abs(self.acceleration * rest * rest / 2.0)
        return out + back

    def at(self, when):
        """(position, velocity) at a time measured from this stage's start."""
        return (self.start_position + self.start_velocity * when
                + self.acceleration * when * when / 2.0,
                self.start_velocity + self.acceleration * when)


@dataclass
class Motion:
    """A movement, described as the stages it goes through."""

    phases: list = field(default_factory=list)
    start_velocity: float = 0.0
    start_position: float = 0.0

    def legs(self) -> list:
        """Work each stage out in turn, carrying the velocity forward."""
        if not self.phases:
            raise MotionError("Describe at least one stage of the movement.")
        found = []
        when, where = 0.0, self.start_position
        speed = self.start_velocity
        for index, phase in enumerate(self.phases, 1):
            given = phase.given()
            if len(given) < 2:
                raise MotionError(
                    f"Stage {index} needs two of duration, acceleration, "
                    f"end velocity and distance; it has {len(given)}.")
            values, _working, _both = solve_suvat(u=speed, **given)
            if values["t"] < -TINY:
                raise MotionError(
                    f"Stage {index} works out at {values['t']:.4g} seconds, "
                    f"which is a stage that finishes before it starts. "
                    f"Check the signs - slowing down is a negative "
                    f"acceleration.")
            found.append(Leg(
                label=phase.label or f"stage {index}",
                start_time=when, duration=values["t"],
                start_velocity=speed, end_velocity=values["v"],
                acceleration=values["a"], distance=values["s"],
                start_position=where))
            when += values["t"]
            where += values["s"]
            speed = values["v"]
        return found

    def trace(self, per_leg: int = 160) -> tuple:
        """(t, s, v, a) along the whole movement.

        Sampled stage by stage rather than over the whole thing, because the
        acceleration jumps between stages and a curve drawn straight through
        the jump says the opposite of what happened.
        """
        legs = self.legs()
        times, places, speeds, rates = [], [], [], []
        for leg in legs:
            steps = np.linspace(0.0, max(leg.duration, 0.0), per_leg)
            place, speed = leg.at(steps)
            times.append(leg.start_time + steps)
            places.append(place)
            speeds.append(speed)
            rates.append(np.full_like(steps, leg.acceleration))
        return (np.concatenate(times), np.concatenate(places),
                np.concatenate(speeds), np.concatenate(rates))

    def summary(self) -> dict:
        legs = self.legs()
        return {
            "time": sum(leg.duration for leg in legs),
            "displacement": sum(leg.distance for leg in legs),
            "travelled": sum(leg.travelled() for leg in legs),
            "top speed": max(
                [abs(leg.start_velocity) for leg in legs]
                + [abs(leg.end_velocity) for leg in legs]),
            "final velocity": legs[-1].end_velocity,
        }

    def rows(self) -> list:
        """(label, value, unit) for the table under the diagrams."""
        legs = self.legs()
        rows = []
        for leg in legs:
            rows.append((f"{leg.label}: lasts", leg.duration, "s"))
            rows.append((f"{leg.label}: at", leg.acceleration, "m/s^2"))
            rows.append((f"{leg.label}: reaches", leg.end_velocity, "m/s"))
            rows.append((f"{leg.label}: covers", leg.distance, "m"))
        found = self.summary()
        rows += [("total time", found["time"], "s"),
                 ("displacement", found["displacement"], "m"),
                 ("distance travelled", found["travelled"], "m"),
                 ("top speed", found["top speed"], "m/s"),
                 ("average velocity",
                  found["displacement"] / found["time"]
                  if found["time"] else 0.0, "m/s")]
        return rows

    def notes(self) -> list:
        """What the numbers do not say by themselves."""
        legs = self.legs()
        found = self.summary()
        said = []
        if abs(found["travelled"] - abs(found["displacement"])) > 1e-9 * max(
                found["travelled"], 1.0):
            said.append(
                f"It turns round part way, so it covers "
                f"{found['travelled']:.4g} m of ground but ends up "
                f"{found['displacement']:.4g} m from where it started. The "
                f"area under the velocity curve counts the part below the "
                f"axis as negative, which is the difference.")
        for leg in legs:
            if leg.duration < TINY:
                said.append(f"{leg.label} takes no time at all.")
        return said


def steady_then_stop(top: float, speed_up: float, slow_down: float,
                     distance: float) -> Motion:
    """Accelerate to *top*, run at it, then brake to rest in *distance*.

    The trapezoidal profile a lift, a conveyor or a machine axis actually
    moves on, and the one worth having as a starting point because working
    the cruise out by hand is the fiddly part.
    """
    if top <= 0 or speed_up <= 0 or slow_down <= 0:
        raise MotionError(
            "The top speed and both rates have to be positive; braking is "
            "made negative for you.")
    speeding = top * top / (2.0 * speed_up)
    braking = top * top / (2.0 * slow_down)
    cruise = distance - speeding - braking
    if cruise < 0:
        raise MotionError(
            f"It cannot reach {top:g} m/s within {distance:g} m and still "
            f"stop - speeding up and braking alone need "
            f"{speeding + braking:.4g} m. Lower the top speed or use more "
            f"room.")
    phases = [Phase(label="speeding up", acceleration=speed_up,
                    end_velocity=top)]
    if cruise > TINY:
        phases.append(Phase(label="at speed", acceleration=0.0,
                            distance=cruise))
    phases.append(Phase(label="braking", acceleration=-slow_down,
                        end_velocity=0.0))
    return Motion(phases=phases)
