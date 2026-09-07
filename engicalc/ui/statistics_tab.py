"""Describing lab data, and fitting a line through it.

One column of numbers is a set of readings and gets the usual summary. Two
columns are a relationship and get a line through them, with R squared and
the residuals - because R squared alone says how much of the variation the
line accounts for, not whether a line was the right thing to fit.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import sympy as sp
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..core.display import fmt_number
from ..core.engine import CalcResult
from ..core.fitting import best as best_curve
from ..core.fitting import comparison_rows, fit_all, fit_curve
from ..core.parsing import ParseError
from ..core.statistics import describe, fit_line, parse_columns
from ..core.steps import Step
from ..export.excel import export_table
from . import mathrender
from .widgets import MONO, ScrollFrame

EXAMPLE = """Load   Extension
0      0.00
10     0.21
20     0.39
30     0.62
40     0.78
50     1.01
60     1.18"""


#: What the trendline selector offers. "Best fit" is first because the point
#: of fitting six shapes is to be told which one describes the readings, not
#: to have to try them one at a time.
TREND_CHOICES = [
    ("Best fit - compares all six", "best"),
    ("Linear", "linear"),
    ("Quadratic", "quadratic"),
    ("Cubic", "cubic"),
    ("Exponential", "exponential"),
    ("Logarithmic", "logarithmic"),
    ("Power", "power"),
]

#: The polynomials are fitted by order, so they answer to a different name
#: than the one on the menu.
CURVE_KEYS = {"linear": "poly1", "quadratic": "poly2", "cubic": "poly3"}


class StatisticsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.columns = None
        self.description = None
        self.fit = None
        self.curves = []
        self.curve = None
        self._build()
        self.compute()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text="Describe measured data",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, style="Hint.TLabel",
                  text="one column of readings, or two for a line through "
                       "them").pack(side="left", padx=(10, 0))

        # Packed before the expanding pane so it keeps its height.
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
        ttk.Button(actions, text="Calculate", style="Accent.TButton",
                   command=self.compute).pack(side="right", padx=6)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(8, 0))

        left = ttk.Labelframe(panes, text="Readings", padding=6)
        self.data_text = tk.Text(left, height=16, width=26, font=MONO,
                                 relief="flat", borderwidth=0,
                                 highlightthickness=1)
        self.data_text.pack(fill="both", expand=True)
        self.data_text.insert("1.0", EXAMPLE)
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="Paste", command=self.paste).pack(side="left")
        ttk.Button(buttons, text="Load CSV...",
                   command=self.load_csv).pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left")
        panes.add(left, weight=2)

        # A split the reader can drag rather than three blocks stacked with
        # the chart getting the crumbs. Stacked, the summary and the
        # trendline took their asked-for heights and the chart was left
        # with ninety pixels and its axis labels cut off.
        right = ttk.PanedWindow(panes, orient="vertical")

        self.summary = ttk.Labelframe(right, text="Summary", padding=6)
        self.summary_body = ScrollFrame(self.summary, height=120)
        self.summary_body.pack(fill="both", expand=True)
        right.add(self.summary, weight=3)

        self.fit_frame = ttk.Labelframe(right, text="Trendline", padding=6)
        picker = ttk.Frame(self.fit_frame)
        picker.pack(fill="x")
        ttk.Label(picker, text="Shape").pack(side="left")
        self.trend = tk.StringVar(value=TREND_CHOICES[0][0])
        self.trend_box = ttk.Combobox(
            picker, state="readonly", width=26, textvariable=self.trend,
            values=[label for label, _key in TREND_CHOICES])
        self.trend_box.pack(side="left", padx=4)
        self.trend_box.bind("<<ComboboxSelected>>", lambda e: self._show())
        self.fit_math = mathrender.MathLabel(self.fit_frame, fontsize=18,
                                             height=48)
        self.fit_math.pack(fill="x", pady=(4, 0))
        self.fit_body = ScrollFrame(self.fit_frame, height=90)
        self.fit_body.pack(fill="both", expand=True)

        plot_frame = ttk.Labelframe(right, text="The data", padding=4)
        self.figure = Figure(figsize=(4.8, 2.8), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.plot_frame = plot_frame
        right.add(plot_frame, weight=4)
        panes.add(right, weight=4)

    # -- data -------------------------------------------------------------
    def paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Nothing to paste",
                                "The clipboard has no text in it.")
            return
        self.data_text.delete("1.0", "end")
        self.data_text.insert("1.0", text)
        self.compute()

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
        self.compute()

    def clear(self) -> None:
        self.data_text.delete("1.0", "end")
        self.summary_body.clear()
        self.fit_body.clear()
        self.fit_math.clear()
        self.fit_frame.pack_forget()
        self.axes.clear()
        self.canvas.draw_idle()
        self.columns = self.description = self.fit = None

    # -- computing --------------------------------------------------------
    def compute(self) -> None:
        try:
            self.columns = parse_columns(self.data_text.get("1.0", "end"))
        except ParseError as exc:
            messagebox.showerror("Could not read the data", str(exc))
            self.status.configure(text="Check the data")
            return

        self.description = describe(self.columns.x)
        self.fit = None
        self.curves = []
        if self.columns.paired:
            try:
                self.fit = fit_line(self.columns.x, self.columns.y)
            except ParseError as exc:
                self.status.configure(text=str(exc))
            try:
                # All six, every time. Fitting is cheap and the comparison is
                # the thing worth having.
                self.curves = fit_all(self.columns.x, self.columns.y)
            except ParseError:
                self.curves = []

        self._show()

    def _rows_into(self, holder, rows) -> None:
        holder.clear()
        for index, (label, value, note) in enumerate(rows):
            ttk.Label(holder.body, text=label, width=20, anchor="w").grid(
                row=index, column=0, sticky="w", padx=4, pady=1)
            if value == "":
                shown = ""                    # a heading between the tables
            elif isinstance(value, int):
                shown = str(value)
            else:
                shown = fmt_number(value, 6)
            ttk.Label(holder.body, text=shown, width=14, anchor="e",
                      font=MONO).grid(row=index, column=1, sticky="w", padx=4)
            if note:
                ttk.Label(holder.body, text=note, style="Hint.TLabel").grid(
                    row=index, column=2, sticky="w", padx=4)

    def _show(self) -> None:
        if self.columns.paired:
            self.summary.configure(text="Summary of both columns")
            rows = [("--- first column (x) ---", "", "")]
            rows += self.description.rows()
            rows += [("--- second column (y) ---", "", "")]
            rows += describe(self.columns.y).rows()
        else:
            self.summary.configure(text="Summary of the readings")
            rows = self.description.rows()
        self._rows_into(self.summary_body, rows)

        self.curve = self._chosen_curve()
        if self.curves:
            if str(self.fit_frame) not in self.fit_frame.master.panes():
                self.fit_frame.master.insert(self.plot_frame, self.fit_frame,
                                             weight=3)
            self._rows_into(self.fit_body, self._trend_rows())
            self._show_equation()
        else:
            self.fit_frame.pack_forget()

        self._draw()
        count = self.description.count
        note = ""
        if self.curve is not None and self.curve.ok:
            note = (f", {self.curve.name.lower()}, "
                    f"R squared {fmt_number(self.curve.r_squared, 5)}")
        self.status.configure(text=f"{count} readings{note}")

    def _chosen_curve(self):
        """The shape the selector asks for, or the best-scoring one."""
        if not self.curves:
            return None
        wanted = dict(TREND_CHOICES).get(self.trend.get(), "best")
        if wanted == "best":
            return best_curve(self.curves)
        key = CURVE_KEYS.get(wanted, wanted)
        for curve in self.curves:
            if curve.key == key:
                return curve
        return None

    def _trend_rows(self) -> list:
        """Every shape with its score, the chosen one marked."""
        rows = []
        for curve, (name, score, note) in zip(self.curves,
                                              comparison_rows(self.curves)):
            mark = "   <- shown" if curve is self.curve else ""
            rows.append((name, score, note + mark))
        return rows

    def _show_equation(self) -> None:
        curve = self.curve
        if curve is None or not curve.ok:
            self.fit_math.show(None, curve.refused if curve else "")
            return
        try:
            self.fit_math.show(
                sp.latex(sp.Eq(sp.Symbol("y"), curve.shown())),
                curve.as_text())
        except Exception:                             # noqa: BLE001
            self.fit_math.show(None, curve.as_text())

    def _draw(self) -> None:
        axes = self.axes
        axes.clear()
        if self.columns is None:
            return

        if self.columns.paired:
            axes.plot(self.columns.x, self.columns.y, "o", color="#1f77b4",
                      markersize=5, label="readings")
            curve = self.curve
            if curve is not None and curve.ok:
                span = np.linspace(min(self.columns.x), max(self.columns.x),
                                   200)
                axes.plot(span, curve.predict(span), "-", color="#d62728",
                          linewidth=1.5,
                          label=f"{curve.name}, "
                                f"R²={fmt_number(curve.r_squared, 4)}")
                # The residuals, drawn where they happen. A high R squared
                # with a pattern in these means the shape is wrong.
                for x, y, residual in zip(self.columns.x, self.columns.y,
                                          curve.residuals):
                    axes.plot([x, x], [y - residual, y], color="#999999",
                              linewidth=0.8, zorder=1)
        else:
            axes.plot(range(1, self.description.count + 1), self.columns.x,
                      "o-", color="#1f77b4", markersize=4, label="readings")
            axes.axhline(self.description.mean, color="#d62728",
                         linestyle="--", linewidth=1.2, label="mean")
            for sign in (1, -1):
                axes.axhline(
                    self.description.mean
                    + sign * self.description.sample_sd,
                    color="#d62728", linestyle=":", linewidth=0.9,
                    label="+/- 1 sd" if sign == 1 else None)

        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.legend(loc="best", fontsize=7, framealpha=0.85)
        self.figure.subplots_adjust(left=0.13, right=0.98, top=0.95,
                                    bottom=0.16)
        self.canvas.draw_idle()

    # -- output -----------------------------------------------------------
    def _blocks(self) -> list:
        blocks = [("Readings", None,
                   f"{self.description.count} values")]
        blocks += [(label, None, f"{fmt_number(value, 6)}   {note}".strip())
                   for label, value, note in self.description.rows()]
        if self.columns.paired:
            blocks.append(("Second column", None, ""))
            blocks += [(label, None,
                        f"{fmt_number(value, 6)}   {note}".strip())
                       for label, value, note
                       in describe(self.columns.y).rows()]
        if self.curve is not None and self.curve.ok:
            blocks.append(("Trendline", None,
                           f"{self.curve.name}: {self.curve.as_text()}"))
            blocks.append((None, None,
                           f"R squared {fmt_number(self.curve.r_squared, 6)}"))
        if self.fit is not None and self.curve is not None \
                and self.curve.key == "poly1":
            # The uncertainties only mean anything for the straight line,
            # which is the only shape they were worked out for.
            blocks += [(label, None,
                        f"{fmt_number(value, 6)}   {note}".strip())
                       for label, value, note in self.fit.rows()]
        if len(self.curves) > 1:
            blocks.append(("Shapes compared", None, ""))
            blocks += [(None, None,
                        f"{name}   {fmt_number(score, 6) if score != '' else ''}"
                        f"   {note}".strip())
                       for name, score, note in comparison_rows(self.curves)]
        return blocks

    # -- getting it out ----------------------------------------------------
    def _summary_rows(self) -> list:
        """Every figure on the page, flattened for a table."""
        # describe() already reports the count, so it is not added again.
        rows = [[label, value, note]
                for label, value, note in self.description.rows()]
        if self.columns.paired:
            rows.append(["Second column", "", ""])
            rows += [[label, value, note]
                     for label, value, note in describe(self.columns.y).rows()]
        if self.curve is not None and self.curve.ok:
            rows.append(["Trendline", "",
                         f"{self.curve.name}: {self.curve.as_text()}"])
            rows.append(["R squared", self.curve.r_squared,
                         "measured on the readings, not their logs"])
        if self.fit is not None and self.curve is not None \
                and self.curve.key == "poly1":
            rows += [[label, value, note] for label, value, note
                     in self.fit.rows()]
        if len(self.curves) > 1:
            rows.append(["Shapes compared", "", "by R squared, best first"])
            rows += [[name, score, note]
                     for name, score, note in comparison_rows(self.curves)]
        return rows

    def _as_result(self) -> CalcResult:
        result = CalcResult(operation="statistics",
                            input_text=f"{self.description.count} readings")
        lines = [f"{label} = {fmt_number(value, 6)}" if value != "" else label
                 for label, value, _note in self._summary_rows()]
        result.variable = ", ".join(
            label for label, value, _note in self._summary_rows()
            if value != "")
        result.result_text = "\n".join(lines)
        for label, value, note in self._summary_rows():
            result.steps.append(Step(
                label, detail=f"{value}   {note}".strip()))
        return result

    def save(self, quiet: bool = False) -> None:
        if self.description is None:
            self.compute()
        if self.description is None:
            if not quiet:
                messagebox.showinfo("Nothing to save", "Paste some data first.")
            return
        self.app.history.add_result(
            self._as_result(), project=self.app.project.get(),
            source={"readings": self.data_text.get("1.0", "end").strip(),
                    "shape": self.trend.get()})
        self.app.refresh_history()
        self.status.configure(text="Saved to history")

    def export(self) -> None:
        if self.description is None:
            self.compute()
        if self.description is None:
            messagebox.showinfo("Nothing to export", "Paste some data first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="data.xlsx")
        if not path:
            return
        # The readings go out with the summary. A mean and a standard
        # deviation with no data under them cannot be checked by anyone.
        rows = self._summary_rows() + [["", "", ""], ["The data itself", "", ""]]
        if self.columns.paired:
            rows.append(["x", "y", ""])
            rows += [[x, y, ""] for x, y in zip(self.columns.x,
                                                self.columns.y)]
        else:
            rows += [[x, "", ""] for x in self.columns.x]
        try:
            export_table(("", "Value", "Note"), rows, path,
                         title="Data and statistics", sheet="Data")
            self.status.configure(text="Exported")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def restore(self, source: dict) -> None:
        """Put the readings back and work them out again."""
        self.data_text.delete("1.0", "end")
        self.data_text.insert("1.0", source.get("readings", ""))
        if source.get("shape"):
            self.trend.set(source["shape"])
        self.compute()
        self.status.configure(text="Reopened from history")

    def copy_picture(self) -> None:
        if self.description is None:
            self.compute()
        from . import clipboard
        try:
            image = mathrender.render_calculation(self._blocks())
            clipboard.copy_image(image, None)
        except clipboard.ClipboardError as exc:
            messagebox.showerror("Could not copy", str(exc))
            return
        except Exception as exc:                      # noqa: BLE001
            messagebox.showerror("Could not draw it", str(exc))
            return
        self.status.configure(text="Copied - paste it straight into Word")
