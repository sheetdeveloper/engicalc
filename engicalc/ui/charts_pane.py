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
from matplotlib.patches import Arc

from ..core.parsing import ParseError, parse_number
from ..export.excel import export_table
from . import figures
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
        ttk.Button(actions, text="Copy numbers",
                   command=self.copy).pack(side="right", padx=6)
        ttk.Button(actions, text="Copy chart",
                   command=self.copy_chart).pack(side="right")
        ttk.Button(actions, text="Save chart...",
                   command=self.save_chart).pack(side="right", padx=6)

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
        self.layout()
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
            initialfile=f"{self._file_name()}.xlsx")
        if not path:
            return
        try:
            # The chart goes in beside the numbers. A workbook of peak
            # values is not what anybody opens the file to see.
            with figures.temporary_png(self.figure) as picture:
                export_table(("Quantity", "Value", "Unit"),
                             [list(row) for row in self.rows], path,
                             title=self.title, sheet="Chart",
                             picture=picture)
            self.status.configure(text="Exported, chart and all")
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def _file_name(self) -> str:
        return self.title.lower().replace(" ", "-").replace("'", "")

    def save_chart(self) -> None:
        """The chart as a picture - PNG for a report, PDF or SVG to print."""
        try:
            path = figures.save_figure(self.figure, self._file_name())
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        if path:
            self.status.configure(text="Chart saved")

    def copy_chart(self) -> None:
        try:
            figures.copy_figure(self.figure)
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Could not copy", str(exc))
            return
        self.status.configure(text="Chart copied - paste it into your report")

    # -- for subclasses -----------------------------------------------------
    def layout(self) -> None:
        """Fit the drawing to the pane. Overridden where that is not enough."""
        self.figure.tight_layout()

    def build_form(self, parent) -> None:
        raise NotImplementedError

    def draw(self) -> tuple:
        """Draw the chart. Returns (rows, notes)."""
        raise NotImplementedError


# --------------------------------------------------------------------------
class LoadRow:
    """One line of the beam's load table.

    A row rather than a fixed pair of fields, because a beam carries what it
    carries. Columns that mean nothing for the kind chosen are greyed rather
    than hidden, so the table keeps its shape as rows change kind.
    """

    #: (name, width) - the heading uses the same widths so they line up.
    COLUMNS = (("at", 7), ("to", 7), ("size", 8), ("size_to", 8),
               ("angle", 6))

    #: Which columns each kind uses, and what its size is measured in.
    USES = {
        "point": (("at", "size", "angle"), "kN, at that angle to the beam"),
        "spread": (("at", "to", "size", "size_to"),
                   "kN/m, and kN/m at the far end"),
        "moment": (("at", "size"), "kN m anticlockwise"),
    }

    def __init__(self, tab, parent, kind="point", at="2", to="",
                 size="12", size_to="", angle="90"):
        self.tab = tab
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=1)

        self.kind = tk.StringVar(value=kind)
        box = ttk.Combobox(self.frame, width=8, state="readonly",
                           values=list(self.USES), textvariable=self.kind)
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda e: self._retitle())

        given = {"at": at, "to": to, "size": size, "size_to": size_to,
                 "angle": angle}
        self.entries = {}
        for name, width in self.COLUMNS:
            variable = tk.StringVar(value=given[name])
            entry = ttk.Entry(self.frame, textvariable=variable, width=width,
                              font=MONO)
            entry.pack(side="left", padx=(4, 0))
            entry.bind("<Return>", lambda e: self.tab.refresh())
            variable.trace_add("write", lambda *a: self.tab.refresh())
            setattr(self, name, variable)
            self.entries[name] = entry

        self.unit = ttk.Label(self.frame, text="", style="Hint.TLabel",
                              width=30, anchor="w")
        self.unit.pack(side="left", padx=(8, 0))
        ttk.Button(self.frame, text="Remove", width=7,
                   command=self.remove).pack(side="right")
        self._retitle()

    def _retitle(self) -> None:
        """Grey the columns this kind does not use, and say the units."""
        used, unit = self.USES.get(self.kind.get(), ((), ""))
        for name, entry in self.entries.items():
            entry.configure(state="normal" if name in used else "disabled")
        self.unit.configure(text=unit)
        self.tab.refresh()

    def remove(self) -> None:
        self.frame.destroy()
        if self in self.tab.load_rows:
            self.tab.load_rows.remove(self)
        self.tab.refresh()

    # -- reading it back ----------------------------------------------------
    def _value(self, variable, fallback=None):
        text = variable.get().strip()
        if not text:
            return fallback
        value = parse_number(text)
        if value is None:
            raise ParseError(f"'{text}' is not a number.")
        return float(value)

    def load(self, length: float):
        """The load this row describes, in newtons, or None if it is blank."""
        kind = self.kind.get()
        size = self._value(self.size)
        far_size = self._value(self.size_to) if kind == "spread" else None
        if not size and not far_size:
            return None                # a blank or zero row is not a load
        at = self._value(self.at, 0.0)
        if kind == "point":
            # Ninety degrees is straight down, so an ordinary vertical load
            # needs nothing said about it.
            return beams.inclined(at, size * 1000.0,
                                  self._value(self.angle, 90.0))
        if kind == "moment":
            return beams.Moment(at, size * 1000.0)
        # A load ramping up from nothing has a zero at one end and is still
        # a load; only a row with nothing in it at all is skipped.
        far = min(self._value(self.to, length), length)
        return beams.Distributed(
            at, far, -(size or 0.0) * 1000.0,
            None if far_size is None else -far_size * 1000.0)


# --------------------------------------------------------------------------
class BeamTab(ChartTab):
    """Shear force, bending moment and axial force, worked from the loads."""

    title = "Beam diagrams"
    hint = "the free body, then shear, moment and axial force along the span"

    #: The beam it starts on - a load part way along and a spread load over
    #: the whole span, which is the shape of most of the worked examples.
    STARTING_LOADS = (
        dict(kind="point", at="2", size="12", angle="90"),
        dict(kind="spread", at="0", to="6", size="5"),
    )

    #: What a support can be. A roller holds the beam up, a pin holds it up
    #: and back, a built-in end does both and stops it turning too - and
    #: "none" is how a cantilever is described, by there being nothing at
    #: the far end.
    SUPPORT_KINDS = ("pin", "roller", "fixed", "none")

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        self.length = self.field(first, "Length", "6", "m")

        # Supports where you put them and whatever kind you want, which is
        # the point of letting them move: a beam held in from its ends
        # overhangs and hogs over the support, and which one is the pin
        # decides which half of it an inclined load pulls.
        ttk.Label(first, text="Held at").pack(side="left")
        self.first_support = tk.StringVar(value="0")
        self.first_kind = tk.StringVar(value="pin")
        self.second_support = tk.StringVar(value="6")
        self.second_kind = tk.StringVar(value="roller")
        self.support_entries = []
        for index, (where, kind) in enumerate(
                ((self.first_support, self.first_kind),
                 (self.second_support, self.second_kind))):
            if index:
                ttk.Label(first, text="and").pack(side="left", padx=(8, 0))
            entry = ttk.Entry(first, textvariable=where, width=6, font=MONO)
            entry.pack(side="left", padx=(4, 2))
            entry.bind("<Return>", lambda e: self.refresh())
            where.trace_add("write", lambda *a: self.refresh())
            ttk.Label(first, text="m", style="Hint.TLabel").pack(side="left")
            box = ttk.Combobox(first, state="readonly", width=7,
                               textvariable=kind,
                               values=list(self.SUPPORT_KINDS))
            box.pack(side="left", padx=(4, 0))
            box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
            self.support_entries.append(entry)
        self.support_hint = ttk.Label(first, text="", style="Hint.TLabel")
        self.support_hint.pack(side="left", padx=(10, 0))

        heading = ttk.Frame(parent)
        heading.pack(fill="x", pady=(8, 0))
        ttk.Label(heading, text="Loads", width=9).pack(side="left")
        for label, width in (("at / from", 7), ("to", 7), ("size", 8),
                             ("to size", 8), ("angle", 6)):
            ttk.Label(heading, text=label, width=width,
                      style="Hint.TLabel").pack(side="left", padx=(4, 0))

        self.load_table = ScrollFrame(parent, height=84)
        self.load_table.pack(fill="x")
        self.load_rows = []
        for spec in self.STARTING_LOADS:
            self.load_rows.append(
                LoadRow(self, self.load_table.body, **spec))

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(4, 0))
        for label, spec in (
                ("Add point load", dict(kind="point", at="3", size="10",
                                        angle="90")),
                ("Add spread load", dict(kind="spread", at="0", to="6",
                                         size="5")),
                ("Add moment", dict(kind="moment", at="3", size="8"))):
            ttk.Button(buttons, text=label,
                       command=lambda s=spec: self.add_load(**s)).pack(
                           side="left", padx=(0, 6))
        self.free_body = tk.BooleanVar(value=True)
        ttk.Checkbutton(buttons, text="Free body diagram",
                        variable=self.free_body,
                        command=self.refresh).pack(side="right")

    def add_load(self, **spec) -> None:
        self.load_rows.append(LoadRow(self, self.load_table.body, **spec))
        self.refresh()

    def _supports(self) -> list:
        """The supports as described, leaving out the ones set to none."""
        found = []
        for where, kind, what in (
                (self.first_support, self.first_kind,
                 "where the beam is held"),
                (self.second_support, self.second_kind,
                 "where the other support is")):
            if kind.get() == "none":
                continue
            found.append(beams.Support(self.number(where, what), kind.get()))
        if not found:
            raise ParseError("Nothing is holding the beam up.")
        return found

    def draw(self) -> tuple:
        length = self.number(self.length, "the length")

        loads = []
        for row in self.load_rows:
            load = row.load(length)
            if load is not None:
                loads.append(load)

        supports = self._supports()
        beam = beams.Beam(length=length, supports=supports, loads=loads)
        result = beams.analyse(beam)

        places = [support.position for support in supports]
        overhanging = (len(supports) > 1
                       and (min(places) > 1e-9
                            or max(places) < length - 1e-9))
        self.support_hint.configure(text="overhanging" if overhanging else "")

        has_axial = bool(result.axial is not None
                         and np.any(np.abs(result.axial) > 1e-9))
        sketches = 2 if self.free_body.get() else 1
        curves = 3 if has_axial else 2

        self.figure.clear()
        ratios = [1.3] * sketches + [1.15] * curves
        grid = self.figure.add_gridspec(sketches + curves, 1, hspace=0.34,
                                        height_ratios=ratios)
        # How tall one sketch is, in points, so the arrows can be drawn to
        # fit it. Sized blindly they overshot into the panel above, which on
        # five stacked panels is most of the drawing.
        panel = (self.figure.get_size_inches()[1] * 72.0
                 * ratios[0] / sum(ratios) * 0.72)
        self.arrow_reach = max(16.0, min(0.38 * panel, 40.0))

        top = self.figure.add_subplot(grid[0])
        self._draw_beam(top, beam, result, free_body=False)
        if sketches == 2:
            self._draw_beam(self.figure.add_subplot(grid[1], sharex=top),
                            beam, result, free_body=True)

        shear_axes = self.figure.add_subplot(grid[sketches], sharex=top)
        moment_axes = self.figure.add_subplot(grid[sketches + 1], sharex=top)
        self._draw_curve(shear_axes, result.x, result.shear / 1000.0,
                         "#1f4e79", "shear  kN")
        self._draw_curve(moment_axes, result.x, result.moment / 1000.0,
                         "#c0392b", "moment  kN m")
        last = moment_axes
        if has_axial:
            axial_axes = self.figure.add_subplot(grid[sketches + 2],
                                                 sharex=top)
            self._draw_curve(axial_axes, result.x, result.axial / 1000.0,
                             "#0b7a3b", "axial  kN")
            last = axial_axes
        for axes in (shear_axes, moment_axes):
            if axes is not last:
                axes.tick_params(labelbottom=False)
        last.set_xlabel("distance along the beam  m", fontsize=8)
        top.set_xlim(-0.08 * length, 1.08 * length)

        rows = [(label, value / 1000.0, unit.replace("N", "kN"))
                for label, value, unit in result.rows()]
        return rows, result.notes

    def layout(self) -> None:
        """Left to the gridspec.

        tight_layout will not lay out a grid that has been given its own
        spacing - it says so, on every redraw - and the spacing here is
        deliberate: the two sketches want to sit closer to each other than
        the diagrams below them do.
        """
        self.figure.subplots_adjust(left=0.13, right=0.98, top=0.97,
                                    bottom=0.1)

    def _draw_curve(self, axes, x, values, colour: str, label: str) -> None:
        axes.plot(x, values, color=colour, linewidth=1.5)
        axes.axhline(0, color="#888888", linewidth=0.8)
        axes.fill_between(x, values, 0, color=colour, alpha=0.12)
        # Small, because the label is written up the side of the panel and
        # five panels in one figure leaves each of them shorter than the
        # words. At eight point "moment  kN m" ran into the label above it.
        axes.set_ylabel(label, fontsize=7, labelpad=2)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)

    # -- the beam itself ----------------------------------------------------
    #: Where a force's label sits, as a fraction of the panel's height.
    LABEL_AT = 1.16

    def _arrow(self, axes, at: float, unit_x: float, unit_y: float,
               label: str, colour: str, scale: float = 1.0,
               label_at: float | None = None, nudge: float = 0.0) -> None:
        """One force arrow, drawn pointing the way the force points.

        The arrow is offset in points rather than in data units, so it leans
        at the angle the force was given rather than at whatever the axes
        make of it: a 6 m beam a quarter of an inch tall would draw a load
        at sixty degrees as one at five.

        The label is placed in data units instead, up against the top of the
        panel. Hung off the end of the arrow it landed in the panel above,
        where it belonged to a different diagram.
        """
        reach = self.arrow_reach * scale
        axes.annotate("", xy=(at, 0.0),
                      xytext=(-unit_x * reach, -unit_y * reach),
                      textcoords="offset points",
                      arrowprops=dict(arrowstyle="-|>", color=colour,
                                      linewidth=1.3, shrinkA=0, shrinkB=0))
        above = unit_y < 0
        height = (self.LABEL_AT if above else -self.LABEL_AT)
        axes.annotate(label,
                      (at + nudge, height if label_at is None else label_at),
                      fontsize=6.5, color=colour,
                      ha="center" if not nudge else "left",
                      va="top" if above else "bottom")

    def _draw_beam(self, axes, beam, result, free_body: bool) -> None:
        """The beam as described, or the same beam cut free of its supports.

        The free body is the step the whole method turns on and the one
        people skip: the supports come away and their reactions stand in
        their place. Drawn beside the loading it is a substitution you can
        see rather than one you are told about.
        """
        length = beam.length
        axes.plot([0, length], [0, 0], color="#333333", linewidth=3,
                  solid_capstyle="butt", zorder=4)

        if free_body:
            self._draw_reactions(axes, beam, result)
        else:
            self._draw_supports(axes, beam)

        # One arrow length for all of them, so the picture says which load
        # is the big one.
        points = [load for load in beam.loads
                  if isinstance(load, beams.PointLoad)]
        biggest = max((float(np.hypot(load.magnitude, load.along))
                       for load in points), default=0.0)
        for load in points:
            size = float(np.hypot(load.magnitude, load.along))
            if not size:
                continue
            # Scaled a little by how big it is, so the picture says which
            # load is the heavy one without anybody reading the numbers.
            self._arrow(axes, load.position, load.along / size,
                        load.magnitude / size, f"{size / 1000.0:g} kN",
                        "#c0392b", 0.6 + 0.4 * (size / biggest))

        spreads = [load for load in beam.loads
                   if isinstance(load, beams.Distributed)]
        tallest = max((max(abs(load.magnitude), abs(load.finish))
                       for load in spreads), default=0.0)
        for load in spreads:
            if not tallest:
                continue
            # Drawn on the side it pushes from - a load pressing down sits on
            # top of the beam, the way it is drawn on paper - and ramped if
            # it ramps, so a triangular load looks like one.
            here = -0.62 * load.magnitude / tallest
            there = -0.62 * load.finish / tallest
            axes.fill([load.start, load.end, load.end, load.start],
                      [0, 0, there, here], color="#c0392b", alpha=0.16,
                      zorder=2)
            axes.plot([load.start, load.end], [here, there],
                      color="#c0392b", linewidth=1.0, zorder=3)
            label = (f"{abs(load.magnitude) / 1000.0:g} kN/m"
                     if load.end_magnitude is None else
                     f"{abs(load.magnitude) / 1000.0:g} to "
                     f"{abs(load.finish) / 1000.0:g} kN/m")
            highest = max(here, there)
            axes.annotate(label, ((load.start + load.end) / 2.0,
                                  highest + 0.1 if highest > 0
                                  else min(here, there) - 0.1),
                          fontsize=6.5, ha="center",
                          va="bottom" if highest > 0 else "top",
                          color="#c0392b")

        for load in beam.loads:
            if isinstance(load, beams.Moment):
                self._couple(axes, length, load.position, load.magnitude,
                             "#8a4fbf")

        axes.set_ylim(-1.5, 1.5)
        axes.set_yticks([])
        axes.tick_params(labelbottom=False, length=0)
        for side in ("left", "right", "top", "bottom"):
            axes.spines[side].set_visible(False)
        # In the margin beside the drawing, lined up with the labels on the
        # diagrams below. Written inside it, it sat on top of the wall of a
        # cantilever, which is exactly where a caption must not be.
        axes.set_ylabel("free body" if free_body else "the beam",
                        fontsize=7, labelpad=2, color="#666666")

    def _draw_supports(self, axes, beam) -> None:
        """Each support drawn as the thing it is.

        A pin sits on hatched ground, a roller on a line it can slide along,
        and a built-in end is a hatched wall. Told apart at a glance,
        because which is which changes the answer.
        """
        for support in beam.held:
            place, width = support.position, 0.03 * beam.length
            if support.holds_turning:
                axes.plot([place, place], [-0.7, 0.7], color="#333333",
                          linewidth=2.5, zorder=5)
                away = -1.0 if place > beam.length / 2.0 else 1.0
                for offset in np.linspace(-0.7, 0.5, 6):
                    axes.plot([place, place - away * width],
                              [offset, offset + 0.2], color="#888888",
                              linewidth=0.9, zorder=5)
                continue
            # No distance written under it: the axis below the diagrams is
            # shared with this one and already says where it is.
            axes.plot([place], [-0.16], marker="^", markersize=10,
                      color="#1f4e79", zorder=5)
            ground = -0.62 if support.holds_along else -0.72
            axes.plot([place - 1.6 * width, place + 1.6 * width],
                      [ground, ground], color="#1f4e79", linewidth=1.0,
                      zorder=5)
            if support.holds_along:
                for offset in np.linspace(-1.4, 1.0, 5):
                    axes.plot([place + offset * width,
                               place + (offset - 0.6) * width],
                              [ground, ground - 0.18], color="#888888",
                              linewidth=0.9, zorder=5)
            else:
                # Rollers: the thing that says it is free to slide.
                for offset in (-0.9, 0.0, 0.9):
                    axes.plot([place + offset * width], [-0.5], marker="o",
                              markersize=3, color="#1f4e79", zorder=5)

    def _draw_reactions(self, axes, beam, result) -> None:
        """The supports taken away and what they were doing put in instead."""
        for place, value in sorted(result.reactions.items(),
                                   key=lambda pair: str(pair[0])):
            if isinstance(place, str):
                continue
            if not value:
                continue
            # The size only, never the sign: the arrow is already pointing
            # the way it acts, and a minus sign beside it says the opposite
            # half the time.
            self._arrow(axes, float(place), 0.0, value / abs(value),
                        f"{abs(value) / 1000.0:.4g} kN", "#1f4e79")
        for place, value in result.reactions.items():
            if not isinstance(place, str) or not value:
                continue
            where = float(place.split(" at ")[-1])
            if place.startswith("moment at "):
                # Above the beam. A built-in end has a force, a thrust and a
                # couple at the same station, and all three labelled at the
                # same height came out as one smudge.
                self._couple(axes, beam.length, where, value, "#1f4e79",
                             label_at=1.16)
            else:
                # Higher than the support reaction below it, which is at the
                # same station and was writing over it.
                # Nudged along the beam as well as up, because a built-in
                # end has a force and a thrust at the same station and two
                # labels one under the other still touch in a short panel.
                self._arrow(axes, where, value / abs(value), 0.0,
                            f"{abs(value) / 1000.0:.4g} kN", "#0b7a3b",
                            label_at=-0.55, nudge=0.06 * beam.length)

    def _couple(self, axes, length: float, at: float, size: float,
                colour: str, label_at: float = -1.16) -> None:
        """A curved arrow for an applied or resisting moment."""
        axes.add_patch(Arc((at, 0.0), max(0.09 * length, 1e-6), 1.0,
                           theta1=250 if size > 0 else 70,
                           theta2=110 if size > 0 else 290,
                           color=colour, linewidth=1.4, zorder=5))
        axes.annotate(f"{abs(size) / 1000.0:.4g} kN m", (at, label_at),
                      fontsize=6.5, ha="center",
                      va="bottom" if label_at > 0 else "top", color=colour)


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
