"""The formula library: load, group, search, extend."""

from __future__ import annotations

import importlib
import json
import os
from collections import OrderedDict

import sympy as sp

from ..core.display import fmt as _display_fmt
from ..core.engine import rearrange
from .model import Formula, Variable

_DATA_MODULES = [
    "mechanics", "strength", "thermodynamics", "fluids", "heat_transfer",
    "electrical", "civil", "manufacturing", "chemical", "control", "geometry",
    "hvac",
]

USER_FORMULA_FILE = os.path.join(
    os.path.expanduser("~"), ".engicalc", "user_formulas.json")


class FormulaLibrary:
    def __init__(self, load_user: bool = True):
        self._formulas: dict[str, Formula] = OrderedDict()
        self.load_builtin()
        if load_user:
            self.load_user_formulas()

    # -- loading ----------------------------------------------------------
    def load_builtin(self) -> None:
        for name in _DATA_MODULES:
            mod = importlib.import_module(f".data.{name}", package=__package__)
            for formula in mod.FORMULAS:
                self._formulas[formula.key] = formula

    def load_user_formulas(self, path: str = USER_FORMULA_FILE) -> int:
        if not os.path.exists(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return 0
        count = 0
        for item in payload:
            try:
                self._formulas[item["key"]] = Formula(
                    key=item["key"], name=item["name"], branch=item["branch"],
                    category=item.get("category", "User"),
                    equation=item["equation"],
                    variables=[Variable(**v) for v in item.get("variables", [])],
                    notes=item.get("notes", ""),
                    assumptions=item.get("assumptions", ""),
                    tags=tuple(item.get("tags", ())),
                    reference=item.get("reference", ""))
                count += 1
            except (KeyError, TypeError):
                continue
        return count

    def add_user_formula(self, formula: Formula,
                         path: str = USER_FORMULA_FILE) -> None:
        """Store a formula the user typed in and persist it to disk."""
        self._formulas[formula.key] = formula
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existing = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            except (OSError, json.JSONDecodeError):
                existing = []
        existing = [e for e in existing if e.get("key") != formula.key]
        existing.append({
            "key": formula.key, "name": formula.name, "branch": formula.branch,
            "category": formula.category, "equation": formula.equation,
            "variables": [v.__dict__ for v in formula.variables],
            "notes": formula.notes, "assumptions": formula.assumptions,
            "tags": list(formula.tags), "reference": formula.reference,
        })
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)

    # -- access -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self._formulas)

    def all(self) -> list[Formula]:
        return list(self._formulas.values())

    def get(self, key: str) -> Formula | None:
        return self._formulas.get(key)

    def branches(self) -> list[str]:
        return sorted({f.branch for f in self._formulas.values()})

    def categories(self, branch: str) -> list[str]:
        return sorted({f.category for f in self._formulas.values()
                       if f.branch == branch})

    def by_branch(self, branch: str) -> list[Formula]:
        return [f for f in self._formulas.values() if f.branch == branch]

    def tree(self) -> dict:
        """{branch: {category: [Formula, ...]}} for the UI tree."""
        out: dict = OrderedDict()
        for f in sorted(self._formulas.values(),
                        key=lambda x: (x.branch, x.category, x.name)):
            out.setdefault(f.branch, OrderedDict()).setdefault(f.category, []).append(f)
        return out

    def search(self, query: str) -> list[Formula]:
        """Match every whitespace-separated term against the formula text."""
        terms = [t for t in query.lower().split() if t]
        if not terms:
            return self.all()
        results = []
        for f in self._formulas.values():
            text = f.search_text()
            score = 0
            if all(t in text for t in terms):
                score = 1
                if all(t in f.name.lower() for t in terms):
                    score = 3
                elif any(t in f.name.lower() for t in terms):
                    score = 2
            if score:
                results.append((score, f.name, f))
        results.sort(key=lambda r: (-r[0], r[1]))
        return [r[2] for r in results]


# --------------------------------------------------------------------------
# Evaluating a formula
# --------------------------------------------------------------------------
class FormulaSolution:
    def __init__(self, formula: Formula, target: str, expression,
                 value=None, substitutions=None, warnings=None,
                 spread=None):
        self.formula = formula
        self.target = target
        self.expression = expression        # symbolic rearrangement
        self.value = value                  # numeric result (or None)
        self.substitutions = substitutions or {}
        self.warnings = warnings or []
        #: How far the answer moves for the tolerances that were typed in,
        #: or None where none were.
        self.spread = spread

    @property
    def unit(self) -> str:
        return self.formula.unit_of(self.target)

    def __str__(self) -> str:
        parts = [f"{self.target} = {_display_fmt(self.expression)}"]
        if self.value is not None:
            parts.append(f"{self.target} = {self.value:.6g} {self.unit}".strip())
        return "\n".join(parts)


def solve_formula(formula: Formula, target: str,
                  values: dict[str, str] | None = None) -> FormulaSolution:
    """Rearrange *formula* for *target* and, if enough values are given, evaluate it.

    ``values`` maps symbol names to strings the user typed. Blank entries are
    ignored, which is what lets the same formula solve for any variable.
    """
    from ..core.parsing import parse_number

    values = {k: v for k, v in (values or {}).items()
              if v is not None and str(v).strip() != ""}
    tgt = sp.Symbol(target)
    warnings: list[str] = []

    # Asked before trying, not after. The attempt can be abandoned but
    # it cannot be stopped, and what it leaves running is what kept the
    # window from closing.
    expr = (None if target in formula.numeric_only
            else _timed(rearrange, formula.eq, tgt, timeout=6.0))
    if expr is None:
        # A few formulas (implicit or transcendental in the target) have no
        # closed-form rearrangement - solve them numerically instead.
        return _numeric_solve(formula, target, values, warnings)
    if isinstance(expr, list):
        warnings.append(
            f"{len(expr)} solutions exist; showing the first. "
            "Others: " + ", ".join(sp.sstr(e) for e in expr[1:]))
        expr = expr[0]

    subs = {}
    for name, raw in values.items():
        if name == target:
            continue
        subs[sp.Symbol(name)] = _read_value(formula, name, raw, warnings)

    substituted = expr.subs(subs)
    value = None
    missing = sorted(s.name for s in substituted.free_symbols)
    if not missing:
        try:
            value = float(sp.N(substituted))
        except (TypeError, ValueError):
            value = complex(sp.N(substituted))
        if not _balances(formula, tgt, subs, value):
            # The rearrangement does not solve the equation it came from at
            # these values, so it is not the answer to this question. The
            # numerical route makes no claim to a closed form and is the
            # honest thing to fall back on.
            return _numeric_solve(
                formula, target, values, warnings,
                because="The rearranged formula does not satisfy the "
                        "original equation at these values, so it was not "
                        "used.")
    else:
        warnings.append("Still symbolic - no value for: " + ", ".join(missing))

    return FormulaSolution(
        formula, target, sp.simplify(expr), value,
        {str(k): sp.sstr(v) for k, v in subs.items()}, warnings,
        spread=_spread(formula, target, expr, values, value))


def _spread(formula: Formula, target: str, expression, values: dict,
            value) -> object:
    """How far the answer moves for the tolerances that were typed in.

    The rearrangement is exactly the expression to differentiate, and
    every variable already declares a unit, so the whole thing is
    dimensionally checked on the way through.

    A formula whose declared units do not balance - Manning's, and the
    Brinell rule of thumb, which carry a constant with units in it - has
    no dimensionally consistent derivative to take, so it gets no
    uncertainty rather than a wrong one.
    """
    from ..core import uncertainty
    from ..core.quantity import Quantity, parse_powers

    if value is None or formula.dimensional_constant:
        return None
    known, any_tolerance = {}, False
    for variable in formula.variables:
        if variable.symbol == target:
            continue
        raw = values.get(variable.symbol)
        if raw is None or not str(raw).strip():
            continue
        try:
            typed = Quantity.parse(str(raw))
            if variable.unit:
                # A bare number is in the unit the formula declares, which
                # is what declaring one means here and everywhere else. A
                # number with a unit on it is converted into that one, and
                # its tolerance goes with it.
                typed = (Quantity(typed.value, parse_powers(variable.unit),
                                  typed.error) if typed.plain
                         else typed.to(variable.unit, absolute=False))
        except Exception:                              # noqa: BLE001
            return None
        known[variable.symbol] = typed
        any_tolerance = any_tolerance or bool(typed.error)
    if not any_tolerance:
        return None
    try:
        answer = Quantity.of(float(value), formula.unit_of(target))
        return uncertainty.through(expression, known, answer)
    except Exception:                                  # noqa: BLE001
        # A formula whose declared units do not hold together has no
        # derivative worth taking. Better nothing than a wrong number.
        return None


#: How far the two sides of the equation may differ, relative to their own
#: size, before the rearrangement is not solving it. Floating point through a
#: formula loses a few digits, so this is nowhere near the precision of the
#: arithmetic - and a rearrangement that is actually wrong is wrong by whole
#: orders of magnitude, not by parts per million.
BALANCES = 1e-6


def _precise(value):
    """A number carried at thirty digits, so the arithmetic has room.

    The value itself is no better known for it - a float is a float - but
    the sums done with it are, and it is the sums that were going wrong.
    """
    try:
        return sp.Float(value, 30)
    except (TypeError, ValueError):
        return value              # complex, or already exact


def _balances(formula: Formula, target: sp.Symbol, subs: dict,
              value) -> bool:
    """Does putting the answer back into the equation balance it?

    The one check that was missing. A closed form that does not satisfy the
    equation it was derived from is not an answer, however plausible it
    looks, and SymPy will hand one over without comment.

    Judged on the values given rather than on invented ones. A rearrangement
    can be right for the numbers in front of it and wrong for others - the
    quadratic formula solved for `a` gives an `a` that makes x a root, which
    is the *plus* root only for some b and c - so the numbers somebody
    actually typed are the ones it has to be right for.
    """
    # Put the numbers in at more digits than a float carries. Substituting
    # ordinary floats and then asking for thirty digits recovers nothing -
    # the rounding has already happened - and on this formula it mattered:
    # (1 + 0.05/1.2e12) has three significant digits left in float64, and
    # raising it to the power 1.2e13 turned a wrong answer of 1648.72 into
    # 1647.0094976903, which is the right answer to fourteen digits. The
    # check waved it through.
    both = {name: _precise(number) for name, number in subs.items()}
    both[target] = _precise(value)
    try:
        left = complex(sp.N(formula.eq.lhs.subs(both), 30))
        right = complex(sp.N(formula.eq.rhs.subs(both), 30))
    except (TypeError, ValueError, ZeroDivisionError):
        # Cannot be put to the test, which does not make it wrong.
        return True
    if left != left or right != right:                 # NaN
        return False
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) <= BALANCES * scale


def _read_value(formula: Formula, name: str, raw: str, warnings: list):
    """Read one typed value against the unit the formula declares for it.

    ``50 mm`` in a field that wants metres becomes 0.05 and says so. A bare
    number is taken to be in the declared unit, which is what it always used
    to mean. A value in the wrong kind of unit is an error rather than a
    silent thousandfold mistake.
    """
    from ..core import units as unit_tools
    from ..core.quantity import Quantity

    variable = formula.variable(name)
    declared = variable.unit if variable else ""
    # A tolerance is read separately - see _spread - and the nominal value
    # is what gets substituted. Left in, it reaches sympify as
    # "5000 +/- 50" and fails there with a syntax error about nothing the
    # person typing it did wrong.
    wide = Quantity.TOLERANCE.match(str(raw))
    if wide:
        raw = f"{wide.group('value')} {wide.group('unit')}".strip()
    try:
        value, note = unit_tools.to_declared(str(raw), declared)
    except unit_tools.UnitError as exc:
        raise ValueError(f"{name}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not read the value for {name}: {exc}") from exc

    if note:
        warnings.append(f"{name}: {note}")
    elif variable is not None:
        # No unit was given, so nothing has been checked by conversion. The
        # typical value is the only other thing that knows what the number
        # ought to look like.
        odd = unit_tools.looks_wrong(value, variable.typical)
        if odd:
            warnings.append(f"{name}: {odd}")
    return value


def _timed(func, *args, timeout: float = 6.0):
    """Run *func*, giving up after *timeout* seconds (returns None on failure).

    SymPy occasionally disappears down a rabbit hole on an awkward
    rearrangement; the UI must not freeze while that happens.

    A Python thread cannot be killed from outside, so a call that runs away
    is abandoned rather than stopped. That is the price of the timeout being
    real, and it is meant to cost a core for a few seconds while nobody
    waits on it.

    **The thread is a daemon, and that is the whole of why this is written
    out by hand rather than using a ThreadPoolExecutor.** Executor workers
    are not daemons, and `concurrent.futures` registers an atexit hook that
    joins them - so abandoning one did not cost a core for a few seconds, it
    held the entire process open at exit for as long as the runaway call
    took. Heron's formula solved for the semi-perimeter answered in six
    seconds and then EngiCalc would not close: the window went, the process
    stayed, indefinitely. A daemon thread cannot do that. It is killed with
    the interpreter, and abandoning it is finally free.
    """
    import threading

    box: dict = {}

    def work():
        try:
            box["value"] = func(*args)
        except Exception:  # noqa: BLE001 - SymPy gave up; so do we
            box["failed"] = True

    runner = threading.Thread(target=work, daemon=True,
                              name="engicalc-rearrange")
    runner.start()
    runner.join(timeout)
    if runner.is_alive() or "failed" in box:
        return None
    return box.get("value")


def _numeric_solve(formula: Formula, target: str, values: dict,
                   warnings: list, because: str = "") -> FormulaSolution:
    """Solve by iteration, for the formulas a closed form cannot serve.

    Two ways to get here. Some formulas have no closed-form rearrangement at
    all, and some produce one that turns out not to solve the equation -
    *because* says which, since they are different things to be told.
    """
    tgt = sp.Symbol(target)
    # Read the same way the closed-form route reads them, units and all.
    # Reading them differently here meant a value typed as `50 mm` worked
    # on one path and not on the other.
    subs = {sp.Symbol(k): _read_value(formula, k, v, warnings)
            for k, v in values.items() if k != target}
    residual = formula.eq.lhs - formula.eq.rhs
    residual = residual.subs(subs)
    missing = sorted(s.name for s in residual.free_symbols if s.name != target)
    if missing:
        raise ValueError(
            f"{formula.name} has no closed-form rearrangement for {target}, so "
            "every other variable needs a value. Missing: " + ", ".join(missing))

    warnings.append(
        because or "Solved numerically - no closed-form rearrangement exists.")
    for guess in (1.0, 0.5, 2.0, 10.0, 0.1, -1.0, 100.0, 1e-3):
        try:
            root = sp.nsolve(residual, tgt, guess)
            return FormulaSolution(formula, target, sp.Eq(residual, 0),
                                   float(root),
                                   {str(k): sp.sstr(v) for k, v in subs.items()},
                                   warnings)
        except Exception:  # noqa: BLE001 - try the next starting point
            continue
    raise ValueError(
        f"Could not solve {formula.name} for {target} numerically. "
        "Check the input values are physically sensible.")


_LIBRARY: FormulaLibrary | None = None


def get_library() -> FormulaLibrary:
    """Process-wide singleton (loading is cheap but not free)."""
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = FormulaLibrary()
    return _LIBRARY
