"""Steam tables, without the table.

Three ways of asking, because those are the three ways a question is put:
somewhere on the saturation line, somewhere inside the dome at a known
dryness, or at a pressure and temperature that fix the state outright.

Nothing is looked up and nothing is interpolated - the properties are
computed from IAPWS-IF97 each time - so there is no row to read between and
no edge to fall off. What the tab does have to do is refuse clearly: a state
in the regions the standard covers but this does not is an error rather than
a number from the wrong equations.

Everything is entered and shown in the units a course uses - degrees Celsius
and kPa - while the standard underneath works in kelvin and MPa.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..core.display import fmt_number
from ..core.engine import CalcResult
from ..core.parsing import ParseError, parse_number
from ..core.steam import (P_CRITICAL, T_CRITICAL, SteamError, saturated,
                          saturation_pressure, saturation_temperature, state,
                          wet)
from ..core.steps import Step
from ..plotting.property_plot import DIAGRAMS, draw
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..export.excel import export_table
from .widgets import MONO, ScrollFrame

#: How the question is being asked.
MODES = [
    ("On the boil - saturated liquid and vapour", "saturated"),
    ("Wet steam, at a known dryness", "wet"),
    ("At a pressure and a temperature", "state"),
]

#: What each property is called and what it is measured in.
LABELS = {
    "v": ("specific volume", "m3/kg"),
    "h": ("specific enthalpy", "kJ/kg"),
    "u": ("internal energy", "kJ/kg"),
    "s": ("entropy", "kJ/(kg K)"),
}


class SteamTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.rows = []
        self.result = None
        self._build()
        self.compute()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Water and steam",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="computed from IAPWS-IF97, so there is nothing to "
                       "interpolate").pack(side="left", padx=(10, 0))

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
                        command=self.compute).pack(side="left")
        ttk.Radiobutton(self.by_row, text="pressure", value="p",
                        variable=self.by,
                        command=self.compute).pack(side="left", padx=6)

        self.temperature = tk.StringVar(value="100")
        self.pressure = tk.StringVar(value="101.325")
        self.quality = tk.StringVar(value="0.8")
        self.t_row = self._entry_row("Temperature", self.temperature, "deg C")
        self.p_row = self._entry_row("Pressure", self.pressure, "kPa")
        self.x_row = self._entry_row("Dryness x", self.quality,
                                     "0 is liquid, 1 is dry steam")

        self.note = ttk.Label(asked, text="", style="Hint.TLabel",
                              wraplength=900, justify="left")
        self.note.pack(fill="x", pady=(6, 0))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        answer = ttk.Labelframe(panes, text="Properties", padding=6)
        self.table = ScrollFrame(answer, height=300)
        self.table.pack(fill="both", expand=True)
        panes.add(answer, weight=3)

        # The chart beside the numbers. Where a state sits - inside the dome
        # or outside it, near the critical point or nowhere near - is usually
        # the actual question, and it is the thing a table cannot show.
        chart = ttk.Labelframe(panes, text="Where that is", padding=6)
        picker = ttk.Frame(chart)
        picker.pack(fill="x")
        ttk.Label(picker, text="Diagram").pack(side="left")
        self.diagram = tk.StringVar(value="T-s")
        box = ttk.Combobox(picker, state="readonly", width=8,
                           textvariable=self.diagram, values=list(DIAGRAMS))
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda e: self._draw())
        self.figure = Figure(figsize=(4.6, 3.4), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart)
        self.canvas.get_tk_widget().pack(fill="both", expand=True,
                                         pady=(4, 0))
        panes.add(chart, weight=4)

        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right")
        ttk.Button(actions, text="Export...",
                   command=self.export).pack(side="right", padx=6)
        ttk.Button(actions, text="Copy",
                   command=self.copy).pack(side="right")

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
            # Inside the dome, and on its edge, temperature and pressure are
            # not independent - one fixes the other - so only one is asked
            # for. A form that took both would be lying about that.
            self.by_row.pack(fill="x", pady=(0, 4))
            (self.t_row if self.by.get() == "T" else self.p_row).pack(fill="x")
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
            raise SteamError(f"Enter a {what}.")
        return float(value)

    def compute(self, *_args) -> None:
        # The pickers are rebuilt as the mode changes, so this runs while the
        # form is half-built; a missing field is not an error worth shouting
        # about until there is something to work out.
        try:
            states, heading = self._states()
        except (SteamError, ParseError) as exc:
            self.result = None
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

    def _draw(self) -> None:
        """Redraw the chart with the current states marked."""
        try:
            draw(self.axes, self.diagram.get(), self.result or ())
            self.figure.tight_layout()
            self.canvas.draw_idle()
        except Exception:                             # noqa: BLE001
            pass          # a chart that will not draw must not stop the table

    def _states(self):
        """(the states to show, a line describing them)."""
        key = self._key()
        by_temperature = self.by.get() == "T"

        if key in ("saturated", "wet"):
            if by_temperature:
                T = self._number(self.temperature, "temperature") + 273.15
                p = saturation_pressure(T)
            else:
                p = self._number(self.pressure, "pressure") / 1000.0
                T = saturation_temperature(p)
            where = (f"boiling at {T - 273.15:.2f} deg C "
                     f"and {p * 1000:.4g} kPa")
            if key == "saturated":
                liquid, vapour = saturated(T=T)
                return [liquid, vapour], where
            dryness = self._number(self.quality, "dryness")
            return [wet(dryness, T=T)], f"{where}, {dryness:g} dry"

        T = self._number(self.temperature, "temperature") + 273.15
        p = self._number(self.pressure, "pressure") / 1000.0
        found = state(p, T)
        return [found], f"{found.phase} at {T - 273.15:.2f} deg C and {p * 1000:.4g} kPa"

    def _fill(self, states, heading: str) -> None:
        self.table.clear()
        self.result = states
        body = self.table.body

        ttk.Label(body, text="", width=22).grid(row=0, column=0)
        for column, one in enumerate(states, start=1):
            ttk.Label(body, text=one.phase, width=18, anchor="e",
                      font=("Segoe UI", 9, "bold")).grid(
                          row=0, column=column, sticky="e", padx=6)

        rows = [("temperature", "deg C", lambda s: s.T - 273.15),
                ("pressure", "kPa", lambda s: s.p * 1000.0),
                ("specific volume", "m3/kg", lambda s: s.v),
                ("density", "kg/m3", lambda s: s.density),
                ("specific enthalpy", "kJ/kg", lambda s: s.h),
                ("internal energy", "kJ/kg", lambda s: s.u),
                ("entropy", "kJ/(kg K)", lambda s: s.s)]
        for index, (label, unit, get) in enumerate(rows, start=1):
            ttk.Label(body, text=label, width=22, anchor="w").grid(
                row=index, column=0, sticky="w", pady=1)
            for column, one in enumerate(states, start=1):
                ttk.Label(body, text=fmt_number(get(one), 7), width=18,
                          anchor="e", font=MONO).grid(
                              row=index, column=column, sticky="e", padx=6)
            ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                row=index, column=len(states) + 1, sticky="w", padx=(8, 0))

        # The difference between the two is what most questions are after,
        # and it is the one number a table makes you work out yourself.
        if len(states) == 2:
            liquid, vapour = states
            ttk.Label(body, text="").grid(row=len(rows) + 1, column=0)
            for offset, (label, value, unit) in enumerate([
                    ("h_fg  (latent heat)", vapour.h - liquid.h, "kJ/kg"),
                    ("s_fg", vapour.s - liquid.s, "kJ/(kg K)"),
                    ("v_fg", vapour.v - liquid.v, "m3/kg")]):
                line = len(rows) + 2 + offset
                ttk.Label(body, text=label, width=22, anchor="w").grid(
                    row=line, column=0, sticky="w", pady=1)
                ttk.Label(body, text=fmt_number(value, 7), width=18,
                          anchor="e", font=MONO).grid(row=line, column=2,
                                                      sticky="e", padx=6)
                ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                    row=line, column=3, sticky="w", padx=(8, 0))

    # -- getting it out ------------------------------------------------------
    def _rows_out(self) -> list:
        if not self.result:
            return []
        rows = [["", *[one.phase for one in self.result], ""]]
        for label, unit, get in [
                ("temperature", "deg C", lambda s: s.T - 273.15),
                ("pressure", "kPa", lambda s: s.p * 1000.0),
                ("specific volume", "m3/kg", lambda s: s.v),
                ("specific enthalpy", "kJ/kg", lambda s: s.h),
                ("internal energy", "kJ/kg", lambda s: s.u),
                ("entropy", "kJ/(kg K)", lambda s: s.s)]:
            rows.append([label, *[get(one) for one in self.result], unit])
        if len(self.result) == 2:
            liquid, vapour = self.result
            rows.append(["h_fg", "", vapour.h - liquid.h, "kJ/kg"])
        return rows

    def _as_text(self) -> str:
        lines = []
        for one in self.result or []:
            lines.append(one.phase)
            for label, value, unit in one.rows():
                lines.append(f"    {label:20} {fmt_number(value, 7)} {unit}")
        return "\n".join(lines)

    def copy(self) -> None:
        if not self.result:
            messagebox.showinfo("Nothing to copy", "Set a state first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._as_text())
        self.status.configure(text="Copied")

    def save(self, quiet: bool = False) -> None:
        if not self.result:
            if not quiet:
                messagebox.showinfo("Nothing to save", "Set a state first.")
            return
        first = self.result[0]
        result = CalcResult(
            operation="steam",
            input_text=f"water at {first.T - 273.15:.2f} deg C, "
                       f"{first.p * 1000:.4g} kPa",
            variable=", ".join(one.phase for one in self.result))
        result.result_text = self._as_text()
        for one in self.result:
            for label, value, unit in one.rows():
                result.steps.append(
                    Step(f"{one.phase}: {label}",
                         detail=f"{fmt_number(value, 7)} {unit}"))
        self.app.history.add_result(
            result, project=self.app.project.get(),
            source={"mode": self.mode.get(), "by": self.by.get(),
                    "T": self.temperature.get(), "p": self.pressure.get(),
                    "x": self.quality.get()})
        self.app.refresh_history()
        self.status.configure(text="Saved to history")

    def restore(self, source: dict) -> None:
        """Put the state back as it was asked for."""
        self.mode.set(source.get("mode", MODES[0][0]))
        self.by.set(source.get("by", "T"))
        self.temperature.set(source.get("T", ""))
        self.pressure.set(source.get("p", ""))
        self.quality.set(source.get("x", ""))
        self._mode_changed()
        self.status.configure(text="Reopened from history")

    def export(self) -> None:
        from tkinter import filedialog

        rows = self._rows_out()
        if not rows:
            messagebox.showinfo("Nothing to export", "Set a state first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="steam.xlsx")
        if not path:
            return
        try:
            export_table(("Property", *[f"value {i + 1}" for i in
                                        range(len(rows[0]) - 2)], "Unit"),
                         rows, path, title="Water and steam", sheet="Steam")
            self.status.configure(text="Exported")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))
