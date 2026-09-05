"""Render real mathematical notation inside the Tk window.

Matplotlib's mathtext engine draws a LaTeX subset to a PNG, and Tk 8.6 can load
PNG bytes directly, so we get proper fractions, radicals, integrals and Greek
letters without a TeX installation or any extra dependency.

Anything mathtext cannot draw (matrices, piecewise braces, unusual operators)
falls back to plain monospace text rather than showing an error.
"""

from __future__ import annotations

import base64
import io
import re
import tkinter as tk
from tkinter import ttk

import sympy as sp
from matplotlib.figure import Figure

# mathtext understands a subset of LaTeX. These rewrites cover what SymPy
# actually emits for the expressions this app produces.
_REWRITES = [
    (re.compile(r"\\operatorname\s*\{([^{}]*)\}"), r"\\mathrm{\1}"),
    (re.compile(r"\\text\s*\{([^{}]*)\}"), r"\\mathrm{\1}"),
    (re.compile(r"\\mathtt\s*\{([^{}]*)\}"), r"\\mathrm{\1}"),
    (re.compile(r"\\displaystyle"), ""),
    (re.compile(r"\\!"), ""),
    (re.compile(r"\\ "), " "),
]

# Constructs mathtext genuinely cannot draw - fall back to text if seen.
_UNSUPPORTED = re.compile(r"\\begin\{|\\end\{|\\substack|\\overbrace|\\underbrace")

_CACHE: dict[tuple, tk.PhotoImage] = {}
_MAX_CACHE = 400


class MathRenderError(ValueError):
    pass


def sanitise(latex: str) -> str:
    """Make SymPy's LaTeX safe for mathtext, or raise if it cannot be drawn."""
    text = latex.strip().strip("$")
    for pattern, replacement in _REWRITES:
        text = pattern.sub(replacement, text)
    if _UNSUPPORTED.search(text):
        raise MathRenderError("construct not supported by the renderer")
    return text


def to_latex(expr) -> str:
    """LaTeX for any SymPy object, including equations and relations."""
    if isinstance(expr, str):
        return expr
    return sp.latex(expr)


def render_png(latex: str, fontsize: int = 14, colour: str = "#111111",
               dpi: int = 130) -> bytes:
    """Draw ``latex`` and return PNG bytes."""
    body = sanitise(latex)
    figure = Figure(figsize=(0.05, 0.05), dpi=dpi)
    figure.patch.set_alpha(0.0)
    figure.text(0.0, 0.0, f"${body}$", fontsize=fontsize, color=colour)
    buffer = io.BytesIO()
    try:
        figure.savefig(buffer, format="png", dpi=dpi, transparent=True,
                       bbox_inches="tight", pad_inches=0.06)
    except Exception as exc:  # noqa: BLE001 - mathtext parse failure
        raise MathRenderError(str(exc)) from exc
    return buffer.getvalue()


def photo(latex: str, fontsize: int = 14, colour: str = "#111111",
          dpi: int = 130) -> tk.PhotoImage:
    """Cached Tk image for a LaTeX string."""
    key = (latex, fontsize, colour, dpi)
    image = _CACHE.get(key)
    if image is not None:
        return image
    data = base64.b64encode(render_png(latex, fontsize, colour, dpi))
    image = tk.PhotoImage(data=data)
    if len(_CACHE) > _MAX_CACHE:
        _CACHE.clear()
    _CACHE[key] = image
    return image


def available() -> bool:
    """True if the renderer works in this environment."""
    try:
        render_png("x^2")
        return True
    except Exception:  # noqa: BLE001
        return False


class MathLabel(ttk.Frame):
    """Shows one expression as typeset maths, with a plain-text fallback."""

    def __init__(self, master, fontsize: int = 15, colour: str = "#111111",
                 anchor: str = "w", background: str = "white",
                 height: int | None = None, **kwargs):
        super().__init__(master, **kwargs)
        self.fontsize = fontsize
        self.colour = colour
        self.anchor = anchor
        self._image = None
        self.canvas = tk.Canvas(self, highlightthickness=0, background=background,
                                height=height or int(fontsize * 3.0))
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._place())
        self._latex = ""
        self._fallback = ""

    def show(self, expr, fallback: str = "") -> None:
        """Display a SymPy object or a raw LaTeX string."""
        self._latex = to_latex(expr) if expr is not None else ""
        self._fallback = fallback or (str(expr) if expr is not None else "")
        self._place()

    def clear(self) -> None:
        self._latex = ""
        self._fallback = ""
        self.canvas.delete("all")

    def _place(self) -> None:
        self.canvas.delete("all")
        if not self._latex:
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        x = 8 if self.anchor == "w" else width / 2
        try:
            self._image = photo(self._latex, self.fontsize, self.colour)
            self.canvas.create_image(x, height / 2, image=self._image,
                                     anchor="w" if self.anchor == "w" else "center")
        except Exception:  # noqa: BLE001 - never let a display issue break a result
            self._image = None
            self.canvas.create_text(x, height / 2,
                                    anchor="w" if self.anchor == "w" else "center",
                                    text=self._fallback, font=("Consolas", 11),
                                    fill=self.colour)


class MathList(ttk.Frame):
    """A scrollable column of headings and typeset expressions (the steps panel)."""

    LINE_HEIGHT = 20

    def __init__(self, master, fontsize: int = 14, background: str = "white",
                 **kwargs):
        super().__init__(master, **kwargs)
        self.fontsize = fontsize
        self.canvas = tk.Canvas(self, background=background, highlightthickness=0,
                                borderwidth=1, relief="solid")
        self.scroll = ttk.Scrollbar(self, orient="vertical",
                                    command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Enter>", lambda e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._wheel(False))
        self._images: list = []

    def _wheel(self, on: bool) -> None:
        if on:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.bind_all(sequence, self._scroll)
        else:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.unbind_all(sequence)

    def _scroll(self, event) -> None:
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    def clear(self) -> None:
        self.canvas.delete("all")
        self._images.clear()

    def render(self, blocks) -> None:
        """``blocks`` is a sequence of (title, expr_or_None, detail_or_None)."""
        self.clear()
        y = 12
        for title, expr, detail in blocks:
            if title:
                self.canvas.create_text(12, y, anchor="nw", text=title,
                                        font=("Segoe UI", 10, "bold"),
                                        fill="#1f4e79")
                y += self.LINE_HEIGHT
            if expr is not None:
                y = self._draw_expression(expr, y)
            if detail:
                for line in str(detail).splitlines():
                    self.canvas.create_text(26, y, anchor="nw", text=line,
                                            font=("Segoe UI", 9), fill="#555555")
                    y += self.LINE_HEIGHT - 2
            y += 10
        self.canvas.configure(scrollregion=(0, 0, 10, y + 10))

    def _draw_expression(self, expr, y: int) -> int:
        try:
            image = photo(to_latex(expr), self.fontsize)
            self.canvas.create_image(26, y, image=image, anchor="nw")
            self._images.append(image)
            return y + image.height() + 6
        except Exception:  # noqa: BLE001
            from ..core.display import fmt
            self.canvas.create_text(26, y, anchor="nw", text=fmt(expr),
                                    font=("Consolas", 10), fill="#111111")
            return y + self.LINE_HEIGHT
