"""The Calculator and its sub-tabs.

One equation, a set of them, a unit conversion and a complex number are the
same subject approached four ways, so they sit together rather than as four
entries in a top-level bar that already has ten.

The tabs run down the left with the notation each one stands for drawn on
them. Along the top they competed with the bar directly above; down the side
they read as a list of what this tab can do, and there is room for the
picture as well as the name. The icon is the notation itself rather than a
symbol standing in for a topic - `dy/dx` says calculus without having to.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme
from .calculator_tab import CalculatorTab
from .complex_tab import ComplexTab
from .simultaneous_tab import SimultaneousTab
from .units_tab import UnitsTab

#: (label, the notation drawn beside it) for each sub-tab.
ICONS = {
    "One equation": r"a x^{2}+b x+c=0",
    "Simultaneous": r"\begin{matrix}\end{matrix}",     # replaced below
    "Units": r"\mathrm{mm}\rightarrow\mathrm{in}",
    "Complex": r"a+b\,j",
}
# mathtext has no matrix environment, so the pair of equations is written
# the way it would be said instead.
ICONS["Simultaneous"] = r"x{+}y,\;x{-}y"

#: Every icon is drawn to this width so the tabs stack rather
#: than step down the side.
ICON_WIDTH = 132


class CalculatorPane(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._icons: dict[str, tk.PhotoImage] = {}

        self.tabs = ttk.Notebook(self, style="Side.TNotebook")
        self.tabs.pack(fill="both", expand=True)

        self.calculator = CalculatorTab(self.tabs, app)
        self.simultaneous = SimultaneousTab(self.tabs, app)
        self.units = UnitsTab(self.tabs, app)
        self.complex = ComplexTab(self.tabs, app)

        self._labels = ["One equation", "Simultaneous", "Units", "Complex"]
        for label, page in zip(self._labels,
                               (self.calculator, self.simultaneous,
                                self.units, self.complex)):
            self.tabs.add(page, text=f"  {label}  ", image=self._icon(label),
                          compound="top")

    def retheme(self) -> None:
        """Draw the tab notation again in the new ink.

        The icons are pictures, not text, so no amount of restyling moves
        them: a dark app would keep four dark-grey equations down the side
        of a dark strip, which is the same as not having them.
        """
        self._icons.clear()
        for index, label in enumerate(self._labels):
            picture = self._icon(label)
            if picture != "":
                self.tabs.tab(index, image=picture)

    def _icon(self, label: str):
        """The notation for one tab, drawn once and kept.

        Centred on a canvas of a fixed width so every tab comes out the same
        size: sized to their own notation they stepped down the side like a
        staircase, because `ax^2+bx+c=0` is three times the width of `a+bj`.

        A tab without a picture is no worse than the old ones, so a renderer
        that cannot draw this is not worth failing the window over.
        """
        import base64
        import io as _io

        import numpy as np
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties
        from PIL import Image

        try:
            parse = mathtext.MathTextParser("agg").parse(
                f"${ICONS[label]}$", dpi=110, prop=FontProperties(size=11))
            ink = np.asarray(parse.image, dtype=np.uint8)
            height, width = ink.shape
            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            # The same grey the unselected tab labels are written in,
            # so the notation and the words under it read as one thing.
            grey = theme.colours()["muted"].lstrip("#")
            rgba[..., 0], rgba[..., 1], rgba[..., 2] = (
                int(grey[0:2], 16), int(grey[2:4], 16), int(grey[4:6], 16))
            rgba[..., 3] = ink
            drawn = Image.fromarray(rgba, "RGBA")

            canvas = Image.new("RGBA", (ICON_WIDTH, height), (0, 0, 0, 0))
            if width > ICON_WIDTH:
                drawn = drawn.resize(
                    (ICON_WIDTH, max(1, int(height * ICON_WIDTH / width))),
                    Image.LANCZOS)
                width, height = drawn.size
                canvas = Image.new("RGBA", (ICON_WIDTH, height), (0, 0, 0, 0))
            canvas.paste(drawn, ((ICON_WIDTH - width) // 2, 0), drawn)

            buffer = _io.BytesIO()
            canvas.save(buffer, format="PNG")
            image = tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))
        except Exception:                             # noqa: BLE001
            return ""
        self._icons[label] = image        # kept, or Tk drops it
        return image

    def show_calculator(self) -> None:
        """Bring the single-equation pane forward.

        Sending a formula or a history entry to the calculator has to land
        somewhere visible, and it lands here rather than wherever the pane
        happened to be left.
        """
        self.tabs.select(self.calculator)

    def show_simultaneous(self) -> None:
        self.tabs.select(self.simultaneous)
