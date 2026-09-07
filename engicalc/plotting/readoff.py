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

import numpy as np
import sympy as sp

from ..core.parsing import parse_input

#: The x the parser uses. A plain symbol, with no assumptions on it -
#: `Symbol("x", real=True)` is a *different* symbol as far as SymPy is
#: concerned, and an expression parsed with one and searched with the
#: other comes back looking like it still has a free variable in it. The
#: realness is asked for where it matters, in the domain given to
#: solveset.
X = sp.Symbol("x")

#: How many of anything to report. Past this the panel is a wall of
#: numbers and the picture was the better answer after all.
MOST = 24

#: How finely to scan when SymPy will not solve it. A sign change between
#: neighbouring samples is what gets found, so this sets the closest two
#: features can be and still be told apart: over a window of 20 it is one
#: part in a hundred of the width.
SCAN = 2000

#: Bisections after a sign change is found. Sixty halvings takes a bracket
#: of any width to the last bit of a float.
REFINE = 60


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
        for at in _solutions(expr, lo, hi):
            found.append(Feature("root", name, at, 0.0))
        slope = sp.diff(expr, X)
        for at in _solutions(slope, lo, hi):
            found.append(Feature("turning point", name, at,
                                 _value(expr, at), _which_way(expr, at)))

    for first in range(len(wanted)):
        for second in range(first + 1, len(wanted)):
            (one, left), (other, right) = wanted[first], wanted[second]
            for at in _solutions(left - right, lo, hi):
                found.append(Feature("crossing", f"{one} and {other}",
                                     at, _value(left, at)))

    found.sort(key=lambda one: (one.x, one.kind))
    return _thinned(found)


# --------------------------------------------------------------------------
# Solving
# --------------------------------------------------------------------------
def _solutions(expr, lo: float, hi: float) -> list:
    """Every real solution of ``expr = 0`` between *lo* and *hi*."""
    exact = _exactly(expr, lo, hi)
    return exact if exact is not None else _by_scanning(expr, lo, hi)


def _exactly(expr, lo: float, hi: float):
    """The symbolic answer, or None if there is not one.

    None and an empty list are different answers and both are wanted:
    the empty list means SymPy looked and there are none, None means it
    could not tell, and only the second is worth scanning for.
    """
    try:
        answer = sp.solveset(expr, X, sp.S.Reals)
    except Exception:                                      # noqa: BLE001
        return None
    got = _spread(answer, lo, hi)
    return None if got is None else sorted(got)


def _spread(answer, lo: float, hi: float):
    """Solutions inside the window, or None if the set is not enumerable.

    ``solveset`` answers a periodic equation with an ImageSet - the whole
    infinite family, indexed by an integer. Walking that index over a
    range and keeping what lands in the window is what turns "n*pi for
    every whole n" into the seven roots of a sine that are on screen.
    """
    if isinstance(answer, sp.FiniteSet):
        return [v for v in (_real(one) for one in answer)
                if v is not None and lo <= v <= hi]
    if isinstance(answer, sp.Union):
        together = []
        for part in answer.args:
            got = _spread(part, lo, hi)
            if got is None:
                return None
            together += got
        return together
    if isinstance(answer, sp.sets.fancysets.ImageSet):
        rule = answer.lamda
        found = []
        for step in range(-500, 501):
            try:
                value = _real(rule(step))
            except Exception:                              # noqa: BLE001
                continue
            if value is not None and lo <= value <= hi:
                found.append(value)
                if len(found) >= MOST:
                    break
        return found
    if answer is sp.S.EmptySet:
        return []
    # A ConditionSet, an Interval, or anything else: SymPy has not
    # answered the question, so say so rather than reporting nothing.
    return None


def _real(one):
    """*one* as a real number, or None if it is complex or not a number."""
    try:
        got = complex(sp.N(one))
    except (TypeError, ValueError):
        return None
    return got.real if abs(got.imag) < 1e-9 else None


def _by_scanning(expr, lo: float, hi: float) -> list:
    """Where the curve changes sign, pinned down by bisection.

    For everything SymPy will not solve. It finds a crossing and not a
    touch: a curve that comes down to nought and goes back up has no sign
    change and is not reported, which is a real limitation and a better
    one than a guess.
    """
    try:
        func = sp.lambdify(X, expr, "numpy")
    except Exception:                                      # noqa: BLE001
        return []
    xs = np.linspace(lo, hi, SCAN)
    try:
        with np.errstate(all="ignore"):
            ys = np.asarray(func(xs), dtype=float) * np.ones_like(xs)
    except Exception:                                      # noqa: BLE001
        return []

    fine = np.isfinite(ys)
    found = []
    for at in range(len(xs) - 1):
        if not (fine[at] and fine[at + 1]) or ys[at] == 0.0:
            continue
        if np.sign(ys[at]) == np.sign(ys[at + 1]):
            continue
        found.append(_between(func, xs[at], xs[at + 1], ys[at]))
        if len(found) >= MOST:
            break
    return [one for one in found if one is not None]


def _between(func, low: float, high: float, at_low: float):
    """Bisect between two samples that straddle a sign change."""
    for _ in range(REFINE):
        middle = (low + high) / 2.0
        try:
            here = float(func(middle))
        except Exception:                                  # noqa: BLE001
            return None
        if not np.isfinite(here):
            return None
        if np.sign(here) == np.sign(at_low):
            low, at_low = middle, here
        else:
            high = middle
    return (low + high) / 2.0


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
