"""Draw a matrix, because mathtext will not.

Matplotlib's mathtext renders a subset of LaTeX that has no array or matrix
environment: ``\\begin{bmatrix}``, ``\\begin{array}`` and SymPy's own matrix
LaTeX all fail to parse, which is the same limitation `mathrender.sanitise`
already refuses to pretend around.

So the grid is laid out here instead. Each entry is typeset on its own -
those are ordinary expressions and mathtext handles them happily - and the
brackets are drawn as lines. The result is a properly typeset matrix built
out of parts that can each be drawn.
"""

from __future__ import annotations

import tkinter as tk

import sympy as sp

from . import mathrender

from . import theme

CELL_PAD_X = 14
CELL_PAD_Y = 8
BRACKET_GAP = 8
BRACKET_TICK = 7
BRACKET_WIDTH = 2


class MatrixView(tk.Canvas):
    """A canvas that draws one matrix, or a labelled row of them."""

    def __init__(self, master, fontsize: int = 15, colour: str | None = None,
                 background: str | None = None, **kwargs):
        palette = theme.colours()
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("background", background or palette["surface"])
        super().__init__(master, **kwargs)
        self.fontsize = fontsize
        self.colour = colour or palette["ink"]
        self._images: list = []          # kept alive; Tk will not hold them
        self._parts: list = []
        self.bind("<Configure>", lambda e: self._draw())

    # -- public -----------------------------------------------------------
    def show(self, *parts) -> None:
        """Display a sequence of matrices and strings, left to right.

        ``show("x =", solution)`` draws the label and then the matrix.

        The canvas asks for the height it needs. A matrix is as tall as its
        row count makes it, and a fixed height silently slices the top and
        bottom rows off - along with the bracket feet, so it does not even
        look like a matrix any more.
        """
        self._parts = list(parts)
        needed = self.required_height()
        if needed != int(self["height"]):
            self.configure(height=needed)
        self._draw()

    def retheme(self) -> None:
        """New ink, new paper, and the same matrix drawn again in them."""
        palette = theme.colours()
        self.colour = palette["ink"]
        self.configure(background=palette["surface"])
        self._draw()

    def clear(self) -> None:
        self._parts = []
        self._images.clear()
        self.delete("all")

    # -- drawing ----------------------------------------------------------
    def _cell_image(self, value):
        try:
            latex = sp.latex(value) if not isinstance(value, str) else value
            return mathrender.photo(latex, self.fontsize, self.colour)
        except Exception:                             # noqa: BLE001
            return None

    def _measure(self, matrix: sp.Matrix):
        """Cell images plus the column widths and row heights they need."""
        images = [[self._cell_image(matrix[r, c]) for c in range(matrix.cols)]
                  for r in range(matrix.rows)]
        widths = []
        for column in range(matrix.cols):
            widths.append(max(
                (images[r][column].width() if images[r][column] else 30)
                for r in range(matrix.rows)))
        heights = []
        for row in range(matrix.rows):
            heights.append(max(
                (images[row][c].height() if images[row][c] else 18)
                for c in range(matrix.cols)))
        return images, widths, heights

    def _matrix_size(self, widths, heights):
        width = sum(widths) + CELL_PAD_X * len(widths) + 2 * BRACKET_GAP \
            + 2 * BRACKET_TICK
        height = sum(heights) + CELL_PAD_Y * len(heights)
        return width, height

    def _draw(self) -> None:
        self.delete("all")
        self._images.clear()
        if not self._parts:
            return

        # Measure everything first so the row can be centred as a whole.
        measured = []
        total_width = 0
        max_height = 0
        for part in self._parts:
            if isinstance(part, sp.MatrixBase):
                images, widths, heights = self._measure(part)
                size = self._matrix_size(widths, heights)
                measured.append(("matrix", part, images, widths, heights, size))
                total_width += size[0] + 10
                max_height = max(max_height, size[1])
            else:
                image = self._cell_image(str(part))
                width = image.width() if image else 8 * len(str(part))
                height = image.height() if image else 18
                measured.append(("label", part, image, None, None,
                                 (width, height)))
                total_width += width + 12
                max_height = max(max_height, height)

        canvas_height = max(self.winfo_height(), 1)
        x = 10
        for kind, part, images, widths, heights, size in measured:
            middle = canvas_height / 2
            if kind == "label":
                if images is not None:
                    self._images.append(images)
                    self.create_image(x, middle, image=images, anchor="w")
                else:
                    self.create_text(x, middle, text=str(part), anchor="w",
                                     font=("Segoe UI", 11), fill=self.colour)
                x += size[0] + 12
            else:
                self._draw_matrix(part, images, widths, heights, x,
                                  middle - size[1] / 2, size)
                x += size[0] + 10

        self.configure(scrollregion=(0, 0, x + 10, max_height + 20))

    def _draw_matrix(self, matrix, images, widths, heights, left, top, size):
        width, height = size
        inner = left + BRACKET_GAP + BRACKET_TICK

        y = top
        for row in range(matrix.rows):
            x = inner
            for column in range(matrix.cols):
                image = images[row][column]
                centre_x = x + widths[column] / 2
                centre_y = y + heights[row] / 2 + CELL_PAD_Y / 2
                if image is not None:
                    self._images.append(image)
                    self.create_image(centre_x, centre_y, image=image)
                else:
                    self.create_text(centre_x, centre_y,
                                     text=str(matrix[row, column]),
                                     font=("Consolas", 10), fill=self.colour)
                x += widths[column] + CELL_PAD_X
            y += heights[row] + CELL_PAD_Y

        self._bracket(left + BRACKET_GAP, top, height, facing="right")
        self._bracket(left + width - BRACKET_GAP, top, height, facing="left")

    def _bracket(self, x, top, height, facing: str) -> None:
        """One square bracket: a stem with a foot at each end."""
        tick = BRACKET_TICK if facing == "right" else -BRACKET_TICK
        bottom = top + height
        self.create_line(x, top, x, bottom, fill=self.colour,
                         width=BRACKET_WIDTH)
        self.create_line(x, top, x + tick, top, fill=self.colour,
                         width=BRACKET_WIDTH)
        self.create_line(x, bottom, x + tick, bottom, fill=self.colour,
                         width=BRACKET_WIDTH)

    def required_height(self) -> int:
        """How tall the canvas needs to be to show what it has been given."""
        height = 0
        for part in self._parts:
            if isinstance(part, sp.MatrixBase):
                _images, widths, heights = self._measure(part)
                height = max(height, self._matrix_size(widths, heights)[1])
            else:
                height = max(height, 24)
        return int(height + 24)
