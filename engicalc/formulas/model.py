"""Data model for the engineering formula library."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import sympy as sp

from ..core.display import latex as _display_latex
from ..core.parsing import parse_for_display, parse_input


@dataclass(frozen=True)
class Variable:
    """One slot in a formula.

    ``material`` names the property of a solid this slot takes, if it
    takes one - and it is said on the formula rather than worked out from
    the words. A drag force and a sheet of steel both call something
    "density", and only one of them wants a material out of the database;
    nothing in the description tells the two apart, so the formula has to.
    """

    symbol: str
    description: str
    unit: str = ""
    typical: str = ""      # a sensible default value, as a string
    material: str = ""     # the material property this slot takes, if any

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
    #: Set where a number in the formula carries units of its own, so the
    #: two sides do not balance dimensionally and are not meant to. It
    #: holds the reason, because "this one is exempt" with no explanation
    #: is how an exemption becomes a place to hide a mistake.
    dimensional_constant: str = ""

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
                self._latex = _display_latex(expr, order="none")
            except Exception:  # noqa: BLE001
                self._latex = _display_latex(self.eq)
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
              assumptions="", tags=(), reference="", made_of=None,
              dimensional_constant=""):
        made_of = made_of or {}
        vs = [Variable(sym, *rest) if isinstance(rest, tuple) else Variable(sym, rest)
              for sym, rest in variables.items()]
        if made_of:
            unknown = set(made_of) - {v.symbol for v in vs}
            if unknown:
                raise KeyError(f"{key}: made_of names {sorted(unknown)}, "
                               f"which are not variables of this formula")
            vs = [replace(v, material=made_of[v.symbol])
                  if v.symbol in made_of else v for v in vs]
        slug = re.sub(r"[^a-z0-9]+", "_", branch.lower()).strip("_")
        return Formula(key=f"{slug}.{key}", name=name,
                       branch=branch, category=category, equation=equation,
                       variables=vs, notes=notes, assumptions=assumptions,
                       tags=tuple(tags), reference=reference,
                       dimensional_constant=dimensional_constant)

    return build
