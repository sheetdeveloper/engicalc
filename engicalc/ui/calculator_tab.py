"""The general-purpose calculator tab: solve, simplify, calculus, systems.

Everything the user sees is typeset, including what they are typing: the
equation bar is an editable maths field, so a definite integral appears as a
real integral sign with boxes for the limits. The answer and each step of the
working are drawn the same way.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sympy as sp

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..core.display import fmt
from ..core.engine import OPERATIONS, calculate
from ..core.parsing import (names_read_as_products,
                            parse_for_display)
from ..export.excel import export_expression
from ..plotting.plot import draw as draw_plot, spec_from_result
from . import clipboard, mathfield, mathrender
from .symbol_pad import SymbolPad
from .widgets import AsyncRunner, MONO_BIG, ReadOnlyText

EXAMPLES = [
    "2x^2 - 5x - 3 = 0",
    "sqrt(x - 1) - x = -7",
    "3^x = 9^(x + 5)",
    "|3x + 1| = 4",
    "x^4 - 5x^2 + 4 = 0",
    "sin(x) + cos(x) = 1",
    "x + y = 10; x - y = 2",
    "1/(x - 2) + 1/(x + 2) = 1",
]


class CalculatorTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.runner = AsyncRunner(self)
        self.result = None
        self._syncing = False
        self._build()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x")

        heading = ttk.Frame(top)
        heading.pack(fill="x")
        ttk.Label(heading, text="Enter an equation or expression",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text="Symbols and syntax",
                   command=self.app.show_reference).pack(side="right")

        # The equation bar itself is typeset: pad shapes arrive as real
        # notation with empty boxes, and the values are typed into them.
        field_row = ttk.Frame(top)
        field_row.pack(fill="x", pady=(4, 0))
        self.field = mathfield.MathField(field_row, on_change=self._field_edited,
                                         on_submit=self.compute, fontsize=17)
        self.field.pack(side="left", fill="x", expand=True)
        ttk.Button(field_row, text="Go", style="Accent.TButton",
                   command=self.compute).pack(side="left", padx=(8, 0))

        # The plain-text box stays, for anyone who would rather type ASCII.
        # The two are kept in step; either can drive.
        entry_row = ttk.Frame(top)
        entry_row.pack(fill="x", pady=(4, 0))
        ttk.Label(entry_row, text="as text", style="Hint.TLabel").pack(
            side="left", padx=(0, 6))
        self.input_var = tk.StringVar(value="2x^2 - 5x - 3 = 0")
        self.entry = ttk.Entry(entry_row, textvariable=self.input_var,
                               font=MONO_BIG)
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", lambda e: self.compute())
        self.input_var.trace_add("write", lambda *a: self._text_edited())
        self.field.set_text(self.input_var.get())

        self.pad = SymbolPad(top, self.insert_item)
        self.pad.pack(fill="x", pady=(6, 0))

        options = ttk.Frame(top)
        options.pack(fill="x", pady=8)
        ttk.Label(options, text="Operation").pack(side="left")
        self.op_var = tk.StringVar(value="solve")
        op_box = ttk.Combobox(options, textvariable=self.op_var, width=12,
                              state="readonly", values=OPERATIONS)
        op_box.pack(side="left", padx=(4, 12))
        op_box.bind("<<ComboboxSelected>>", lambda e: self._sync_options())

        ttk.Label(options, text="Variable").pack(side="left")
        self.var_var = tk.StringVar(value="x")
        ttk.Entry(options, textvariable=self.var_var, width=6).pack(side="left",
                                                                    padx=(4, 12))

        self.extra = ttk.Frame(options)
        self.extra.pack(side="left")
        self.lower_var = tk.StringVar()
        self.upper_var = tk.StringVar()
        self.point_var = tk.StringVar(value="0")
        self.order_var = tk.StringVar(value="1")
        self.conditions_var = tk.StringVar()
        self._extra_widgets = {}
        for key, label, var, width in (
                ("lower", "from", self.lower_var, 6),
                ("upper", "to", self.upper_var, 6),
                ("point", "at", self.point_var, 6),
                ("order", "order", self.order_var, 4),
                ("conditions", "conditions", self.conditions_var, 22)):
            frame = ttk.Frame(self.extra)
            ttk.Label(frame, text=label).pack(side="left")
            ttk.Entry(frame, textvariable=var, width=width).pack(side="left",
                                                                 padx=(3, 10))
            self._extra_widgets[key] = frame

        self.show_plot = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Plot it", variable=self.show_plot,
                        command=self._refresh_plot).pack(side="left",
                                                         padx=(10, 0))

        ttk.Label(options, text="Example").pack(side="left", padx=(10, 2))
        self.example_var = tk.StringVar()
        example = ttk.Combobox(options, textvariable=self.example_var, width=22,
                               state="readonly", values=EXAMPLES)
        example.pack(side="left")
        example.bind("<<ComboboxSelected>>",
                     lambda e: self.input_var.set(self.example_var.get()))

        # The action row is packed before the panes and anchored to the
        # bottom, so it always gets its full height. Packed after them it is
        # last in line for space, and on a shorter window it was being given
        # 16 pixels of the 31 it needs - the buttons were there, sliced in
        # half, showing as four blank grey slivers.
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(6, 0))

        left = ttk.Labelframe(panes, text="Result", padding=6)
        # The number and the picture share the pane, split so either can be
        # dragged larger.
        self.result_panes = ttk.PanedWindow(left, orient="vertical")
        self.result_panes.pack(fill="both", expand=True)
        math_holder = ttk.Frame(self.result_panes)
        self.result_math = mathrender.MathList(math_holder, fontsize=17)
        self.result_math.pack(fill="both", expand=True)
        self.result_panes.add(math_holder, weight=2)

        # The picture of the answer. For a definite integral that is the area
        # under the curve, which is the thing being measured - so it belongs
        # beside the number rather than on the separate Graph tab.
        self.plot_frame = ttk.Frame(self.result_panes)
        self.figure = Figure(figsize=(5.0, 3.0), dpi=100)
        self.figure.patch.set_facecolor("white")
        self.plot_axes = self.figure.add_subplot(111)
        self.plot_canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.plot_canvas.get_tk_widget().pack(fill="both", expand=True)
        self._plot_shown = False
        panes.add(left, weight=3)

        right = ttk.Labelframe(panes, text="Steps", padding=6)
        header = ttk.Frame(right)
        header.pack(fill="x")
        self.steps_mode = tk.StringVar(value="math")
        ttk.Radiobutton(header, text="typeset", value="math",
                        variable=self.steps_mode,
                        command=self._render_steps).pack(side="right")
        ttk.Radiobutton(header, text="plain text", value="text",
                        variable=self.steps_mode,
                        command=self._render_steps).pack(side="right", padx=6)
        ttk.Checkbutton(header, text="all working",
                        variable=self.app.show_working,
                        command=self.app.refresh_working).pack(side="right",
                                                               padx=(0, 14))
        self.steps_holder = ttk.Frame(right)
        self.steps_holder.pack(fill="both", expand=True, pady=(4, 0))
        self.steps_math = mathrender.MathList(self.steps_holder, fontsize=15)
        self.steps_text = ReadOnlyText(self.steps_holder, height=10)
        self.steps_math.pack(fill="both", expand=True)
        panes.add(right, weight=4)

        self.status = ttk.Label(actions, text="Ready", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(actions, text="Export to Excel",
                   command=self.export).pack(side="right")
        ttk.Button(actions, text="Plot this",
                   command=self.send_to_graph).pack(side="right", padx=6)
        # One Copy control rather than three buttons: the row is already
        # busy, and which format you want depends on where it is going.
        copy_menu = ttk.Menubutton(actions, text="Copy  v")
        menu = tk.Menu(copy_menu, tearoff=0)
        menu.add_command(label="Copy as picture  (paste into Word)",
                         command=self.copy_picture)
        menu.add_command(label="Copy LaTeX", command=self.copy_latex)
        menu.add_separator()
        menu.add_command(label="Save as image...", command=self.save_picture)
        copy_menu.configure(menu=menu)
        copy_menu.pack(side="right")
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="right", padx=6)
        self._sync_options()

    # -- pad and the two input boxes --------------------------------------
    def insert_item(self, item) -> None:
        """Handle a press on the symbol pad or a double-click in the reference."""
        template = getattr(item, "template", "")
        if template:
            # Draw the shape in the equation bar and put the caret in its
            # first empty box; the operation selector follows along so the
            # rest of the tab still reflects what is being asked for.
            self.field.insert_template(template)
            if item.operation:
                self.op_var.set(item.operation)
                self._sync_options()
            self.field.focus_set()
            return
        if item.operation:
            self.op_var.set(item.operation)
            self._sync_options()
            focus = {"integral": "lower", "limit": "point",
                     "series": "point"}.get(item.operation)
            if focus and focus in self._extra_widgets:
                for child in self._extra_widgets[focus].winfo_children():
                    if isinstance(child, ttk.Entry):
                        child.focus_set()
                        return
            self.entry.focus_set()
            return
        text = item.inserted_text()
        if not text:
            return
        self.field.insert_text(text)
        self.field.focus_set()

    def _field_edited(self) -> None:
        """The typeset field changed - mirror it into the plain-text box."""
        if self._syncing:
            return
        self._syncing = True
        try:
            self.input_var.set(self.field.get_text())
        finally:
            self._syncing = False

    def _text_edited(self) -> None:
        """The plain-text box changed - mirror it into the typeset field."""
        if self._syncing:
            return
        self._syncing = True
        try:
            self.field.set_text(self.input_var.get())
        finally:
            self._syncing = False

    def _sync_options(self) -> None:
        for frame in self._extra_widgets.values():
            frame.pack_forget()
        operation = self.op_var.get()
        if operation in ("integral", "minimise", "maximise"):
            # For an integral these are the limits; for an optimisation
            # they are the range to look in, and giving one matters more
            # than it looks: the least value of x^2 on [1, 3] is at the
            # end of the range, where nothing is turning.
            self._extra_widgets["lower"].pack(side="left")
            self._extra_widgets["upper"].pack(side="left")
        elif operation in ("limit", "series"):
            self._extra_widgets["point"].pack(side="left")
            if operation == "series":
                self._extra_widgets["order"].pack(side="left")
        elif operation == "derivative":
            self._extra_widgets["order"].pack(side="left")
        elif operation == "ode":
            # Without conditions the answer carries arbitrary constants and
            # is a family of curves, so the box is put in front of people.
            self._extra_widgets["conditions"].pack(side="left")

    # -- actions ----------------------------------------------------------
    def compute(self) -> None:
        operation = self.op_var.get()
        kwargs = dict(lower=self.lower_var.get(), upper=self.upper_var.get(),
                      point=self.point_var.get(), order=self.order_var.get(),
                      conditions=self.conditions_var.get())
        variable = self.var_var.get().strip() or None

        # A calculus shape in the equation bar carries its own limits, so it
        # takes precedence over the selector and the from/to boxes.
        compiled = self.field.compiled()
        if compiled.operation:
            text = compiled.text.strip()
            operation = compiled.operation
            for name, value in compiled.extras.items():
                if not value.strip():
                    continue
                if name == "variable":
                    variable = value.strip()
                else:
                    kwargs[name] = value
        else:
            text = self.input_var.get().strip()

        if not text:
            return
        if ";" in text and operation == "solve":
            operation = "system"
        self.status.configure(text="Working...")
        self.runner.run(
            lambda: calculate(text, operation, variable, **kwargs),
            self._show, self._failed)

    def _refresh_plot(self) -> None:
        """Draw the answer, or hide the panel if there is nothing to draw.

        A plot that cannot be produced is not an error - plenty of results are
        not curves - so the panel simply stays out of the way.
        """
        if not self.show_plot.get() or self.result is None \
                or not self.result.plottable:
            self._hide_plot()
            return
        try:
            spec = spec_from_result(self.result)
            if not spec.curves:
                self._hide_plot()
                return
            warnings = draw_plot(spec, self.plot_axes)
            if warnings and not self.plot_axes.lines:
                self._hide_plot()
                return
            self._shrink_plot_labels()
            self.plot_canvas.draw_idle()
        except Exception:                       # noqa: BLE001 - never let a
            self._hide_plot()                   # picture break a result
            return
        if not self._plot_shown:
            self.result_panes.add(self.plot_frame, weight=3)
            self._plot_shown = True

    def _hide_plot(self) -> None:
        if self._plot_shown:
            self.result_panes.forget(self.plot_frame)
            self._plot_shown = False

    def _shrink_plot_labels(self) -> None:
        """Inline plots are small, so the decorations have to be too."""
        axes = self.plot_axes
        axes.title.set_fontsize(9)
        axes.xaxis.label.set_size(8)
        axes.yaxis.label.set_size(8)
        axes.tick_params(labelsize=7)
        legend = axes.get_legend()
        if legend is not None:
            for text in legend.get_texts():
                text.set_fontsize(7)
        self.figure.subplots_adjust(left=0.11, right=0.98, top=0.86,
                                    bottom=0.16)

    def _show(self, result) -> None:
        self.result = result
        self.result_math.render(self._result_blocks(result))
        self._render_steps()
        self._refresh_plot()
        self.status.configure(text=f"{result.operation} complete")
        if self.app.autosave.get():
            self.save(quiet=True)

    def _result_blocks(self, result) -> list:
        """(heading, expression, detail) rows for the result panel."""
        blocks = []
        variable = None
        if result.variable and "," not in result.variable:
            variable = sp.Symbol(result.variable)

        if result.operation in ("solve", "roots") and result.results:
            for index, solution in enumerate(result.results, 1):
                heading = f"Solution {index}" if len(result.results) > 1 \
                    else "Solution"
                # An inequality's answer is a range, and `x = [-3, 3]` is not
                # a true statement - Eq(x, Interval(...)) evaluates to False,
                # which is what the panel would otherwise print. It wants
                # `x in [-3, 3]`, which is what result.latex already holds.
                if isinstance(solution, sp.Set):
                    blocks.append((heading, result.latex or None,
                                   result.result_text))
                    continue
                expr = sp.Eq(variable, solution) if variable is not None \
                    else solution
                approx = ""
                try:
                    value = sp.N(solution, 10)
                    if value.is_real and fmt(value) != fmt(solution):
                        approx = f"≈ {float(value):.10g}"
                except Exception:  # noqa: BLE001
                    pass
                blocks.append((heading, expr, approx))
        elif result.operation == "system" and result.results:
            for index, mapping in enumerate(result.results, 1):
                if len(result.results) > 1:
                    blocks.append((f"Solution {index}", None, None))
                for symbol, value in mapping.items():
                    blocks.append((None, sp.Eq(symbol, value), None))
        elif result.operation in ("minimise", "maximise") and result.results:
            # The answer is a pair. Drawing the value alone leaves out the
            # half anybody asking this question wants: not how small it
            # gets, but where.
            blocks.append((
                "Least value" if result.operation == "minimise"
                else "Greatest value", result.results[0], None))
            where = result.result_text.split(" at ", 1)
            if len(where) == 2 and variable is not None:
                blocks.append(("Where", None, "at " + where[1]))
        elif result.results:
            blocks.append(("Result", result.results[0], None))
            if result.numeric and isinstance(result.numeric[0], float):
                blocks.append((None, None, f"= {result.numeric[0]:.10g}"))
        else:
            blocks.append(("Result", None, result.result_text or "No solution."))

        for warning in result.warnings:
            blocks.append(("Note", None, warning))

        # Said once, beside the answer. Nothing is wrong - juxtaposition is
        # multiplication here and `xy` has always meant x times y - but it
        # is worth knowing that `Re` was read as two things rather than one.
        split = names_read_as_products(result.input_text, result.expression)
        if split:
            names = ", ".join(split)
            spelled = ", ".join(f"{run[0]}_{run[1:]}" for run in split)
            blocks.append((
                "Read as a product", None,
                f"{names} - a run of letters is multiplied here, so this is "
                f"not one name. Write it {spelled} to keep it together."))
        return blocks

    def _shown_steps(self) -> list:
        """The steps to draw, at the level of working being asked for."""
        if self.result is None:
            return []
        wants_all = self.app.show_working.get()
        return [step for step in self.result.steps
                if wants_all or not step.minor]

    def _render_steps(self) -> None:
        if self.result is None:
            return
        for widget in (self.steps_math, self.steps_text):
            widget.pack_forget()
        steps = self._shown_steps()
        if self.steps_mode.get() == "text":
            self.steps_text.pack(fill="both", expand=True)
            self.steps_text.set("\n\n".join(s.text() for s in steps) or
                                "(no steps for this operation)")
        else:
            self.steps_math.pack(fill="both", expand=True)
            blocks = [(step.title, step.drawn(), step.detail)
                      for step in steps]
            self.steps_math.render(blocks or
                                   [("", None, "(no steps for this operation)")])

    def _failed(self, exc: Exception) -> None:
        self.result = None
        self.result_math.render([("Could not compute that", None, str(exc))])
        self.steps_math.clear()
        self.steps_text.set("")
        self.status.configure(text="Error")

    def copy_latex(self) -> None:
        if self.result is None:
            return
        latex = self.result.latex or (sp.latex(self.result.results[0])
                                      if self.result.results else "")
        if not latex:
            return
        self.clipboard_clear()
        self.clipboard_append(latex)
        self.status.configure(text="LaTeX copied to the clipboard")

    def _picture_blocks(self) -> list:
        """The whole calculation as (heading, expression, detail) rows.

        The problem first, then the answer, then the working - the order it
        would be written out by hand. Built from the same blocks the panels
        draw, so the picture cannot say something different from the window.
        """
        blocks = []
        try:
            blocks.append(("Problem",
                           parse_for_display(self.input_var.get()), None))
        except Exception:                           # noqa: BLE001
            blocks.append(("Problem", None, self.input_var.get()))
        blocks.extend(self._result_blocks(self.result))
        if self.result.steps:
            blocks.append(("Working", None, None))
            for step in self.result.steps:
                blocks.append((step.title, step.drawn(), step.detail))
        return blocks

    def _picture(self):
        return mathrender.render_calculation(self._picture_blocks())

    def copy_picture(self) -> None:
        """Copy the calculation as a picture, for pasting into a report."""
        if self.result is None:
            messagebox.showinfo("Nothing to copy", "Run a calculation first.")
            return
        try:
            image = self._picture()
        except Exception as exc:                    # noqa: BLE001
            messagebox.showerror("Could not draw the calculation", str(exc))
            return
        try:
            clipboard.copy_image(image, self.result.latex or None)
        except clipboard.ClipboardError as exc:
            messagebox.showerror("Could not copy", str(exc))
            return
        self.status.configure(
            text="Copied as a picture - paste it straight into Word")

    def save_picture(self) -> None:
        if self.result is None:
            messagebox.showinfo("Nothing to save", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG image", "*.png")],
            initialfile="calculation.png")
        if not path:
            return
        try:
            self._picture().save(path)
        except Exception as exc:                    # noqa: BLE001
            messagebox.showerror("Could not save", str(exc))
            return
        self.status.configure(text=f"Saved {path}")

    def save(self, quiet: bool = False) -> None:
        if self.result is None:
            if not quiet:
                messagebox.showinfo("Nothing to save", "Run a calculation first.")
            return
        self.app.history.add_result(self.result, project=self.app.project.get())
        self.app.refresh_history()
        self.status.configure(text="Saved to history")

    def send_to_graph(self) -> None:
        if self.result is None:
            messagebox.showinfo("Nothing to plot", "Run a calculation first.")
            return
        self.app.plot_result(self.result)

    def export(self) -> None:
        if self.result is None:
            messagebox.showinfo("Nothing to export", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="calculation.xlsx")
        if not path:
            return
        try:
            export_expression(self.result, path)
            self.status.configure(text=f"Exported to {path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))
