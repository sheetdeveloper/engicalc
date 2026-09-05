"""The Calculator and its sub-tabs.

One equation and a set of them are the same subject approached two ways, so
they sit together rather than as two entries in a top-level bar that already
has nine. They are genuinely different surfaces, though - a set needs several
lines and has no single unknown to select - which is why this is two panes
rather than a mode switch on one.

The pane holds the tabs; it does not do any of the work. Anything wanting the
calculator itself asks for :attr:`calculator`, so the rest of the app is
unchanged by this being a container.
"""

from __future__ import annotations

from tkinter import ttk

from .calculator_tab import CalculatorTab
from .simultaneous_tab import SimultaneousTab


class CalculatorPane(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.calculator = CalculatorTab(self.tabs, app)
        self.simultaneous = SimultaneousTab(self.tabs, app)

        self.tabs.add(self.calculator, text="  One equation  ")
        self.tabs.add(self.simultaneous, text="  Solved together  ")

    def show_calculator(self) -> None:
        """Bring the single-equation pane forward.

        Sending a formula or a history entry to the calculator has to land
        somewhere visible, and it lands here rather than wherever the pane
        happened to be left.
        """
        self.tabs.select(self.calculator)

    def show_simultaneous(self) -> None:
        self.tabs.select(self.simultaneous)
