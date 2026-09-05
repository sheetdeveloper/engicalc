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

from ..core.display import fmt
from ..core.parsing import ParseError
from ..core.system import parse_set, solve_set
from ..export.excel import export_table
from . import clipboard, mathrender
from .widgets import AsyncRunner, MONO, ReadOnlyText

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


class SimultaneousTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.runner = AsyncRunner(self)
        self.result = None
        self._build()
        self.set_text(EXAMPLES[1][1])

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
        self.text = tk.Text(left, height=12, width=38, font=MONO, undo=True,
                            wrap="none")
        self.text.pack(fill="both", expand=True)
        self.text.bind("<KeyRelease>", lambda e: self._recount())
        self.text.bind("<Control-Return>", lambda e: (self.solve(), "break"))

        # The count, before anything is solved. This is the diagnostic worth
        # having: it says what to do, which no answer could.
        self.count = ttk.Label(left, text="", style="Hint.TLabel",
                               wraplength=300, justify="left")
        self.count.pack(fill="x", pady=(6, 0))

        picker = ttk.Frame(left)
        picker.pack(fill="x", pady=(6, 0))
        ttk.Label(picker, text="Start from").pack(side="left")
        self.example = ttk.Combobox(
            picker, state="readonly", width=22,
            values=[name for name, _text in EXAMPLES])
        self.example.pack(side="left", padx=4)
        self.example.bind("<<ComboboxSelected>>", self._load_example)
        ttk.Button(picker, text="Clear", command=self.clear).pack(side="left")
        panes.add(left, weight=3)

        right = ttk.Labelframe(panes, text="Answer", padding=6)
        split = ttk.PanedWindow(right, orient="vertical")
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

    # -- the text -----------------------------------------------------------
    def get_text(self) -> str:
        return self.text.get("1.0", "end").strip()

    def set_text(self, text: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self._recount()

    def clear(self) -> None:
        self.set_text("")
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
