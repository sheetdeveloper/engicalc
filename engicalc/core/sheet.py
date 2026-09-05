"""A calculation sheet: several steps in order, each able to use the last.

Real work is never one calculation. It is a diameter, then an area from that
diameter, then a velocity from the area, then a Reynolds number from the
velocity - and if the diameter changes, everything after it should follow.
Doing that in the calculator means copying numbers between boxes by hand,
which is where transcription errors come from.

A sheet is a list of named steps evaluated top to bottom. Each step defines a
name, and any step may use the names defined above it. Nothing may use a name
defined below it: a sheet reads downwards, like the page it stands in for.

Each step carries its own unit, so a diameter declared in mm is stored in mm
and used as mm, and :mod:`core.units` converts when a value arrives in
something else.

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

from . import units as unit_tools
from .display import fmt, fmt_number
from .parsing import ParseError, canonical_name, parse_input

#: Checked against the canonical spelling, which is always
#: ASCII however the name was typed.
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

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
    value: object = None          # SymPy number, or None if it failed
    error: str = ""
    note: str = ""                # a unit conversion, or another remark

    @property
    def ok(self) -> bool:
        return self.error == ""

    def text(self) -> str:
        if not self.ok:
            return f"{self.step.name}: {self.error}"
        shown = fmt_number(self.value) if getattr(self.value, "is_number",
                                                  False) else fmt(self.value)
        return f"{self.step.name} = {shown}" + (
            f" {self.step.unit}" if self.step.unit else "")


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
        results: list = []
        seen: set = set()

        for step in self.steps:
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
            name = canonical_name(step.name)
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

            try:
                value, note = self._evaluate_step(step, known)
            except ParseError as exc:
                result.error = str(exc)
                continue
            except Exception as exc:                  # noqa: BLE001
                result.error = f"Could not work this out: {exc}"
                continue

            result.value = value
            result.note = note
            known[name] = value

        return results

    def _evaluate_step(self, step: SheetStep, known: dict):
        """One step, against the names defined above it."""
        text = step.expression
        note = ""

        # A plain value may carry its own unit: "50 mm" in a step declared mm
        # stays 50; in one declared m it becomes 0.05.
        value_text, given_unit = unit_tools.split_quantity(text)
        if given_unit and step.unit and not _looks_like_expression(value_text):
            converted, note = unit_tools.to_declared(text, step.unit)
            return sp.nsimplify(converted, rational=False), note

        # A sheet knows what its rows are called, so it says so. Otherwise
        # the parser splits the name into a product - T1 becomes T times 1,
        # which is T, and Re becomes R times e - and the sheet quietly works
        # out something other than what it says.
        declared = {name: sp.Symbol(name) for name in known}
        for other in self.steps:
            declared.setdefault(canonical_name(other.name),
                                sp.Symbol(canonical_name(other.name)))
        declared.pop("", None)
        parsed = parse_input(text, extra_symbols=declared)
        expression = parsed.expr
        if isinstance(expression, sp.Eq):
            expression = expression.rhs

        unknown = sorted(s.name for s in expression.free_symbols
                         if s.name not in known)
        if unknown:
            later = [n for n in unknown
                     if any(canonical_name(s.name) == n for s in self.steps)]
            hint = (" They are defined further down; a sheet reads downwards."
                    if later else "")
            raise ParseError(
                "Nothing here defines " + ", ".join(unknown) + "." + hint)

        substituted = expression.subs(
            {sp.Symbol(name): value for name, value in known.items()})
        return sp.simplify(substituted), note

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
        heading = step.name + (f"  [{step.unit}]" if step.unit else "")
        if not result.ok:
            rows.append((heading, None, "! " + result.error))
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
