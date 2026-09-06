"""R134a properties, and the diagram a refrigeration cycle is drawn on.

The same three ways of asking as the steam tab, because they are the same
three ways the question is put: on the saturation line, inside the dome at a
known dryness, or at a pressure and a temperature that fix the state
outright.

The chart is pressure against enthalpy with a logarithmic pressure axis,
which is the one every refrigeration course draws a cycle on - the two
throttles are vertical lines on it and the two heat exchangers horizontal
ones, so the shape of the cycle is the shape of the drawing.

Nothing is looked up. Everything comes from the equation of state each time,
so there is no row to read between and no edge to fall off.
"""

from __future__ import annotations

import tkinter as tk
from functools import lru_cache
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..core import r134a
from ..core.display import fmt_number
from ..core.parsing import ParseError, parse_number
from ..export.excel import export_table
from . import figures
from .widgets import MONO, ScrollFrame

#: How the question is being asked.
MODES = [
    ("On the boil - saturated liquid and vapour", "saturated"),
    ("Wet, at a known dryness", "wet"),
    ("At a pressure and a temperature", "state"),
]

#: (symbol, name, unit, how to get it). The symbol first, because it is the
#: one that turns up in the equation the number is going into.
PROPERTIES = [
    ("T", "temperature", "deg C", lambda s: s.T - 273.15),
    ("p", "pressure", "kPa", lambda s: s.p / 1000.0),
    ("v", "specific volume", "m3/kg", lambda s: s.v),
    ("rho", "density", "kg/m3", lambda s: s.rho),
    ("h", "specific enthalpy", "kJ/kg", lambda s: s.h / 1000.0),
    ("u", "internal energy", "kJ/kg", lambda s: s.u / 1000.0),
    ("s", "entropy", "kJ/(kg K)", lambda s: s.s / 1000.0),
    ("cp", "heat capacity at constant p", "kJ/(kg K)",
     lambda s: s.cp / 1000.0),
    ("cv", "heat capacity at constant v", "kJ/(kg K)",
     lambda s: s.cv / 1000.0),
    ("w", "speed of sound", "m/s", lambda s: s.w),
]


@lru_cache(maxsize=1)
def _dome() -> tuple:
    """The saturation dome, as (h liquid, h vapour, pressure).

    Worked out once. Each point on it is a full saturation solve and the
    chart is redrawn on every keystroke, so doing it again each time would
    be the slowest thing in the program by a wide margin.
    """
    liquid_h, vapour_h, pressures = [], [], []
    top = r134a.T_CRITICAL - r134a.CRITICAL_MARGIN
    for step in range(90):
        T = 233.15 + (top - 233.15) * step / 89.0
        try:
            liquid, vapour = r134a.saturated(T)
        except r134a.R134aError:
            continue
        liquid_h.append(liquid.h / 1000.0)
        vapour_h.append(vapour.h / 1000.0)
        pressures.append(liquid.p / 1000.0)
    return liquid_h, vapour_h, pressures


class R134aTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.rows = []
        self.states = []
        self._build()
        self.compute()

    # -- layout -------------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="R134a", style="Title.TLabel").pack(
            side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="computed from the Tillner-Roth and Baehr equation "
                       "of state, so there is nothing to interpolate").pack(
                           side="left", padx=(10, 0))

        # Packed before the expanding pane so it keeps its height.
        # See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))

        asked = ttk.Labelframe(self, text="The state", padding=8)
        asked.pack(fill="x", pady=(6, 0))

        mode_row = ttk.Frame(asked)
        mode_row.pack(fill="x")
        ttk.Label(mode_row, text="Given").pack(side="left")
        self.mode = tk.StringVar(value=MODES[0][0])
        box = ttk.Combobox(mode_row, state="readonly", width=38,
                           textvariable=self.mode,
                           values=[label for label, _key in MODES])
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda e: self._mode_changed())

        self.fields = ttk.Frame(asked)
        self.fields.pack(fill="x", pady=(8, 0))

        self.by = tk.StringVar(value="T")
        self.by_row = ttk.Frame(self.fields)
        ttk.Radiobutton(self.by_row, text="temperature", value="T",
                        variable=self.by,
                        command=self._mode_changed).pack(side="left")
        ttk.Radiobutton(self.by_row, text="pressure", value="p",
                        variable=self.by,
                        command=self._mode_changed).pack(side="left", padx=6)

        self.temperature = tk.StringVar(value="0")
        self.pressure = tk.StringVar(value="292.8")
        self.quality = tk.StringVar(value="0.8")
        self.t_row = self._entry_row("Temperature", self.temperature,
                                     "deg C")
        self.p_row = self._entry_row("Pressure", self.pressure, "kPa")
        self.x_row = self._entry_row("Dryness x", self.quality,
                                     "0 is liquid, 1 is dry vapour")

        self.note = ttk.Label(asked, text="", style="Hint.TLabel",
                              wraplength=900, justify="left")
        self.note.pack(fill="x", pady=(6, 0))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        answer = ttk.Labelframe(panes, text="Properties", padding=6)
        self.table = ScrollFrame(answer, height=300)
        self.table.pack(fill="both", expand=True)
        panes.add(answer, weight=3)

        chart = ttk.Labelframe(panes, text="Where that is", padding=6)
        self.figure = Figure(figsize=(4.6, 3.4), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        panes.add(chart, weight=4)

        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Export...",
                   command=self.export).pack(side="right")
        ttk.Button(actions, text="Copy numbers",
                   command=self.copy).pack(side="right", padx=6)
        ttk.Button(actions, text="Copy chart",
                   command=self.copy_chart).pack(side="right")
        ttk.Button(actions, text="Save chart...",
                   command=self.save_chart).pack(side="right", padx=6)

        self._mode_changed()

    def _entry_row(self, label: str, variable: tk.StringVar, unit: str):
        row = ttk.Frame(self.fields)
        ttk.Label(row, text=label, width=13).pack(side="left")
        entry = ttk.Entry(row, textvariable=variable, width=14, font=MONO)
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self.compute())
        variable.trace_add("write", lambda *a: self.compute())
        ttk.Label(row, text=unit, style="Hint.TLabel").pack(side="left",
                                                            padx=(6, 0))
        return row

    def _key(self) -> str:
        return dict(MODES).get(self.mode.get(), "saturated")

    def _mode_changed(self) -> None:
        for row in (self.by_row, self.t_row, self.p_row, self.x_row):
            row.pack_forget()
        key = self._key()
        if key in ("saturated", "wet"):
            # On the saturation line the temperature and the pressure are
            # not independent - either one fixes the other - so only one is
            # asked for. A form taking both would be lying about that.
            self.by_row.pack(fill="x", pady=(0, 4))
            (self.t_row if self.by.get() == "T"
             else self.p_row).pack(fill="x")
            if key == "wet":
                self.x_row.pack(fill="x", pady=(4, 0))
        else:
            self.t_row.pack(fill="x")
            self.p_row.pack(fill="x", pady=(4, 0))
        self.compute()

    # -- working it out -----------------------------------------------------
    def _number(self, variable: tk.StringVar, what: str) -> float:
        value = parse_number(variable.get())
        if value is None:
            raise r134a.R134aError(f"Enter a {what}.")
        return float(value)

    def compute(self, *_args) -> None:
        # The fields are repacked as the mode changes, so this runs while
        # the form is half-built. A missing box is not worth complaining
        # about until there is something to work out.
        try:
            states, heading = self._states()
        except (r134a.R134aError, ParseError) as exc:
            self.states = []
            self.table.clear()
            self.note.configure(text=str(exc))
            self.status.configure(text="Check the state")
            return
        except Exception:                             # noqa: BLE001
            return

        self.note.configure(text="")
        self._fill(states, heading)
        self._draw()
        self.status.configure(text=heading)

    def _states(self):
        """(the states to show, a line describing them)."""
        key = self._key()
        if key in ("saturated", "wet"):
            if self.by.get() == "T":
                T = self._number(self.temperature, "temperature") + 273.15
                p = r134a.saturation_pressure(T)
            else:
                p = self._number(self.pressure, "pressure") * 1000.0
                T = r134a.saturation_temperature(p)
            where = (f"boiling at {T - 273.15:.2f} deg C and "
                     f"{p / 1000.0:.4g} kPa")
            if key == "saturated":
                liquid, vapour = r134a.saturated(T)
                return [liquid, vapour], where
            dryness = self._number(self.quality, "dryness")
            return [r134a.wet(T, dryness)], f"{where}, {dryness:g} dry"

        T = self._number(self.temperature, "temperature") + 273.15
        p = self._number(self.pressure, "pressure") * 1000.0
        found = r134a.at_pressure_and_temperature(p, T)
        phase = ("liquid" if found.T < r134a.T_CRITICAL
                 and found.p > r134a.saturation_pressure(found.T)
                 else "vapour")
        return [found], (f"{phase} at {T - 273.15:.2f} deg C and "
                         f"{p / 1000.0:.4g} kPa")

    def _phase_name(self, state) -> str:
        if state.quality == 0.0:
            return "saturated liquid"
        if state.quality == 1.0:
            return "saturated vapour"
        if state.quality is not None:
            return f"{state.quality:g} dry"
        return "single phase"

    def _fill(self, states, heading: str) -> None:
        self.table.clear()
        self.states = states
        body = self.table.body

        ttk.Label(body, text="", width=24).grid(row=0, column=0)
        for column, one in enumerate(states, start=1):
            ttk.Label(body, text=self._phase_name(one), width=18, anchor="e",
                      font=("Segoe UI", 9, "bold")).grid(
                          row=0, column=column, sticky="e", padx=6)

        self.rows = []
        for index, (symbol, name, unit, get) in enumerate(PROPERTIES,
                                                          start=1):
            ttk.Label(body, text=f"{symbol}   {name}", width=30,
                      anchor="w").grid(row=index, column=0, sticky="w",
                                       pady=1)
            values = []
            for column, one in enumerate(states, start=1):
                try:
                    value = get(one)
                except Exception:                      # noqa: BLE001
                    value = float("nan")
                shown = ("-" if value != value else fmt_number(value, 6))
                ttk.Label(body, text=shown, width=18, anchor="e",
                          font=MONO).grid(row=index, column=column,
                                          sticky="e", padx=6)
                values.append(value)
            ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                row=index, column=len(states) + 1, sticky="w", padx=(6, 0))
            self.rows.append([f"{symbol}  {name}"] + values + [unit])

        if len(states) == 2:
            # The one number a saturated pair is usually being looked up for.
            latent = (states[1].h - states[0].h) / 1000.0
            ttk.Label(body, text="hfg   latent heat", width=30,
                      anchor="w").grid(row=len(PROPERTIES) + 1, column=0,
                                       sticky="w", pady=(6, 1))
            ttk.Label(body, text=fmt_number(latent, 6), width=18,
                      anchor="e", font=MONO).grid(
                          row=len(PROPERTIES) + 1, column=1, sticky="e",
                          padx=6)
            ttk.Label(body, text="kJ/kg", style="Hint.TLabel").grid(
                row=len(PROPERTIES) + 1, column=len(states) + 1, sticky="w",
                padx=(6, 0))
            self.rows.append(["hfg  latent heat", latent, "", "kJ/kg"])

    def _draw(self) -> None:
        """Pressure against enthalpy, with the dome and the state on it."""
        try:
            self.axes.clear()
            liquid_h, vapour_h, pressures = _dome()
            self.axes.plot(liquid_h, pressures, color="#1f4e79",
                           linewidth=1.3)
            self.axes.plot(vapour_h, pressures, color="#1f4e79",
                           linewidth=1.3)
            self.axes.plot([liquid_h[-1], vapour_h[-1]],
                           [pressures[-1], pressures[-1]], color="#1f4e79",
                           linewidth=1.3)
            for one in self.states:
                self.axes.plot([one.h / 1000.0], [one.p / 1000.0], "o",
                               color="#c0392b", markersize=7, zorder=5)
            self.axes.set_yscale("log")
            self.axes.set_xlabel("specific enthalpy  kJ/kg", fontsize=8)
            self.axes.set_ylabel("pressure  kPa", fontsize=8)
            self.axes.grid(True, which="both", alpha=0.3, linestyle=":")
            self.axes.tick_params(labelsize=7)
            # Each one where its own side of the dome is not. The liquid
            # line leans right as the pressure rises, so its name goes high
            # and left; the vapour line leans left, so its name goes low and
            # right. Put at the same height they both sat on the curve they
            # were naming.
            self.axes.annotate("liquid", (0.02, 0.62),
                               xycoords="axes fraction", fontsize=7,
                               color="#1f4e79")
            self.axes.annotate("vapour", (0.90, 0.28),
                               xycoords="axes fraction", fontsize=7,
                               color="#1f4e79")
            self.axes.annotate("wet", (0.52, 0.12),
                               xycoords="axes fraction", fontsize=7,
                               color="#1f4e79")
            self.figure.tight_layout()
            self.canvas.draw_idle()
        except Exception:                             # noqa: BLE001
            pass          # a chart that will not draw must not stop the table

    # -- getting it out -----------------------------------------------------
    def _as_text(self) -> str:
        lines = ["R134a"]
        for row in self.rows:
            values = "  ".join(
                fmt_number(v, 6) if isinstance(v, float) and v == v
                else str(v) for v in row[1:-1])
            lines.append(f"    {row[0]:32} {values} {row[-1]}")
        return "\n".join(lines)

    def copy(self) -> None:
        if not self.rows:
            messagebox.showinfo("Nothing to copy", "Ask for a state first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._as_text())
        self.status.configure(text="Copied")

    def save_chart(self) -> None:
        try:
            path = figures.save_figure(self.figure, "r134a")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        if path:
            self.status.configure(text="Chart saved")

    def copy_chart(self) -> None:
        try:
            figures.copy_figure(self.figure)
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not copy", str(exc))
            return
        self.status.configure(text="Chart copied")

    def export(self) -> None:
        if not self.rows:
            messagebox.showinfo("Nothing to export", "Ask for a state first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="r134a.xlsx")
        if not path:
            return
        try:
            width = max(len(row) for row in self.rows)
            headings = (["Property"]
                        + [self._phase_name(one) for one in self.states]
                        + ["Unit"])
            headings += [""] * (width - len(headings))
            with figures.temporary_png(self.figure) as picture:
                export_table(headings[:width],
                             [list(row) + [""] * (width - len(row))
                              for row in self.rows],
                             path, title="R134a", sheet="R134a",
                             picture=picture)
            self.status.configure(text="Exported, chart and all")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))
