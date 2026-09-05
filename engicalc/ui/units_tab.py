"""Converting one unit to another, and to every other one at once.

A converter that answers only the question asked is half a tool. Most of the
time the useful thing is the whole column - 2.5 bar is 250 kPa and 36.3 psi
and 0.25 MPa - because the number you need is often not the one you thought
to ask for. So the single conversion is there for when you want it, and the
full set is always shown beside it.

Temperature is the one case that cannot be answered without a question back.
20 °C is 293.15 K as a temperature and 20 K as a difference, and picking the
wrong one is a 273 degree error that looks entirely plausible on the page.
The choice is on screen rather than guessed at.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import sympy as sp

from ..core.display import fmt_number
from ..core.engine import CalcResult
from ..core.steps import Step
from ..core.units import (CATEGORIES, CELSIUS, UnitError, category_of,
                          convert, same_dimension)
from . import clipboard
from .widgets import MONO, ScrollFrame

#: Where the picker starts. A length is the conversion people reach for most.
START_CATEGORY = "Length"
START_FROM = "mm"
START_TO = "in"


class UnitsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.rows = []
        self._build()
        self.convert()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Convert a quantity",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="the same value in every unit that measures the same "
                       "thing").pack(side="left", padx=(10, 0))

        # Packed before the expanding pane so it keeps its height.
        # See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))

        entry = ttk.Labelframe(self, text="Quantity", padding=8)
        entry.pack(fill="x", pady=(6, 0))

        line = ttk.Frame(entry)
        line.pack(fill="x")
        ttk.Label(line, text="Measuring").pack(side="left")
        self.category = tk.StringVar(value=START_CATEGORY)
        self.category_box = ttk.Combobox(
            line, state="readonly", width=13, textvariable=self.category,
            values=list(CATEGORIES))
        self.category_box.pack(side="left", padx=(4, 14))
        self.category_box.bind("<<ComboboxSelected>>",
                               lambda e: self._category_changed())

        self.value = tk.StringVar(value="25")
        value_entry = ttk.Entry(line, textvariable=self.value, width=14,
                                font=MONO)
        value_entry.pack(side="left")
        self.value.trace_add("write", lambda *a: self.convert())

        self.source = tk.StringVar(value=START_FROM)
        self.source_box = ttk.Combobox(line, state="readonly", width=8,
                                       textvariable=self.source)
        self.source_box.pack(side="left", padx=4)
        self.source_box.bind("<<ComboboxSelected>>", lambda e: self.convert())

        ttk.Button(line, text="<->", width=4,
                   command=self.swap).pack(side="left", padx=6)

        self.target = tk.StringVar(value=START_TO)
        self.target_box = ttk.Combobox(line, state="readonly", width=8,
                                       textvariable=self.target)
        self.target_box.pack(side="left", padx=4)
        self.target_box.bind("<<ComboboxSelected>>", lambda e: self.convert())

        # Only shown for temperature, where the answer genuinely depends on
        # it. Everywhere else it would be a question with one answer.
        self.absolute = tk.BooleanVar(value=True)
        self.temperature_row = ttk.Frame(entry)
        ttk.Label(self.temperature_row, style="Hint.TLabel",
                  text="This value is").pack(side="left")
        ttk.Radiobutton(self.temperature_row, text="a temperature",
                        value=True, variable=self.absolute,
                        command=self.convert).pack(side="left", padx=4)
        ttk.Radiobutton(self.temperature_row, text="a difference",
                        value=False, variable=self.absolute,
                        command=self.convert).pack(side="left")
        ttk.Label(self.temperature_row, style="Hint.TLabel",
                  text="- 20 °C is 293.15 K, but a rise of 20 °C is a rise "
                       "of 20 K").pack(side="left", padx=(10, 0))

        self.answer = ttk.Label(entry, text="", font=("Segoe UI", 17))
        self.answer.pack(fill="x", pady=(8, 0))
        self.note = ttk.Label(entry, text="", style="Hint.TLabel")
        self.note.pack(fill="x")

        table = ttk.Labelframe(self, text="In every unit that measures the "
                                          "same thing", padding=6)
        table.pack(fill="both", expand=True, pady=(8, 0))
        self.table = ScrollFrame(table, height=260)
        self.table.pack(fill="both", expand=True)

        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right")
        ttk.Button(actions, text="Copy the table",
                   command=self.copy_table).pack(side="right", padx=6)
        ttk.Button(actions, text="Copy the answer",
                   command=self.copy_answer).pack(side="right")

        self._category_changed(keep=True)

    # -- the pickers --------------------------------------------------------
    def _category_changed(self, keep: bool = False) -> None:
        members = CATEGORIES.get(self.category.get(), [])
        self.source_box.configure(values=members)
        self.target_box.configure(values=members)
        if not keep or self.source.get() not in members:
            self.source.set(members[0] if members else "")
        if not keep or self.target.get() not in members:
            self.target.set(members[1] if len(members) > 1 else
                            (members[0] if members else ""))
        self.convert()

    def swap(self) -> None:
        source, target = self.source.get(), self.target.get()
        self.source.set(target)
        self.target.set(source)
        self.convert()

    # -- converting ---------------------------------------------------------
    def _absolute(self):
        """Whether a temperature is a reading or a difference, when it matters."""
        pair = (self.source.get(), self.target.get())
        if any(unit in CELSIUS for unit in pair):
            return self.absolute.get()
        return None

    def convert(self, *_args) -> None:
        source, target = self.source.get(), self.target.get()
        if any(unit in CELSIUS or unit == "K"
               for unit in (source, target)):
            self.temperature_row.pack(fill="x", pady=(6, 0),
                                      before=self.answer)
        else:
            self.temperature_row.pack_forget()

        try:
            value = sp.sympify(self.value.get() or "0")
            float(value)
        except Exception:                             # noqa: BLE001
            self.answer.configure(text="")
            self.note.configure(text="That is not a number.")
            self._fill_table(None)
            self.status.configure(text="Check the value")
            return

        try:
            converted = convert(value, source, target, self._absolute())
        except UnitError as exc:
            self.answer.configure(text="")
            self.note.configure(text=str(exc))
            self._fill_table(None)
            self.status.configure(text="Cannot convert those")
            return

        self.answer.configure(
            text=f"{fmt_number(value, 8)} {source}   =   "
                 f"{fmt_number(converted, 8)} {target}")
        self.note.configure(text="")
        self._fill_table(value)
        self.status.configure(text="Converted")

    def equivalents(self, value=None) -> list:
        """(unit, number) for every unit measuring the same thing."""
        if value is None:
            try:
                value = sp.sympify(self.value.get() or "0")
            except Exception:                         # noqa: BLE001
                return []
        source = self.source.get()
        out = []
        for unit in same_dimension(source):
            try:
                out.append((unit, convert(value, source, unit,
                                          self._absolute())))
            except UnitError:
                continue
        return out

    def _fill_table(self, value) -> None:
        self.table.clear()
        if value is None:
            return
        for index, (unit, number) in enumerate(self.equivalents(value)):
            here = unit == self.target.get()
            ttk.Label(self.table.body, text=fmt_number(number, 8), width=22,
                      anchor="e", font=MONO).grid(row=index, column=0,
                                                  sticky="e", padx=6, pady=1)
            ttk.Label(self.table.body, text=unit, width=10, anchor="w",
                      style=("" if not here else "Hint.TLabel")).grid(
                          row=index, column=1, sticky="w")
            if here:
                ttk.Label(self.table.body, text="<- asked for",
                          style="Hint.TLabel").grid(row=index, column=2,
                                                    sticky="w")

    # -- getting it out ------------------------------------------------------
    def _as_text(self) -> str:
        lines = [f"{fmt_number(sp.sympify(self.value.get()), 8)} "
                 f"{self.source.get()} is"]
        lines += [f"    {fmt_number(number, 8)} {unit}"
                  for unit, number in self.equivalents()]
        return "\n".join(lines)

    def restore(self, source: dict) -> None:
        """Put the conversion back as it was asked."""
        if source.get("category"):
            self.category.set(source["category"])
            self._category_changed(keep=True)
        self.value.set(source.get("value", ""))
        self.source.set(source.get("from", ""))
        self.target.set(source.get("to", ""))
        self.absolute.set(bool(source.get("absolute", True)))
        self.convert()
        self.status.configure(text="Reopened from history")

    def copy_answer(self) -> None:
        text = self.answer.cget("text")
        if not text:
            messagebox.showinfo("Nothing to copy", "Enter a value first.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.configure(text="Copied")

    def copy_table(self) -> None:
        if not self.equivalents():
            messagebox.showinfo("Nothing to copy", "Enter a value first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._as_text())
        self.status.configure(text="Copied the table")

    def save(self, quiet: bool = False) -> None:
        equivalents = self.equivalents()
        if not equivalents:
            if not quiet:
                messagebox.showinfo("Nothing to save", "Enter a value first.")
            return
        result = CalcResult(
            operation="convert",
            input_text=f"{self.value.get()} {self.source.get()} "
                       f"to {self.target.get()}",
            variable=self.target.get())
        result.result_text = self.answer.cget("text")
        for unit, number in equivalents:
            result.steps.append(Step(f"{fmt_number(number, 8)} {unit}"))
        self.app.history.add_result(
            result, project=self.app.project.get(),
            source={"value": self.value.get(), "from": self.source.get(),
                    "to": self.target.get(), "category": self.category.get(),
                    "absolute": self.absolute.get()})
        self.app.refresh_history()
        self.status.configure(text="Saved to history")
