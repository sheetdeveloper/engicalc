"""The clickable symbol pad, with every button drawn as real notation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import mathrender
from .pad import GROUPS, PAD, by_group, common_items


class SymbolPad(ttk.Frame):
    """Compact row of common symbols, with a Full pad that expands below it.

    ``on_insert(item)`` is called when a button is pressed. The caller decides
    what to do: type the markup, or switch the operation selector.
    """

    def __init__(self, master, on_insert, columns: int = 12, **kwargs):
        super().__init__(master, **kwargs)
        self.on_insert = on_insert
        self.columns = columns
        self._images: dict[str, tk.PhotoImage] = {}
        self.expanded = tk.BooleanVar(value=False)

        self.compact = ttk.Frame(self)
        self.compact.pack(fill="x")
        self.full = ttk.Frame(self)

        self._build_compact()
        self._build_full()

    # -- construction -----------------------------------------------------
    def _image(self, item):
        if item.key not in self._images:
            try:
                self._images[item.key] = mathrender.photo(item.label, 13,
                                                          "#1a1a1a")
            except Exception:  # noqa: BLE001 - fall back to the plain markup
                return None
        return self._images[item.key]

    def _button(self, master, item, row: int, column: int) -> None:
        image = self._image(item)
        if image is not None:
            button = ttk.Button(master, image=image, width=3,
                                command=lambda i=item: self.on_insert(i))
        else:
            button = ttk.Button(master, text=item.markup, width=6,
                                command=lambda i=item: self.on_insert(i))
        button.grid(row=row, column=column, padx=2, pady=2, sticky="nsew")
        _Tooltip(button, f"{item.name}\ntype:  {item.markup}")

    def _build_compact(self) -> None:
        row = ttk.Frame(self.compact)
        row.pack(side="left", fill="x", expand=True)
        for index, item in enumerate(common_items()[:self.columns * 2]):
            self._button(row, item, index // self.columns, index % self.columns)
        for column in range(self.columns):
            row.columnconfigure(column, weight=1)

        toggle = ttk.Frame(self.compact)
        toggle.pack(side="right", padx=(8, 0))
        self.toggle_button = ttk.Button(toggle, text="Full pad  v", width=11,
                                        command=self.toggle)
        self.toggle_button.pack()

    def _build_full(self) -> None:
        for group in GROUPS:
            items = by_group().get(group, [])
            if not items:
                continue
            frame = ttk.Labelframe(self.full, text=group, padding=4)
            frame.pack(fill="x", pady=2)
            for index, item in enumerate(items):
                self._button(frame, item, index // self.columns,
                             index % self.columns)
            for column in range(self.columns):
                frame.columnconfigure(column, weight=1)

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
