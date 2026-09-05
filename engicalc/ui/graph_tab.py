"""Graphing tab: several curves, four plot types, matplotlib toolbar."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)
from matplotlib.figure import Figure

from ..plotting.plot import Curve, PlotSpec, draw
from .widgets import MONO

KINDS = ["explicit", "implicit", "parametric", "polar"]
MAX_CURVES = 6


class CurveRow:
    def __init__(self, master, row: int, on_change, expression: str = ""):
        self.visible = tk.BooleanVar(value=True)
        self.kind = tk.StringVar(value="explicit")
        self.expression = tk.StringVar(value=expression)
        self.second = tk.StringVar()

        ttk.Checkbutton(master, variable=self.visible,
                        command=on_change).grid(row=row, column=0)
        box = ttk.Combobox(master, textvariable=self.kind, width=10,
                           state="readonly", values=KINDS)
        box.grid(row=row, column=1, padx=2)
        box.bind("<<ComboboxSelected>>", lambda e: on_change())
        entry = ttk.Entry(master, textvariable=self.expression, font=MONO, width=30)
        entry.grid(row=row, column=2, sticky="ew", padx=2)
        entry.bind("<Return>", lambda e: on_change())
        self.second_entry = ttk.Entry(master, textvariable=self.second, font=MONO,
                                      width=16)
        self.second_entry.grid(row=row, column=3, padx=2)
        self.second_entry.bind("<Return>", lambda e: on_change())
        master.columnconfigure(2, weight=1)

    def to_curve(self) -> Curve:
        return Curve(expression=self.expression.get(), kind=self.kind.get(),
                     second=self.second.get(), visible=self.visible.get())


class GraphTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.rows: list[CurveRow] = []
        self._build()
        self.replot()

    def _build(self) -> None:
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left, text="Curves", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="y(x) for explicit, F(x,y)=0 for implicit, "
                             "x(t) and y(t) for parametric, r(theta) for polar.",
                  style="Hint.TLabel", wraplength=380).pack(anchor="w",
                                                            pady=(0, 6))

        grid = ttk.Frame(left)
        grid.pack(fill="x")
        ttk.Label(grid, text="on").grid(row=0, column=0)
        ttk.Label(grid, text="type").grid(row=0, column=1)
        ttk.Label(grid, text="expression / x(t)").grid(row=0, column=2)
        ttk.Label(grid, text="y(t)").grid(row=0, column=3)
        defaults = ["x^2 - 4", "sin(x)", "", "", "", ""]
        for index in range(MAX_CURVES):
            self.rows.append(CurveRow(grid, index + 1, self.replot,
                                      defaults[index]))

        ranges = ttk.Labelframe(left, text="Window", padding=6)
        ranges.pack(fill="x", pady=10)
        self.xmin = tk.StringVar(value="-10")
        self.xmax = tk.StringVar(value="10")
        self.ymin = tk.StringVar()
        self.ymax = tk.StringVar()
        self.samples = tk.StringVar(value="800")
        for column, (label, var) in enumerate((
                ("x min", self.xmin), ("x max", self.xmax),
                ("y min", self.ymin), ("y max", self.ymax))):
            ttk.Label(ranges, text=label).grid(row=0, column=column * 2, padx=(0, 2))
            ttk.Entry(ranges, textvariable=var, width=7).grid(row=0,
                                                              column=column * 2 + 1,
                                                              padx=(0, 8))
        ttk.Label(ranges, text="samples").grid(row=1, column=0, pady=(6, 0))
        ttk.Entry(ranges, textvariable=self.samples, width=7).grid(row=1, column=1,
                                                                   pady=(6, 0))
        self.mark_roots = tk.BooleanVar(value=True)
        ttk.Checkbutton(ranges, text="mark roots", variable=self.mark_roots,
                        command=self.replot).grid(row=1, column=2, columnspan=2,
                                                  pady=(6, 0), sticky="w")
        self.equal_aspect = tk.BooleanVar(value=False)
        ttk.Checkbutton(ranges, text="equal aspect", variable=self.equal_aspect,
                        command=self.replot).grid(row=1, column=4, columnspan=2,
                                                  pady=(6, 0), sticky="w")

        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Plot", style="Accent.TButton",
                   command=self.replot).pack(side="left")
        ttk.Button(buttons, text="Reset window",
                   command=self.reset_window).pack(side="left", padx=6)
        ttk.Button(buttons, text="Save PNG", command=self.save_png).pack(side="left")

        self.messages = tk.Label(left, text="", justify="left", anchor="w",
                                 fg="#a33", wraplength=380, background="#f7f7f9")
        self.messages.pack(fill="x", pady=(8, 0))

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        self.figure = Figure(figsize=(6.5, 5.2), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(fill="x")

    # -- actions ----------------------------------------------------------
    def _float(self, var, default=None):
        text = var.get().strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default

    def spec(self) -> PlotSpec:
        return PlotSpec(
            curves=[row.to_curve() for row in self.rows],
            xmin=self._float(self.xmin, -10.0), xmax=self._float(self.xmax, 10.0),
            ymin=self._float(self.ymin), ymax=self._float(self.ymax),
            samples=int(self._float(self.samples, 800) or 800),
            mark_roots=self.mark_roots.get(),
            equal_aspect=self.equal_aspect.get())

    def replot(self) -> None:
        spec = self.spec()
        if spec.xmax <= spec.xmin:
            self.messages.configure(text="x max must be greater than x min.")
            return
        warnings = draw(spec, self.ax)
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.messages.configure(text="\n".join(warnings))

    def reset_window(self) -> None:
        self.xmin.set("-10")
        self.xmax.set("10")
        self.ymin.set("")
        self.ymax.set("")
        self.replot()

    def save_png(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("PDF", "*.pdf"),
                       ("SVG", "*.svg")], initialfile="graph.png")
        if not path:
            return
        try:
            self.figure.savefig(path, dpi=200, bbox_inches="tight")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))

    # -- called from other tabs ------------------------------------------
    def show_spec(self, spec: PlotSpec) -> None:
        for row in self.rows:
            row.expression.set("")
            row.second.set("")
        for row, curve in zip(self.rows, spec.curves):
            row.expression.set(curve.expression)
            row.kind.set(curve.kind)
            row.second.set(curve.second)
            row.visible.set(True)
        self.xmin.set(str(spec.xmin))
        self.xmax.set(str(spec.xmax))
        self.mark_roots.set(spec.mark_roots)
        self.replot()

    def show_series(self, xs, ys, xlabel: str, ylabel: str, title: str) -> None:
        """Plot a numeric sweep computed elsewhere (formula sensitivity)."""
        self.ax.clear()
        self.ax.plot(xs, ys, color="#1f77b4", linewidth=2)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self.ax.grid(True, alpha=0.3, linestyle=":")
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.messages.configure(
            text="Showing a numeric sweep. Press Plot to return to the curves above.")
