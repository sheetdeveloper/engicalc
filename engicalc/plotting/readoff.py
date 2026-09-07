"""The numbers you would otherwise read off a graph with a ruler.

A plot answers "what does it look like". The questions that follow are
always the same three - where does it cross zero, where does it turn
round, and where do two of them meet - and answering them by squinting at
the picture is how a graph gets misread.

So they are computed. Symbolically first, because ``x^2 = 4`` should say
2 and not 1.9999999, and numerically when SymPy cannot solve the thing in
closed form, because ``x*cos(x)`` having no closed form for its turning
points is not a reason to leave them off.

Everything is clipped to the window on screen. A sine has infinitely many
roots and a panel listing them would be no more use than the picture; the
seven that are actually in view are.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from ..core.parsing import parse_input
from ..core.roots import MOST, X, solutions

#: The solving lives in `core.roots` - finding where something crosses
#: zero inside a range is not a drawing question, and the optimiser wants
#: it too. What is here is what to do with the answers.


@dataclass
class Feature:
    """One thing worth reading off, and where it is."""

    kind: str            # "root", "turning point", "crossing"
    where: str           # which curve, or which two
    x: float
    y: float
    detail: str = ""     # "minimum", "maximum", ...

    def __str__(self) -> str:
        return f"{self.kind} of {self.where} at x = {self.x:.6g}"


def read_off(spec, curves=None) -> list:
    """Roots, turning points and crossings of the explicit curves.

    Only the explicit ones. A root of an implicit curve is a point on a
    contour rather than a number, and a parametric curve crosses zero at a
    value of t rather than of x - both are real questions with different
    answers, and answering them as though they were this one would be
    worse than not answering.
    """
    wanted = []
    for curve in (curves if curves is not None else spec.curves):
        if curve.kind != "explicit" or not curve.visible:
            continue
        if not curve.expression.strip():
            continue
        try:
            expr = parse_input(curve.expression).expr
            expr = (expr.lhs - expr.rhs) if isinstance(expr, sp.Eq) else expr
        except Exception:                                  # noqa: BLE001
            continue
        if expr.free_symbols - {X}:
            continue
        wanted.append((curve.label or curve.expression, expr))

    lo, hi = float(spec.xmin), float(spec.xmax)
    found = []
    for name, expr in wanted:
        for at in solutions(expr, lo, hi):
            found.append(Feature("root", name, at, 0.0))
        slope = sp.diff(expr, X)
        for at in solutions(slope, lo, hi):
            found.append(Feature("turning point", name, at,
                                 _value(expr, at), _which_way(expr, at)))

    for first in range(len(wanted)):
        for second in range(first + 1, len(wanted)):
            (one, left), (other, right) = wanted[first], wanted[second]
            for at in solutions(left - right, lo, hi):
                found.append(Feature("crossing", f"{one} and {other}",
                                     at, _value(left, at)))

    found.sort(key=lambda one: (one.x, one.kind))
    return _thinned(found)


# --------------------------------------------------------------------------
# Saying what a turning point is
# --------------------------------------------------------------------------
def _which_way(expr, at: float) -> str:
    """Minimum, maximum, or neither, from the second derivative."""
    try:
        bend = float(sp.diff(expr, X, 2).subs(X, at))
    except Exception:                                      # noqa: BLE001
        return ""
    if bend > 1e-9:
        return "minimum"
    if bend < -1e-9:
        return "maximum"
    return "flat"          # an inflection, or a stationary point of order 3


def _value(expr, at: float) -> float:
    try:
        return float(sp.N(expr.subs(X, at)))
    except Exception:                                      # noqa: BLE001
        return float("nan")


def _thinned(found: list) -> list:
    """Drop repeats: the same feature found twice at the same place.

    A root of x^3 - 3x at nought and a crossing of two curves at nought
    are two different things and both stay. The same root reported twice
    because it came out of both routes is one thing and goes once.
    """
    kept = []
    for one in found:
        same = any(other.kind == one.kind and other.where == one.where
                   and abs(other.x - one.x) < 1e-7 for other in kept)
        if not same:
            kept.append(one)
    return kept[:MOST * 3]
