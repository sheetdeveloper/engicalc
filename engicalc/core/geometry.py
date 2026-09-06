"""Triangles, arcs and intersections - shapes solved from what is known.

This is the other half of geometry from ``sections``. That module answers
"what are the properties of this shape"; this one answers "what shape is
this, given these few things about it" - the setting-out question. Three
parts of a triangle and the other three follow; two facts about an arc and
the rest of it follows; two lines and where they cross.

Three things here are worth saying out loud, because each is a place where
a program can quietly hand back one answer where there are two, or none.

**The ambiguous case is genuinely ambiguous.** Two sides and an angle that
is not between them can describe two different triangles, and both are
correct. Returning one of them - whichever the arcsine happened to give -
is the classic wrong answer in every trigonometry course there is. Both
are returned, and the caller shows both.

**Three angles are not a triangle.** They fix the shape and say nothing
about the size, so there is no answer to give and one is not invented.

**Two circles that touch have one intersection, not two.** Floating point
will not land exactly on the touching case, so it is admitted with a
tolerance rather than pretended away: within that tolerance the answer is
one point, and the two roots that differ in the fifteenth decimal are not
reported as two crossings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .parsing import ParseError


class GeometryError(ParseError):
    """A shape that cannot exist, or is not pinned down by what was given."""


#: How close two intersections have to be before they are one. Scaled by
#: the size of the figure, since "close" on a 3 mm circle and on a 3 km
#: one are not the same distance.
TOUCHING = 1e-9

#: Angles within this of a right angle are reported as one. The arcsine of
#: a number that is 1 to fifteen figures is not exactly pi/2.
SQUARE_ENOUGH = 1e-12


# --------------------------------------------------------------------------
# Triangles
# --------------------------------------------------------------------------
#: The six parts, sides first. A capital angle is opposite the small side
#: of the same letter, which is the convention every textbook uses.
SIDES = ("a", "b", "c")
ANGLES = ("A", "B", "C")
PARTS = SIDES + ANGLES


@dataclass(frozen=True)
class Triangle:
    """All six parts, and what follows from them.

    Angles are radians throughout. The tab converts at its edges; keeping
    degrees out of the arithmetic means no formula here has to remember
    which it is holding.
    """

    a: float
    b: float
    c: float
    A: float
    B: float
    C: float
    #: Which of the two the ambiguous case gave, when it gave two.
    which: str = ""

    @property
    def perimeter(self) -> float:
        return self.a + self.b + self.c

    @property
    def area(self) -> float:
        # From two sides and the angle between them rather than from
        # Heron's formula. Heron loses figures badly on a needle-thin
        # triangle - the semi-perimeter and the longest side subtract to
        # almost nothing - and this does not.
        return 0.5 * self.a * self.b * math.sin(self.C)

    @property
    def circumradius(self) -> float:
        return self.a / (2.0 * math.sin(self.A))

    @property
    def inradius(self) -> float:
        return 2.0 * self.area / self.perimeter

    @property
    def right_angled(self) -> bool:
        return any(abs(angle - math.pi / 2) < 1e-9
                   for angle in (self.A, self.B, self.C))

    @property
    def obtuse(self) -> bool:
        return max(self.A, self.B, self.C) > math.pi / 2 + 1e-12

    @property
    def isosceles(self) -> bool:
        sides = sorted((self.a, self.b, self.c))
        return (abs(sides[0] - sides[1]) < 1e-9 * sides[2]
                or abs(sides[1] - sides[2]) < 1e-9 * sides[2])

    def corners(self) -> list:
        """The three vertices, with side c along the x axis from the origin.

        A drawing needs somewhere to put the thing; any placement will do
        as long as it is consistent, and this one puts the triangle the way
        it is normally drawn - one side flat at the bottom.
        """
        # C is the angle at the third corner, so A and B are the corners
        # at each end of side c.
        return [(0.0, 0.0),
                (self.c, 0.0),
                (self.b * math.cos(self.A), self.b * math.sin(self.A))]

    def rows(self) -> list:
        return [("a", self.a, ""), ("b", self.b, ""), ("c", self.c, ""),
                ("A", math.degrees(self.A), "deg"),
                ("B", math.degrees(self.B), "deg"),
                ("C", math.degrees(self.C), "deg"),
                ("area", self.area, ""),
                ("perimeter", self.perimeter, ""),
                ("circumradius", self.circumradius, ""),
                ("inradius", self.inradius, "")]


def _angle_from_sides(opposite: float, one: float, other: float) -> float:
    """The cosine rule, solved for the angle opposite *opposite*."""
    cosine = (one * one + other * other - opposite * opposite) / (2 * one * other)
    # Rounding can put a degenerate triangle a hair outside [-1, 1].
    return math.acos(max(-1.0, min(1.0, cosine)))


def solve_triangle(given: dict) -> list:
    """Every triangle consistent with *given*.

    Returns one triangle, or two when the given parts are the ambiguous
    case, and raises when they are impossible or do not fix a size.
    """
    known = {k: v for k, v in given.items() if v is not None}
    unknown = set(known) - set(PARTS)
    if unknown:
        raise GeometryError(f"{', '.join(sorted(unknown))} is not a part of "
                            f"a triangle. Use a, b, c, A, B or C.")
    for name, value in known.items():
        if value <= 0:
            raise GeometryError(f"{name} must be more than zero.")
    for name in ANGLES:
        if name in known and known[name] >= math.pi:
            raise GeometryError(f"{name} is {math.degrees(known[name]):.6g} "
                                f"degrees, and the three angles of a "
                                f"triangle come to 180.")

    sides = [k for k in SIDES if k in known]
    angles = [k for k in ANGLES if k in known]
    if len(sides) + len(angles) < 3:
        raise GeometryError("A triangle needs three of its six parts. "
                            f"Only {len(sides) + len(angles)} were given.")
    if len(sides) + len(angles) > 3:
        raise GeometryError("A triangle is fixed by three parts, and more "
                            "than three were given. Clear one - the others "
                            "will come back as answers.")
    if not sides:
        # Three angles fix the shape and say nothing about the size, so
        # there is no triangle to give and one is not invented.
        raise GeometryError(
            "Three angles fix the shape but not the size - every triangle "
            "with these angles is a valid answer. Give at least one side.")

    if len(angles) == 2:
        return [_from_two_angles(known, sides[0], angles)]
    if len(sides) == 3:
        return [_from_three_sides(known)]
    # Two sides and one angle: included, or not.
    return _from_two_sides(known, sides, angles[0])


def _third_angle(one: float, other: float) -> float:
    third = math.pi - one - other
    if third <= 0:
        raise GeometryError(
            f"Those two angles come to {math.degrees(one + other):.6g} "
            f"degrees, which leaves nothing for the third.")
    return third


def _from_two_angles(known: dict, side: str, angles: list) -> Triangle:
    """One side and two angles - ASA or AAS, which are the same problem."""
    A, B, C = (known.get(name) for name in ANGLES)
    missing = [name for name in ANGLES if known.get(name) is None][0]
    filled = dict(zip(ANGLES, (A, B, C)))
    filled[missing] = _third_angle(*[v for v in (A, B, C) if v is not None])
    # The sine rule from the one side that is known.
    ratio = known[side] / math.sin(filled[side.upper()])
    lengths = {name: ratio * math.sin(filled[name.upper()]) for name in SIDES}
    return Triangle(a=lengths["a"], b=lengths["b"], c=lengths["c"],
                    A=filled["A"], B=filled["B"], C=filled["C"])


def _from_three_sides(known: dict) -> Triangle:
    a, b, c = known["a"], known["b"], known["c"]
    longest = max(a, b, c)
    if longest >= (a + b + c) - longest:
        raise GeometryError(
            f"No triangle has sides {a:g}, {b:g} and {c:g} - the longest is "
            f"as long as the other two together, so they cannot close.")
    A = _angle_from_sides(a, b, c)
    B = _angle_from_sides(b, a, c)
    return Triangle(a=a, b=b, c=c, A=A, B=B, C=math.pi - A - B)


def _from_two_sides(known: dict, sides: list, angle: str) -> list:
    """Two sides and an angle - SAS if it is between them, SSA if not."""
    first, second = sides
    missing_side = [s for s in SIDES if s not in sides][0]
    if angle.lower() == missing_side:
        # The angle is between the two known sides: one triangle, and the
        # cosine rule gives the third side straight away.
        one, other = known[first], known[second]
        included = known[angle]
        third = math.sqrt(one * one + other * other
                          - 2 * one * other * math.cos(included))
        lengths = {first: one, second: other, missing_side: third}
        return [_from_three_sides(lengths)]

    # SSA. The known angle is opposite one of the known sides; the other
    # known side is adjacent, and may be able to reach the far line in two
    # places.
    opposite = angle.lower()
    adjacent = [s for s in sides if s != opposite][0]
    facing = known[opposite]
    swinging = known[adjacent]
    sine = swinging * math.sin(known[angle]) / facing
    if sine > 1.0 + 1e-12:
        raise GeometryError(
            f"No triangle: side {opposite} = {facing:g} is too short to "
            f"reach. It would have to be at least "
            f"{swinging * math.sin(known[angle]):.6g}.")
    sine = min(1.0, sine)
    first_angle = math.asin(sine)

    candidates = [first_angle]
    # The supplement is the second triangle, and it exists only when there
    # is room for it. sin is the same for an angle and its supplement, so
    # this is where the two answers come from.
    supplement = math.pi - first_angle
    if (abs(sine - 1.0) > SQUARE_ENOUGH
            and supplement + known[angle] < math.pi - 1e-12):
        candidates.append(supplement)

    found = []
    for n, value in enumerate(candidates):
        filled = {angle: known[angle], adjacent.upper(): value}
        third = [name for name in ANGLES if name not in filled][0]
        filled[third] = _third_angle(*filled.values())
        ratio = facing / math.sin(known[angle])
        lengths = {name: ratio * math.sin(filled[name.upper()])
                   for name in SIDES}
        found.append(Triangle(
            a=lengths["a"], b=lengths["b"], c=lengths["c"],
            A=filled["A"], B=filled["B"], C=filled["C"],
            which="" if len(candidates) == 1
                  else ("acute" if n == 0 else "obtuse")))
    return found


def why_ambiguous(known: dict) -> str:
    """A sentence saying why there are two answers, or "" when there are not."""
    sides = [k for k in SIDES if k in known]
    angles = [k for k in ANGLES if k in known]
    if len(sides) != 2 or len(angles) != 1:
        return ""
    angle = angles[0]
    if angle.lower() not in sides:
        return ""
    adjacent = [s for s in sides if s != angle.lower()][0]
    return (f"Two sides and an angle that is not between them. Side "
            f"{adjacent} can swing to meet the far line in two places, and "
            f"both triangles are correct - which one is meant is not in the "
            f"numbers. Give a third part, or say which.")


# --------------------------------------------------------------------------
# Arcs
# --------------------------------------------------------------------------
#: The parts of a circular arc. Any two of these fix it.
#:
#:   R      radius
#:   theta  included angle, radians
#:   L      arc length along the curve
#:   chord  straight across, end to end
#:   rise   the sagitta - how far the curve stands off the chord
ARC_PARTS = ("R", "theta", "L", "chord", "rise")


@dataclass(frozen=True)
class Arc:
    R: float
    theta: float
    #: "minor" or "major" when the parts given describe both, "" when they
    #: describe only one.
    which: str = ""

    @property
    def length(self) -> float:
        return self.R * self.theta

    @property
    def chord(self) -> float:
        return 2.0 * self.R * math.sin(self.theta / 2.0)

    @property
    def rise(self) -> float:
        """The sagitta: how far the middle of the arc stands off the chord.

        Written as 2 sin^2 rather than 1 - cos. They are the same identity,
        but on a shallow arc the second subtracts two numbers that agree to
        fifteen figures and keeps almost none of them - and at a quarter of
        a nanoradian it returns exactly zero, which a solver dividing by it
        does not survive.
        """
        return 2.0 * self.R * math.sin(self.theta / 4.0) ** 2

    @property
    def sector_area(self) -> float:
        return 0.5 * self.R * self.R * self.theta

    @property
    def segment_area(self) -> float:
        """The area between the chord and the curve."""
        return 0.5 * self.R * self.R * (self.theta - math.sin(self.theta))

    @property
    def major(self) -> bool:
        return self.theta > math.pi

    def rows(self) -> list:
        return [("radius", self.R, ""),
                ("included angle", math.degrees(self.theta), "deg"),
                ("arc length", self.length, ""),
                ("chord", self.chord, ""),
                ("rise (sagitta)", self.rise, ""),
                ("sector area", self.sector_area, ""),
                ("segment area", self.segment_area, "")]


def _versine(half: float) -> float:
    """1 - cos(half), kept accurate all the way down to nothing."""
    return 2.0 * math.sin(half / 2.0) ** 2


def _arc_ratio(theta: float, have: frozenset) -> float:
    """The one quantity a pair of lengths fixes, as a function of theta.

    Two lengths give a ratio and the radius divides straight out of it, so
    a problem in two unknowns becomes one in a single unknown and stays
    well behaved.
    """
    half = theta / 2.0
    if have == frozenset({"L", "chord"}):
        return theta / (2.0 * math.sin(half))
    if have == frozenset({"L", "rise"}):
        return theta / _versine(half)
    if have == frozenset({"chord", "rise"}):
        return 2.0 * math.sin(half) / _versine(half)
    raise GeometryError("Those two do not fix an arc.")


def _where_the_ratio_turns() -> float:
    """The angle at which arc length stops falling relative to its rise.

    Differentiating theta / (2 sin^2(theta/4)) and setting the numerator to
    zero leaves tan(theta/4) = theta/2, which is solved here rather than
    written down as a number. A constant with no derivation beside it is a
    constant nobody can check.
    """
    def slope(theta):
        return math.tan(theta / 4.0) - theta / 2.0

    # theta/4 never reaches a right angle over the range of an arc, so the
    # tangent has no pole in here to step over.
    low, high = 1e-6, 2.0 * math.pi - 1e-12
    for _ in range(200):
        middle = 0.5 * (low + high)
        if slope(low) * slope(middle) <= 0:
            high = middle
        else:
            low = middle
    return 0.5 * (low + high)


#: Where the arc length to rise ratio turns round, and the lowest it gets.
#: Below that ratio no arc exists at all; between it and pi there are two.
TURNS_AT = _where_the_ratio_turns()
SHALLOWEST = _arc_ratio(TURNS_AT, frozenset({"L", "rise"}))

#: How close to the turning point counts as landing on it. There the two
#: arcs have merged into one, and reporting two answers a hair apart would
#: be reporting the arithmetic rather than the geometry.
MERGED = 1e-12


def solve_arc(given: dict) -> list:
    """Every arc that has these two parts.

    Any two of radius, angle, arc length, chord and rise. Usually there is
    one; two of the pairs describe two arcs, and both are returned for the
    same reason the ambiguous triangle returns two.

    A chord in a circle of known radius is the obvious one - it cuts the
    circle in two and both pieces are arcs of that chord. The other is not
    obvious at all: the ratio of arc length to rise falls to a minimum of
    2.7601 near 267 degrees and climbs back to pi, so any ratio between
    those two belongs to two different arcs.
    """
    known = {k: v for k, v in given.items() if v is not None}
    unknown = set(known) - set(ARC_PARTS)
    if unknown:
        raise GeometryError(f"{', '.join(sorted(unknown))} is not a part of "
                            f"an arc.")
    for name, value in known.items():
        if value <= 0:
            raise GeometryError(f"{name} must be more than zero.")
    if len(known) != 2:
        raise GeometryError(
            f"An arc is fixed by two of its parts, and "
            f"{'one was' if len(known) == 1 else str(len(known)) + ' were'} "
            f"given. Radius, angle, arc length, chord or rise - any two.")
    if "theta" in known and known["theta"] > 2 * math.pi:
        raise GeometryError("The included angle cannot be more than 360 "
                            "degrees.")

    have = set(known)
    # -- the angle is given, so there is nothing to choose ----------------
    if have == {"R", "theta"}:
        return [Arc(known["R"], known["theta"])]
    if have == {"theta", "L"}:
        return [Arc(known["L"] / known["theta"], known["theta"])]
    if have == {"theta", "chord"}:
        return [Arc(known["chord"] / (2.0 * math.sin(known["theta"] / 2.0)),
                    known["theta"])]
    if have == {"theta", "rise"}:
        divisor = _versine(known["theta"] / 2.0)
        if divisor <= 0:
            raise GeometryError("An arc with no angle has no rise.")
        return [Arc(known["rise"] / divisor, known["theta"])]

    # -- the radius and one length ----------------------------------------
    if have == {"R", "L"}:
        theta = known["L"] / known["R"]
        if theta > 2.0 * math.pi:
            raise GeometryError(
                f"An arc {known['L']:g} long on a radius of {known['R']:g} "
                f"would go round {theta / (2 * math.pi):.4g} times.")
        return [Arc(known["R"], theta)]

    if have == {"R", "chord"}:
        ratio = known["chord"] / (2.0 * known["R"])
        if ratio > 1.0 + TOUCHING:
            raise GeometryError(
                f"A chord of {known['chord']:g} will not fit in a circle of "
                f"radius {known['R']:g} - the longest is the diameter, "
                f"{2 * known['R']:g}.")
        minor = 2.0 * math.asin(min(1.0, ratio))
        if abs(minor - math.pi) < TOUCHING:
            return [Arc(known["R"], math.pi)]
        # A chord cuts the circle in two and both pieces are arcs of it.
        return [Arc(known["R"], minor, "minor"),
                Arc(known["R"], 2.0 * math.pi - minor, "major")]

    if have == {"R", "rise"}:
        if known["rise"] > 2.0 * known["R"] * (1.0 + TOUCHING):
            raise GeometryError(
                f"A rise of {known['rise']:g} is more than the diameter of "
                f"a circle of radius {known['R']:g}.")
        # Here the rise settles which of the two it is - standing off
        # further than the radius means the arc has come past halfway - so
        # unlike the chord there is nothing to choose. Through the arcsine
        # of the quarter angle rather than the arccosine of the half: on a
        # shallow arc the arccosine is asked for an angle where its own
        # slope is infinite, and hands back half the figures it was given.
        return [Arc(known["R"], 4.0 * math.asin(
            min(1.0, math.sqrt(known["rise"] / (2.0 * known["R"])))))]

    # -- two lengths -------------------------------------------------------
    if have == {"chord", "rise"}:
        # The setting-out formula everybody knows: R = (c^2/4 + s^2) / 2s.
        chord, rise = known["chord"], known["rise"]
        radius = (chord * chord / 4.0 + rise * rise) / (2.0 * rise)
        minor = 2.0 * math.asin(min(1.0, chord / (2.0 * radius)))
        return [Arc(radius, 2.0 * math.pi - minor if rise > radius else minor)]

    if have == {"L", "chord"} and known["L"] <= known["chord"]:
        raise GeometryError(
            "The arc must be longer than its chord - the straight line is "
            "the shortest way between the ends.")

    if have in ({"L", "chord"}, {"L", "rise"}):
        other = "chord" if "chord" in have else "rise"
        target = known["L"] / known[other]
        angles = _thetas_giving(target, frozenset(have))
        if not angles:
            raise GeometryError(_no_such_arc(target, frozenset(have)))
        named = ["minor", "major"] if len(angles) == 2 else [""]
        return [Arc(known["L"] / theta, theta, name)
                for theta, name in zip(angles, named)]

    raise GeometryError("Those two do not fix an arc.")


def _thetas_giving(target: float, have: frozenset) -> list:
    """Every included angle whose ratio is *target*.

    Each ratio is solved on the stretches where it only goes one way, so
    an answer cannot be missed. Arc length against chord climbs the whole
    way and has one root. Arc length against rise falls to a minimum near
    267 degrees and climbs back, so it has two, one or none - and which of
    those is settled before anything is solved, rather than discovered by
    a search that stopped early.
    """
    ends = (1e-9, 2.0 * math.pi - 1e-12)
    if have == frozenset({"L", "chord"}):
        # From 1 at no angle to unbounded as the chord closes up.
        return [] if target <= 1.0 else [_bisect(ends[0], ends[1], target,
                                                 have)]
    if have == frozenset({"chord", "rise"}):
        # 2 cot(theta/4): unbounded down to nothing, one way the whole time.
        return [_bisect(ends[0], ends[1], target, have)] if target > 0 else []

    # Arc length against rise, on the two stretches either side of the turn.
    if target < SHALLOWEST * (1.0 - MERGED):
        return []
    if target <= SHALLOWEST * (1.0 + MERGED):
        # The two have merged into one at the bottom of the curve.
        return [TURNS_AT]
    found = [_bisect(ends[0], TURNS_AT, target, have)]
    if target < math.pi:
        found.append(_bisect(TURNS_AT, ends[1], target, have))
    return found


def _bisect(low: float, high: float, target: float, have: frozenset) -> float:
    at_low = _arc_ratio(low, have) - target
    for _ in range(200):
        middle = 0.5 * (low + high)
        value = _arc_ratio(middle, have) - target
        if at_low * value <= 0:
            high = middle
        else:
            low, at_low = middle, value
    return 0.5 * (low + high)


def _no_such_arc(target: float, have: frozenset) -> str:
    if have == frozenset({"L", "rise"}):
        return (f"No arc is {target:.6g} times as long as its rise. That "
                f"ratio never falls below {SHALLOWEST:.4f}, which it "
                f"reaches at an included angle of "
                f"{math.degrees(TURNS_AT):.1f} degrees.")
    return "No arc has those two together."


# --------------------------------------------------------------------------
# Where things cross
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Crossing:
    """Where two figures meet, and what to say when they do not."""

    points: tuple = ()
    note: str = ""

    def __bool__(self) -> bool:
        return bool(self.points)

    def rows(self) -> list:
        if not self.points:
            return [("they do not cross", self.note, "")]
        rows = []
        for n, (x, y) in enumerate(self.points, start=1):
            label = "" if len(self.points) == 1 else f" {n}"
            rows.append((f"x{label}", x, ""))
            rows.append((f"y{label}", y, ""))
        return rows


def line_through(one: tuple, other: tuple) -> tuple:
    """The line through two points as (A, B, C) with Ax + By = C.

    The general form rather than y = mx + c, because a vertical line has no
    gradient and would have to be a special case everywhere it appeared.
    """
    (x1, y1), (x2, y2) = one, other
    if math.hypot(x2 - x1, y2 - y1) == 0:
        raise GeometryError("Those two points are the same, and one point "
                            "does not make a line.")
    return (y2 - y1, x1 - x2, (y2 - y1) * x1 + (x1 - x2) * y1)


def cross_lines(first: tuple, second: tuple) -> Crossing:
    """Where two lines meet, each given as (A, B, C) for Ax + By = C."""
    (a1, b1, c1), (a2, b2, c2) = first, second
    determinant = a1 * b2 - a2 * b1
    size = max(abs(a1), abs(b1)) * max(abs(a2), abs(b2))
    if abs(determinant) <= TOUCHING * max(size, 1.0):
        # Parallel. Same line or not is worth distinguishing - one has no
        # crossing and the other has every point in common.
        same = abs(a1 * c2 - a2 * c1) <= TOUCHING * max(size, 1.0)
        return Crossing((), "the same line - every point is common" if same
                            else "parallel")
    return Crossing((((c1 * b2 - c2 * b1) / determinant,
                      (a1 * c2 - a2 * c1) / determinant),))


def cross_line_circle(line: tuple, centre: tuple, radius: float) -> Crossing:
    """Where a line meets a circle: nothing, a tangent point, or two."""
    if radius <= 0:
        raise GeometryError("The radius must be more than zero.")
    a, b, c = line
    cx, cy = centre
    norm = math.hypot(a, b)
    if norm == 0:
        raise GeometryError("That is not a line.")
    # Distance from the centre to the line, and the foot of that
    # perpendicular - which is the midpoint of the chord.
    distance = (a * cx + b * cy - c) / norm
    foot = (cx - a * distance / norm, cy - b * distance / norm)
    gap = abs(distance) - radius
    if gap > TOUCHING * radius:
        return Crossing((), f"the line passes {abs(distance) - radius:.6g} "
                            f"clear of the circle")
    if abs(gap) <= TOUCHING * radius:
        return Crossing((foot,), "tangent - it touches at one point")
    half = math.sqrt(max(radius * radius - distance * distance, 0.0))
    along = (-b / norm, a / norm)
    return Crossing(((foot[0] - along[0] * half, foot[1] - along[1] * half),
                     (foot[0] + along[0] * half, foot[1] + along[1] * half)))


def cross_circles(first_centre: tuple, first_radius: float,
                  second_centre: tuple, second_radius: float) -> Crossing:
    """Where two circles meet."""
    if first_radius <= 0 or second_radius <= 0:
        raise GeometryError("Both radii must be more than zero.")
    (x1, y1), (x2, y2) = first_centre, second_centre
    apart = math.hypot(x2 - x1, y2 - y1)
    scale = max(first_radius, second_radius)
    if apart <= TOUCHING * scale:
        if abs(first_radius - second_radius) <= TOUCHING * scale:
            return Crossing((), "the same circle - every point is common")
        return Crossing((), "one inside the other, sharing a centre")

    # Touching is admitted with a tolerance rather than pretended away:
    # floating point will not land exactly on it, and two roots differing
    # in the fifteenth decimal are one crossing, not two.
    outside = apart - (first_radius + second_radius)
    inside = abs(first_radius - second_radius) - apart
    if outside > TOUCHING * scale:
        return Crossing((), f"{outside:.6g} apart - too far to meet")
    if inside > TOUCHING * scale:
        return Crossing((), f"one is {inside:.6g} inside the other")

    along = ((first_radius * first_radius - second_radius * second_radius
              + apart * apart) / (2.0 * apart))
    height_squared = first_radius * first_radius - along * along
    middle = (x1 + along * (x2 - x1) / apart, y1 + along * (y2 - y1) / apart)
    if height_squared <= (TOUCHING * scale) ** 2:
        return Crossing((middle,), "they touch at one point")
    height = math.sqrt(height_squared)
    step = (-(y2 - y1) / apart * height, (x2 - x1) / apart * height)
    return Crossing(((middle[0] + step[0], middle[1] + step[1]),
                     (middle[0] - step[0], middle[1] - step[1])))


def tangent_from_point(point: tuple, centre: tuple, radius: float) -> Crossing:
    """The two points on a circle where a line from *point* touches it."""
    if radius <= 0:
        raise GeometryError("The radius must be more than zero.")
    apart = math.hypot(point[0] - centre[0], point[1] - centre[1])
    if apart < radius - TOUCHING * radius:
        return Crossing((), "the point is inside the circle, so no line "
                            "from it can touch")
    if abs(apart - radius) <= TOUCHING * radius:
        return Crossing((point,), "the point is on the circle - the tangent "
                                  "touches there")
    # The touch points lie on a circle of their own: the one on the line
    # joining the point to the centre as a diameter. So this is a
    # circle-circle crossing, and needs no new arithmetic.
    middle = (0.5 * (point[0] + centre[0]), 0.5 * (point[1] + centre[1]))
    return cross_circles(centre, radius, middle, apart / 2.0)


def tangent_length(point: tuple, centre: tuple, radius: float) -> float:
    """How long the tangent is, from the point to where it touches."""
    apart = math.hypot(point[0] - centre[0], point[1] - centre[1])
    if apart < radius:
        raise GeometryError("The point is inside the circle.")
    return math.sqrt(apart * apart - radius * radius)


def circle_through(one: tuple, two: tuple, three: tuple) -> tuple:
    """The circle through three points, as (centre, radius).

    The setting-out problem: three points measured off a curve, and the
    radius that made them.
    """
    (x1, y1), (x2, y2), (x3, y3) = one, two, three
    # The centre is where the two perpendicular bisectors cross, which is
    # a line crossing already written.
    first = _bisector(one, two)
    second = _bisector(two, three)
    found = cross_lines(first, second)
    if not found:
        raise GeometryError("Those three points are in a straight line, so "
                            "no circle passes through all three.")
    centre = found.points[0]
    return centre, math.hypot(x1 - centre[0], y1 - centre[1])


def _bisector(one: tuple, other: tuple) -> tuple:
    """The perpendicular bisector of two points, as Ax + By = C."""
    (x1, y1), (x2, y2) = one, other
    if math.hypot(x2 - x1, y2 - y1) == 0:
        raise GeometryError("Two of those points are the same.")
    middle = (0.5 * (x1 + x2), 0.5 * (y1 + y2))
    a, b = x2 - x1, y2 - y1
    return (a, b, a * middle[0] + b * middle[1])
