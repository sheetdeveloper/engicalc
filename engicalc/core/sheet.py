"""A calculation sheet: several steps in order, each able to use the last.

Real work is never one calculation. It is a diameter, then an area from that
diameter, then a velocity from the area, then a Reynolds number from the
velocity - and if the diameter changes, everything after it should follow.
Doing that in the calculator means copying numbers between boxes by hand,
which is where transcription errors come from.

A sheet is a list of named steps evaluated top to bottom. Each step defines a
name, and any step may use the names defined above it. Nothing may use a name
defined below it: a sheet reads downwards, like the page it stands in for.

Each step carries its own unit, and the unit is carried through the
arithmetic rather than written beside it. A row computing ``pi*d^2/4`` from
a diameter in millimetres comes out in mm^2 because that is what it is, and
a row that declares m^2 for it is told so rather than believed. A row that
declares nothing is given whatever the expression produced.

That is the whole of the difference between a unit as a label and a unit as
a fact, and it is where the mistakes are: mixing millimetres and metres is
the commonest error in engineering arithmetic and a labelled sheet cannot
see it.

The whole sheet evaluates to a list of :class:`StepResult`, and a step that
fails does not stop the ones after it - it is reported and the rest carry on,
because one broken line in the middle of a sheet should not blank the page.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import sympy as sp

from . import dimensional, uncertainty
from . import units as unit_tools
from .display import fmt, fmt_number
from .parsing import ParseError, canonical_name, parse_input
from .quantity import Quantity, QuantityError, parse_powers

#: Checked against the canonical spelling, which is always
#: ASCII however the name was typed.
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: A subscript, written the way an engineer writes one.
INDEX = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)"
                   r"\[\s*([0-9]+)\s*\]")


def subscripted(text: str) -> str:
    """``T[1]`` as ``T_1`` - the same quantity, written two ways.

    A calculation with stages in it is written with subscripts: the
    temperature at state 1, the pressure at state 2. ``T1`` will not do,
    because the parser reads it as T times 1 and quietly works out
    something else. ``T_1`` works and reads like a filename.

    So ``T[1]`` is accepted, and it is the *same name* as ``T_1`` rather
    than a new kind of thing - exactly the way ``rho`` and its Greek
    letter are the same name. Two spellings of one quantity, so a sheet
    defining both is defining a row twice and is already told so.

    Nothing downstream knows about it. The expression that reaches SymPy
    has ordinary names in it, the units carry through as they always did,
    and the tolerance of ``T[1]`` is counted once because it is one name.
    And the typeset display draws ``T_1`` as T with a subscript, which is
    what it was written as in the first place.
    """
    return INDEX.sub(r"\1_\2", str(text or ""))

#: A row that is a table of numbers rather than a value:
#:
#:     table: 15, 0.35; 30, 0.60; 45, 0.95
#:     table in mm: 10, 1.2; 20, 1.5
#:
#: The second form says what the x column is in, so a later row can call
#: it with a length in metres and be understood.
TABLE = re.compile(r"^\s*table\s*(?:\bin\s+(?P<unit>[^:]+?)\s*)?:"
                   r"\s*(?P<body>.+)$", re.IGNORECASE | re.DOTALL)

#: A call to one: ``k(30)``, ``k(theta/2)``.
CALL = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)\s*\(")


@dataclass
class Lookup:
    """A table of numbers that a row can be asked a question of.

    Engineering runs on tabulated data - a k-factor against a bend angle,
    a correction against a diameter, a curve off a manufacturer's sheet -
    and the alternative to putting one on the sheet is fitting a
    polynomial to it and pretending that is the data.

    Between the rows it interpolates linearly and past the ends it
    refuses. A table is a set of measurements, and the straight line
    between two of them is a defensible guess where the line beyond the
    last one is not; a reading taken off the end of a manufacturer's
    curve is how a number nobody can defend gets into a calculation.
    """

    table: object                # interpolate.Table
    x_unit: str = ""
    y_unit: str = ""

    def at(self, x) -> float:
        """What the table says at *x*, which may carry a unit."""
        from . import interpolate

        if hasattr(x, "value"):
            wanted = self._plain(x)
        else:
            wanted = float(x)
        low, high = self.table.span
        if not low <= wanted <= high:
            raise ParseError(
                f"The table runs from {low:g} to {high:g}"
                + (f" {self.x_unit}" if self.x_unit else "")
                + f", and {wanted:g} is outside it. A straight line between "
                  f"two measurements is a defensible guess; past the last "
                  f"one it is not.")
        return float(interpolate.interpolate(self.table, wanted).numeric[0])

    def _plain(self, quantity) -> float:
        """The argument as a plain number in the table's own x unit."""
        if self.x_unit:
            return float(quantity.to(self.x_unit).value)
        if not quantity.plain:
            raise ParseError(
                f"This table is a table of plain numbers, and it is being "
                f"asked about {quantity.unit}. Say what the first column "
                f"is in - 'table in {quantity.unit}: ...' - or take the "
                f"unit off what it is being asked.")
        return float(quantity.value)

    def describe(self) -> str:
        low, high = self.table.span
        unit = f" {self.x_unit}" if self.x_unit else ""
        return (f"a table of {len(self.table)} points, "
                f"x from {low:g} to {high:g}{unit}")


#: How big a row's expression may get, written back out in terms of the
#: measurements, before the tolerances stop being worked out.
#:
#: Writing each row out in terms of the givens is what makes a measurement
#: count once however many routes it took, and it is also what makes the
#: expression grow - a row using two rows above it, each of which used two
#: above them, doubles at every level. A twenty-row sheet can get large,
#: and differentiating it in the middle of a keystroke would stop the
#: window. Past this the row says so rather than hanging.
TOO_BIG_TO_DIFFERENTIATE = 2000

SHEET_DIR = os.path.join(os.path.expanduser("~"), ".engicalc", "sheets")


@dataclass
class SheetStep:
    """One line of a sheet: ``name = expression``, optionally with a unit."""

    name: str
    expression: str
    unit: str = ""
    note: str = ""

    def is_input(self) -> bool:
        """True when the expression is just a number - a given, not a result."""
        try:
            value, _unit = unit_tools.split_quantity(self.expression)
            float(sp.sympify(value))
            return True
        except Exception:                             # noqa: BLE001
            return False


@dataclass
class StepResult:
    step: SheetStep
    value: object = None          # the magnitude, in ``unit`` below
    error: str = ""
    note: str = ""                # a unit conversion, or another remark
    #: What the row actually came out in. The declared unit where there is
    #: one and it fits; otherwise whatever the arithmetic produced.
    unit: str = ""
    quantity: object = None       # the answer with its unit attached
    #: How far the answer moves for the tolerances on what went into it,
    #: and which input put most of that in. None where no tolerance was
    #: given anywhere above.
    spread: object = None
    #: Set when the row is a table rather than a value. It has no single
    #: number, so it has no value and says what it holds instead.
    table: object = None

    @property
    def ok(self) -> bool:
        return self.error == ""

    @property
    def derived(self) -> bool:
        """True when the row was given its unit rather than declaring one."""
        return bool(self.unit) and not self.step.unit

    def text(self) -> str:
        if not self.ok:
            return f"{self.step.name}: {self.error}"
        if self.table is not None:
            return f"{self.step.name} - {self.table.describe()}"
        shown = fmt_number(self.value) if getattr(self.value, "is_number",
                                                  False) else fmt(self.value)
        if self.spread is not None and self.spread.known:
            shown += f" +/- {self.spread.error:.4g}"
        return f"{self.step.name} = {shown}" + (
            f" {self.unit}" if self.unit else "")


@dataclass
class Sheet:
    title: str = "Calculation sheet"
    steps: list = field(default_factory=list)

    # -- editing ----------------------------------------------------------
    def add(self, name: str, expression: str, unit: str = "",
            note: str = "") -> SheetStep:
        step = SheetStep(name.strip(), expression.strip(), unit.strip(),
                         note.strip())
        self.steps.append(step)
        return step

    def move(self, index: int, delta: int) -> None:
        target = index + delta
        if 0 <= index < len(self.steps) and 0 <= target < len(self.steps):
            self.steps[index], self.steps[target] = \
                self.steps[target], self.steps[index]

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.steps):
            del self.steps[index]

    # -- evaluating -------------------------------------------------------
    def evaluate(self) -> list:
        """Work down the sheet, carrying each answer into the next step."""
        known: dict = {}
        tables: dict = {}
        results: list = []
        seen: set = set()
        # Each row's expression, written out in terms of the rows that
        # were typed in rather than worked out - so a name reached by two
        # routes is one name, and its tolerance is counted once.
        formulas: dict = {}
        givens: dict = {}

        for index, step in enumerate(self.steps):
            result = StepResult(step)
            results.append(result)

            if not step.name:
                result.error = "This line has no name."
                continue
            # A row named with a symbol and a row named with the word are
            # the same quantity, so both spellings resolve to one name before
            # anything is keyed off it - or checked, which is why the check
            # comes after: the canonical spelling is always plain ASCII, so
            # every symbol the app can draw passes without widening this.
            name = canonical_name(subscripted(step.name))
            if not NAME.match(name):
                result.error = (f"{step.name!r} is not a usable name - letters, "
                                "digits and underscores, not starting with a "
                                "digit.")
                continue
            if name in seen:
                result.error = (f"{step.name} is defined twice. Later lines "
                                "would not know which one they meant.")
                continue
            seen.add(name)
            if not step.expression:
                result.error = "This line has no expression."
                continue

            # A table has no single value, so it goes no further down the
            # ordinary path - it is something later rows can ask, rather
            # than something with a number in it.
            written = TABLE.match(step.expression)
            if written:
                try:
                    tables[name] = self._read_table(written, step)
                except ParseError as exc:
                    result.error = str(exc)
                    continue
                result.table = tables[name]
                result.note = tables[name].describe()
                continue

            try:
                value, note, spread = self._evaluate_step(
                    step, known, formulas, givens, index, tables)
            except ParseError as exc:
                result.error = str(exc)
                continue
            except Exception as exc:                  # noqa: BLE001
                result.error = f"Could not work this out: {exc}"
                continue

            # Kept in kelvin and shown in whatever the row asked for.
            # Degrees Celsius is an offset rather than a scale, so there
            # is nothing sensible to multiply or divide it by - every row
            # below this one wants the kelvin.
            result.quantity = value
            result.unit = value.unit
            result.value = sp.Float(value.value)
            if step.unit in unit_tools.CELSIUS and value.unit == "K":
                result.unit = step.unit
                result.value = sp.Float(value.value
                                        - float(unit_tools.ABSOLUTE_ZERO))
            result.note = note
            # A given that was written with a tolerance has one too, and
            # is given the same shape as a worked-out row so that whatever
            # displays it has one thing to deal with rather than two.
            if spread is None and value.error is not None:
                spread = uncertainty.Answer(
                    value=value, error=value.error,
                    contributions=[uncertainty.Contribution(
                        name=name, given=value.error, unit=value.unit,
                        moves=value.error, share=1.0)])
            result.spread = spread
            known[name] = value

        return results

    def _ask_the_tables(self, text: str, tables: dict, known: dict,
                        tag: str = "") -> tuple:
        """Replace every ``k(30)`` with a name holding what k says at 30.

        Innermost first, so a table asked about another table's answer
        works - by the time the outer call is looked at, the inner one is
        already a number.

        The argument is worked out with the same machinery the row itself
        uses, so it can be any expression of the rows above: ``k(theta/2)``
        and ``k(2*d + 5 mm)`` both mean what they look like.
        """
        if not tables:
            return text, {}
        found: dict = {}
        while True:
            spot = self._innermost_call(text, tables)
            if spot is None:
                return text, found
            start, stop, name, argument = spot
            answer = tables[name].at(self._value_of(argument, known, tables))
            label = f"_table{tag}_{len(found)}"
            found[label] = Quantity.of(answer, tables[name].y_unit or "")
            text = text[:start] + label + text[stop:]

    @staticmethod
    def _innermost_call(text: str, tables: dict):
        """The first table call with no table call inside it.

        Returns (start, stop, name, argument) or None. Brackets are
        counted rather than matched by a pattern, because an argument may
        have brackets of its own and a regular expression cannot see that.
        """
        best = None
        for match in CALL.finditer(text):
            name = match.group(1)
            if name not in tables:
                continue
            depth, at = 0, match.end() - 1
            while at < len(text):
                if text[at] == "(":
                    depth += 1
                elif text[at] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                at += 1
            if depth != 0:
                raise ParseError(f"{name}( is never closed.")
            argument = text[match.end():at]
            inside = any(other in argument for other in tables)
            if not inside:
                return (match.start(), at + 1, name, argument)
            best = best or True
        if best:
            raise ParseError("A table call could not be worked out.")
        return None

    def _value_of(self, text: str, known: dict, tables: dict):
        """One expression, worked out against the rows already defined.

        The argument of a table call is an ordinary expression and gets
        ordinary treatment - the units in it are lifted, the names above
        it are substituted, and what comes back carries a unit so the
        table can be told what it is being asked about.
        """
        text = text.strip()
        if not text:
            raise ParseError("A table was asked about nothing.")
        lifted, literals = dimensional.lift_units(text, known, "_arg")
        wider = dict(known)
        wider.update(literals)
        declared = {one: sp.Symbol(one) for one in wider}
        parsed = parse_input(lifted, extra_symbols=declared)
        expression = parsed.expr
        if isinstance(expression, sp.Eq):
            expression = expression.rhs
        missing = sorted(one.name for one in expression.free_symbols
                         if one.name not in wider)
        if missing:
            raise ParseError(
                "Nothing here defines " + ", ".join(missing)
                + " - and it is what a table is being asked about.")
        return dimensional.walk(expression, wider).tidy()

    @staticmethod
    def _read_table(written, step: SheetStep) -> "Lookup":
        """One table row, from ``table: 15, 0.35; 30, 0.6``.

        Semicolons become line breaks first. The table reader takes two
        numbers a line and ignores the rest of the line, which on a
        worksheet - where the whole table is typed into one box - would
        quietly keep the first pair and drop every other one.
        """
        from . import interpolate

        body = written.group("body").replace(";", "\n")
        found = interpolate.parse_table(body)
        x_unit = (written.group("unit") or "").strip()
        if x_unit:
            Quantity.of(1.0, x_unit)          # raises if it is not a unit
        return Lookup(found, x_unit, step.unit)

    def _evaluate_step(self, step: SheetStep, known: dict,
                       formulas: dict = None, givens: dict = None,
                       index: int = 0, tables: dict = None):
        """One step, against the names defined above it.

        Returns ``(answer, note, spread)``: the answer as a
        :class:`~core.quantity.Quantity`, so the next step down inherits a
        unit rather than a bare number, and how far it moves for the
        tolerances on what went into it.
        """
        text = subscripted(step.expression)
        note = ""

        # A plain value may carry its own unit: "50 mm" in a step declared
        # mm stays 50; in one declared m it becomes 0.05.
        # "5000 +/- 50 N" is a given, not an expression. Without asking
        # first it goes down the expression path, where the unit lifting
        # turns the 50 N into a name and leaves "5000 +/- _given_0" for
        # the parser, which is not Python and says so unhelpfully.
        formulas = {} if formulas is None else formulas
        givens = {} if givens is None else givens
        name = canonical_name(subscripted(step.name))

        value_text, given_unit = unit_tools.split_quantity(text)
        if Quantity.TOLERANCE.match(text):
            typed = Quantity.parse(text)
            if step.unit:
                typed = self._as_declared(step, typed)
            self._is_a_given(name, typed, formulas, givens)
            return typed, note, None
        if not _looks_like_expression(value_text):
            typed = Quantity.parse(text)
            if not given_unit and step.unit:
                given = self._as_declared(step, typed)
                self._is_a_given(name, given, formulas, givens)
                return given, note, None
            if given_unit and step.unit and given_unit != step.unit:
                _converted, note = unit_tools.to_declared(
                    text, step.unit, absolute=True)
            # A value typed into a row is a temperature, not a difference:
            # 20 degC in a row declared K is 293.15. A row that works one
            # out is genuinely ambiguous and is asked about instead.
            given = self._in_declared(step, typed, absolute=True)
            self._is_a_given(name, given, formulas, givens)
            return given, note, None

        # A sheet knows what its rows are called, so it says so. Otherwise
        # the parser splits the name into a product - T1 becomes T times 1,
        # which is T, and Re becomes R times e - and the sheet quietly
        # works out something other than what it says.
        # A unit written on a number inside the expression - T - 5 K, or
        # 2 m + 300 mm - is pulled out and given a name, so what is left
        # is ordinary algebra. A row name always wins over a unit of the
        # same spelling.
        # A table call is answered before anything else looks at the
        # line, and what it answered becomes a number with a unit on it -
        # the same treatment a literal like "5 K" gets, and for the same
        # reason: what is left is then ordinary algebra.
        tables = tables or {}
        text, looked_up = self._ask_the_tables(text, tables, known,
                                               f"_{index}")

        text, literals = dimensional.lift_units(text, known, f"_{index}")
        known = dict(known)
        known.update(literals)
        known.update(looked_up)
        givens.update({key: one for key, one in literals.items()})
        givens.update(looked_up)

        declared = {name: sp.Symbol(name) for name in known}
        for other in self.steps:
            other_name = canonical_name(subscripted(other.name))
            declared.setdefault(other_name, sp.Symbol(other_name))
        declared.pop("", None)
        parsed = parse_input(text, extra_symbols=declared)
        expression = parsed.expr
        if isinstance(expression, sp.Eq):
            expression = expression.rhs

        unknown = sorted(s.name for s in expression.free_symbols
                         if s.name not in known)
        if unknown:
            uncalled = [n for n in unknown if n in tables]
            if uncalled:
                raise ParseError(
                    ", ".join(uncalled) + (" is a table" if len(uncalled) == 1
                                           else " are tables")
                    + ", which has no one value - ask it for one, as "
                    + f"{uncalled[0]}(x).")
            later = [n for n in unknown
                     if any(canonical_name(subscripted(s.name)) == n
                            for s in self.steps)]
            hint = (" They are defined further down; a sheet reads downwards."
                    if later else "")
            raise ParseError(
                "Nothing here defines " + ", ".join(unknown) + "." + hint)

        worked = dimensional.walk(expression, known).tidy()
        answer = self._in_declared(step, worked)

        # Written out in terms of the givens, so the row below inherits
        # the whole history rather than a number with a tolerance on it.
        written = expression.subs(
            {sp.Symbol(key): value for key, value in formulas.items()})
        formulas[name] = written

        # Only if something above actually carried a tolerance. Taking
        # the derivatives costs a differentiation per name, and a sheet
        # with no tolerances on it is the ordinary case.
        spread = None
        if any(one.error for one in givens.values()):
            if written.count_ops() > TOO_BIG_TO_DIFFERENTIATE:
                note = _and(note,
                            "too many steps deep to work the tolerances "
                            "out - the expression written back to the "
                            "measurements has over "
                            f"{TOO_BIG_TO_DIFFERENTIATE} operations in it")
            else:
                try:
                    spread = uncertainty.through(written, givens, answer)
                except (ParseError, ArithmeticError, ValueError,
                        OverflowError) as exc:
                    # The row's own answer is fine - it was worked out from
                    # the row above. It is the expression written all the
                    # way back to the measurements that would not go, and
                    # losing the value over that would be losing the thing
                    # the row is for.
                    note = _and(note, f"the tolerances would not work out "
                                      f"here ({exc})")
        return answer, note, spread

    @staticmethod
    def _is_a_given(name: str, value, formulas: dict, givens: dict) -> None:
        """Record a row that was typed in rather than worked out."""
        formulas[name] = sp.Symbol(name)
        givens[name] = value

    def _as_declared(self, step: SheetStep, typed: "Quantity"):
        """A number typed into a row that declares a unit, in that unit.

        That is what declaring a unit is for, and it is how nearly every
        given on a sheet is written. The rule has to be the same whether
        or not a tolerance was written on it - a bare 0.5 in a row saying
        kg/s and 0.5 +/- 0.01 in the same row are the same statement, and
        they used to go down different paths that disagreed: the first was
        taken as kg/s and the second was refused for being a plain number.

        Celsius is the exception, and it is the exception everywhere: an
        offset rather than a scale, so labelling 20 as degC is not the
        same as converting it. Left as a label the row held 20 kelvin,
        showed it back as -253 C, and handed 20 kelvin to every row below.
        """
        if not typed.plain:
            # It came with a unit of its own, so the row's job is to check
            # it rather than to supply one.
            return self._in_declared(step, typed, absolute=True)
        if step.unit in unit_tools.CELSIUS:
            return self._in_declared(step, typed, absolute=True)
        return Quantity(typed.value, parse_powers(step.unit), typed.error)

    @staticmethod
    def _in_declared(step: SheetStep, answer: "Quantity",
                     absolute: bool | None = None) -> "Quantity":
        """The answer in the unit the row declares, or a reason it cannot be.

        A row that declares nothing takes what it was given. A row that
        declares something has to be able to hold it - and where it cannot,
        the message says what the row actually comes out in, because that
        is the thing the person writing the sheet did not know.
        """
        if not step.unit:
            return answer
        if step.unit in unit_tools.CELSIUS and answer.plain:
            # A number typed into a row that says degC is a temperature in
            # degC, and is held as one.
            #
            # The tolerance comes with it unchanged. A tolerance is a
            # difference between two temperatures and a difference does
            # not care where the scale starts, so 20 +/- 0.5 degC is
            # 293.15 +/- 0.5 K - the same half kelvin. It was being
            # dropped here, which silently turned a measurement into an
            # exact number and took it out of the uncertainty sum.
            moved = Quantity.of(answer.value
                                + float(unit_tools.ABSOLUTE_ZERO), "K")
            return Quantity(moved.value, moved.powers, answer.error)
        if step.unit in unit_tools.CELSIUS:
            # Held in kelvin; the row's own display turns it back. Asking
            # to_declared for it here would raise the ambiguity, and the
            # ambiguity does not arise: a row that says degC is showing a
            # temperature, not a rise.
            if answer.unit == "K":
                return answer
            raise ParseError(
                f"This row says {step.unit}, but it works out to "
                f"{answer.unit or 'a plain number'} - "
                f"{answer.measures()} rather than a temperature.")
        try:
            touches_celsius = (answer.unit in unit_tools.CELSIUS
                               or step.unit in unit_tools.CELSIUS)
            return answer.to(step.unit,
                             absolute=absolute if touches_celsius else False)
        except QuantityError as exc:
            raise ParseError(
                f"This row says {step.unit}, but it works out to "
                f"{answer.unit or 'a plain number'}"
                + (f" - {answer.measures()} rather than "
                   f"{Quantity.of(1.0, step.unit).measures()}."
                   if answer.unit else ".")
                + f" ({exc})") from exc

    # -- storage ----------------------------------------------------------
    def to_dict(self) -> dict:
        return {"title": self.title,
                "steps": [{"name": s.name, "expression": s.expression,
                           "unit": s.unit, "note": s.note} for s in self.steps]}

    @classmethod
    def from_dict(cls, payload: dict) -> "Sheet":
        sheet = cls(title=payload.get("title", "Calculation sheet"))
        for item in payload.get("steps", []):
            sheet.add(item.get("name", ""), item.get("expression", ""),
                      item.get("unit", ""), item.get("note", ""))
        return sheet

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)

    @classmethod
    def load(cls, path: str) -> "Sheet":
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))


def _and(note: str, said: str) -> str:
    """Add a remark to a row's note without losing what was there."""
    return f"{note}   {said}" if note else said


def _looks_like_expression(text: str) -> bool:
    """True if this is arithmetic rather than a bare number."""
    try:
        float(sp.sympify(text))
        return False
    except Exception:                                 # noqa: BLE001
        return True


def blocks_for(sheet: Sheet, results: list) -> list:
    """``(heading, expression, detail)`` rows, for the picture and the report."""
    rows = [(sheet.title, None, None)]
    for result in results:
        step = result.step
        unit = getattr(result, "unit", "") or step.unit
        heading = step.name + (f"  [{unit}]" if unit else "")
        if not result.ok:
            rows.append((heading, None, "! " + result.error))
            continue
        if result.table is not None:
            # A table has no equation to draw. What is worth putting in
            # the report is the table itself, so the row shows what it
            # holds and how far it reaches.
            rows.append((heading, None,
                         step.expression
                         + (f"   -   {step.note}" if step.note else "")
                         + f"   ({result.table.describe()})"))
            continue
        try:
            drawn = sp.Eq(sp.Symbol(step.name), sp.sympify(result.value),
                          evaluate=False)
        except Exception:                             # noqa: BLE001
            drawn = None
        detail = step.expression
        if step.note:
            detail += "   -   " + step.note
        if result.note:
            detail += "   (" + result.note + ")"
        rows.append((heading, drawn, detail))
    return rows
