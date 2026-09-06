"""Small shared Tk helpers."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

#: The page behind everything. Quiet, so the white cards on it read as
#: content rather than as another panel.
BG = "#f1f3f6"
#: Content sits on this.
SURFACE = "#ffffff"
#: Hairlines. A one pixel line separates things as well as a bevel does and
#: takes up a tenth of the room.
LINE = "#dcdfe5"
#: The accent, used on the control that does the work and on the heading
#: that says what a panel is - and nowhere else, so it keeps meaning that.
ACCENT = "#1f4e79"
ACCENT_LIGHT = "#2b6ca8"
ACCENT_SOFT = "#e8f0f9"
#: Text.
INK = "#1b1d21"
MUTED = "#6b7280"

_CACHE_ROOTS: dict = {}


def images_are_stale(owner: str) -> bool:
    """True when *owner*'s cached images belong to a root that has gone.

    A tk.PhotoImage is owned by one Tk interpreter. A cache that outlives its
    root holds dangling references, and using one raises an error about an
    image name or a destroyed application - neither of which points at the
    replaced interpreter that actually caused it. Callers clear their cache
    when this says so.
    """
    root = tk._default_root
    if _CACHE_ROOTS.get(owner, False) is root:
        return False
    _CACHE_ROOTS[owner] = root
    return True

MONO = ("Consolas", 10)
MONO_BIG = ("Consolas", 12)


def apply_theme(root: tk.Tk) -> None:
    """Style every widget class the app uses, from the palette above."""
    style = ttk.Style(root)
    # clam is the one that lets most of this be set at all; the native
    # themes ignore half of it.
    for candidate in ("clam", "vista", "aqua", "default"):
        if candidate in style.theme_names():
            style.theme_use(candidate)
            break

    style.configure(".", background=BG, foreground=INK,
                    font=("Segoe UI", 9))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("TCheckbutton", background=BG, foreground=INK)
    style.configure("TRadiobutton", background=BG, foreground=INK)
    style.map("TCheckbutton", background=[("active", BG)])
    style.map("TRadiobutton", background=[("active", BG)])

    # -- panels ----------------------------------------------------------
    # A hairline round the card and the title in the accent, rather than a
    # groove that eats four pixels on every side.
    style.configure("TLabelframe", background=BG, relief="solid",
                    borderwidth=1, bordercolor=LINE)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                    font=("Segoe UI", 9, "bold"))
    style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"),
                    foreground=ACCENT, background=BG)
    style.configure("Hint.TLabel", font=("Segoe UI", 8), foreground=MUTED,
                    background=BG)

    # -- the tab strip ---------------------------------------------------
    # Ten tabs need room to be told apart, and the selected one needs to
    # look like the page it opens rather than like its neighbours.
    style.configure("TNotebook", background=BG, borderwidth=0,
                    tabmargins=(2, 4, 2, 0))
    style.configure("TNotebook.Tab", background=BG, foreground=MUTED,
                    padding=(14, 7), borderwidth=0,
                    font=("Segoe UI", 9))
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE), ("active", ACCENT_SOFT)],
              foreground=[("selected", ACCENT), ("active", ACCENT)],
              font=[("selected", ("Segoe UI", 9, "bold"))],
              expand=[("selected", (0, 0, 0, 0))])

    # -- buttons ---------------------------------------------------------
    style.configure("TButton", background=SURFACE, foreground=INK,
                    bordercolor=LINE, lightcolor=SURFACE, darkcolor=SURFACE,
                    relief="solid", borderwidth=1, padding=(12, 5),
                    focusthickness=0, focuscolor="")
    style.map("TButton",
              background=[("pressed", "#e4e8ee"), ("active", ACCENT_SOFT)],
              bordercolor=[("active", ACCENT_LIGHT)],
              foreground=[("active", ACCENT)])

    # The one that does the work is filled, so it is obvious which it is.
    style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"),
                    background=ACCENT, foreground="#ffffff",
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    relief="solid", borderwidth=1, padding=(14, 5))
    style.map("Accent.TButton",
              background=[("pressed", "#17395a"), ("active", ACCENT_LIGHT)],
              bordercolor=[("active", ACCENT_LIGHT)],
              foreground=[("active", "#ffffff")])

    style.configure("TMenubutton", background=SURFACE, foreground=INK,
                    bordercolor=LINE, relief="solid", borderwidth=1,
                    padding=(12, 5))
    style.map("TMenubutton",
              background=[("active", ACCENT_SOFT)],
              foreground=[("active", ACCENT)])

    # -- fields ----------------------------------------------------------
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=SURFACE, background=SURFACE,
                        foreground=INK, bordercolor=LINE, lightcolor=LINE,
                        darkcolor=LINE, insertcolor=INK,
                        relief="solid", borderwidth=1, padding=(5, 3),
                        arrowcolor=MUTED)
        style.map(name,
                  bordercolor=[("focus", ACCENT_LIGHT)],
                  lightcolor=[("focus", ACCENT_LIGHT)],
                  darkcolor=[("focus", ACCENT_LIGHT)])
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)],
              arrowcolor=[("active", ACCENT)])

    # -- the symbol pad --------------------------------------------------
    # White keys with a hairline read as a keyboard; the theme's grey-on-grey
    # buttons at this size look like empty boxes. Padding is small because
    # the glyph is the label - there is no text needing room around it.
    style.configure("Pad.TButton", padding=(1, 2), relief="solid",
                    borderwidth=1, background=SURFACE, bordercolor=LINE,
                    lightcolor=SURFACE, darkcolor=SURFACE,
                    focusthickness=0, focuscolor="")
    style.map("Pad.TButton",
              background=[("pressed", "#d7e4f6"), ("active", ACCENT_SOFT)],
              bordercolor=[("active", ACCENT_LIGHT)],
              relief=[("pressed", "solid"), ("active", "solid")])
    style.configure("PadGroup.TLabel", font=("Segoe UI", 8, "bold"),
                    foreground=MUTED, background=BG)

    # -- lists and scrollbars ---------------------------------------------
    style.configure("Treeview", rowheight=24, background=SURFACE,
                    fieldbackground=SURFACE, foreground=INK,
                    bordercolor=LINE, borderwidth=1, relief="solid")
    style.configure("Treeview.Heading", background=BG, foreground=ACCENT,
                    font=("Segoe UI", 9, "bold"), relief="flat",
                    padding=(6, 4))
    style.map("Treeview.Heading", background=[("active", ACCENT_SOFT)])
    style.map("Treeview",
              background=[("selected", ACCENT_SOFT)],
              foreground=[("selected", ACCENT)])

    style.configure("Vertical.TScrollbar", background=BG, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED, relief="flat",
                    borderwidth=0)
    style.configure("Horizontal.TScrollbar", background=BG, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED, relief="flat",
                    borderwidth=0)
    for orientation in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.map(orientation,
                  background=[("active", "#c3c8d1"), ("!active", "#d5d9e0")])

    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", sashthickness=6, gripcount=0)

    _side_tabs(style)
    root.configure(background=BG)



#: Sub-tabs run down the left with an icon as well as a label. Set on the
#: notebook with style="Side.TNotebook".
def _side_tabs(style) -> None:
    """A notebook whose tabs run down the left-hand side.

    Only clam lets `tabposition` be set at all, which is why the app is on
    clam; the native themes draw their own tabs and ignore it.
    """
    style.configure("Side.TNotebook", tabposition="wn", background=BG,
                    borderwidth=0, tabmargins=(0, 4, 0, 0))
    style.configure("Side.TNotebook.Tab", background=BG, foreground=MUTED,
                    padding=(12, 9), borderwidth=0, anchor="w",
                    font=("Segoe UI", 9))
    style.map("Side.TNotebook.Tab",
              background=[("selected", SURFACE), ("active", ACCENT_SOFT)],
              foreground=[("selected", ACCENT), ("active", ACCENT)],
              font=[("selected", ("Segoe UI", 9, "bold"))])


class ScrollFrame(ttk.Frame):
    """A vertically scrollable frame; put content in ``.body``."""

    def __init__(self, master, height: int = 320, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0,
                                background=BG, height=height)
        self.scroll = ttk.Scrollbar(self, orient="vertical",
                                    command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body,
                                                 anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", lambda e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._bind_wheel(False))

    def _on_body(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, on: bool):
        if on:
            self.canvas.bind_all("<MouseWheel>", self._wheel)
            self.canvas.bind_all("<Button-4>", self._wheel)
            self.canvas.bind_all("<Button-5>", self._wheel)
        else:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

    def _wheel(self, event):
        delta = 0
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        elif event.delta:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()


class ReadOnlyText(tk.Text):
    """Text widget the user can select and copy from but not edit."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("wrap", "word")
        kwargs.setdefault("font", MONO)
        kwargs.setdefault("background", "white")
        kwargs.setdefault("relief", "solid")
        kwargs.setdefault("borderwidth", 1)
        super().__init__(master, **kwargs)
        self.configure(state="disabled")

    def set(self, text: str) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self.configure(state="disabled")

    def append(self, text: str) -> None:
        self.configure(state="normal")
        self.insert("end", text)
        self.configure(state="disabled")


class AsyncRunner:
    """Run slow SymPy work off the Tk thread and deliver the result safely."""

    def __init__(self, widget: tk.Misc, poll_ms: int = 60):
        self.widget = widget
        self.queue: queue.Queue = queue.Queue()
        self.poll_ms = poll_ms
        self._polling = False

    def run(self, func, on_success, on_error=None, on_finally=None):
        def worker():
            try:
                self.queue.put(("ok", func()))
            except Exception as exc:  # noqa: BLE001 - reported to the user
                self.queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self._start_poll(on_success, on_error, on_finally)

    def _start_poll(self, on_success, on_error, on_finally):
        def poll():
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                self.widget.after(self.poll_ms, poll)
                return
            try:
                if kind == "ok":
                    on_success(payload)
                elif on_error is not None:
                    on_error(payload)
                else:
                    raise payload
            finally:
                if on_finally is not None:
                    on_finally()

        self.widget.after(self.poll_ms, poll)


def labelled_entry(master, label: str, width: int = 12, value: str = "",
                   row: int | None = None, column: int = 0):
    """Return (frame, StringVar) laid out with grid if a row is given."""
    frame = ttk.Frame(master)
    ttk.Label(frame, text=label).pack(side="left")
    var = tk.StringVar(value=value)
    entry = ttk.Entry(frame, textvariable=var, width=width)
    entry.pack(side="left", padx=(4, 10))
    if row is not None:
        frame.grid(row=row, column=column, sticky="w", pady=2)
    return frame, var
