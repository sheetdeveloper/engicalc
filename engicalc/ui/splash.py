"""The window that says what this is while the rest of it loads.

Two jobs. It says which version is running, which nothing in the app did -
you could not tell 1.3 from 1.4 with it open in front of you. And it covers
the second or so the formula library and matplotlib take to come up, which
otherwise looks like nothing happening.

Deliberately plain. A splash screen that lingers is an advertisement; this
one states what it is, shows what it is doing, and goes.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import __version__
from .widgets import ACCENT, LINE, MUTED, SURFACE

#: How long it stays up once the window behind it is ready, in milliseconds.
LINGER = 450

WIDTH, HEIGHT = 460, 260


class Splash(tk.Toplevel):
    """Shown while the window is built, closed once it is."""

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)          # no title bar; it is not a window
        self.configure(background=SURFACE)
        self._centre(master)

        # A hairline round the whole thing, since there is no frame to give
        # it an edge.
        border = tk.Frame(self, background=LINE)
        border.pack(fill="both", expand=True)
        body = tk.Frame(border, background=SURFACE)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Frame(body, background=ACCENT, height=4).pack(fill="x")

        tk.Label(body, text="EngiCalc", background=SURFACE, foreground=ACCENT,
                 font=("Segoe UI", 30, "bold")).pack(pady=(34, 0))
        tk.Label(body, text="equation solver, grapher and formula library",
                 background=SURFACE, foreground=MUTED,
                 font=("Segoe UI", 10)).pack(pady=(2, 0))
        tk.Label(body, text=f"Version {__version__}", background=SURFACE,
                 foreground="#1b1d21",
                 font=("Segoe UI", 11, "bold")).pack(pady=(18, 0))

        self.note = tk.Label(body, text="Starting...", background=SURFACE,
                             foreground=MUTED, font=("Segoe UI", 9))
        self.note.pack(side="bottom", pady=(0, 16))

        self.progress = ttk.Progressbar(body, mode="indeterminate",
                                        length=WIDTH - 120)
        self.progress.pack(side="bottom", pady=(0, 6))
        self.progress.start(12)

        # Clicking it should not be the only way out, but it should be a way
        # out - a splash screen that cannot be dismissed is an annoyance.
        for widget in (self, body, border):
            widget.bind("<Button-1>", lambda e: self.finish())
        self.update_idletasks()

    def _centre(self, master) -> None:
        master.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - WIDTH) // 2
        y = (screen_height - HEIGHT) // 2
        self.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def say(self, what: str) -> None:
        """Say what is being loaded, so the wait is accounted for."""
        try:
            self.note.configure(text=what)
            self.update_idletasks()
        except tk.TclError:
            pass                    # already gone; nothing to say it to

    def finish(self) -> None:
        try:
            self.progress.stop()
            self.destroy()
        except tk.TclError:
            pass
