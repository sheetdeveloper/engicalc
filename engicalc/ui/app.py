"""EngiCalc main window."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..formulas.library import get_library
from ..plotting.plot import spec_from_result
from ..storage.history import DEFAULT_DB, History
from .calculator_tab import CalculatorTab
from .cards_tab import CardsTab
from .graph_tab import GraphTab
from .history_tab import HistoryTab
from .interpolate_tab import InterpolateTab
from .matrix_tab import MatrixTab
from .sheet_tab import SheetTab
from .library_tab import LibraryTab
from .reference_window import ReferenceWindow
from .widgets import apply_theme

ABOUT = """EngiCalc

A symbolic calculator, grapher and engineering formula library.

Everything is computed locally with SymPy - no internet connection is used
and nothing is uploaded. Calculations you save live in:
  {db}

Results are only as good as the assumptions behind them. Check the
assumption line on any library formula before relying on it for design work.
"""


class EngiCalcApp(tk.Tk):
    def __init__(self, db_path: str = DEFAULT_DB):
        super().__init__()
        self.title("EngiCalc - equation solver, grapher and formula library")
        self.geometry("1200x780")
        self.minsize(980, 640)
        apply_theme(self)

        self.library = get_library()
        self.history = History(db_path)
        self.project = tk.StringVar(value="")
        self.autosave = tk.BooleanVar(value=False)

        self._build_menu()
        self._build_body()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # -- construction -----------------------------------------------------
    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Export history to Excel...",
                              command=lambda: self.history_tab.export())
        file_menu.add_command(label="Export history to JSON...",
                              command=lambda: self.history_tab.export_json())
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.on_close)
        menu.add_cascade(label="File", menu=file_menu)

        view = tk.Menu(menu, tearoff=0)
        view.add_checkbutton(label="Auto-save every result",
                             variable=self.autosave)
        menu.add_cascade(label="Options", menu=view)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Symbols and syntax reference...",
                              command=self.show_reference)
        help_menu.add_command(label="Quick syntax card", command=self.show_syntax)
        help_menu.add_command(label="About", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _build_body(self) -> None:
        header = ttk.Frame(self, padding=(10, 8, 10, 0))
        header.pack(fill="x")
        ttk.Label(header, text="Project").pack(side="left")
        ttk.Entry(header, textvariable=self.project, width=22).pack(side="left",
                                                                    padx=(4, 12))
        ttk.Label(header,
                  text=f"{len(self.library)} formulas loaded",
                  style="Hint.TLabel").pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.calculator_tab = CalculatorTab(self.notebook, self)
        self.graph_tab = GraphTab(self.notebook, self)
        self.library_tab = LibraryTab(self.notebook, self)
        self.cards_tab = CardsTab(self.notebook, self)
        self.interpolate_tab = InterpolateTab(self.notebook, self)
        self.matrix_tab = MatrixTab(self.notebook, self)
        self.sheet_tab = SheetTab(self.notebook, self)
        self.history_tab = HistoryTab(self.notebook, self)

        self.notebook.add(self.calculator_tab, text="  Calculator  ")
        self.notebook.add(self.graph_tab, text="  Graph  ")
        self.notebook.add(self.library_tab, text="  Formula library  ")
        self.notebook.add(self.cards_tab, text="  Formula cards  ")
        self.notebook.add(self.interpolate_tab, text="  Interpolate  ")
        self.notebook.add(self.matrix_tab, text="  Matrices  ")
        self.notebook.add(self.sheet_tab, text="  Sheet  ")
        self.notebook.add(self.history_tab, text="  History  ")

        self.status = ttk.Label(self, text="Ready", style="Hint.TLabel",
                                anchor="w", padding=(10, 2))
        self.status.pack(fill="x", side="bottom")

    # -- cross-tab plumbing ----------------------------------------------
    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def refresh_history(self) -> None:
        self.history_tab.refresh()

    def show_reference(self) -> None:
        """Open (or raise) the symbol and syntax reference window."""
        existing = getattr(self, "_reference", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_set()
            return
        self._reference = ReferenceWindow(
            self, on_insert=self._insert_from_reference)

    def _insert_from_reference(self, item) -> None:
        self.notebook.select(self.calculator_tab)
        self.calculator_tab.insert_item(item)

    def open_formula(self, formula) -> None:
        """Load a formula into the library tab (used by the card browser)."""
        self.library_tab.show_formula(formula)
        self.notebook.select(self.library_tab)

    def plot_result(self, result) -> None:
        self.graph_tab.show_spec(spec_from_result(result))
        self.notebook.select(self.graph_tab)

    def show_series(self, xs, ys, xlabel, ylabel, title) -> None:
        self.graph_tab.show_series(xs, ys, xlabel, ylabel, title)
        self.notebook.select(self.graph_tab)

    def reopen_entry(self, entry) -> None:
        """Load a stored calculation back into the tab it came from."""
        if entry.kind == "formula":
            formula = self.library.get(entry.operation)
            if formula is None:
                messagebox.showinfo(
                    "Formula not found",
                    "That formula is no longer in the library.")
                return
            self.library_tab.show_formula(formula)
            if entry.variable:
                self.library_tab.target_var.set(entry.variable)
                self.library_tab._build_inputs()
            for symbol, value in entry.inputs.items():
                if symbol in self.library_tab.entries:
                    self.library_tab.entries[symbol].set(str(value))
            self.notebook.select(self.library_tab)
        else:
            self.calculator_tab.input_var.set(entry.input_text)
            if entry.operation:
                self.calculator_tab.op_var.set(entry.operation)
            if entry.variable:
                self.calculator_tab.var_var.set(entry.variable)
            self.calculator_tab._sync_options()
            self.notebook.select(self.calculator_tab)
            self.calculator_tab.compute()

    # -- dialogs ----------------------------------------------------------
    def show_about(self) -> None:
        messagebox.showinfo("About EngiCalc", ABOUT.format(db=self.history.path))

    def show_syntax(self) -> None:
        messagebox.showinfo("Syntax", SYNTAX_HELP)

    def on_close(self) -> None:
        try:
            self.history.close()
        finally:
            self.destroy()


SYNTAX_HELP = """Input syntax

Powers            x^2   or   x**2
Multiplication    2x, 3sin(x) and 2*x all work
Roots             sqrt(x),  cbrt(x),  root(x, 3),  x^(1/3)
Logs              log(x) is natural, log(x, 10), log10(x), log2(x)
Exponential       exp(x),  e^x
Absolute value    abs(x)  or  |x|
Trig              sin cos tan asin acos atan atan2, and the hyperbolics
Constants         pi, e, oo (infinity), I (imaginary unit)
Equations         put a single '=' in the line
Systems           separate equations with ';'  ->  x + y = 10; x - y = 2
Numbers           2/3 stays exact, 0.667 is a decimal, 1.5e-3 works

Graph tab
  explicit     y as a function of x, e.g.  x^2 - 4  or  y = sin(x)
  implicit     any relation, e.g.  x^2 + y^2 = 9
  parametric   x(t) in the first box, y(t) in the second
  polar        r as a function of theta, e.g.  1 + cos(theta)
"""


def main() -> None:
    app = EngiCalcApp()
    app.mainloop()
