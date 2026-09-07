"""Browse the library as typeset formula cards.

A card is the fastest way to recognise a formula - you read the notation, not a
line of ASCII. Clicking one opens it in the Formula library tab, ready to solve.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme

from . import mathrender

CARD_WIDTH = 300
CARD_HEIGHT = 150
PAGE = 24


class CardsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.library = app.library
        self.shown = PAGE
        self._cards: list = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Formula cards", style="Title.TLabel").pack(side="left")

        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=32)
        entry.pack(side="left", padx=12)
        entry.bind("<KeyRelease>", lambda e: self.refresh(reset=True))
        ttk.Label(bar, text="Branch").pack(side="left", padx=(8, 4))
        self.branch_var = tk.StringVar(value="(all)")
        branches = ttk.Combobox(bar, textvariable=self.branch_var, width=24,
                                state="readonly",
                                values=["(all)"] + self.library.branches())
        branches.pack(side="left")
        branches.bind("<<ComboboxSelected>>", lambda e: self.refresh(reset=True))
        self.count_label = ttk.Label(bar, text="", style="Hint.TLabel")
        self.count_label.pack(side="left", padx=12)
        ttk.Label(bar, text="Click a card to open it",
                  style="Hint.TLabel").pack(side="right")

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas = tk.Canvas(holder, background=theme.colours()["bg"],
                                highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient="vertical",
                               command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body,
                                                 anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Enter>", lambda e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._wheel(False))

        self.more_button = ttk.Button(self, text="Show more",
                                      command=self.show_more)
        self.more_button.pack(pady=(8, 0))

    # -- scrolling --------------------------------------------------------
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

    def _on_resize(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        columns = max(1, event.width // (CARD_WIDTH + 12))
        if columns != getattr(self, "_columns", None):
            self._columns = columns
            self.refresh()

    # -- content ----------------------------------------------------------
    def matching(self) -> list:
        query = self.search_var.get().strip()
        formulas = self.library.search(query) if query else self.library.all()
        branch = self.branch_var.get()
        if branch != "(all)":
            formulas = [f for f in formulas if f.branch == branch]
        return formulas

    def refresh(self, reset: bool = False) -> None:
        if reset:
            self.shown = PAGE
        for child in self.body.winfo_children():
            child.destroy()
        self._cards.clear()

        formulas = self.matching()
        columns = getattr(self, "_columns", 3)
        for index, formula in enumerate(formulas[:self.shown]):
            self._card(formula, index // columns, index % columns)
        for column in range(columns):
            self.body.columnconfigure(column, weight=1, uniform="cards")

        total = len(formulas)
        self.count_label.configure(
            text=f"showing {min(self.shown, total)} of {total}")
        if total > self.shown:
            self.more_button.pack(pady=(8, 0))
        else:
            self.more_button.pack_forget()

    def show_more(self) -> None:
        self.shown += PAGE
        self.refresh()

    def retheme(self) -> None:
        """Recolour the page and lay the cards out again in the new ink."""
        self.canvas.configure(background=theme.colours()["bg"])
        self.refresh()

    def _card(self, formula, row: int, column: int) -> None:
        palette = theme.colours()
        surface, line = palette["surface"], palette["line"]
        card = tk.Frame(self.body, background=surface, highlightthickness=1,
                        highlightbackground=line, width=CARD_WIDTH,
                        height=CARD_HEIGHT)
        card.grid(row=row, column=column, padx=6, pady=6, sticky="nsew")
        card.grid_propagate(False)

        # The title strip and the footer sit a shade off the card so the
        # equation between them is the thing the eye lands on.
        strip = theme.mix(surface, palette["bg"], 0.6)
        title = tk.Label(card, text=formula.name, background=strip,
                         foreground=palette["muted"], font=("Segoe UI", 9),
                         anchor="center", pady=5)
        title.pack(fill="x")

        math = mathrender.MathLabel(card, fontsize=16, height=CARD_HEIGHT - 60,
                                    anchor="center", background=surface)
        math.pack(fill="both", expand=True)
        math.show(formula.display_latex, formula.equation)

        footer = tk.Label(card, text=formula.branch, background=surface,
                          foreground=palette["muted"], font=("Segoe UI", 8),
                          pady=3)
        footer.pack(fill="x")

        accent = palette["accent"]
        for widget in (card, title, footer, math, math.canvas):
            widget.bind("<Button-1>", lambda e, f=formula: self._open(f))
            widget.bind("<Enter>", lambda e, c=card, a=accent:
                        c.configure(highlightbackground=a))
            widget.bind("<Leave>", lambda e, c=card, l=line:
                        c.configure(highlightbackground=l))
        self._cards.append(card)

    def _open(self, formula) -> None:
        self.app.open_formula(formula)
