"""Small shared Tk helpers."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

BG = "#f7f7f9"
ACCENT = "#1f4e79"
MONO = ("Consolas", 10)
MONO_BIG = ("Consolas", 12)


def apply_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    for candidate in ("clam", "vista", "aqua", "default"):
        if candidate in style.theme_names():
            style.theme_use(candidate)
            break
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG)
    style.configure("TLabelframe", background=BG)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                    font=("Segoe UI", 10, "bold"))
    style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"),
                    foreground=ACCENT, background=BG)
    style.configure("Hint.TLabel", font=("Segoe UI", 8), foreground="#666666",
                    background=BG)
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    # The symbol pad. White keys with a hairline border read as a keyboard;
    # the theme's default grey-on-grey buttons at this size just look like
    # empty boxes. Padding is small because the glyph inside is the label -
    # there is no text needing room around it.
    style.configure("Pad.TButton", padding=(1, 2), relief="flat",
                    background="#ffffff", bordercolor="#d4d4dc",
                    lightcolor="#ffffff", darkcolor="#ffffff",
                    focusthickness=0, focuscolor="")
    style.map("Pad.TButton",
              background=[("pressed", "#d7e4f6"), ("active", "#eef3fc")],
              bordercolor=[("active", "#8fb2e0")],
              relief=[("pressed", "flat"), ("active", "flat")])
    style.configure("PadGroup.TLabel", font=("Segoe UI", 8, "bold"),
                    foreground="#7a7a86", background=BG)

    style.configure("Treeview", rowheight=22)
    root.configure(background=BG)


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
