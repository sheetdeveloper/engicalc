"""Matrices: solving several equations at once, and the operations around it.

Laid out around ``A x = b``, because that is what matrices are for in
engineering - a frame with a dozen joints gives a dozen equations that all
have to hold, and solving them in one step is the point.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..core.matrices import (
    OPERATIONS,
    matrix_text,
    operate,
    parse_matrix,
    solve_system,
)
from ..core.parsing import ParseError
from . import mathrender
from .matrixview import MatrixView
from .widgets import MONO, ReadOnlyText

EXAMPLE_A = """2   1  -1
-3  -1   2
-2   1   2"""
EXAMPLE_B = """8
-11
-3"""

NEEDS_B = {"solve", "multiply"}

EXPLAIN = {
    "solve": "Finds the values that satisfy every equation at once. This is "
             "what matrices are for.",
    "determinant": "Zero means the rows are not independent - no inverse, and "
                   "no unique solution.",
    "inverse": "The matrix that undoes this one. Solving is usually better "
               "conditioned than inverting.",
    "transpose": "Rows become columns.",
    "eigenvalues": "Natural frequencies, buckling loads and principal "
                   "stresses are all eigenvalue problems.",
    "rank": "How many of the rows say something the others do not.",
    "multiply": "A times B, in that order - matrix multiplication is not "
                "commutative.",
}


class MatrixTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.result = None
        self._build()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Solve several equations at once",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="one row per line; paste straight from Excel").pack(
                      side="left", padx=(10, 0))

        # Packed before the expanding pane and anchored to the bottom.
        # Pack allocates in packing order, so a row packed after an
        # expanding widget is last in line for space and gets sliced
        # to a few pixels - the buttons are there but show as blank
        # slivers. side="bottom" alone is not enough. See
        # TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right")
        ttk.Button(actions, text="Copy as picture",
                   command=self.copy_picture).pack(side="right", padx=6)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        left = ttk.Frame(panes)

        a_frame = ttk.Labelframe(left, text="A  - the coefficients", padding=6)
        a_frame.pack(fill="both", expand=True)
        self.a_text = tk.Text(a_frame, height=8, width=26, font=MONO,
                              relief="solid", borderwidth=1)
        self.a_text.pack(fill="both", expand=True)
        self.a_text.insert("1.0", EXAMPLE_A)

        self.b_frame = ttk.Labelframe(left, text="b  - the right-hand side",
                                      padding=6)
        self.b_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.b_text = tk.Text(self.b_frame, height=5, width=26, font=MONO,
                              relief="solid", borderwidth=1)
        self.b_text.pack(fill="both", expand=True)
        self.b_text.insert("1.0", EXAMPLE_B)

        self._buttons = buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="Load CSV...",
                   command=self.load_csv).pack(side="left")
        ttk.Button(buttons, text="Clear",
                   command=self.clear).pack(side="left", padx=6)
        panes.add(left, weight=2)

        right = ttk.Frame(panes)

        controls = ttk.Labelframe(right, text="Do what", padding=6)
        controls.pack(fill="x")
        row = ttk.Frame(controls)
        row.pack(fill="x")
        self.operation = tk.StringVar(value="solve")
        box = ttk.Combobox(row, textvariable=self.operation, width=14,
                           state="readonly", values=OPERATIONS)
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda e: self._sync())
        ttk.Button(row, text="Go", style="Accent.TButton",
                   command=self.compute).pack(side="left", padx=(8, 0))
        self.explain = ttk.Label(controls, style="Hint.TLabel",
                                 wraplength=430, justify="left")
        self.explain.pack(fill="x", pady=(4, 0))

        answer = ttk.Labelframe(right, text="Answer", padding=6)
        answer.pack(fill="both", expand=True, pady=(6, 0))
        self.view = MatrixView(answer, fontsize=15)
        self.view.pack(fill="x")
        self.working = ReadOnlyText(answer, height=10)
        self.working.pack(fill="both", expand=True, pady=(4, 0))
        panes.add(right, weight=3)

        self._sync()

    def _sync(self) -> None:
        operation = self.operation.get()
        self.explain.configure(text=EXPLAIN.get(operation, ""))
        label = "B  - the second matrix" if operation == "multiply" \
            else "b  - the right-hand side"
        self.b_frame.configure(text=label)
        if operation in NEEDS_B:
            self.b_frame.pack(fill="both", expand=True, pady=(6, 0),
                              before=self._buttons)
        else:
            self.b_frame.pack_forget()

    # -- data -------------------------------------------------------------
    def load_csv(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Data files", "*.csv *.txt *.tsv"), ("All files", "*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                text = handle.read()
        except OSError as exc:
            messagebox.showerror("Could not open the file", str(exc))
            return
        self.a_text.delete("1.0", "end")
        self.a_text.insert("1.0", text)
        self.status.configure(text=f"Loaded {path}")

    def clear(self) -> None:
        self.a_text.delete("1.0", "end")
        self.b_text.delete("1.0", "end")
        self.view.clear()
        self.working.set("")
        self.result = None

    # -- computing --------------------------------------------------------
    def compute(self) -> None:
        operation = self.operation.get()
        try:
            a = parse_matrix(self.a_text.get("1.0", "end"))
        except ParseError as exc:
            messagebox.showerror("Could not read A", str(exc))
            return

        b = None
        if operation in NEEDS_B:
            try:
                b = parse_matrix(self.b_text.get("1.0", "end"))
            except ParseError as exc:
                messagebox.showerror("Could not read the second matrix",
                                     str(exc))
                return

        try:
            if operation == "solve":
                result = solve_system(a, b)
            else:
                result = operate(a, operation, b)
        except (ParseError, ValueError) as exc:
            messagebox.showerror("Could not do that", str(exc))
            self.status.configure(text="See the message")
            return

        self.result = result
        self._show(result, a)

    def _show(self, result, a) -> None:
        import sympy as sp

        parts = []
        if result.results and isinstance(result.results[0], sp.MatrixBase):
            label = {"solve": "x =", "inverse": "A" + "⁻" + "¹ = ",
                     "transpose": "A" + "ᵀ" + " =",
                     "multiply": "A B ="}.get(self.operation.get(), "=")
            parts = [label, result.results[0]]
        if parts:
            self.view.show(*parts)
        else:
            self.view.clear()

        lines = [result.result_text, ""]
        if result.warnings:
            lines += ["! " + w for w in result.warnings] + [""]
        lines.append(result.steps_text())
        self.working.set("\n".join(lines))
        self.status.configure(
            text="Check the warning" if result.warnings else "Done")
        if self.app.autosave.get():
            self.save(quiet=True)

    # -- output -----------------------------------------------------------
    def _blocks(self) -> list:
        blocks = [("Matrix", None, self.result.input_text),
                  ("Answer", None, self.result.result_text)]
        blocks += [("Note", None, w) for w in self.result.warnings]
        blocks += [(s.title, s.expr, s.detail) for s in self.result.steps]
        return blocks

    def copy_picture(self) -> None:
        if self.result is None:
            messagebox.showinfo("Nothing to copy", "Work something out first.")
            return
        from . import clipboard
        try:
            image = mathrender.render_calculation(self._blocks())
            clipboard.copy_image(image, self.result.latex or None)
        except clipboard.ClipboardError as exc:
            messagebox.showerror("Could not copy", str(exc))
            return
        except Exception as exc:                      # noqa: BLE001
            messagebox.showerror("Could not draw it", str(exc))
            return
        self.status.configure(text="Copied - paste it straight into Word")

    def save(self, quiet: bool = False) -> None:
        if self.result is None:
            if not quiet:
                messagebox.showinfo("Nothing to save",
                                    "Work something out first.")
            return
        self.app.history.add_result(self.result,
                                    project=self.app.project.get())
        self.app.refresh_history()
        self.status.configure(text="Saved to history")
