"""Graphs: curves of an expression, and the standard engineering charts.

The plotter draws whatever you write; the charts each take the handful of
numbers that define them and work the whole thing out. Both are graphs, so
they share a tab rather than taking two places in a bar that already has ten.

The sub-tabs run down the left rather than across the top. There are
fifteen of them now, and across the top they came to more than the window
is wide - so the last few were simply not there, on a window at the size
the app opens at. Down the side there is room for as many as the work
needs, which is the direction this has been going in for a while.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .charts_pane import CHARTS
from .graph_tab import GraphTab


class GraphPane(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.tabs = ttk.Notebook(self, style="Side.TNotebook")
        self.tabs.pack(fill="both", expand=True)

        # Every tab the same width. Sized to their own text they step down
        # the side like a staircase, because "Moody" is a third the width
        # of "Stress and strain" - and padding the labels out with spaces
        # does not fix it, because ttk trims them off again. A blank image
        # the width of the longest label does: the tab is as wide as the
        # wider of its image and its text, and now that is always the
        # image. It is the same trick the calculator pane uses, which
        # draws its notation onto a canvas of a fixed width for the same
        # reason.
        names = ["Curves"] + [label.strip() for label, _b in CHARTS]
        self._spacer = self._blank(names)

        self.curves = GraphTab(self.tabs, app)
        self._add(self.curves, "Curves")

        #: The standard charts, by the name on their tab.
        self.charts = {}
        for label, builder in CHARTS:
            chart = builder(self.tabs, app)
            name = label.strip()
            self.charts[name] = chart
            self._add(chart, name)
        # Once they all exist, each is told about the others. The beam uses
        # it to put the section worked out next door straight onto itself,
        # which is better than copying an I across by hand.
        for chart in self.charts.values():
            chart.linked(self.charts)

    def _blank(self, names: list):
        """A transparent image as wide as the longest label."""
        measure = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        widest = max(measure.measure(name) for name in names)
        return tk.PhotoImage(width=widest + 4, height=1)

    def _add(self, page, name: str) -> None:
        # compound="center" puts the text over the image rather than
        # beside it, so the spacer sets the width and costs no height.
        self.tabs.add(page, text=name, image=self._spacer,
                      compound="center")

    def show_curves(self) -> None:
        self.tabs.select(self.curves)
