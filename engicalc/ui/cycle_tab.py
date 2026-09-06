"""The refrigeration cycle, drawn on the chart it is always drawn on.

Pressure against enthalpy with a logarithmic pressure axis, because on it
three of the four processes are straight lines you can read off: the two heat
exchangers are horizontal, the throttle is vertical, and only the compression
leans. The shape of the cycle is the shape of the drawing.

The numbers underneath are what the four states are for - refrigerating
effect, work, coefficient of performance - and the two that size a machine,
mass flow and compressor power, once a duty is given.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..core import cycle as cycles
from ..core import refrigerants
from ..core.display import fmt_number
from ..core.parsing import ParseError, parse_number
from ..export.excel import export_table
from . import figures
from .r134a_tab import dome
from .widgets import MONO, ScrollFrame

#: The refrigerants this can be run on. The cycle takes the fluid as a
#: parameter, so this is the whole of what makes it work on all of them.
FLUIDS = {name: refrigerants.fluid(name) for name in refrigerants.names()}

#: (symbol, what it is, unit, how to get it) for each of the four states.
STATE_ROWS = [
    ("T", "temperature", "deg C", lambda s: s.T - 273.15),
    ("p", "pressure", "kPa", lambda s: s.p / 1000.0),
    ("h", "enthalpy", "kJ/kg", lambda s: s.h / 1000.0),
    ("s", "entropy", "kJ/(kg K)", lambda s: s.s / 1000.0),
    ("v", "specific volume", "m3/kg", lambda s: s.v),
    ("x", "dryness", "", lambda s: s.quality),
]

#: What each corner of the cycle is.
CORNERS = ["1 into the compressor", "2 into the condenser",
           "3 into the throttle", "4 into the evaporator"]


class CycleTab(ttk.Frame):
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
        ttk.Label(heading, text="Refrigeration cycle",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="the four states, from the two temperatures - and "
                       "what they come to").pack(side="left", padx=(10, 0))

        # Packed before the expanding pane so it keeps its height.
        # See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))

        asked = ttk.Labelframe(self, text="The machine", padding=8)
        asked.pack(fill="x", pady=(6, 0))

        first = ttk.Frame(asked)
        first.pack(fill="x")
        ttk.Label(first, text="Refrigerant").pack(side="left")
        self.fluid = tk.StringVar(value="R134a")
        box = ttk.Combobox(first, state="readonly", width=10,
                           textvariable=self.fluid, values=list(FLUIDS))
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.compute())
        self.evaporating = self._entry(first, "Evaporating at", "-10",
                                       "deg C")
        self.condensing = self._entry(first, "condensing at", "40", "deg C")

        second = ttk.Frame(asked)
        second.pack(fill="x", pady=(6, 0))
        self.superheat = self._entry(second, "Superheat", "5", "K")
        self.subcool = self._entry(second, "Subcooling", "3", "K")
        self.efficiency = self._entry(second, "Compressor", "70",
                                      "% isentropic")

        third = ttk.Frame(asked)
        third.pack(fill="x", pady=(6, 0))
        self.duty = self._entry(third, "Duty", "5", "kW")
        self.wanted = tk.StringVar(value="cooling")
        for label in ("cooling", "heating"):
            ttk.Radiobutton(third, text=label, value=label,
                            variable=self.wanted,
                            command=self.compute).pack(side="left", padx=2)
        ttk.Label(third, text="- leave the duty blank for the answers per "
                             "kilogram", style="Hint.TLabel").pack(
                                 side="left", padx=(14, 0))

        self.note = ttk.Label(asked, text="", style="Hint.TLabel",
                              wraplength=900, justify="left")
        self.note.pack(fill="x", pady=(6, 0))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        answer = ttk.Labelframe(panes, text="The cycle", padding=6)
        self.table = ScrollFrame(answer, height=300)
        self.table.pack(fill="both", expand=True)
        panes.add(answer, weight=4)

        chart = ttk.Labelframe(panes, text="On the chart", padding=6)
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

    def _entry(self, parent, label: str, value: str, unit: str):
        holder = ttk.Frame(parent)
        holder.pack(side="left", padx=(0, 14))
        ttk.Label(holder, text=label).pack(side="left")
        variable = tk.StringVar(value=value)
        entry = ttk.Entry(holder, textvariable=variable, width=7, font=MONO)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: self.compute())
        variable.trace_add("write", lambda *a: self.compute())
        ttk.Label(holder, text=unit, style="Hint.TLabel").pack(side="left")
        return variable

    # -- working it out -----------------------------------------------------
    def _number(self, variable: tk.StringVar, what: str,
                blank: float | None = None) -> float:
        text = variable.get().strip()
        if not text and blank is not None:
            return blank
        value = parse_number(text)
        if value is None:
            raise cycles.CycleError(f"Enter a value for {what}.")
        return float(value)

    def cycle(self) -> cycles.Cycle:
        return cycles.Cycle(
            fluid=FLUIDS[self.fluid.get()],
            evaporating=self._number(self.evaporating,
                                     "the evaporating temperature") + 273.15,
            condensing=self._number(self.condensing,
                                    "the condensing temperature") + 273.15,
            superheat=self._number(self.superheat, "the superheat", 0.0),
            subcool=self._number(self.subcool, "the subcooling", 0.0),
            efficiency=self._number(self.efficiency,
                                    "the compressor efficiency", 100.0)
            / 100.0,
            duty=self._number(self.duty, "the duty", 0.0) * 1000.0,
            heating=self.wanted.get() == "heating")

    def compute(self, *_args) -> None:
        try:
            run = self.cycle()
            states = run.states()
            rows = run.rows()
            notes = run.notes()
        except (cycles.CycleError, ParseError) as exc:
            self.states = []
            self.table.clear()
            self.note.configure(text=str(exc))
            self.status.configure(text="Check the machine")
            return
        except Exception:                             # noqa: BLE001
            return

        self.note.configure(text="  ".join(notes))
        self.states = states
        self._fill(states, rows)
        self._draw(run)
        found = run.performance()
        self.status.configure(
            text=f"COP {found['cooling COP']:.3f} cooling, "
                 f"{found['heating COP']:.3f} heating")

    def _fill(self, states, performance) -> None:
        self.table.clear()
        body = self.table.body
        self.rows = []

        ttk.Label(body, text="", width=20).grid(row=0, column=0)
        for column, corner in enumerate(CORNERS, start=1):
            ttk.Label(body, text=corner.split()[0], width=13, anchor="e",
                      font=("Segoe UI", 9, "bold")).grid(
                          row=0, column=column, sticky="e", padx=4)

        for index, (symbol, name, unit, get) in enumerate(STATE_ROWS,
                                                          start=1):
            ttk.Label(body, text=f"{symbol}  {name}", width=22,
                      anchor="w").grid(row=index, column=0, sticky="w")
            values = []
            for column, state in enumerate(states, start=1):
                value = get(state)
                shown = ("-" if value is None or value != value
                         else fmt_number(value, 6))
                ttk.Label(body, text=shown, width=13, anchor="e",
                          font=MONO).grid(row=index, column=column,
                                          sticky="e", padx=4)
                values.append("" if value is None or value != value
                              else value)
            ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                row=index, column=5, sticky="w", padx=(6, 0))
            self.rows.append([f"{symbol}  {name}"] + values + [unit])

        start = len(STATE_ROWS) + 2
        ttk.Label(body, text="").grid(row=start - 1, column=0)
        for offset, (label, value, unit) in enumerate(performance):
            ttk.Label(body, text=label, width=32, anchor="w").grid(
                row=start + offset, column=0, columnspan=2, sticky="w",
                pady=1)
            ttk.Label(body, text=fmt_number(value, 6), width=13, anchor="e",
                      font=MONO).grid(row=start + offset, column=3,
                                      sticky="e", padx=4)
            ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                row=start + offset, column=4, columnspan=2, sticky="w",
                padx=(6, 0))
            self.rows.append([label, value, "", "", "", unit])

    def _draw(self, run) -> None:
        """The dome, and the cycle drawn round on top of it."""
        try:
            self.axes.clear()
            fluid = FLUIDS[self.fluid.get()]
            liquid_h, vapour_h, pressures = dome(fluid)
            self.axes.plot(liquid_h, pressures, color="#b8bec8",
                           linewidth=1.2)
            self.axes.plot(vapour_h, pressures, color="#b8bec8",
                           linewidth=1.2)

            first, second, third, fourth = self.states
            h = [s.h / 1000.0 for s in self.states]
            p = [s.p / 1000.0 for s in self.states]
            # Round in the order the refrigerant goes, and back to the
            # start. Three of the four legs are exactly straight on these
            # axes - the two heat exchangers are at constant pressure and
            # the throttle at constant enthalpy - which is what makes this
            # the chart the cycle is always drawn on.
            self.axes.plot(h + [h[0]], p + [p[0]], "-o", color="#c0392b",
                           linewidth=1.6, markersize=5, zorder=5)
            for index, (x, y) in enumerate(zip(h, p), start=1):
                self.axes.annotate(str(index), (x, y),
                                   textcoords="offset points",
                                   xytext=(6, 5), fontsize=8,
                                   color="#c0392b")

            # Windowed on the cycle rather than on the whole dome, which
            # runs down to the triple point and would leave the machine in
            # a corner of its own chart.
            span = max(h) - min(h)
            self.axes.set_xlim(min(h) - 0.25 * span, max(h) + 0.20 * span)
            self.axes.set_ylim(min(p) / 3.0, max(p) * 3.0)
            self.axes.set_yscale("log")
            self.axes.set_xlabel("specific enthalpy  kJ/kg", fontsize=8)
            self.axes.set_ylabel("pressure  kPa", fontsize=8)
            self.axes.grid(True, which="both", alpha=0.3, linestyle=":")
            self.axes.tick_params(labelsize=7)
            self.figure.tight_layout()
            self.canvas.draw_idle()
        except Exception:                             # noqa: BLE001
            pass          # a chart that will not draw must not stop the table

    # -- getting it out -----------------------------------------------------
    def _as_text(self) -> str:
        lines = [f"{self.fluid.get()} refrigeration cycle"]
        for row in self.rows:
            values = "  ".join(
                fmt_number(v, 6) if isinstance(v, float) else str(v)
                for v in row[1:-1])
            lines.append(f"    {row[0]:26} {values} {row[-1]}")
        return "\n".join(lines)

    def copy(self) -> None:
        if not self.rows:
            messagebox.showinfo("Nothing to copy", "Describe a cycle first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._as_text())
        self.status.configure(text="Copied")

    def save_chart(self) -> None:
        try:
            path = figures.save_figure(self.figure, "cycle")
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
            messagebox.showinfo("Nothing to export",
                                "Describe a cycle first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="refrigeration-cycle.xlsx")
        if not path:
            return
        try:
            with figures.temporary_png(self.figure) as picture:
                export_table(["Quantity"] + [c.split()[0] for c in CORNERS]
                             + ["Unit"],
                             [list(row) for row in self.rows], path,
                             title=f"{self.fluid.get()} refrigeration cycle",
                             sheet="Cycle", picture=picture)
            self.status.configure(text="Exported, chart and all")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))
