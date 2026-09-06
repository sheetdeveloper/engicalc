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

import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Arc, Rectangle

from ..core import (beams, buckling, geometry, materials, motion, moody,
                    section_table, sections, tensile, torsion,
                    trusses, vessels)
from ..core.display import fmt_number
from ..core import mohr
from ..core.mohr import Mohr
from ..core.parsing import ParseError, parse_number
from ..export.excel import export_table
from . import figures
from .widgets import BY_HAND, MONO, ScrollFrame


def material_picker(tab, parent, label: str = "Material"):
    """A box offering the grades, which fills the fields beside it.

    Only grades. A class is a range and a calculation wants a number;
    handing over the middle of 250 to 1500 N/mm2 would look like an answer
    and be worse than nothing.
    """
    ttk.Label(parent, text=label).pack(side="left")
    chosen = tk.StringVar(value=BY_HAND)
    box = ttk.Combobox(parent, state="readonly", width=22,
                       textvariable=chosen,
                       values=[BY_HAND] + materials.names(grades=True))
    box.pack(side="left", padx=(4, 14))
    box.bind("<<ComboboxSelected>>", lambda e: tab.take_material())
    return chosen


def _sideways_label(axes, label: str) -> None:
    """Name an axis across the margin rather than up the side of it.

    A stacked diagram is short and a label written up the side of a short
    panel runs into the one above. Written across it uses the margin, which
    is the same width however many panels there are - so it stops being a
    thing that breaks again each time one is added.
    """
    axes.set_ylabel(label.replace("  ", "\n"), fontsize=7, rotation=0,
                    ha="right", va="center", labelpad=6)


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
    def linked(self, charts: dict) -> None:
        """Told about the other charts once they all exist.

        Nothing has to use it. The beam does, so that a section worked out
        next door can be put straight on it rather than copied across by
        hand, which is how a beam ends up analysed with somebody else's I.
        """

    def layout(self) -> None:
        """Fit the drawing to the pane. Overridden where that is not enough."""
        self.figure.tight_layout()

    def build_form(self, parent) -> None:
        raise NotImplementedError

    def draw(self) -> tuple:
        """Draw the chart. Returns (rows, notes)."""
        raise NotImplementedError


# --------------------------------------------------------------------------
#: What the section chooser says when there is no section, and when it
#: should take whatever the Section tab currently has.
NO_SECTION = "-"
FROM_SECTION_TAB = "from Section tab"


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
        # A third, off unless it is wanted. Two supports is a simple span
        # and three is a continuous beam, which needs the deflection to
        # settle and so could not be described here until it did.
        self.third_support = tk.StringVar(value="3")
        self.third_kind = tk.StringVar(value="none")
        self.support_entries = []
        for index, (where, kind) in enumerate(
                ((self.first_support, self.first_kind),
                 (self.second_support, self.second_kind),
                 (self.third_support, self.third_kind))):
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

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        ttk.Label(second, text="Section").pack(side="left")
        self.section_name = tk.StringVar(value="-")
        chooser = ttk.Combobox(second, state="readonly", width=17,
                               textvariable=self.section_name,
                               values=([NO_SECTION, FROM_SECTION_TAB]
                                       + section_table.names()))
        chooser.pack(side="left", padx=(4, 14))
        chooser.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.modulus = self.field(second, "E", "210", "GPa")
        self.material = material_picker(self, second, "of")
        self.section_hint = ttk.Label(second, text="", style="Hint.TLabel")
        self.section_hint.pack(side="left", padx=(4, 0))

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

    def take_material(self) -> None:
        """Fill the modulus from the material picked."""
        material = materials.find(self.material.get())
        if material is not None and material.has("youngs"):
            self.modulus.set(f"{material.typical('youngs'):.6g}")
        self.refresh()

    def linked(self, charts: dict) -> None:
        self.section_tab = charts.get("Section")

    def section(self):
        """The section to work the stress and the movement out on.

        None when there is not one, which is the ordinary case: the shear
        and the moment do not depend on what the beam is made of, and asking
        for a material before drawing them would be asking for something
        that is not needed yet.
        """
        chosen = self.section_name.get()
        if chosen in ("", NO_SECTION):
            return None
        if chosen == FROM_SECTION_TAB:
            beside = getattr(self, "section_tab", None)
            if beside is None:
                return None
            try:
                return beside.section()
            except Exception:                          # noqa: BLE001
                return None      # half-typed next door is not an error here
        return section_table.build(chosen)

    def _supports(self) -> list:
        """The supports as described, leaving out the ones set to none."""
        found = []
        for where, kind, what in (
                (self.first_support, self.first_kind,
                 "where the beam is held"),
                (self.second_support, self.second_kind,
                 "where the other support is"),
                (self.third_support, self.third_kind,
                 "where the third support is")):
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

        # E I in newton metres squared. The section is in millimetres and
        # the modulus in gigapascals, which is the conversion this exists to
        # get right: 1 mm^4 is 1e-12 m^4 and 1 GPa is 1e9 N/m^2.
        section = self.section()
        properties = section.properties() if section is not None else None
        stiffness = 0.0
        if properties is not None:
            stiffness = (self.number(self.modulus, "the modulus") * 1e9
                         * properties.ixx * 1e-12)
        result = beams.analyse(beam, stiffness=stiffness)

        places = [support.position for support in supports]
        overhanging = (len(supports) > 1
                       and (min(places) > 1e-9
                            or max(places) < length - 1e-9))
        self.support_hint.configure(text="overhanging" if overhanging else "")

        has_axial = bool(result.axial is not None
                         and np.any(np.abs(result.axial) > 1e-9))
        has_drop = result.deflection is not None
        sketches = 2 if self.free_body.get() else 1
        curves = 2 + (1 if has_axial else 0) + (1 if has_drop else 0)

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
        drawn = [shear_axes, moment_axes]
        step = sketches + 2
        if has_axial:
            axial_axes = self.figure.add_subplot(grid[step], sharex=top)
            self._draw_curve(axial_axes, result.x, result.axial / 1000.0,
                             "#0b7a3b", "axial  kN")
            drawn.append(axial_axes)
            last = axial_axes
            step += 1
        if has_drop:
            drop_axes = self.figure.add_subplot(grid[step], sharex=top)
            # Drawn in millimetres, which is the unit a deflection limit is
            # always quoted in, and negative downwards because that is which
            # way it went.
            self._draw_curve(drop_axes, result.x, result.deflection * 1000.0,
                             "#8a4fbf", "deflection  mm")
            drawn.append(drop_axes)
            last = drop_axes
        for axes in drawn:
            if axes is not last:
                axes.tick_params(labelbottom=False)
        last.set_xlabel("distance along the beam  m", fontsize=8)
        top.set_xlim(-0.08 * length, 1.08 * length)

        rows = [(label, value / 1000.0, unit.replace("N", "kN"))
                for label, value, unit in result.rows()]
        notes = list(result.notes)
        if properties is not None:
            rows += self._section_rows(beam, result, section, properties)
            notes += self._section_notes(rows)
            self.section_hint.configure(
                text=f"Ixx {properties.ixx / 1e4:.0f} cm4, "
                     f"Z {properties.z / 1e3:.0f} cm3")
        else:
            self.section_hint.configure(text="")
        return rows, notes

    #: Where a bending stress stops describing anything elastic, and the
    #: deflection a floor is commonly held to. Neither is a rule this
    #: enforces - one is a grade of steel and the other is what the beam is
    #: for - but a number on the wrong side of either is worth saying out
    #: loud rather than leaving in a table.
    YIELD = 355.0
    FLOOR_LIMIT = 360.0

    def _section_notes(self, rows) -> list:
        """When the answer has stopped describing anything."""
        found = dict((label, value) for label, value, _unit in rows)
        said = []
        stress = found.get("largest bending stress")
        if stress is not None and abs(stress) > self.YIELD:
            said.append(
                f"{abs(stress):.0f} N/mm2 is past the yield of ordinary "
                f"structural steel, so the deflection below - which assumes "
                f"it springs back - is describing a beam that does not. The "
                f"arithmetic is right and the section is too small.")
        ratio = found.get("span over deflection")
        if ratio is not None and 0 < ratio < self.FLOOR_LIMIT:
            said.append(
                f"It moves span/{ratio:.0f}. A floor is commonly held to "
                f"span/360, though what is acceptable depends on what the "
                f"beam is carrying and what is attached to it.")
        return said

    def _section_rows(self, beam, result, section, properties) -> list:
        """What the section adds: how hard it is worked, and how far it
        moves."""
        _at, moment = result.max_moment
        # Newton metres to newton millimetres, because the section is in
        # millimetres and mixing the two is how a stress comes out a
        # thousand times wrong and still looks like a number.
        stress, _x, _y = section.worst_stress(moment * 1000.0)
        rows = [("section", section.name, ""),
                ("Ixx", properties.ixx / 1e4, "cm^4"),
                ("Z, the governing one", properties.z / 1e3, "cm^3"),
                ("largest bending stress", stress, "N/mm^2")]

        # The shear is the other half, and it peaks where the bending does
        # not - so a section passed on bending alone has not been checked.
        _where, shear = result.max_shear
        worst, _level = section.worst_shear(abs(shear))
        rows.append(("largest shear stress", abs(worst), "N/mm^2"))

        at_drop, drop = result.max_deflection
        rows.append(("largest deflection", drop * 1000.0,
                     f"mm, at {at_drop:g} m"))
        # Against the span it is spanning, which is what a limit is quoted
        # against - the distance between the supports, or the reach of a
        # cantilever, not the length of the timber.
        # The longest span between neighbouring supports, not the length of
        # the beam. On a continuous beam over three supports those are not
        # the same thing, and a limit of span/360 means the span that is
        # sagging rather than the whole timber.
        places = sorted(support.position for support in beam.held)
        span = (beam.length - places[0] if len(places) == 1
                else max(b - a for a, b in zip(places, places[1:])))
        if drop and span:
            rows.append(("span over deflection", span / abs(drop),
                         f"({span:g} m span)"))
        return rows

    def layout(self) -> None:
        """Left to the gridspec.

        tight_layout will not lay out a grid that has been given its own
        spacing - it says so, on every redraw - and the spacing here is
        deliberate: the two sketches want to sit closer to each other than
        the diagrams below them do.
        """
        self.figure.subplots_adjust(left=0.155, right=0.98, top=0.97,
                                    bottom=0.14)

    def _draw_curve(self, axes, x, values, colour: str, label: str) -> None:
        axes.plot(x, values, color=colour, linewidth=1.5)
        axes.axhline(0, color="#888888", linewidth=0.8)
        axes.fill_between(x, values, 0, color=colour, alpha=0.12)
        _sideways_label(axes, label)
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
                        fontsize=7, rotation=0, ha="right", va="center",
                        labelpad=6, color="#666666")

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
    """A plane stress state: where it came from, and whether it matters."""

    title = "Stress state"
    hint = "Mohr's circle, and whether the material can take it"

    BY_STRESS, BY_ROSETTE = "the stresses", "a strain gauge rosette"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        ttk.Label(first, text="Given").pack(side="left")
        self.given = tk.StringVar(value=self.BY_STRESS)
        box = ttk.Combobox(first, state="readonly", width=22,
                           textvariable=self.given,
                           values=[self.BY_STRESS, self.BY_ROSETTE])
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.sx = self.field(first, "sigma x", "80", "N/mm2")
        self.sy = self.field(first, "sigma y", "-40", "N/mm2")
        self.txy = self.field(first, "tau xy", "25", "N/mm2")

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        ttk.Label(second, text="Rosette").pack(side="left")
        self.rosette = tk.StringVar(value=list(mohr.ROSETTES)[0])
        kinds = ttk.Combobox(second, state="readonly", width=20,
                             textvariable=self.rosette,
                             values=list(mohr.ROSETTES))
        kinds.pack(side="left", padx=(4, 10))
        kinds.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.gauge_a = self.field(second, "a", "450", "microstrain", width=8)
        self.gauge_b = self.field(second, "b", "315", "", width=8)
        self.gauge_c = self.field(second, "c", "-120", "", width=8)
        self.modulus = self.field(second, "E", "210", "GPa", width=6)
        self.poisson = self.field(second, "nu", "0.3", "", width=6)

        third = ttk.Frame(parent)
        third.pack(fill="x", pady=(6, 0))
        self.angle = self.field(third, "Axes turned", "0", "degrees")
        self.yield_stress = self.field(third, "Yield", "275", "N/mm2")

    def state(self):
        if self.given.get() == self.BY_ROSETTE:
            readings = [self.number(box, f"gauge {name}") * 1e-6
                        for box, name in ((self.gauge_a, "a"),
                                          (self.gauge_b, "b"),
                                          (self.gauge_c, "c"))]
            angles = mohr.ROSETTES[self.rosette.get()]
            return mohr.from_rosette(
                readings, angles,
                self.number(self.modulus, "the modulus") * 1000.0,
                self.number(self.poisson, "Poisson's ratio"))
        return Mohr(self.number(self.sx, "sigma x"),
                    self.number(self.sy, "sigma y"),
                    self.number(self.txy, "tau xy"))

    def draw(self) -> tuple:
        state = self.state()
        turned = self.number(self.angle, "the angle")
        strength = self.number(self.yield_stress, "the yield stress")

        self.figure.clear()
        grid = self.figure.add_gridspec(1, 2, wspace=0.28)
        axes = self.figure.add_subplot(grid[0])
        self._draw_locus(self.figure.add_subplot(grid[1]), state, strength)
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

        axes.set_title("Mohr's circle", fontsize=8, color="#1f4e79")

        rows = [(label, value, unit) for label, value, unit in state.rows()]
        rows.append((f"on axes turned {turned:g} deg",
                     first[0], "direct stress"))
        rows.append(("and the shear there", first[1], "shear stress"))
        if self.given.get() == self.BY_ROSETTE:
            rows = self._strain_rows() + rows
        rows += state.failure_rows(strength)
        return rows, state.failure_notes(strength)

    def _strain_rows(self) -> list:
        """What the gauges said, before it became a stress."""
        readings = [self.number(box, f"gauge {name}") * 1e-6
                    for box, name in ((self.gauge_a, "a"),
                                      (self.gauge_b, "b"),
                                      (self.gauge_c, "c"))]
        across, up, shear = mohr.strains_from_rosette(
            readings, mohr.ROSETTES[self.rosette.get()])
        first, second, turn = mohr.principal_strains(across, up, shear)
        return [("strain ex", across * 1e6, "microstrain"),
                ("strain ey", up * 1e6, "microstrain"),
                ("shear strain gxy", shear * 1e6, "microstrain"),
                ("principal strain 1", first * 1e6, "microstrain"),
                ("principal strain 2", second * 1e6, "microstrain"),
                ("at", turn, "degrees")]

    def _draw_locus(self, axes, state, strength) -> None:
        """The two criteria, and this state among them.

        Tresca is a hexagon and von Mises the ellipse through its corners,
        so the hexagon is inside - which is what makes Tresca the safe one
        and is not obvious from either formula.
        """
        if strength > 0:
            first, second = state.tresca_locus(strength)
            axes.plot(first, second, color="#c0392b", linewidth=1.3,
                      label="Tresca")
            first, second = state.mises_locus(strength)
            axes.plot(first, second, color="#1f4e79", linewidth=1.3,
                      label="von Mises")
            axes.legend(loc="upper left", fontsize=6.5, framealpha=0.85)
        axes.plot([state.sigma_2], [state.sigma_1], "o", color="#0b7a3b",
                  markersize=7, zorder=5)
        axes.annotate("this state", (state.sigma_2, state.sigma_1),
                      textcoords="offset points", xytext=(7, 6),
                      fontsize=7, color="#0b7a3b")
        axes.axhline(0, color="#bbbbbb", linewidth=0.7)
        axes.axvline(0, color="#bbbbbb", linewidth=0.7)
        axes.set_xlabel("sigma 2  N/mm2", fontsize=8)
        axes.set_ylabel("sigma 1  N/mm2", fontsize=8)
        axes.grid(True, alpha=0.25, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.set_aspect("equal", adjustable="datalim")
        axes.set_title("does it yield?", fontsize=8, color="#c0392b")

    def layout(self) -> None:
        self.figure.subplots_adjust(left=0.1, right=0.97, top=0.92,
                                    bottom=0.13)


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


# --------------------------------------------------------------------------
class SectionTab(ChartTab):
    """Area, centroid and second moment of area for a shape."""

    title = "Section properties"
    hint = "the centroid and the second moment, from the dimensions"

    #: What the moment box means. Section properties are in millimetres and
    #: bending moments are quoted in kilonewton metres, and 1 kN m is 10^6
    #: N mm - which is the conversion this tab exists to get right for you.
    N_MM_PER_KN_M = 1e6

    #: Where a bending stress stops describing anything. Not a limit - the
    #: number is still worked out and shown - but a stress of five thousand
    #: newtons per square millimetre is a section that has already failed,
    #: and saying so is more use than printing it without comment.
    YIELD = 355.0

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")

        ttk.Label(first, text="From the table").pack(side="left")
        self.designation = tk.StringVar(value="305x165x40 UB")
        picker = ttk.Combobox(first, state="readonly", width=17,
                              textvariable=self.designation,
                              values=["-"] + section_table.names())
        picker.pack(side="left", padx=(4, 14))
        picker.bind("<<ComboboxSelected>>", lambda e: self._from_table())

        ttk.Label(first, text="or shape").pack(side="left")
        self.shape = tk.StringVar(value="I section")
        shapes = ttk.Combobox(first, state="readonly", width=18,
                              textvariable=self.shape,
                              values=list(sections.PROFILES))
        shapes.pack(side="left", padx=(4, 14))
        shapes.bind("<<ComboboxSelected>>", lambda e: self._shape_changed())

        self.moment = self.field(first, "Bending moment", "120", "kN m")
        self.shear = self.field(first, "shear", "100", "kN")

        # The dimension boxes are rebuilt when the shape changes, because
        # which of them there are is part of what a shape is.
        self.dimension_row = ttk.Frame(parent)
        self.dimension_row.pack(fill="x", pady=(6, 0))
        self.dimensions = {}
        self.stress = None
        self._shape_changed(draw=False)
        self._from_table(draw=False)

    # -- the dimension boxes ------------------------------------------------
    def _shape_changed(self, draw: bool = True) -> None:
        """Put up the boxes this shape is measured by.

        Values are kept by name across the change, so switching an I section
        to a tee keeps the depth and the flange you already typed rather
        than making you type them again.
        """
        for child in self.dimension_row.winfo_children():
            child.destroy()
        _builder, wanted, starting = sections.PROFILES[self.shape.get()]
        boxes = {}
        for name, start in zip(wanted, starting):
            holder = ttk.Frame(self.dimension_row)
            holder.pack(side="left", padx=(0, 12))
            ttk.Label(holder, text=name).pack(side="left")
            was = self.dimensions.get(name)
            variable = tk.StringVar(
                value=was.get() if was is not None else f"{start:g}")
            entry = ttk.Entry(holder, textvariable=variable, width=7,
                              font=MONO)
            entry.pack(side="left", padx=3)
            entry.bind("<Return>", lambda e: self.refresh())
            variable.trace_add("write", lambda *a: self._typed())
            ttk.Label(holder, text=sections.DIMENSIONS.get(name, ""),
                      style="Hint.TLabel").pack(side="left")
            boxes[name] = variable
        self.dimensions = boxes
        ttk.Label(self.dimension_row, text="mm",
                  style="Hint.TLabel").pack(side="left")
        if draw:
            self.refresh()

    def _typed(self) -> None:
        """Typing a dimension means this is no longer a catalogue section."""
        if getattr(self, "_filling", False):
            return
        self.designation.set("-")
        self.refresh()

    def _from_table(self, draw: bool = True) -> None:
        """Fill the boxes in from a designation."""
        found = section_table.find(self.designation.get())
        if found is None:
            if draw:
                self.refresh()
            return
        profile, dimensions = found
        self._filling = True
        try:
            if self.shape.get() != profile:
                self.shape.set(profile)
                self._shape_changed(draw=False)
            wanted = sections.PROFILES[profile][1]
            for name, value in zip(wanted, dimensions):
                self.dimensions[name].set(f"{value:g}")
        finally:
            self._filling = False
        if draw:
            self.refresh()

    # -- working it out -----------------------------------------------------
    def section(self):
        builder, wanted, _starting = sections.PROFILES[self.shape.get()]
        given = []
        for name in wanted:
            variable = self.dimensions.get(name)
            text = "" if variable is None else variable.get().strip()
            value = parse_number(text) if text else 0.0
            if value is None:
                raise ParseError(f"{name} is not a number.")
            given.append(float(value))
        told = self.designation.get()
        return builder(*given,
                       name=told if told and told != "-" else
                       self.shape.get())

    def draw(self) -> tuple:
        section = self.section()
        found = section.properties()

        force = parse_number(self.shear.get().strip() or "0")
        force = float(force or 0.0) * 1000.0        # kN to newtons

        self.figure.clear()
        if force:
            # Side by side, sharing the height axis, so the step in the
            # shear lines up with the flange it steps at.
            grid = self.figure.add_gridspec(1, 2, wspace=0.05,
                                            width_ratios=[1.0, 1.0])
            axes = self.figure.add_subplot(grid[0])
            self._draw_shear(self.figure.add_subplot(grid[1], sharey=axes),
                             section, force)
        else:
            axes = self.figure.add_subplot(111)
        self._draw_section(axes, section, found)

        rows = list(found.rows())
        self.stress = None
        moment = parse_number(self.moment.get().strip() or "0")
        if moment:
            # Millimetres in, kilonewton metres on the form, newtons per
            # square millimetre out - which is megapascals, and is the unit
            # every steel grade is quoted in.
            stress, at_x, at_y = section.worst_stress(
                float(moment) * self.N_MM_PER_KN_M)
            self.stress = (stress, at_x, at_y)
            rows.append(("largest bending stress", stress, "N/mm^2"))
            rows.append(("at", at_x - found.bounds[0],
                         f"mm from the left, {at_y - found.bounds[2]:g} mm "
                         f"up"))
        if force:
            worst, level = section.worst_shear(force)
            rows.append(("largest shear stress", worst, "N/mm^2"))
            rows.append(("at", level - found.bounds[2],
                         f"mm up, where the section is "
                         f"{section.width_at(level):.4g} mm wide"))
            rows.append(("average shear stress", force / found.area,
                         "N/mm^2"))
        return rows, self._notes(section, found, force)

    def layout(self) -> None:
        """Left to the gridspec when there are two panels.

        tight_layout will not lay out a grid that has been given its own
        spacing, and the two panels here want to sit close together - they
        share a height axis and reading across between them is the point.
        """
        if len(self.figure.axes) > 1:
            self.figure.subplots_adjust(left=0.08, right=0.97, top=0.93,
                                        bottom=0.12)
        else:
            self.figure.tight_layout()

    def _draw_shear(self, axes, section, force) -> None:
        """Nothing at the top and bottom, most at the neutral axis.

        The opposite way round from the bending stress, which is why a
        section checked for one has not been checked for the other.
        """
        levels, stresses = section.shear_profile(force)
        axes.plot(stresses, levels, color="#0b7a3b", linewidth=1.4)
        axes.fill_betweenx(levels, stresses, 0, color="#0b7a3b", alpha=0.15)
        axes.axvline(0, color="#888888", linewidth=0.8)
        axes.set_xlabel("shear stress  N/mm2", fontsize=8)
        axes.grid(True, alpha=0.25, linestyle=":")
        axes.tick_params(labelsize=7, labelleft=False)
        axes.set_title("shear", fontsize=8, color="#0b7a3b")

    def _notes(self, section, found, force=0.0) -> list:
        """What the numbers do not say on their own."""
        notes = []
        told = self.designation.get()
        if told and told != "-":
            notes.append(
                f"{told}: worked out from its dimensions, not looked up. "
                f"The table only fills the boxes in.")
        else:
            notes.append("Worked out from the dimensions as typed.")
        if abs(found.ixy) > 1e-9 * max(found.ixx, found.iyy, 1.0):
            _first, _second, turn = found.principal()
            notes.append(
                f"No axis of symmetry, so the stiff and weak axes are not "
                f"the ones drawn - they lie {turn:.1f} degrees round. "
                f"Bending it about x alone also bends it sideways, and the "
                f"stress is worked out with the term that says so rather "
                f"than by M y / I.")
        if force:
            worst, _level = section.worst_shear(force)
            average = force / found.area
            notes.append(
                f"The shear peaks at {abs(worst) / abs(average):.2f} times "
                f"its average, and where the bending stress is nothing. The "
                f"two never peak in the same place, so a section checked "
                f"for one has not been checked for the other.")
        if self.stress and abs(self.stress[0]) > self.YIELD:
            notes.append(
                f"{abs(self.stress[0]):.0f} N/mm2 is past the yield of "
                f"ordinary structural steel, so the elastic answer above "
                f"describes a section that is no longer elastic. The "
                f"arithmetic is right and the section is too small.")
        return notes

    # -- the drawing --------------------------------------------------------
    def _draw_section(self, axes, section, found) -> None:
        """The shape, to scale, with the centroid on it.

        The centroid is the one number on the list that can be checked by
        looking at it, which is reason enough to draw the thing.
        """
        # Painted in the order the parts are listed, each one over the last:
        # material in colour, holes in the background. That is the order the
        # section was built in, so a corner cut off the outside and put back
        # on the inside comes out the way it was meant to. Drawing all the
        # solids first and then all the holes gave a rounded tube with
        # square corners inside it.
        for part in section.parts:
            points = part.outline()
            axes.fill([px for px, _ in points], [py for _, py in points],
                      color="#1f4e79" if part.solid else "white",
                      zorder=2, linewidth=0)

        # Framed on the section, with the axes drawn long and left to the
        # view to cut them off. The other way round - fitting the view to
        # the lines - put a 100 mm angle in a 250 mm window.
        left, right, bottom, top = found.bounds
        span = max(right - left, top - bottom)
        pad = 0.14 * span
        reach = span * 1.5

        axes.plot([found.cx - reach, found.cx + reach],
                  [found.cy, found.cy], "--", color="#c0392b",
                  linewidth=0.9, zorder=4)
        axes.plot([found.cx, found.cx],
                  [found.cy - reach, found.cy + reach], "--",
                  color="#c0392b", linewidth=0.9, zorder=4)
        axes.plot([found.cx], [found.cy], marker="o", markersize=5,
                  color="#c0392b", zorder=5)
        # Labelled on whichever side of the centroid has more room.
        towards = 1 if (right - found.cx) > (found.cx - left) else -1
        axes.annotate(f"centroid\n{found.cx - left:.4g}, "
                      f"{found.cy - bottom:.4g} mm",
                      (found.cx, found.cy), textcoords="offset points",
                      xytext=(9 * towards, 9), fontsize=7, color="#c0392b",
                      ha="left" if towards > 0 else "right")

        if abs(found.ixy) > 1e-9 * max(found.ixx, found.iyy, 1.0):
            # Only drawn when they are somewhere else. On a symmetrical
            # section they lie along the axes already drawn, and a picture
            # that says a thing twice is saying nothing the second time.
            _first, _second, turn = found.principal()
            for offset in (0.0, 90.0):
                angle = math.radians(turn + offset)
                axes.plot(
                    [found.cx - reach * math.cos(angle),
                     found.cx + reach * math.cos(angle)],
                    [found.cy - reach * math.sin(angle),
                     found.cy + reach * math.sin(angle)],
                    "-.", color="#0b7a3b", linewidth=1.0, zorder=4)
            axes.annotate(f"principal axes, {turn:.1f} deg", (0.02, 0.02),
                          xycoords="axes fraction", fontsize=7,
                          color="#0b7a3b")

        axes.set_xlim(left - pad, right + pad)
        axes.set_ylim(bottom - pad, top + pad)
        axes.set_aspect("equal", adjustable="box")
        axes.set_xlabel("mm", fontsize=8)
        axes.grid(True, alpha=0.25, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.set_title(section.name, fontsize=9, color="#333333")


# --------------------------------------------------------------------------
class StageRow:
    """One stage of a movement: give any two of its four numbers.

    Which two is up to you, and that is the point. The stage a lift spends
    getting up to speed is described by a rate and a speed; the stage it
    spends at that speed is described by a distance; the stage it takes to
    stop is described by a rate and a speed again. Making people convert
    each of those into the same two would be work the program should do.
    """

    #: (name, label, unit, width) for the boxes, in the order they appear.
    BOXES = (("duration", "for", "s", 7),
             ("acceleration", "at", "m/s2", 7),
             ("end_velocity", "reaching", "m/s", 7),
             ("distance", "covering", "m", 7))

    def __init__(self, tab, parent, label="", duration="", acceleration="",
                 end_velocity="", distance=""):
        self.tab = tab
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=1)

        self.label = tk.StringVar(value=label)
        entry = ttk.Entry(self.frame, textvariable=self.label, width=12)
        entry.pack(side="left")
        self.label.trace_add("write", lambda *a: self.tab.refresh())

        given = {"duration": duration, "acceleration": acceleration,
                 "end_velocity": end_velocity, "distance": distance}
        for name, said, unit, width in self.BOXES:
            ttk.Label(self.frame, text=said).pack(side="left", padx=(8, 2))
            variable = tk.StringVar(value=given[name])
            box = ttk.Entry(self.frame, textvariable=variable, width=width,
                            font=MONO)
            box.pack(side="left")
            box.bind("<Return>", lambda e: self.tab.refresh())
            variable.trace_add("write", lambda *a: self.tab.refresh())
            ttk.Label(self.frame, text=unit,
                      style="Hint.TLabel").pack(side="left", padx=(2, 0))
            setattr(self, name, variable)

        ttk.Button(self.frame, text="Remove", width=7,
                   command=self.remove).pack(side="right")

    def remove(self) -> None:
        self.frame.destroy()
        if self in self.tab.stage_rows:
            self.tab.stage_rows.remove(self)
        self.tab.refresh()

    def _value(self, variable):
        text = variable.get().strip()
        if not text:
            return None
        value = parse_number(text)
        if value is None:
            raise ParseError(f"'{text}' is not a number.")
        return float(value)

    def phase(self):
        """The stage this row describes, or None if the row is empty."""
        given = {name: self._value(getattr(self, name))
                 for name, _said, _unit, _width in self.BOXES}
        if all(value is None for value in given.values()):
            return None
        return motion.Phase(label=self.label.get().strip(), **given)


# --------------------------------------------------------------------------
class MotionTab(ChartTab):
    """Distance, velocity and acceleration against time."""

    title = "Motion"
    hint = "one movement seen three ways, from the stages it goes through"

    #: The movement it starts on: up to speed, along, and stop. A lift, a
    #: conveyor, a machine axis - and the profile whose middle stage is the
    #: fiddly one to work out by hand.
    STARTING_STAGES = (
        dict(label="speeding up", acceleration="1.2", end_velocity="2"),
        dict(label="at speed", acceleration="0", distance="7.5"),
        dict(label="braking", acceleration="-0.8", end_velocity="0"),
    )

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        self.start_velocity = self.field(first, "Starting at", "0", "m/s")
        self.start_position = self.field(first, "from", "0", "m")
        ttk.Label(first,
                  text="Each stage takes any two of the four - the other "
                       "two are worked out.",
                  style="Hint.TLabel").pack(side="left", padx=(14, 0))

        self.stage_table = ScrollFrame(parent, height=92)
        self.stage_table.pack(fill="x", pady=(8, 0))
        self.stage_rows = []
        for spec in self.STARTING_STAGES:
            self.stage_rows.append(
                StageRow(self, self.stage_table.body, **spec))

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text="Add stage",
                   command=self.add_stage).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Speed up, run, stop",
                   command=self.trapezoid).pack(side="left")
        self.show_area = tk.BooleanVar(value=True)
        ttk.Checkbutton(buttons, text="Shade the area under v",
                        variable=self.show_area,
                        command=self.refresh).pack(side="right")

    def add_stage(self, **spec) -> None:
        self.stage_rows.append(
            StageRow(self, self.stage_table.body,
                     **(spec or dict(label="", duration="2",
                                     acceleration="0"))))
        self.refresh()

    def trapezoid(self) -> None:
        """Put the three-stage profile back, whatever is there now."""
        for row in list(self.stage_rows):
            row.frame.destroy()
        self.stage_rows = []
        self.start_velocity.set("0")
        for spec in self.STARTING_STAGES:
            self.stage_rows.append(
                StageRow(self, self.stage_table.body, **spec))
        self.refresh()

    def movement(self):
        phases = []
        for row in self.stage_rows:
            phase = row.phase()
            if phase is not None:
                phases.append(phase)
        return motion.Motion(
            phases=phases,
            start_velocity=self.number(self.start_velocity,
                                       "the starting velocity"),
            start_position=self.number(self.start_position,
                                       "where it starts"))

    def draw(self) -> tuple:
        run = self.movement()
        legs = run.legs()
        times, places, speeds, rates = run.trace()

        self.figure.clear()
        grid = self.figure.add_gridspec(3, 1, hspace=0.3)
        first = self.figure.add_subplot(grid[0])
        second = self.figure.add_subplot(grid[1], sharex=first)
        third = self.figure.add_subplot(grid[2], sharex=first)

        self._curve(first, times, places, "#1f4e79", "distance  m")
        self._curve(second, times, speeds, "#c0392b", "velocity  m/s")
        self._curve(third, times, rates, "#0b7a3b", "acceleration  m/s2",
                    step=True)
        if self.show_area.get():
            # The area under the velocity curve is the distance, which is
            # the one thing these three diagrams exist to say.
            second.fill_between(times, speeds, 0, color="#c0392b",
                                alpha=0.18)
        for axes in (first, second):
            axes.tick_params(labelbottom=False)
        third.set_xlabel("time  s", fontsize=8)

        # Where one stage becomes the next, on all three at once.
        for leg in legs[1:]:
            for axes in (first, second, third):
                axes.axvline(leg.start_time, color="#999999",
                             linewidth=0.7, linestyle=":")
        # Above the top panel rather than inside it. Written inside, a stage
        # named near the end of the run sat on top of a distance curve that
        # by then is near the top of its own axes.
        for leg in legs:
            if leg.duration > 0:
                first.annotate(leg.label,
                               (leg.start_time + leg.duration / 2.0, 1.04),
                               xycoords=("data", "axes fraction"),
                               fontsize=6.5, ha="center", va="bottom",
                               color="#666666")

        return run.rows(), run.notes()

    def _curve(self, axes, x, y, colour: str, label: str,
               step: bool = False) -> None:
        # Acceleration is constant within a stage and jumps between them, so
        # it is drawn as the steps it is. Joined up it would slope through
        # the jump and say the opposite of what happened.
        axes.plot(x, y, color=colour, linewidth=1.5,
                  drawstyle="steps-post" if step else "default")
        axes.axhline(0, color="#888888", linewidth=0.8)
        _sideways_label(axes, label)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)

    def layout(self) -> None:
        # Room at the top for the stage names, which sit above the first
        # panel where nothing else is, and at the left for the labels.
        self.figure.subplots_adjust(left=0.155, right=0.98, top=0.93,
                                    bottom=0.11)


# --------------------------------------------------------------------------
class TorsionTab(ChartTab):
    """Shear stress and angle of twist in a round shaft."""

    title = "Torsion"
    hint = "shear stress and twist in a shaft, from the torque or the power"

    #: How the torque is known. Usually it is not - it is a motor rating.
    BY_TORQUE, BY_POWER = "a torque", "power at a speed"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        self.outer = self.field(first, "Outside dia", "30", "mm")
        self.bore = self.field(first, "bore", "0", "mm")
        self.length = self.field(first, "Length", "1", "m")
        self.modulus = self.field(first, "G", "80", "GPa")

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        ttk.Label(second, text="Driven by").pack(side="left")
        self.driven = tk.StringVar(value=self.BY_POWER)
        box = ttk.Combobox(second, state="readonly", width=15,
                           textvariable=self.driven,
                           values=[self.BY_TORQUE, self.BY_POWER])
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.torque = self.field(second, "Torque", "500", "N m")
        self.power = self.field(second, "Power", "15", "kW")
        self.speed = self.field(second, "at", "1450", "rev/min")
        self.allowable = self.field(second, "Allowable", "60", "N/mm2")

    def shaft(self):
        outer = self.number(self.outer, "the outside diameter") / 1000.0
        bore = self.number(self.bore, "the bore") / 1000.0
        if self.driven.get() == self.BY_POWER:
            torque = torsion.torque_from_power(
                self.number(self.power, "the power") * 1000.0,
                self.number(self.speed, "the speed"))
        else:
            torque = self.number(self.torque, "the torque")
        return torsion.Shaft(
            outer=outer, inner=bore,
            length=self.number(self.length, "the length"),
            modulus=self.number(self.modulus, "the modulus") * 1e9,
            torque=torque,
            allowable=self.number(self.allowable, "the allowable stress")
            * 1e6)

    def draw(self) -> tuple:
        shaft = self.shaft()
        rows = list(shaft.rows())
        notes = list(shaft.notes())

        # The torque is worth showing when it was worked out rather than
        # typed, since it is the number every other answer came from.
        if self.driven.get() == self.BY_POWER:
            rows.insert(0, ("torque", shaft.torque, "N m"))
        else:
            rows.insert(0, ("power at " + self.speed.get() + " rev/min",
                            torsion.power_from_torque(
                                shaft.torque,
                                self.number(self.speed, "the speed"))
                            / 1000.0, "kW"))

        # What it would have to be, which is the question behind the answer.
        if shaft.allowable > 0:
            needed = torsion.diameter_for_stress(
                shaft.torque, shaft.allowable,
                shaft.inner / shaft.outer if shaft.outer else 0.0)
            rows.append(("smallest diameter for that stress", needed * 1000.0,
                         "mm"))

        self.figure.clear()
        grid = self.figure.add_gridspec(2, 1, hspace=0.12,
                                        height_ratios=[0.7, 1.3])
        section = self.figure.add_subplot(grid[0])
        stress = self.figure.add_subplot(grid[1], sharex=section)
        self._draw_section(section, shaft)
        self._draw_stress(stress, shaft)
        return rows, notes

    def _draw_section(self, axes, shaft) -> None:
        """The shaft cut across a diameter, above the stress it carries."""
        outer = shaft.outer / 2.0 * 1000.0
        inner = shaft.inner / 2.0 * 1000.0
        for side in (-1.0, 1.0):
            axes.add_patch(Rectangle(
                (side * inner if side > 0 else -outer, -1.0),
                outer - inner, 2.0, facecolor="#1f4e79", edgecolor="none"))
        axes.axvline(0, color="#888888", linewidth=0.8, linestyle="--")
        if inner > 0:
            axes.annotate("bore", (0, 0), fontsize=6.5, ha="center",
                          va="center", color="#666666")
        axes.set_ylim(-1.6, 1.6)
        axes.set_yticks([])
        axes.tick_params(labelbottom=False, length=0)
        for edge in ("left", "right", "top", "bottom"):
            axes.spines[edge].set_visible(False)
        _sideways_label(axes, "the shaft")

    def _draw_stress(self, axes, shaft) -> None:
        """Nothing at the centre, most at the surface, straight between.

        Drawn across the whole diameter with the sign turning over, because
        that is the picture: the two halves of a twisted shaft are sheared
        in opposite directions.
        """
        radii, stresses = shaft.profile()
        # The two sides drawn separately. Joined up, the line runs
        # straight across the bore - through the middle of a hole,
        # where there is no metal and no stress to draw.
        for side in (1.0, -1.0):
            across = [side * r * 1000.0 for r in radii]
            values = [side * v / 1e6 for v in stresses]
            axes.plot(across, values, color="#c0392b", linewidth=1.6)
            axes.fill_between(across, values, 0, color="#c0392b",
                              alpha=0.15)
        axes.axhline(0, color="#888888", linewidth=0.8)
        if shaft.allowable > 0:
            for side in (1, -1):
                axes.axhline(side * shaft.allowable / 1e6, color="#0b7a3b",
                             linewidth=0.9, linestyle=":")
            axes.annotate("allowable", (0.985, shaft.allowable / 1e6),
                          xycoords=("axes fraction", "data"), fontsize=6.5,
                          ha="right", va="bottom", color="#0b7a3b")
        axes.set_xlabel("distance from the axis  mm", fontsize=8)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        _sideways_label(axes, "shear stress  N/mm2")

    def layout(self) -> None:
        self.figure.subplots_adjust(left=0.19, right=0.97, top=0.97,
                                    bottom=0.14)


# --------------------------------------------------------------------------
class ColumnTab(ChartTab):
    """What a strut will carry before it bends sideways."""

    title = "Columns"
    hint = "buckling: Euler, yield, and the curve real columns follow"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        ttk.Label(first, text="Section").pack(side="left")
        self.section_name = tk.StringVar(value="203x203x46 UC")
        chooser = ttk.Combobox(first, state="readonly", width=17,
                               textvariable=self.section_name,
                               values=([FROM_SECTION_TAB]
                                       + section_table.names()))
        chooser.pack(side="left", padx=(4, 14))
        chooser.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.length = self.field(first, "Length", "4", "m")
        ttk.Label(first, text="Held").pack(side="left")
        self.ends = tk.StringVar(value="pinned both ends")
        box = ttk.Combobox(first, state="readonly", width=28,
                           textvariable=self.ends,
                           values=list(buckling.END_CONDITIONS))
        box.pack(side="left", padx=(4, 0))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        self.material = material_picker(self, second)
        self.modulus = self.field(second, "E", "210", "GPa")
        self.yield_stress = self.field(second, "Yield", "275", "N/mm2")
        self.load = self.field(second, "Carrying", "900", "kN")
        self.about = ttk.Label(second, text="", style="Hint.TLabel")
        self.about.pack(side="left", padx=(10, 0))

    def take_material(self) -> None:
        """Fill the modulus and the yield stress from the material picked."""
        material = materials.find(self.material.get())
        if material is None:
            return
        if material.has("youngs"):
            self.modulus.set(f"{material.typical('youngs'):.6g}")
        if material.has("yield"):
            self.yield_stress.set(f"{material.typical('yield'):.6g}")
        self.refresh()

    def linked(self, charts: dict) -> None:
        self.section_tab = charts.get("Section")

    def section(self):
        chosen = self.section_name.get()
        if chosen == FROM_SECTION_TAB:
            beside = getattr(self, "section_tab", None)
            if beside is None:
                raise ParseError("There is no Section tab to take one from.")
            return beside.section()
        return section_table.build(chosen)

    def column(self):
        section = self.section()
        found = section.properties()
        # A column bends about whichever axis is easiest, and that is the
        # smaller *principal* second moment - not the smaller of Ixx and
        # Iyy. On an angle those are not the same thing and the weak axis
        # is nowhere near either leg.
        _stiff, weak, turn = found.principal()
        self.about.configure(
            text=f"buckles about the weak axis, I = {weak / 1e4:.0f} cm4"
                 + (f", {turn:.0f} deg round" if abs(turn) > 0.5 else ""))
        return buckling.Column(
            area=found.area, second_moment=weak,
            length=self.number(self.length, "the length") * 1000.0,
            modulus=self.number(self.modulus, "the modulus") * 1000.0,
            yield_stress=self.number(self.yield_stress, "the yield stress"),
            ends=self.ends.get(),
            load=self.number(self.load, "the load") * 1000.0)

    def draw(self) -> tuple:
        column = self.column()
        rows = list(column.rows())

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        ratios, euler, yielding, perry = column.curve()
        top = column.yield_stress * 1.35
        axes.plot(ratios, [min(v, top * 4) for v in euler], "--",
                  color="#888888", linewidth=1.2, label="Euler")
        axes.plot(ratios, yielding, ":", color="#c0392b", linewidth=1.2,
                  label="yield")
        axes.plot(ratios, perry, color="#1f4e79", linewidth=1.8,
                  label="Perry-Robertson")
        axes.axvline(column.transition, color="#0b7a3b", linewidth=0.9,
                     linestyle="-.")
        # Low down, where neither curve is: the point being marked is on
        # the x axis and the top of the chart is where the labels for the
        # column itself go.
        axes.annotate("Euler reaches yield here",
                      (column.transition, top * 0.04), fontsize=6.5,
                      rotation=90, ha="right", va="bottom", color="#0b7a3b")

        here = column.perry_stress()
        axes.plot([column.slenderness], [here], "o", color="#c0392b",
                  markersize=8, zorder=5)
        axes.annotate(f"this column\n{here:.0f} N/mm2",
                      (column.slenderness, here),
                      textcoords="offset points", xytext=(8, 8),
                      fontsize=7, color="#c0392b")

        axes.set_xlim(0, max(ratios))
        axes.set_ylim(0, top)
        axes.set_xlabel("slenderness  Le / r", fontsize=8)
        axes.set_ylabel("stress it fails at  N/mm2", fontsize=8)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.legend(loc="upper right", fontsize=7, framealpha=0.9)
        return rows, column.notes()


# --------------------------------------------------------------------------
class VesselTab(ChartTab):
    """A cylinder or a sphere under pressure."""

    title = "Pressure vessel"
    hint = "hoop and radial stress, thin walled and thick"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        self.shape = tk.StringVar(value="cylinder")
        ttk.Label(first, text="Shape").pack(side="left")
        box = ttk.Combobox(first, state="readonly", width=10,
                           textvariable=self.shape,
                           values=["cylinder", "sphere"])
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.bore = self.field(first, "Bore radius", "500", "mm")
        self.wall = self.field(first, "wall", "10", "mm")
        self.pressure = self.field(first, "Pressure", "2", "N/mm2")
        self.outside = self.field(first, "outside", "0", "N/mm2")

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        self.yield_stress = self.field(second, "Yield", "275", "N/mm2")
        self.closed = tk.BooleanVar(value=True)
        ttk.Checkbutton(second, text="closed ends carry the pressure",
                        variable=self.closed,
                        command=self.refresh).pack(side="left", padx=(6, 0))

    def vessel(self):
        return vessels.Vessel(
            inner_radius=self.number(self.bore, "the bore"),
            thickness=self.number(self.wall, "the wall"),
            pressure=self.number(self.pressure, "the pressure"),
            outside_pressure=self.number(self.outside,
                                         "the outside pressure"),
            shape=self.shape.get(), closed=self.closed.get(),
            yield_stress=self.number(self.yield_stress, "the yield stress"))

    def draw(self) -> tuple:
        vessel = self.vessel()
        rows = list(vessel.rows())

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        radii, hoop, radial = vessel.profile()
        axes.plot(radii, hoop, color="#1f4e79", linewidth=1.6,
                  label="hoop, Lame")
        axes.plot(radii, radial, color="#0b7a3b", linewidth=1.4,
                  label="radial, Lame")
        axes.axhline(vessel.thin_hoop, color="#c0392b", linestyle="--",
                     linewidth=1.1, label="hoop, thin walled")
        if vessel.shape == "cylinder" and vessel.closed:
            axes.axhline(vessel.along, color="#8a4fbf", linestyle=":",
                         linewidth=1.1, label="along the axis")
        axes.axhline(0, color="#bbbbbb", linewidth=0.7)
        axes.set_xlabel("radius  mm", fontsize=8)
        axes.set_ylabel("stress  N/mm2", fontsize=8)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.legend(loc="best", fontsize=7, framealpha=0.85)
        return rows, vessel.notes()


# --------------------------------------------------------------------------
class TrussTab(ChartTab):
    """A pin-jointed frame, solved at every joint at once."""

    title = "Truss"
    hint = "member forces in a pin-jointed frame, written down as text"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        ttk.Label(first, text="Warren girder:").pack(side="left")
        self.bays = self.field(first, "bays", "4", "", width=4)
        self.span = self.field(first, "bay", "2", "m", width=5)
        self.height = self.field(first, "deep", "1.5", "m", width=5)
        self.point = self.field(first, "load at each bottom joint", "20",
                                "kN", width=5)
        ttk.Button(first, text="Put one in the box",
                   command=self.make_warren).pack(side="left", padx=(10, 0))

        ttk.Label(parent, style="Hint.TLabel", justify="left",
                  text="One thing per line: `node x y [pin|roller]`, "
                       "`member first second`, `load joint across up`. "
                       "Joints are numbered from one, in the order they "
                       "are written.").pack(fill="x", pady=(6, 2))

        self.text = tk.Text(parent, height=8, font=MONO, wrap="none")
        self.text.pack(fill="x")
        self.text.bind("<KeyRelease>", lambda e: self.refresh())
        self.make_warren(draw=False)

    def make_warren(self, draw: bool = True) -> None:
        """Put a girder in the box, since a blank one is hard to start."""
        try:
            frame = trusses.warren(
                int(self.number(self.bays, "the bays")),
                self.number(self.span, "the bay width") * 1000.0,
                self.number(self.height, "the depth") * 1000.0,
                self.number(self.point, "the load") * 1000.0)
        except Exception:                                  # noqa: BLE001
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", trusses.as_text(frame))
        if draw:
            self.refresh()

    def draw(self) -> tuple:
        frame = trusses.parse(self.text.get("1.0", "end"))
        found = frame.solve()

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        biggest = max(found.biggest, 1.0)
        for index, member in enumerate(frame.members):
            start, end = frame.nodes[member.start], frame.nodes[member.end]
            force = found.forces[index]
            # Red pulls, blue pushes, and the thickness says how hard - so
            # the way the frame carries its load is visible before any of
            # the numbers are read.
            colour = ("#bbbbbb" if abs(force) <= 1e-9 * biggest
                      else "#c0392b" if force > 0 else "#1f4e79")
            axes.plot([start.x, end.x], [start.y, end.y], color=colour,
                      linewidth=0.8 + 3.2 * abs(force) / biggest, zorder=2)
            axes.annotate(f"{force / 1000.0:.0f}",
                          ((start.x + end.x) / 2, (start.y + end.y) / 2),
                          fontsize=6, ha="center", va="center",
                          color=colour, zorder=4,
                          bbox=dict(boxstyle="round,pad=0.1", fc="white",
                                    ec="none", alpha=0.75))

        for index, node in enumerate(frame.nodes):
            axes.plot([node.x], [node.y], "o", color="#333333",
                      markersize=4, zorder=5)
            axes.annotate(str(index + 1), (node.x, node.y),
                          textcoords="offset points", xytext=(4, 4),
                          fontsize=6, color="#666666")
            if node.support != "free":
                axes.plot([node.x], [node.y], marker="^", markersize=10,
                          color="#0b7a3b", zorder=4)
        for load in frame.loads:
            node = frame.nodes[load.node]
            size = math.hypot(load.across, load.up)
            if size:
                axes.annotate(
                    "", xy=(node.x, node.y),
                    xytext=(-load.across / size * 26.0,
                            -load.up / size * 26.0),
                    textcoords="offset points",
                    arrowprops=dict(arrowstyle="-|>", color="#8a4fbf",
                                    linewidth=1.4, shrinkA=0, shrinkB=0))

        axes.set_aspect("equal", adjustable="datalim")
        axes.set_xlabel("mm", fontsize=8)
        axes.grid(True, alpha=0.2, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.set_title("red pulls, blue pushes, thickness is how hard",
                       fontsize=7.5, color="#666666")
        return found.rows(), found.notes()


# --------------------------------------------------------------------------
class MaterialsTab(ChartTab):
    """Two properties against each other, with a selection line on them."""

    title = "Material chart"
    hint = "properties on log axes, with a performance index laid across"

    NO_INDEX = "none - just the chart"

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        labels = {key: name for key, (name, _u, _k)
                  in materials.PROPERTIES.items()}
        self._label_to_key = {name: key for key, name in labels.items()}
        choices = sorted(labels.values())

        ttk.Label(first, text="Across").pack(side="left")
        self.across = tk.StringVar(value=labels["density"])
        for variable, default in ((self.across, labels["density"]),):
            box = ttk.Combobox(first, state="readonly", width=26,
                               textvariable=variable, values=choices)
            box.pack(side="left", padx=(4, 14))
            box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(first, text="up").pack(side="left")
        self.up = tk.StringVar(value=labels["youngs"])
        box = ttk.Combobox(first, state="readonly", width=26,
                           textvariable=self.up, values=choices)
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        self.level = tk.StringVar(value="classes")
        for text in ("classes", "grades", "both"):
            ttk.Radiobutton(first, text=text, value=text,
                            variable=self.level,
                            command=self.refresh).pack(side="left", padx=2)

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        ttk.Label(second, text="Index").pack(side="left")
        self.index = tk.StringVar(value=materials.INDICES[1][0])
        box = ttk.Combobox(second, state="readonly", width=34,
                           textvariable=self.index,
                           values=[self.NO_INDEX]
                                  + [i[0] for i in materials.INDICES])
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self._index_changed())
        ttk.Label(second, text="line through").pack(side="left")
        self.through = tk.StringVar(value="Carbon steel")
        self.through_box = ttk.Combobox(second, state="readonly", width=26,
                                        textvariable=self.through,
                                        values=materials.names())
        self.through_box.pack(side="left", padx=(4, 0))
        self.through_box.bind("<<ComboboxSelected>>",
                              lambda e: self.refresh())
        self.written = ttk.Label(second, text="", style="Hint.TLabel")
        self.written.pack(side="left", padx=(12, 0))

    def _index_changed(self) -> None:
        """Picking an index sets the two axes it is about."""
        found = self._index()
        if found:
            labels = {key: name for key, (name, _u, _k)
                      in materials.PROPERTIES.items()}
            self.across.set(labels[found[1]])
            self.up.set(labels[found[2]])
        self.refresh()

    def _index(self):
        for entry in materials.INDICES:
            if entry[0] == self.index.get():
                return entry
        return None

    def _keys(self) -> tuple:
        return (self._label_to_key[self.across.get()],
                self._label_to_key[self.up.get()])

    def _wanted(self) -> list:
        across, up = self._keys()
        grades = {"classes": False, "grades": True}.get(self.level.get())
        return [material for material in materials.all_materials()
                if material.has(across) and material.has(up)
                and (grades is None or material.grade == grades)]

    def draw(self) -> tuple:
        across, up = self._keys()
        shown = self._wanted()
        if not shown:
            raise ParseError(
                f"Nothing here records both {self.across.get().lower()} and "
                f"{self.up.get().lower()}.")

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        self._labels = []
        for material in shown:
            self._bubble(axes, material, across, up)

        index = self._index()
        self.written.configure(text=index[5] if index else "")
        rows = []
        if index and index[1] == across and index[2] == up:
            rows = self._draw_index(axes, index, shown)

        axes.set_xscale("log")
        axes.set_yscale("log")
        axes.set_xlabel(f"{self.across.get()}  "
                        f"{materials.PROPERTIES[across][1]}", fontsize=8)
        axes.set_ylabel(f"{self.up.get()}  "
                        f"{materials.PROPERTIES[up][1]}", fontsize=8)
        axes.grid(True, which="both", alpha=0.25, linestyle=":")
        axes.tick_params(labelsize=7)
        # The names are placed last, because where they overlap depends on
        # the axes, and the axes are not settled until everything is on.
        axes.autoscale_view()
        self._spread_labels(axes)
        handles = [Line2D([], [], color=colour, linewidth=6, alpha=0.5,
                          label=family)
                   for family, colour in materials.FAMILIES.items()
                   if any(m.family == family for m in shown)]
        axes.legend(handles=handles, loc="lower right", fontsize=6.5,
                    framealpha=0.85)
        return rows, self._notes(shown, across, up)

    def _bubble(self, axes, material, across, up) -> None:
        """One material, as the range it actually covers.

        A box rather than a point, because the range is the information. A
        material that draws long in one direction is one whose grade has to
        be pinned down before the number is used.
        """
        low_x, high_x = material.span(across)
        low_y, high_y = material.span(up)
        # A property that does not move would draw as a line of no width,
        # so it is given a little - which still reads as "this one is
        # fixed" beside a neighbour three decades long.
        low_x, high_x = low_x * 0.98, high_x * 1.02
        low_y, high_y = low_y * 0.98, high_y * 1.02
        colour = materials.FAMILIES.get(material.family, "#666666")
        axes.add_patch(Rectangle(
            (low_x, low_y), high_x - low_x, high_y - low_y,
            facecolor=colour, edgecolor=colour, alpha=0.30, linewidth=1.0))
        self._labels.append((material.name, (low_x * high_x) ** 0.5,
                             (low_y * high_y) ** 0.5, colour))

    #: How big a label is allowed to look, in points.
    LABEL_POINTS = 5.5

    def _spread_labels(self, axes) -> None:
        """Move the names apart until they can all be read.

        Metals genuinely cluster in the top corner of a modulus against
        density chart - that is the fact the chart exists to show - so the
        names land on top of each other and none of them can be read. They
        are pushed apart here in screen space rather than in data space,
        because overlapping is a screen fact and has nothing to do with the
        units; and each one that moves keeps a thin line back to the box it
        belongs to, so nudging a name never reassigns it.
        """
        if not self._labels:
            return
        to_screen = axes.transData.transform
        to_data = axes.transData.inverted().transform
        wide = self.LABEL_POINTS * self.figure.dpi / 72.0
        placed = [list(to_screen((x, y))) for _n, x, y, _c in self._labels]
        anchors = [tuple(spot) for spot in placed]
        sizes = [(0.56 * wide * len(name) + 2.0, wide + 2.0)
                 for name, _x, _y, _c in self._labels]

        for _pass in range(60):
            moved = False
            for i in range(len(placed)):
                for j in range(i + 1, len(placed)):
                    across = abs(placed[i][0] - placed[j][0])
                    up = abs(placed[i][1] - placed[j][1])
                    room_x = (sizes[i][0] + sizes[j][0]) / 2.0
                    room_y = (sizes[i][1] + sizes[j][1]) / 2.0
                    if across >= room_x or up >= room_y:
                        continue
                    # Push along whichever axis needs the least movement,
                    # so a name travels the shortest distance from the
                    # material it names.
                    short_x, short_y = room_x - across, room_y - up
                    if short_y <= short_x * (room_y / room_x):
                        step = short_y / 2.0 + 0.5
                        way = 1.0 if placed[i][1] >= placed[j][1] else -1.0
                        placed[i][1] += step * way
                        placed[j][1] -= step * way
                    else:
                        step = short_x / 2.0 + 0.5
                        way = 1.0 if placed[i][0] >= placed[j][0] else -1.0
                        placed[i][0] += step * way
                        placed[j][0] -= step * way
                    moved = True
            if not moved:
                break

        for (name, _x, _y, colour), spot, anchor in zip(
                self._labels, placed, anchors):
            at = to_data(spot)
            gone = math.hypot(spot[0] - anchor[0], spot[1] - anchor[1])
            if gone > wide:
                start = to_data(anchor)
                axes.plot([start[0], at[0]], [start[1], at[1]],
                          color=colour, linewidth=0.4, alpha=0.55,
                          zorder=2)
            axes.annotate(name, at, fontsize=self.LABEL_POINTS, ha="center",
                          va="center", color=colour, zorder=3)

    def _draw_index(self, axes, index, shown) -> list:
        """The straight edge, and what is above it."""
        across, up = self._keys()
        through = materials.find(self.through.get())
        if through is None or not (through.has(across) and through.has(up)):
            through = max(shown,
                          key=lambda m: materials.index_value(m, index))
            self.through.set(through.name)

        span = (min(m.span(across)[0] for m in shown) * 0.6,
                max(m.span(across)[1] for m in shown) * 1.6)
        line_x, line_y = materials.guideline(index, through, span)
        axes.plot(line_x, line_y, "--", color="#333333", linewidth=1.3)
        axes.annotate(f"{index[5]}  -  better above",
                      (line_x[1], line_y[1]), fontsize=6.5, ha="right",
                      va="bottom", color="#333333")

        wanted = materials.index_value(through, index)
        rows = [("index", index[5], ""),
                ("line through", through.name, ""),
                ("its value", wanted, "")]
        better = [(value, material) for value, material
                  in materials.ranked(index)
                  if material in shown and value >= wanted]
        for value, material in better[:14]:
            rows.append((material.name, value / wanted,
                         "times better" if material is not through
                         else "the line"))
        return rows

    def _notes(self, shown, across, up) -> list:
        said = [f"{len(shown)} materials, each drawn as the range it "
                f"covers. A long box is a material whose grade has to be "
                f"pinned down before the number is used."]
        widest = max(shown, key=lambda m: m.spread(up))
        if widest.spread(up) > 3:
            said.append(
                f"{widest.name} spans a factor of "
                f"{widest.spread(up):.0f} in {self.up.get().lower()} - "
                f"which is what processing does to it, and why the class "
                f"is a range and a grade is not.")
        return said


# --------------------------------------------------------------------------
class GeometryTab(ChartTab):
    """Triangles, arcs and crossings - drawn, and solved from a few parts.

    Section properties live on the Section tab; this is the setting-out
    side of geometry, where the question is what the shape is rather than
    what it does.
    """

    title = "Geometry"
    hint = "solve a triangle, an arc, or where two things cross"

    PROBLEMS = ("Triangle", "Arc", "Two lines", "Line and circle",
                "Two circles", "Tangents from a point",
                "Circle through three points")

    def build_form(self, parent) -> None:
        first = ttk.Frame(parent)
        first.pack(fill="x")
        ttk.Label(first, text="Problem").pack(side="left")
        self.problem = tk.StringVar(value=self.PROBLEMS[0])
        box = ttk.Combobox(first, state="readonly", width=26,
                           textvariable=self.problem, values=self.PROBLEMS)
        box.pack(side="left", padx=(4, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self._problem_changed())

        self.forms = {}
        holder = ttk.Frame(parent)
        holder.pack(fill="x", pady=(6, 0))
        self.form_holder = holder

        # -- the triangle: any three of the six, the rest left empty ------
        frame = ttk.Frame(holder)
        self.forms["Triangle"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.side_a = self.field(top, "a", "3")
        self.side_b = self.field(top, "b", "4")
        self.side_c = self.field(top, "c", "5")
        self.angle_A = self.field(top, "A", "", "deg")
        self.angle_B = self.field(top, "B", "", "deg")
        self.angle_C = self.field(top, "C", "", "deg")
        ttk.Label(top, text="fill any three - a capital angle faces the "
                            "small side of the same letter",
                  style="Hint.TLabel").pack(side="left", padx=(6, 0))

        # -- the arc: any two of the five --------------------------------
        frame = ttk.Frame(holder)
        self.forms["Arc"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.arc_R = self.field(top, "radius", "")
        self.arc_theta = self.field(top, "angle", "", "deg")
        self.arc_L = self.field(top, "arc length", "")
        self.arc_chord = self.field(top, "chord", "2000")
        self.arc_rise = self.field(top, "rise", "250")
        ttk.Label(top, text="fill any two", style="Hint.TLabel").pack(
            side="left", padx=(6, 0))

        # -- two lines ---------------------------------------------------
        frame = ttk.Frame(holder)
        self.forms["Two lines"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="first through").pack(side="left", padx=(0, 6))
        self.line1 = [self.field(top, name, value, width=8) for name, value
                      in (("x1", "0"), ("y1", "0"), ("x2", "10"),
                          ("y2", "10"))]
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(4, 0))
        ttk.Label(bottom, text="second through").pack(side="left", padx=(0, 6))
        self.line2 = [self.field(bottom, name, value, width=8) for name, value
                      in (("x1", "0"), ("y1", "10"), ("x2", "10"),
                          ("y2", "0"))]

        # -- a line and a circle -----------------------------------------
        frame = ttk.Frame(holder)
        self.forms["Line and circle"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="line through").pack(side="left", padx=(0, 6))
        self.lc_line = [self.field(top, name, value, width=8) for name, value
                        in (("x1", "-10"), ("y1", "3"), ("x2", "10"),
                            ("y2", "3"))]
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(4, 0))
        ttk.Label(bottom, text="circle at").pack(side="left", padx=(0, 6))
        self.lc_circle = [self.field(bottom, name, value, width=8)
                          for name, value in (("x", "0"), ("y", "0"))]
        self.lc_radius = self.field(bottom, "radius", "5", width=8)

        # -- two circles --------------------------------------------------
        frame = ttk.Frame(holder)
        self.forms["Two circles"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="first at").pack(side="left", padx=(0, 6))
        self.cc_one = [self.field(top, name, value, width=8) for name, value
                       in (("x", "0"), ("y", "0"))]
        self.cc_one_r = self.field(top, "radius", "5", width=8)
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(4, 0))
        ttk.Label(bottom, text="second at").pack(side="left", padx=(0, 6))
        self.cc_two = [self.field(bottom, name, value, width=8)
                       for name, value in (("x", "8"), ("y", "0"))]
        self.cc_two_r = self.field(bottom, "radius", "5", width=8)

        # -- tangents from a point ---------------------------------------
        frame = ttk.Frame(holder)
        self.forms["Tangents from a point"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="from").pack(side="left", padx=(0, 6))
        self.tan_point = [self.field(top, name, value, width=8)
                          for name, value in (("x", "10"), ("y", "0"))]
        ttk.Label(top, text="to the circle at").pack(side="left", padx=(6, 6))
        self.tan_centre = [self.field(top, name, value, width=8)
                           for name, value in (("x", "0"), ("y", "0"))]
        self.tan_radius = self.field(top, "radius", "6", width=8)

        # -- the circle through three points -----------------------------
        frame = ttk.Frame(holder)
        self.forms["Circle through three points"] = frame
        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.three = []
        for n, (x, y) in enumerate((("0", "0"), ("10", "0"), ("0", "10")),
                                   start=1):
            ttk.Label(top, text=f"point {n}").pack(side="left", padx=(0, 4))
            self.three.append([self.field(top, "x", x, width=8),
                               self.field(top, "y", y, width=8)])

        self._problem_changed()

    def _problem_changed(self) -> None:
        for name, frame in self.forms.items():
            frame.pack_forget()
        self.forms[self.problem.get()].pack(fill="x")
        self.refresh()

    # -- reading the form --------------------------------------------------
    def _maybe(self, variable) -> float | None:
        """A number, or None where the box was left empty on purpose."""
        text = variable.get().strip()
        if not text:
            return None
        value = parse_number(text)
        if value is None:
            raise ParseError(f"{text!r} is not a number.")
        return float(value)

    def _point(self, pair) -> tuple:
        return (self.number(pair[0], "x"), self.number(pair[1], "y"))

    def _line(self, four) -> tuple:
        return geometry.line_through(
            (self.number(four[0], "x1"), self.number(four[1], "y1")),
            (self.number(four[2], "x2"), self.number(four[3], "y2")))

    # -- drawing -----------------------------------------------------------
    def draw(self) -> tuple:
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        # A circle has to look like a circle and a right angle like a right
        # angle, or the drawing is telling a different story from the
        # numbers beside it.
        self.axes.set_aspect("equal", adjustable="datalim")
        self.axes.grid(True, alpha=0.25, linestyle=":")
        self.axes.tick_params(labelsize=7)
        return getattr(self, "_draw_" + _slug(self.problem.get()))()

    def layout(self) -> None:
        self.figure.tight_layout()

    # -- triangles ---------------------------------------------------------
    def _draw_triangle(self) -> tuple:
        given = {}
        for name, variable in (("a", self.side_a), ("b", self.side_b),
                               ("c", self.side_c)):
            value = self._maybe(variable)
            if value is not None:
                given[name] = value
        for name, variable in (("A", self.angle_A), ("B", self.angle_B),
                               ("C", self.angle_C)):
            value = self._maybe(variable)
            if value is not None:
                given[name] = math.radians(value)

        found = geometry.solve_triangle(given)
        rows = []
        for n, triangle in enumerate(found):
            self._one_triangle(triangle, n, len(found))
            if len(found) > 1:
                rows.append((f"-- the {triangle.which} one --", "", ""))
            rows.extend(triangle.rows())

        notes = []
        if len(found) > 1:
            notes.append(geometry.why_ambiguous(given))
        else:
            shape = [word for word, yes in
                     (("right angled", found[0].right_angled),
                      ("obtuse", found[0].obtuse),
                      ("isosceles", found[0].isosceles)) if yes]
            if shape:
                notes.append("It is " + " and ".join(shape) + ".")
        return rows, notes

    def _one_triangle(self, triangle, n: int, of: int) -> None:
        corners = triangle.corners()
        colour = "#1f4e79" if n == 0 else "#c00000"
        closed = corners + [corners[0]]
        self.axes.plot([x for x, _y in closed], [y for _x, y in closed],
                       color=colour, linewidth=1.6,
                       linestyle="-" if n == 0 else "--",
                       label=triangle.which or None)
        self.axes.fill([x for x, _y in corners], [y for _x, y in corners],
                       color=colour, alpha=0.08)
        # The vertex letters, pushed out from the middle so they do not sit
        # on the lines they belong to.
        middle = (sum(x for x, _y in corners) / 3.0,
                  sum(y for _x, y in corners) / 3.0)
        size = max(triangle.a, triangle.b, triangle.c)
        for letter, (x, y) in zip("ABC", corners):
            away = math.hypot(x - middle[0], y - middle[1]) or 1.0
            self.axes.annotate(
                letter, (x + (x - middle[0]) / away * size * 0.06,
                         y + (y - middle[1]) / away * size * 0.06),
                fontsize=8, ha="center", va="center", color=colour)
        # And the side lengths at the midpoints of the sides they measure.
        for name, (one, other) in zip("cab", ((0, 1), (1, 2), (2, 0))):
            if of > 1 and n == 1:
                continue
            x = 0.5 * (corners[one][0] + corners[other][0])
            y = 0.5 * (corners[one][1] + corners[other][1])
            self.axes.annotate(f"{name} = {getattr(triangle, name):.4g}",
                               (x, y), fontsize=6.5, ha="center",
                               va="center", color="#333333",
                               bbox=dict(boxstyle="round,pad=0.15",
                                         facecolor="white", alpha=0.75,
                                         edgecolor="none"))
        if of > 1:
            self.axes.legend(loc="upper right", fontsize=7)

    # -- arcs --------------------------------------------------------------
    def _draw_arc(self) -> tuple:
        given = {"R": self._maybe(self.arc_R),
                 "L": self._maybe(self.arc_L),
                 "chord": self._maybe(self.arc_chord),
                 "rise": self._maybe(self.arc_rise)}
        angle = self._maybe(self.arc_theta)
        if angle is not None:
            given["theta"] = math.radians(angle)

        found = geometry.solve_arc(given)
        rows = []
        for n, arc in enumerate(found):
            self._one_arc(arc, n)
            if len(found) > 1:
                rows.append((f"-- the {arc.which} arc --", "", ""))
            rows.extend(arc.rows())

        notes = []
        if len(found) > 1:
            if "chord" in given and given.get("R"):
                notes.append(
                    "A chord cuts the circle in two, and both pieces are "
                    "arcs of it - so a radius and a chord describe two "
                    "arcs, not one. Give the angle or the rise to say "
                    "which.")
            else:
                notes.append(
                    f"Two arcs have that length with that rise. The ratio "
                    f"of an arc to its rise falls to "
                    f"{geometry.SHALLOWEST:.4f} at an included angle of "
                    f"{math.degrees(geometry.TURNS_AT):.1f} degrees and "
                    f"climbs back, so a ratio between that and pi belongs "
                    f"to two different arcs.")
        elif found[0].major:
            notes.append("This is the major arc - it goes the long way "
                         "round.")
        return rows, notes

    def _one_arc(self, arc, n: int) -> None:
        colour = "#1f4e79" if n == 0 else "#c00000"
        # The chord is put down first and the centre falls where it falls -
        # which for the major arc is above the chord rather than below it.
        # Centring each arc on its own middle instead would draw the two
        # answers to "a radius and a chord" with their chords in different
        # places, when the whole point is that it is the same chord.
        centre = (0.0, arc.rise - arc.R)
        angles = np.linspace(math.pi / 2 - arc.theta / 2,
                             math.pi / 2 + arc.theta / 2, 400)
        self.axes.plot(centre[0] + arc.R * np.cos(angles),
                       centre[1] + arc.R * np.sin(angles),
                       color=colour, linewidth=1.8,
                       linestyle="-" if n == 0 else "--",
                       label=arc.which or None)
        half = arc.chord / 2.0
        self.axes.plot([-half, half], [0.0, 0.0], color=colour,
                       linewidth=1.0, alpha=0.6)
        # The rise, straight up from the middle of the chord to the arc.
        self.axes.plot([0.0, 0.0], [0.0, arc.rise], color="#666666",
                       linewidth=0.9, linestyle=":")
        self.axes.plot([centre[0]], [centre[1]], marker="+", color=colour,
                       markersize=8)
        if n == 0:
            self.axes.annotate(f"  rise {arc.rise:.4g}", (0.0, arc.rise / 2),
                               fontsize=6.5, ha="left", va="center",
                               color="#333333")
            self.axes.annotate(f"chord {arc.chord:.4g}", (0.0, 0.0),
                               fontsize=6.5, ha="center", va="top",
                               color="#333333")
        if arc.which:
            self.axes.legend(loc="lower right", fontsize=7)

    # -- crossings ---------------------------------------------------------
    def _draw_two_lines(self) -> tuple:
        first, second = self._line(self.line1), self._line(self.line2)
        found = geometry.cross_lines(first, second)
        span = self._window([self._point(self.line1[:2]),
                             self._point(self.line1[2:]),
                             self._point(self.line2[:2]),
                             self._point(self.line2[2:])])
        for line, colour in ((first, "#1f4e79"), (second, "#c00000")):
            self._plot_line(line, span, colour)
        self._mark(found.points)
        return self._crossing_rows(found, "the two lines")

    def _draw_line_and_circle(self) -> tuple:
        line = self._line(self.lc_line)
        centre = self._point(self.lc_circle)
        radius = self.number(self.lc_radius, "the radius")
        found = geometry.cross_line_circle(line, centre, radius)
        self._plot_circle(centre, radius, "#c00000")
        self._plot_line(line, self._window(
            [self._point(self.lc_line[:2]), self._point(self.lc_line[2:]),
             (centre[0] - radius, centre[1] - radius),
             (centre[0] + radius, centre[1] + radius)]), "#1f4e79")
        self._mark(found.points)
        return self._crossing_rows(found, "the line and the circle")

    def _draw_two_circles(self) -> tuple:
        one, two = self._point(self.cc_one), self._point(self.cc_two)
        first = self.number(self.cc_one_r, "the first radius")
        second = self.number(self.cc_two_r, "the second radius")
        found = geometry.cross_circles(one, first, two, second)
        self._plot_circle(one, first, "#1f4e79")
        self._plot_circle(two, second, "#c00000")
        self._mark(found.points)
        rows, notes = self._crossing_rows(found, "the two circles")
        apart = math.hypot(two[0] - one[0], two[1] - one[1])
        rows.append(("centres apart", apart, ""))
        return rows, notes

    def _draw_tangents_from_a_point(self) -> tuple:
        point = self._point(self.tan_point)
        centre = self._point(self.tan_centre)
        radius = self.number(self.tan_radius, "the radius")
        found = geometry.tangent_from_point(point, centre, radius)
        self._plot_circle(centre, radius, "#c00000")
        self.axes.plot([point[0]], [point[1]], marker="o", markersize=5,
                       color="#1f4e79")
        for x, y in found.points:
            self.axes.plot([point[0], x], [point[1], y], color="#1f4e79",
                           linewidth=1.4)
        self._mark(found.points)
        rows, notes = self._crossing_rows(
            found, "the tangents",
            twice="Two tangents, touching at these two points - which is "
                  "what a point outside a circle always has.")
        if found:
            length = geometry.tangent_length(point, centre, radius)
            rows.insert(0, ("tangent length", length, ""))
            notes.append(
                "The two touch points, the centre and the point all lie on "
                "one circle, because a tangent meets the radius square - so "
                "this is a circle crossing a circle, and needs no arithmetic "
                "of its own.")
        return rows, notes

    def _draw_circle_through_three_points(self) -> tuple:
        points = [self._point(pair) for pair in self.three]
        centre, radius = geometry.circle_through(*points)
        self._plot_circle(centre, radius, "#1f4e79")
        self.axes.plot([x for x, _y in points], [y for _x, y in points],
                       linestyle="none", marker="o", markersize=5,
                       color="#c00000")
        self.axes.plot([centre[0]], [centre[1]], marker="+", markersize=9,
                       color="#1f4e79")
        rows = [("centre x", centre[0], ""), ("centre y", centre[1], ""),
                ("radius", radius, ""), ("diameter", 2 * radius, ""),
                ("circumference", 2 * math.pi * radius, "")]
        return rows, ["The centre is where the perpendicular bisectors of "
                      "two of the chords cross, which is the same line "
                      "crossing as the first problem on this tab."]

    # -- the drawing odds and ends ----------------------------------------
    def _window(self, points) -> tuple:
        xs = [x for x, _y in points]
        ys = [y for _x, y in points]
        pad = max(max(xs) - min(xs), max(ys) - min(ys), 1.0) * 0.25
        return (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)

    def _plot_line(self, line, span, colour) -> None:
        """Draw Ax + By = C across the window, upright lines included."""
        a, b, c = line
        left, right, bottom, top = span
        if abs(b) < 1e-12:
            x = c / a
            self.axes.plot([x, x], [bottom, top], color=colour, linewidth=1.4)
            return
        self.axes.plot([left, right],
                       [(c - a * left) / b, (c - a * right) / b],
                       color=colour, linewidth=1.4)

    def _plot_circle(self, centre, radius, colour) -> None:
        angles = np.linspace(0, 2 * math.pi, 400)
        self.axes.plot(centre[0] + radius * np.cos(angles),
                       centre[1] + radius * np.sin(angles),
                       color=colour, linewidth=1.4)
        self.axes.plot([centre[0]], [centre[1]], marker="+", markersize=7,
                       color=colour)

    def _mark(self, points) -> None:
        for n, (x, y) in enumerate(points, start=1):
            self.axes.plot([x], [y], marker="o", markersize=6,
                           color="#107C41", zorder=5)
            self.axes.annotate(f"  {n}" if len(points) > 1 else "", (x, y),
                               fontsize=8, color="#107C41")

    def _crossing_rows(self, found, what: str, twice: str = "") -> tuple:
        if not found:
            return ([(what, "do not cross", "")],
                    [found.note.capitalize() + "."])
        notes = [found.note.capitalize() + "."] if found.note else []
        if len(found.points) == 2 and not notes:
            notes.append(twice or
                         f"Two crossings, and which is wanted is not in the "
                         f"numbers - {what} really do meet twice.")
        return found.rows(), notes


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


CHARTS = [
    ("  Stress and strain  ", TensileTab),
    ("  Beam  ", BeamTab),
    ("  Section  ", SectionTab),
    ("  Torsion  ", TorsionTab),
    ("  Columns  ", ColumnTab),
    ("  Motion  ", MotionTab),
    ("  Stress state  ", MohrTab),
    ("  Pressure vessel  ", VesselTab),
    ("  Truss  ", TrussTab),
    ("  Geometry  ", GeometryTab),
    ("  Material chart  ", MaterialsTab),
    ("  Moody  ", MoodyTab),
]
