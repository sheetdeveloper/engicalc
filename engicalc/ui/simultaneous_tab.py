"""Equations solved together, in whatever order they are written.

A calculation is rarely a chain that runs one way. Sizing a duct, the
friction factor depends on the Reynolds number, which depends on the
velocity, which depends on the area - and the pressure drop depends on all
three. Written as a chain that has to be untangled by hand first, that is
where the mistakes come from. Written as a set, you state what is true and
the solver finds the values that make all of it true at once.

The count is shown before anything is solved, and updates as you type. That
is the most useful thing this screen does: three equations and four unknowns
has no single answer, and saying so is more help than any number would be.
Everything is an equation here, so fixing an unknown means writing
``d = 0.15`` as a line of its own - which is also how it reads.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sympy as sp

from ..core.display import fmt, fmt_number
from ..core.parsing import ParseError, parse_number
from ..core.system import (fixed_names, free_names, parse_set, solve_set,
                           spread, sweep, sweep_table)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..export.excel import export_table
from . import clipboard, figures, mathfield, mathrender
from .symbol_pad import SymbolPad
from .widgets import AsyncRunner, MONO, ReadOnlyText, ScrollFrame

from . import theme

#: Sets worth starting from. The duct is the case the solver exists for -
#: nothing in it can be worked out without something else in it.
EXAMPLES = [
    ("Two unknowns", "x + y = 10\nx - y = 2"),
    ("Duct pressure drop", "\n".join([
        "# A 150 mm duct carrying 0.5 m3/s over 20 m.",
        "# Nothing here can be worked out first - the friction factor",
        "# needs the Reynolds number, which needs the velocity.",
        "A = pi*0.15^2/4",
        "v = 0.5/A",
        "Re = v*0.15/7.5e-6",
        "f = 0.3164/Re^0.25",
        "dp = f*(20/0.15)*1.2*v^2/2",
    ])),
    ("Two resistors in parallel", "\n".join([
        "1/Rt = 1/R1 + 1/R2",
        "R1 = 220",
        "R2 = 330",
    ])),
    ("Beam reactions", "\n".join([
        "# A 6 m beam, 12 kN at 2 m from the left.",
        "Ra + Rb = 12",
        "Rb*6 = 12*2",
    ])),
]



class _CommentRow(ttk.Frame):
    """A note in the equations, kept and shown but never solved.

    It carries the same `get_text` the equation rows do, so everything that
    walks the rows - reading them out, putting the text box in step - does
    not need to know which kind it is looking at.
    """

    def __init__(self, master, text: str, on_change):
        super().__init__(master)
        self.value = tk.StringVar(value=text.strip())
        entry = ttk.Entry(self, textvariable=self.value, font=MONO,
                          foreground=theme.colours()["muted"])
        entry.pack(fill="x")
        self.value.trace_add("write", lambda *a: on_change())

    def get_text(self) -> str:
        return self.value.get()

    def set_text(self, text: str) -> None:
        self.value.set(text)

    def clear(self) -> None:
        self.value.set("")


class SimultaneousTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.runner = AsyncRunner(self)
        self.result = None
        self._syncing = False
        self._build()
        # Two bars to start with: the smallest set worth calling
        # simultaneous, and the shape the screen is meant to suggest.
        self.set_text(EXAMPLES[0][1])

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Write the equations; order does not matter",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="one per line - a known value is an equation too, "
                       "like d = 0.15").pack(side="left", padx=(10, 0))

        # Packed before the panes so it keeps its height. See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(6, 0))

        left = ttk.Labelframe(panes, text="Equations", padding=6)

        # The same field the calculator uses, one per equation. Pressing the
        # fraction key here puts a fraction here too, rather than the app
        # asking for maths two different ways on two different tabs.
        self.pad = SymbolPad(left, self._insert_item)
        self.pad.pack(fill="x", pady=(0, 6))

        self.fields = []

        # Everything with a height of its own goes in before the rows, which
        # take whatever is left. Packed the other way round, the picker below
        # is last in line for space and its buttons render as slivers - the
        # same rule as the action rows. See TestActionRows.
        picker = ttk.Frame(left)
        picker.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Label(picker, text="Start from").pack(side="left")
        self.example = ttk.Combobox(
            picker, state="readonly", width=22,
            values=[name for name, _text in EXAMPLES])
        self.example.pack(side="left", padx=4)
        self.example.bind("<<ComboboxSelected>>", self._load_example)
        ttk.Button(picker, text="Clear", command=self.clear).pack(side="left")
        ttk.Button(picker, text="Add equation",
                   command=self.add_equation).pack(side="right")

        # The text box stays: pasting five lines at once is still the
        # quickest way to start. The two are kept in step, either can drive.
        text_row = ttk.Frame(left)
        text_row.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Label(text_row, text="as text", style="Hint.TLabel").pack(
            side="left")
        self.text = tk.Text(text_row, height=4, width=34, font=MONO,
                            undo=True, wrap="none")
        self.text.pack(fill="x", expand=True, pady=(2, 0))
        self.text.bind("<KeyRelease>", lambda e: self._text_edited())
        self.text.bind("<Control-Return>", lambda e: (self.solve(), "break"))

        # The count, before anything is solved. This is the diagnostic worth
        # having: it says what to do, which no answer could.
        self.count = ttk.Label(left, text="", style="Hint.TLabel",
                               wraplength=300, justify="left")
        self.count.pack(side="bottom", fill="x", pady=(6, 0))

        self.field_area = ScrollFrame(left, height=150)
        self.field_area.pack(fill="both", expand=True)

        panes.add(left, weight=3)

        right = ttk.Notebook(panes)
        self.right_tabs = right
        answer_page = ttk.Frame(right, padding=6)
        right.add(answer_page, text="  Answer  ")
        self.study_page = ttk.Frame(right, padding=6)
        right.add(self.study_page, text="  Study  ")
        self._build_study()

        split = ttk.PanedWindow(answer_page, orient="vertical")
        split.pack(fill="both", expand=True)

        answer = ttk.Frame(split)
        self.result_math = mathrender.MathList(answer, fontsize=17)
        self.result_math.pack(fill="both", expand=True)
        split.add(answer, weight=3)

        steps = ttk.Frame(split)
        steps_header = ttk.Frame(steps)
        steps_header.pack(fill="x")
        ttk.Label(steps_header, text="Working",
                  style="Hint.TLabel").pack(side="left")
        self.steps_mode = tk.StringVar(value="math")
        ttk.Radiobutton(steps_header, text="typeset", value="math",
                        variable=self.steps_mode,
                        command=self._render_steps).pack(side="right")
        ttk.Radiobutton(steps_header, text="plain text", value="text",
                        variable=self.steps_mode,
                        command=self._render_steps).pack(side="right", padx=6)
        self.steps_holder = ttk.Frame(steps)
        self.steps_holder.pack(fill="both", expand=True, pady=(4, 0))
        self.steps_math = mathrender.MathList(self.steps_holder, fontsize=14)
        self.steps_text = ReadOnlyText(self.steps_holder, height=8)
        self.steps_math.pack(fill="both", expand=True)
        split.add(steps, weight=3)
        panes.add(right, weight=4)

        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Solve", style="Accent.TButton",
                   command=self.solve).pack(side="right")
        ttk.Button(actions, text="Export...",
                   command=self.export).pack(side="right", padx=6)
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right")
        ttk.Button(actions, text="Copy as picture",
                   command=self.copy_picture).pack(side="right", padx=6)

    # -- the study page -----------------------------------------------------
    def _build_study(self) -> None:
        """A column of values for one name, and what the set gives for each."""
        page = self.study_page

        controls = ttk.Frame(page)
        controls.pack(fill="x")
        # Packed first and to the right, so it keeps its place when the row
        # runs out of width - packed last it was pushed off the edge of the
        # pane and only a sliver of it showed.
        ttk.Button(controls, text="Run", style="Accent.TButton",
                   command=self.run_study).pack(side="right")
        ttk.Label(controls, text="Sweep").pack(side="left")
        self.sweep_name = tk.StringVar()
        self.sweep_box = ttk.Combobox(controls, width=8, state="readonly",
                                      textvariable=self.sweep_name)
        self.sweep_box.pack(side="left", padx=4)
        self.sweep_box.bind("<<ComboboxSelected>>",
                            lambda e: self._suggest_range())
        self.sweep_from = tk.StringVar(value="0.1")
        self.sweep_to = tk.StringVar(value="0.3")
        self.sweep_steps = tk.StringVar(value="9")
        for label, variable, width in (("from", self.sweep_from, 8),
                                       ("to", self.sweep_to, 8),
                                       ("in", self.sweep_steps, 4)):
            ttk.Label(controls, text=label).pack(side="left", padx=(8, 2))
            ttk.Entry(controls, textvariable=variable, width=width,
                      font=MONO).pack(side="left")
        ttk.Label(controls, text="steps", style="Hint.TLabel").pack(
            side="left", padx=(2, 8))

        self.study_note = ttk.Label(page, text="", style="Hint.TLabel",
                                    wraplength=520, justify="left")
        self.study_note.pack(fill="x", pady=(6, 0))

        plot_row = ttk.Frame(page)
        plot_row.pack(fill="x", pady=(6, 0))
        ttk.Label(plot_row, text="Plot").pack(side="left")
        self.study_y = tk.StringVar()
        self.study_y_box = ttk.Combobox(plot_row, width=10, state="readonly",
                                        textvariable=self.study_y)
        self.study_y_box.pack(side="left", padx=4)
        self.study_y_box.bind("<<ComboboxSelected>>",
                              lambda e: self._draw_study())
        ttk.Button(plot_row, text="Export...",
                   command=self.export_study).pack(side="right")
        ttk.Button(plot_row, text="Copy chart",
                   command=self.copy_study_chart).pack(side="right", padx=6)
        ttk.Button(plot_row, text="Save chart...",
                   command=self.save_study_chart).pack(side="right")

        self.figure = Figure(figsize=(4.4, 2.6), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=page)
        self.canvas.get_tk_widget().pack(fill="both", expand=True,
                                         pady=(6, 0))

        self.study_table = ScrollFrame(page, height=150)
        self.study_table.pack(fill="both", expand=True, pady=(6, 0))
        self.study_rows = []
        self.study_headings = []

    def _offer_sweep_names(self) -> None:
        """Fill the picker with the names the equations take as input."""
        try:
            names = free_names(self.get_text())
        except Exception:                             # noqa: BLE001
            names = []
        self.sweep_box.configure(values=names)
        if names and self.sweep_name.get() not in names:
            self.sweep_name.set(names[0])
            self._suggest_range()
        if not names:
            self.study_note.configure(
                text="Nothing here can be varied. Every name is worked out "
                     "by the equations rather than given to them, and an "
                     "answer is not an input.")

    def _suggest_range(self) -> None:
        """Put a range around whatever the name is at the moment.

        A sweep from 0.1 to 0.3 is no use for a temperature of 350 K, and
        working out the right range by hand before you can press Run is the
        sort of thing that stops people pressing it. Half the value either
        side is a guess, but it is a guess in the right place, and it can be
        typed over.
        """
        name = self.sweep_name.get().strip()
        if not name:
            return
        try:
            value = fixed_names(self.get_text()).get(name)
        except Exception:                             # noqa: BLE001
            value = None
        if not value:
            # Either nothing fixes it - so there is no current value to
            # centre on - or it is fixed at zero, and half of zero either
            # side is not a range.
            return
        low, high = sorted((value * 0.5, value * 1.5))
        self.sweep_from.set(fmt_number(low, 4))
        self.sweep_to.set(fmt_number(high, 4))
        self.study_note.configure(
            text=f"{name} is {fmt_number(value, 6)} at the moment. Run "
                 f"solves the whole set again at each value in the range, "
                 f"putting each one in place of the line that fixes it.")

    def run_study(self) -> None:
        name = self.sweep_name.get().strip()
        if not name:
            self._offer_sweep_names()
            name = self.sweep_name.get().strip()
        if not name:
            return
        try:
            start = float(parse_number(self.sweep_from.get()))
            stop = float(parse_number(self.sweep_to.get()))
            steps = int(float(parse_number(self.sweep_steps.get())))
        except (TypeError, ValueError):
            self.study_note.configure(text="The range needs three numbers.")
            return
        if steps < 1 or steps > 200:
            self.study_note.configure(
                text="Between 1 and 200 steps - each one is a full solve.")
            return

        # Bring the page forward: a study started from the answer page would
        # otherwise finish somewhere nobody is looking.
        self.right_tabs.select(self.study_page)
        self.study_note.configure(text=f"Solving {steps} times...")
        self.update_idletasks()
        rows = sweep(self.get_text(), name, spread(start, stop, steps))
        outputs = sorted({key for row in rows if row.ok
                          for key in map(str, row.result.results[0])
                          if key != name})
        self.study_headings, self.study_rows = sweep_table(rows, outputs)
        self.study_headings[0] = name

        self.study_y_box.configure(values=outputs)
        if outputs and self.study_y.get() not in outputs:
            self.study_y.set(outputs[-1])
        worked = sum(1 for row in rows if row.ok)
        self.study_note.configure(
            text=f"{worked} of {len(rows)} solved."
                 + ("" if worked == len(rows) else
                    " The rest are in the table with what went wrong."))
        self._fill_study()
        self._draw_study()

    def _fill_study(self) -> None:
        self.study_table.clear()
        body = self.study_table.body
        for column, heading in enumerate(self.study_headings):
            ttk.Label(body, text=heading, width=13, anchor="e",
                      font=("Segoe UI", 9, "bold")).grid(
                          row=0, column=column, sticky="e", padx=4)
        for index, row in enumerate(self.study_rows, start=1):
            for column, value in enumerate(row):
                text = (fmt_number(value, 6)
                        if isinstance(value, (int, float)) else str(value))
                ttk.Label(body, text=text, width=13, anchor="e",
                          font=MONO).grid(row=index, column=column,
                                          sticky="e", padx=4)

    def _draw_study(self) -> None:
        axes = self.axes
        axes.clear()
        wanted = self.study_y.get()
        if wanted and wanted in self.study_headings:
            column = self.study_headings.index(wanted)
            points = [(row[0], row[column]) for row in self.study_rows
                      if isinstance(row[column], (int, float))]
            if points:
                axes.plot([x for x, _y in points], [y for _x, y in points],
                          "o-", color="#1f4e79", markersize=4, linewidth=1.4)
                axes.set_xlabel(self.study_headings[0], fontsize=8)
                axes.set_ylabel(wanted, fontsize=8)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def export_study(self) -> None:
        if not self.study_rows:
            messagebox.showinfo("Nothing to export", "Run a study first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="study.xlsx")
        if not path:
            return
        try:
            with figures.temporary_png(self.figure) as picture:
                export_table(self.study_headings, self.study_rows, path,
                             title="Parametric study", sheet="Study",
                             picture=picture)
            self.status.configure(text="Study exported, chart and all")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def save_study_chart(self) -> None:
        try:
            path = figures.save_figure(self.figure, "study")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        if path:
            self.status.configure(text="Chart saved")

    def copy_study_chart(self) -> None:
        try:
            figures.copy_figure(self.figure)
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not copy", str(exc))
            return
        self.status.configure(text="Chart copied")

    # -- the typeset rows ---------------------------------------------------
    def _add_field(self, text: str = "", after=None):
        """One more row, optionally just below *after*.

        A line starting with `#` is a note rather than an equation, so it
        gets a plain single-line box: three lines of explanation in
        full-height typeset fields pushed the equations they explain off the
        bottom of the pane.
        """
        holder = ttk.Frame(self.field_area.body)
        if text.strip().startswith("#"):
            field = _CommentRow(holder, text, self._fields_edited)
        else:
            # The same size as the calculator's bar: one equation, one bar,
            # whichever screen you are on.
            field = mathfield.MathField(
                holder, fontsize=17, height=56,
                on_change=self._fields_edited,
                on_submit=lambda f=None: self._return_in(field))
        field.pack(side="left", fill="x", expand=True)
        ttk.Button(holder, text="x", width=2,
                   command=lambda: self._remove_field(field)).pack(
                       side="left", padx=(4, 0))
        if text and not isinstance(field, _CommentRow):
            field.set_text(text)

        index = len(self.fields) if after is None else \
            self.fields.index(after) + 1
        self.fields.insert(index, field)
        self._repack_fields()
        return field

    def add_equation(self) -> None:
        """One more equation, at the end, with the caret in it."""
        field = self._add_field()
        field.focus_set()
        self._fields_edited()

    def _repack_fields(self) -> None:
        for field in self.fields:
            field.master.pack_forget()
        for field in self.fields:
            field.master.pack(fill="x", pady=1)

    def _remove_field(self, field) -> None:
        if len(self.fields) <= 1:
            field.clear()
            return
        index = self.fields.index(field)
        self.fields.remove(field)
        field.master.destroy()
        self._fields_edited()
        if self.fields:
            self.fields[max(0, index - 1)].focus_set()

    def _return_in(self, field) -> None:
        """Enter opens the next row rather than solving.

        A set is written a line at a time, so the key that ends a line should
        start the next one. Ctrl+Enter solves, which is what the text box has
        always done.
        """
        new = self._add_field(after=field)
        new.focus_set()

    def _insert_item(self, item) -> None:
        """Send a pad press to whichever row was last being edited."""
        field = self._focused_field()
        if field is None:
            return
        template = getattr(item, "template", "")
        if template:
            field.insert_template(template)
            field.focus_set()
            return
        # A set has no single operation to select, so a pad key that only
        # changes one - the integral sign, say - has nothing to do here.
        text = item.inserted_text() if hasattr(item, "inserted_text") else ""
        if text:
            field.insert_text(text)
        field.focus_set()

    def _focused_field(self):
        """The equation row a pad press should go to, never a note."""
        focused = self.focus_get()
        for field in self.fields:
            if focused is field and not isinstance(field, _CommentRow):
                return field
        equations = [f for f in self.fields
                     if not isinstance(f, _CommentRow)]
        return equations[-1] if equations else None

    def _fields_edited(self) -> None:
        """The rows changed, so put the text box in step and recount."""
        if self._syncing:
            return
        self._syncing = True
        try:
            text = "\n".join(f.get_text() for f in self.fields
                              if f.get_text().strip())
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
        finally:
            self._syncing = False
        self._recount()

    def _text_edited(self) -> None:
        """The text box changed, so rebuild the rows from it."""
        if self._syncing:
            return
        self._syncing = True
        try:
            self._rebuild_fields(self.text.get("1.0", "end"))
        finally:
            self._syncing = False
        self._recount()

    def _rebuild_fields(self, text: str) -> None:
        lines = [line for line in (text or "").splitlines() if line.strip()]
        for field in self.fields:
            field.master.destroy()
        self.fields = []
        # Never fewer than two: this is the simultaneous screen, and one
        # empty bar on it looks like the calculator with something missing.
        for line in lines or ["", ""]:
            self._add_field(line)
        while len(self.fields) < 2:
            self._add_field("")

    # -- the text -----------------------------------------------------------
    def get_text(self) -> str:
        """The equations, as the lines the solver reads."""
        from_fields = "\n".join(f.get_text() for f in self.fields
                                 if f.get_text().strip())
        return from_fields or self.text.get("1.0", "end").strip()

    def set_text(self, text: str) -> None:
        self._syncing = True
        try:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
            self._rebuild_fields(text)
        finally:
            self._syncing = False
        self._recount()

    def clear(self) -> None:
        self.set_text("")
        self.fields[0].focus_set() if self.fields else None
        self.result = None
        self.result_math.clear()
        self.steps_math.clear()
        self.status.configure(text="Ready")

    def _load_example(self, _event=None) -> None:
        name = self.example.get()
        for label, text in EXAMPLES:
            if label == name:
                self.set_text(text)
                self.solve()
                return

    # -- the count, as you type ---------------------------------------------
    def _recount(self) -> None:
        """Say how the equations and unknowns stand, before solving.

        Written to be read while typing, so it says what to do about the
        shortfall rather than only naming it.
        """
        text = self.get_text()
        if not text:
            self.count.configure(text="")
            return
        try:
            parsed = parse_set(text)
        except ParseError as exc:
            self.count.configure(text=str(exc))
            return
        except Exception:                              # noqa: BLE001
            self.count.configure(text="")
            return

        equations = len(parsed.equations)
        unknowns = len(parsed.unknowns)
        summary = (f"{equations} equation{'s' if equations != 1 else ''}, "
                   f"{unknowns} unknown{'s' if unknowns != 1 else ''}: "
                   + ", ".join(s.name for s in parsed.unknowns))
        spare = parsed.freedom
        if spare > 0:
            summary += (f"\nGive {spare} more equation"
                        f"{'s' if spare > 1 else ''}, or fix {spare} of them "
                        "to a value.")
        elif spare < 0:
            summary += (f"\n{-spare} more equation{'s' if spare < -1 else ''} "
                        "than unknowns - they have to agree exactly.")
        else:
            summary += "\nEnough to solve."
        self.count.configure(text=summary)
        self._offer_sweep_names()

    # -- solving ------------------------------------------------------------
    def solve(self) -> None:
        text = self.get_text()
        if not text:
            messagebox.showinfo("Nothing to solve", "Write an equation first.")
            return
        self.status.configure(text="Solving...")
        self.runner.run(lambda: solve_set(text), self._show, self._failed)

    def _show(self, result) -> None:
        self.result = result
        self.result_math.render(self._result_blocks(result))
        self._render_steps()
        self.status.configure(
            text="Solved" if result.results else "No values found")
        if self.app.autosave.get() and result.results:
            self.save(quiet=True)

    #: Significant figures shown. Past anything the inputs to an engineering
    #: calculation carry, and still narrow enough to read at this size.
    FIGURES = 8

    def _result_blocks(self, result) -> list:
        blocks = []
        if result.results:
            for symbol, value in sorted(result.results[0].items(),
                                        key=lambda pair: str(pair[0])):
                drawn, detail = value, ""
                try:
                    number = sp.N(value, self.FIGURES)
                    if number.is_real:
                        drawn = number
                        # Only where the exact form is a different kind of
                        # answer - a fraction, or something still carrying
                        # pi. For a float it is the same number written
                        # longer, which is a row of digits to read past.
                        if not value.is_Float and fmt(value) != fmt(number):
                            detail = f"exactly {fmt(value)}"
                except Exception:                      # noqa: BLE001
                    pass
                blocks.append((None, sp.Eq(symbol, drawn), detail))
        else:
            blocks.append(("No answer", None,
                           result.result_text or "No solution found."))
        for warning in result.warnings:
            blocks.append(("Note", None, warning))
        return blocks

    def _render_steps(self) -> None:
        if self.result is None:
            return
        for widget in (self.steps_math, self.steps_text):
            widget.pack_forget()
        wants_all = self.app.show_working.get()
        steps = [step for step in self.result.steps
                 if wants_all or not step.minor]
        if self.steps_mode.get() == "text":
            self.steps_text.pack(fill="both", expand=True)
            self.steps_text.set("\n\n".join(s.text() for s in steps)
                                or "(no working)")
        else:
            self.steps_math.pack(fill="both", expand=True)
            blocks = [(step.title, step.drawn(), step.detail)
                      for step in steps]
            self.steps_math.render(blocks or [("", None, "(no working)")])

    def _failed(self, exc: Exception) -> None:
        self.result = None
        self.result_math.render([("Could not solve that", None, str(exc))])
        self.steps_math.clear()
        self.status.configure(text="Check the equations")

    # -- getting it out ------------------------------------------------------
    def _answer_rows(self) -> list:
        """Name, exact value and number, for a table."""
        if not self.result or not self.result.results:
            return []
        rows = []
        for symbol, value in sorted(self.result.results[0].items(),
                                    key=lambda pair: str(pair[0])):
            try:
                number = float(sp.N(value))
            except (TypeError, ValueError):
                number = fmt(value)
            rows.append([str(symbol), fmt(value), number])
        return rows

    def save(self, quiet: bool = False) -> None:
        if self.result is None or not self.result.results:
            if not quiet:
                messagebox.showinfo("Nothing to save", "Solve something first.")
            return
        self.app.history.add_result(self.result,
                                    project=self.app.project.get(),
                                    source={"equations": self.get_text()})
        self.app.refresh_history()
        self.status.configure(text="Saved to history")

    def restore(self, source: dict) -> None:
        """Put the equations back and solve them again."""
        self.set_text(source.get("equations", ""))
        self.solve()

    def export(self) -> None:
        rows = self._answer_rows()
        if not rows:
            messagebox.showinfo("Nothing to export", "Solve something first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="equations.xlsx")
        if not path:
            return
        # The equations go out with the answers. A column of values with
        # nothing stating what they satisfy cannot be checked by anyone.
        rows = rows + [["", "", ""], ["Equations", "", ""]]
        rows += [[line, "", ""] for line in self.get_text().splitlines()
                 if line.strip()]
        try:
            export_table(("Unknown", "Exact", "Value"), rows, path,
                         title="Equations solved together", sheet="Equations")
            self.status.configure(text=f"Exported to {os.path.basename(path)}")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def _picture_blocks(self) -> list:
        blocks = [("Equations", None, self.get_text())]
        blocks += self._result_blocks(self.result) if self.result else []
        return blocks

    def copy_picture(self) -> None:
        if self.result is None:
            messagebox.showinfo("Nothing to copy", "Solve something first.")
            return
        try:
            image = mathrender.render_calculation(self._picture_blocks())
            clipboard.copy_image(image)
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not copy", str(exc))
            return
        self.status.configure(text="Copied - paste it straight into Word")
