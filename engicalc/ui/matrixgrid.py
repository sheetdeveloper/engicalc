"""A grid of cells to type a matrix into.

Typing a matrix into a text box means counting spaces and hoping the rows
line up. A grid is what a matrix is, so this is a grid: one entry per cell,
Tab across, Enter down, arrow keys anywhere.

It still speaks text at the edges - :func:`get_text` produces exactly what
:func:`core.matrices.parse_matrix` already reads, and :func:`set_text` takes
what comes off the clipboard - so pasting two columns out of Excel still
works and the core needs no idea a grid exists.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

CELL_WIDTH = 8
MAX_ROWS = 12
MAX_COLUMNS = 12


class MatrixGrid(ttk.Frame):
    """An editable grid of numbers, sized by the buttons beside it."""

    def __init__(self, master, rows: int = 3, columns: int = 3,
                 on_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_change = on_change
        self.cells: list = []          # list of rows, each a list of StringVar
        self.widgets: list = []        # the matching Entry widgets

        self.grid_holder = ttk.Frame(self)
        self.grid_holder.pack(side="left", anchor="n")

        controls = ttk.Frame(self)
        controls.pack(side="left", anchor="n", padx=(8, 0))
        for text, delta_rows, delta_columns, tip in (
                ("+ row", 1, 0, "another equation"),
                ("- row", -1, 0, "one fewer equation"),
                ("+ col", 0, 1, "another unknown"),
                ("- col", 0, -1, "one fewer unknown")):
            ttk.Button(controls, text=text, width=7,
                       command=lambda r=delta_rows, c=delta_columns:
                       self.resize_by(r, c)).pack(pady=1)

        self.size_label = ttk.Label(controls, text="", style="Hint.TLabel")
        self.size_label.pack(pady=(4, 0))

        self.set_size(rows, columns)

    # -- shape -------------------------------------------------------------
    @property
    def rows(self) -> int:
        return len(self.cells)

    @property
    def columns(self) -> int:
        return len(self.cells[0]) if self.cells else 0

    def resize_by(self, delta_rows: int, delta_columns: int) -> None:
        self.set_size(self.rows + delta_rows, self.columns + delta_columns)
        self._changed()

    def set_size(self, rows: int, columns: int) -> None:
        """Resize, keeping whatever was already typed in the cells that stay."""
        rows = max(1, min(MAX_ROWS, rows))
        columns = max(1, min(MAX_COLUMNS, columns))
        if rows == self.rows and columns == self.columns:
            return

        kept = [[var.get() for var in row] for row in self.cells]
        for widget_row in self.widgets:
            for widget in widget_row:
                widget.destroy()
        self.cells.clear()
        self.widgets.clear()

        for r in range(rows):
            variables, widgets = [], []
            for c in range(columns):
                previous = kept[r][c] if r < len(kept) and c < len(kept[r]) \
                    else ""
                var = tk.StringVar(value=previous)
                var.trace_add("write", lambda *a: self._changed())
                entry = ttk.Entry(self.grid_holder, textvariable=var,
                                  width=CELL_WIDTH, justify="right")
                entry.grid(row=r, column=c, padx=1, pady=1)
                entry.bind("<Return>", lambda e, r=r, c=c: self._step(r, c, 1, 0))
                entry.bind("<Up>", lambda e, r=r, c=c: self._step(r, c, -1, 0))
                entry.bind("<Down>", lambda e, r=r, c=c: self._step(r, c, 1, 0))
                entry.bind("<Control-v>", self._on_paste)
                entry.bind("<<Paste>>", self._on_paste)
                variables.append(var)
                widgets.append(entry)
            self.cells.append(variables)
            self.widgets.append(widgets)
        self.size_label.configure(text=f"{rows} x {columns}")

    def _step(self, row: int, column: int, down: int, across: int):
        """Move the keyboard focus between cells."""
        r = min(max(row + down, 0), self.rows - 1)
        c = min(max(column + across, 0), self.columns - 1)
        self.widgets[r][c].focus_set()
        self.widgets[r][c].selection_range(0, "end")
        return "break"

    # -- contents ----------------------------------------------------------
    def get_text(self) -> str:
        """The grid as the text ``core.matrices.parse_matrix`` reads."""
        lines = []
        for row in self.cells:
            values = [(var.get().strip() or "0") for var in row]
            lines.append(" ".join(values))
        return "\n".join(lines)

    def set_text(self, text: str) -> None:
        """Fill the grid from text, resizing it to fit what arrived."""
        rows = []
        for line in (text or "").strip().splitlines():
            cleaned = line.strip().strip("[]")
            if not cleaned:
                continue
            parts = [p for p in _split(cleaned) if p]
            if parts:
                rows.append(parts)
        if not rows:
            return
        width = max(len(r) for r in rows)
        self.set_size(len(rows), width)
        for r, row in enumerate(rows):
            for c in range(self.columns):
                self.cells[r][c].set(row[c] if c < len(row) else "")
        self._changed()

    def clear(self) -> None:
        for row in self.cells:
            for var in row:
                var.set("")

    def _on_paste(self, event):
        """Paste a whole block into the grid, not one cell.

        Two columns copied out of Excel arrive as tab-separated lines. Letting
        that land in a single cell would be useless, so it fills the grid and
        resizes to suit.
        """
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return None
        if "\n" not in text.strip() and "\t" not in text:
            return None                     # a single value - normal paste
        self.set_text(text)
        return "break"

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()


def _split(line: str) -> list:
    import re
    return re.split(r"[,;\t]| +", line.strip())
