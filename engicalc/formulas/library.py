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
                 value=None, substitutions=None, warnings=None):
        self.formula = formula
        self.target = target
        self.expression = expression        # symbolic rearrangement
        self.value = value                  # numeric result (or None)
        self.substitutions = substitutions or {}
        self.warnings = warnings or []

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

    expr = _timed(rearrange, formula.eq, tgt, timeout=6.0)
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
    else:
        warnings.append("Still symbolic - no value for: " + ", ".join(missing))

    return FormulaSolution(formula, target, sp.simplify(expr), value,
                           {str(k): sp.sstr(v) for k, v in subs.items()}, warnings)


def _read_value(formula: Formula, name: str, raw: str, warnings: list):
    """Read one typed value against the unit the formula declares for it.

    ``50 mm`` in a field that wants metres becomes 0.05 and says so. A bare
    number is taken to be in the declared unit, which is what it always used
    to mean. A value in the wrong kind of unit is an error rather than a
    silent thousandfold mistake.
    """
    from ..core import units as unit_tools

    variable = formula.variable(name)
    declared = variable.unit if variable else ""
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
    """
    import concurrent.futures as cf

    with cf.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func, *args)
        try:
            return future.result(timeout=timeout)
        except Exception:  # noqa: BLE001 - timeout, or SymPy gave up
            pool.shutdown(wait=False, cancel_futures=True)
            return None


def _numeric_solve(formula: Formula, target: str, values: dict,
                   warnings: list) -> FormulaSolution:
    from ..core.parsing import parse_number

    tgt = sp.Symbol(target)
    subs = {sp.Symbol(k): parse_number(v) for k, v in values.items() if k != target}
    residual = formula.eq.lhs - formula.eq.rhs
    residual = residual.subs(subs)
    missing = sorted(s.name for s in residual.free_symbols if s.name != target)
    if missing:
        raise ValueError(
            f"{formula.name} has no closed-form rearrangement for {target}, so "
            "every other variable needs a value. Missing: " + ", ".join(missing))

    warnings.append("Solved numerically - no closed-form rearrangement exists.")
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
