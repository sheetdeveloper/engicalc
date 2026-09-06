"""Moist air: the state of the air in a duct.

Everything on a psychrometric chart comes from two things - how much water
vapour the air is carrying, and how much it could carry - and the second of
those is the saturation pressure of water, which this app already computes
from IAPWS-IF97 and checks against the published values. So this module is
built on that rather than on a correlation of its own: one saturation
pressure, already validated, used everywhere it is needed.

The relations on top are ASHRAE's, and they are simple enough to read:

* the humidity ratio is a mass ratio, vapour to *dry* air, which is why
  every specific quantity here is per kilogram of dry air rather than per
  kilogram of mixture - the dry air is the part that does not change as
  moisture is added or taken out;
* the enthalpy is the dry air's plus the vapour's, the vapour carrying its
  latent heat with it;
* the dew point is where the vapour already present would saturate, found by
  running the saturation pressure backwards;
* the wet bulb is where evaporating water into the air until it saturates
  leaves the enthalpy unchanged, which has to be solved for rather than
  written down.

Below freezing the water would saturate over ice rather than over liquid
water, which is a different curve and not one IF-97 region 4 covers. Rather
than quietly using the wrong one, this refuses below 0 C and says why.
"""

from __future__ import annotations

from dataclasses import dataclass

from .parsing import ParseError
from .steam import saturation_pressure, saturation_temperature

#: Standard atmospheric pressure at sea level, kPa.
STANDARD_PRESSURE = 101.325

#: The ratio of the molar masses of water and dry air. The constant that
#: turns a pressure ratio into a mass ratio.
MOLAR_RATIO = 0.621945

#: Specific heats, kJ/(kg K), and the latent heat of vaporisation at 0 C,
#: kJ/kg - ASHRAE's values for the enthalpy of moist air.
CP_AIR = 1.006
CP_VAPOUR = 1.860
H_VAPOUR_0 = 2501.0

#: The gas constant for dry air, kJ/(kg K).
R_AIR = 0.287042

#: Where the water would freeze rather than condense.
MIN_TEMPERATURE = 0.0


class PsychrometricError(ParseError):
    """Raised for air this module cannot describe."""


def _check(temperature: float, pressure: float) -> None:
    if temperature < MIN_TEMPERATURE:
        raise PsychrometricError(
            f"{temperature:g} C is below freezing, where the water saturates "
            "over ice rather than over liquid water. That is a different "
            "curve and this does not have it, so it will not guess.")
    if temperature > 200.0:
        raise PsychrometricError(
            f"{temperature:g} C is hotter than moist air is normally worked "
            "out for; above about 200 C the relations here stop applying.")
    if pressure <= 0:
        raise PsychrometricError("The air has to be at some pressure.")


def saturation_vapour_pressure(temperature: float) -> float:
    """The most water vapour the air can hold at *temperature*, in kPa.

    Straight from IAPWS-IF97, the same equation the steam tables use, so
    there is one saturation pressure in this app rather than two that
    disagree in the fourth figure.
    """
    return saturation_pressure(temperature + 273.15) * 1000.0


def humidity_ratio(vapour_pressure: float, pressure: float) -> float:
    """Mass of water vapour per kilogram of *dry* air."""
    if vapour_pressure >= pressure:
        raise PsychrometricError(
            "The vapour pressure cannot reach the total pressure - that would "
            "be steam rather than moist air.")
    return MOLAR_RATIO * vapour_pressure / (pressure - vapour_pressure)


def vapour_pressure_from_ratio(ratio: float, pressure: float) -> float:
    """The partial pressure of the vapour, from the humidity ratio."""
    if ratio < 0:
        raise PsychrometricError("There cannot be less than no moisture.")
    return pressure * ratio / (MOLAR_RATIO + ratio)


@dataclass
class MoistAir:
    """The state of moist air, every quantity per kilogram of dry air."""

    temperature: float             # dry bulb, deg C
    pressure: float                # total, kPa
    humidity_ratio: float          # kg water / kg dry air
    relative_humidity: float       # fraction, 0 to 1
    vapour_pressure: float         # kPa
    enthalpy: float                # kJ/kg dry air
    specific_volume: float         # m3/kg dry air
    dew_point: float               # deg C, nan below freezing
    wet_bulb: float                # deg C
    #: Anything that could not be worked out, and why. Empty when it all
    #: could.
    note: str = ""

    @property
    def saturated(self) -> bool:
        return self.relative_humidity >= 0.999

    def rows(self) -> list:
        """(symbol, name, value, unit), the symbol first - it is the one
        written on a psychrometric chart and in the equations."""
        return [
            ("t", "dry bulb", self.temperature, "deg C"),
            ("t_wb", "wet bulb", self.wet_bulb,
             "deg C" if self.wet_bulb == self.wet_bulb
             else "below freezing - see the note"),
            ("t_dp", "dew point", self.dew_point,
             "deg C" if self.dew_point == self.dew_point
             else "below freezing - see the note"),
            ("\u03c6", "relative humidity", self.relative_humidity * 100.0,
             "%"),
            ("W", "humidity ratio", self.humidity_ratio, "kg/kg dry air"),
            ("p_v", "vapour pressure", self.vapour_pressure, "kPa"),
            ("h", "enthalpy", self.enthalpy, "kJ/kg dry air"),
            ("v", "specific volume", self.specific_volume, "m3/kg dry air"),
        ]


def enthalpy(temperature: float, ratio: float) -> float:
    """Enthalpy of the mixture, kJ per kilogram of dry air."""
    return (CP_AIR * temperature
            + ratio * (H_VAPOUR_0 + CP_VAPOUR * temperature))


def specific_volume(temperature: float, ratio: float,
                    pressure: float) -> float:
    """Volume per kilogram of dry air, m3/kg."""
    return (R_AIR * (temperature + 273.15)
            * (1.0 + ratio / MOLAR_RATIO) / pressure)


#: Below this the water would deposit as frost rather than condense, and
#: the curve is the sublimation one - not the saturation line IF-97 has.
TRIPLE_PRESSURE = 0.611657


def dew_point(vapour_pressure: float) -> float:
    """The temperature at which the vapour already there would condense.

    Returns nan when that temperature is below freezing: the vapour would
    deposit as frost, on a curve this does not have. Everything else about
    the air is unaffected, so the rest of the state is still worth having.
    """
    if vapour_pressure <= 0:
        raise PsychrometricError(
            "Perfectly dry air never reaches a dew point.")
    if vapour_pressure < TRIPLE_PRESSURE:
        return float("nan")
    return saturation_temperature(vapour_pressure / 1000.0) - 273.15


def _wet_bulb(temperature: float, ratio: float, pressure: float) -> float:
    """The wet bulb temperature, found by closing in on it.

    Evaporating water into the air until it saturates is an adiabatic
    process, and the wet bulb is the temperature that leaves. There is no
    way to write it down directly, so it is bracketed between the dew point
    and the dry bulb - the answer is always between the two - and halved
    until it stops moving.
    """
    def ratio_at(wet: float) -> float:
        saturated = humidity_ratio(saturation_vapour_pressure(wet), pressure)
        # The adiabatic saturation relation, ASHRAE's form.
        top = ((2501.0 - 2.326 * wet) * saturated
               - 1.006 * (temperature - wet))
        return top / (2501.0 + 1.86 * temperature - 4.186 * wet)

    low, high = MIN_TEMPERATURE, temperature
    if ratio_at(high) <= ratio:
        return temperature                    # already saturated
    if ratio_at(low) > ratio:
        # The answer is below the bottom of the search, which is freezing.
        # Returning `low` would report saturated air, which this is not.
        return float("nan")
    for _ in range(80):
        middle = (low + high) / 2.0
        if ratio_at(middle) < ratio:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0



def _note(dew: float, wet: float) -> str:
    """What could not be worked out, and why. Empty when it all could."""
    missing = []
    if dew != dew:                                    # nan
        missing.append("dew point")
    if wet != wet:
        missing.append("wet bulb")
    if not missing:
        return ""
    return (f"The {' and '.join(missing)} would be below freezing, where the "
            "vapour deposits as frost rather than condensing. That is the "
            "sublimation curve, which this does not have - everything else "
            "here is unaffected.")

def state(temperature: float, pressure: float = STANDARD_PRESSURE, *,
          relative_humidity: float | None = None,
          ratio: float | None = None,
          wet_bulb: float | None = None,
          dew_point_at: float | None = None) -> MoistAir:
    """Moist air from a dry bulb temperature and one measure of its moisture.

    Exactly one of relative humidity, humidity ratio, wet bulb or dew point
    is needed: the dry bulb alone does not fix the state, and any two of the
    moisture measures would over-determine it.
    """
    _check(temperature, pressure)
    given = [x for x in (relative_humidity, ratio, wet_bulb, dew_point_at)
             if x is not None]
    if len(given) != 1:
        raise PsychrometricError(
            "Give the dry bulb and exactly one of: relative humidity, "
            "humidity ratio, wet bulb, or dew point. One fixes the state; "
            "two would have to agree, and a chart is easier to read than an "
            "argument about which one was right.")

    saturated_pressure = saturation_vapour_pressure(temperature)

    if relative_humidity is not None:
        if not 0.0 <= relative_humidity <= 1.0:
            raise PsychrometricError(
                "Relative humidity runs from 0 to 100%.")
        vapour = relative_humidity * saturated_pressure
        moisture = humidity_ratio(vapour, pressure)
    elif ratio is not None:
        moisture = ratio
        vapour = vapour_pressure_from_ratio(moisture, pressure)
    elif dew_point_at is not None:
        if dew_point_at > temperature + 1e-9:
            raise PsychrometricError(
                "The dew point cannot be above the dry bulb - the air would "
                "already have condensed.")
        _check(dew_point_at, pressure)
        vapour = saturation_vapour_pressure(dew_point_at)
        moisture = humidity_ratio(vapour, pressure)
    else:
        if wet_bulb > temperature + 1e-9:
            raise PsychrometricError(
                "The wet bulb cannot be above the dry bulb.")
        _check(wet_bulb, pressure)
        saturated_at_wet = humidity_ratio(
            saturation_vapour_pressure(wet_bulb), pressure)
        moisture = (((2501.0 - 2.326 * wet_bulb) * saturated_at_wet
                     - 1.006 * (temperature - wet_bulb))
                    / (2501.0 + 1.86 * temperature - 4.186 * wet_bulb))
        if moisture < 0:
            raise PsychrometricError(
                "That wet bulb is too far below the dry bulb for air at this "
                "pressure - it would need less than no moisture.")
        vapour = vapour_pressure_from_ratio(moisture, pressure)

    relative = vapour / saturated_pressure if saturated_pressure else 0.0
    below = dew_point(vapour) if vapour > 0 else float("nan")
    wet = (wet_bulb if wet_bulb is not None
           else _wet_bulb(temperature, moisture, pressure))
    return MoistAir(
        temperature=temperature,
        pressure=pressure,
        humidity_ratio=moisture,
        relative_humidity=min(relative, 1.0),
        vapour_pressure=vapour,
        enthalpy=enthalpy(temperature, moisture),
        specific_volume=specific_volume(temperature, moisture, pressure),
        dew_point=below,
        note=_note(below, wet),
        wet_bulb=wet)
