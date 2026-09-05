"""Property diagrams for water: T-s, P-v, P-h, T-v.

The chart every thermodynamics problem is worked on. The dome is what makes
it a chart rather than a graph - inside it the fluid is part liquid and part
vapour, and where a state sits relative to that line is usually the whole
question.

The dome is not drawn from a stored outline. It is the saturation line
computed from IAPWS-IF97 at a few hundred temperatures, which is the same
equation the numbers beside it come from - so the point plotted on the chart
and the figure in the table cannot disagree.

Temperature is shown in Celsius and pressure in kPa, because that is what
the rest of the app shows; the standard's kelvin and MPa stay underneath.
A pressure axis is logarithmic, since the useful range spans four decades
and a linear one would put everything below ten bar in the bottom line of
pixels.
"""

from __future__ import annotations

import numpy as np

from ..core.steam import (P_CRITICAL, T_CRITICAL, T_TRIPLE, SteamError,
                          saturated)

#: What can be drawn, and what goes on each axis.
DIAGRAMS = {
    "T-s": ("entropy", "s", "kJ/(kg K)", "temperature", "T", "deg C"),
    "P-v": ("specific volume", "v", "m3/kg", "pressure", "p", "kPa"),
    "P-h": ("enthalpy", "h", "kJ/kg", "pressure", "p", "kPa"),
    "T-v": ("specific volume", "v", "m3/kg", "temperature", "T", "deg C"),
}

#: How many points the dome is computed at. Enough that the nose near the
#: critical point is a curve rather than a corner.
POINTS = 260


def _axis_value(state, key: str) -> float:
    if key == "T":
        return state.T - 273.15
    if key == "p":
        return state.p * 1000.0
    return getattr(state, key)


def dome(kind: str = "T-s"):
    """The saturation line, as (liquid, vapour) pairs of (x, y) arrays.

    Spaced towards the critical end, where the two branches turn hard and
    an even spacing would cut the corner.
    """
    if kind not in DIAGRAMS:
        raise SteamError(f"There is no {kind} diagram; try one of "
                         f"{', '.join(DIAGRAMS)}.")
    _xl, x_key, _xu, _yl, y_key, _yu = DIAGRAMS[kind]

    # Bunched towards the critical point: the dome is nearly flat at the
    # bottom and turns sharply at the top.
    spread = np.linspace(0.0, 1.0, POINTS) ** 0.5
    temperatures = T_TRIPLE + 0.05 + spread * (T_CRITICAL - 0.05 - T_TRIPLE)

    liquid_x, liquid_y, vapour_x, vapour_y = [], [], [], []
    for T in temperatures:
        try:
            liquid, vapour = saturated(T=float(T))
        except SteamError:
            continue
        liquid_x.append(_axis_value(liquid, x_key))
        liquid_y.append(_axis_value(liquid, y_key))
        vapour_x.append(_axis_value(vapour, x_key))
        vapour_y.append(_axis_value(vapour, y_key))
    return ((np.array(liquid_x), np.array(liquid_y)),
            (np.array(vapour_x), np.array(vapour_y)))


def critical_point(kind: str = "T-s"):
    """Where the two branches of the dome meet, as (x, y)."""
    _xl, x_key, _xu, _yl, y_key, _yu = DIAGRAMS[kind]
    # Just below the critical temperature: at it exactly the two phases are
    # the same state and the property routines have nothing to return.
    liquid, vapour = saturated(T=T_CRITICAL - 0.05)
    x = (_axis_value(liquid, x_key) + _axis_value(vapour, x_key)) / 2.0
    if y_key == "T":
        return x, T_CRITICAL - 273.15
    if y_key == "p":
        return x, P_CRITICAL * 1000.0
    return x, (_axis_value(liquid, y_key) + _axis_value(vapour, y_key)) / 2.0


def draw(axes, kind: str = "T-s", states=(), quality_lines: bool = True):
    """Draw the diagram on *axes*, marking each state in *states*."""
    x_label, x_key, x_unit, y_label, y_key, y_unit = DIAGRAMS[kind]
    (liquid_x, liquid_y), (vapour_x, vapour_y) = dome(kind)

    axes.clear()
    axes.plot(liquid_x, liquid_y, "-", color="#1f4e79", linewidth=1.4,
              label="saturated liquid")
    axes.plot(vapour_x, vapour_y, "-", color="#c0392b", linewidth=1.4,
              label="saturated vapour")

    if quality_lines:
        # Lines of constant dryness, which is how a point inside the dome is
        # read off. Drawn faintly: they are a background grid, not data.
        for fraction in (0.2, 0.4, 0.6, 0.8):
            axes.plot(liquid_x + fraction * (vapour_x - liquid_x),
                      liquid_y + fraction * (vapour_y - liquid_y),
                      ":", color="#9aa1ab", linewidth=0.7, zorder=1)

    x_critical, y_critical = critical_point(kind)
    axes.plot([x_critical], [y_critical], "o", color="#111111",
              markersize=4, zorder=5)
    axes.annotate("critical point", (x_critical, y_critical),
                  textcoords="offset points", xytext=(6, 4), fontsize=7,
                  color="#444444")

    for index, state in enumerate(states or ()):
        # Labelled once. Each point is annotated with its own phase beside
        # it, and repeating those in the legend would say "saturated liquid"
        # twice - once for the line, once for the dot on it.
        axes.plot([_axis_value(state, x_key)], [_axis_value(state, y_key)],
                  "o", color="#0b7a3b", markersize=7, zorder=6,
                  label="this state" if index == 0 else None)
        axes.annotate(state.phase, (_axis_value(state, x_key),
                                    _axis_value(state, y_key)),
                      textcoords="offset points", xytext=(8, -10),
                      fontsize=7, color="#0b7a3b")

    if y_key == "p":
        # Four decades of pressure; linear would put everything below ten
        # bar into the bottom row of pixels.
        axes.set_yscale("log")
    if x_key == "v":
        axes.set_xscale("log")

    axes.set_xlabel(f"{x_label}  {x_unit}", fontsize=8)
    axes.set_ylabel(f"{y_label}  {y_unit}", fontsize=8)
    axes.grid(True, alpha=0.3, linestyle=":")
    axes.tick_params(labelsize=7)
    axes.legend(loc="best", fontsize=7, framealpha=0.85)
    return axes
