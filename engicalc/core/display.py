"""Turn SymPy objects into the notation an engineer expects to read.

SymPy's own ``sstr`` gives ``Eq(2*x**2 - 5*x - 3, 0)``; this module gives
``2*x^2 - 5*x - 3 = 0``. Purely cosmetic - nothing here is parsed back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from sympy.printing.latex import LatexPrinter

from .parsing import GREEK_NAMES, NAME_PATTERN, SAFE_FUNCTIONS


def fmt(expr) -> str:
    """Format *expr* for display in the window."""
    if expr is None:
        return ""
    if isinstance(expr, str):
        return expr
    if isinstance(expr, (list, tuple)):
        return ", ".join(fmt(e) for e in expr)
    if isinstance(expr, dict):
        return ", ".join(f"{fmt(k)} = {fmt(v)}" for k, v in expr.items())
    if not isinstance(expr, sp.Basic):
        return str(expr)

    # A Float prints all fifteen of the digits it is carrying, so a limit
    # typed as -1.6 comes back as -1.60000000000000. None of those zeros are
    # information, and they make a worked solution look like a machine
    # readout rather than an answer.
    if isinstance(expr, sp.Float):
        return fmt_number(expr)

    if isinstance(expr, sp.Equality):
        return f"{fmt(expr.lhs)} = {fmt(expr.rhs)}"
    if isinstance(expr, sp.Rel):
        return f"{fmt(expr.lhs)} {expr.rel_op} {fmt(expr.rhs)}"
    if isinstance(expr, sp.Derivative):
        variable = expr.variables[0]
        order = len(expr.variables)
        lead = f"d/d{variable}" if order == 1 else f"d^{order}/d{variable}^{order}"
        return f"{lead} [ {fmt(expr.expr)} ]"
    if isinstance(expr, sp.Integral):
        limits = expr.limits[0]
        variable = limits[0]
        if len(limits) == 3:
            return (f"integral from {fmt(limits[1])} to {fmt(limits[2])} of "
                    f"[ {fmt(expr.function)} ] d{variable}")
        return f"integral of [ {fmt(expr.function)} ] d{variable}"
    if isinstance(expr, sp.Limit):
        function, variable, point = expr.args[0], expr.args[1], expr.args[2]
        direction = expr.args[3] if len(expr.args) > 3 else ""
        return (f"lim {variable} -> {fmt(point)}{direction} "
                f"[ {fmt(function)} ]")
    return sp.sstr(expr).replace("**", "^")


_DIFFERENCE = re.compile(r"^d([A-Z])(\d*)$")


def symbol_names(expr) -> dict:
    """How each symbol should be drawn, for ``sp.latex(symbol_names=...)``.

    A variable named ``dT`` means a change in temperature and is written
    ``ΔT`` everywhere outside a keyboard. The name has to stay ``dT`` - it is
    what the parser and the formula data use - so the difference is made at
    the point of drawing.

    Deliberately narrow: ``d`` followed by a capital. ``delta`` is left alone
    because in this library it means a deflection, the lowercase δ, which is
    a different quantity and not a difference at all.
    """
    names = {}
    try:
        symbols = expr.free_symbols
    except AttributeError:
        return names
    for symbol in symbols:
        drawn = latex_name(symbol.name)
        if drawn != symbol.name:
            names[symbol] = drawn
    return names




#: How a rate is spelled, and the accent it is drawn with. The two-dot form
#: is checked first, or `xddot` would be read as `xd` with one dot.
_RATES = (("ddot", r"\ddot"), ("dot", r"\dot"))
_RATE_SUFFIX = {name: command for name, command in _RATES}


def _base_latex(base: str, one_symbol: bool) -> str:
    """The part of a name before its subscript."""
    if base in GREEK_NAMES:
        return "\\" + base.rstrip("_") + " "
    if base in SAFE_FUNCTIONS:
        return r"\mathrm{" + base + "}"
    if one_symbol:
        for suffix, command in _RATES:
            # `dot` on its own is a name, not a rate with nothing under it.
            if base.endswith(suffix) and len(base) > len(suffix):
                return (command + "{"
                        + latex_name(base[:-len(suffix)], one_symbol) + "}")
    if one_symbol and len(base) > 1:
        # Two italic letters side by side are what a product looks like, so
        # a name that really is one symbol is set upright to say so: `Re` is
        # a Reynolds number rather than R times e.
        return r"\mathrm{" + base + "}"
    return base


def latex_name(name: str, one_symbol: bool = True) -> str:
    """One variable name, typeset the way it is written by hand.

    ``one_symbol`` says whether a run of letters is a single name. It is,
    wherever the names have been declared - a sheet, a set of equations - and
    it is not in the equation bar, where nothing is declared and `Re` really
    does parse as R times e. Drawing it upright there would be a claim the
    arithmetic does not support, so the letters stay italic and read as the
    product they are.

    Anything after an underscore is a subscript either way, because an
    underscore name is a single symbol in every path. That is what makes a
    subscript the way to write a multi-letter variable that has to survive.
    """
    word = str(name or "")
    if not word:
        return ""
    # log10 and atan2 are whole names, not a log with a subscript.
    if word in SAFE_FUNCTIONS:
        return r"\mathrm{" + word + "}"
    # dT is a change in T. Narrow on purpose - d then a capital - because
    # `delta` in this library is a deflection, and dx and dt are
    # differentials rather than differences.
    difference = _DIFFERENCE.match(word)
    if difference:
        letter, index = difference.groups()
        return r"\Delta " + letter + (f"_{{{index}}}" if index else "")
    base, separator, index = word.partition("_")
    if separator and index in _RATE_SUFFIX:
        # m_dot spells the rate out with an underscore, which makes it one
        # symbol in every path - so it draws with the dot in every path.
        return _RATE_SUFFIX[index] + "{" + latex_name(base, one_symbol) + "}"
    if not separator and one_symbol:
        # Only split a trailing number off a name that is one symbol. Where
        # it is not, T1 has already been read as T times 1 and a subscript
        # would be drawing something that was never computed.
        stripped = base.rstrip("0123456789")
        if stripped and stripped != base:
            base, index = stripped, base[len(stripped):]
    drawn = _base_latex(base, one_symbol)
    if index:
        drawn += "_{" + latex_name(index, one_symbol) + "}"
    return drawn


def number_to_latex(text: str) -> str:
    """A formatted number as notation: 5.66e+05 becomes 5.66 x 10^5.

    Takes the string :func:`fmt_number` produced, so whatever notation and
    how many figures were asked for are already decided - this only turns
    the ASCII way of writing an exponent into the drawn one.
    """
    lowered = str(text).strip()
    if "e" not in lowered.lower():
        return lowered
    mantissa, _, exponent = lowered.lower().partition("e")
    try:
        power = int(exponent)
    except ValueError:
        return lowered
    mantissa = mantissa.rstrip(".")
    if mantissa in ("1", "1.0", ""):
        return f"10^{{{power}}}"
    if mantissa in ("-1", "-1.0"):
        return f"-10^{{{power}}}"
    return rf"{mantissa} \times 10^{{{power}}}"


class _Printer(LatexPrinter):
    """SymPy's printer, with the app's number format for Floats.

    Only that one method is replaced. SymPy has no idea the setting exists,
    and everything else about how an expression is drawn should stay exactly
    as it was.
    """

    def _print_Float(self, expr):
        return number_to_latex(fmt_number(expr))


def latex(expr, **kwargs) -> str:
    """``sp.latex`` with the difference symbols drawn as Δ, and the app's
    number format applied to any Float in the expression."""
    kwargs.setdefault("symbol_names", symbol_names(expr))
    try:
        return _Printer(kwargs).doprint(expr)
    except Exception:  # noqa: BLE001 - a drawn answer is not worth an error
        return sp.latex(expr, **kwargs)


_GREEK = GREEK_NAMES
_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def unicode_symbol(name: str) -> str:
    """A variable's name written the way it is read: rho -> ρ, dT -> ΔT.

    For places that show a bare name in a plain label - the symbol column of
    the formula library, say - where a rendered image would be heavy and
    would not line up in a table.
    """
    if not name:
        return ""
    text = str(name)

    match = _DIFFERENCE.match(text)
    if match:
        letter, index = match.groups()
        return "Δ" + letter + index.translate(_SUBSCRIPT)

    base, separator, index = text.partition("_")
    if not index and not separator:
        # A trailing number is a subscript: T1 is read as T-one.
        stripped = base.rstrip("0123456789")
        if stripped and stripped != base and stripped not in _GREEK:
            base, index = stripped, base[len(stripped):]
    letter = _GREEK.get(base, base)
    if index.isdigit():
        return letter + index.translate(_SUBSCRIPT)
    if index:
        # Unicode has no full subscript alphabet, so tau_max would come out
        # as "taumax" - the underscore is doing real work and stays.
        return letter + "_" + _GREEK.get(index, index)
    return letter



_TOKEN = re.compile(NAME_PATTERN)


def pretty_names(text: str) -> str:
    """Greek names in *text* written as their letters, and nothing else.

    For text that is going back into an editable box and will be parsed
    again, so only substitutions that survive the round trip are made. That
    rules out the ``dT`` -> ``ΔT`` reading used by :func:`unicode_symbol`:
    Δ reads back as ``Delta``, so the name would quietly change identity.
    Greek names are the whole of what is safe here.
    """
    if not text:
        return ""

    def letter(match):
        # A difference first: dT is a change in T, and the triangle is how
        # that is written. U+2206, so it reads back as the dT it came from
        # rather than colliding with a variable called Delta.
        difference = _DIFFERENCE.match(match.group(0))
        if difference:
            base, index = difference.groups()
            return "\u2206" + base + index
        # sigma_max is a sigma with a subscript, so each part between the
        # underscores is looked up rather than the whole name. Splitting only
        # where both sides are non-empty leaves lambda_ alone, which exists
        # to keep clear of the Python keyword and is not a subscript at all.
        name = match.group(0)
        if "_" in name and not name.endswith("_") and not name.startswith("_"):
            return "_".join(GREEK_NAMES.get(part, part)
                            for part in name.split("_"))
        return GREEK_NAMES.get(name, name)

    return _TOKEN.sub(letter, str(text))


def fmt_set(solution) -> str:
    """An inequality's answer, written the way it is read.

    SymPy's own text for these is ``Union(Interval.open(-oo, -2),
    Interval.open(2, oo))``. An engineer reads ``(-inf, -2) or (2, inf)``.
    Square brackets where the endpoint is included, round where it is not,
    which is the same convention every textbook uses.
    """
    if solution is None:
        return ""
    if isinstance(solution, sp.Interval):
        left = "(" if solution.left_open else "["
        right = ")" if solution.right_open else "]"
        return f"{left}{fmt(solution.start)}, {fmt(solution.end)}{right}"
    if isinstance(solution, sp.Union):
        return "  or  ".join(fmt_set(part) for part in solution.args)
    if isinstance(solution, sp.FiniteSet):
        return "{" + ", ".join(fmt(part) for part in solution.args) + "}"
    if solution is sp.S.EmptySet or solution == sp.S.EmptySet:
        return "no solution"
    if solution == sp.S.Reals:
        return "all real numbers"
    if isinstance(solution, sp.Complement):
        whole, removed = solution.args
        return f"{fmt_set(whole)} except {fmt_set(removed)}"
    return fmt(solution)


#: How numbers are written, app-wide. `figures` of None means "however many
#: the caller asked for", which is the behaviour every call site was written
#: against - so leaving this alone changes nothing.
@dataclass
class NumberFormat:
    figures: int | None = None
    #: auto, fixed, scientific or engineering.
    notation: str = "auto"


FORMAT = NumberFormat()

#: What the notations are called where somebody has to choose one.
NOTATIONS = {
    "auto": "As it reads best",
    "fixed": "Plain decimal",
    "scientific": "Scientific  1.23e5",
    "engineering": "Engineering  123e3",
}


#: Passed as `figures` to go back to letting each caller choose.
AS_ASKED = "auto"

#: Not passed at all. Distinct from AS_ASKED, which is a request to reset -
#: telling the two apart from the values themselves is what went wrong the
#: first time.
_KEEP = object()


def set_number_format(figures=_KEEP, notation=_KEEP) -> None:
    """Set how numbers are written from here on.

    Anything not passed is left as it is; ``figures=AS_ASKED`` puts the
    figures back to each caller's own choice, which is how the app starts.
    """
    if figures is not _KEEP:
        FORMAT.figures = (None if figures in (None, "", AS_ASKED)
                          else int(figures))
    if notation is not _KEEP and notation is not None:
        if notation not in NOTATIONS:
            raise ValueError(f"There is no {notation!r} notation.")
        FORMAT.notation = notation


def _engineering(value: float, figures: int) -> str:
    """The exponent as a multiple of three, which is what a prefix is.

    566e3 and 5.66e5 are the same number, but only one of them reads as
    kilo-anything.
    """
    if value == 0:
        return "0"
    from math import floor, log10

    exponent = int(floor(log10(abs(value))))
    exponent -= exponent % 3
    mantissa = value / (10.0 ** exponent)
    # The mantissa runs from 1 to 1000 here rather than 1 to 10, so it needs
    # up to two more places before the point than a scientific mantissa -
    # and those places are significant figures already spent.
    before = len(str(int(abs(mantissa))))
    text = f"{mantissa:.{max(figures - before, 0)}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text if exponent == 0 else f"{text}e{exponent}"


def fmt_number(value, digits: int = 10) -> str:
    """Format a number the way the app has been asked to write them.

    *digits* is what this caller would like; the app-wide setting wins when
    one has been chosen, since a preference that applied to only some tabs
    would not be one.

    For plain decimal the number is places after the point, which is what
    "decimal places" means. For the others it is significant figures - a
    fixed number of places after the point does not go with an exponent.
    """
    chosen = FORMAT.figures
    notation = FORMAT.notation
    try:
        # Converted at full precision and rounded once, at the end. Rounding
        # to significant figures first and then formatting to decimal places
        # rounds twice and answers neither question.
        number = sp.N(value, 20)
        if not number.is_real:
            return str(number)
        as_float = float(number)
    except Exception:  # noqa: BLE001
        return str(value)

    if notation == "fixed":
        places = 4 if chosen is None else chosen
        return f"{as_float:.{max(places, 0)}f}"

    figures = max(chosen if chosen is not None else digits, 1)
    if notation == "scientific":
        return f"{as_float:.{figures - 1}e}"
    if notation == "engineering":
        return _engineering(as_float, figures)

    # Auto: a whole number is written as one, and anything else to the
    # figures asked for with the trailing zeros trimmed.
    if as_float == int(as_float) and abs(as_float) < 1e15:
        return str(int(as_float))
    return f"{as_float:.{figures}g}"