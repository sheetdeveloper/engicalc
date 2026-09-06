"""The computation engine.

Every public function returns a :class:`CalcResult` so that the UI, the CLI, the
history store and the Excel exporter all consume the same shape of object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sympy as sp

from . import steps as steps_mod
from .display import fmt as _display_fmt
from .display import fmt_set as _display_set
from .parsing import ParseError, parse_input, parse_number, parse_system

OPERATIONS = [
    "solve", "simplify", "expand", "factor", "evaluate",
    "derivative", "integral", "limit", "series", "roots", "system", "ode",
]


@dataclass
class CalcResult:
    operation: str
    input_text: str
    results: list = field(default_factory=list)      # SymPy objects
    result_text: str = ""
    latex: str = ""
    numeric: list = field(default_factory=list)      # floats / complex
    steps: list = field(default_factory=list)        # steps_mod.Step
    variable: str | None = None
    expression: sp.Basic | None = None               # canonical expr/eq
    assumptions: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    plottable: bool = False
    # For a definite integral the answer is an area, so the thing worth
    # drawing is the integrand between the limits - not the antiderivative,
    # which is what `expression` holds.
    integrand: sp.Basic | None = None
    limits: tuple | None = None

    def summary(self) -> str:
        return self.result_text or "(no result)"

    def steps_text(self) -> str:
        return "\n\n".join(s.text() for s in self.steps)


def _fmt(obj) -> str:
    return _display_fmt(obj)


def _to_float(value):
    try:
        n = sp.N(value, 15)
        if n.is_real:
            return float(n)
        c = complex(n)
        return c
    except Exception:  # noqa: BLE001
        return None


def _pick_variable(expr, requested: str | None) -> sp.Symbol | None:
    free = sorted(expr.free_symbols, key=lambda s: s.name)
    if requested:
        for s in free:
            if s.name == requested:
                return s
        return sp.Symbol(requested)
    if not free:
        return None
    for preferred in ("x", "y", "t", "z"):
        for s in free:
            if s.name == preferred:
                return s
    return free[0]


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def calculate(text: str, operation: str = "solve", variable: str | None = None,
              subs: dict | None = None, **kwargs) -> CalcResult:
    """Run *operation* on *text*. ``subs`` maps variable name -> value string."""
    operation = operation.lower().strip()
    if operation == "system":
        return solve_system(text, subs=subs)
    if operation == "ode":
        # Imported here: core.odes imports CalcResult from this module, so a
        # module-level import would be circular.
        from .odes import solve_ode

        return solve_ode(text, variable=variable or "x",
                         conditions=str(kwargs.get("conditions", "") or ""))

    parsed = parse_input(text)
    expr = parsed.expr
    subs_map = _build_subs(subs, expr)
    if subs_map:
        expr = expr.subs(subs_map)

    if operation == "solve":
        return _solve(text, expr, variable, subs_map)
    if operation == "roots":
        return _roots(text, expr, variable)
    if operation in ("simplify", "expand", "factor"):
        return _rewrite(text, expr, operation)
    if operation == "evaluate":
        return _evaluate(text, expr, subs_map)
    if operation == "derivative":
        return _derivative(text, expr, variable, int(kwargs.get("order", 1) or 1))
    if operation == "integral":
        return _integral(text, expr, variable,
                         kwargs.get("lower"), kwargs.get("upper"))
    if operation == "limit":
        return _limit(text, expr, variable, kwargs.get("point", "0"),
                      kwargs.get("direction", "+"))
    if operation == "series":
        return _series(text, expr, variable, kwargs.get("point", "0"),
                       int(kwargs.get("order", 6) or 6))
    raise ParseError(f"Unknown operation {operation!r}")


def _build_subs(subs: dict | None, expr) -> dict:
    out = {}
    if not subs:
        return out
    names = {s.name: s for s in expr.free_symbols}
    for key, raw in subs.items():
        if raw is None or str(raw).strip() == "":
            continue
        sym = names.get(key, sp.Symbol(key))
        out[sym] = parse_number(raw)
    return out


# --------------------------------------------------------------------------
# Individual operations
# --------------------------------------------------------------------------
def _solve(text, expr, variable, subs_map) -> CalcResult:
    # An inequality is not an equation with a different sign on it - its
    # answer is a range, not a list of points. Wrapping one in Eq(expr, 0),
    # which is what the equation path below does to anything that is not
    # already an Eq, asks SymPy to solve `Eq(Le(...), 0)` and gets back
    # nothing, which used to surface as a confident "No solution."
    if isinstance(expr, sp.Rel) and not isinstance(expr, sp.Equality):
        return _solve_inequality(text, expr, variable)

    var = _pick_variable(expr, variable)
    res = CalcResult(operation="solve", input_text=text, expression=expr,
                     variable=var.name if var else None, plottable=True)
    if var is None:
        # No unknowns: it is a numeric identity check.
        truth = sp.simplify(expr.lhs - expr.rhs) == 0 if isinstance(expr, sp.Eq) else expr
        res.result_text = f"{truth}"
        return res

    target = sp.Eq(expr.lhs, expr.rhs) if isinstance(expr, sp.Eq) else sp.Eq(expr, 0)

    sols = []
    try:
        sols = sp.solve(target, var, dict=False)
    except Exception as exc:  # noqa: BLE001
        res.warnings.append(f"Symbolic solve failed ({exc}); trying numerically.")

    if not sols:
        numeric = _numeric_roots(target, var)
        if numeric:
            sols = numeric
            res.warnings.append("No closed form found - these are numerical roots.")

    sols = [sp.simplify(s) if not s.free_symbols else s for s in sols]
    res.results = sols
    res.numeric = [_to_float(s) for s in sols]
    res.result_text = "\n".join(
        f"{var.name} = {_fmt(s)}" + (f"   ≈ {_pretty_num(n)}" if n is not None
                                     and _fmt(s) != _pretty_num(n) else "")
        for s, n in zip(sols, res.numeric)) or "No solution."
    try:
        res.latex = r" ,\quad ".join(sp.latex(sp.Eq(var, s)) for s in sols)
    except Exception:  # noqa: BLE001
        res.latex = ""
    res.steps = steps_mod.equation_steps(target, var, sols)
    return res


def _solve_inequality(text, rel, variable) -> CalcResult:
    """Solve an inequality or a not-equal, giving the range that satisfies it.

    The answer is reported as a set - ``[-3, 3]``, ``(-inf, -2) or (2, inf)`` -
    because that is what an inequality has for an answer. ``expression`` is
    left as the difference, so the plot draws the curve whose sign is the
    question and marks the points where it changes.
    """
    var = _pick_variable(rel, variable)
    difference = sp.together(rel.lhs - rel.rhs)
    res = CalcResult(operation="solve", input_text=text, expression=difference,
                     variable=var.name if var else None, plottable=True)

    if var is None:
        # No unknowns: it is a true-or-false statement about numbers.
        res.result_text = str(bool(rel))
        res.results = [rel]
        return res

    solution = None
    try:
        solution = sp.solveset(rel, var, sp.S.Reals)
    except Exception as exc:  # noqa: BLE001
        res.warnings.append(f"Could not solve the inequality ({exc}).")

    if solution is None or isinstance(solution, sp.ConditionSet):
        res.warnings.append(
            "No explicit range found; the condition is shown unchanged.")
        res.result_text = _fmt(rel)
        res.results = [rel] if solution is None else [solution]
        res.steps = steps_mod.inequality_steps(rel, var, solution)
        return res

    res.results = [solution]
    res.result_text = f"{var.name} in {_display_set(solution)}"
    if solution is sp.S.EmptySet or solution == sp.S.EmptySet:
        res.result_text = "No value of " + var.name + " satisfies it."
    try:
        res.latex = sp.latex(var) + r" \in " + sp.latex(solution)
    except Exception:  # noqa: BLE001
        res.latex = ""
    res.steps = steps_mod.inequality_steps(rel, var, solution)
    return res


def _numeric_roots(target, var, span=(-50, 50), samples=400):
    expr = target.lhs - target.rhs if isinstance(target, sp.Eq) else target
    if expr.free_symbols - {var}:
        return []
    found = []
    try:
        f = sp.lambdify(var, expr, "math")
    except Exception:  # noqa: BLE001
        return []
    lo, hi = span
    prev_x = lo
    prev_y = None
    for i in range(samples + 1):
        x = lo + (hi - lo) * i / samples
        try:
            y = f(x)
        except Exception:  # noqa: BLE001
            prev_y = None
            prev_x = x
            continue
        if isinstance(y, complex):
            prev_y = None
            prev_x = x
            continue
        if prev_y is not None and prev_y * y <= 0:
            try:
                r = sp.nsolve(expr, var, (prev_x + x) / 2)
                r = sp.nsimplify(r, rational=False)
                if all(abs(float(r) - float(k)) > 1e-7 for k in found):
                    found.append(r)
            except Exception:  # noqa: BLE001
                pass
        prev_x, prev_y = x, y
    return found


def _roots(text, expr, variable) -> CalcResult:
    var = _pick_variable(expr, variable)
    e = expr.lhs - expr.rhs if isinstance(expr, sp.Eq) else expr
    res = CalcResult(operation="roots", input_text=text, expression=e,
                     variable=var.name if var else None, plottable=True)
    try:
        rd = sp.roots(sp.Poly(e, var))
        res.results = list(rd.keys())
        res.result_text = "\n".join(
            f"{var.name} = {_fmt(r)}  (multiplicity {m})" for r, m in rd.items())
    except Exception:  # noqa: BLE001
        return _solve(text, expr, variable, {})
    res.numeric = [_to_float(r) for r in res.results]
    return res


def _rewrite(text, expr, operation) -> CalcResult:
    func = {"simplify": sp.simplify, "expand": sp.expand, "factor": sp.factor}[operation]
    if isinstance(expr, sp.Eq):
        out = sp.Eq(func(expr.lhs), func(expr.rhs))
    else:
        out = func(expr)
    res = CalcResult(operation=operation, input_text=text, expression=out,
                     results=[out], result_text=_fmt(out), plottable=True)
    res.latex = sp.latex(out)
    res.steps = [steps_mod.Step("Input", expr=expr),
                 steps_mod.Step(operation.capitalize() + "d", expr=out)]
    res.numeric = [_to_float(out)] if not out.free_symbols else []
    return res


def _evaluate(text, expr, subs_map) -> CalcResult:
    e = expr.lhs - expr.rhs if isinstance(expr, sp.Eq) else expr
    res = CalcResult(operation="evaluate", input_text=text, expression=e)
    if e.free_symbols:
        res.warnings.append(
            "Unassigned symbols: " + ", ".join(sorted(s.name for s in e.free_symbols)))
        res.results = [sp.simplify(e)]
        res.result_text = _fmt(res.results[0])
        return res
    exact = sp.simplify(e)
    value = sp.N(exact, 15)
    res.results = [exact]
    res.numeric = [_to_float(exact)]
    res.result_text = f"{_fmt(exact)}\n= {_pretty_num(value)}"
    res.latex = sp.latex(exact)
    if subs_map:
        res.steps = [steps_mod.Step(
            "Substitute", detail=", ".join(f"{k} = {_fmt(v)}" for k, v in subs_map.items()))]
    res.steps.append(steps_mod.Step("Result", expr=value))
    return res


def _derivative(text, expr, variable, order) -> CalcResult:
    e = expr.rhs if isinstance(expr, sp.Eq) else expr
    var = _pick_variable(e, variable)
    d = sp.diff(e, var, order)
    res = CalcResult(operation="derivative", input_text=text, expression=d,
                     variable=var.name, results=[d], plottable=True)
    res.result_text = f"d^{order}/d{var.name}^{order} = {_fmt(sp.simplify(d))}" \
        if order > 1 else f"d/d{var.name} = {_fmt(sp.simplify(d))}"
    res.latex = sp.latex(sp.simplify(d))
    if order == 1:
        res.steps = steps_mod.derivative_steps(e, var)
    else:
        res.steps = [steps_mod.Step(f"Differentiate {order} times", expr=d)]
    return res


def _integral(text, expr, variable, lower, upper) -> CalcResult:
    e = expr.rhs if isinstance(expr, sp.Eq) else expr
    var = _pick_variable(e, variable)
    lo = parse_number(lower) if lower not in (None, "") else None
    hi = parse_number(upper) if upper not in (None, "") else None
    if lo is not None and hi is not None:
        out = sp.integrate(e, (var, lo, hi))
    else:
        out = sp.integrate(e, var)
    res = CalcResult(operation="integral", input_text=text, expression=out,
                     variable=var.name, results=[out], plottable=True,
                     integrand=e,
                     limits=(lo, hi) if (lo is not None and hi is not None)
                     else None)
    tail = "" if (lo is not None and hi is not None) else " + C"
    res.result_text = _fmt(out) + tail
    if not out.free_symbols:
        res.numeric = [_to_float(out)]
        res.result_text += f"\n= {_pretty_num(sp.N(out, 12))}"
    res.latex = sp.latex(out)
    res.steps = steps_mod.integral_steps(e, var, lo, hi)
    return res


def _limit(text, expr, variable, point, direction) -> CalcResult:
    e = expr.rhs if isinstance(expr, sp.Eq) else expr
    var = _pick_variable(e, variable)
    pt = parse_number(point) if point not in (None, "") else sp.Integer(0)
    d = direction if direction in ("+", "-") else "+"
    out = sp.limit(e, var, pt, d)
    res = CalcResult(operation="limit", input_text=text, expression=out,
                     variable=var.name, results=[out],
                     result_text=f"limit = {_fmt(out)}", plottable=True)
    res.latex = sp.latex(sp.Limit(e, var, pt, d)) + " = " + sp.latex(out)
    res.steps = [steps_mod.Step(f"Take the limit as {var.name} -> {_fmt(pt)}{d}",
                                expr=sp.Limit(e, var, pt, d)),
                 steps_mod.Step("Result", expr=out)]
    if not out.free_symbols:
        res.numeric = [_to_float(out)]
    return res


def _series(text, expr, variable, point, order) -> CalcResult:
    e = expr.rhs if isinstance(expr, sp.Eq) else expr
    var = _pick_variable(e, variable)
    pt = parse_number(point) if point not in (None, "") else sp.Integer(0)
    out = sp.series(e, var, pt, order)
    res = CalcResult(operation="series", input_text=text, expression=out.removeO(),
                     variable=var.name, results=[out], result_text=_fmt(out),
                     plottable=True)
    res.latex = sp.latex(out)
    res.steps = [steps_mod.Step(
        f"Taylor expansion about {var.name} = {_fmt(pt)} to order {order}", expr=out)]
    return res


def solve_system(text, subs: dict | None = None) -> CalcResult:
    parts = parse_system(text)
    eqs = []
    for p in parts:
        eqs.append(p.expr if isinstance(p.expr, sp.Eq) else sp.Eq(p.expr, 0))
    unknowns = sorted({s for e in eqs for s in e.free_symbols}, key=lambda s: s.name)
    if subs:
        smap = {sp.Symbol(k): parse_number(v) for k, v in subs.items()
                if str(v).strip() != ""}
        eqs = [e.subs(smap) for e in eqs]
        unknowns = [u for u in unknowns if u not in smap]

    res = CalcResult(operation="system", input_text=text,
                     variable=", ".join(u.name for u in unknowns))
    sol = sp.solve(eqs, unknowns, dict=True)
    res.results = sol
    if not sol:
        res.result_text = "No solution (or the system is inconsistent)."
        return res
    lines = []
    for i, s in enumerate(sol, 1):
        prefix = f"Solution {i}: " if len(sol) > 1 else ""
        lines.append(prefix + ", ".join(f"{k} = {_fmt(v)}" for k, v in s.items()))
    res.result_text = "\n".join(lines)
    res.steps = [steps_mod.Step(f"Equation {i}", expr=e) for i, e in enumerate(eqs, 1)]
    res.steps.append(steps_mod.Step(
        f"Solve simultaneously for {', '.join(u.name for u in unknowns)}"))
    for line in lines:
        res.steps.append(steps_mod.Step(line))
    return res


def _pretty_num(value, digits: int = 10) -> str:
    try:
        n = sp.N(value, digits)
        if n.is_real:
            f = float(n)
            if f == int(f) and abs(f) < 1e15:
                return str(int(f))
            return f"{f:.10g}"
        return str(n)
    except Exception:  # noqa: BLE001
        return str(value)


#: Values put in to tell one branch of a rearrangement from another.
#: Positive, and awkward enough that nothing cancels by luck.
_TRIAL_VALUES = (sp.Rational(11, 7), sp.Rational(23, 13), sp.Rational(7, 3))


def _branch_rank(expression, equation: sp.Eq, target: sp.Symbol) -> tuple:
    """How good a rearrangement this is. Lower sorts first.

    The only thing insisted on is that it solves the equation it came from.
    A power like `Rh^(2/3)` has more than one branch and only some of them
    are solutions; taking whichever was listed first gave a negative
    hydraulic radius that did not satisfy Manning's equation at all.

    Real is preferred to complex after that, and no further judgement is
    made - whether a root should be positive is a question about the
    problem, not about the algebra.

    Done in ordinary floating point, which is ample to tell +0.75 from
    -0.75, and with one substitution rather than two. Working to twenty-five
    digits and substituting through the equation twice was correct and put
    the test suite from two minutes to over ten.
    """
    others = sorted(equation.free_symbols - {target}, key=lambda s: s.name)
    numbers = {s: float(_TRIAL_VALUES[i % len(_TRIAL_VALUES)]) + i
               for i, s in enumerate(others)}
    try:
        value = complex(expression.subs(numbers).evalf())
        residual = complex(
            (equation.lhs - equation.rhs).subs(numbers).subs(
                target, value).evalf())
    except (TypeError, ValueError, ZeroDivisionError):
        # Cannot be judged at these values, which does not make it wrong.
        return (1, 1)
    scale = max(abs(value), 1.0)
    return (0 if abs(residual) < 1e-9 * scale else 1,
            0 if abs(value.imag) < 1e-9 * scale else 1)


def rearrange(equation: sp.Eq, target: sp.Symbol):
    """Solve an equation symbolically for one of its symbols (formula library).

    More than one branch usually means a power or a root, and only some
    branches are solutions of the equation. They are ordered so a real one
    that satisfies it comes first; the rest are still returned, because
    which is wanted can be a question about the problem.
    """
    sols = sp.solve(equation, target, dict=False)
    if not sols:
        return None
    simplified = [sp.simplify(s) for s in sols]
    if len(simplified) == 1:
        return simplified[0]
    # Only worth putting numbers through something small. A branch too big
    # to evaluate quickly is left in the order SymPy gave it.
    if max(sp.count_ops(e) for e in simplified) > 40:
        return simplified
    return sorted(simplified,
                  key=lambda e: _branch_rank(e, equation, target))
