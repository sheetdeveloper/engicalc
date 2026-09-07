"""What the window is coloured with, and how to change it.

Two decisions live here and they are separate on purpose.

**The base** is light or dark: the page, the cards on it, the hairlines and
the two greys the text is written in. It is what makes the app comfortable
in a bright office or a dark one.

**The accent** is one colour, and the app is disciplined about where it
goes: the control that does the work, and the heading that says what a
panel is. Nowhere else, so it keeps meaning that. Because it is only ever
those two things, it can be anything the user likes without the window
falling apart - which is why it is a choice rather than a constant.

Everything else about an accent is worked out from it. The hover tint is
the accent mixed into the page; the lighter one is the accent mixed toward
white. And the accent used for **text** is moved until it actually contrasts
with what it is written on - four and a half to one, the readable
threshold - so somebody who picks navy on a dark base gets a navy that can
be read rather than a heading that is not there.

**The charts stay light.** A chart is a document: it gets exported into a
report, pasted into an email, and printed. A dark one would arrive in all
three places wrong, and the colours that mean tension and compression were
chosen against white. So the window goes dark around them and the drawing
does not. That is a decision, not an omission.
"""

from __future__ import annotations

import weakref

#: The page, the cards, the lines and the text. Everything that is not the
#: accent.
BASES = {
    "light": {
        # Quiet, so the white cards on it read as content rather than as
        # another panel.
        "bg": "#f1f3f6",
        "surface": "#ffffff",
        # A one pixel line separates things as well as a bevel does and
        # takes a tenth of the room.
        "line": "#dcdfe5",
        "ink": "#1b1d21",
        "muted": "#6b7280",
        "field": "#ffffff",
        # A refusal. Red enough to be one at a glance, dark enough to be
        # read - and lifted on the dark base, where #b00020 is a smudge.
        "bad": "#b00020",
    },
    "dark": {
        "bg": "#1c1f24",
        "surface": "#24282f",
        "line": "#383d46",
        "ink": "#e6e8eb",
        "muted": "#98a1ad",
        "field": "#2b3038",
        "bad": "#ff6b6b",
    },
}

#: Accents worth offering by name. Anything else can be picked from the
#: colour dialog - these are a starting point, not a limit.
ACCENTS = {
    "Navy": "#1f4e79",
    "Blue": "#2563eb",
    "Teal": "#0f766e",
    "Green": "#15803d",
    "Plum": "#7c3aed",
    "Crimson": "#b91c1c",
    "Amber": "#b45309",
    "Slate": "#475569",
}

#: How readable accent text has to be against what it sits on. 4.5:1 is
#: the ordinary-text threshold; a heading could get away with 3, but a
#: heading that is only just readable is not worth shipping.
LEAST_CONTRAST = 4.5

_base = "light"
_accent = ACCENTS["Navy"]
_listeners: list = []


# --------------------------------------------------------------------------
# Colour arithmetic
# --------------------------------------------------------------------------
def _rgb(colour: str) -> tuple:
    text = colour.lstrip("#")
    return tuple(int(text[at:at + 2], 16) for at in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(one))):02x}" for one in rgb)


def mix(one: str, other: str, how_far: float) -> str:
    """*how_far* of the way from *one* to *other*."""
    return _hex(a + (b - a) * how_far
                for a, b in zip(_rgb(one), _rgb(other)))


def _channel(value: float) -> float:
    value /= 255.0
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    """Relative luminance, the way the accessibility guidelines define it."""
    red, green, blue = (_channel(one) for one in _rgb(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: str, other: str) -> float:
    """The ratio between two colours, 1 for identical and 21 at the most."""
    first, second = luminance(one), luminance(other)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def readable(colour: str, against: str,
             least: float = LEAST_CONTRAST) -> str:
    """*colour*, moved until it can be read on *against*.

    Toward white on a dark ground and toward black on a light one, in
    small steps, stopping as soon as it is readable. A user who picks navy
    on a dark base gets a navy they can read rather than a heading that is
    not there; one who picks a pale yellow on white gets it darkened.
    """
    toward = "#ffffff" if luminance(against) < 0.5 else "#000000"
    moved = colour
    for step in range(21):
        if contrast(moved, against) >= least:
            return moved
        moved = mix(colour, toward, step / 20.0)
    return moved


# --------------------------------------------------------------------------
# The palette in force
# --------------------------------------------------------------------------
def colours() -> dict:
    """Every colour the window uses, for the base and accent in force."""
    base = dict(BASES[_base])
    dark = _base == "dark"
    # The accent as text has to be readable on both the page and a card,
    # and those differ - so it is corrected against whichever is harder.
    harder = (base["surface"] if contrast(_accent, base["surface"])
              < contrast(_accent, base["bg"]) else base["bg"])
    accent = readable(_accent, harder)
    base.update({
        "accent": accent,
        # What the accent looks like when a button is pressed or a tab is
        # hovered: lifted on a dark ground, deepened on a light one.
        "accent_light": mix(accent, "#ffffff" if dark else "#000000", 0.22),
        # A wash of the accent for a hover, close enough to the page that
        # it reads as a highlight rather than as a second colour.
        "accent_soft": mix(base["bg"], accent, 0.18 if dark else 0.12),
        # What the accent was asked for, before it was made readable -
        # so a picker can show the choice rather than the correction.
        "accent_asked": _accent,
    })
    return base


def base() -> str:
    return _base


def accent() -> str:
    return _accent


def use(base_name: str | None = None, accent_colour: str | None = None) -> None:
    """Change the base, the accent, or both, and tell everyone who asked."""
    global _base, _accent
    if base_name in BASES:
        _base = base_name
    if accent_colour:
        _accent = accent_colour
    _tell_everyone()


def _tell_everyone() -> None:
    living = []
    for held in _listeners:
        listener = held() if isinstance(held, weakref.WeakMethod) else held
        if listener is None:
            continue              # its window has gone; drop it quietly
        living.append(held)
        try:
            listener()
        except Exception:                              # noqa: BLE001
            pass                  # one tab that will not redraw is not fatal
    _listeners[:] = living


def on_change(listener) -> None:
    """Call *listener* whenever the colours change.

    Held weakly when it is a bound method, so a window that has been
    closed stops being told about colours instead of being kept alive by
    the fact that it once asked.
    """
    try:
        _listeners.append(weakref.WeakMethod(listener))
    except TypeError:
        _listeners.append(listener)      # a plain function; nothing to leak


def is_dark() -> bool:
    return _base == "dark"


# --------------------------------------------------------------------------
# The charts
# --------------------------------------------------------------------------
#: A chart keeps document colours whatever the window is doing - see the
#: note at the top of this file.
CHART_PAPER = "#ffffff"
CHART_INK = "#111111"
