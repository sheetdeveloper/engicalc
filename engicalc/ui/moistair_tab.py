"""Moist air: a psychrometric chart you can read off exactly.

The dry bulb never fixes the state on its own - it takes one measure of how
much water the air is carrying as well - and any two of those measures would
have to agree with each other. So the form asks for the dry bulb and exactly
one other, and says which ones it will take.

Whatever you give it, the rest follow, and they are the same quantities a
chart carries: humidity ratio, enthalpy, specific volume, dew point, wet
bulb. Below freezing the vapour deposits as frost rather than condensing,
which is a different curve and not one this has; where that happens the
number is left out and the reason is on screen, rather than a plausible
answer from the wrong equation.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..core.display import fmt_number
from ..core.engine import CalcResult
from ..core.parsing import ParseError, parse_number
from ..core.psychrometrics import (STANDARD_PRESSURE, PsychrometricError,
                                   state)
from ..core.steps import Step
from ..export.excel import export_table
from .widgets import MONO, ScrollFrame

#: What the moisture can be given as. The dry bulb is always needed; exactly
#: one of these goes with it.
GIVEN = [
    ("Relative humidity", "rh", "%"),
    ("Humidity ratio", "ratio", "kg/kg dry air"),
    ("Wet bulb", "wet", "deg C"),
    ("Dew point", "dew", "deg C"),
]


class MoistAirTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.air = None
        self._build()
        self.compute()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Moist air",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="the dry bulb and one measure of the moisture fix "
                       "everything else").pack(side="left", padx=(10, 0))

        # Packed before the expanding pane so it keeps its height.
        # See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))

        asked = ttk.Labelframe(self, text="The air", padding=8)
        asked.pack(fill="x", pady=(6, 0))

        first = ttk.Frame(asked)
        first.pack(fill="x")
        ttk.Label(first, text="Dry bulb", width=13).pack(side="left")
        self.dry = tk.StringVar(value="20")
        self._entry(first, self.dry, "deg C")
        ttk.Label(first, text="Pressure", width=10).pack(side="left",
                                                         padx=(18, 0))
        self.pressure = tk.StringVar(value=f"{STANDARD_PRESSURE:g}")
        self._entry(first, self.pressure, "kPa - lower up a mountain")

        second = ttk.Frame(asked)
        second.pack(fill="x", pady=(6, 0))
        ttk.Label(second, text="and", width=13).pack(side="left")
        self.given = tk.StringVar(value=GIVEN[0][0])
        box = ttk.Combobox(second, state="readonly", width=18,
                           textvariable=self.given,
                           values=[label for label, _key, _unit in GIVEN])
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda e: self._given_changed())
        self.moisture = tk.StringVar(value="50")
        self.moisture_entry = ttk.Entry(second, textvariable=self.moisture,
                                        width=14, font=MONO)
        self.moisture_entry.pack(side="left", padx=4)
        self.moisture.trace_add("write", lambda *a: self.compute())
        self.moisture_unit = ttk.Label(second, text="%", style="Hint.TLabel")
        self.moisture_unit.pack(side="left")

        self.note = ttk.Label(asked, text="", style="Hint.TLabel",
                              wraplength=900, justify="left")
        self.note.pack(fill="x", pady=(6, 0))

        answer = ttk.Labelframe(self, text="The state", padding=6)
        answer.pack(fill="both", expand=True, pady=(8, 0))
        self.table = ScrollFrame(answer, height=280)
        self.table.pack(fill="both", expand=True)

        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right")
        ttk.Button(actions, text="Export...",
                   command=self.export).pack(side="right", padx=6)
        ttk.Button(actions, text="Copy",
                   command=self.copy).pack(side="right")

    def _entry(self, parent, variable, unit):
        entry = ttk.Entry(parent, textvariable=variable, width=12, font=MONO)
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self.compute())
        variable.trace_add("write", lambda *a: self.compute())
        ttk.Label(parent, text=unit, style="Hint.TLabel").pack(side="left",
                                                               padx=(6, 0))
        return entry

    def _key(self) -> str:
        for label, key, _unit in GIVEN:
            if label == self.given.get():
                return key
        return "rh"

    def _given_changed(self) -> None:
        key = self._key()
        for label, other, unit in GIVEN:
            if other == key:
                self.moisture_unit.configure(text=unit)
        # A sensible starting value for the one just chosen, so the field is
        # never briefly nonsense in the units it has just been given.
        defaults = {"rh": "50", "ratio": "0.0073", "wet": "14", "dew": "9"}
        self.moisture.set(defaults.get(key, ""))
        self.compute()

    # -- working it out -----------------------------------------------------
    def compute(self, *_args) -> None:
        try:
            self.air = self._state()
        except (PsychrometricError, ParseError) as exc:
            self.air = None
            self.table.clear()
            self.note.configure(text=str(exc))
            self.status.configure(text="Check the air")
            return
        except Exception:                             # noqa: BLE001
            return

        self.note.configure(text=self.air.note)
        self._fill()
        self.status.configure(
            text=f"{self.air.temperature:g} deg C, "
                 f"{self.air.relative_humidity * 100:.1f}% saturated")

    def _number(self, variable: tk.StringVar, what: str) -> float:
        value = parse_number(variable.get())
        if value is None:
            raise PsychrometricError(f"Enter a {what}.")
        return float(value)

    def _state(self):
        dry = self._number(self.dry, "dry bulb temperature")
        pressure = self._number(self.pressure, "pressure")
        amount = self._number(self.moisture, "value for the moisture")
        key = self._key()
        if key == "rh":
            return state(dry, pressure, relative_humidity=amount / 100.0)
        if key == "ratio":
            return state(dry, pressure, ratio=amount)
        if key == "wet":
            return state(dry, pressure, wet_bulb=amount)
        return state(dry, pressure, dew_point_at=amount)

    def _fill(self) -> None:
        self.table.clear()
        body = self.table.body
        for index, (symbol, label, value, unit) in enumerate(
                self.air.rows()):
            ttk.Label(body, text=symbol, width=5, anchor="w",
                      font=("Cambria", 11, "italic")).grid(
                          row=index, column=0, sticky="w", padx=(2, 0))
            ttk.Label(body, text=label, width=20, anchor="w").grid(
                row=index, column=0, sticky="w", pady=1, padx=(40, 0))
            shown = "-" if value != value else fmt_number(value, 7)
            ttk.Label(body, text=shown, width=16, anchor="e",
                      font=MONO).grid(row=index, column=1, sticky="e", padx=6)
            ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                row=index, column=2, sticky="w", padx=(8, 0))

    # -- getting it out ------------------------------------------------------
    def _as_text(self) -> str:
        if self.air is None:
            return ""
        lines = [f"Moist air at {self.air.pressure:g} kPa"]
        for symbol, label, value, unit in self.air.rows():
            shown = "-" if value != value else fmt_number(value, 7)
            lines.append(f"    {symbol:5} {label:20} {shown} {unit}")
        if self.air.note:
            lines.append(f"    ({self.air.note})")
        return "\n".join(lines)

    def copy(self) -> None:
        if self.air is None:
            messagebox.showinfo("Nothing to copy", "Describe the air first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._as_text())
        self.status.configure(text="Copied")

    def save(self, quiet: bool = False) -> None:
        if self.air is None:
            if not quiet:
                messagebox.showinfo("Nothing to save",
                                    "Describe the air first.")
            return
        result = CalcResult(
            operation="moistair",
            input_text=f"moist air at {self.air.temperature:g} deg C, "
                       f"{self.air.relative_humidity * 100:.1f}% RH",
            variable="humidity ratio, enthalpy")
        result.result_text = self._as_text()
        for symbol, label, value, unit in self.air.rows():
            shown = "-" if value != value else fmt_number(value, 7)
            result.steps.append(Step(f"{symbol}, {label}",
                                     detail=f"{shown} {unit}"))
        self.app.history.add_result(
            result, project=self.app.project.get(),
            source={"dry": self.dry.get(), "pressure": self.pressure.get(),
                    "given": self.given.get(),
                    "moisture": self.moisture.get()})
        self.app.refresh_history()
        self.status.configure(text="Saved to history")

    def restore(self, source: dict) -> None:
        """Put the air back as it was described."""
        self.given.set(source.get("given", GIVEN[0][0]))
        for label, key, unit in GIVEN:
            if label == self.given.get():
                self.moisture_unit.configure(text=unit)
        self.dry.set(source.get("dry", ""))
        self.pressure.set(source.get("pressure", ""))
        self.moisture.set(source.get("moisture", ""))
        self.compute()
        self.status.configure(text="Reopened from history")

    def export(self) -> None:
        if self.air is None:
            messagebox.showinfo("Nothing to export", "Describe the air first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="moist-air.xlsx")
        if not path:
            return
        rows = [[symbol, label, value, unit]
                for symbol, label, value, unit in self.air.rows()]
        try:
            export_table(("Symbol", "Property", "Value", "Unit"), rows, path,
                         title="Moist air", sheet="Moist air")
            self.status.configure(text="Exported")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))
