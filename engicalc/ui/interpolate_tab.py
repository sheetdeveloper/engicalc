"""Reading a value between the rows of a table.

The data goes in as text rather than a grid of cells on purpose: the way this
gets used is to select two columns in Excel, copy, and paste. A grid would
mean retyping numbers that are already on the clipboard.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..core.display import fmt_number
from ..core.interpolate import METHODS, interpolate, parse_table, reverse
from ..core.parsing import ParseError
from . import mathrender
from .widgets import MONO, ReadOnlyText

EXAMPLE = """Temp    Pressure
80      47.39
85      57.87
90      70.14
95      84.55
100     101.42"""


class InterpolateTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.result = None
        self.table = None
        self._build()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Read a value between the rows of a table",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="paste two columns straight from Excel").pack(
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

        # -- the data -----------------------------------------------------
        left = ttk.Labelframe(panes, text="Data  (x in the first column, "
                                          "y in the second)", padding=6)
        self.data_text = tk.Text(left, height=14, width=30, font=MONO,
                                 relief="solid", borderwidth=1)
        self.data_text.pack(fill="both", expand=True)
        self.data_text.insert("1.0", EXAMPLE)

        data_buttons = ttk.Frame(left)
        data_buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(data_buttons, text="Paste",
                   command=self.paste).pack(side="left")
        ttk.Button(data_buttons, text="Load CSV...",
                   command=self.load_csv).pack(side="left", padx=6)
        ttk.Button(data_buttons, text="Clear",
                   command=self.clear).pack(side="left")
        panes.add(left, weight=2)

        # -- what to look up ----------------------------------------------
        right = ttk.Frame(panes)

        controls = ttk.Labelframe(right, text="Look up", padding=6)
        controls.pack(fill="x")

        row = ttk.Frame(controls)
        row.pack(fill="x")
        ttk.Label(row, text="Method").pack(side="left")
        self.method = tk.StringVar(value="linear")
        method_box = ttk.Combobox(row, textvariable=self.method, width=12,
                                  state="readonly", values=METHODS)
        method_box.pack(side="left", padx=(4, 12))
        method_box.bind("<<ComboboxSelected>>", lambda e: self._sync())

        self.degree_frame = ttk.Frame(row)
        ttk.Label(self.degree_frame, text="degree").pack(side="left")
        self.degree = tk.StringVar(value="2")
        ttk.Entry(self.degree_frame, textvariable=self.degree,
                  width=4).pack(side="left", padx=(4, 12))

        direction = ttk.Frame(controls)
        direction.pack(fill="x", pady=(6, 0))
        self.direction = tk.StringVar(value="forward")
        ttk.Radiobutton(direction, text="find y at x =", value="forward",
                        variable=self.direction,
                        command=self._sync).pack(side="left")
        ttk.Radiobutton(direction, text="find x where y =", value="reverse",
                        variable=self.direction,
                        command=self._sync).pack(side="left", padx=(10, 0))
        self.at = tk.StringVar(value="92")
        entry = ttk.Entry(direction, textvariable=self.at, width=12)
        entry.pack(side="left", padx=(8, 0))
        entry.bind("<Return>", lambda e: self.compute())
        ttk.Button(direction, text="Go", style="Accent.TButton",
                   command=self.compute).pack(side="left", padx=(8, 0))

        answer = ttk.Labelframe(right, text="Answer", padding=6)
        answer.pack(fill="both", expand=True, pady=(6, 0))
        self.answer_math = mathrender.MathLabel(answer, fontsize=20, height=54)
        self.answer_math.pack(fill="x")
        self.working = ReadOnlyText(answer, height=9)
        self.working.pack(fill="both", expand=True, pady=(4, 0))

        plot_frame = ttk.Labelframe(right, text="The data", padding=4)
        plot_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.figure = Figure(figsize=(4.6, 2.6), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        panes.add(right, weight=3)

        self._sync()

    def _sync(self) -> None:
        if self.method.get() == "polynomial" and \
                self.direction.get() == "forward":
            self.degree_frame.pack(side="left")
        else:
            self.degree_frame.pack_forget()

    # -- data ---------------------------------------------------------------
    def paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Nothing to paste",
                                "The clipboard has no text in it.")
            return
        self.data_text.delete("1.0", "end")
        self.data_text.insert("1.0", text)
        self.status.configure(text="Pasted")

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
        self.data_text.delete("1.0", "end")
        self.data_text.insert("1.0", text)
        self.status.configure(text=f"Loaded {path}")

    def clear(self) -> None:
        self.data_text.delete("1.0", "end")
        self.answer_math.clear()
        self.working.set("")
        self.axes.clear()
        self.canvas.draw_idle()
        self.result = None

    # -- computing -----------------------------------------------------------
    def compute(self) -> None:
        try:
            self.table = parse_table(self.data_text.get("1.0", "end"))
        except ParseError as exc:
            messagebox.showerror("Could not read the data", str(exc))
            self.status.configure(text="Check the data")
            return

        try:
            if self.direction.get() == "reverse":
                result = reverse(self.table, self.at.get())
            else:
                degree = int(self.degree.get() or 2)
                result = interpolate(self.table, self.at.get(),
                                     self.method.get(), degree)
        except (ParseError, ValueError) as exc:
            messagebox.showerror("Could not interpolate", str(exc))
            self.status.configure(text="Check the value to look up")
            return

        self.result = result
        self._show(result)

    def _show(self, result) -> None:
        try:
            self.answer_math.show(result.latex or result.result_text,
                                  result.result_text)
        except Exception:                             # noqa: BLE001
            self.answer_math.show(None, result.result_text)

        lines = [result.result_text, ""]
        if result.warnings:
            lines += ["! " + w for w in result.warnings] + [""]
        lines.append(result.steps_text())
        self.working.set("\n".join(lines))
        self._draw(result)
        self.status.configure(
            text="Extrapolated - see the warning" if result.warnings
            else "Done")
        if self.app.autosave.get():
            self.save(quiet=True)

    def _draw(self, result) -> None:
        """The data, the fitted curve if there is one, and the answer on it."""
        axes = self.axes
        axes.clear()
        if self.table is None:
            return
        axes.plot(self.table.xs, self.table.ys, "o-", color="#1f77b4",
                  markersize=4, linewidth=1.2, label="data")

        if result.expression is not None:
            import numpy as np
            import sympy as sp
            try:
                span = np.linspace(min(self.table.xs), max(self.table.xs), 200)
                func = sp.lambdify(sp.Symbol("x"), result.expression, "numpy")
                axes.plot(span, func(span), "--", color="#d62728",
                          linewidth=1.4, label="fit")
            except Exception:                         # noqa: BLE001
                pass

        for index, value in enumerate(result.numeric or []):
            if value is None:
                continue
            if result.variable == "y":
                x, y = value, float(self.at.get() or 0)
            else:
                x, y = float(self.at.get() or 0), value
            axes.plot([x], [y], "o", color="#2ca02c", markersize=9,
                      markerfacecolor="white", markeredgewidth=2, zorder=5,
                      label="answer" if index == 0 else None)
            axes.annotate(f"({fmt_number(x)}, {fmt_number(y)})", (x, y),
                          textcoords="offset points", xytext=(8, 8),
                          fontsize=8, color="#2ca02c")

        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.legend(loc="best", fontsize=7, framealpha=0.85)
        self.figure.subplots_adjust(left=0.12, right=0.98, top=0.95,
                                    bottom=0.15)
        self.canvas.draw_idle()

    # -- output --------------------------------------------------------------
    def _blocks(self) -> list:
        blocks = [("Interpolation", None, self.result.input_text),
                  ("Answer", None, self.result.result_text)]
        blocks += [("Note", None, w) for w in self.result.warnings]
        blocks += [(s.title, s.drawn(), s.detail) for s in self.result.steps]
        return blocks

    def copy_picture(self) -> None:
        if self.result is None:
            messagebox.showinfo("Nothing to copy", "Look something up first.")
            return
        from . import clipboard
        try:
            image = mathrender.render_calculation(self._blocks())
            clipboard.copy_image(image, self.result.result_text)
        except clipboard.ClipboardError as exc:
            messagebox.showerror("Could not copy", str(exc))
            return
        except Exception as exc:                      # noqa: BLE001
            messagebox.showerror("Could not draw the calculation", str(exc))
            return
        self.status.configure(text="Copied - paste it straight into Word")

    def save(self, quiet: bool = False) -> None:
        if self.result is None:
            if not quiet:
                messagebox.showinfo("Nothing to save",
                                    "Look something up first.")
            return
        self.app.history.add_result(self.result,
                                    project=self.app.project.get())
        self.app.refresh_history()
        self.status.configure(text="Saved to history")
