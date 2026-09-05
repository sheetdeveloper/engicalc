"""The clickable symbol pad, with every button drawn as real notation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import mathrender
from .pad import GROUPS, by_group, common_items
from .widgets import ScrollFrame


class SymbolPad(ttk.Frame):
    """Compact row of common symbols, with a Full pad that expands below it.

    ``on_insert(item)`` is called when a button is pressed. The caller decides
    what to do: type the markup, or switch the operation selector.

    The grid reflows on resize. Buttons keep a constant size and the number of
    columns changes to suit the width, which is what a pad of keys should do -
    stretching a dozen buttons across a wide window leaves a row of letterboxes
    with a small glyph adrift in each.
    """

    CELL = 46           # fallback key width, before one has been measured
    GLYPH_SIZE = 13     # point size for a key's label
    GLYPH_WIDTH = 38    # widest a label may draw before it is scaled down
    MIN_COLUMNS = 8
    MAX_COLUMNS = 26
    FULL_HEIGHT = 190   # the expanded pad is capped and scrolls instead
    TOGGLE_ROOM = 120   # width reserved for the Full pad button beside it

    def __init__(self, master, on_insert, **kwargs):
        super().__init__(master, **kwargs)
        self.on_insert = on_insert
        self.columns = 12
        self._images: dict[str, tk.PhotoImage] = {}
        self._sections: list[tuple] = []     # (frame, [buttons]) to re-grid
        self._cell = None                    # measured key width
        self.expanded = tk.BooleanVar(value=False)

        self.compact = ttk.Frame(self)
        self.compact.pack(fill="x")
        self.keys = ttk.Frame(self.compact)
        self.keys.pack(side="left", fill="x", expand=True)

        toggle = ttk.Frame(self.compact)
        toggle.pack(side="right", padx=(8, 0), anchor="n")
        self.toggle_button = ttk.Button(toggle, text="Full pad  v", width=11,
                                        command=self.toggle)
        self.toggle_button.pack()

        self.full = ScrollFrame(self, height=self.FULL_HEIGHT)

        self._build_compact()
        self._build_full()
        self._regrid()          # _on_resize only acts on a *change*
        self.bind("<Configure>", self._on_resize)

    # -- construction -----------------------------------------------------
    def _image(self, item):
        """The key's glyph, drawn to fit a common box.

        Labels differ enormously in width - a definite integral with limits is
        three times the width of a pi. Since every key is the same size, the
        widest label would otherwise set that size for all of them, and the pad
        ends up a third of the window. Wide ones are redrawn smaller so they
        fit the same box.
        """
        if item.key not in self._images:
            try:
                size = self.GLYPH_SIZE
                image = mathrender.photo(item.label, size, "#1a1a1a")
                if image.width() > self.GLYPH_WIDTH:
                    size = max(7, int(size * self.GLYPH_WIDTH / image.width()))
                    image = mathrender.photo(item.label, size, "#1a1a1a")
                self._images[item.key] = image
            except Exception:  # noqa: BLE001 - fall back to the plain markup
                return None
        return self._images[item.key]

    def _button(self, master, item):
        image = self._image(item)
        if image is not None:
            button = ttk.Button(master, image=image, style="Pad.TButton",
                                command=lambda i=item: self.on_insert(i))
        else:
            button = ttk.Button(master, text=item.markup, width=5,
                                style="Pad.TButton",
                                command=lambda i=item: self.on_insert(i))
        _Tooltip(button, f"{item.name}\ntype:  {item.markup}")
        return button

    def _build_compact(self) -> None:
        buttons = [self._button(self.keys, item) for item in common_items()]
        self._sections.append((self.keys, buttons))

    def _build_full(self) -> None:
        for group in GROUPS:
            items = by_group().get(group, [])
            if not items:
                continue
            header = ttk.Label(self.full.body, text=group.upper(),
                               style="PadGroup.TLabel")
            header.pack(fill="x", padx=2, pady=(6, 1))
            frame = ttk.Frame(self.full.body)
            frame.pack(fill="x")
            self._sections.append(
                (frame, [self._button(frame, item) for item in items]))

    # -- layout -----------------------------------------------------------
    def _cell_width(self) -> int:
        """How wide a key actually is, measured rather than assumed.

        The glyphs differ in width and the theme adds its own padding, so a
        guessed constant is wrong by enough to matter: estimating low claims
        more columns than fit and the row runs off the edge of the window.
        """
        if self._cell is None:
            widths = [b.winfo_reqwidth()
                      for _frame, buttons in self._sections for b in buttons]
            self._cell = (max(widths) + 2) if widths else self.CELL
        return self._cell

    def _fit_columns(self, width: int) -> int:
        """How many keys fit across, leaving the Full pad button its corner."""
        cell = self._cell_width()
        usable = max(width - self.TOGGLE_ROOM, cell)
        return max(self.MIN_COLUMNS, min(self.MAX_COLUMNS, usable // cell))

    @staticmethod
    def _balanced(count: int, columns: int) -> int:
        """Even out the rows.

        Twenty-four keys in a pad twenty-two wide is a row of twenty-two and
        a row of two, which looks like a mistake. Filling the same rows evenly
        gives two rows of twelve.
        """
        if count <= columns:
            return count
        rows = -(-count // columns)             # ceiling division
        return -(-count // rows)

    def _on_resize(self, event=None) -> None:
        width = event.width if event is not None else self.winfo_width()
        if width <= 1:
            return
        columns = self._fit_columns(width)
        if columns != self.columns:
            self.columns = columns
            self._regrid()

    def _regrid(self) -> None:
        for frame, buttons in self._sections:
            columns = self._balanced(len(buttons), self.columns)
            for index, button in enumerate(buttons):
                button.grid(row=index // columns, column=index % columns,
                            padx=1, pady=1, sticky="nsew")
            # Keys are a fixed size and the slack goes to a spacer column on
            # the right. Letting the columns share the width instead makes
            # every key as wide as the window allows - a 95 pixel box with a
            # small glyph marooned in the middle of it.
            for column in range(self.MAX_COLUMNS + 1):
                frame.columnconfigure(
                    column,
                    weight=1 if column == columns else 0,
                    minsize=self._cell_width() if column < columns else 0,
                    uniform="pad" if column < columns else "")

    # -- behaviour --------------------------------------------------------
    def toggle(self) -> None:
        if self.expanded.get():
            self.full.pack_forget()
            self.toggle_button.configure(text="Full pad  v")
            self.expanded.set(False)
        else:
            self.full.pack(fill="x", pady=(6, 0))
            self.toggle_button.configure(text="Hide pad  ^")
            self.expanded.set(True)
            self.after_idle(self._regrid)


class _Tooltip:
    """Plain hover tooltip - Tk has no built-in one."""

    def __init__(self, widget, text: str, delay: int = 450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after = None
        self._window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after is not None:
            self.widget.after_cancel(self._after)
            self._after = None

    def _show(self):
        if self._window is not None:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        tk.Label(self._window, text=self.text, justify="left",
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Segoe UI", 9), padx=6, pady=3).pack()

    def _hide(self, _event=None):
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None
