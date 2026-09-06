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
    # Hand-written LaTeX, for notation SymPy has no object for - the
    # evaluation bar in a definite integral, say. Preferred over `expr` when
    # the step is drawn; `expr` and `detail` still carry the plain-text form.
    latex: str = ""
    # A step that names the rule being used rather than the result of using
    # it. Always generated - it costs nothing and means the switch that
    # shows them does not have to work the answer out again - and shown only
    # when the working is asked for.
    minor: bool = False

    def drawn(self):
        """What to typeset for this step."""
        return self.latex or self.expr

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
# The rules themselves, stated as a textbook states them
# --------------------------------------------------------------------------
def _integration_rule(term, var):
    """(name, the rule in notation, the term integrated) for one term.

    Only the rules worth naming. Anything else falls through to None and the
    step is simply not offered, which is better than inventing a name for
    whatever SymPy did.
    """
    x = sp.latex(var)

    if not term.has(var):
        return ("Integral of a constant",
                r"\int k \,d" + x + " = k" + x,
                sp.integrate(term, var))

    coefficient, rest = term.as_independent(var, as_Add=False)
    if coefficient != 1 and rest.has(var):
        inner = _integration_rule(rest, var)
        if inner is not None:
            return ("Constant multiple",
                    r"\int k\,f(" + x + r")\,d" + x
                    + r" = k \int f(" + x + r")\,d" + x,
                    sp.integrate(term, var))

    if term == var:
        return ("Power rule",
                r"\int " + x + r"^{n} \,d" + x + " = \\frac{" + x
                + "^{n+1}}{n+1}",
                sp.integrate(term, var))

    if term.is_Pow and term.base == var and not term.exp.has(var):
        if term.exp == -1:
            return ("Reciprocal",
                    r"\int \frac{1}{" + x + r"} \,d" + x
                    + r" = \ln\left|" + x + r"\right|",
                    sp.integrate(term, var))
        return ("Power rule",
                r"\int " + x + r"^{n} \,d" + x + " = \\frac{" + x
                + "^{n+1}}{n+1}" + r",\quad n = " + sp.latex(term.exp),
                sp.integrate(term, var))

    if isinstance(term, sp.exp):
        return ("Exponential",
                r"\int e^{k" + x + r"} \,d" + x + r" = \frac{e^{k" + x
                + "}}{k}",
                sp.integrate(term, var))

    for function, statement in (
            (sp.sin, r"\int \sin(" + x + r")\,d" + x + r" = -\cos(" + x + ")"),
            (sp.cos, r"\int \cos(" + x + r")\,d" + x + r" = \sin(" + x + ")")):
        if isinstance(term, function):
            return (f"Integral of {function.__name__}", statement,
                    sp.integrate(term, var))
    return None


def _derivative_rule(expr, var):
    """(name, the rule in notation) for the shape of *expr*."""
    x = sp.latex(var)
    d = r"\frac{d}{d" + x + "}"

    if not expr.has(var):
        return ("Derivative of a constant", d + " k = 0")
    if expr == var:
        return ("Power rule", d + " " + x + " = 1")
    if expr.is_Pow and expr.base == var and not expr.exp.has(var):
        return ("Power rule",
                d + " " + x + "^{n} = n\\," + x + "^{n-1}"
                + r",\quad n = " + sp.latex(expr.exp))
    if isinstance(expr, sp.exp):
        return ("Exponential", d + " e^{k" + x + "} = k\\,e^{k" + x + "}")
    if isinstance(expr, sp.log):
        return ("Logarithm", d + r" \ln(" + x + r") = \frac{1}{" + x + "}")
    if isinstance(expr, sp.sin):
        return ("Derivative of sin", d + r" \sin(" + x + r") = \cos(" + x + ")")
    if isinstance(expr, sp.cos):
        return ("Derivative of cos",
                d + r" \cos(" + x + r") = -\sin(" + x + ")")
    return None


def _derivative_rule_pair(expr, var):
    """:func:`_derivative_rule`, padded to the shape :func:`_rule_steps` wants."""
    rule = _derivative_rule(expr, var)
    return None if rule is None else (rule[0], rule[1], None)


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
        # One move at a time, each shown with what it leaves behind. This is
        # the transposition written out - the part that is obvious once you
        # can already do it, and the whole difficulty before that.
        if b != 0:
            # Adding four is the same move as taking away minus four, and it
            # is the one a person would say they were doing.
            moving = sp.simplify(-b)
            word = "Add" if moving.is_positive else "Take"
            amount = _pretty(moving if moving.is_positive else b)
            steps.append(_both_sides(
                f"{word} {amount} {'to' if word == 'Add' else 'from'} "
                "both sides", sp.Eq(a * var, moving)))
        if a != 1:
            steps.append(_both_sides(
                f"Divide both sides by {_pretty(a)}",
                sp.Eq(var, sp.simplify(-b / a))))
        steps.append(Step("Which gives", expr=sp.Eq(var, sp.simplify(-b / a))))

    elif poly is not None and poly.degree() == 2:
        a, b, c = poly.all_coeffs()
        steps.append(Step("This is a quadratic",
                          detail=f"a = {_pretty(a)},  b = {_pretty(b)},  c = {_pretty(c)}"))
        disc = sp.simplify(b ** 2 - 4 * a * c)
        # With the numbers in it. `(-5)^2 - 4(2)(-3)` is the step somebody
        # writes down; `49` is the result of having taken it.
        steps.append(Step(
            "Put the numbers into  D = b^2 - 4ac",
            latex=(r"D = \left(" + sp.latex(b) + r"\right)^{2} - 4\left("
                   + sp.latex(a) + r"\right)\left(" + sp.latex(c)
                   + r"\right) = " + sp.latex(disc)),
            minor=True))
        steps.append(Step("Discriminant  D = b^2 - 4ac", expr=disc))
        if disc.is_number and disc.is_nonnegative:
            steps.append(Step("Root of the discriminant",
                              expr=sp.Eq(sp.sqrt(sp.Symbol("D")),
                                         sp.sqrt(disc)),
                              minor=True))
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
            for piece in factored.args:
                if piece.has(var):
                    steps.extend(_solve_factor(piece, var))
        else:
            steps.append(Step(
                "The quadratic formula",
                latex=sp.latex(var) + r" = \frac{-b \pm \sqrt{b^{2} - 4ac}}"
                      r"{2a}",
                minor=True))
            steps.append(Step(
                "With the numbers in",
                latex=(sp.latex(var) + r" = \frac{-\left(" + sp.latex(b)
                       + r"\right) \pm \sqrt{" + sp.latex(disc)
                       + r"}}{2\left(" + sp.latex(a) + r"\right)}"),
                minor=True))
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
    x = sp.latex(var)
    steps = [Step(f"Differentiate with respect to {var.name}",
                  expr=sp.Derivative(expr, var))]

    if expr.is_Add:
        steps.append(Step("Sum rule: differentiate term by term",
                          latex=r"\frac{d}{d" + x
                                + r"}\left(f + g\right) = \frac{df}{d" + x
                                + r"} + \frac{dg}{d" + x + "}",
                          minor=True))
        for term in expr.args:
            steps.extend(_rule_steps(term, var, _derivative_rule_pair))
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


def _rule_steps(term, var, rule_for) -> list[Step]:
    """The rule used on one term, stated and then named again if nested.

    A constant multiple is two rules, not one: the constant comes out and
    then something is done to what is left. Showing only the first is the
    gap that made `2x` become `x^2` with nothing in between.
    """
    out = []
    rule = rule_for(term, var)
    if rule is None:
        return out
    out.append(Step(rule[0], latex=rule[1], minor=True))
    if rule[0] == "Constant multiple":
        _coefficient, rest = term.as_independent(var, as_Add=False)
        inner = rule_for(rest, var)
        if inner is not None:
            out.append(Step(inner[0], latex=inner[1], minor=True))
    return out



def _solve_factor(factor, var: sp.Symbol) -> list[Step]:
    """Set one factor to zero and transpose it, a move at a time.

    A factorised quadratic is two linear equations, and the working on each
    is the working on any linear equation - which is what somebody turning
    the steps on is asking to see.
    """
    out = []
    try:
        poly = sp.Poly(factor, var)
    except Exception:                                 # noqa: BLE001
        return out
    if poly.degree() != 1:
        return out
    a, b = poly.all_coeffs()
    out.append(Step(f"Set {_pretty(factor)} to zero",
                    expr=sp.Eq(factor, 0), minor=True))
    if b != 0:
        moving = sp.simplify(-b)
        word = "Add" if moving.is_positive else "Take"
        amount = _pretty(moving if moving.is_positive else b)
        out.append(Step(
            f"{word} {amount} {'to' if word == 'Add' else 'from'} both sides",
            expr=sp.Eq(a * var, moving), minor=True))
    if a != 1:
        out.append(Step(f"Divide both sides by {_pretty(a)}",
                        expr=sp.Eq(var, sp.simplify(-b / a)), minor=True))
    return out

def _both_sides(what: str, equation) -> Step:
    """One move of a transposition, with the equation it leaves behind."""
    return Step(what, expr=equation, minor=True)


def integral_steps(expr: sp.Expr, var: sp.Symbol, lower=None, upper=None) -> list[Step]:
    x = sp.latex(var)
    steps = [Step("Integrate with respect to " + var.name,
                  expr=sp.Integral(expr, var))]
    if expr.is_Add:
        steps.append(Step("Split the integral over the sum",
                          latex=r"\int \left(f + g\right)\,d" + x
                                + r" = \int f\,d" + x + r" + \int g\,d" + x,
                          minor=True))
        for term in expr.args:
            steps.extend(_rule_steps(term, var, _integration_rule))
            steps.append(Step(f"  integral of {_pretty(term)}",
                              expr=sp.integrate(term, var)))
    else:
        steps.extend(_rule_steps(expr, var, _integration_rule))
    anti = sp.integrate(expr, var)
    if lower is None or upper is None:
        steps.append(Step("Antiderivative F(x)", expr=anti,
                          detail="Add the constant of integration C."))
        return steps

    steps.append(Step("Antiderivative F(x)", expr=anti))

    # Written the way it is written by hand: the antiderivative inside a
    # tall bar carrying the limits, then the subtraction, then the answer,
    # all on one line. Three separate steps for F(b), F(a) and the result
    # is not how anyone sets this out.
    fb = sp.simplify(anti.subs(var, upper))
    fa = sp.simplify(anti.subs(var, lower))
    answer = sp.simplify(fb - fa)
    try:
        # The limits are nested a level deeper than an ordinary script, so
        # they draw at about half the body size rather than 70% of it.
        # mathtext has no \scriptstyle to ask for that directly.
        bar = (r"\left. " + sp.latex(anti) + r" \right|"
               + "_{{}_{" + sp.latex(lower) + "}}"
               + "^{{}^{" + sp.latex(upper) + "}} = "
               + sp.latex(fb) + " - " + sp.latex(fa) + " = " + sp.latex(answer))
    except Exception:  # noqa: BLE001 - fall back to the plain wording
        bar = ""
    steps.append(Step(
        "Evaluate between the limits",
        latex=bar,
        expr=None if bar else answer,
        detail=f"[ F(x) ] from {_pretty(lower)} to {_pretty(upper)}"
               f"  =  F(b) - F(a)  =  {_pretty(fb)} - {_pretty(fa)}"))
    steps.append(Step("Result", expr=answer))
    return steps


def rearrangement_steps(eq: sp.Eq, target: sp.Symbol, result) -> list[Step]:
    """Steps shown when a stored engineering formula is rearranged."""
    steps = [Step("Formula", expr=eq),
             Step(f"Rearrange for {target.name}")]
    if result is not None:
        steps.append(Step(f"{target.name} =", expr=result))
    return steps
