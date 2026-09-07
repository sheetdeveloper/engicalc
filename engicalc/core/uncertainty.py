"""How wrong the answer is, given how wrong the measurements were.

Every number that came off an instrument has a tolerance on it, and an
answer worked out from three of them has one too. Quoting the answer to
six figures when the inputs were good to two is the commonest way of
overstating a result, and it is done by leaving the tolerances at the door.

Given ``sigma = F/A`` with F = 5000 +/- 50 N and A = 20 +/- 0.5 mm^2, the
answer is 250 +/- 7 N/mm^2 - and the useful part is not the 7. It is that
**the area contributes more than the force does**, so measuring the force
better would buy nothing and measuring the area better would buy a lot.
That is the question an uncertainty calculation is actually asked.

**How it is done, and why not the other way.** The standard method: the
uncertainty in the answer is the square root of the sum of the squares of
each input's uncertainty multiplied by how much the answer moves when that
input moves - its partial derivative. Those derivatives are taken
symbolically, of the whole expression at once, rather than by carrying an
error term through the arithmetic operation by operation.

That distinction matters, and it is the one thing worth getting right.
Propagating operation by operation treats every appearance of a name as a
separate measurement, so ``x*x`` comes out with root-two times the relative
error of x when the answer is twice it - the same x cannot be high and low
at the same time. Differentiating the expression handles that exactly and
needs no special case, because d(x^2)/dx is 2x and nothing had to notice
that x appeared twice.

**What it assumes**, and it is worth saying because it is not always true:
that the inputs are independent of each other, and that the answer is close
enough to a straight line over the range of the uncertainties for the first
derivative to describe it. Both hold for ordinary engineering arithmetic
with tolerances of a few per cent. Neither holds for two measurements taken
off the same badly calibrated instrument, and nothing here can tell.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import sympy as sp

from .dimensional import DimensionError, _parse, read, walk
from .quantity import Quantity, QuantityError


@dataclass
class Contribution:
    """How much one input's uncertainty puts into the answer's."""

    name: str
    #: The input's own uncertainty, in the input's unit.
    given: float
    unit: str
    #: How far the answer moves, in the answer's unit.
    moves: float
    #: The share of the total variance, 0 to 1.
    share: float

    def rows(self) -> tuple:
        return (f"    from {self.name}", self.moves,
                f"{100 * self.share:.0f}% of it")


@dataclass
class Answer:
    """The answer, its uncertainty, and where the uncertainty came from."""

    value: Quantity
    error: float
    contributions: list

    @property
    def relative(self) -> float:
        return abs(self.error / self.value.value) if self.value.value else 0.0

    @property
    def known(self) -> bool:
        return bool(self.contributions)

    def written(self) -> str:
        unit = f" {self.value.unit}" if self.value.unit else ""
        if not self.known:
            return f"{self.value.value:.10g}{unit}"
        return (f"{self.value.value:.10g} +/- {self.error:.4g}{unit}"
                f"  ({100 * self.relative:.2g}%)")

    def dominant(self):
        """The input worth measuring better, or None when nothing dominates."""
        if len(self.contributions) < 2:
            return None
        ordered = sorted(self.contributions, key=lambda c: -c.share)
        if ordered[0].share < 0.5:
            return None
        return ordered[0]

    def notes(self) -> list:
        if not self.known:
            return ["No tolerances were given, so there is no uncertainty "
                    "to work out. Write one as 5000 +/- 50 N, or as "
                    "5000 N +/- 1%."]
        said = [f"Uncertainties added in quadrature, from the partial "
                f"derivatives of the whole expression - so a name that "
                f"appears twice is counted as one measurement, which it is."]
        worst = self.dominant()
        if worst is not None:
            said.append(
                f"{worst.name} accounts for {100 * worst.share:.0f}% of it. "
                f"Measuring anything else better would buy almost nothing; "
                f"measuring {worst.name} better is the whole of what is "
                f"left.")
        elif len(self.contributions) > 1:
            said.append("No one input dominates, so there is nothing "
                        "obvious to measure better.")
        said.append("Independent inputs assumed, and the answer taken as "
                    "straight over the range of the tolerances.")
        return said


def propagate(text: str, values: dict) -> Answer:
    """Work *text* out, and how far the answer moves for the tolerances."""
    known = read(values)
    expression = _parse(text, known)
    missing = sorted(str(symbol) for symbol in expression.free_symbols
                     if str(symbol) not in known)
    if missing:
        raise DimensionError(f"Nothing was given for {', '.join(missing)}.")
    return through(expression, known)


def through(expression, known: dict, answer=None) -> Answer:
    """The same, for a caller that has already parsed and worked it out.

    The worksheet parses its own rows - it has to, because it knows what
    its rows are called - so it arrives here with the expression and the
    answer in hand and only wants the derivatives taken.
    """
    if answer is None:
        answer = walk(expression, known).tidy()
    pieces = []
    for name, given in known.items():
        if given.error is None or not given.error:
            continue
        symbol = sp.Symbol(name)
        if symbol not in expression.free_symbols:
            continue
        try:
            slope = walk(sp.diff(expression, symbol), known)
        except (DimensionError, QuantityError) as exc:
            raise DimensionError(
                f"Could not work out how the answer moves with {name}: "
                f"{exc}") from exc
        moved = (slope * Quantity(given.error, dict(given.powers))).tidy()
        try:
            moved = moved.to(answer.unit, absolute=False)
        except QuantityError as exc:
            raise DimensionError(
                f"The answer moves in {moved.unit} when {name} moves, but "
                f"the answer itself is in {answer.unit}. Those cannot both "
                f"be right. ({exc})") from exc
        pieces.append((name, given, abs(moved.value)))

    total = math.sqrt(sum(moves * moves for _n, _g, moves in pieces))
    contributions = [
        Contribution(name=name, given=given.error, unit=given.unit,
                     moves=moves,
                     share=(moves * moves / (total * total)) if total else 0.0)
        for name, given, moves in pieces]
    contributions.sort(key=lambda c: -c.share)
    return Answer(value=Quantity(answer.value, dict(answer.powers)),
                  error=total, contributions=contributions)


def rows(answer: Answer) -> list:
    """The answer as table rows, for a tab or an export."""
    unit = answer.value.unit
    found = [("answer", answer.value.value, unit)]
    if not answer.known:
        return found
    found.append(("uncertainty", answer.error, unit))
    found.append(("relative", 100 * answer.relative, "%"))
    found.append(("low", answer.value.value - answer.error, unit))
    found.append(("high", answer.value.value + answer.error, unit))
    for one in answer.contributions:
        found.append(one.rows())
    return found
