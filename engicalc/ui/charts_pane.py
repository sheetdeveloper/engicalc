"""The standard engineering charts, grouped under Graph.

These are the diagrams a course is taught on rather than curves of an
expression, so they sit beside the general plotter rather than in it: each
one takes the handful of numbers that define it, works the whole thing out
and draws it, and puts the figures worth quoting in a table underneath.

They share a shape - a form, a chart, a table of results - so they share a
base class. What differs is the form and the drawing, which is the part
worth reading in each of them.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..core import beams, moody, tensile
from ..core.display import fmt_number
from ..core.mohr import Mohr
from ..core.parsing import ParseError, parse_number
from ..export.excel import export_table
from .widgets import MONO, ScrollFrame


class ChartTab(ttk.Frame):
    """A form, a chart drawn from it, and the numbers worth quoting.

    Subclasses fill in the form and the drawing; everything else - when to
    redraw, how to report a bad number, getting the results out - is the
    same for all of them and lives here.
    """

    title = ""
    hint = ""

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.rows = []
        self.notes = []
        self._build()
        self.refresh()

    # -- the frame every chart sits in -------------------------------------
    def _build(self) -> None:
        heading = ttk.Frame(self)
        heading.pack(fill="x")
        ttk.Label(heading, text=self.title,
                  style="Title.TLabel").pack(side="left")
        ttk.Label(heading, text=self.hint, style="Hint.TLabel").pack(
            side="left", padx=(10, 0))

        # Packed before the expanding pane so it keeps its height.
        # See TestActionRows.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Export...",
                   command=self.export).pack(side="right")
        ttk.Button(actions, text="Copy",
                   command=self.copy).pack(side="right", padx=6)

        form = ttk.Labelframe(self, text="Given", padding=8)
        form.pack(fill="x", pady=(6, 0))
        self.build_form(form)

        self.note = ttk.Label(self, text="", style="Hint.TLabel",
                              wraplength=1000, justify="left")
        self.note.pack(fill="x", pady=(4, 0))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(6, 0))

        chart = ttk.Labelframe(panes, text="Chart", padding=4)
        self.figure = Figure(figsize=(5.4, 3.6), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        panes.add(chart, weight=5)

        results = ttk.Labelframe(panes, text="Results", padding=6)
        self.table = ScrollFrame(results, height=260)
        self.table.pack(fill="both", expand=True)
        panes.add(results, weight=3)

    def field(self, parent, label: str, value: str, unit: str = "",
              width: int = 10) -> tk.StringVar:
        """One labelled entry that redraws the chart as it is edited."""
        holder = ttk.Frame(parent)
        holder.pack(side="left", padx=(0, 14))
        ttk.Label(holder, text=label).pack(side="left")
        variable = tk.StringVar(value=value)
        entry = ttk.Entry(holder, textvariable=variable, width=width,
                          font=MONO)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: self.refresh())
        variable.trace_add("write", lambda *a: self.refresh())
        if unit:
            ttk.Label(holder, text=unit, style="Hint.TLabel").pack(side="left")
        return variable

    def number(self, variable: tk.StringVar, what: str) -> float:
        value = parse_number(variable.get())
        if value is None:
            raise ParseError(f"Enter a value for {what}.")
        return float(value)

    # -- what every chart does the same way --------------------------------
    def refresh(self, *_args) -> None:
        try:
            self.rows, self.notes = self.draw()
        except (ParseError, ValueError) as exc:
            self.note.configure(text=str(exc))
            self.status.configure(text="Check the numbers")
            return
        except Exception:                             # noqa: BLE001
            return          # a half-built form is not worth complaining about

        self.note.configure(text="  ".join(self.notes))
        self._fill()
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.status.configure(text="Drawn")

    def _fill(self) -> None:
        self.table.clear()
        body = self.table.body
        for index, (label, value, unit) in enumerate(self.rows):
            ttk.Label(body, text=label, width=24, anchor="w").grid(
                row=index, column=0, sticky="w", pady=1)
            shown = (fmt_number(value, 6)
                     if isinstance(value, (int, float)) else str(value))
            ttk.Label(body, text=shown, width=14, anchor="e",
                      font=MONO).grid(row=index, column=1, sticky="e", padx=6)
            ttk.Label(body, text=unit, style="Hint.TLabel").grid(
                row=index, column=2, sticky="w", padx=(6, 0))

    def _as_text(self) -> str:
        lines = [self.title]
        for label, value, unit in self.rows:
            shown = (fmt_number(value, 6)
                     if isinstance(value, (int, float)) else str(value))
            lines.append(f"    {label:26} {shown} {unit}")
        return "\n".join(lines + list(self.notes))

    def copy(self) -> None:
        if not self.rows:
            messagebox.showinfo("Nothing to copy", "Fill the form in first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._as_text())
        self.status.configure(text="Copied")

    def export(self) -> None:
        if not self.rows:
            messagebox.showinfo("Nothing to export", "Fill the form in first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=f"{self.title.lower().replace(' ', '-')}.xlsx")
        if not path:
            return
        try:
            export_table(("Quantity", "Value", "Unit"),
                         [list(row) for row in self.rows], path,
                         title=self.title, sheet="Chart")
            self.status.configure(text="Exported")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    # -- for subclasses -----------------------------------------------------
    def build_form(self, parent) -> None:
        raise NotImplementedError

    def draw(self) -> tuple:
        """Draw the chart. Returns (rows, notes)."""
        raise NotImplementedError


# --------------------------------------------------------------------------
class BeamTab(ChartTab):
    """Shear force and bending moment, worked from the loads."""

    title = "Beam diagrams"
    hint = "shear and moment along the span, from the loads on it"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        self.kind = tk.StringVar(value="simply supported")
        ttk.Label(first, text="Beam").pack(side="left")
        box = ttk.Combobox(first, state="readonly", width=17,
                           textvariable=self.kind,
                           values=["simply supported", "cantilever"])
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.length = self.field(first, "Length", "6", "m")
        self.point_at = self.field(first, "Point load at", "2", "m")
        self.point_size = self.field(first, "of", "12", "kN down")

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        self.udl = self.field(second, "Spread load", "0", "kN/m down")
        self.udl_from = self.field(second, "from", "0", "m")
        self.udl_to = self.field(second, "to", "6", "m")

    def draw(self) -> tuple:
        length = self.number(self.length, "the length")
        loads = []
        size = self.number(self.point_size, "the point load")
        if size:
            loads.append(beams.PointLoad(
                self.number(self.point_at, "where the point load is"),
                -size * 1000.0))
        spread = self.number(self.udl, "the spread load")
        if spread:
            loads.append(beams.Distributed(
                self.number(self.udl_from, "where the spread load starts"),
                min(self.number(self.udl_to, "where it ends"), length),
                -spread * 1000.0))

        cantilever = self.kind.get() == "cantilever"
        beam = beams.Beam(length=length,
                          supports=[0.0] if cantilever else [0.0, length],
                          loads=loads,
                          kind="cantilever" if cantilever else
                               "simply supported")
        result = beams.analyse(beam)

        self.figure.clear()
        shear_axes = self.figure.add_subplot(211)
        moment_axes = self.figure.add_subplot(212, sharex=shear_axes)
        shear_axes.plot(result.x, result.shear / 1000.0, color="#1f4e79",
                        linewidth=1.5)
        shear_axes.axhline(0, color="#888888", linewidth=0.8)
        shear_axes.fill_between(result.x, result.shear / 1000.0, 0,
                                color="#1f4e79", alpha=0.12)
        shear_axes.set_ylabel("shear  kN", fontsize=8)
        moment_axes.plot(result.x, result.moment / 1000.0, color="#c0392b",
                         linewidth=1.5)
        moment_axes.axhline(0, color="#888888", linewidth=0.8)
        moment_axes.fill_between(result.x, result.moment / 1000.0, 0,
                                 color="#c0392b", alpha=0.12)
        moment_axes.set_ylabel("moment  kN m", fontsize=8)
        moment_axes.set_xlabel("distance along the beam  m", fontsize=8)
        for axes in (shear_axes, moment_axes):
            axes.grid(True, alpha=0.3, linestyle=":")
            axes.tick_params(labelsize=7)

        rows = [(label, value / 1000.0, unit.replace("N", "kN"))
                for label, value, unit in result.rows()]
        return rows, result.notes


# --------------------------------------------------------------------------
class MohrTab(ChartTab):
    """Mohr's circle for a plane stress state."""

    title = "Mohr's circle"
    hint = "the same stress state seen from every angle"

    def build_form(self, parent) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x")
        self.sx = self.field(row, "sigma x", "80", "MPa")
        self.sy = self.field(row, "sigma y", "-40", "MPa")
        self.txy = self.field(row, "tau xy", "25", "MPa")
        self.angle = self.field(row, "axes turned", "0", "degrees")

    def draw(self) -> tuple:
        state = Mohr(self.number(self.sx, "sigma x"),
                     self.number(self.sy, "sigma y"),
                     self.number(self.txy, "tau xy"))
        turned = self.number(self.angle, "the angle")

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        x, y = state.circle()
        axes.plot(x, y, color="#1f4e79", linewidth=1.5)
        axes.axhline(0, color="#888888", linewidth=0.8)
        axes.plot([state.sigma_2, state.sigma_1], [0, 0], "o",
                  color="#c0392b", markersize=6)
        for value, name in ((state.sigma_1, "sigma 1"),
                            (state.sigma_2, "sigma 2")):
            axes.annotate(f"{name} = {value:.4g}", (value, 0),
                          textcoords="offset points", xytext=(0, 8),
                          fontsize=7, ha="center", color="#c0392b")
        # The pair of points the given axes sit at, and the diameter joining
        # them - which is the construction itself.
        first, second = state.at_angle(turned), state.at_angle(turned + 90.0)
        axes.plot([first[0], second[0]], [first[1], second[1]], "-",
                  color="#0b7a3b", linewidth=1.2)
        axes.plot([first[0], second[0]], [first[1], second[1]], "o",
                  color="#0b7a3b", markersize=6)
        axes.annotate(f"({first[0]:.4g}, {first[1]:.4g})", first,
                      textcoords="offset points", xytext=(8, 4), fontsize=7,
                      color="#0b7a3b")
        axes.set_xlabel("direct stress", fontsize=8)
        axes.set_ylabel("shear stress", fontsize=8)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.set_aspect("equal", adjustable="datalim")

        rows = [(label, value, unit) for label, value, unit in state.rows()]
        rows.append((f"on axes turned {turned:g} deg",
                     first[0], "direct stress"))
        rows.append((f"and the shear there", first[1], "shear stress"))
        return rows, []


# --------------------------------------------------------------------------
class MoodyTab(ChartTab):
    """The Moody chart, with this flow marked on it."""

    title = "Moody chart"
    hint = "friction factor against Reynolds number"

    def build_form(self, parent) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x")
        self.reynolds = self.field(row, "Reynolds number", "100000", "",
                                   width=12)
        self.material = tk.StringVar(value="galvanised steel")
        ttk.Label(row, text="Surface").pack(side="left")
        box = ttk.Combobox(row, state="readonly", width=20,
                           textvariable=self.material,
                           values=list(moody.MATERIALS))
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.diameter = self.field(row, "Bore", "150", "mm")

    def draw(self) -> tuple:
        reynolds = self.number(self.reynolds, "the Reynolds number")
        bore = self.number(self.diameter, "the bore") / 1000.0
        absolute = moody.MATERIALS[self.material.get()]
        roughness = moody.relative_roughness(absolute, bore)
        factor, regime, note = moody.friction_factor(reynolds, roughness)

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        for value in moody.ROUGHNESSES:
            x, y = moody.curve(value)
            axes.plot(x, y, color="#b8bec8", linewidth=0.7)
        x, y = moody.curve(roughness)
        axes.plot(x, y, color="#1f4e79", linewidth=1.8,
                  label=f"e/D = {roughness:.2g}")
        axes.plot([reynolds], [factor], "o", color="#c0392b", markersize=8,
                  zorder=5, label=f"this flow, f = {factor:.4f}")
        axes.axvspan(moody.LAMINAR_LIMIT, moody.TURBULENT_START,
                     color="#e8b923", alpha=0.18)
        axes.annotate("transition", (3000, 0.07), fontsize=7, ha="center",
                      color="#8a6d0b")
        axes.set_xscale("log")
        axes.set_yscale("log")
        axes.set_xlabel("Reynolds number", fontsize=8)
        axes.set_ylabel("Darcy friction factor", fontsize=8)
        axes.grid(True, which="both", alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.legend(loc="best", fontsize=7, framealpha=0.85)

        rows = [("friction factor", factor, ""),
                ("regime", regime, ""),
                ("relative roughness", roughness, "e/D"),
                ("absolute roughness", absolute * 1000.0, "mm"),
                ("Reynolds number", reynolds, "")]
        return rows, [note] if note else []


# --------------------------------------------------------------------------
class TensileTab(ChartTab):
    """A stress-strain curve, read the way a ruler would read it."""

    title = "Stress and strain"
    hint = "paste a tensile test and it reads the modulus, yield and UTS off it"

    EXAMPLE = "\n".join(
        f"{s:.5f}\t{v:.1f}" for s, v in
        [(i * 0.00125 / 29, i * 0.00125 / 29 * 200000) for i in range(30)]
        + [(0.00125 + i * 0.0195, 400 - 150 * 2.718281828 **
            (-(i * 0.0195) * 25)) for i in range(1, 11)])

    def build_form(self, parent) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x")
        self.offset = self.field(row, "Proof offset", "0.2", "%")
        ttk.Label(row, text="strain in the first column, stress in the "
                            "second", style="Hint.TLabel").pack(side="left")

        self.data = tk.Text(parent, height=6, width=30, font=MONO,
                            wrap="none")
        self.data.pack(fill="x", pady=(6, 0))
        self.data.insert("1.0", self.EXAMPLE)
        self.data.bind("<KeyRelease>", lambda e: self.refresh())

    def draw(self) -> tuple:
        strain, stress = [], []
        for line in self.data.get("1.0", "end").splitlines():
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                strain.append(float(parts[0]))
                stress.append(float(parts[1]))
            except ValueError:
                continue
        if len(strain) < tensile.MINIMUM_POINTS:
            raise ParseError(
                f"{len(strain)} readings. Paste two columns - strain, then "
                f"stress - with {tensile.MINIMUM_POINTS} at least.")

        offset = self.number(self.offset, "the proof offset") / 100.0
        curve = tensile.read_curve(strain, stress, offset)

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.plot(curve.strain, curve.stress, "-", color="#1f4e79",
                  linewidth=1.5, label="the test")
        # The straight part it took the modulus from, and the offset line
        # the proof stress is read off - the two constructions a ruler does.
        elastic = slice(0, curve.elastic_points)
        axes.plot(curve.strain[elastic], curve.stress[elastic], "-",
                  color="#0b7a3b", linewidth=2.6, alpha=0.5,
                  label="the straight part")
        line_x = np.array([offset, offset + curve.ultimate / curve.modulus])
        axes.plot(line_x, curve.modulus * (line_x - offset), "--",
                  color="#c0392b", linewidth=1.0,
                  label=f"{offset * 100:g}% offset")
        if curve.proof_stress == curve.proof_stress:
            axes.plot([curve.proof_strain], [curve.proof_stress], "o",
                      color="#c0392b", markersize=7, zorder=5)
        axes.plot([curve.ultimate_strain], [curve.ultimate], "o",
                  color="#8e44ad", markersize=7, zorder=5, label="ultimate")
        axes.set_xlabel("strain", fontsize=8)
        axes.set_ylabel("stress", fontsize=8)
        axes.set_ylim(bottom=0)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.legend(loc="lower right", fontsize=7, framealpha=0.85)
        return curve.rows(), curve.notes


CHARTS = [
    ("  Stress and strain  ", TensileTab),
    ("  Beam  ", BeamTab),
    ("  Mohr's circle  ", MohrTab),
    ("  Moody  ", MoodyTab),
]
