"""A number that knows what it measures.

``units`` already converts one unit into another. What it cannot do is
carry a unit *through* a calculation - and that is where the mistakes are.
Divide 5000 N by 20 mm^2 and the answer is 250 N/mm^2; divide it by 20 m^2
and the answer is 250 Pa, which is 250 000 times smaller. Nothing in a bare
number says which happened, and mixing millimetres with metres is the
commonest real mistake in engineering arithmetic.

So a :class:`Quantity` is a magnitude and a unit together, and the ordinary
operators do the ordinary thing with both:

    adding and subtracting   the two have to measure the same kind of
                             thing, and the right one is converted to the
                             left one's unit. 5 m + 3 mm is 5.003 m.
    multiplying, dividing    the units multiply and divide with them, so
                             N over mm^2 comes out as N/mm^2 without
                             anybody saying so.
    powers                   the exponent has to be a plain number, and
                             the unit goes up with it. The square root of
                             an area is a length.
    functions                sin, log, exp and the rest want a plain
                             number. An angle counts, because an angle is
                             a plain number - but a length is refused.

The unit is held as what it was written in rather than reduced to SI, so
an answer comes back in N/mm^2 rather than in kg/(m s^2). Reducing to base
units and back is what makes a unit-aware calculator hand you 250000000
where you wanted 250.

**What this refuses is the point of it.** A length plus a mass is not a
slip that can be recovered from by picking one; it means the expression is
wrong, and the only useful thing to do is say so and where.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from fractions import Fraction

import sympy as sp

from . import units
from .parsing import ParseError


class QuantityError(ParseError):
    """Raised when two quantities cannot be combined."""


#: Powers are kept as fractions so that the square root of an area is a
#: length exactly, rather than a length to the power 0.5000000000000001.
Power = Fraction


def _clean(powers: dict) -> dict:
    return {name: power for name, power in powers.items() if power}


@dataclass(frozen=True)
class Quantity:
    """A magnitude in a unit, where the unit is a product of named units.

    ``powers`` maps a unit name to its power: ``{"N": 1, "mm": -2}`` is
    N/mm^2. An empty mapping is a plain number.
    """

    value: float
    powers: dict = field(default_factory=dict)

    # -- making one --------------------------------------------------------
    @classmethod
    def parse(cls, text: str) -> "Quantity":
        """Read ``"50 mm"``, ``"2.5e3 N/mm^2"`` or a bare number."""
        number, unit = units.split_quantity(str(text))
        try:
            value = float(sp.sympify(number))
        except Exception as exc:                       # noqa: BLE001
            raise QuantityError(f"{text!r} is not a number.") from exc
        if unit.strip() in units.CELSIUS:
            # Held in kelvin from here on, because degrees Celsius is an
            # offset rather than a scale and there is nothing sensible to
            # multiply or divide it by. Read as a temperature, not as a
            # difference: a bare "20 degC" is twenty degrees Celsius, and
            # a rise of twenty is written as 20 K.
            return cls(value + float(units.ABSOLUTE_ZERO), {"K": Power(1)})
        return cls(value, parse_powers(unit))

    @classmethod
    def of(cls, value: float, unit: str) -> "Quantity":
        return cls(float(value), parse_powers(unit))

    # -- what it is --------------------------------------------------------
    @property
    def unit(self) -> str:
        return write_powers(self.powers)

    @property
    def plain(self) -> bool:
        """True when it is just a number."""
        return not self.powers

    def expression(self):
        """The unit as a SymPy quantity, for asking what dimension it is."""
        found = sp.Integer(1)
        for name, power in self.powers.items():
            found *= units.parse_unit(name) ** sp.Rational(power)
        return found

    def dimension(self) -> tuple:
        return units.dimension_of(self.expression())

    def measures(self) -> str:
        """A plain-English name for the dimension, for a message."""
        return name_of(self.powers)

    # -- combining ---------------------------------------------------------
    def _same_kind(self, other: "Quantity", doing: str) -> float:
        """*other* as a number in this one's unit, or a refusal."""
        if self.powers == other.powers:
            return other.value
        if self.plain != other.plain:
            plain, sized = ((self, other) if self.plain else (other, self))
            raise QuantityError(
                f"{doing.capitalize()} {sized.unit} and a plain number. "
                f"{sized.value:g} {sized.unit} measures "
                f"{sized.measures()}; {plain.value:g} measures nothing. "
                f"Give the plain one a unit, or take the other's away.")
        if self.dimension() != other.dimension():
            raise QuantityError(
                f"{doing.capitalize()} {self.unit} and {other.unit}. "
                f"{self.unit} measures {self.measures()} and {other.unit} "
                f"measures {other.measures()}, so there is no answer to "
                f"give - the expression is wrong, not the numbers.")
        return float(units.convert(other.value, other.unit, self.unit,
                                   absolute=False))

    def __add__(self, other):
        other = _as_quantity(other)
        return Quantity(self.value + self._same_kind(other, "adding"),
                        dict(self.powers))

    def __radd__(self, other):
        return _as_quantity(other) + self

    def __sub__(self, other):
        other = _as_quantity(other)
        return Quantity(self.value - self._same_kind(other, "subtracting"),
                        dict(self.powers))

    def __rsub__(self, other):
        return _as_quantity(other) - self

    def __mul__(self, other):
        other = _as_quantity(other)
        return Quantity(self.value * other.value,
                        _combine(self.powers, other.powers, 1))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = _as_quantity(other)
        if other.value == 0:
            raise QuantityError("Dividing by nothing.")
        return Quantity(self.value / other.value,
                        _combine(self.powers, other.powers, -1))

    def __rtruediv__(self, other):
        return _as_quantity(other) / self

    def __pow__(self, other):
        other = _as_quantity(other)
        if not other.plain:
            raise QuantityError(
                f"Raising something to the power of {other.value:g} "
                f"{other.unit}. An exponent has to be a plain number - "
                f"there is no such thing as x to the power of a length.")
        if self.value == 0 and other.value < 0:
            # F/A arrives here as F * A**-1, so a zero area never reaches
            # the check in __truediv__ and comes out as a ZeroDivisionError
            # from Python rather than as a sentence.
            raise QuantityError(
                f"Dividing by nothing: {self.unit or 'a plain number'} was "
                f"given as zero.")
        power = Fraction(other.value).limit_denominator(1000)
        if abs(float(power) - other.value) > 1e-12 and self.powers:
            raise QuantityError(
                f"Raising {self.unit} to the power {other.value!r}, which "
                f"is not a simple fraction, so the unit it would come out "
                f"in is not one anybody could write down.")
        return Quantity(self.value ** other.value,
                        _clean({name: p * power
                                for name, p in self.powers.items()}))

    def __neg__(self):
        return Quantity(-self.value, dict(self.powers))

    def __pos__(self):
        return self

    def __abs__(self):
        return Quantity(abs(self.value), dict(self.powers))

    # -- comparing ---------------------------------------------------------
    def __lt__(self, other):
        other = _as_quantity(other)
        return self.value < self._same_kind(other, "comparing")

    def __le__(self, other):
        other = _as_quantity(other)
        return self.value <= self._same_kind(other, "comparing")

    def __gt__(self, other):
        other = _as_quantity(other)
        return self.value > self._same_kind(other, "comparing")

    def __ge__(self, other):
        other = _as_quantity(other)
        return self.value >= self._same_kind(other, "comparing")

    # -- moving between units ---------------------------------------------
    def to(self, unit: str, absolute: bool | None = None) -> "Quantity":
        """The same quantity written in another unit."""
        wanted = parse_powers(unit)
        if wanted == self.powers:
            return self
        target = Quantity(1.0, wanted)
        if self.dimension() != target.dimension():
            raise QuantityError(
                f"{self.unit or 'a plain number'} measures "
                f"{self.measures()} and {unit or 'a plain number'} measures "
                f"{target.measures()}, so one cannot be written as the "
                f"other.")
        return Quantity(float(units.convert(self.value, self.unit, unit,
                                            absolute=absolute)),
                        wanted)

    def tidy(self) -> "Quantity":
        """The same quantity, with a unit that has been allowed to cancel.

        Units are kept as they were written, which is what makes an answer
        come back in N/mm^2 rather than in kg/(m s^2). The price is that
        two names for the same thing do not cancel by themselves: a
        Reynolds number worked out as rho v d / mu comes out in
        kg/(mm s^2 Pa), which is dimensionless and does not look it,
        because Pa and kg/(m s^2) are the same dimension under different
        names.

        So the dimension is asked for at the end. Where it is nothing, the
        answer is a plain number and is given as one, with the factor the
        units were carrying folded into it - which for mm against m is a
        thousand, and is exactly the error this whole thing exists to
        catch.
        """
        if self.plain or self.dimension():
            return self._folded()
        factor = _to_plain(self.expression())
        if factor is None:
            return self._folded()
        return Quantity(self.value * factor, {})

    def _folded(self) -> "Quantity":
        """Two names for the same kind of thing, put onto the first of them.

        mm^2*m is a real unit and a useless one. It turns up whenever two
        lengths in different units are multiplied, which is most of the
        time in practice.
        """
        moved, factor = dict(self.powers), 1.0
        for name in list(moved):
            if name not in moved:
                continue
            for other in list(moved):
                if other == name or other not in moved:
                    continue
                if not _looks_like(name, other):
                    continue
                power = moved.pop(other)
                factor *= float(units.convert(1.0, other, name,
                                              absolute=False)) ** float(power)
                moved[name] = moved.get(name, Power(0)) + power
        cleaned = _clean(moved)
        if cleaned == self.powers:
            return self
        return Quantity(self.value * factor, cleaned)

    def __str__(self) -> str:
        shown = f"{self.value:.10g}"
        return f"{shown} {self.unit}".strip()

    def __repr__(self) -> str:
        return f"Quantity({self.value!r}, {self.unit!r})"


def _looks_like(one: str, other: str) -> bool:
    try:
        return units.compatible(one, other)
    except units.UnitError:
        return False


def _to_plain(expression):
    """How many of nothing a dimensionless unit expression is worth.

    kg/(m s^2 Pa) is one. mm/m is a thousandth. Reduced through SI base
    units, because two names for the same thing will not cancel any other
    way.
    """
    from sympy.physics import units as u

    try:
        reduced = sp.simplify(u.convert_to(
            expression, [u.meter, u.kilogram, u.second, u.ampere, u.kelvin,
                         u.mole, u.candela]))
    except Exception:                                  # noqa: BLE001
        return None
    if getattr(reduced, "free_symbols", set()) or not reduced.is_number:
        return None
    try:
        return float(reduced)
    except (TypeError, ValueError):
        return None


def _as_quantity(value) -> Quantity:
    if isinstance(value, Quantity):
        return value
    if isinstance(value, str):
        return Quantity.parse(value)
    return Quantity(float(value), {})


def _combine(one: dict, other: dict, sign: int) -> dict:
    """Multiply two unit products together, or divide them.

    Units of the same dimension but different size - mm and m in one
    expression - are folded onto the left one's, so an area comes out as
    mm^2 rather than as mm*m, which is a real unit and a useless one.
    """
    found = dict(one)
    for name, power in other.items():
        if name in found:
            found[name] += sign * power
            continue
        matching = _same_dimension_as(name, found)
        if matching:
            # Fold it in. The magnitude has already been multiplied, so
            # the conversion factor has to go somewhere - it cannot, at
            # this level, which is why this only folds identical names and
            # leaves the rest alone. See harmonise().
            found[name] = sign * power
        else:
            found[name] = sign * power
    return _clean(found)


def _same_dimension_as(name: str, powers: dict):
    for other in powers:
        try:
            if units.compatible(name, other):
                return other
        except units.UnitError:
            continue
    return None


def harmonise(one: Quantity, other: Quantity) -> tuple:
    """Put two quantities onto one set of units before combining them.

    ``mm * m`` is a real unit and a useless one. Where the two carry units
    of the same kind under different names, the right-hand one is written
    in the left-hand one's, so the product comes out in something that can
    be read.
    """
    swaps = {}
    for name in other.powers:
        if name in one.powers:
            continue
        match = _same_dimension_as(name, one.powers)
        if match:
            swaps[name] = match
    if not swaps:
        return one, other
    moved = other
    for name, wanted in swaps.items():
        power = moved.powers[name]
        factor = float(units.convert(1.0, name, wanted, absolute=False))
        rest = dict(moved.powers)
        del rest[name]
        rest[wanted] = rest.get(wanted, Power(0)) + power
        moved = Quantity(moved.value * factor ** float(power), _clean(rest))
    return one, moved


# --------------------------------------------------------------------------
# Reading and writing a unit
# --------------------------------------------------------------------------
def parse_powers(unit: str) -> dict:
    """``"N/mm^2"`` -> ``{"N": 1, "mm": -2}``.

    Parsed with SymPy rather than by splitting on slashes, so that
    ``J/(kg*K)`` and ``kg*m/s^2`` and ``1/s`` all read the way they look.
    """
    cleaned = (unit or "").strip()
    if units.is_dimensionless(cleaned):
        return {}
    names = {name: sp.Symbol(name) for name in units.UNITS}
    for name in units.CELSIUS:
        names[name] = sp.Symbol("K")
    try:
        expression = sp.sympify(cleaned.replace("^", "**"), locals=names)
    except Exception as exc:                           # noqa: BLE001
        raise QuantityError(f"Unit {unit!r} is not one I know.") from exc
    if not isinstance(expression, sp.Expr):
        raise QuantityError(f"Unit {unit!r} is not one I know.")

    found: dict = {}
    for piece, power in expression.as_powers_dict().items():
        if piece == 1:
            continue
        if not isinstance(piece, sp.Symbol) or str(piece) not in units.UNITS:
            raise QuantityError(
                f"Unit {unit!r} has {piece} in it, which is not a unit I "
                f"know.")
        if not power.is_Rational:
            raise QuantityError(
                f"Unit {unit!r} raises {piece} to {power}, which is not a "
                f"power a unit can have.")
        found[str(piece)] = Power(int(power.p), int(power.q))

    # Kept in the order they were written. SymPy hands them back in its own
    # order, which would turn J/(kg*K) into J/(K*kg) - the same unit,
    # written a way nobody writes it, on every answer.
    def written(name: str) -> int:
        # Whole words only. Without the boundaries "K" is found
        # inside "kg", which sorts it first and hands back
        # J/(K*kg) anyway - the same unit, written the way nobody
        # writes it, on every answer.
        place = re.search(r"\b" + re.escape(name) + r"\b",
                          cleaned)
        return place.start() if place else len(cleaned)

    return _clean({name: found[name] for name in sorted(found, key=written)})


def write_powers(powers: dict) -> str:
    """``{"N": 1, "mm": -2}`` -> ``"N/mm^2"``."""
    if not powers:
        return ""
    top, bottom = [], []
    for name, power in powers.items():
        size = abs(power)
        piece = name if size == 1 else f"{name}^{_power(size)}"
        (top if power > 0 else bottom).append(piece)
    above = "*".join(top) if top else "1"
    if not bottom:
        return above
    below = "*".join(bottom)
    if len(bottom) > 1:
        below = f"({below})"
    return f"{above}/{below}"


def _power(size: Power) -> str:
    return str(size.numerator) if size.denominator == 1 else str(size)


#: What a dimension is called, so a refusal can say "a length and a mass"
#: rather than printing two exponent tuples at somebody.
NAMED = {
    (): "nothing",
    (("length", 1),): "a length",
    (("length", 2),): "an area",
    (("length", 3),): "a volume",
    (("mass", 1),): "a mass",
    (("time", 1),): "a time",
    (("temperature", 1),): "a temperature",
    (("current", 1),): "a current",
    (("amount_of_substance", 1),): "an amount of substance",
    (("length", 1), ("time", -1)): "a speed",
    (("length", 1), ("time", -2)): "an acceleration",
    (("length", 1), ("mass", 1), ("time", -2)): "a force",
    (("length", -1), ("mass", 1), ("time", -2)): "a pressure",
    (("length", 2), ("mass", 1), ("time", -2)): "an energy",
    (("length", 2), ("mass", 1), ("time", -3)): "a power",
    (("length", -3), ("mass", 1)): "a density",
    (("length", 3), ("time", -1)): "a flow rate",
    (("time", -1),): "a frequency",
    (("length", 2), ("time", -2), ("temperature", -1)): "a specific heat",
    (("length", 1), ("mass", 1), ("temperature", -1), ("time", -3)):
        "a thermal conductivity",
    (("length", 2), ("time", -1)): "a diffusivity",
    (("length", -1), ("mass", 1), ("time", -1)): "a dynamic viscosity",
    (("length", 2), ("mass", 1), ("time", -2), ("temperature", -1)):
        "a heat capacity",
    (("length", 2), ("mass", 1), ("time", -3), ("temperature", -1)):
        "a thermal conductance",
    (("length", 4),): "a second moment of area",
    (("length", 1), ("mass", 1), ("time", -2)): "a force",
    (("length", 2), ("mass", 1), ("time", -2)): "an energy or a moment",
    (("mass", 1), ("time", -1)): "a mass flow",
    (("current", 1), ("time", 1)): "a charge",
    (("length", 2), ("mass", 1), ("current", -1), ("time", -3)):
        "a voltage",
}

#: Single named units worth offering as "this is also that", in the order
#: they are preferred.
EQUIVALENTS = ("N", "J", "W", "V", "A", "ohm", "Hz", "C", "F", "H", "Pa",
               "L", "m", "kg", "s", "K")

#: How far the magnitude may move for the swap to still be an improvement,
#: depending on how much tidier it makes the unit.
#:
#: Losing two names or more is worth a lot: kN/(GPa*cm) is a length nobody
#: would recognise as one, and being told it is 0.003 m is worth the
#: change of size. Losing one name is worth almost nothing on its own -
#: a stress in kN/m^2 is a pascal a thousand times over, and being told so
#: replaces a readable number with an unreadable one for no gain.
MUCH_TIDIER = 1e6
A_LITTLE_TIDIER = 10.0


def equivalents(value: "Quantity") -> list:
    """The same quantity in a single named unit, where that reads better.

    A force worked out as kg*m/s^2 is worth showing as newtons: same
    number, one name instead of three. A stress worked out as N/mm^2 is
    not worth showing as 250000000 Pa: one name instead of two, and a
    number nobody can read. So the test is both - fewer names *and* a
    magnitude that has not run away.
    """
    if value.plain or len(value.powers) < 2:
        return []
    for name in EQUIVALENTS:
        try:
            if Quantity(1.0, {name: Power(1)}).dimension() != value.dimension():
                continue
            swapped = value.to(name, absolute=False)
        except Exception:                              # noqa: BLE001
            continue
        saved = len(value.powers) - len(swapped.powers)
        if saved < 1:
            continue
        allowed = MUCH_TIDIER if saved >= 2 else A_LITTLE_TIDIER
        moved = abs(swapped.value / value.value) if value.value else 1.0
        if 1.0 / allowed <= moved <= allowed:
            return [swapped]
    return []


#: Sorted on the way in, so an entry above can be written in the order it
#: is said - length, time, temperature - rather than in the order the
#: dimension system happens to hand its bases back. Written unsorted, an
#: entry simply never matches and the name quietly falls back to
#: "whatever J/(kg*K) measures".
NAMED = {tuple(sorted(key)): name for key, name in NAMED.items()}


def name_of(powers: dict) -> str:
    """A plain-English name for what a unit measures."""
    if not powers:
        return "nothing"
    try:
        found = Quantity(1.0, powers).dimension()
    except Exception:                                  # noqa: BLE001
        return f"whatever {write_powers(powers)} measures"
    named = NAMED.get(tuple(sorted(found)))
    if named:
        return named
    return f"whatever {write_powers(powers)} measures"


# --------------------------------------------------------------------------
# Functions of a quantity
# --------------------------------------------------------------------------
#: The ones that only mean anything for a plain number. Trigonometry is
#: separate: an angle is a plain number in SI, but degrees are not, so it
#: is converted rather than refused.
PLAIN_ONLY = ("exp", "log", "ln", "log10", "sinh", "cosh", "tanh")
TRIGONOMETRY = ("sin", "cos", "tan", "asin", "acos", "atan")


def as_angle(value: Quantity) -> float:
    """An angle in radians, from a plain number or from degrees."""
    if value.plain:
        return value.value
    try:
        return float(units.convert(value.value, value.unit, "rad",
                                   absolute=False))
    except units.UnitError:
        raise QuantityError(
            f"Taking the sine of {value.value:g} {value.unit}, which "
            f"measures {value.measures()}. Trigonometry wants an angle."
        ) from None


def apply(name: str, value: Quantity) -> Quantity:
    """A named function of a quantity, refusing the ones that make no sense."""
    if name in TRIGONOMETRY:
        angle = as_angle(value)
        if name.startswith("a"):
            if not value.plain:
                raise QuantityError(
                    f"{name} of {value.unit} - an inverse trigonometric "
                    f"function takes a ratio, which is a plain number.")
            return Quantity(getattr(math, name)(value.value),
                            {"rad": Power(1)})
        return Quantity(getattr(math, name)(angle), {})
    if name in PLAIN_ONLY:
        if not value.plain:
            raise QuantityError(
                f"{name} of {value.value:g} {value.unit}, which measures "
                f"{value.measures()}. {name} wants a plain number - a "
                f"logarithm of a length would depend on whether you "
                f"measured it in metres or in feet.")
        function = {"ln": math.log, "log": math.log,
                    "log10": math.log10}.get(name, None)
        if function is None:
            function = getattr(math, name)
        return Quantity(function(value.value), {})
    if name == "sqrt":
        return value ** Quantity(0.5, {})
    if name == "abs":
        return abs(value)
    raise QuantityError(f"{name} is not a function I can apply to a unit.")
