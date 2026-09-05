"""Units, so millimetres and metres cannot be quietly mixed.

Every variable in the formula library already declares its unit - ``m``,
``Pa``, ``J/(kg*K)``. Until now that was a label on the screen and nothing
more: type 50 into a field that wants metres when you meant 50 mm and the
answer is a thousand times wrong, with nothing to suggest it.

This lets a value carry its own unit. Type ``50 mm`` where metres are wanted
and it converts; type ``50 kg`` and it says so rather than pretending.

Temperature is deliberately awkward here, because it is deliberately awkward
in reality: °C to K is an offset, not a scale factor, and the offset applies
to an absolute temperature but not to a difference. 20 °C is 293.15 K, while
a *rise* of 20 °C is a rise of 20 K. Nothing can tell which one a bare number
means, so :func:`convert` refuses the ambiguous case and asks.
"""

from __future__ import annotations

import re

import sympy as sp
from sympy.physics import units as u

from .parsing import ParseError

# Units that carry no dimension, and so convert to nothing.
DIMENSIONLESS = {"", "-", "none", "ratio", "currency", "count", "%",
                 "percent", "varies", "db", "-/-"}

# Substrings that make a whole unit string unconvertible, wherever they
# appear: "currency/kWh" is a price, not a quantity of anything.
OPAQUE = ("currency", "varies")

ABSOLUTE_ZERO = sp.Float("273.15")

# The unit names understood in an entry box, and in the library's own unit
# strings. Kept explicit rather than pulled from SymPy's namespace so that
# what is accepted is a decision rather than an accident.
UNITS: dict = {
    # length
    "m": u.meter, "meter": u.meter, "metre": u.meter, "meters": u.meter,
    "mm": u.mm, "cm": u.cm, "km": u.km, "um": u.um, "micron": u.um,
    "in": u.inch, "inch": u.inch, "inches": u.inch, "ft": u.foot,
    "foot": u.foot, "feet": u.foot, "yd": u.yard, "mile": u.mile,
    # mass
    "kg": u.kilogram, "g": u.gram, "tonne": u.metric_ton, "t": u.metric_ton,
    "lb": u.pound, "lbm": u.pound,
    # time
    "s": u.second, "sec": u.second, "ms": u.ms, "min": u.minute,
    "h": u.hour, "hr": u.hour, "day": u.day, "year": u.year,
    # force, pressure, energy, power
    "N": u.newton, "kN": sp.Integer(1000) * u.newton,
    "MN": sp.Integer(10) ** 6 * u.newton,
    "Pa": u.pascal, "kPa": u.kilo * u.pascal, "MPa": u.mega * u.pascal,
    "GPa": u.giga * u.pascal, "bar": u.bar, "mbar": u.milli * u.bar,
    "atm": u.atmosphere, "psi": u.psi,
    "J": u.joule, "kJ": u.kilo * u.joule, "MJ": u.mega * u.joule,
    "kWh": u.kilo * u.watt * u.hour,
    # SymPy has no calorie, and the thermochemical one is the useful one
    "cal": sp.Float("4.184") * u.joule,
    "kcal": sp.Float("4184") * u.joule,
    "W": u.watt, "kW": u.kilo * u.watt, "MW": u.mega * u.watt,
    "hp": sp.Float("745.699872") * u.watt,
    # electrical
    "V": u.volt, "mV": u.milli * u.volt, "kV": u.kilo * u.volt,
    "A": u.ampere, "mA": u.milli * u.ampere, "ohm": u.ohm, "Ohm": u.ohm,
    "kohm": u.kilo * u.ohm, "F": u.farad, "uF": u.micro * u.farad,
    "H": u.henry, "mH": u.milli * u.henry, "C": u.coulomb,
    "Hz": u.hertz, "kHz": u.kilo * u.hertz, "rpm": 2 * sp.pi / u.minute,
    # temperature (scale only - the offset is handled separately)
    "K": u.kelvin,
    # amount of substance
    "mol": u.mole, "mole": u.mole, "kmol": u.kilo * u.mole,
    # angle and volume
    "rad": u.radian, "deg": sp.pi / 180 * u.radian,
    "rev": 2 * sp.pi * u.radian, "hectare": sp.Integer(10000) * u.meter ** 2,
    "ha": sp.Integer(10000) * u.meter ** 2,
    "L": u.liter, "litre": u.liter, "mL": u.milli * u.liter,
    "gal": sp.Float("3.785411784") * u.liter,
}

# Names that mean degrees Celsius. Handled apart from the table above,
# because an offset is not a unit conversion.
CELSIUS = {"degC", "C_deg", "celsius", "oC", "°C"}


class UnitError(ParseError):
    """Raised when two quantities cannot be compared or converted."""


def is_dimensionless(unit: str) -> bool:
    cleaned = (unit or "").strip().lower()
    if cleaned in DIMENSIONLESS:
        return True
    return any(token in cleaned for token in OPAQUE)


def _namespace() -> dict:
    return dict(UNITS)


def parse_unit(text: str):
    """A unit string - ``m``, ``kPa``, ``J/(kg*K)`` - as a SymPy quantity."""
    cleaned = (text or "").strip()
    if is_dimensionless(cleaned):
        return sp.Integer(1)
    if cleaned in CELSIUS:
        return u.kelvin                       # scale of one; offset elsewhere
    # "in" is a Python keyword, so sympify cannot see it as a name at all -
    # it is a syntax error, not an unknown symbol. Spell it out first, and
    # only as a whole word: without the boundaries this rewrites 'min' to
    # 'minch' and 'sin' to 'sinch'.
    cleaned = re.sub(r"\bin\b", "inch", cleaned)
    try:
        expression = sp.sympify(cleaned.replace("^", "**"),
                                locals=_namespace())
    except Exception as exc:                  # noqa: BLE001
        raise UnitError(f"Unit {text!r} is not one I know.") from exc
    if not isinstance(expression, sp.Expr) or expression.free_symbols:
        raise UnitError(f"Unit {text!r} is not one I know.")
    return expression


_VALUE_AND_UNIT = re.compile(r"^\s*([-+0-9.eE/*() ]+?)\s*([A-Za-z°][\w^/*()°]*)\s*$")


def split_quantity(text: str) -> tuple:
    """``"50 mm"`` -> ``("50", "mm")``; a bare number -> ``(text, "")``."""
    raw = (text or "").strip()
    if not raw:
        return raw, ""

    # A complete number is never a value with a unit stuck to it. Without
    # this, "200e9" - Young's modulus, and how anyone writes it - splits
    # into 200 with a unit of "e9", and the conversion then fails saying
    # e9 and Pa measure different things.
    try:
        float(raw)
        return raw, ""
    except ValueError:
        pass

    match = _VALUE_AND_UNIT.match(raw)
    if not match:
        return raw, ""
    value, unit = match.group(1).strip(), match.group(2).strip()
    if not value:
        return raw, ""
    return value, unit


def dimension_of(unit_expression):
    """What kind of quantity this is - length, pressure, energy.

    Compared dimensionally rather than by cancelling the units themselves.
    A kilowatt-hour over a megajoule does not simplify to a number, because
    watt-hour and joule are different quantity objects even though both
    measure energy, so the naive ratio test calls them incompatible.
    """
    from sympy.physics.units.systems import SI

    try:
        system = SI.get_dimension_system()
        powers = system.get_dimensional_dependencies(
            SI.get_dimensional_expr(unit_expression))
        # Keyed by name: an inch reduces to Dimension(length, L) while a
        # kilowatt-hour reduces to Dimension(length), and those two compare
        # unequal despite being the same base dimension.
        return tuple(sorted((str(base.name), power)
                            for base, power in powers.items()))
    except Exception:                         # noqa: BLE001
        return ("unknown", str(unit_expression))


def compatible(one: str, other: str) -> bool:
    """True if a value in one unit can be expressed in the other."""
    if is_dimensionless(one) and is_dimensionless(other):
        return True
    if is_dimensionless(one) or is_dimensionless(other):
        return False
    if one.strip() in CELSIUS or other.strip() in CELSIUS:
        return (one.strip() in CELSIUS or one.strip() == "K") and \
               (other.strip() in CELSIUS or other.strip() == "K")
    try:
        return dimension_of(parse_unit(one)) == dimension_of(parse_unit(other))
    except UnitError:
        return False


def convert(value, from_unit: str, to_unit: str, absolute: bool | None = None):
    """Express *value* given in *from_unit* as a number in *to_unit*.

    ``absolute`` only matters for temperature: True treats the value as a
    temperature (20 °C is 293.15 K), False as a difference (a rise of 20 °C
    is a rise of 20 K). Left as None the ambiguous case raises rather than
    guessing, because guessing wrong is a 273 kelvin error that looks
    perfectly plausible.
    """
    number = sp.sympify(value)
    source, target = (from_unit or "").strip(), (to_unit or "").strip()

    if source == target:
        return number
    if is_dimensionless(source) and is_dimensionless(target):
        return number
    if not compatible(source, target):
        raise UnitError(
            f"{source or 'a plain number'} and {target or 'a plain number'} "
            "measure different things, so one cannot be expressed as the "
            "other.")

    celsius_source, celsius_target = source in CELSIUS, target in CELSIUS
    if celsius_source or celsius_target:
        if absolute is None:
            raise UnitError(
                "Converting between °C and K needs to know whether this is a "
                "temperature or a temperature difference: 20 °C is 293.15 K, "
                "but a rise of 20 °C is a rise of 20 K.")
        if not absolute:
            return number
        if celsius_source and not celsius_target:
            return number + ABSOLUTE_ZERO
        if celsius_target and not celsius_source:
            return number - ABSOLUTE_ZERO
        return number

    converted = u.convert_to(number * parse_unit(source), parse_unit(target))
    return sp.simplify(converted / parse_unit(target))


def to_declared(text: str, declared_unit: str,
                absolute: bool | None = None) -> tuple:
    """Read a typed entry against the unit a formula expects.

    Returns ``(value, note)``. ``note`` is a sentence describing the
    conversion when one happened, so the working can say what it did rather
    than silently changing the number.
    """
    value_text, given_unit = split_quantity(text)
    if not given_unit:
        return sp.sympify(value_text), ""
    if is_dimensionless(declared_unit):
        raise UnitError(
            f"This value has no units, so {given_unit!r} does not belong "
            "on it.")
    converted = convert(value_text, given_unit, declared_unit, absolute)
    if sp.simplify(converted - sp.sympify(value_text)) == 0:
        return converted, ""
    return converted, (f"{value_text} {given_unit} = "
                       f"{sp.Float(converted, 10)} {declared_unit}")


#: Units grouped for a picker, in the order they are worth offering. Every
#: name here is a key of :data:`UNITS` (or of :data:`CELSIUS`), and every one
#: of those appears here exactly once - see the tests.
CATEGORIES: dict = {
    "Length": ["m", "mm", "cm", "km", "um", "in", "ft", "yd", "mile"],
    "Area": ["hectare"],
    "Volume": ["L", "mL", "gal"],
    "Mass": ["kg", "g", "tonne", "lb"],
    "Time": ["s", "ms", "min", "h", "day", "year"],
    "Force": ["N", "kN", "MN"],
    "Pressure": ["Pa", "kPa", "MPa", "GPa", "bar", "mbar", "atm", "psi"],
    "Energy": ["J", "kJ", "MJ", "kWh", "cal", "kcal"],
    "Power": ["W", "kW", "MW", "hp"],
    "Temperature": ["K", "degC"],
    "Angle": ["rad", "deg", "rev"],
    "Frequency": ["Hz", "kHz", "rpm"],
    "Electrical": ["V", "mV", "kV", "A", "mA", "ohm", "kohm", "F", "uF",
                   "H", "mH", "C"],
    "Amount": ["mol", "kmol"],
}

#: The spellings that are the same unit written another way. Offering all of
#: them in a picker would be a list of synonyms rather than a list of units.
ALIASES = {
    "meter", "metre", "meters", "inch", "inches", "foot", "feet", "micron",
    "sec", "hr", "t", "lbm", "litre", "mole", "Ohm", "ha",
}


def category_of(unit: str) -> str:
    """Which group *unit* is offered under, or "" if it is not offered."""
    for name, members in CATEGORIES.items():
        if unit in members:
            return name
    return ""


def same_dimension(unit: str) -> list:
    """Every offered unit measuring the same thing as *unit*.

    Decided by comparing dimensions rather than by reading the categories,
    because that is the question actually being asked - what this value can
    be expressed as. Temperature is the exception the table cannot express:
    degrees Celsius is a kelvin with an offset, so it is paired by hand.
    """
    unit = (unit or "").strip()
    if unit in CELSIUS or unit == "K":
        return ["K", "degC"]
    try:
        wanted = dimension_of(parse_unit(unit))
    except Exception:                                 # noqa: BLE001
        return []
    out = []
    for name in [n for members in CATEGORIES.values() for n in members]:
        if name in CELSIUS or name == "K":
            continue
        try:
            if dimension_of(parse_unit(name)) == wanted:
                out.append(name)
        except Exception:                             # noqa: BLE001
            continue
    return out


def looks_wrong(value, typical: str) -> str:
    """A warning when a value is wildly unlike the typical one, or "".

    The library already stores a sensible value for most variables, and the
    commonest real mistake - millimetres entered where metres are wanted -
    lands three orders of magnitude away from it. This is a hint, not a rule:
    plenty of legitimate values are far from typical, so it warns and never
    refuses.
    """
    if not typical:
        return ""
    try:
        given, usual = abs(float(sp.N(value))), abs(float(sp.sympify(typical)))
    except Exception:                         # noqa: BLE001
        return ""
    if given == 0 or usual == 0:
        return ""
    ratio = given / usual
    if 1e-3 < ratio < 1e3:
        return ""
    factor = ratio if ratio > 1 else 1 / ratio
    direction = "larger" if ratio > 1 else "smaller"
    return (f"{sp.Float(given, 6)} is about {sp.Float(factor, 2)} times "
            f"{direction} than the usual {typical}. Check the units.")
