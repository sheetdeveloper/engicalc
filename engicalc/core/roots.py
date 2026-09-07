"""Where an expression crosses zero, and how many times, inside a range.

Symbolically first, because ``x^2 = 4`` should say 2 and not 1.9999999,
and by scanning for a sign change where SymPy cannot solve it in closed
form - ``x*cos(x)`` turning where ``cos(x) = x*sin(x)`` has no closed form
and eight answers on screen.

The distinction that does the work is between *no solutions* and *no
answer*. ``solveset`` returning an empty set means it looked and there
are none; returning a ConditionSet means it could not tell. Only the
second is worth scanning for, and treating them alike would either scan
everything or quietly report nothing.

Written for the graph tab's read-off panel and used by the optimiser as
well, which is why it lives here rather than under plotting: finding real
solutions inside a range is not a drawing question.
"""

from __future__ import annotations

import numpy as np
import sympy as sp

#: The x these are written in. A plain symbol, with no assumptions on it -
#: `Symbol("x", real=True)` is a *different* symbol as far as SymPy is
#: concerned, and an expression parsed with one and searched with the
#: other comes back looking like it still has a free variable in it. The
#: realness is asked for where it matters, in the domain given to
#: solveset.
X = sp.Symbol("x")

#: How many of anything to report. Past this a panel is a wall of numbers
#: and the picture was the better answer after all.
MOST = 24

#: How finely to scan when SymPy will not solve it. A sign change between
#: neighbouring samples is what gets found, so this sets the closest two
#: solutions can be and still be told apart: over a window of 20 it is one
#: part in a hundred of the width.
SCAN = 2000

#: Bisections after a sign change is found. Sixty halvings takes a bracket
#: of any width to the last bit of a float.
REFINE = 60


def solutions(expr, lo: float, hi: float, symbol=None) -> list:
    """Every real solution of ``expr = 0`` between *lo* and *hi*."""
    return _solutions(expr, float(lo), float(hi), symbol or X)


def _solutions(expr, lo: float, hi: float, symbol) -> list:
    exact = _exactly(expr, lo, hi, symbol)
    return (exact if exact is not None
            else _by_scanning(expr, lo, hi, symbol))


def _exactly(expr, lo: float, hi: float, symbol=X):
    """The symbolic answer, or None if there is not one.

    None and an empty list are different answers and both are wanted:
    the empty list means SymPy looked and there are none, None means it
    could not tell, and only the second is worth scanning for.
    """
    try:
        answer = sp.solveset(expr, symbol, sp.S.Reals)
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


def _by_scanning(expr, lo: float, hi: float,
                 symbol=X) -> list:
    """Where the curve changes sign, pinned down by bisection.

    For everything SymPy will not solve. It finds a crossing and not a
    touch: a curve that comes down to nought and goes back up has no sign
    change and is not reported, which is a real limitation and a better
    one than a guess.
    """
    try:
        func = sp.lambdify(symbol, expr, "numpy")
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
