"""Section properties: where the centroid is and how stiff the shape is.

Every bending calculation runs through two numbers that are not in the
loading at all. The second moment of area decides how much a beam deflects
and where the stress goes; the centroid decides what the second moment is
measured about. Get the centroid wrong and every number after it is wrong by
a term nobody notices, because it still looks like a plausible answer.

So the shape is built up out of parts and the parts are added together
properly. Each part knows three things - its area, where its own centre is,
and its second moments about that centre - and the section combines them by
the parallel axis theorem about the centroid it works out first. A hole is a
part with a minus sign, which is the whole of what a hole is.

Nothing here is a table of catalogue values. A rolled section is described
by the dimensions on the drawing and its properties come out of the
geometry, so what you read is a consequence of what you typed rather than a
number this program is asserting. The root radii are included, because
leaving them out reads about 2% low on a universal beam and 2% of a
deflection is worth having.

Axes: x across, y up, both measured from wherever the parts were placed;
the centroid is found afterwards and everything is reported about it. Ixx
bends the section about the horizontal axis, which is the one an ordinary
beam bends about.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .parsing import ParseError

#: A fillet is the square in the corner with a quarter circle taken out of
#: it. All four constants below are that region, worked out once: its area,
#: how far its centroid sits from the corner, and its second moments about
#: its own centroid - all as multiples of the radius to the right power.
#:
#: Written as expressions rather than decimals so they can be read back to
#: the integrals they came from.
FILLET_AREA = 1.0 - math.pi / 4.0
FILLET_ARM = (5.0 / 6.0 - math.pi / 4.0) / FILLET_AREA
FILLET_I = (1.0 - 5.0 * math.pi / 16.0) - FILLET_AREA * FILLET_ARM ** 2
FILLET_IXY = ((1.0 / 4.0 - (1.0 / 8.0 - 2.0 / 3.0 + math.pi / 4.0))
              - FILLET_AREA * FILLET_ARM ** 2)


class SectionError(ParseError):
    """Raised when a section cannot be worked out."""


# --------------------------------------------------------------------------
# The parts a section is built from
# --------------------------------------------------------------------------
@dataclass
class Part:
    """Something with an area, a centre, and second moments about it.

    ``solid`` is what makes a hole a hole: it flips the sign of everything
    the part contributes, which is exactly right and is why a hole needs no
    other special handling anywhere.
    """

    x: float = 0.0
    y: float = 0.0
    solid: bool = True

    @property
    def sign(self) -> float:
        return 1.0 if self.solid else -1.0

    def area(self) -> float:
        raise NotImplementedError

    def own(self) -> tuple:
        """(Ixx, Iyy, Ixy) about this part's own centre."""
        raise NotImplementedError

    def bounds(self) -> tuple:
        """(left, right, bottom, top). Where the material actually reaches."""
        raise NotImplementedError

    def outline(self) -> list:
        """The edge of this part, as points, for drawing it.

        Asked of the part rather than worked out again by whatever is doing
        the drawing: two descriptions of one shape drift apart, and the
        picture is what people check the numbers against.
        """
        raise NotImplementedError

    def above(self, level: float) -> tuple:
        """(area, first moment about y = 0) of this part above *level*.

        What the shear formula wants, asked of the shape rather than
        assumed. Everything below is ignored; everything above counts.
        """
        return _above_polygon(self.outline(), level)

    def width_at(self, level: float) -> float:
        """How much of this part lies on the line at *level*."""
        return _width_of_polygon(self.outline(), level)


@dataclass
class Rectangle(Part):
    """A rectangle, given by its size and the position of its centre."""

    width: float = 0.0
    height: float = 0.0

    def area(self) -> float:
        return self.width * self.height

    def own(self) -> tuple:
        return (self.width * self.height ** 3 / 12.0,
                self.height * self.width ** 3 / 12.0,
                0.0)

    def bounds(self) -> tuple:
        return (self.x - self.width / 2.0, self.x + self.width / 2.0,
                self.y - self.height / 2.0, self.y + self.height / 2.0)

    def outline(self) -> list:
        left, right, bottom, top = self.bounds()
        return [(left, bottom), (right, bottom), (right, top), (left, top)]

    def above(self, level: float) -> tuple:
        _l, _r, bottom, top = self.bounds()
        cut = max(level, bottom)
        if cut >= top:
            return 0.0, 0.0
        area = self.width * (top - cut)
        return area, area * (top + cut) / 2.0

    def width_at(self, level: float) -> float:
        _l, _r, bottom, top = self.bounds()
        return self.width if bottom <= level <= top else 0.0


@dataclass
class Circle(Part):
    """A circle, given by its diameter and the position of its centre."""

    diameter: float = 0.0

    def area(self) -> float:
        return math.pi * self.diameter ** 2 / 4.0

    def own(self) -> tuple:
        second = math.pi * self.diameter ** 4 / 64.0
        return (second, second, 0.0)

    def bounds(self) -> tuple:
        radius = self.diameter / 2.0
        return (self.x - radius, self.x + radius,
                self.y - radius, self.y + radius)

    def outline(self, steps: int = 96) -> list:
        radius = self.diameter / 2.0
        return [(self.x + radius * math.cos(2.0 * math.pi * i / steps),
                 self.y + radius * math.sin(2.0 * math.pi * i / steps))
                for i in range(steps)]

    def above(self, level: float) -> tuple:
        """The circular segment above a chord, in closed form.

        Worth doing exactly rather than off the drawn outline: a round bar
        is one of the two shapes with a shear answer everybody knows, and
        checking against 4V/3A is no check at all if the shape itself is a
        ninety-six-sided approximation to a circle.
        """
        radius = self.diameter / 2.0
        height = level - self.y
        if height >= radius:
            return 0.0, 0.0
        if height <= -radius:
            area = self.area()
            return area, area * self.y
        rest = math.sqrt(radius * radius - height * height)
        area = radius * radius * math.acos(height / radius) - height * rest
        # The segment's first moment about the centre of the circle is
        # (2/3)(r^2 - a^2)^(3/2), which is one of the tidier results in the
        # subject and the reason this is closed form at all.
        return area, (2.0 / 3.0) * rest ** 3 + area * self.y

    def width_at(self, level: float) -> float:
        radius = self.diameter / 2.0
        height = level - self.y
        if abs(height) >= radius:
            return 0.0
        return 2.0 * math.sqrt(radius * radius - height * height)


@dataclass
class Polygon(Part):
    """Any straight-sided shape, given by its corners.

    The corners are taken as they come and the shape is closed for you.
    Which way round they go does not matter: the area comes out negative if
    they are the wrong way and is turned back, so a shape traced clockwise
    is not quietly a hole.
    """

    points: list = field(default_factory=list)

    def _terms(self):
        """Each edge's cross product, which every one of these sums over."""
        points = list(self.points)
        if len(points) < 3:
            raise SectionError(
                "A shape given by its corners needs at least three of them.")
        for index, (x1, y1) in enumerate(points):
            x2, y2 = points[(index + 1) % len(points)]
            yield x1, y1, x2, y2, x1 * y2 - x2 * y1

    def _signed_area(self) -> float:
        return sum(cross for *_, cross in self._terms()) / 2.0

    def area(self) -> float:
        return abs(self._signed_area())

    def centre(self) -> tuple:
        """Where the shape's own centroid is, before it is offset."""
        signed = self._signed_area()
        if abs(signed) < 1e-15:
            raise SectionError("That shape has no area.")
        cx = sum((x1 + x2) * cross for x1, _, x2, _, cross in self._terms())
        cy = sum((y1 + y2) * cross for _, y1, _, y2, cross in self._terms())
        return (cx / (6.0 * signed), cy / (6.0 * signed))

    def own(self) -> tuple:
        """Second moments about the shape's own centroid.

        Worked about the origin the corners were given in and then moved,
        which is the parallel axis theorem used backwards - the one place it
        is subtracted rather than added.
        """
        signed = self._signed_area()
        ixx = sum((y1 ** 2 + y1 * y2 + y2 ** 2) * cross
                  for _, y1, _, y2, cross in self._terms()) / 12.0
        iyy = sum((x1 ** 2 + x1 * x2 + x2 ** 2) * cross
                  for x1, _, x2, _, cross in self._terms()) / 12.0
        ixy = sum((x1 * y2 + 2 * x1 * y1 + 2 * x2 * y2 + x2 * y1) * cross
                  for x1, y1, x2, y2, cross in self._terms()) / 24.0
        cx, cy = self.centre()
        area = abs(signed)
        # Traced the wrong way round every term comes out negative together,
        # so the sign is taken off all of them at once.
        turn = 1.0 if signed > 0 else -1.0
        return (turn * ixx - area * cy ** 2,
                turn * iyy - area * cx ** 2,
                turn * ixy - area * cx * cy)

    def bounds(self) -> tuple:
        xs = [self.x + px for px, _ in self.points]
        ys = [self.y + py for _, py in self.points]
        return (min(xs), max(xs), min(ys), max(ys))

    def outline(self) -> list:
        return [(self.x + px, self.y + py) for px, py in self.points]

    def above(self, level: float) -> tuple:
        return _above_polygon(self.outline(), level)

    def width_at(self, level: float) -> float:
        return _width_of_polygon(self.outline(), level)


@dataclass
class Fillet(Part):
    """The material in the corner where a web meets a flange.

    A square with a quarter circle taken out of it, filling the concave
    corner at (x, y) and reaching *radius* in the direction (across, up).
    Small, and worth having: leaving the four of them off a universal beam
    reads about 2% low, which is 2% of every deflection worked from it.
    """

    radius: float = 0.0
    across: float = 1.0          # +1 reaches right, -1 reaches left
    up: float = 1.0              # +1 reaches up, -1 reaches down

    def area(self) -> float:
        return FILLET_AREA * self.radius ** 2

    def centre(self) -> tuple:
        """Its own centroid, relative to the corner it sits in."""
        arm = FILLET_ARM * self.radius
        return (self.across * arm, self.up * arm)

    def own(self) -> tuple:
        fourth = self.radius ** 4
        # The product term is the only one that knows which corner this is;
        # the other two are the same whichever way the fillet faces.
        return (FILLET_I * fourth, FILLET_I * fourth,
                self.across * self.up * FILLET_IXY * fourth)

    def bounds(self) -> tuple:
        return (min(self.x, self.x + self.across * self.radius),
                max(self.x, self.x + self.across * self.radius),
                min(self.y, self.y + self.up * self.radius),
                max(self.y, self.y + self.up * self.radius))

    def outline(self, steps: int = 24) -> list:
        """The corner, then back round the arc that cuts it out.

        The arc runs from 270 degrees to 180 about the centre of the quarter
        circle, which is the quadrant nearest the corner. Round the other
        way it is the far side of the same circle and a different shape
        altogether.
        """
        radius = self.radius
        points = [(0.0, 0.0)]
        for step in range(steps + 1):
            angle = math.radians(270.0 - 90.0 * step / steps)
            points.append((radius + radius * math.cos(angle),
                           radius + radius * math.sin(angle)))
        return [(self.x + self.across * u, self.y + self.up * v)
                for u, v in points]


def _above_polygon(points: list, level: float) -> tuple:
    """(area, first moment about y = 0) of a polygon above a horizontal line.

    The polygon is cut at the line and the part above is measured. Cutting
    first and measuring second is the whole of it: a shape clipped to a
    half-plane is still a polygon, and a polygon's area and first moment are
    the same two sums they always were.
    """
    kept = []
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        inside, next_inside = y1 >= level, y2 >= level
        if inside:
            kept.append((x1, y1))
        if inside != next_inside and y2 != y1:
            share = (level - y1) / (y2 - y1)
            kept.append((x1 + share * (x2 - x1), level))
    if len(kept) < 3:
        return 0.0, 0.0

    twice = 0.0
    moment = 0.0
    for index, (x1, y1) in enumerate(kept):
        x2, y2 = kept[(index + 1) % len(kept)]
        cross = x1 * y2 - x2 * y1
        twice += cross
        moment += (y1 + y2) * cross
    area = abs(twice) / 2.0
    if area <= 0:
        return 0.0, 0.0
    # The sign of the first moment has to follow the way round the corners
    # were given, which the area has already had taken off it.
    turn = 1.0 if twice > 0 else -1.0
    return area, turn * moment / 6.0


def _width_of_polygon(points: list, level: float) -> float:
    """How much of a polygon lies on a horizontal line.

    The crossings pair off along the line - in one side and out the other -
    so the width is the sum of the gaps between them taken two at a time.
    """
    crossings = []
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        if (y1 <= level < y2) or (y2 <= level < y1):
            crossings.append(x1 + (level - y1) / (y2 - y1) * (x2 - x1))
    crossings.sort()
    return sum(second - first
               for first, second in zip(crossings[::2], crossings[1::2]))


def _centre_of(part: Part) -> tuple:
    """Where a part's own centroid is, in the section's coordinates.

    Most parts are placed by their centre. A polygon is placed by its
    corners and a fillet by the corner it fills, so both are asked.
    """
    if isinstance(part, (Polygon, Fillet)):
        own_x, own_y = part.centre()
        return (part.x + own_x, part.y + own_y)
    return (part.x, part.y)


# --------------------------------------------------------------------------
# The section
# --------------------------------------------------------------------------
@dataclass
class Properties:
    """Everything a section has to say about itself."""

    area: float
    cx: float
    cy: float
    ixx: float
    iyy: float
    ixy: float
    bounds: tuple

    @property
    def top(self) -> float:
        """How far the material reaches above the centroid."""
        return self.bounds[3] - self.cy

    @property
    def bottom(self) -> float:
        return self.cy - self.bounds[2]

    @property
    def right(self) -> float:
        return self.bounds[1] - self.cx

    @property
    def left(self) -> float:
        return self.cx - self.bounds[0]

    @property
    def z_top(self) -> float:
        """Section modulus to the top fibre: I over the distance to it."""
        return self.ixx / self.top if self.top else float("inf")

    @property
    def z_bottom(self) -> float:
        return self.ixx / self.bottom if self.bottom else float("inf")

    @property
    def z(self) -> float:
        """The one that governs, which is always the smaller of the two."""
        return min(self.z_top, self.z_bottom)

    @property
    def rx(self) -> float:
        """Radius of gyration about the horizontal axis."""
        return math.sqrt(self.ixx / self.area) if self.area > 0 else 0.0

    @property
    def ry(self) -> float:
        return math.sqrt(self.iyy / self.area) if self.area > 0 else 0.0

    def principal(self) -> tuple:
        """(larger, smaller, angle in degrees to the larger).

        A section with an axis of symmetry has its principal axes along it
        and this says so - the angle comes out zero. An angle section has
        neither, and its weak axis is nowhere near the leg it looks like it
        should be, which is the case worth knowing about: an unrestrained
        angle bends and twists about an axis that is not drawn on it.
        """
        average = (self.ixx + self.iyy) / 2.0
        half = (self.ixx - self.iyy) / 2.0
        radius = math.hypot(half, self.ixy)
        angle = 0.5 * math.degrees(math.atan2(-2.0 * self.ixy,
                                              self.ixx - self.iyy))
        return (average + radius, average - radius, angle)

    def stress_at(self, across: float, up: float, moment: float,
                  sideways: float = 0.0) -> float:
        """Bending stress at a point, measured from the centroid.

        The general form, which has a term in x as well as one in y:

            sigma = [(Mx Iyy + My Ixy) y - (Mx Ixy + My Ixx) x]
                    / (Ixx Iyy - Ixy^2)

        With an axis of symmetry Ixy is zero and this collapses back to the
        M y / I everybody knows, so there is no reason to keep both. Without
        one - an angle, a zed - M y / I is not the stress and is not close
        to it: bending an angle about its x axis bends it sideways too, and
        the term that says so is the one M y / I has dropped.
        """
        bottom = self.ixx * self.iyy - self.ixy ** 2
        if abs(bottom) < 1e-30:
            raise SectionError("The section has no stiffness to bend about.")
        return (((moment * self.iyy + sideways * self.ixy) * up
                 - (moment * self.ixy + sideways * self.ixx) * across)
                / bottom)

    def bending_stress(self, moment: float, distance: float = None) -> float:
        """The stress at *distance* above the centroid, or at the far fibre.

        Kept for the symmetrical case, where the far fibre is the answer.
        On a section with a product term ask the section itself - the worst
        stress is then at the corner furthest from the neutral axis, and the
        neutral axis is not horizontal.
        """
        reach = (max(self.top, self.bottom) if distance is None
                 else float(distance))
        return self.stress_at(0.0, reach, moment)

    def rows(self) -> list:
        """(label, value, unit) in millimetre units, ready to show."""
        first, second, angle = self.principal()
        rows = [
            ("area", self.area, "mm^2"),
            ("centroid from the left", self.cx - self.bounds[0], "mm"),
            ("centroid from the bottom", self.cy - self.bounds[2], "mm"),
            ("Ixx", self.ixx, "mm^4"),
            ("Iyy", self.iyy, "mm^4"),
            ("Ixx", self.ixx / 1e4, "cm^4"),
            ("Iyy", self.iyy / 1e4, "cm^4"),
            ("to the top fibre", self.top, "mm"),
            ("to the bottom fibre", self.bottom, "mm"),
            ("Z to the top", self.z_top, "mm^3"),
            ("Z to the bottom", self.z_bottom, "mm^3"),
            ("radius of gyration rx", self.rx, "mm"),
            ("radius of gyration ry", self.ry, "mm"),
        ]
        if abs(self.ixy) > 1e-9 * max(self.ixx, self.iyy, 1.0):
            # Only worth saying when the axes given are not the principal
            # ones. On anything symmetrical it is zero and printing it
            # invites the question of why.
            rows += [("Ixy", self.ixy, "mm^4"),
                     ("larger principal I", first, "mm^4"),
                     ("smaller principal I", second, "mm^4"),
                     ("angle to the larger", angle, "degrees")]
        return rows


@dataclass
class Section:
    """A shape built out of parts, some of which may be holes."""

    parts: list = field(default_factory=list)
    name: str = ""

    def properties(self) -> Properties:
        if not self.parts:
            raise SectionError("There is nothing in the section yet.")

        area = 0.0
        first_x = first_y = 0.0
        for part in self.parts:
            piece = part.sign * part.area()
            centre_x, centre_y = _centre_of(part)
            area += piece
            first_x += piece * centre_x
            first_y += piece * centre_y
        if abs(area) < 1e-12:
            raise SectionError(
                "The holes take away as much as the shape puts in, so there "
                "is no section left to work out.")
        if area < 0:
            raise SectionError(
                "The holes are bigger than the shape they are in.")
        cx, cy = first_x / area, first_y / area

        # Parallel axis, about the centroid just found. Doing it in this
        # order is the point: about any other axis the answer is larger, and
        # larger by an amount that looks like a real section.
        ixx = iyy = ixy = 0.0
        for part in self.parts:
            piece = part.sign * part.area()
            centre_x, centre_y = _centre_of(part)
            own_xx, own_yy, own_xy = part.own()
            across, up = centre_x - cx, centre_y - cy
            ixx += part.sign * own_xx + piece * up ** 2
            iyy += part.sign * own_yy + piece * across ** 2
            ixy += part.sign * own_xy + piece * across * up

        # Only material decides how far the section reaches. A hole is
        # inside the shape it is cut from and cannot make it wider.
        solid = [part for part in self.parts if part.solid]
        if not solid:
            raise SectionError("The section is all holes.")
        edges = [part.bounds() for part in solid]
        bounds = (min(e[0] for e in edges), max(e[1] for e in edges),
                  min(e[2] for e in edges), max(e[3] for e in edges))
        return Properties(area=area, cx=cx, cy=cy, ixx=ixx, iyy=iyy,
                          ixy=ixy, bounds=bounds)

    # -- shear ---------------------------------------------------------
    def above(self, level: float) -> tuple:
        """(area, first moment about y = 0) of everything above *level*.

        Holes come off, the same as everywhere else, because a hole above
        the level is area that is not there to be sheared.
        """
        area = moment = 0.0
        for part in self.parts:
            piece, first = part.above(level)
            area += part.sign * piece
            moment += part.sign * first
        return area, moment

    def width_at(self, level: float) -> float:
        """How much metal is on the line at *level*.

        Signed, so a hole narrows the section rather than widening it. That
        is right for shapes built the way these are - a bore inside a wall,
        a void inside a tube - and it would not be for two parts that
        overlapped in some more inventive way.
        """
        return sum(part.sign * part.width_at(level) for part in self.parts)

    def shear_stress(self, force: float, level: float,
                     found=None) -> float:
        """tau = V Q / (I t) at a height above the section's own base.

        Q is the first moment about the neutral axis of everything beyond
        the level, and t is the metal there to carry it. Both are questions
        about the level rather than about the section, which is why they
        are asked here and not once at the start.
        """
        found = found or self.properties()
        area, first = self.above(level)
        # Q about the neutral axis, not about the origin.
        q = first - found.cy * area
        width = self.width_at(level)
        span = found.bounds[1] - found.bounds[0]
        if width <= 1e-12 * max(span, 1.0) or not found.ixx:
            # At the very top and bottom there is no width and no area
            # above; both go to nothing together and so does the stress.
            return 0.0
        return force * q / (found.ixx * width)

    def shear_profile(self, force: float, points: int = 240) -> tuple:
        """(levels, stresses) up the section, for drawing.

        The levels where parts begin and end are included on purpose, a
        hair either side. That is where the width changes and the stress
        steps, and a diagram that samples evenly walks straight past it.
        """
        found = self.properties()
        _left, _right, bottom, top = found.bounds
        depth = top - bottom
        levels = [bottom + depth * index / (points - 1)
                  for index in range(points)]
        edges = []
        for part in self.parts:
            for place in part.bounds()[2:]:
                if bottom < place < top:
                    edges += [place - depth * 1e-7, place + depth * 1e-7]
        levels = sorted(set(levels + edges))
        return (levels, [self.shear_stress(force, y, found)
                         for y in levels])

    def worst_shear(self, force: float) -> tuple:
        """(stress, level) where the section is worked hardest in shear.

        Found by asking rather than assumed to be at the neutral axis. It
        usually is, and on a tee or a channel it is not.
        """
        levels, stresses = self.shear_profile(force)
        best = max(range(len(levels)), key=lambda i: abs(stresses[i]))
        return stresses[best], levels[best]

    def worst_stress(self, moment: float, sideways: float = 0.0) -> tuple:
        """(stress, x, y) at the hardest-worked corner of the shape.

        Asked of every corner rather than assumed to be at the top or the
        bottom. On a symmetrical section it is at the top or the bottom and
        this agrees; on an angle it is at the tip of a leg, which is neither.
        """
        found = self.properties()
        worst = (0.0, 0.0, 0.0)
        for part in self.parts:
            if not part.solid:
                continue
            for px, py in part.outline():
                across, up = px - found.cx, py - found.cy
                stress = found.stress_at(across, up, moment, sideways)
                if abs(stress) > abs(worst[0]):
                    worst = (stress, px, py)
        return worst

# --------------------------------------------------------------------------
# The shapes people actually have
# --------------------------------------------------------------------------
# Built from the dimensions on the drawing rather than looked up. What comes
# out is a consequence of what was typed, so a section this program has
# never heard of works exactly as well as one it has - and there is no table
# of quoted values here to fall out of date or to be wrong about.
#
# Names follow the drawings: d overall depth, b overall width, t thickness,
# tw the web, tf the flange, r the root radius.


def i_section(d: float, b: float, tw: float, tf: float,
              r: float = 0.0, name: str = "I section") -> Section:
    """A universal beam or column: two flanges and a web between them.

    The four root radii are included. They are about 2% of the second moment
    of a universal beam - small enough to dismiss and large enough that it
    is worth not dismissing, since it is 2% of every deflection worked from
    it.
    """
    if tf * 2 >= d:
        raise SectionError("The flanges are thicker than the section is deep.")
    if tw >= b:
        raise SectionError("The web is wider than the flange.")
    inner = d / 2.0 - tf                     # the flange's inside face
    parts = [
        Rectangle(x=0.0, y=d / 2.0 - tf / 2.0, width=b, height=tf),
        Rectangle(x=0.0, y=-(d / 2.0 - tf / 2.0), width=b, height=tf),
        Rectangle(x=0.0, y=0.0, width=tw, height=d - 2.0 * tf),
    ]
    for across in (1.0, -1.0):
        for up in (1.0, -1.0):
            # The corner is where the web face meets the flange's inside
            # face. The material fills outwards from the web and inwards
            # from the flange, which is why `up` goes in the other way.
            parts.append(Fillet(x=across * tw / 2.0, y=up * inner,
                                radius=r, across=across, up=-up))
    return Section(parts=parts, name=name)


def channel(d: float, b: float, tw: float, tf: float, r: float = 0.0,
            name: str = "channel") -> Section:
    """A parallel flange channel: a web with both flanges on one side.

    The first shape here whose centroid is not in the middle of it.
    """
    if tf * 2 >= d:
        raise SectionError("The flanges are thicker than the section is deep.")
    if tw >= b:
        raise SectionError("The web is thicker than the section is wide.")
    parts = [
        Rectangle(x=tw / 2.0, y=0.0, width=tw, height=d),
        Rectangle(x=tw + (b - tw) / 2.0, y=d / 2.0 - tf / 2.0,
                  width=b - tw, height=tf),
        Rectangle(x=tw + (b - tw) / 2.0, y=-(d / 2.0 - tf / 2.0),
                  width=b - tw, height=tf),
    ]
    for up in (1.0, -1.0):
        parts.append(Fillet(x=tw, y=up * (d / 2.0 - tf), radius=r,
                            across=1.0, up=-up))
    return Section(parts=parts, name=name)


def tee(d: float, b: float, tw: float, tf: float, r: float = 0.0,
        name: str = "tee") -> Section:
    """A tee, flange up, with the bottom of the stem at zero."""
    if tf >= d:
        raise SectionError("The flange is thicker than the section is deep.")
    parts = [
        Rectangle(x=0.0, y=(d - tf) / 2.0, width=tw, height=d - tf),
        Rectangle(x=0.0, y=d - tf / 2.0, width=b, height=tf),
    ]
    for across in (1.0, -1.0):
        parts.append(Fillet(x=across * tw / 2.0, y=d - tf, radius=r,
                            across=across, up=-1.0))
    return Section(parts=parts, name=name)


#: A rolled angle's toe radius as a share of its root radius. Not a
#: constant of nature - it is the proportion the sections are made to, and
#: it is here because it is what makes the shape agree with the tables:
#: square toes read 2 to 3% stiff, and at a half they land within a third
#: of a percent across eleven sections.
TOE_SHARE = 0.5


def angle(a: float, b: float, t: float, r: float = 0.0,
          toe: float = None, name: str = "angle") -> Section:
    """An angle: one leg up, one along, the heel at the origin.

    The only common section with no axis of symmetry at all, so its
    principal axes are not its legs and its weak axis runs diagonally across
    it. That is why an unrestrained angle moves sideways when it is loaded
    downwards, and why the product term is worth reporting for this one.

    *toe* is the radius on the free end of each leg, and defaults to half
    the root radius. Pass zero for something cut from plate, which really
    does have square toes.
    """
    if t >= min(a, b):
        raise SectionError("The angle is thicker than its own legs.")
    toe = r * TOE_SHARE if toe is None else toe
    parts = [
        Polygon(points=[(0.0, 0.0), (b, 0.0), (b, t), (t, t), (t, a),
                        (0.0, a)]),
        Fillet(x=t, y=t, radius=r, across=1.0, up=1.0),
    ]
    if toe > 0:
        # Off the inside corner of each leg's free end, which is the corner
        # a rolled angle does not have.
        parts.append(Fillet(x=b, y=t, radius=toe, across=-1.0, up=-1.0,
                            solid=False))
        parts.append(Fillet(x=t, y=a, radius=toe, across=-1.0, up=-1.0,
                            solid=False))
    return Section(parts=parts, name=name)


def hollow_rectangle(b: float, d: float, t: float, r: float = 0.0,
                     name: str = "rectangular hollow") -> Section:
    """RHS or SHS, rounded outside and inside.

    The corner radius is not decoration on these. Square corners read about
    3% stiffer than the real thing, and the radius is on the drawing.
    """
    if 2.0 * t >= min(b, d):
        raise SectionError("The walls meet in the middle.")
    parts = [Rectangle(x=0.0, y=0.0, width=b, height=d),
             Rectangle(x=0.0, y=0.0, width=b - 2.0 * t, height=d - 2.0 * t,
                       solid=False)]
    if r > 0:
        inside = max(r - t, 0.0)
        for across in (1.0, -1.0):
            for up in (1.0, -1.0):
                # Taken off the outside corner and put back at the inside
                # one: the void has rounded corners too, so it never took
                # that material away in the first place.
                parts.append(Fillet(x=across * b / 2.0, y=up * d / 2.0,
                                    radius=r, across=-across, up=-up,
                                    solid=False))
                if inside:
                    parts.append(
                        Fillet(x=across * (b / 2.0 - t),
                               y=up * (d / 2.0 - t), radius=inside,
                               across=-across, up=-up, solid=True))
    return Section(parts=parts, name=name)


def hollow_circle(d: float, t: float,
                  name: str = "circular hollow") -> Section:
    """CHS: a tube, by its outside diameter and its wall."""
    if 2.0 * t >= d:
        raise SectionError("The wall is thicker than the tube is wide.")
    return Section(parts=[Circle(diameter=d),
                          Circle(diameter=d - 2.0 * t, solid=False)],
                   name=name)


def solid_round(d: float, name: str = "round bar") -> Section:
    return Section(parts=[Circle(diameter=d)], name=name)


def solid_rectangle(b: float, d: float, name: str = "flat bar") -> Section:
    return Section(parts=[Rectangle(width=b, height=d)], name=name)


#: The profiles the tab offers: what builds each one, what it needs
#: measuring, and a set of dimensions to start from.
PROFILES = {
    "I section": (i_section, ("d", "b", "tw", "tf", "r"),
                  (303.4, 165.0, 6.0, 10.2, 8.9)),
    "channel": (channel, ("d", "b", "tw", "tf", "r"),
                (200.0, 75.0, 6.0, 12.5, 12.0)),
    "tee": (tee, ("d", "b", "tw", "tf", "r"),
            (100.0, 100.0, 8.0, 10.0, 8.0)),
    "angle": (angle, ("a", "b", "t", "r"), (100.0, 75.0, 10.0, 10.0)),
    "rectangular hollow": (hollow_rectangle, ("b", "d", "t", "r"),
                           (100.0, 60.0, 5.0, 7.5)),
    "circular hollow": (hollow_circle, ("d", "t"), (114.3, 5.0)),
    "round bar": (solid_round, ("d",), (50.0,)),
    "flat bar": (solid_rectangle, ("b", "d"), (100.0, 12.0)),
}

#: What each dimension is called, for the label beside the box.
DIMENSIONS = {
    "d": "depth", "b": "width", "t": "thickness", "tw": "web",
    "tf": "flange", "r": "root radius", "a": "leg up",
}
