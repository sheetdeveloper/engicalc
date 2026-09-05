"""Formula library tab: browse by branch, fill in what you know, solve for the rest."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sympy as sp

from ..core.display import unicode_symbol
from ..core.parsing import parse_input
from ..export.excel import export_formula
from ..formulas.library import solve_formula
from ..formulas.model import Formula, Variable
from ..plotting.plot import sweep
from . import mathrender
from .widgets import AsyncRunner, MONO, ReadOnlyText, ScrollFrame


class LibraryTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.library = app.library
        self.runner = AsyncRunner(self)
        self.formula: Formula | None = None
        self.entries: dict[str, tk.StringVar] = {}
        self.solution = None
        self._build()
        self.populate_tree()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)

        left = ttk.Frame(panes)
        panes.add(left, weight=2)

        search_row = ttk.Frame(left)
        search_row.pack(fill="x")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search_row, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<KeyRelease>", lambda e: self.populate_tree())
        ttk.Button(search_row, text="Clear",
                   command=lambda: (self.search_var.set(""),
                                    self.populate_tree())).pack(side="left", padx=4)

        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=(6, 0))
        scroll.pack(side="right", fill="y", pady=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        right = ttk.Frame(panes)
        panes.add(right, weight=3)

        self.title_label = ttk.Label(right, text="Pick a formula",
                                     style="Title.TLabel")
        self.title_label.pack(anchor="w")
        # Packed before the panels that expand, so it always gets its
        # full height. Pack allocates in packing order, and a row
        # packed after an expanding widget is last in line for space.
        # See TestActionRows.
        actions = ttk.Frame(right)
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(actions, text="Save to history",
                   command=self.save).pack(side="left")
        ttk.Button(actions, text="Export to Excel",
                   command=self.export).pack(side="left", padx=6)
        ttk.Button(actions, text="Sensitivity plot",
                   command=self.plot_sweep).pack(side="left")
        ttk.Button(actions, text="Add my own formula",
                   command=self.add_formula_dialog).pack(side="right")

        equation_box = ttk.Frame(right, relief="solid", borderwidth=1)
        equation_box.pack(fill="x", pady=(4, 4))
        self.equation_math = mathrender.MathLabel(equation_box, fontsize=19,
                                                  height=62,
                                                  background="#fbfbfd")
        self.equation_math.pack(fill="x")
        self.meta_label = ttk.Label(right, text="", style="Hint.TLabel",
                                    wraplength=520, justify="left")
        self.meta_label.pack(anchor="w", pady=(0, 6))

        solve_row = ttk.Frame(right)
        solve_row.pack(fill="x")
        ttk.Label(solve_row, text="Solve for").pack(side="left")
        self.target_var = tk.StringVar()
        self.target_box = ttk.Combobox(solve_row, textvariable=self.target_var,
                                       width=12, state="readonly")
        self.target_box.pack(side="left", padx=(4, 10))
        self.target_box.bind("<<ComboboxSelected>>", lambda e: self._build_inputs())
        ttk.Button(solve_row, text="Calculate", style="Accent.TButton",
                   command=self.calculate).pack(side="left")
        ttk.Button(solve_row, text="Use defaults",
                   command=self.fill_defaults).pack(side="left", padx=6)

        # Values may carry their own unit, so say so - nobody types "50 mm"
        # into a box that has only ever wanted a bare number.
        ttk.Label(right, style="Hint.TLabel", justify="left",
                  text="A value can bring its own unit - type 50 mm into a "
                       "field that wants metres and it converts.").pack(
                           anchor="w", pady=(2, 0))

        self.inputs = ScrollFrame(right, height=210)
        self.inputs.pack(fill="both", expand=True, pady=8)

        result_frame = ttk.Labelframe(right, text="Result", padding=4)
        result_frame.pack(fill="x")
        self.result_math = mathrender.MathList(result_frame, fontsize=17)
        self.result_math.configure(height=120)
        self.result_math.pack(fill="both", expand=True)

        sweep_row = ttk.Frame(right)
        sweep_row.pack(fill="x", pady=(6, 0))
        ttk.Label(sweep_row, text="Sweep").pack(side="left")
        self.sweep_var = tk.StringVar()
        self.sweep_box = ttk.Combobox(sweep_row, textvariable=self.sweep_var,
                                      width=10, state="readonly")
        self.sweep_box.pack(side="left", padx=4)
        self.sweep_from = tk.StringVar()
        self.sweep_to = tk.StringVar()
        self.sweep_points = tk.StringVar(value="25")
        for label, var, width in (("from", self.sweep_from, 8),
                                  ("to", self.sweep_to, 8),
                                  ("points", self.sweep_points, 5)):
            ttk.Label(sweep_row, text=label).pack(side="left")
            ttk.Entry(sweep_row, textvariable=var, width=width).pack(side="left",
                                                                     padx=(2, 8))
        ttk.Label(sweep_row, text="(also written into the Excel export)",
                  style="Hint.TLabel").pack(side="left")

    # -- tree -------------------------------------------------------------
    def populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        query = self.search_var.get().strip()
        if query:
            for formula in self.library.search(query)[:200]:
                self.tree.insert("", "end", iid=formula.key,
                                 text=f"{formula.name}  ({formula.branch})")
            return
        for branch, categories in self.library.tree().items():
            branch_id = self.tree.insert("", "end", text=branch, open=False)
            for category, formulas in categories.items():
                cat_id = self.tree.insert(branch_id, "end", text=category)
                for formula in formulas:
                    self.tree.insert(cat_id, "end", iid=formula.key,
                                     text=formula.name)

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        formula = self.library.get(selection[0])
        if formula is None:
            return
        self.show_formula(formula)

    def show_formula(self, formula: Formula) -> None:
        self.formula = formula
        self.title_label.configure(text=formula.name)
        self.equation_math.show(formula.display_latex, formula.equation)
        meta = [f"{formula.branch} / {formula.category}"]
        if formula.assumptions:
            meta.append("Assumes: " + formula.assumptions)
        if formula.notes:
            meta.append(formula.notes)
        if formula.reference:
            meta.append("Ref: " + formula.reference)
        self.meta_label.configure(text="\n".join(meta))
        symbols = [v.symbol for v in formula.variables]
        self.target_box.configure(values=symbols)
        self.sweep_box.configure(values=symbols)
        if symbols:
            self.target_var.set(symbols[0])
        self.result_math.clear()
        self._build_inputs()

    def _build_inputs(self) -> None:
        self.inputs.clear()
        self.entries.clear()
        if self.formula is None:
            return
        target = self.target_var.get()
        body = self.inputs.body
        ttk.Label(body, text="Symbol", font=("Segoe UI", 9, "bold")
                  ).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(body, text="Quantity", font=("Segoe UI", 9, "bold")
                  ).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(body, text="Value", font=("Segoe UI", 9, "bold")
                  ).grid(row=0, column=2, sticky="w", padx=4)
        ttk.Label(body, text="Unit", font=("Segoe UI", 9, "bold")
                  ).grid(row=0, column=3, sticky="w", padx=4)

        for index, var in enumerate(self.formula.variables, start=1):
            is_target = var.symbol == target
            # Read as it is written: rho is a Greek letter, dT is a change
            # in T. The name stays ASCII everywhere it is typed or parsed.
            ttk.Label(body, text=unicode_symbol(var.symbol),
                      font=("Segoe UI", 10)).grid(
                row=index, column=0, sticky="w", padx=4, pady=1)
            ttk.Label(body, text=var.description).grid(
                row=index, column=1, sticky="w", padx=4)
            value = tk.StringVar(value="" if is_target else var.typical)
            entry = ttk.Entry(body, textvariable=value, width=16, font=MONO)
            entry.grid(row=index, column=2, sticky="w", padx=4)
            if is_target:
                entry.configure(state="disabled")
            else:
                entry.bind("<Return>", lambda e: self.calculate())
            self.entries[var.symbol] = value
            ttk.Label(body, text=var.unit).grid(row=index, column=3, sticky="w",
                                                padx=4)
        # Column 4 absorbs the slack so the value boxes stay beside the
        # descriptions instead of being pushed to the far right.
        body.columnconfigure(1, minsize=200)
        body.columnconfigure(4, weight=1)

    def fill_defaults(self) -> None:
        if self.formula is None:
            return
        for var in self.formula.variables:
            if var.symbol in self.entries and var.typical:
                self.entries[var.symbol].set(var.typical)

    # -- actions ----------------------------------------------------------
    def _values(self) -> dict:
        return {name: var.get() for name, var in self.entries.items()}

    def calculate(self) -> None:
        if self.formula is None:
            return
        target = self.target_var.get()
        values = self._values()
        self.result_math.render([("Working...", None, None)])
        self.runner.run(
            lambda: solve_formula(self.formula, target, values),
            self._show, self._failed)

    def _show(self, solution) -> None:
        self.solution = solution
        target = sp.Symbol(solution.target)
        blocks = []
        if isinstance(solution.expression, sp.Equality):
            blocks.append(("Solved numerically from", solution.expression, None))
        else:
            blocks.append(("Rearranged", sp.Eq(target, solution.expression), None))
        if solution.value is not None:
            unit = f" {solution.unit}" if solution.unit not in ("", "-") else ""
            blocks.append(("Answer", sp.Eq(target, sp.Float(solution.value, 6)),
                           f"{solution.value:.6g}{unit}"))
        for warning in solution.warnings:
            blocks.append(("Note", None, warning))
        self.result_math.render(blocks)
        if self.app.autosave.get() and solution.value is not None:
            self.save(quiet=True)

    def _failed(self, exc: Exception) -> None:
        self.solution = None
        self.result_math.render([("Could not calculate that", None, str(exc))])

    def save(self, quiet: bool = False) -> None:
        if self.solution is None:
            if not quiet:
                messagebox.showinfo("Nothing to save", "Calculate something first.")
            return
        self.app.history.add_formula_solution(self.solution,
                                              project=self.app.project.get())
        self.app.refresh_history()
        self.app.set_status("Saved to history")

    def _sweep_settings(self) -> dict | None:
        variable = self.sweep_var.get()
        if not variable or not self.sweep_from.get() or not self.sweep_to.get():
            return None
        try:
            return {"variable": variable, "start": float(self.sweep_from.get()),
                    "stop": float(self.sweep_to.get()),
                    "points": int(self.sweep_points.get() or 25)}
        except ValueError:
            return None

    def export(self) -> None:
        if self.formula is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=f"{self.formula.name[:40].replace(' ', '_')}.xlsx")
        if not path:
            return
        try:
            export_formula(self.formula, self.target_var.get(), self._values(),
                           path, sweep=self._sweep_settings(),
                           project=self.app.project.get())
            self.app.set_status(f"Exported to {path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def plot_sweep(self) -> None:
        settings = self._sweep_settings()
        if self.formula is None or settings is None:
            messagebox.showinfo(
                "Sweep not set",
                "Choose a variable to sweep and give it a from/to range.")
            return
        target = self.target_var.get()
        values = self._values()

        def work():
            return sweep(self.formula, target, values, settings["variable"],
                         settings["start"], settings["stop"], settings["points"])

        self.runner.run(
            work,
            lambda data: self.app.show_series(
                data[0], data[1],
                f"{settings['variable']} [{self.formula.unit_of(settings['variable'])}]",
                f"{target} [{self.formula.unit_of(target)}]",
                f"{self.formula.name}: {target} vs {settings['variable']}"),
            lambda exc: messagebox.showerror("Sweep failed", str(exc)))

    # -- user formulas ----------------------------------------------------
    def add_formula_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Add a formula")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        fields = {}
        rows = [("Name", "name", "Bolt preload"),
                ("Branch", "branch", "My formulas"),
                ("Category", "category", "General"),
                ("Equation", "equation", "F = k*d*T"),
                ("Notes", "notes", "")]
        for index, (label, key, placeholder) in enumerate(rows):
            ttk.Label(dialog, text=label).grid(row=index, column=0, sticky="w",
                                               padx=8, pady=4)
            var = tk.StringVar(value=placeholder if key in ("branch", "category")
                               else "")
            ttk.Entry(dialog, textvariable=var, width=52, font=MONO).grid(
                row=index, column=1, padx=8, pady=4)
            fields[key] = var
        ttk.Label(dialog,
                  text="Variables are picked up from the equation. Describe them\n"
                       "as  symbol: description [unit]  one per line (optional).",
                  style="Hint.TLabel", justify="left").grid(
            row=len(rows), column=0, columnspan=2, sticky="w", padx=8)
        detail = tk.Text(dialog, height=6, width=60, font=MONO)
        detail.grid(row=len(rows) + 1, column=0, columnspan=2, padx=8, pady=6)

        def save_it():
            try:
                formula = self._formula_from_fields(fields, detail.get("1.0", "end"))
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Could not add", str(exc), parent=dialog)
                return
            self.library.add_user_formula(formula)
            self.populate_tree()
            self.show_formula(formula)
            dialog.destroy()

        ttk.Button(dialog, text="Save", style="Accent.TButton",
                   command=save_it).grid(row=len(rows) + 2, column=1, sticky="e",
                                         padx=8, pady=(0, 10))

    def _formula_from_fields(self, fields, detail_text: str) -> Formula:
        equation = fields["equation"].get().strip()
        name = fields["name"].get().strip() or "Untitled formula"
        if not equation or "=" not in equation:
            raise ValueError("Give an equation with an '=' in it.")
        parsed = parse_input(equation)
        described = {}
        for line in detail_text.splitlines():
            if ":" in line:
                symbol, rest = line.split(":", 1)
                unit = ""
                if "[" in rest and "]" in rest:
                    unit = rest[rest.index("[") + 1:rest.index("]")].strip()
                    rest = rest[:rest.index("[")]
                described[symbol.strip()] = (rest.strip(), unit)
        variables = []
        for symbol in sorted(parsed.expr.free_symbols, key=lambda s: s.name):
            description, unit = described.get(symbol.name, ("", ""))
            variables.append(Variable(symbol.name, description or symbol.name, unit))
        branch = fields["branch"].get().strip() or "My formulas"
        key = "user." + name.lower().replace(" ", "_")[:40]
        return Formula(key=key, name=name, branch=branch,
                       category=fields["category"].get().strip() or "General",
                       equation=equation, variables=variables,
                       notes=fields["notes"].get().strip())
