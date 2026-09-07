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
import textwrap
import tkinter as tk
from tkinter import ttk

import sympy as sp
from matplotlib.figure import Figure

from .widgets import LINE, images_are_stale

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
    """LaTeX for any SymPy object, including equations and relations.

    Goes through `core.display.latex` so a variable named dT is drawn as the
    ΔT it means, rather than as two letters.
    """
    if isinstance(expr, str):
        return expr
    from ..core.display import latex as _latex

    return _latex(expr)


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
    if images_are_stale(__name__):
        _CACHE.clear()
    image = _CACHE.get(key)
    if image is not None:
        return image
    data = base64.b64encode(render_png(latex, fontsize, colour, dpi))
    image = tk.PhotoImage(data=data)
    if len(_CACHE) > _MAX_CACHE:
        _CACHE.clear()
    _CACHE[key] = image
    return image


def render_calculation(blocks, fontsize: int = 15, dpi: int = 200,
                       width_inches: float = 6.5):
    """Draw a whole calculation as one picture, for pasting into a report.

    ``blocks`` is the same ``(heading, expression, detail)`` sequence the
    steps panel is built from, so the picture and the panel cannot show
    different things.

    Rendered at 200 dpi because a screen-resolution image looks soft once
    Word scales it onto a page. Returns a PIL image.
    """
    from PIL import Image

    figure = Figure(figsize=(width_inches, 100), dpi=dpi)
    figure.patch.set_facecolor("white")

    # Lay out top-down in figure coordinates, then crop to the ink at the
    # end - simpler than measuring every line twice to size the canvas.
    y = 0.995
    # One text line as a fraction of the tall canvas: points -> inches -> a
    # share of the 100 inch figure.
    line_gap = (fontsize / 72.0) / 100.0
    for heading, expression, detail in blocks:
        if heading:
            figure.text(0.02, y, heading, fontsize=fontsize * 0.72,
                        color="#1f4e79", va="top", weight="bold")
            y -= line_gap * 1.1
        if expression is not None:
            body = None
            try:
                body = sanitise(to_latex(expression))
            except Exception:                       # noqa: BLE001
                body = None
            if body:
                figure.text(0.05, y, f"${body}$", fontsize=fontsize,
                            color="#111111", va="top")
            else:
                figure.text(0.05, y, str(expression), fontsize=fontsize * 0.85,
                            color="#111111", va="top", family="monospace")
            y -= line_gap * 2.0
        if detail:
            # Wrapped, or one long note stretches the whole picture wider
            # than the page it is going onto - `bbox_inches="tight"` sizes
            # the canvas to whatever the widest line turns out to be.
            for source in str(detail).splitlines():
                for line in textwrap.wrap(source, width=78) or [""]:
                    figure.text(0.05, y, line, fontsize=fontsize * 0.68,
                                color="#555555", va="top")
                    y -= line_gap * 0.95
        y -= line_gap * 0.5

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, facecolor="white",
                   bbox_inches="tight", pad_inches=0.12)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


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

    def _fitted(self, room: int, tall: int):
        """The expression drawn at a size that fits the box it is in.

        Rendered once at the size asked for, and again smaller if it did
        not fit - scaled by how much it overran, so one retry lands rather
        than stepping down a point at a time. A cubic trendline is what
        turned this up: rendered at its asked-for size it ran off the
        right and the last term was simply not on screen.
        """
        drawn = photo(self._latex, self.fontsize, self.colour)
        if room < 40 or tall < 12:
            return drawn                       # not laid out yet
        over = max(drawn.width() / room, drawn.height() / tall)
        if over <= 1.0:
            return drawn
        smaller = max(self.SMALLEST, int(self.fontsize / over))
        if smaller >= self.fontsize:
            return drawn
        return photo(self._latex, smaller, self.colour)

    #: How small the type may get to fit an expression in. Past this the
    #: reader would need a magnifier, so it is better to clip and let them
    #: widen the window.
    SMALLEST = 8

    def _place(self) -> None:
        self.canvas.delete("all")
        if not self._latex:
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        x = 8 if self.anchor == "w" else width / 2
        try:
            self._image = self._fitted(width - 16, height - 4)
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
        # A canvas is not a ttk widget, so it does not pick the theme up; it
        # is given the same hairline the cards use rather than relief
        # "solid", which draws black.
        self.canvas = tk.Canvas(self, background=background, borderwidth=0,
                                highlightthickness=1,
                                highlightbackground=LINE,
                                highlightcolor=LINE)
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
