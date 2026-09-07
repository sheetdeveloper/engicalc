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
from ..plotting.readoff import read_off
from .widgets import AsyncRunner, MONO, ReadOnlyText

from . import theme

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
                                 fg=theme.colours()["bad"], wraplength=380,
                                 background=theme.colours()["bg"])
        self.messages.pack(fill="x", pady=(8, 0))

        # The three questions anybody asks a graph after looking at it.
        # They used to be answered by squinting at the picture, and the
        # room they take up was empty.
        found = ttk.Labelframe(left, text="What it does", padding=6)
        found.pack(fill="both", expand=True, pady=(10, 0))
        bar = ttk.Scrollbar(found, orient="vertical")
        bar.pack(side="right", fill="y")
        self.features = ReadOnlyText(found, height=8, width=42,
                                     font=("Consolas", 9),
                                     yscrollcommand=bar.set)
        self.features.pack(side="left", fill="both", expand=True)
        bar.configure(command=self.features.yview)
        self.features.set("Plot something and the roots, turning points\n"
                          "and crossings will be listed here.")
        self.reader = AsyncRunner(self)
        #: Which plot the numbers on screen belong to. A slow read-off
        #: that lands after the user has changed the window would
        #: otherwise label the new picture with the old numbers.
        self._reading = 0

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
        self._read_off(spec)

    # -- what the graph says ----------------------------------------------
    def _read_off(self, spec: PlotSpec) -> None:
        """Work out the roots, turns and crossings, off the Tk thread.

        A second of SymPy is a second of a frozen window if it is done
        here, and the picture is already right - so the plot goes up
        first and the numbers arrive under it.
        """
        self._reading += 1
        mine = self._reading
        self.features.set("working it out...")

        def landed(found):
            if mine == self._reading:      # still the plot on screen
                self.features.set(self._as_text(found))

        def failed(_problem):
            if mine == self._reading:
                self.features.set("Could not work these out for this plot.")

        self.reader.run(lambda: read_off(spec), landed, failed)

    @staticmethod
    def _as_text(found) -> str:
        """Grouped by curve, in x order within each.

        Grouped rather than interleaved, because the curve a feature
        belongs to is the first thing you need to know about it, and
        repeating the name against every line spends half the column
        saying it again.

        A root's y is nought by definition, so it is not said. A turning
        point's y is the whole point of the turning point.
        """
        if not found:
            return ("Nothing to report in this window.\n\n"
                    "Roots, turning points and crossings are found for "
                    "y(x) curves. Implicit, parametric and polar ones "
                    "cross zero somewhere that is not an x.")
        order, grouped = [], {}
        for one in found:
            if one.where not in grouped:
                order.append(one.where)
                grouped[one.where] = []
            grouped[one.where].append(one)

        lines = []
        for where in order:
            if lines:
                lines.append("")
            lines.append(where)
            for one in sorted(grouped[where], key=lambda f: f.x):
                said = f"{one.x:>11.6g}   {one.kind}"
                if one.detail:
                    said += f", {one.detail}"
                if one.kind != "root":
                    said += f",  y = {one.y:.6g}"
                lines.append(said)
        return "\n".join(lines)

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
