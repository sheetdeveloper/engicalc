"""Pin-jointed frames, solved at the joints.

A truss is a set of straight bars pinned at their ends, and because a pin
carries no moment every bar carries load along itself and nothing else. So
each joint is a set of forces meeting at a point, and a point in a plane
gives two equations - the forces balance across and up. That is the whole
method.

Doing it by hand means choosing joints in an order where only two members
are unknown at a time, which is a puzzle in itself and the part that goes
wrong. Written as one system it is 2n equations in as many unknowns, solved
at once, and the order stops mattering.

Tension is positive throughout. A bar pulls on the joints at its ends when
it is in tension and pushes when it is in compression, which is the sign
convention that makes the arithmetic come out and is worth stating because
half of textbooks use the other one.

Two things come free and are worth having. The count says at once whether
the frame is solvable at all - a truss with too few members is a mechanism
and will fold, one with too many cannot be settled by statics - and that is
more use than any number. And zero-force members are found rather than
spotted, which is the other classic exam question and the other thing people
miss.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .parsing import ParseError

#: How small a force has to be, against the largest in the frame, before it
#: is being carried by rounding rather than by the bar.
NOTHING = 1e-9


class TrussError(ParseError):
    """Raised when a frame cannot be worked out."""


@dataclass
class Node:
    """A joint, and what holds it if anything does."""

    x: float
    y: float
    #: "free", "pin" - held both ways - or "roller", held vertically only.
    support: str = "free"

    @property
    def restraints(self) -> int:
        return {"free": 0, "roller": 1, "pin": 2}.get(self.support, 0)


@dataclass
class Member:
    """A bar between two joints."""

    start: int
    end: int


@dataclass
class Load:
    """A force applied at a joint, in newtons. Up and right are positive."""

    node: int
    across: float = 0.0
    up: float = 0.0


@dataclass
class Truss:
    """A pin-jointed frame."""

    nodes: list = field(default_factory=list)
    members: list = field(default_factory=list)
    loads: list = field(default_factory=list)

    def check(self) -> None:
        if len(self.nodes) < 2:
            raise TrussError("A frame needs at least two joints.")
        if not self.members:
            raise TrussError("A frame needs at least one member.")
        for index, member in enumerate(self.members, 1):
            for end in (member.start, member.end):
                if not 0 <= end < len(self.nodes):
                    raise TrussError(
                        f"Member {index} is joined to a node that is not "
                        f"there.")
            if member.start == member.end:
                raise TrussError(
                    f"Member {index} starts and ends at the same joint.")
            if self.length_of(member) <= 0:
                raise TrussError(
                    f"Member {index} has no length - its two joints are in "
                    f"the same place.")
        for load in self.loads:
            if not 0 <= load.node < len(self.nodes):
                raise TrussError("A load is applied to a joint that is not "
                                 "there.")

    def length_of(self, member: Member) -> float:
        start, end = self.nodes[member.start], self.nodes[member.end]
        return math.hypot(end.x - start.x, end.y - start.y)

    def direction_of(self, member: Member) -> tuple:
        """The unit vector from the start joint towards the end one."""
        start, end = self.nodes[member.start], self.nodes[member.end]
        length = self.length_of(member)
        return ((end.x - start.x) / length, (end.y - start.y) / length)

    # -- is it solvable at all? --------------------------------------------
    @property
    def restraints(self) -> int:
        return sum(node.restraints for node in self.nodes)

    @property
    def determinacy(self) -> int:
        """Members plus restraints, less the equations. Nought is solvable.

        Negative is a mechanism - not enough bars to hold its shape, and it
        will fold rather than carry anything. Positive is statically
        indeterminate, which a real frame often is and which the joints
        alone cannot settle.
        """
        return (len(self.members) + self.restraints
                - 2 * len(self.nodes))

    def solve(self) -> "Solution":
        """Every member force and every reaction, in one system.

        Each joint gives two equations. Each member and each restraint is
        one unknown. Written out and solved together rather than joint by
        joint, so there is no order to find and nothing to get stuck on.
        """
        self.check()
        spare = self.determinacy
        if spare < 0:
            raise TrussError(
                f"This frame is a mechanism: {len(self.members)} members "
                f"and {self.restraints} restraints against "
                f"{2 * len(self.nodes)} equations, so it is {-spare} short. "
                f"It will fold rather than carry anything.")
        if spare > 0:
            raise TrussError(
                f"This frame has {spare} more members or restraints than "
                f"statics can settle. A frame like that is held by how much "
                f"each bar stretches, which the joints alone cannot say.")

        count = len(self.members) + self.restraints
        matrix = np.zeros((2 * len(self.nodes), count))
        wanted = np.zeros(2 * len(self.nodes))

        for column, member in enumerate(self.members):
            across, up = self.direction_of(member)
            # A bar in tension pulls each of its joints towards the other.
            matrix[2 * member.start, column] = across
            matrix[2 * member.start + 1, column] = up
            matrix[2 * member.end, column] = -across
            matrix[2 * member.end + 1, column] = -up

        column = len(self.members)
        reactions = []
        for index, node in enumerate(self.nodes):
            if node.support == "pin":
                matrix[2 * index, column] = 1.0
                matrix[2 * index + 1, column + 1] = 1.0
                reactions += [(index, "across"), (index, "up")]
                column += 2
            elif node.support == "roller":
                matrix[2 * index + 1, column] = 1.0
                reactions.append((index, "up"))
                column += 1

        for load in self.loads:
            wanted[2 * load.node] -= load.across
            wanted[2 * load.node + 1] -= load.up

        try:
            found = np.linalg.solve(matrix, wanted)
        except np.linalg.LinAlgError as exc:
            raise TrussError(
                "The frame has the right number of members but they are "
                "arranged so that it still cannot stand - three joints in a "
                "line, or a part of it free to turn.") from exc

        return Solution(
            truss=self,
            forces=[float(v) for v in found[:len(self.members)]],
            reactions=[(node, way, float(value)) for (node, way), value
                       in zip(reactions, found[len(self.members):])])


@dataclass
class Solution:
    """What every bar carries, and what holds the frame up."""

    truss: Truss
    forces: list
    reactions: list

    @property
    def biggest(self) -> float:
        return max((abs(force) for force in self.forces), default=0.0)

    def zero_members(self) -> list:
        """The bars carrying nothing.

        Found rather than spotted. They are not useless - they hold the
        others straight, and take load as soon as the loading changes - but
        under this loading they carry nothing at all.
        """
        limit = NOTHING * max(self.biggest, 1.0)
        return [index for index, force in enumerate(self.forces)
                if abs(force) <= limit]

    def rows(self) -> list:
        rows = []
        for index, force in enumerate(self.forces, 1):
            kind = ("zero" if abs(force) <= NOTHING * max(self.biggest, 1.0)
                    else "tension" if force > 0 else "compression")
            rows.append((f"member {index}", force / 1000.0, f"kN {kind}"))
        for node, way, value in self.reactions:
            rows.append((f"reaction at joint {node + 1}, {way}",
                         value / 1000.0, "kN"))
        return rows

    def notes(self) -> list:
        said = []
        spare = self.zero_members()
        if spare:
            names = ", ".join(str(index + 1) for index in spare)
            said.append(
                f"Member{'s' if len(spare) > 1 else ''} {names} "
                f"{'carry' if len(spare) > 1 else 'carries'} nothing under "
                f"this loading. They are not useless - they hold the rest "
                f"straight and take load the moment the loading changes - "
                f"but nothing goes through them here.")

        pulls = [force for force in self.forces if force > 0]
        pushes = [force for force in self.forces if force < 0]
        if pushes:
            said.append(
                f"The hardest-worked bar in compression carries "
                f"{min(pushes) / 1000.0:.4g} kN. A bar in compression can "
                f"buckle, so that one is sized on its length as well as on "
                f"its force - unlike the {len(pulls)} in tension.")
        return said


def warren(spans: int, span: float, height: float,
           load: float = 0.0) -> Truss:
    """A Warren girder: the one every course starts with.

    Equal triangles, pinned at one end and on a roller at the other, with
    the load hung from the bottom joints.
    """
    if spans < 1:
        raise TrussError("A girder needs at least one bay.")
    nodes, members, loads = [], [], []
    for index in range(spans + 1):
        nodes.append(Node(index * span, 0.0))
    for index in range(spans):
        nodes.append(Node((index + 0.5) * span, height))

    bottom = list(range(spans + 1))
    top = list(range(spans + 1, spans + 1 + spans))
    for index in range(spans):
        members.append(Member(bottom[index], bottom[index + 1]))
    for index in range(spans - 1):
        members.append(Member(top[index], top[index + 1]))
    for index in range(spans):
        members.append(Member(bottom[index], top[index]))
        members.append(Member(top[index], bottom[index + 1]))

    nodes[0].support = "pin"
    nodes[spans].support = "roller"
    if load:
        for index in bottom[1:-1]:
            loads.append(Load(index, up=-load))
    return Truss(nodes=nodes, members=members, loads=loads)


# --------------------------------------------------------------------------
# Writing one down
# --------------------------------------------------------------------------
def parse(text: str) -> Truss:
    """A frame from three kinds of line.

        node   x y [pin|roller]
        member first second
        load   joint across up

    Joints are numbered from one in the order they are written. Blank lines
    and anything after a # are ignored, so a frame can be commented like
    any other working.
    """
    nodes, members, loads = [], [], []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        parts = line.replace(",", " ").split()
        kind = parts[0].lower()
        try:
            if kind.startswith("n"):
                held = parts[3].lower() if len(parts) > 3 else "free"
                if held not in ("free", "pin", "roller"):
                    raise TrussError(
                        f"Line {number}: a joint is free, on a pin or on a "
                        f"roller, not '{parts[3]}'.")
                nodes.append(Node(float(parts[1]), float(parts[2]), held))
            elif kind.startswith("m"):
                members.append(Member(int(parts[1]) - 1, int(parts[2]) - 1))
            elif kind.startswith("l"):
                loads.append(Load(int(parts[1]) - 1, float(parts[2]),
                                  float(parts[3])))
            else:
                raise TrussError(
                    f"Line {number}: lines start with node, member or "
                    f"load - not '{parts[0]}'.")
        except TrussError:
            raise
        except (IndexError, ValueError) as exc:
            raise TrussError(
                f"Line {number} does not read as a {kind[:1] and kind}: "
                f"{raw.strip()}") from exc

    if not nodes:
        raise TrussError("No joints. Start with a line like `node 0 0 pin`.")
    return Truss(nodes=nodes, members=members, loads=loads)


def as_text(truss: Truss) -> str:
    """The frame written back out, which is how a preset reaches the box."""
    lines = ["# joints: x  y  [pin|roller]"]
    for node in truss.nodes:
        held = "" if node.support == "free" else f" {node.support}"
        lines.append(f"node {node.x:g} {node.y:g}{held}")
    lines.append("")
    lines.append("# members: the two joints each one runs between")
    for member in truss.members:
        lines.append(f"member {member.start + 1} {member.end + 1}")
    if truss.loads:
        lines.append("")
        lines.append("# loads: joint, across, up - in newtons")
        for load in truss.loads:
            lines.append(f"load {load.node + 1} {load.across:g} "
                         f"{load.up:g}")
    return "\n".join(lines)
