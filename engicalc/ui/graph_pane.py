"""Graphs: curves of an expression, and the standard engineering charts.

The plotter draws whatever you write; the charts each take the handful of
numbers that define them and work the whole thing out. Both are graphs, so
they share a tab rather than taking two places in a bar that already has ten.
"""

from __future__ import annotations

from tkinter import ttk

from .charts_pane import CHARTS
from .graph_tab import GraphTab


class GraphPane(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.curves = GraphTab(self.tabs, app)
        self.tabs.add(self.curves, text="  Curves  ")

        #: The standard charts, by the name on their tab.
        self.charts = {}
        for label, builder in CHARTS:
            chart = builder(self.tabs, app)
            self.charts[label.strip()] = chart
            self.tabs.add(chart, text=label)

    def show_curves(self) -> None:
        self.tabs.select(self.curves)
