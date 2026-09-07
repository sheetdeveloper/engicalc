"""A calculation sheet: several steps in order, each able to use the last.

Laid out as a table because that is what a calculation sheet is - a column of
names, a column of what each one is worked out from, and a column of answers.
Change a number near the top and press Calculate; everything below it follows.
"""

from __future__ import annotations

import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sympy as sp

from ..core.display import fmt, pretty_names
from ..core.engine import CalcResult
from ..core.steps import Step
from ..export.excel import export_table
from ..core.parsing import ParseError
from ..core.sheet import SHEET_DIR, Aim, Sheet, blocks_for, seek
from . import mathrender
from .widgets import AsyncRunner, MONO, ScrollFrame

from . import theme

EXAMPLE = [
    ("d", "50 mm", "m", "pipe bore"),
    ("Q", "0.0035", "m^3/s", "volume flow"),
    ("rho", "998", "kg/m^3", "water at 20 C"),
    ("mu", "0.001", "Pa*s", "dynamic viscosity"),
    ("A", "pi*d^2/4", "m^2", "cross-sectional area"),
    ("v", "Q/A", "m/s", "mean velocity"),
    ("Re", "rho*v*d/mu", "-", "turbulent above ~4000"),
]

HEADINGS = ("Name", "Is", "Unit", "Note", "Answer")
WIDTHS = (10, 26, 10, 22)



def _show_greek(var: tk.StringVar) -> None:
    """Rewrite a cell with its Greek names as letters.

    Done when the cell is finished with rather than on every keystroke:
    ``tau`` is the first three characters of ``taper``, and swapping it for a
    letter mid-word would fight whoever is still typing. The substitution is
    reversible - the sheet reads a letter and its name as one quantity - so
    nothing downstream needs to know this happened.
    """
    text = var.get()
    shown = pretty_names(text)
    if shown != text:
        var.set(shown)


class SheetTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.sheet = Sheet()
        self.results: list = []
        self.rows: list = []          # (name, expression, unit, note, answer)
        self.path: str | None = None
        self._build()
        self._load_example()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Work down the page, one step at a time",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="each step can use any name defined above it").pack(
                      side="left", padx=(10, 0))

        title_row = ttk.Frame(self)
        title_row.pack(fill="x", pady=(6, 0))
        ttk.Label(title_row, text="Worksheet").pack(side="left")
        self.title_var = tk.StringVar(value="Calculation sheet")
        ttk.Entry(title_row, textvariable=self.title_var, width=40).pack(
            side="left", padx=(4, 12))
        ttk.Button(title_row, text="New", command=self.new).pack(side="left")
        ttk.Button(title_row, text="Open...", command=self.open).pack(
            side="left", padx=4)
        ttk.Button(title_row, text="Save", command=self.save_file).pack(
            side="left")
        ttk.Button(title_row, text="Save as...", command=self.save_as).pack(
            side="left", padx=4)

        # Packed before the scrolling table, so it keeps its height.
        # See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Copy as picture",
                   command=self.copy_picture).pack(side="right")
        ttk.Button(actions, text="Export...",
                   command=self.export).pack(side="right", padx=6)
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right")
        ttk.Button(actions, text="Add a step",
                   command=self.add_row).pack(side="right", padx=6)
        ttk.Button(actions, text="Calculate", style="Accent.TButton",
                   command=self.calculate).pack(side="right")

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(8, 0))
        for index, text in enumerate(HEADINGS):
            width = WIDTHS[index] if index < len(WIDTHS) else 24
            ttk.Label(header, text=text, width=width,
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=2)

        # Working backwards, which is how every design question is
        # actually stated: not "what is the Reynolds number at 50 mm" but
        # "what bore keeps it under 4000".
        aim = ttk.Frame(self)
        aim.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Label(aim, text="Vary").pack(side="left")
        self.vary = tk.StringVar()
        self.vary_box = ttk.Combobox(aim, textvariable=self.vary, width=10,
                                     state="readonly", values=[])
        self.vary_box.pack(side="left", padx=4)
        ttk.Label(aim, text="until").pack(side="left")
        self.target = tk.StringVar()
        self.target_box = ttk.Combobox(aim, textvariable=self.target,
                                       width=10, state="readonly", values=[])
        self.target_box.pack(side="left", padx=4)
        ttk.Label(aim, text="is").pack(side="left")
        self.wanted = tk.StringVar()
        wanted_box = ttk.Entry(aim, textvariable=self.wanted, width=14,
                               font=MONO)
        wanted_box.pack(side="left", padx=4)
        wanted_box.bind("<Return>", lambda e: self.seek())
        ttk.Label(aim, text="looking between", style="Hint.TLabel").pack(
            side="left", padx=(10, 2))
        self.seek_low = tk.StringVar()
        ttk.Entry(aim, textvariable=self.seek_low, width=7,
                  font=MONO).pack(side="left", padx=2)
        ttk.Label(aim, text="and", style="Hint.TLabel").pack(side="left")
        self.seek_high = tk.StringVar()
        ttk.Entry(aim, textvariable=self.seek_high, width=7,
                  font=MONO).pack(side="left", padx=2)
        ttk.Label(aim, text="- leave blank and it works one out",
                  style="Hint.TLabel").pack(side="left", padx=(4, 0))
        self.seek_button = ttk.Button(aim, text="Work it backwards",
                                      command=self.seek)
        self.seek_button.pack(side="left", padx=(10, 0))
        self.seeker = AsyncRunner(self)

        self.seek_note = ttk.Label(self, text="", style="Hint.TLabel",
                                   wraplength=980, justify="left")
        self.seek_note.pack(side="bottom", fill="x", pady=(2, 0))

        # What the tolerances came to, and which measurement to improve.
        # Under the table rather than in it: it is about the sheet as a
        # whole, and the row it belongs to is whichever one is last.
        self.spread_note = ttk.Label(self, text="", style="Hint.TLabel",
                                     wraplength=980, justify="left")
        self.spread_note.pack(side="bottom", fill="x", pady=(4, 0))

        self.table = ScrollFrame(self, height=360)
        self.table.pack(fill="both", expand=True)

    # -- rows -------------------------------------------------------------
    def _add_widgets(self, name="", expression="", unit="", note="") -> None:
        body = self.table.body
        row = ttk.Frame(body)
        row.pack(fill="x", pady=1)
        variables = []
        # The name and what it equals are the two that hold quantities, so
        # they are the two written in Greek. A unit or a note is prose.
        cells = ((pretty_names(name), WIDTHS[0]),
                 (pretty_names(expression), WIDTHS[1]),
                 (unit, WIDTHS[2]), (note, WIDTHS[3]))
        for index, (value, width) in enumerate(cells):
            var = tk.StringVar(value=value)
            entry = ttk.Entry(row, textvariable=var, width=width, font=MONO)
            entry.pack(side="left", padx=2)
            if index < 2:
                entry.bind("<FocusOut>", lambda e, v=var: _show_greek(v))
                entry.bind("<Return>", lambda e, v=var: (_show_greek(v),
                                                         self.calculate()))
            else:
                entry.bind("<Return>", lambda e: self.calculate())
            variables.append(var)
        answer = ttk.Label(row, text="", width=34, anchor="w", font=MONO)
        answer.pack(side="left", padx=2)
        ttk.Button(row, text="x", width=2,
                   command=lambda r=row: self.remove_row(r)).pack(side="right")
        ttk.Button(row, text="v", width=2,
                   command=lambda r=row: self.move_row(r, 1)).pack(side="right")
        ttk.Button(row, text="^", width=2,
                   command=lambda r=row: self.move_row(r, -1)).pack(side="right")
        self.rows.append((row, variables, answer))

    def add_row(self) -> None:
        self._add_widgets()
        self.status.configure(text="Added a step")

    def remove_row(self, row) -> None:
        for index, (frame, _vars, _answer) in enumerate(self.rows):
            if frame is row:
                frame.destroy()
                del self.rows[index]
                break
        self.calculate()

    def move_row(self, row, delta: int) -> None:
        for index, (frame, _vars, _answer) in enumerate(self.rows):
            if frame is row:
                target = index + delta
                if 0 <= target < len(self.rows):
                    self.rows[index], self.rows[target] = \
                        self.rows[target], self.rows[index]
                    for frame_again, _v, _a in self.rows:
                        frame_again.pack_forget()
                    for frame_again, _v, _a in self.rows:
                        frame_again.pack(fill="x", pady=1)
                break
        self.calculate()

    def _clear_rows(self) -> None:
        for frame, _vars, _answer in self.rows:
            frame.destroy()
        self.rows.clear()

    def _load_example(self) -> None:
        self.title_var.set("Water in a 50 mm pipe")
        for name, expression, unit, note in EXAMPLE:
            self._add_widgets(name, expression, unit, note)
        self.calculate()

    # -- computing --------------------------------------------------------
    def _collect(self) -> Sheet:
        sheet = Sheet(self.title_var.get().strip() or "Calculation sheet")
        for _frame, variables, _answer in self.rows:
            name, expression, unit, note = (v.get() for v in variables)
            if not name.strip() and not expression.strip():
                continue
            sheet.add(name, expression, unit, note)
        return sheet

    def calculate(self) -> None:
        self.sheet = self._collect()
        self.results = self.sheet.evaluate()

        by_name = {id(step): result
                   for step, result in zip(self.sheet.steps, self.results)}
        index = 0
        problems = 0
        for _frame, variables, answer in self.rows:
            if not variables[0].get().strip() and not variables[1].get().strip():
                answer.configure(text="")
                continue
            if index >= len(self.results):
                break
            result = self.results[index]
            index += 1
            if result.ok and result.table is not None:
                answer.configure(text=result.table.describe(),
                                 foreground=theme.colours()["muted"])
            elif result.ok:
                answer.configure(text=result.text().split(" = ", 1)[-1],
                                 foreground=theme.colours()["accent"])
            else:
                answer.configure(text=result.error[:40],
                                 foreground=theme.colours()["bad"])
                problems += 1

        self.status.configure(
            text=f"{len(self.results)} steps, {problems} need attention"
            if problems else f"{len(self.results)} steps, all worked out")
        self.spread_note.configure(text=self._about_the_spread())
        self._offer_rows()

    # -- working it backwards ---------------------------------------------
    def _offer_rows(self) -> None:
        """Fill the two pickers from the rows the sheet actually has.

        Only rows that were typed in can be varied - a row below is not
        free to take a value, it is whatever the rows above make it - so
        only those are offered, and the mistake cannot be made.
        """
        named = [step for step in self.sheet.steps if step.name.strip()]
        can_vary = [step.name for step in named if step.is_input()]
        self.vary_box.configure(values=can_vary)
        self.target_box.configure(values=[step.name for step in named])
        if self.vary.get() not in can_vary:
            self.vary.set(can_vary[0] if can_vary else "")
        if self.target.get() not in [s.name for s in named]:
            self.target.set(named[-1].name if named else "")

    def seek(self) -> None:
        """Find the value of one row that makes another read what is wanted."""
        if not self.wanted.get().strip():
            self.seek_note.configure(
                text="Say what the target row should read.")
            return
        self.sheet = self._collect()
        aim = Aim(vary=self.vary.get(), target=self.target.get(),
                  wanted=self.wanted.get(), low=self.seek_low.get(),
                  high=self.seek_high.get())
        self.seek_note.configure(text="Working backwards...")
        self.seek_button.configure(state="disabled")

        def done(found):
            self.seek_button.configure(state="normal")
            self.seek_note.configure(text=self._about_the_seek(found))
            if len(found.answers) == 1:
                # One answer, so put it on the sheet and work it through -
                # which is what was being asked for. More than one and it
                # is not this tab's business to choose.
                self._put_back(aim.vary, found.answers[0])

        def failed(problem):
            self.seek_button.configure(state="normal")
            self.seek_note.configure(text=str(problem))

        self.seeker.run(lambda: seek(self.sheet, aim), done, failed)

    def _put_back(self, name: str, answer) -> None:
        """Type the answer into the row it belongs to, and recalculate."""
        for _frame, variables, _answer in self.rows:
            if variables[0].get().strip() == name.strip():
                variables[1].set(f"{answer.value:.10g}")
                break
        self.calculate()

    def _about_the_seek(self, found) -> str:
        aim = found.aim
        if not found.answers:
            return _and_note(found.note, f"Nothing found for {aim.target}.")
        if len(found.answers) == 1:
            one = found.answers[0]
            unit = f" {one.unit}" if one.unit else ""
            return _and_note(
                found.note,
                f"{aim.vary} = {one.value:.6g}{unit} makes {aim.target} "
                f"read {aim.wanted}. Put on the sheet.")
        # More than one, which is an answer and not a problem: a Reynolds
        # number of 4000 can happen at two bores.
        said = ", ".join(f"{one.value:.6g}" for one in found.answers)
        unit = f" {found.answers[0].unit}" if found.answers[0].unit else ""
        return _and_note(
            found.note,
            f"{len(found.answers)} values of {aim.vary} make {aim.target} "
            f"read {aim.wanted}: {said}{unit}. Type the one you want in.")

    def _about_the_spread(self) -> str:
        """A sentence about the tolerances, or nothing if there are none.

        About the last row that has one, because that is the answer the
        sheet was written to get - the rows above it are the working.
        """
        worked = [r for r in self.results
                  if r.ok and r.spread is not None and r.spread.known]
        if not worked:
            return ""
        last = worked[-1]
        said = (f"{last.step.name} = {float(last.value):.6g} "
                f"+/- {last.spread.error:.4g}"
                + (f" {last.unit}" if last.unit else "")
                + f", which is {100 * last.spread.relative:.2g}%.")
        worst = last.spread.dominant()
        if worst is not None:
            said += (f"  {worst.name} accounts for "
                     f"{100 * worst.share:.0f}% of that - measuring anything "
                     f"else better would buy almost nothing.")
        elif len(last.spread.contributions) > 1:
            share = ", ".join(f"{c.name} {100 * c.share:.0f}%"
                              for c in last.spread.contributions[:4])
            said += f"  Shared between {share}."
        return said

    # -- files ------------------------------------------------------------
    def new(self) -> None:
        self._clear_rows()
        self.title_var.set("Calculation sheet")
        self.path = None
        for _ in range(3):
            self._add_widgets()
        self.status.configure(text="New sheet")

    def open(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=SHEET_DIR if os.path.isdir(SHEET_DIR) else None,
            filetypes=[("EngiCalc sheet", "*.json"), ("All files", "*")])
        if not path:
            return
        try:
            sheet = Sheet.load(path)
        except Exception as exc:                      # noqa: BLE001
            messagebox.showerror("Could not open that sheet", str(exc))
            return
        self._clear_rows()
        self.title_var.set(sheet.title)
        for step in sheet.steps:
            self._add_widgets(step.name, step.expression, step.unit, step.note)
        self.path = path
        self.calculate()
        self.status.configure(text=f"Opened {os.path.basename(path)}")

    def restore(self, source: dict) -> None:
        """Rebuild this sheet from what was saved with it."""
        sheet = Sheet.from_dict(source["sheet"])
        self._clear_rows()
        self.title_var.set(sheet.title)
        for step in sheet.steps:
            self._add_widgets(step.name, step.expression, step.unit, step.note)
        self.path = None
        self.calculate()
        self.status.configure(text="Reopened from history")

    def save_file(self) -> None:
        """Save the sheet where it came from, or ask where to put it.

        What Ctrl+S means everywhere else. Going straight to Save as would
        put a file dialog in front of somebody who has already told the
        app where the file is.
        """
        if not self.path:
            self.save_as()
            return
        try:
            self._collect().save(self.path)
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        self.status.configure(text=f"Saved to {os.path.basename(self.path)}")

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialdir=SHEET_DIR,
            initialfile=(self.title_var.get().strip() or "sheet") + ".json",
            filetypes=[("EngiCalc sheet", "*.json")])
        if not path:
            return
        try:
            self._collect().save(path)
        except Exception as exc:                      # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        self.path = path
        self.status.configure(text=f"Saved {os.path.basename(path)}")

    # -- output -----------------------------------------------------------
    # -- getting it out ----------------------------------------------------
    @staticmethod
    def _answer(result):
        """A number where there is one, so a spreadsheet can use it.

        `279440.0/pi` is the exact answer and no use at all in Excel, which
        cannot add up a symbol. Anything that evaluates to a real number goes
        out as that number; anything genuinely symbolic goes out as its own
        text, which is the honest thing to send.
        """
        if result.error:
            return result.error
        try:
            value = float(sp.N(result.value))
        except (TypeError, ValueError):
            return fmt(result.value)
        return value if math.isfinite(value) else fmt(result.value)

    def _worked_rows(self) -> list:
        """The rows that produced an answer, in the order they are headed."""
        rows = []
        for step, result in zip(self.sheet.steps, self.results):
            if not step.name.strip():
                continue
            rows.append([step.name, step.expression, step.unit, step.note,
                         self._answer(result)])
        return rows

    def _as_result(self) -> CalcResult:
        """The sheet as one calculation, for the history."""
        worked = self._worked_rows()
        result = CalcResult(
            operation="sheet",
            input_text=self.title_var.get().strip() or "Calculation sheet",
            variable=", ".join(row[0] for row in worked))
        result.result_text = "\n".join(
            f"{name} = {answer}" + (f" {unit}" if unit else "")
            for name, _is, unit, _note, answer in worked)
        for name, expression, unit, note, answer in worked:
            result.steps.append(Step(
                f"{name} = {expression}" + (f"  [{unit}]" if unit else ""),
                detail=(f"{answer}   {note}".strip())))
        return result

    def save(self, quiet: bool = False) -> None:
        self.calculate()
        if not self._worked_rows():
            if not quiet:
                messagebox.showinfo("Nothing to save",
                                    "Add a step or two first.")
            return
        self.app.history.add_result(self._as_result(),
                                    project=self.app.project.get(),
                                    source={"sheet": self.sheet.to_dict()})
        self.app.refresh_history()
        self.status.configure(text="Saved to history")

    def export(self) -> None:
        self.calculate()
        rows = self._worked_rows()
        if not rows:
            messagebox.showinfo("Nothing to export", "Add a step or two first.")
            return
        title = self.title_var.get().strip() or "Calculation sheet"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=f"{title}.xlsx")
        if not path:
            return
        try:
            export_table(HEADINGS, rows, path, title=title, sheet="Sheet")
            self.status.configure(text=f"Exported to {os.path.basename(path)}")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def copy_picture(self) -> None:
        if not self.results:
            self.calculate()
        from . import clipboard
        try:
            image = mathrender.render_calculation(
                blocks_for(self.sheet, self.results))
            clipboard.copy_image(image, None)
        except clipboard.ClipboardError as exc:
            messagebox.showerror("Could not copy", str(exc))
            return
        except Exception as exc:                      # noqa: BLE001
            messagebox.showerror("Could not draw the sheet", str(exc))
            return
        self.status.configure(text="Copied - paste it straight into Word")


def _and_note(note: str, said: str) -> str:
    """Two remarks, or whichever of them there is."""
    return "  ".join(part for part in (said, note) if part)
