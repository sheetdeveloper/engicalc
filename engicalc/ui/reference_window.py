"""The reference window: every pad symbol, what to type, and a worked example.

The symbol table is drawn from plain frames rather than a ttk Treeview, because
Treeview row height is a theme-wide setting and the rendered symbols need room.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import mathrender
from .pad import GROUPS, SYNTAX_NOTES, find

ROW_BG = "#ffffff"
ROW_ALT = "#f6f7fa"
ROW_SELECTED = "#dce6f2"


class ReferenceWindow(tk.Toplevel):
    """Opened from Help. Lists every symbol with the markup that produces it."""

    def __init__(self, master, on_insert=None):
        super().__init__(master)
        self.title("Symbols and syntax")
        self.geometry("900x660")
        self.minsize(760, 520)
        self.on_insert = on_insert
        self._images: dict[str, tk.PhotoImage] = {}
        self._rows: dict[str, list] = {}
        self._items: list = []
        self._selected = None
        self._build()
        self.refresh()

    # -- layout -----------------------------------------------------------
    def _build(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        symbols = ttk.Frame(notebook, padding=8)
        notebook.add(symbols, text="  Symbols  ")

        bar = ttk.Frame(symbols)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=26)
        entry.pack(side="left", padx=6)
        entry.bind("<KeyRelease>", lambda e: self.refresh())
        ttk.Label(bar, text="Group").pack(side="left", padx=(12, 4))
        self.group_var = tk.StringVar(value="(all)")
        group = ttk.Combobox(bar, textvariable=self.group_var, width=20,
                             state="readonly", values=["(all)"] + GROUPS)
        group.pack(side="left")
        group.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="Double-click a row to type it into the calculator.",
                  style="Hint.TLabel").pack(side="right")

        head = tk.Frame(symbols, background="#1f4e79")
        head.pack(fill="x", pady=(8, 0))
        for text, width in (("Symbol", 12), ("Name", 24), ("What you type", 20),
                            ("Example", 30)):
            tk.Label(head, text=text, background="#1f4e79", foreground="white",
                     font=("Segoe UI", 9, "bold"), width=width, anchor="w",
                     padx=6, pady=4).pack(side="left")

        holder = ttk.Frame(symbols)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, background=ROW_BG, highlightthickness=1,
                                highlightbackground="#cccccc")
        scroll = ttk.Scrollbar(holder, orient="vertical",
                               command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, background=ROW_BG)
        self._window = self.canvas.create_window((0, 0), window=self.body,
                                                 anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._window, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._wheel(False))

        detail = ttk.Labelframe(symbols, text="Detail", padding=6)
        detail.pack(fill="x", pady=(8, 0))
        self.detail_math = mathrender.MathLabel(detail, fontsize=18, height=62)
        self.detail_math.pack(fill="x")
        self.detail_text = ttk.Label(detail, text="", wraplength=820,
                                     justify="left")
        self.detail_text.pack(anchor="w", pady=(4, 0))

        # -- syntax rules tab
        syntax = ttk.Frame(notebook, padding=4)
        notebook.add(syntax, text="  Syntax rules  ")
        rules_canvas = tk.Canvas(syntax, highlightthickness=0,
                                 background="#f7f7f9")
        rules_scroll = ttk.Scrollbar(syntax, orient="vertical",
                                     command=rules_canvas.yview)
        inner = ttk.Frame(rules_canvas)
        rules_canvas.create_window((0, 0), window=inner, anchor="nw")
        rules_canvas.configure(yscrollcommand=rules_scroll.set)
        rules_scroll.pack(side="right", fill="y")
        rules_canvas.pack(side="left", fill="both", expand=True)
        inner.bind("<Configure>", lambda e: rules_canvas.configure(
            scrollregion=rules_canvas.bbox("all")))
        ttk.Label(inner, text="How to type things",
                  style="Title.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        for heading, body in SYNTAX_NOTES:
            ttk.Label(inner, text=heading, font=("Segoe UI", 10, "bold"),
                      foreground="#1f4e79").pack(anchor="w", padx=12,
                                                 pady=(10, 2))
            ttk.Label(inner, text=body, wraplength=780,
                      justify="left").pack(anchor="w", padx=12)

        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0, 10))

    def _wheel(self, on: bool) -> None:
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            if on:
                self.canvas.bind_all(sequence, self._scroll)
            else:
                self.canvas.unbind_all(sequence)

    def _scroll(self, event) -> None:
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    # -- content ----------------------------------------------------------
    def refresh(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self._rows.clear()
        self._selected = None

        items = find(self.search_var.get())
        group = self.group_var.get()
        if group != "(all)":
            items = [i for i in items if i.group == group]
        self._items = items

        for index, item in enumerate(items):
            self._row(item, index)
        if items:
            self.select(items[0])

    def _row(self, item, index: int) -> None:
        background = ROW_BG if index % 2 == 0 else ROW_ALT
        row = tk.Frame(self.body, background=background, height=42)
        row.pack(fill="x")
        row.pack_propagate(False)

        symbol_cell = tk.Frame(row, background=background, width=108,
                               height=42)
        symbol_cell.pack(side="left")
        symbol_cell.pack_propagate(False)
        symbol = tk.Label(symbol_cell, background=background, anchor="w",
                          padx=6)
        image = self._symbol_image(item)
        if image is not None:
            symbol.configure(image=image)
        else:
            symbol.configure(text=item.markup, font=("Consolas", 10))
        symbol.pack(side="left", fill="both", expand=True)

        cells = [symbol, symbol_cell]
        for text, width, font in ((item.name, 22, ("Segoe UI", 10)),
                                  (item.markup, 20, ("Consolas", 10)),
                                  (item.example, 30, ("Consolas", 9))):
            label = tk.Label(row, text=text, background=background, width=width,
                             anchor="w", padx=6, font=font, foreground="#222222")
            label.pack(side="left")
            cells.append(label)
        cells.append(row)
        self._rows[item.key] = cells

        for widget in cells:
            widget.bind("<Button-1>", lambda e, i=item: self.select(i))
            widget.bind("<Double-1>", lambda e, i=item: self._insert(i))

    def _symbol_image(self, item):
        if item.key not in self._images:
            try:
                self._images[item.key] = mathrender.photo(item.label, 12,
                                                          "#111111", dpi=105)
            except Exception:  # noqa: BLE001
                return None
        return self._images[item.key]

    # -- selection --------------------------------------------------------
    def select(self, item) -> None:
        if self._selected is not None:
            for index, widget in enumerate(self._rows.get(self._selected.key, [])):
                original = ROW_BG if self._items.index(self._selected) % 2 == 0 \
                    else ROW_ALT
                widget.configure(background=original)
        self._selected = item
        for widget in self._rows.get(item.key, []):
            widget.configure(background=ROW_SELECTED)

        self.detail_math.show(item.example_latex or item.label, item.example)
        parts = [f"Type:   {item.markup}"]
        if item.example:
            parts.append(f"Example:   {item.example}")
        extra = []
        if item.operation:
            extra.append(f"Sets the operation selector to '{item.operation}'.")
        if item.note:
            extra.append(item.note)
        self.detail_text.configure(
            text="        ".join(parts) + ("\n" + "  ".join(extra) if extra else ""))

    def _insert(self, item) -> None:
        self.select(item)
        if self.on_insert is not None:
            self.on_insert(item)
