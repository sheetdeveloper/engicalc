"""Working an expression out with the units still attached.

``quantity`` gives a number that knows what it measures. This walks an
expression with those in place of the numbers, so that

    sigma = F / A,  F = 5000 N,  A = 20 mm^2

comes back as **250 N/mm^2** rather than as 250, and

    F / A + T          with T a temperature

comes back as a refusal naming the two things that were added, rather than
as a number that looks fine.

It works on the expression SymPy already parsed, so everything the app can
already read - fractions, powers, roots, the trigonometric functions - is
read here the same way, and there is no second grammar to keep in step.

**Where a unit comes from.** Whatever was typed. A value given as ``50 mm``
is fifty millimetres; a value given as ``50`` is fifty of nothing, and
adding it to a length is refused rather than assumed to be millimetres.
That refusal is the feature: assuming is exactly what goes wrong.
"""

from __future__ import annotations

import re

import sympy as sp

from .parsing import ParseError, parse_input
from .quantity import Quantity, QuantityError, equivalents

#: What SymPy calls a function, and what quantity calls it.
FUNCTIONS = {
    sp.sin: "sin", sp.cos: "cos", sp.tan: "tan",
    sp.asin: "asin", sp.acos: "acos", sp.atan: "atan",
    sp.exp: "exp", sp.log: "log",
    sp.sinh: "sinh", sp.cosh: "cosh", sp.tanh: "tanh",
    sp.Abs: "abs", sp.sqrt: "sqrt",
}


class DimensionError(ParseError):
    """Raised when an expression does not hold together dimensionally."""


def read(values: dict) -> dict:
    """Turn ``{"F": "5000 N"}`` into quantities, saying which one failed."""
    found = {}
    for name, text in values.items():
        if isinstance(text, Quantity):
            found[name] = text
            continue
        try:
            found[name] = Quantity.parse(text)
        except QuantityError as exc:
            raise DimensionError(f"{name}: {exc}") from exc
    return found


def evaluate(text: str, values: dict) -> Quantity:
    """Work *text* out with *values* in it, units and all.

    *values* maps a name to a string like ``"50 mm"``, or to a
    :class:`Quantity` already read.
    """
    known = read(values)
    expression = _parse(text, known)      # adds any lifted literals to known
    missing = sorted(str(symbol) for symbol in expression.free_symbols
                     if str(symbol) not in known)
    if missing:
        raise DimensionError(
            f"Nothing was given for {', '.join(missing)}.")
    return walk(expression, known).tidy()


def _parse(text: str, known: dict):
    """Read *text* with the given names declared as symbols.

    Without declaring them, E is Euler's number and I is the imaginary
    unit - so a beam deflection W L^3 / (48 E I) parses as a complex
    number and falls over on the way to being a length. T2 goes the same
    way for a different reason: undeclared it reads as T times 2.

    The formula library already does this for the same reason. It is the
    one thing that has to happen before any of the rest means anything.
    """
    text, literals = lift_units(text, known)
    known.update(literals)
    local = {name: sp.Symbol(name) for name in known}
    parsed = parse_input(text, extra_symbols=local)
    expression = parsed.expr
    if isinstance(expression, sp.Eq):
        expression = expression.rhs
    return expression


#: A number, and then as much unit as follows it. The unit part is taken a
#: name at a time rather than as one pattern, because whether "m/s^2" is a
#: unit or a division by a variable called s depends on what the variable
#: names are - which a regular expression cannot know.
NUMBER = re.compile(r"(?<![A-Za-z0-9_.])"
                    r"(\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)"
                    r"(?![0-9.])")
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
POWER = re.compile(r"\^-?\d+")


def lift_units(text: str, known: dict) -> tuple:
    """Pull ``5 K`` and ``9.81 m/s^2`` out of an expression.

    Each gets a name of its own and a quantity to go with it, so the rest
    of the expression parses as ordinary algebra and the units arrive with
    the values rather than as unknown symbols.

    **A variable always wins over a unit of the same spelling.** Somebody
    with a row called ``m`` for a mass who writes ``2*m`` means twice their
    mass, and no cleverness about it would be an improvement - so the unit
    reading stops at the first name that is already defined.
    """
    table = units_table()
    found: dict = {}
    out, at = [], 0
    for match in NUMBER.finditer(text):
        if match.start() < at:
            continue
        unit, after = _unit_after(text, match.end(), known, table)
        if not unit:
            continue
        name = f"_given_{len(found)}"
        try:
            found[name] = Quantity.of(float(match.group(1)), unit)
        except QuantityError:
            continue
        out.append((match.start(), after, name))
        at = after

    if not out:
        return text, {}
    pieces, last = [], 0
    for start, stop, name in out:
        pieces.append(text[last:start])
        pieces.append(name)
        last = stop
    pieces.append(text[last:])
    return "".join(pieces), found


def _unit_after(text: str, at: int, known: dict, table: set) -> tuple:
    """The unit written after a number, and where it ends.

    Walks name by name through ``mm``, ``m/s^2``, ``J/(kg*K)``, stopping at
    the first thing that is not a unit - or that is a name the caller has
    already given a value to.
    """
    spot = at
    while spot < len(text) and text[spot] == " ":
        spot += 1
    if spot == at and not (spot < len(text) and text[spot].isalpha()):
        return "", at
    pieces, depth, end = [], 0, spot
    place = spot
    while place < len(text):
        letter = text[place]
        if letter.isalpha():
            name = NAME.match(text, place)
            word = name.group(0)
            if word in known or word not in table:
                break
            pieces.append(word)
            place = name.end()
            power = POWER.match(text, place)
            if power:
                pieces.append(power.group(0))
                place = power.end()
            end = place
            continue
        if letter in "*/" and place + 1 < len(text):
            # Only if a unit follows it, or an opening bracket does.
            ahead = place + 1
            if text[ahead] == "(":
                pieces.append(letter)
                pieces.append("(")
                depth += 1
                place = ahead + 1
                continue
            name = NAME.match(text, ahead)
            if not name or name.group(0) in known \
                    or name.group(0) not in table:
                break
            pieces.append(letter)
            place = ahead
            continue
        if letter == ")" and depth:
            pieces.append(")")
            depth -= 1
            place += 1
            end = place
            continue
        break
    if depth or not pieces:
        return "", at
    return "".join(pieces), end


def units_table() -> set:
    from . import units as unit_tools

    return set(unit_tools.UNITS) | set(unit_tools.CELSIUS)


def walk(expression, known: dict) -> Quantity:
    """One node of the tree, and everything under it."""
    if expression.is_number:
        return Quantity(float(expression), {})
    if isinstance(expression, sp.Symbol):
        found = known.get(str(expression))
        if found is None:
            raise DimensionError(f"Nothing was given for {expression}.")
        return found

    try:
        if isinstance(expression, sp.Add):
            return _added(expression, known)
        if isinstance(expression, sp.Mul):
            return _multiplied(expression, known)
        if isinstance(expression, sp.Pow):
            base = walk(expression.base, known)
            power = walk(expression.exp, known)
            return base ** power
        for kind, name in FUNCTIONS.items():
            if isinstance(expression, kind):
                from .quantity import apply
                return apply(name, walk(expression.args[0], known))
    except QuantityError as exc:
        raise DimensionError(str(exc)) from exc

    raise DimensionError(
        f"I cannot carry units through {sp.srepr(expression)[:60]}. "
        f"Work it out without them, or say what the answer measures.")


def _added(expression, known: dict) -> Quantity:
    """A sum, where every term has to measure the same thing.

    The refusal names the two terms as they were written rather than the
    two units alone, because "adding m and kg" does not say *where*, and
    on an expression of any length that is the only question worth
    answering.
    """
    pieces = [(term, walk(term, known)) for term in expression.args]
    first_term, total = pieces[0]
    for term, value in pieces[1:]:
        try:
            total = total + value
        except QuantityError as exc:
            raise DimensionError(
                f"{exc} It is {sp.sstr(first_term)} and {sp.sstr(term)} "
                f"that will not go together.") from exc
    return total


def _multiplied(expression, known: dict) -> Quantity:
    """A product, folding units of the same kind onto one of them.

    Millimetres times metres is a real unit and a useless one, so where
    two factors carry different units of the same kind the later is
    written in the earlier's - which is what anybody doing it on paper
    does without noticing.
    """
    from .quantity import harmonise

    total = None
    for term in expression.args:
        value = walk(term, known)
        if total is None:
            total = value
            continue
        total, value = harmonise(total, value)
        total = total * value
    return total if total is not None else Quantity(1.0, {})


def describe(answer: Quantity, wanted: str = "") -> tuple:
    """(the answer as a line, anything else worth saying about it)."""
    lines = []
    shown = answer
    if wanted:
        try:
            shown = answer.to(wanted, absolute=False)
        except QuantityError as exc:
            raise DimensionError(str(exc)) from exc
    same = [one for one in equivalents(shown)
            if one.unit != shown.unit]
    if same:
        lines.append("which is " + ", or ".join(str(one) for one in same))
    return str(shown), lines


def check(text: str, values: dict) -> str:
    """Say what an expression comes out in, without working it out.

    Every value is replaced by one of its own unit, so the answer is the
    unit alone. Useful for checking a formula before there are numbers to
    put in it, and for saying what a worksheet step will produce.
    """
    known = {name: Quantity(1.0, one.powers)
             for name, one in read(values).items()}
    return walk(_parse(text, known), known).tidy().unit
