"""Human-readable working, in the spirit of Symbolab's "show steps".

Nothing here is required to get an answer - it exists so the user can see how
the answer was reached. Every generator returns a list of ``Step`` records and
is written defensively: if a case is not recognised it simply returns fewer
steps rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from .display import fmt


@dataclass
class Step:
    title: str
    detail: str = ""
    expr: sp.Basic | None = None

    def text(self) -> str:
        parts = [self.title]
        if self.expr is not None:
            parts.append(f"    {fmt(self.expr)}")
        if self.detail:
            parts.append(f"    {self.detail}")
        return "\n".join(parts)


def _pretty(expr) -> str:
    try:
        return fmt(expr)
    except Exception:  # noqa: BLE001
        return str(expr)


# --------------------------------------------------------------------------
# Equations
# --------------------------------------------------------------------------
def equation_steps(eq: sp.Basic, var: sp.Symbol, solutions: list) -> list[Step]:
    steps: list[Step] = []

    if isinstance(eq, sp.Eq):
        lhs, rhs = eq.lhs, eq.rhs
        steps.append(Step("Start with the equation", expr=sp.Eq(lhs, rhs)))
        expr = sp.together(lhs - rhs)
        if rhs != 0:
            steps.append(
                Step(f"Move every term to the left so the right side is 0",
                     expr=sp.Eq(expr, 0)))
    else:
        expr = eq
        steps.append(Step("Start with the expression set equal to zero",
                          expr=sp.Eq(expr, 0)))

    # Clear denominators if the unknown appears in one.
    num, den = sp.fraction(sp.together(expr))
    if den.has(var) and den != 1:
        steps.append(
            Step("Multiply through by the denominator",
                 detail=f"Valid provided {_pretty(den)} != 0 "
                        "(check the answers against this at the end).",
                 expr=sp.Eq(num, 0)))
        expr = num

    expanded = sp.expand(expr)
    if expanded != expr:
        steps.append(Step("Expand the brackets", expr=sp.Eq(expanded, 0)))
    expr = expanded

    poly = None
    try:
        poly = sp.Poly(expr, var)
    except Exception:  # noqa: BLE001 - not polynomial in var
        poly = None

    if poly is not None and poly.degree() == 1:
        a, b = poly.all_coeffs()
        steps.append(Step("This is linear in " + var.name,
                          detail=f"a = {_pretty(a)},  b = {_pretty(b)}",
                          expr=sp.Eq(a * var + b, 0)))
        steps.append(Step("Subtract b, then divide by a",
                          expr=sp.Eq(var, sp.simplify(-b / a))))

    elif poly is not None and poly.degree() == 2:
        a, b, c = poly.all_coeffs()
        steps.append(Step("This is a quadratic",
                          detail=f"a = {_pretty(a)},  b = {_pretty(b)},  c = {_pretty(c)}"))
        disc = sp.simplify(b ** 2 - 4 * a * c)
        steps.append(Step("Discriminant  D = b^2 - 4ac", expr=disc))
        if disc.is_number:
            if disc.is_positive:
                note = "D > 0: two distinct real roots."
            elif disc.is_zero:
                note = "D = 0: one repeated real root."
            else:
                note = "D < 0: a complex-conjugate pair."
            steps[-1].detail = note
        factored = sp.factor(expr)
        if factored != expr and factored.is_Mul:
            steps.append(Step("It factorises, so set each factor to zero",
                              expr=sp.Eq(factored, 0)))
        else:
            steps.append(Step("Apply the quadratic formula  x = (-b +/- sqrt(D)) / (2a)",
                              expr=sp.Eq(var, (-b + sp.sqrt(disc)) / (2 * a))))

    elif poly is not None and poly.degree() > 2:
        factored = sp.factor(expr)
        steps.append(Step(f"Polynomial of degree {poly.degree()} - factor it",
                          expr=sp.Eq(factored, 0)))
        steps.append(Step("Set each factor to zero and solve"))

    else:
        steps.append(Step("Not polynomial in " + var.name,
                          detail="Solved with SymPy's general solver "
                                 "(isolation of logs/roots/trig as required)."))

    if solutions:
        for s in solutions:
            steps.append(Step(f"Solution", expr=sp.Eq(var, s)))
            check = _verify(eq, var, s)
            if check is not None:
                steps[-1].detail = check
    else:
        steps.append(Step("No solution found in the current domain"))
    return steps


def inequality_steps(rel: sp.Rel, var: sp.Symbol, solution) -> list[Step]:
    """Working for an inequality: boundary points, then which side wins.

    This is how it is done by hand - find where the two sides are equal, then
    test a point in each interval those boundaries cut the line into.
    """
    steps = [Step("Start with the inequality", expr=rel)]
    difference = sp.together(rel.lhs - rel.rhs)
    if rel.rhs != 0:
        steps.append(Step("Move every term to the left",
                          expr=rel.func(difference, 0)))

    numerator, denominator = sp.fraction(difference)
    if denominator.has(var) and denominator != 1:
        steps.append(Step(
            "The unknown is in a denominator",
            detail=f"{_pretty(denominator)} = 0 is excluded, and multiplying "
                   "by it flips the inequality where it is negative - so the "
                   "sign of each interval is tested instead."))

    boundaries = []
    try:
        found = sp.solve(sp.Eq(numerator, 0), var)
        boundaries = sorted(
            (b for b in found if b.is_real is not False and not b.free_symbols),
            key=lambda b: float(sp.N(b)))
    except Exception:  # noqa: BLE001 - not solvable is not an error here
        boundaries = []

    if boundaries:
        steps.append(Step(
            "Find the boundary points, where the two sides are equal",
            detail=", ".join(f"{var.name} = {_pretty(b)}" for b in boundaries)))
        steps.append(Step(
            "Test a point in each interval between them",
            detail="The inequality either holds across a whole interval or "
                   "fails across it, so one test point settles each."))

    if solution is not None:
        from .display import fmt_set

        steps.append(Step(f"{var.name} lies in", detail=fmt_set(solution)))
    else:
        steps.append(Step("No explicit range could be found"))
    return steps


def _verify(eq, var, sol) -> str | None:
    """Substitute the answer back in and report the residual."""
    try:
        if isinstance(eq, sp.Eq):
            residual = sp.simplify(eq.lhs.subs(var, sol) - eq.rhs.subs(var, sol))
        else:
            residual = sp.simplify(eq.subs(var, sol))
        if residual == 0:
            return "Check: substituting back gives 0 = 0."
        val = sp.N(residual, 8)
        if val.is_number and abs(complex(val)) < 1e-9:
            return "Check: substituting back gives ~0 (within numerical tolerance)."
        return f"Check: residual = {_pretty(val)} (verify domain restrictions)."
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# Calculus
# --------------------------------------------------------------------------
def derivative_steps(expr: sp.Expr, var: sp.Symbol) -> list[Step]:
    steps = [Step(f"Differentiate with respect to {var.name}",
                  expr=sp.Derivative(expr, var))]

    if expr.is_Add:
        steps.append(Step("Sum rule: differentiate term by term"))
        for term in expr.args:
            steps.append(Step(f"  d/d{var.name} [{_pretty(term)}]",
                              expr=sp.diff(term, var)))
    elif expr.is_Mul and len(expr.args) == 2 and all(a.has(var) for a in expr.args):
        u, v = expr.args
        steps.append(Step("Product rule:  (uv)' = u'v + uv'",
                          detail=f"u = {_pretty(u)},  v = {_pretty(v)}"))
        steps.append(Step("u' =", expr=sp.diff(u, var)))
        steps.append(Step("v' =", expr=sp.diff(v, var)))
    elif expr.is_Pow:
        base, power = expr.args
        if base == var and not power.has(var):
            steps.append(Step("Power rule:  d/dx x^n = n x^(n-1)",
                              detail=f"n = {_pretty(power)}"))
        elif base.has(var):
            steps.append(Step("Chain rule on the power",
                              detail=f"outer: u^{_pretty(power)},  "
                                     f"inner u = {_pretty(base)}"))
            steps.append(Step("du/d" + var.name + " =", expr=sp.diff(base, var)))
    elif expr.is_Function and expr.args and expr.args[0] != var:
        inner = expr.args[0]
        steps.append(Step("Chain rule:  d/dx f(u) = f'(u) * du/dx",
                          detail=f"u = {_pretty(inner)}"))
        steps.append(Step("du/d" + var.name + " =", expr=sp.diff(inner, var)))

    result = sp.diff(expr, var)
    steps.append(Step("Derivative", expr=result))
    simplified = sp.simplify(result)
    if simplified != result:
        steps.append(Step("Simplified", expr=simplified))
    return steps


def integral_steps(expr: sp.Expr, var: sp.Symbol, lower=None, upper=None) -> list[Step]:
    steps = [Step("Integrate with respect to " + var.name,
                  expr=sp.Integral(expr, var))]
    if expr.is_Add:
        steps.append(Step("Split the integral over the sum"))
        for term in expr.args:
            steps.append(Step(f"  integral of {_pretty(term)}",
                              expr=sp.integrate(term, var)))
    anti = sp.integrate(expr, var)
    steps.append(Step("Antiderivative F(x)", expr=anti,
                      detail="Add the constant of integration C."))
    if lower is not None and upper is not None:
        steps.append(Step("Definite integral: evaluate F(b) - F(a)",
                          detail=f"a = {_pretty(lower)},  b = {_pretty(upper)}"))
        fb = sp.simplify(anti.subs(var, upper))
        fa = sp.simplify(anti.subs(var, lower))
        steps.append(Step("F(b)", expr=fb))
        steps.append(Step("F(a)", expr=fa))
        steps.append(Step("Result", expr=sp.simplify(fb - fa)))
    return steps


def rearrangement_steps(eq: sp.Eq, target: sp.Symbol, result) -> list[Step]:
    """Steps shown when a stored engineering formula is rearranged."""
    steps = [Step("Formula", expr=eq),
             Step(f"Rearrange for {target.name}")]
    if result is not None:
        steps.append(Step(f"{target.name} =", expr=result))
    return steps
