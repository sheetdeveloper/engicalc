"""Material indices, worked out rather than looked up.

Choosing what to make something out of is a piece of algebra, and the
recipe for it is mechanical enough to be done rather than remembered:

    minimise      an objective          m = rho * A * L
    subject to    a constraint          S = C * E * I / L**3
    by choosing   a free variable       A

Eliminate the free variable between the two and the objective falls into
two parts: things that are fixed by the job - the length, the stiffness
asked for, the number that says what shape the section is - and a group of
material properties. Only the second part depends on what the part is made
of, so only the second part can decide it. That group is the index.

Deriving it matters, because the exponent is the whole content of an index
and it is the easy thing to get wrong. ``E^(1/2)/rho`` for a beam and
``E^(1/3)/rho`` for a panel look near enough identical written down, and
they put different materials at the top of the list. Written out here the
exponent is a consequence of the section rule rather than a number
somebody typed, and a wrong one would have to come from a wrong statement
of the mechanics.

Not every index needs eliminating. Some are a direct statement of what is
wanted - the energy a spring stores per unit volume is
``sigma_y^2 / (2E)``, and there is no free variable in it. Those are
written with no constraint and go through the same separation, so their
exponents are still counted off the algebra rather than typed.

Some indices honestly have three properties in them, and a chart with two
axes cannot draw one. Rather than shorten the algebra to fit the picture,
the third is derived, named in ``also``, and printed beside the index on
the chart - because holding it constant along the guideline is a real
restriction on who the chart is ranking, and a reader who is not told
that is being misled by a correct-looking line.

That is not a hypothetical. Both places it happens here were already in
the shipped table with the third property demoted to a parenthesis: the
energy a spring stores per unit weight is ``sigma_y^2/(E*rho)`` and not
``sigma_y^2/rho``, and thermal shock resistance is ``sigma_y/(E*alpha)``
and not ``sigma_y/E`` "with a low expansion".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from .parsing import ParseError

# --------------------------------------------------------------------------
# What counts as a material property
# --------------------------------------------------------------------------
#: The symbol an engineer writes, and the property it is in the materials
#: database. Everything in a job that is not one of these is geometry, load,
#: or a performance that has been asked for.
PROPERTY_OF = {
    "rho": "density",
    "E": "youngs",
    "G": "shear",
    "nu": "poisson",
    "sigma_y": "yield",
    "sigma_u": "uts",
    "K_IC": "toughness",
    "k": "conductivity",
    "c_p": "specific_heat",
    "alpha": "expansion",
    "T_melt": "melting",
    "T_max": "service",
    "rho_e": "resistivity",
}

#: The other way round, for naming a property's symbol.
SYMBOL_OF = {prop: name for name, prop in PROPERTY_OF.items()}

#: Every material symbol as a positive SymPy symbol. Positive, because a
#: density is, and because ``sqrt(E**2)`` only simplifies to ``E`` when
#: SymPy has been told so.
SYMBOLS = {name: sp.Symbol(name, positive=True) for name in PROPERTY_OF}


def _symbol(name: str):
    """A symbol, positive whether it is a property or a length."""
    return SYMBOLS.get(name) or sp.Symbol(name, positive=True)


#: A name in an expression: a letter, then letters, digits or underscores.
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _known(text: str) -> dict:
    """Every name in *text*, declared as a positive symbol.

    Declared, not left to sympify, because sympify's own namespace already
    means something by half of them: ``E`` is Euler's number, ``I`` the
    imaginary unit, ``S`` the singleton registry. In this file those are
    Young's modulus, a second moment of area and a stiffness, and a
    constraint that silently read ``E`` as 2.718 would derive an index
    with the modulus quietly missing from it.
    """
    return {name: _symbol(name) for name in set(_NAME.findall(text))}


def _parse(text: str):
    """One side of a job, as an expression.

    ``a = b`` is read as ``a - b``, so a constraint can be written the way
    it is written in a book rather than rearranged to equal nought first.
    """
    text = str(text).strip()
    try:
        names = _known(text)
        if "=" in text:
            left, right = text.split("=", 1)
            return sp.sympify(left, locals=names) - \
                sp.sympify(right, locals=names)
        return sp.sympify(text, locals=names)
    except Exception as problem:                          # noqa: BLE001
        raise ParseError(f"Cannot read '{text}': {problem}") from problem


# --------------------------------------------------------------------------
# A job, and the index that comes out of it
# --------------------------------------------------------------------------
@dataclass
class Job:
    """A thing to be made, stated so that an index can be derived from it.

    ``objective`` is what is to be made small - usually the mass. Where
    the point is to make something *large* - the energy a spring stores -
    say so with ``bigger_is_better``, and the objective is turned over
    before the properties are separated out.

    ``constraint`` is what must still be true afterwards, and ``free`` is
    the one thing the designer may change to meet it: the section area,
    the wall thickness. ``shape`` says how the section follows from that
    one thing, and it is where the difference between a beam and a panel
    lives.
    """

    name: str
    objective: str
    free: str = ""
    constraint: str = ""
    shape: dict = field(default_factory=dict)
    bigger_is_better: bool = False
    note: str = ""
    #: Which two properties to draw it against, when the honest index has
    #: three. There is no right answer to that - the third property is
    #: held constant along the guideline whichever pair is chosen - so it
    #: is stated rather than picked by whatever order a dict came out in.
    plot_against: tuple = ()


@dataclass
class Index:
    """The group of material properties a job comes down to.

    ``expression`` is maximised: a material higher up it is a better
    choice for that job, all else equal.
    """

    job: Job
    expression: sp.Expr
    powers: dict                 # {property name: exponent, signed}
    also: list                   # properties past the two a chart can hold

    # -- what the chart needs ---------------------------------------------
    @property
    def up(self) -> str:
        """The property that goes up the chart - the one wanted large."""
        if self.job.plot_against:
            return self.job.plot_against[1]
        wanted = [prop for prop, power in self.powers.items() if power > 0]
        return wanted[0] if wanted else ""

    @property
    def across(self) -> str:
        """The property that goes across it - the one wanted small."""
        if self.job.plot_against:
            return self.job.plot_against[0]
        wanted = [prop for prop, power in self.powers.items() if power < 0]
        return wanted[0] if wanted else ""

    @property
    def power_up(self) -> float:
        return float(self.powers.get(self.up, 0.0))

    @property
    def power_across(self) -> float:
        return float(-self.powers.get(self.across, 0.0))

    @property
    def written(self) -> str:
        """How it is written in a book: ``E^(1/2) / rho``."""
        return _written(self.expression)

    @property
    def plottable(self) -> bool:
        """Whether a two-axis chart can show it."""
        return bool(self.up and self.across)

    @property
    def exact_on_a_chart(self) -> bool:
        """Whether the chart shows the *whole* index or a slice of it.

        An index of three properties is drawn against two of them, and
        the third is then held constant along the guideline. That is a
        real restriction - it means the ranking is only right among
        materials whose third property is alike - and it is said out
        loud rather than left for the reader to notice.
        """
        return not self.also

    def as_entry(self) -> tuple:
        """The tuple `materials.INDICES` is made of."""
        written = self.written
        if self.also:
            written += "  (" + " and ".join(
                f"a low {prop}" if self.powers[prop] < 0 else f"a high {prop}"
                for prop in self.also) + ")"
        return (self.job.name, self.across, self.up,
                self.power_up, self.power_across, written)


def _written(expression) -> str:
    """``sqrt(E)/rho`` the way it is written down: ``E^(1/2) / rho``.

    SymPy prefers ``sqrt(E)``; a book prefers ``E^(1/2)``, because the
    exponent is the thing being said and burying it in a function name
    hides it. A product underneath gets brackets, or ``a / b*c`` reads as
    ``(a/b)*c``, which is a different index.
    """
    top, bottom = sp.fraction(sp.together(expression))

    def part(side, bracket: bool) -> str:
        text = str(side).replace("**", "^")
        if text.startswith("sqrt(") and text.endswith(")"):
            text = text[5:-1] + "^(1/2)"
        if bracket and (side.is_Add or side.is_Mul):
            text = f"({text})"
        return text

    if bottom == 1:
        return part(top, False)
    return f"{part(top, False)} / {part(bottom, True)}"


# --------------------------------------------------------------------------
# The derivation
# --------------------------------------------------------------------------
def derive(job: Job) -> Index:
    """Eliminate the free variable and keep what depends on the material."""
    objective = _parse(job.objective)

    if job.constraint:
        if not job.free:
            raise ParseError(f"{job.name}: a constraint needs a free "
                             f"variable to eliminate.")
        constraint = _parse(job.constraint)
        for name, rule in job.shape.items():
            constraint = constraint.subs(_symbol(name), _parse(rule))
            objective = objective.subs(_symbol(name), _parse(rule))
        free = _symbol(job.free)
        answers = sp.solve(constraint, free, dict=True)
        answers = [one for one in answers
                   if one[free].is_real is not False
                   and one[free].is_positive is not False] or answers
        if not answers:
            raise ParseError(f"{job.name}: cannot solve the constraint for "
                             f"{job.free}.")
        objective = objective.subs(answers[0])

    objective = sp.powsimp(sp.simplify(objective), force=True)
    group = _material_part(objective)
    # An objective is made small; an index is made large. Turning it over
    # is the whole of the difference, and doing it here means every index
    # below reads the same way round.
    if not job.bigger_is_better:
        group = 1 / group
    group = sp.powsimp(sp.simplify(group), force=True)
    powers = _powers(group)
    return Index(job=job, expression=group, powers=powers,
                 also=_crowded(powers))


def _material_part(expression):
    """The factors made of material properties, and nothing else."""
    kept = sp.Integer(1)
    for factor, power in expression.as_powers_dict().items():
        if factor.free_symbols & set(SYMBOLS.values()):
            kept *= factor ** power
    return kept


def _powers(expression) -> dict:
    """{property: exponent}, signed - positive wanted large."""
    found = {}
    for factor, power in expression.as_powers_dict().items():
        if factor in SYMBOLS.values():
            found[PROPERTY_OF[factor.name]] = sp.nsimplify(power)
    return found


def _crowded(powers: dict) -> list:
    """Properties past the two a two-axis chart can hold.

    Named rather than dropped. An index of three properties is not wrong,
    it is only unplottable, and a chart that quietly threw one away would
    be recommending materials on an index nobody stated.
    """
    if len(powers) <= 2:
        return []
    up = [p for p, n in powers.items() if n > 0]
    down = [p for p, n in powers.items() if n < 0]
    return sorted(up[1:] + down[1:])


# --------------------------------------------------------------------------
# The jobs themselves
# --------------------------------------------------------------------------
#: A tie carries its load along its length, so its area is set by the load
#: alone. A beam carries it across, so the area is set by the second moment
#: - and that is why the exponent changes.
#:
#: The shape rules are for the simplest section that keeps its proportions
#: as it grows: a square of area A has I = A^2/12 and a depth of sqrt(A),
#: so its section modulus is A^(3/2)/6. A panel is different because its
#: width is given by the job and only the thickness is free.
JOBS = [
    Job("Light, stiff tie", "rho*A*L", free="A",
        constraint="S = E*A/L",
        note="a rod pulled along its length, held to a stiffness"),
    Job("Light, stiff beam", "rho*A*L", free="A",
        constraint="S = C*E*I/L**3", shape={"I": "A**2/12"},
        note="bent about its own axis, square section"),
    Job("Light, stiff panel", "rho*b*t*L", free="t",
        constraint="S = C*E*b*t**3/(12*L**3)",
        note="width given by the job, thickness free"),
    Job("Light, strong tie", "rho*A*L", free="A",
        constraint="F = sigma_y*A",
        note="held to a load rather than to a stiffness"),
    Job("Light, strong beam", "rho*A*L", free="A",
        constraint="M = sigma_y*A**(3/2)/6",
        note="square section, first yield at the outer fibre"),
    Job("Light, strong panel", "rho*b*t*L", free="t",
        constraint="M = sigma_y*b*t**2/6"),

    # No free variable in these: they say what is wanted outright.
    Job("Springs: energy stored per volume", "sigma_y**2/(2*E)",
        bigger_is_better=True,
        note="the area under the elastic line, per unit volume"),
    Job("Springs: energy stored per weight", "sigma_y**2/(2*E*rho)",
        bigger_is_better=True, plot_against=("density", "yield"),
        note="the same, per unit mass - three properties, so a chart "
             "can only show two of them"),
    Job("Flywheels and rotors", "sigma_y/rho", bigger_is_better=True,
        note="the rim stress is rho*v^2, so the speed it can reach "
             "depends on strength over density and on nothing else"),
    Job("Elastic hinges", "sigma_y/E", bigger_is_better=True,
        note="how far it can bend before it stops springing back"),
    Job("Thermal shock resistance", "sigma_y/(E*alpha)",
        bigger_is_better=True, plot_against=("youngs", "yield"),
        note="the temperature step that first yields it"),
    Job("Damage tolerance", "K_IC/sigma_y", bigger_is_better=True,
        note="how big a crack it tolerates before it breaks"),
    Job("Insulation, thin as possible", "T_max/k", bigger_is_better=True),
]


def all_indices() -> list:
    """Every job, derived. Cached, because the algebra is not free."""
    global _DERIVED
    if _DERIVED is None:
        _DERIVED = [derive(job) for job in JOBS]
    return _DERIVED


_DERIVED = None


def entries() -> list:
    """The derived indices in the shape the charts expect.

    Only the ones a two-axis chart can hold. The three-property ones are
    still derived and still correct - they are simply not a line that can
    be laid across a plot of two properties.
    """
    return [one.as_entry() for one in all_indices() if one.plottable]


def find(name: str):
    """One derived index by the name of its job."""
    for one in all_indices():
        if one.job.name == name:
            return one
    return None
