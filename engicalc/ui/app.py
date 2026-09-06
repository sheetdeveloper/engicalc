"""EngiCalc main window."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from .. import __version__
from ..core import display
from ..formulas.library import get_library
from ..plotting.plot import spec_from_result
from .. import faults
from ..storage.history import DEFAULT_DB, History
from .calculator_pane import CalculatorPane
from .cards_tab import CardsTab
from .graph_pane import GraphPane
from .history_tab import HistoryTab
from .interpolate_tab import InterpolateTab
from .matrix_tab import MatrixTab
from .sheet_tab import SheetTab
from .properties_pane import PropertiesPane
from .statistics_tab import StatisticsTab
from .library_tab import LibraryTab
from .reference_window import ReferenceWindow
from .splash import Splash
from .widgets import AsyncRunner, apply_theme

ABOUT = """EngiCalc

A symbolic calculator, grapher and engineering formula library.

Everything is computed locally with SymPy - no internet connection is used
and nothing is uploaded. Calculations you save live in:
  {db}

Results are only as good as the assumptions behind them. Check the
assumption line on any library formula before relying on it for design work.
"""



SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".engicalc",
                             "settings.json")


def _remembered_check_setting() -> bool:
    """Whether update checking was switched on. Off if never answered."""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
            return bool(json.load(handle).get("check_at_start", False))
    except Exception:                                     # noqa: BLE001
        return False


def _remember_check_setting(value: bool) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
            json.dump({"check_at_start": bool(value)}, handle)
    except Exception:                                     # noqa: BLE001
        pass                      # a setting that will not save is not fatal


class EngiCalcApp(tk.Tk):
    def __init__(self, db_path: str = DEFAULT_DB, show_splash: bool = False):
        super().__init__()
        # First, so that anything below which fails is written down rather
        # than thrown at a stderr the windowed build has not got.
        faults.attach(self)
        self.title("EngiCalc - equation solver, grapher and formula library")
        self.geometry("1200x780")
        self.minsize(980, 640)
        apply_theme(self)

        self.library = get_library()
        self.history = History(db_path)
        self.project = tk.StringVar(value="")
        self.autosave = tk.BooleanVar(value=False)
        # Every step is generated either way; this decides how many are
        # shown. See core.steps.Step.minor.
        self.show_working = tk.BooleanVar(value=False)
        # Off unless asked for. The app promises nothing leaves the machine,
        # and a check is a request to GitHub carrying an IP address - small,
        # but not the promise. Remembered once somebody turns it on.
        self.check_at_start = tk.BooleanVar(value=_remembered_check_setting())
        self.check_at_start.trace_add(
            "write", lambda *a: _remember_check_setting(
                self.check_at_start.get()))

        # Up before the body, because the body is the slow part - the
        # formula library and matplotlib are most of the second it takes.
        splash = None
        if show_splash:
            try:
                splash = Splash(self)
            except Exception:                         # noqa: BLE001
                splash = None     # never let the splash stop the app opening

        self._build_menu()
        if splash:
            splash.say("Loading the tabs...")
        self._build_body()
        if splash:
            splash.say("Ready")
            self.after(Splash.LINGER if hasattr(Splash, "LINGER") else 450,
                       splash.finish)
        self._maybe_check_at_start()
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
        view.add_checkbutton(label="Check for updates at startup",
                             variable=self.check_at_start)
        view.add_checkbutton(label="Show all working",
                             variable=self.show_working,
                             command=self.refresh_working)

        # How numbers are written, everywhere at once. A preference that
        # applied to only some tabs would not be one.
        numbers = tk.Menu(view, tearoff=0)
        self.notation = tk.StringVar(value="auto")
        for key, label in display.NOTATIONS.items():
            numbers.add_radiobutton(label=label, value=key,
                                    variable=self.notation,
                                    command=self._number_format_changed)
        numbers.add_separator()
        self.figures = tk.StringVar(value=display.AS_ASKED)
        numbers.add_radiobutton(label="As each screen chooses",
                                value=display.AS_ASKED, variable=self.figures,
                                command=self._number_format_changed)
        for count in range(0, 9):
            numbers.add_radiobutton(
                label=f"{count} decimal places / figures", value=str(count),
                variable=self.figures,
                command=self._number_format_changed)
        view.add_cascade(label="Numbers", menu=numbers)
        menu.add_cascade(label="Options", menu=view)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Symbols and syntax reference...",
                              command=self.show_reference)
        help_menu.add_command(label="Quick syntax card", command=self.show_syntax)
        help_menu.add_command(label="Check for updates...",
                              command=self.check_for_updates)
        help_menu.add_command(label="About", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _number_format_changed(self) -> None:
        """Apply the setting, then redraw whatever is already on screen."""
        display.set_number_format(figures=self.figures.get(),
                                  notation=self.notation.get())
        self.refresh_numbers()

    def refresh_numbers(self) -> None:
        """Ask every tab that shows numbers to write them again.

        A format setting that only took effect on the next calculation would
        look broken, so each tab is asked to redraw what it already has.
        """
        for tab in (self.steam_tab, self.moist_air_tab, self.units_tab,
                    self.statistics_tab, self.sheet_tab,
                    self.interpolate_tab, self.matrix_tab):
            for method in ("compute", "calculate", "convert"):
                if hasattr(tab, method):
                    try:
                        getattr(tab, method)()
                    except Exception:                 # noqa: BLE001
                        pass      # a tab with nothing in it has nothing to do
                    break
        for tab in (self.calculator_tab, self.simultaneous_tab):
            try:
                tab._render_steps()
            except Exception:                         # noqa: BLE001
                pass

    def refresh_working(self) -> None:
        """Redraw the working wherever it is shown, at the new level."""
        for tab in (self.calculator_tab, self.simultaneous_tab):
            try:
                tab._render_steps()
            except Exception:                         # noqa: BLE001
                pass          # a tab with nothing worked out yet has none

    # -- updates ----------------------------------------------------------
    def check_for_updates(self, quietly: bool = False) -> None:
        """Ask GitHub whether there is a newer release, and say so.

        Never downloads and never installs - it opens the release page and a
        person decides. `quietly` is for the automatic check at startup,
        which says nothing when there is nothing to say.
        """
        from ..core import updates

        def look():
            return updates.check(__version__)

        def tell(found):
            if found is None:
                if not quietly:
                    messagebox.showinfo(
                        "No update",
                        f"Version {__version__} is the latest there is.")
                return
            wanted = messagebox.askyesno(
                "An update is available",
                f"{found.summary} is out; this is {__version__}.\n\n"
                "Open the download page? Nothing is downloaded or installed "
                "by the app itself.")
            if wanted:
                import webbrowser
                webbrowser.open(updates.RELEASES_PAGE)

        def failed(_exc):
            if not quietly:
                messagebox.showinfo(
                    "Could not check",
                    "No answer from GitHub just now. Nothing is wrong with "
                    "your copy - try again later.")

        AsyncRunner(self).run(look, tell, failed)

    def _maybe_check_at_start(self) -> None:
        if self.check_at_start.get():
            self.after(2000, lambda: self.check_for_updates(quietly=True))

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

        # The pane holds the two calculator sub-tabs; `calculator_tab` is
        # still the calculator itself, so nothing that talks to it changes.
        self.calculator_pane = CalculatorPane(self.notebook, self)
        self.calculator_tab = self.calculator_pane.calculator
        self.simultaneous_tab = self.calculator_pane.simultaneous
        self.units_tab = self.calculator_pane.units
        self.graph_pane = GraphPane(self.notebook, self)
        self.graph_tab = self.graph_pane.curves
        self.library_tab = LibraryTab(self.notebook, self)
        self.cards_tab = CardsTab(self.notebook, self)
        self.interpolate_tab = InterpolateTab(self.notebook, self)
        self.matrix_tab = MatrixTab(self.notebook, self)
        self.sheet_tab = SheetTab(self.notebook, self)
        self.properties_pane = PropertiesPane(self.notebook, self)
        self.steam_tab = self.properties_pane.steam
        self.moist_air_tab = self.properties_pane.moist_air
        self.statistics_tab = StatisticsTab(self.notebook, self)
        self.history_tab = HistoryTab(self.notebook, self)

        self.notebook.add(self.calculator_pane, text="  Calculator  ")
        self.notebook.add(self.graph_pane, text="  Graph  ")
        self.notebook.add(self.library_tab, text="  Formula library  ")
        self.notebook.add(self.cards_tab, text="  Formula cards  ")
        self.notebook.add(self.interpolate_tab, text="  Interpolate  ")
        self.notebook.add(self.matrix_tab, text="  Matrices  ")
        # "Sheet" reads as sheet metal or a spreadsheet, and it is neither -
        # it is a calculation worked down the page in named steps. The
        # operation string stays "sheet" so entries already in the history
        # still reopen.
        self.notebook.add(self.sheet_tab, text="  Worksheet  ")
        # "Properties" says nothing - everything in the app is a
        # property of something. These are fluid properties.
        self.notebook.add(self.properties_pane,
                          text="  Fluid properties  ")
        self.notebook.add(self.statistics_tab, text="  Data  ")
        self.notebook.add(self.history_tab, text="  History  ")

        footer = ttk.Frame(self)
        footer.pack(fill="x", side="bottom")
        self.status = ttk.Label(footer, text="Ready", style="Hint.TLabel",
                                anchor="w", padding=(10, 2))
        self.status.pack(side="left")
        # Readable without opening a menu: "which version is this" should
        # not need a dialog to answer.
        ttk.Label(footer, text=f"EngiCalc {__version__}",
                  style="Hint.TLabel", padding=(10, 2)).pack(side="right")

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
        self.notebook.select(self.calculator_pane)
        self.calculator_pane.show_calculator()
        self.calculator_tab.insert_item(item)

    def open_formula(self, formula) -> None:
        """Load a formula into the library tab (used by the card browser)."""
        self.library_tab.show_formula(formula)
        self.notebook.select(self.library_tab)

    def plot_result(self, result) -> None:
        self.graph_tab.show_spec(spec_from_result(result))
        self.notebook.select(self.graph_pane)
        self.graph_pane.show_curves()

    def show_series(self, xs, ys, xlabel, ylabel, title) -> None:
        self.graph_tab.show_series(xs, ys, xlabel, ylabel, title)
        self.notebook.select(self.graph_pane)
        self.graph_pane.show_curves()

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
        elif entry.operation in self._restorable() and entry.inputs:
            # Saved from a tab that knows how to rebuild itself. Without
            # this every one of them came back as text in the equation bar -
            # a unit conversion as "25 mm to in", a set of equations as
            # several lines in a field that holds one. Nothing raised; it
            # just landed somewhere it made no sense.
            tab, sub = self._restorable()[entry.operation]
            self.notebook.select(sub if sub is not None else tab)
            if sub is not None:
                self.calculator_pane.tabs.select(tab)
            try:
                tab.restore(entry.inputs)
            except Exception as exc:                  # noqa: BLE001
                messagebox.showinfo(
                    "Could not reopen that",
                    f"It was saved, but not in a form this version can put "
                    f"back ({exc}).")
        else:
            self.calculator_tab.input_var.set(entry.input_text)
            if entry.operation:
                self.calculator_tab.op_var.set(entry.operation)
            if entry.variable:
                self.calculator_tab.var_var.set(entry.variable)
            self.calculator_tab._sync_options()
            self.notebook.select(self.calculator_pane)
            self.calculator_pane.show_calculator()
            self.calculator_tab.compute()

    def _restorable(self) -> dict:
        """operation -> (the tab, the pane holding it if it is a sub-tab)."""
        return {
            "system": (self.simultaneous_tab, self.calculator_pane),
            "convert": (self.units_tab, self.calculator_pane),
            "sheet": (self.sheet_tab, None),
            "steam": (self.steam_tab, self.properties_pane),
            "moistair": (self.moist_air_tab, self.properties_pane),
            "statistics": (self.statistics_tab, None),
        }

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
    # The splash is for someone starting the app, not for a test opening a
    # window - hence the flag rather than always.
    app = EngiCalcApp(show_splash=True)
    app.mainloop()
