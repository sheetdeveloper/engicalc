"""Graphing: explicit, implicit, parametric and polar curves.

The functions here draw onto a matplotlib ``Axes`` that the caller supplies, so
the same code serves the Tk window and headless PNG export.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import sympy as sp

from ..core.parsing import parse_input, parse_number

PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
           "#17becf", "#8c564b", "#e377c2"]


@dataclass
class Curve:
    expression: str
    kind: str = "explicit"        # explicit | implicit | parametric | polar
    label: str = ""
    colour: str = ""
    second: str = ""              # y(t) for parametric
    visible: bool = True


@dataclass
class PlotSpec:
    curves: list = field(default_factory=list)
    xmin: float = -10.0
    xmax: float = 10.0
    ymin: float | None = None
    ymax: float | None = None
    samples: int = 800
    grid: bool = True
    title: str = ""
    xlabel: str = "x"
    ylabel: str = "y"
    mark_roots: bool = False
    equal_aspect: bool = False
    # (lower, upper) to shade under the first explicit curve - the area a
    # definite integral actually measures.
    shade: tuple | None = None
    shade_label: str = ""


class PlotError(ValueError):
    pass


def _lambdify(expr, symbols):
    return sp.lambdify(symbols, expr, modules=["numpy", {"Abs": np.abs}])


def _eval_grid(func, values):
    with np.errstate(all="ignore"):
        out = func(values)
    out = np.asarray(out, dtype=complex)
    real = np.where(np.abs(out.imag) < 1e-9, out.real, np.nan)
    real = np.where(np.isfinite(real), real, np.nan)
    return real


def draw(spec: PlotSpec, ax) -> list:
    """Draw *spec* onto matplotlib axes *ax*. Returns any warning strings."""
    warnings: list[str] = []
    ax.clear()
    x = sp.Symbol("x")
    y = sp.Symbol("y")
    t = sp.Symbol("t")
    theta = sp.Symbol("theta")

    xs = np.linspace(spec.xmin, spec.xmax, max(50, spec.samples))
    plotted = 0

    for index, curve in enumerate(c for c in spec.curves if c.visible and c.expression.strip()):
        colour = curve.colour or PALETTE[index % len(PALETTE)]
        label = curve.label or curve.expression
        try:
            if curve.kind == "explicit":
                expr = _rhs(parse_input(curve.expression).expr)
                free = expr.free_symbols
                if free - {x}:
                    raise PlotError(
                        f"'{curve.expression}' still contains "
                        f"{', '.join(sorted(s.name for s in free - {x}))}. "
                        "Only x may be free.")
                values = _eval_grid(_lambdify(expr, [x]), xs) if free else \
                    np.full_like(xs, float(expr))
                ax.plot(xs, values, color=colour, label=label, linewidth=1.8)
                if spec.mark_roots:
                    _mark_roots(ax, expr, x, spec, colour)
                if spec.shade is not None and index == 0:
                    _shade_area(ax, expr, x, spec, colour)
                plotted += 1

            elif curve.kind == "implicit":
                parsed = parse_input(curve.expression).expr
                expr = (parsed.lhs - parsed.rhs) if isinstance(parsed, sp.Eq) else parsed
                ylo = spec.ymin if spec.ymin is not None else spec.xmin
                yhi = spec.ymax if spec.ymax is not None else spec.xmax
                n = min(400, max(120, spec.samples // 2))
                gx, gy = np.meshgrid(np.linspace(spec.xmin, spec.xmax, n),
                                     np.linspace(ylo, yhi, n))
                func = _lambdify(expr, [x, y])
                with np.errstate(all="ignore"):
                    gz = func(gx, gy)
                gz = np.asarray(gz, dtype=float)
                ax.contour(gx, gy, gz, levels=[0], colors=[colour], linewidths=1.8)
                ax.plot([], [], color=colour, label=label)
                plotted += 1

            elif curve.kind == "parametric":
                if not curve.second.strip():
                    raise PlotError("Parametric curves need both x(t) and y(t).")
                fx = _rhs(parse_input(curve.expression).expr)
                fy = _rhs(parse_input(curve.second).expr)
                ts = np.linspace(spec.xmin, spec.xmax, max(200, spec.samples))
                ax.plot(_eval_grid(_lambdify(fx, [t]), ts),
                        _eval_grid(_lambdify(fy, [t]), ts),
                        color=colour, label=label, linewidth=1.8)
                plotted += 1

            elif curve.kind == "polar":
                expr = _rhs(parse_input(curve.expression).expr)
                sym = theta if theta in expr.free_symbols else \
                    (list(expr.free_symbols)[0] if expr.free_symbols else theta)
                ts = np.linspace(spec.xmin, spec.xmax, max(400, spec.samples))
                r = _eval_grid(_lambdify(expr, [sym]), ts)
                ax.plot(r * np.cos(ts), r * np.sin(ts), color=colour,
                        label=label, linewidth=1.8)
                plotted += 1
        except PlotError as exc:
            warnings.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{curve.expression}: {exc}")

    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.axvline(0, color="#888888", linewidth=0.8)
    if spec.grid:
        ax.grid(True, alpha=0.3, linestyle=":")
    ax.set_xlim(spec.xmin, spec.xmax)
    if spec.ymin is not None and spec.ymax is not None:
        ax.set_ylim(spec.ymin, spec.ymax)
    elif plotted:
        ax.relim()
        ax.autoscale_view(scalex=False)
    if spec.equal_aspect:
        ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(spec.xlabel)
    ax.set_ylabel(spec.ylabel)
    if spec.title:
        ax.set_title(spec.title)
    if plotted:
        ax.legend(loc="best", fontsize=8, framealpha=0.85)
    return warnings


def _rhs(expr):
    """Accept 'y = x^2' as well as 'x^2'."""
    if isinstance(expr, sp.Eq):
        if expr.lhs.free_symbols == {sp.Symbol("y")}:
            return expr.rhs
        return expr.lhs - expr.rhs
    return expr


def _mark_roots(ax, expr, var, spec: PlotSpec, colour: str) -> None:
    try:
        roots = sp.solve(sp.Eq(expr, 0), var)
    except Exception:  # noqa: BLE001
        return
    for r in roots:
        try:
            rv = complex(sp.N(r))
        except (TypeError, ValueError):
            continue
        if abs(rv.imag) > 1e-9:
            continue
        if spec.xmin <= rv.real <= spec.xmax:
            ax.plot([rv.real], [0], "o", color=colour, markersize=6,
                    markerfacecolor="white", markeredgewidth=1.6, zorder=5)
            ax.annotate(f"{rv.real:.4g}", (rv.real, 0), textcoords="offset points",
                        xytext=(4, 8), fontsize=8, color=colour)


def _shade_area(ax, expr, var, spec: PlotSpec, colour: str) -> None:
    """Fill the region a definite integral measures.

    Area below the axis is drawn in a second colour, because that part counts
    as negative in the answer and a single block of shading hides the fact.
    """
    lower, upper = spec.shade
    if lower is None or upper is None:
        return
    lower, upper = float(min(lower, upper)), float(max(lower, upper))
    xs = np.linspace(lower, upper, 400)
    try:
        values = _eval_grid(_lambdify(expr, [var]), xs) \
            if expr.free_symbols else np.full_like(xs, float(expr))
    except Exception:                                   # noqa: BLE001
        return
    ax.fill_between(xs, values, 0, where=values >= 0, interpolate=True,
                    color=colour, alpha=0.25,
                    label=spec.shade_label or None)
    ax.fill_between(xs, values, 0, where=values < 0, interpolate=True,
                    color="#d62728", alpha=0.22, hatch="//",
                    edgecolor="#d62728", linewidth=0.0)
    for edge in (lower, upper):
        ax.axvline(edge, color=colour, linewidth=1.0, linestyle="--",
                   alpha=0.7)


def spec_from_result(result, xmin: float = -10, xmax: float = 10) -> PlotSpec:
    """Build a sensible plot for a :class:`CalcResult`."""
    # An integral's answer is an area, so draw what was integrated and shade
    # between the limits, rather than drawing the antiderivative.
    if result.operation == "integral" and result.integrand is not None:
        label = result.input_text or sp.sstr(result.integrand)
        spec = PlotSpec(curves=[Curve(expression=sp.sstr(result.integrand),
                                      label=label)],
                        xmin=xmin, xmax=xmax, title=label)
        if result.limits:
            low, high = result.limits
            try:
                low, high = float(sp.N(low)), float(sp.N(high))
            except (TypeError, ValueError):
                return spec
            if high < low:
                low, high = high, low
            margin = max((high - low) * 0.35, 1.0)
            spec.xmin, spec.xmax = low - margin, high + margin
            spec.shade = (low, high)
            spec.shade_label = "area = " + (
                f"{result.numeric[0]:.6g}" if result.numeric
                and isinstance(result.numeric[0], float) else "")
            spec.title = f"{label}   from {low:g} to {high:g}"
        return spec

    curves = []
    expr = result.expression
    if expr is not None:
        if isinstance(expr, sp.Eq):
            curves.append(Curve(expression=sp.sstr(expr), kind="implicit",
                                label=result.input_text))
        else:
            curves.append(Curve(expression=sp.sstr(expr), label=result.input_text))
    try:
        parsed = parse_input(result.input_text).expr
        if isinstance(parsed, sp.Eq) and parsed.free_symbols == {sp.Symbol("x")}:
            curves = [Curve(expression=sp.sstr(parsed.lhs - parsed.rhs),
                            label=result.input_text)]
    except Exception:  # noqa: BLE001
        pass
    return PlotSpec(curves=curves, xmin=xmin, xmax=xmax,
                    mark_roots=result.operation in ("solve", "roots"),
                    title=result.input_text)


def sweep(formula, target: str, values: dict, sweep_var: str,
          start, stop, points: int = 50):
    """Numeric sensitivity sweep: vary one input, recompute the target.

    Returns ``(xs, ys)`` ready for plotting or for the Excel export.
    """
    from ..formulas.library import solve_formula

    start = float(parse_number(start))
    stop = float(parse_number(stop))
    xs = np.linspace(start, stop, max(2, int(points)))
    ys = []
    for value in xs:
        trial = dict(values)
        trial[sweep_var] = repr(float(value))
        try:
            solution = solve_formula(formula, target, trial)
            ys.append(solution.value if isinstance(solution.value, float) else np.nan)
        except Exception:  # noqa: BLE001
            ys.append(np.nan)
    return xs, np.array(ys, dtype=float)
