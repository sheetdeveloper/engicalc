"""Data model for the engineering formula library."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from ..core.parsing import parse_for_display, parse_input


@dataclass(frozen=True)
class Variable:
    symbol: str
    description: str
    unit: str = ""
    typical: str = ""      # a sensible default value, as a string

    def label(self) -> str:
        return f"{self.symbol} - {self.description}" + (f" [{self.unit}]" if self.unit else "")


@dataclass(eq=False)
class Formula:
    key: str                       # unique id, e.g. "thermo.sensible_heat"
    name: str
    branch: str                    # Thermodynamics, Fluid Mechanics, ...
    category: str                  # sub-grouping within the branch
    equation: str                  # "Q = m*c*(T2 - T1)"
    variables: list[Variable] = field(default_factory=list)
    notes: str = ""
    assumptions: str = ""
    tags: tuple = ()
    reference: str = ""

    # -- lazily built SymPy objects ---------------------------------------
    _eq: sp.Eq | None = field(default=None, repr=False, compare=False)
    _latex: str | None = field(default=None, repr=False, compare=False)

    @property
    def eq(self) -> sp.Eq:
        if self._eq is None:
            # Declare the formula's own symbols locally so that names like E, I
            # or e are read as Young's modulus / second moment / eccentricity
            # rather than Euler's number or the imaginary unit.
            local = {v.symbol: sp.Symbol(v.symbol) for v in self.variables}
            parsed = parse_input(self.equation, extra_symbols=local)
            expr = parsed.expr
            if not isinstance(expr, sp.Eq):
                expr = sp.Eq(expr, 0)
            self._eq = expr
        return self._eq

    @property
    def display_latex(self) -> str:
        """LaTeX with the terms in the order the formula is normally written.

        SymPy reorders as it evaluates - ``F = m*a`` would come back as
        ``F = a m``. Parsing without evaluation and printing with
        ``order="none"`` keeps the textbook arrangement.
        """
        if self._latex is None:
            try:
                local = {v.symbol: sp.Symbol(v.symbol) for v in self.variables}
                expr = parse_for_display(self.equation, local)
                self._latex = sp.latex(expr, order="none")
            except Exception:  # noqa: BLE001
                self._latex = sp.latex(self.eq)
        return self._latex

    @property
    def symbols(self) -> list[sp.Symbol]:
        return sorted(self.eq.free_symbols, key=lambda s: s.name)

    def variable(self, symbol: str) -> Variable | None:
        for v in self.variables:
            if v.symbol == symbol:
                return v
        return None

    def unit_of(self, symbol: str) -> str:
        v = self.variable(symbol)
        return v.unit if v else ""

    def search_text(self) -> str:
        return " ".join([
            self.name, self.branch, self.category, self.equation,
            self.notes, " ".join(self.tags),
            " ".join(v.description for v in self.variables),
            " ".join(v.symbol for v in self.variables),
        ]).lower()

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return isinstance(other, Formula) and other.key == self.key


def make_builder(branch: str):
    """Return a short constructor bound to *branch* (keeps the data files terse)."""

    def build(key, name, category, equation, variables, notes="",
              assumptions="", tags=(), reference=""):
        vs = [Variable(sym, *rest) if isinstance(rest, tuple) else Variable(sym, rest)
              for sym, rest in variables.items()]
        slug = re.sub(r"[^a-z0-9]+", "_", branch.lower()).strip("_")
        return Formula(key=f"{slug}.{key}", name=name,
                       branch=branch, category=category, equation=equation,
                       variables=vs, notes=notes, assumptions=assumptions,
                       tags=tuple(tags), reference=reference)

    return build
