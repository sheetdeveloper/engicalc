"""Structured, typeset equation entry - the maths bar itself, not a preview.

A definite integral inserted from the pad appears as a real integral sign with
empty boxes at the limits, and the limits are typed straight into those boxes.
The same holds for fractions, powers, roots and logs: the shape is drawn, the
values are typed where they belong.

How it works
------------
The field holds a small tree - :class:`Row` is a run of characters and nested
:class:`Group` templates, and every ``Group`` owns one ``Row`` per slot. The
tree renders to LaTeX, matplotlib's mathtext rasterises it, and the bitmap is
drawn on a Canvas. Empty slots draw as a filled square.

The caret is placed by rendering a *second* copy of the expression with a marker
glyph at the cursor and reading the marker's position out of mathtext's layout.
Everything before the marker is laid out as if the marker were not there, so the
position it reports is the right one for the image actually on screen.

Coordinates from both mathtext parsers are pixels at the dpi passed in, and
``oy`` is measured from the baseline upwards, so the baseline sits
``height - depth`` down from the top of the bitmap.

The tree compiles back to the plain ASCII that :mod:`core.parsing` already
accepts, plus - for the calculus templates - the operation and its limits, so
the engine is unchanged.
"""

from __future__ import annotations

import base64
import io
import re
import tkinter as tk
from dataclasses import dataclass, field

import numpy as np
import sympy as sp
from matplotlib import mathtext
from matplotlib.font_manager import FontProperties

from ..core.parsing import SAFE_FUNCTIONS

DPI = 130
# A hollow box reads as "type here"; mathtext has no \square or \Box, but it
# draws the literal character happily.
PLACEHOLDER = "□"
PLACEHOLDER_CP = ord(PLACEHOLDER)
CARET_MARK = "|"
CARET_CP = ord("|")

# Characters drawn as proper notation rather than literally.
_CHAR_LATEX = {
    "*": r"\cdot ",
    "<=": r"\leq ",
    ">=": r"\geq ",
    "!=": r"\neq ",
}

_GREEK_SET = set((
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda_ mu nu xi "
    "pi rho sigma tau phi chi psi omega Delta Omega Sigma Phi Gamma"
).split())

# Drawn upright. Taken from the parser so the two cannot disagree about what
# counts as a function.
_FUNCTION_NAMES = frozenset(SAFE_FUNCTIONS)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Template:
    """A shape with holes in it.

    ``latex`` and ``text`` use ``@0@``, ``@1@`` ... to mark where each slot's
    contents drop in. ``operation`` marks the calculus templates, which stand
    for the whole input and drive the operation selector; ``extras`` maps a
    :func:`core.engine.calculate` keyword to the slot that fills it.
    """

    key: str
    latex: str
    text: str
    slots: tuple[str, ...]
    operation: str = ""
    main: int = 0
    extras: tuple[tuple[str, int], ...] = ()
    # Slots whose contents need brackets in the compiled text unless they are
    # already a single atom. Only the shapes that lose their grouping when
    # flattened need this - `a+b` over `c` must not compile to `a+b/c`, while
    # anything written as a function call brings its own brackets.
    wrap: tuple[int, ...] = ()

    @property
    def count(self) -> int:
        return len(self.slots)


TEMPLATES: dict[str, Template] = {t.key: t for t in [
    # -- inline: nest anywhere, compile to ordinary ASCII ------------------
    Template("frac", r"\frac{@0@}{@1@}", "@0@/@1@",
             ("numerator", "denominator"), wrap=(0, 1)),
    Template("power", r"{@0@}^{@1@}", "@0@^@1@", ("base", "exponent"),
             wrap=(0, 1)),
    Template("subscript", r"{@0@}_{@1@}", "@0@_@1@", ("symbol", "subscript")),
    Template("sqrt", r"\sqrt{@0@}", "sqrt(@0@)", ("radicand",)),
    Template("nthroot", r"\sqrt[@0@]{@1@}", "root(@1@, @0@)",
             ("index", "radicand")),
    Template("logbase", r"\log_{@0@}\left(@1@\right)", "log(@1@, @0@)",
             ("base", "argument")),
    Template("exp", r"e^{@0@}", "exp(@0@)", ("exponent",)),
    Template("abs", r"\left|@0@\right|", "abs(@0@)", ("expression",)),
    Template("paren", r"\left(@0@\right)", "(@0@)", ("expression",)),

    # -- calculus: stand for the whole input -------------------------------
    Template("defint", r"\int_{@0@}^{@1@}@2@\,d@3@", "@2@",
             ("lower limit", "upper limit", "integrand", "variable"),
             operation="integral", main=2,
             extras=(("lower", 0), ("upper", 1), ("variable", 3))),
    Template("indefint", r"\int @0@\,d@1@", "@0@",
             ("integrand", "variable"),
             operation="integral", main=0, extras=(("variable", 1),)),
    Template("deriv", r"\frac{d}{d@1@}\left(@0@\right)", "@0@",
             ("expression", "variable"),
             operation="derivative", main=0, extras=(("variable", 1),)),
    Template("limit", r"\lim_{@1@ \to @2@}@0@", "@0@",
             ("expression", "variable", "point"),
             operation="limit", main=0,
             extras=(("variable", 1), ("point", 2))),
]}


# --------------------------------------------------------------------------
# The document tree
# --------------------------------------------------------------------------
# Both compare by identity, not by value. Tab order and "which group owns this
# row" are found with .index() and `in`, and two rows holding the same thing -
# the x over x in a fraction, say - are emphatically not the same row.
@dataclass(eq=False)
class Group:
    template: Template
    rows: list = field(default_factory=list)


@dataclass(eq=False)
class Row:
    """A run of single characters and nested groups."""

    items: list = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.items


def new_group(template: Template) -> Group:
    return Group(template, [Row() for _ in range(template.count)])


def walk_rows(row: Row) -> list:
    """Every row in the tree, depth first - the order Tab moves through."""
    out = [row]
    for item in row.items:
        if isinstance(item, Group):
            for sub in item.rows:
                out.extend(walk_rows(sub))
    return out


def _word_to_latex(word: str) -> str:
    """One run of letters: a Greek name, a function name, or a variable.

    Function names are set upright, as they are everywhere else in the app -
    ``sin(x)`` should not read as three variables multiplied together.
    Variables are left alone so they stay italic, which is what they should be.
    """
    if word in _GREEK_SET:
        return "\\" + word.rstrip("_") + " "
    if word in _FUNCTION_NAMES:
        return r"\mathrm{" + word + "}"
    return word


def _chars_to_latex(chars: str) -> str:
    out = chars
    for plain, drawn in _CHAR_LATEX.items():
        out = out.replace(plain, drawn)
    # Split into letter runs and everything else, so that "theta" is one word
    # rather than something containing "eta", and "sin" is only a function when
    # it stands alone.
    # Trailing digits stay attached so log10, log2 and atan2 survive whole.
    return "".join(_word_to_latex(part) if part[:1].isalpha() else part
                   for part in re.split(r"([A-Za-z]+[0-9]*_?)", out) if part)


def _fill(pattern: str, parts: list) -> str:
    for index, value in enumerate(parts):
        pattern = pattern.replace(f"@{index}@", value)
    return pattern


def to_latex(row: Row, caret_row: Row | None = None,
             caret_index: int = 0) -> str:
    """Render the tree. ``caret_row`` gets the caret marker at ``caret_index``."""
    if row.is_empty():
        return CARET_MARK if row is caret_row else PLACEHOLDER

    pieces: list = []
    pending: list = []

    def flush() -> None:
        if pending:
            pieces.append(_chars_to_latex("".join(pending)))
            pending.clear()

    for index, item in enumerate(row.items):
        if row is caret_row and index == caret_index:
            flush()
            pieces.append(CARET_MARK)
        if isinstance(item, Group):
            flush()
            pieces.append(_fill(item.template.latex,
                                [to_latex(r, caret_row, caret_index)
                                 for r in item.rows]))
        else:
            pending.append(item)
    flush()
    if row is caret_row and caret_index >= len(row.items):
        pieces.append(CARET_MARK)
    return "".join(pieces)


def _balanced(text: str) -> bool:
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _is_atom(text: str) -> bool:
    """True when *text* already binds tightly enough to skip brackets."""
    stripped = text.strip()
    if not stripped:
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped):       # x, T_1, rho
        return True
    if re.fullmatch(r"\d+(\.\d+)?", stripped):                  # 2, 1.5
        return True
    if re.fullmatch(r"[A-Za-z_]\w*\(.*\)", stripped) and _balanced(stripped):
        return True                                             # sin(x)
    if stripped.startswith("(") and stripped.endswith(")") and \
            _balanced(stripped[1:-1]):                          # (a + b)
        return True
    return False


def to_text(row: Row) -> str:
    """Compile to the ASCII the parser accepts.

    Slots listed in a template's ``wrap`` get brackets unless they are already
    a single atom, so a power reads ``2x^2`` rather than ``2(x)^(2)`` while
    ``a+b`` over ``c`` still compiles to ``(a+b)/c``.
    """
    if row.is_empty():
        return ""
    out: list = []
    for item in row.items:
        if isinstance(item, Group):
            parts = []
            for index, slot in enumerate(item.rows):
                text = to_text(slot)
                if index in item.template.wrap and not _is_atom(text):
                    text = f"({text})"
                parts.append(text)
            out.append(_fill(item.template.text, parts))
        else:
            out.append(item)
    return "".join(out)


@dataclass
class Compiled:
    """What the field hands to :func:`core.engine.calculate`."""

    text: str
    operation: str = ""
    extras: dict = field(default_factory=dict)


def compile_row(row: Row) -> Compiled:
    """Compile, lifting a whole-input calculus template into an operation."""
    if len(row.items) == 1 and isinstance(row.items[0], Group):
        group = row.items[0]
        template = group.template
        if template.operation:
            extras = {name: to_text(group.rows[i])
                      for name, i in template.extras}
            return Compiled(to_text(group.rows[template.main]),
                            template.operation, extras)
    return Compiled(to_text(row))


def row_from_text(text: str) -> Row:
    """A flat row of characters - the fallback when text will not parse."""
    return Row([ch for ch in text])


# --------------------------------------------------------------------------
# Text -> tree
#
# Typed ASCII becomes real structure, so `sqrt(x)` typed into the plain box
# draws as a radical with an editable box under it rather than as three
# letters. SymPy does the parsing (the whitelist still applies); this walks the
# result and picks the template that matches each node.
#
# `parse_for_display` parses with evaluate=False, so the tree stays close to
# what was typed. Two shapes to know: `a/b` arrives as Mul(a, Pow(b, -1)), and
# `sqrt(x)` as Pow(x, Rational(1, 2)).
# --------------------------------------------------------------------------
def _is_compound(expr) -> bool:
    """True for anything that needs brackets before it can be a power base."""
    return expr.is_Add or expr.is_Mul or (expr.is_Pow and not _is_root(expr))


def _is_root(expr) -> bool:
    return (expr.is_Pow and expr.exp.is_Rational and expr.exp.is_positive
            and expr.exp.p == 1)


def _group(key: str, *rows: Row) -> Group:
    group = new_group(TEMPLATES[key])
    for index, row in enumerate(rows):
        group.rows[index] = row
    return group


def _split_factors(expr):
    """Mul -> (numerator factors, denominator factors)."""
    numerator, denominator = [], []
    for factor in expr.args:
        if (factor.is_Pow and factor.exp.is_Number and factor.exp.is_negative):
            base, power = factor.base, -factor.exp
            denominator.append(base if power == 1 else sp.Pow(base, power,
                                                              evaluate=False))
        else:
            numerator.append(factor)
    return numerator, denominator


def _row_of_factors(factors: list) -> Row:
    """Juxtapose factors, keeping an explicit * wherever dropping it would
    change the meaning - `xy` is one symbol, `2x` is not."""
    if not factors:
        return row_from_text("1")
    row = Row()
    # A coefficient of -1 is a minus sign, not the digits "-1".
    if len(factors) > 1 and factors[0] == -1:
        row.items.append("-")
        factors = factors[1:]
    for index, factor in enumerate(factors):
        if index:
            previous = factors[index - 1]
            if not (previous.is_Number and not factor.is_Number):
                row.items.append("*")
        _append(row, factor, bracket_add=True)
    return row


def _build_row(expr, bracket_add: bool = False) -> Row:
    row = Row()
    _append(row, expr, bracket_add)
    return row


def _append(row: Row, expr, bracket_add: bool = False) -> None:
    if expr.is_Symbol:
        name = expr.name
        if "_" in name and name.count("_") == 1 and all(name.split("_")):
            base, sub = name.split("_")
            row.items.append(_group("subscript", row_from_text(base),
                                    row_from_text(sub)))
        else:
            row.items.extend(name)
        return

    if expr.is_Rational and not expr.is_Integer:
        row.items.append(_group("frac", row_from_text(str(expr.p)),
                                row_from_text(str(expr.q))))
        return

    if expr.is_Number or expr.is_NumberSymbol:
        row.items.extend(str(expr))
        return

    if expr.is_Add:
        if bracket_add:
            row.items.append(_group("paren", _build_row(expr)))
            return
        for index, term in enumerate(expr.args):
            negative = term.is_Mul and term.args[0].is_Number \
                and term.args[0].is_negative
            if negative:
                term = sp.Mul(*([-term.args[0]] + list(term.args[1:])),
                              evaluate=False) if term.args[0] != -1 \
                    else sp.Mul(*term.args[1:], evaluate=False)
            if index:
                row.items.append("-" if negative else "+")
            elif negative:
                row.items.append("-")
            _append(row, term)
        return

    if expr.is_Mul:
        numerator, denominator = _split_factors(expr)
        if denominator:
            row.items.append(_group("frac", _row_of_factors(numerator),
                                    _row_of_factors(denominator)))
            return
        row.items.extend(_row_of_factors(numerator).items)
        return

    if expr.is_Pow:
        base, power = expr.base, expr.exp
        if power == sp.Rational(1, 2):
            row.items.append(_group("sqrt", _build_row(base)))
            return
        if power.is_Rational and power.is_positive and power.p == 1:
            row.items.append(_group("nthroot", row_from_text(str(power.q)),
                                    _build_row(base)))
            return
        if power.is_Number and power.is_negative:
            inner = base if power == -1 else sp.Pow(base, -power, evaluate=False)
            row.items.append(_group("frac", row_from_text("1"),
                                    _build_row(inner)))
            return
        base_row = _build_row(base, bracket_add=True) if not _is_compound(base) \
            else Row([_group("paren", _build_row(base))])
        row.items.append(_group("power", base_row, _build_row(power)))
        return

    if isinstance(expr, sp.exp):
        row.items.append(_group("exp", _build_row(expr.args[0])))
        return

    if isinstance(expr, sp.Abs):
        row.items.append(_group("abs", _build_row(expr.args[0])))
        return

    if isinstance(expr, sp.log) and len(expr.args) == 2:
        row.items.append(_group("logbase", _build_row(expr.args[1]),
                                _build_row(expr.args[0])))
        return

    if isinstance(expr, sp.Function) or expr.is_Function:
        row.items.extend(type(expr).__name__)
        inner = Row()
        for index, argument in enumerate(expr.args):
            if index:
                inner.items.extend(", ")
            _append(inner, argument)
        row.items.append(_group("paren", inner))
        return

    if isinstance(expr, sp.Eq):
        _append(row, expr.lhs)
        row.items.append("=")
        _append(row, expr.rhs)
        return

    # Anything unrecognised still has to appear, so fall back to its text.
    row.items.extend(_display_text(expr))


def _display_text(expr) -> str:
    from ..core.display import fmt

    try:
        return fmt(expr)
    except Exception:                                   # noqa: BLE001
        return str(expr)


def row_from_expression(expr) -> Row:
    """Build an editable tree from a parsed SymPy expression."""
    return _build_row(expr)


def structured_row(text: str) -> Row:
    """Text to tree, falling back to flat characters if it will not parse.

    Half-typed input is the normal case while someone is still typing, so a
    parse failure is not an error - it just means no structure yet.
    """
    from ..core.parsing import parse_for_display

    if not text.strip():
        return Row()
    try:
        row = row_from_expression(parse_for_display(text))
    except Exception:                                   # noqa: BLE001
        return row_from_text(text)
    return row if row.items else row_from_text(text)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
_IMAGE_CACHE: dict = {}
_MAX_CACHE = 300


def _hex_to_rgb(colour: str):
    value = colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def render(latex: str, fontsize: int, colour: str = "#111111", dpi: int = DPI):
    """Rasterise ``latex``. Returns (PhotoImage, width, height, baseline)."""
    key = (latex, fontsize, colour, dpi)
    hit = _IMAGE_CACHE.get(key)
    if hit is not None:
        return hit

    from PIL import Image  # installed as a matplotlib dependency

    parse = mathtext.MathTextParser("agg").parse(
        f"${latex}$", dpi=dpi, prop=FontProperties(size=fontsize))
    ink = np.asarray(parse.image, dtype=np.uint8)
    height, width = ink.shape
    red, green, blue = _hex_to_rgb(colour)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = red, green, blue
    rgba[..., 3] = ink

    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, format="PNG")
    photo = tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))

    if len(_IMAGE_CACHE) > _MAX_CACHE:
        _IMAGE_CACHE.clear()
    result = (photo, width, height, parse.height - parse.depth)
    _IMAGE_CACHE[key] = result
    return result


def caret_position(latex_with_caret: str, fontsize: int, dpi: int = DPI):
    """Where the caret marker landed: (x, y_above_baseline, glyph_fontsize).

    Everything ahead of the marker is laid out as if it were not there, so the
    x it reports is correct for the image drawn without it.
    """
    _w, _h, _d, glyphs, _rects = mathtext.MathTextParser("path").parse(
        f"${latex_with_caret}$", dpi=dpi, prop=FontProperties(size=fontsize))
    for glyph in glyphs:
        if int(glyph[2]) == CARET_CP:
            return float(glyph[4]), float(glyph[5]), float(glyph[1])
    return None


def slot_positions(latex: str, fontsize: int, dpi: int = DPI) -> list:
    """Pixel centres of the empty slots, in the order the rows appear."""
    _w, _h, _d, glyphs, _rects = mathtext.MathTextParser("path").parse(
        f"${latex}$", dpi=dpi, prop=FontProperties(size=fontsize))
    return [(float(g[4]), float(g[5]), float(g[1]))
            for g in glyphs if int(g[2]) == PLACEHOLDER_CP]


# --------------------------------------------------------------------------
# The widget
# --------------------------------------------------------------------------
class MathField(tk.Canvas):
    """An equation bar you type into, drawn as real notation.

    ``on_change`` fires after any edit (the calculator keeps its plain-text box
    in step with it); ``on_submit`` fires on Return.
    """

    PAD_X = 10

    def __init__(self, master, on_change=None, on_submit=None,
                 fontsize: int = 17, colour: str = "#111111",
                 background: str = "#ffffff", height: int = 62, **kwargs):
        super().__init__(master, height=height, background=background,
                         highlightthickness=1, highlightbackground="#c8c8d0",
                         highlightcolor="#4a76c8", takefocus=True, **kwargs)
        self.fontsize = fontsize
        self.colour = colour
        self.on_change = on_change
        self.on_submit = on_submit

        self.root_row = Row()
        self.caret_row = self.root_row
        self.caret_index = 0

        self._image = None
        self._image_origin = (self.PAD_X, 0)
        self._image_baseline = 0.0
        self._image_width = 0
        self._quiet = False          # set while syncing in from the text box
        self._scroll_x = 0.0         # horizontal offset for long expressions
        self._targets = []           # every caret position, for click-to-place
        self._targets_key = None     # the layout those positions belong to

        self.bind("<Button-1>", self._on_click)
        self.bind("<FocusIn>", lambda e: self._redraw())
        self.bind("<FocusOut>", lambda e: self._redraw())
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", self._on_wheel)
        self.bind("<Button-5>", self._on_wheel)
        self.bind("<KeyPress>", self._on_key)
        for sequence, handler in (
                ("<BackSpace>", self._on_backspace),
                ("<Delete>", self._on_delete),
                ("<Left>", lambda e: self._step(-1)),
                ("<Right>", lambda e: self._step(1)),
                ("<Home>", lambda e: self._to_edge(0)),
                ("<End>", lambda e: self._to_edge(1)),
                ("<Tab>", lambda e: self._hop(1)),
                ("<Shift-Tab>", lambda e: self._hop(-1)),
                ("<Return>", self._on_return)):
            self.bind(sequence, handler)
        self._redraw()

    # -- content ----------------------------------------------------------
    def clear(self) -> None:
        self.root_row = Row()
        self.caret_row = self.root_row
        self.caret_index = 0
        self._changed()

    def get_text(self) -> str:
        return to_text(self.root_row)

    def compiled(self) -> Compiled:
        return compile_row(self.root_row)

    def set_text(self, text: str) -> None:
        """Replace the contents with typed text, without re-notifying.

        The text is turned into real structure where it parses, so `sqrt(x)`
        typed into the plain box arrives here as a radical with an editable
        box under it.
        """
        if to_text(self.root_row) == text:
            return
        self._quiet = True
        try:
            self.root_row = structured_row(text)
            self.caret_row = self.root_row
            self.caret_index = len(self.root_row.items)
            self._redraw()
        finally:
            self._quiet = False

    def insert_text(self, text: str) -> None:
        for ch in text:
            self.caret_row.items.insert(self.caret_index, ch)
            self.caret_index += 1
        self._changed()

    def insert_template(self, key: str) -> None:
        """Drop a template in at the caret and move into its first slot."""
        template = TEMPLATES.get(key)
        if template is None:
            return
        group = new_group(template)

        if template.operation:
            # The calculus templates stand for the whole input. Anything
            # already typed becomes the expression being operated on.
            existing = self.root_row.items[:]
            self.root_row = Row([group])
            if existing:
                group.rows[template.main] = Row(existing)
        else:
            self.caret_row.items.insert(self.caret_index, group)

        first = self._first_empty(group) or group.rows[0]
        self.caret_row = first
        self.caret_index = len(first.items)
        self._changed()

    @staticmethod
    def _first_empty(group: Group):
        for row in group.rows:
            if row.is_empty():
                return row
        return None

    # -- navigation -------------------------------------------------------
    def _rows(self) -> list:
        return walk_rows(self.root_row)

    def _hop(self, direction: int):
        rows = self._rows()
        try:
            index = rows.index(self.caret_row)
        except ValueError:
            index = 0
        target = rows[(index + direction) % len(rows)]
        self.caret_row = target
        self.caret_index = len(target.items) if direction < 0 else 0
        self._redraw()
        return "break"

    def _step(self, direction: int):
        new_index = self.caret_index + direction
        if 0 <= new_index <= len(self.caret_row.items):
            self.caret_index = new_index
            self._redraw()
            return "break"
        return self._hop(direction)

    def _to_edge(self, end: int):
        self.caret_index = len(self.caret_row.items) if end else 0
        self._redraw()
        return "break"

    # -- editing ----------------------------------------------------------
    def _on_key(self, event):
        if event.state & 0x0004:            # Control held - not our business
            return None
        char = event.char
        if not char or not char.isprintable():
            return None
        self.caret_row.items.insert(self.caret_index, char)
        self.caret_index += 1
        self._changed()
        return "break"

    def _on_backspace(self, event):
        if self.caret_index > 0:
            previous = self.caret_row.items[self.caret_index - 1]
            if isinstance(previous, Group):
                # Step into the shape rather than swallowing it whole. One
                # press should not be able to remove a whole fraction, and
                # deleting it from the inside empties it first - at which
                # point the branch below takes it away.
                target = previous.rows[-1]
                self.caret_row = target
                self.caret_index = len(target.items)
                self._redraw()
                return "break"
            self.caret_row.items.pop(self.caret_index - 1)
            self.caret_index -= 1
            self._changed()
            return "break"
        # At the head of a slot: drop the whole group if it is empty.
        owner = self._owner_of(self.caret_row)
        if owner is not None:
            parent, group = owner
            if all(r.is_empty() for r in group.rows):
                position = parent.items.index(group)
                parent.items.pop(position)
                self.caret_row = parent
                self.caret_index = position
                self._changed()
                return "break"
        return self._hop(-1)

    def _on_delete(self, event):
        if self.caret_index < len(self.caret_row.items):
            item = self.caret_row.items[self.caret_index]
            if isinstance(item, Group):
                # Same as backspace: a whole shape is not one keystroke's
                # worth of deletion. An equation that is a single fraction
                # or integral would otherwise vanish at one press.
                target = item.rows[0]
                self.caret_row = target
                self.caret_index = 0
                self._redraw()
                return "break"
            self.caret_row.items.pop(self.caret_index)
            self._changed()
        return "break"

    def _owner_of(self, row: Row):
        """(parent row, group) for the group *row* is a slot of, if any."""
        def search(current: Row):
            for item in current.items:
                if isinstance(item, Group):
                    if row in item.rows:
                        return current, item
                    for sub in item.rows:
                        found = search(sub)
                        if found:
                            return found
            return None
        return search(self.root_row)

    def _on_return(self, event):
        if self.on_submit:
            self.on_submit()
        return "break"

    def _changed(self) -> None:
        self._redraw()
        if self.on_change and not self._quiet:
            self.on_change()

    # -- drawing ----------------------------------------------------------
    def _caret_targets(self) -> list:
        """Every place the caret can sit, as (row, index, x, y).

        Found by asking the layout where the caret marker lands for each
        candidate position in turn - about 150 ms for a typical expression,
        so it is computed once per layout and kept until the content changes.
        That is what makes clicking into the middle of something already
        typed work, rather than only being able to hit an empty box.
        """
        key = to_latex(self.root_row)
        if self._targets_key == key:
            return self._targets

        targets = []
        for row in self._rows():
            for index in range(len(row.items) + 1):
                try:
                    spot = caret_position(
                        to_latex(self.root_row, row, index), self.fontsize)
                except Exception:                   # noqa: BLE001
                    spot = None
                if spot is not None:
                    targets.append((row, index, spot[0], spot[1]))
        self._targets_key = key
        self._targets = targets
        return targets

    def _on_click(self, event):
        self.focus_set()
        targets = self._caret_targets()
        if not targets:
            self.caret_row = self.root_row
            self.caret_index = len(self.root_row.items)
            self._redraw()
            return "break"

        origin_x, origin_y = self._image_origin
        best, best_distance = None, None
        for row, index, x, above_baseline in targets:
            screen_x = origin_x + x
            screen_y = origin_y + self._image_baseline - above_baseline
            # Vertical distance counts for more, so a click in a numerator
            # lands in the numerator rather than the denominator below it.
            distance = (screen_x - event.x) ** 2 + \
                (2.5 * (screen_y - event.y)) ** 2
            if best_distance is None or distance < best_distance:
                best, best_distance = (row, index), distance

        self.caret_row, self.caret_index = best
        self._redraw()
        return "break"

    def _on_wheel(self, event):
        """Scroll sideways through an expression wider than the box."""
        step = 0
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        elif getattr(event, "delta", 0):
            step = -1 if event.delta > 0 else 1
        if step:
            self._scroll_x = self._clamp_scroll(self._scroll_x + step * 40)
            self._redraw(follow_caret=False)
        return "break"

    def _clamp_scroll(self, value: float) -> float:
        visible = max(self.winfo_width(), 1) - 2 * self.PAD_X
        return max(0.0, min(value, max(0.0, self._image_width - visible)))

    def _redraw(self, follow_caret: bool = True) -> None:
        self.delete("all")
        height = max(self.winfo_height(), 1)
        latex = to_latex(self.root_row)
        try:
            photo, width, image_height, baseline = render(
                latex, self.fontsize, self.colour)
        except Exception:                           # noqa: BLE001
            self.create_text(self.PAD_X, height / 2, anchor="w",
                             text=to_text(self.root_row) or "",
                             font=("Consolas", 12), fill=self.colour)
            return

        self._image_width = width
        self._image_baseline = baseline
        spot = self._caret_spot() if self.focus_get() is self else None
        if follow_caret and spot is not None:
            self._scroll_x = self._clamp_scroll(self._keep_visible(spot[0]))
        else:
            self._scroll_x = self._clamp_scroll(self._scroll_x)

        top = (height - image_height) / 2
        left = self.PAD_X - self._scroll_x
        self._image = photo
        self._image_origin = (left, top)
        self.create_image(left, top, image=photo, anchor="nw")

        if spot is not None:
            self._draw_caret(top, left, spot)
        if self._scroll_x > 0:
            self._draw_edge_fade(height, "left")
        if self._image_width - self._scroll_x > \
                max(self.winfo_width(), 1) - 2 * self.PAD_X:
            self._draw_edge_fade(height, "right")

    def _keep_visible(self, caret_x: float) -> float:
        """Scroll just enough to bring the caret back into view."""
        visible = max(self.winfo_width(), 1) - 2 * self.PAD_X
        margin = 24
        if caret_x - self._scroll_x < margin:
            return caret_x - margin
        if caret_x - self._scroll_x > visible - margin:
            return caret_x - visible + margin
        return self._scroll_x

    def _caret_spot(self):
        try:
            return caret_position(
                to_latex(self.root_row, self.caret_row, self.caret_index),
                self.fontsize)
        except Exception:                           # noqa: BLE001
            return None

    def _draw_caret(self, top: float, left: float, spot) -> None:
        x, above_baseline, glyph_size = spot
        scale = DPI / 72.0
        half = glyph_size * scale * 0.58
        centre = top + self._image_baseline - above_baseline - half * 0.30
        self.create_line(left + x, centre - half, left + x, centre + half,
                         fill="#2f6fd0", width=2)

    def _draw_edge_fade(self, height: int, side: str) -> None:
        """A hint that the expression continues past the edge of the box."""
        width = max(self.winfo_width(), 1)
        x = 0 if side == "left" else width - 14
        self.create_rectangle(x, 0, x + 14, height, fill="#f0f0f4",
                              outline="", stipple="gray25")
