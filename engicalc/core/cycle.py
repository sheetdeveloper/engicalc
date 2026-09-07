"""The vapour compression cycle: the thing refrigerant tables exist for.

Four processes round a loop. The refrigerant boils in the evaporator taking
heat in, is compressed, condenses giving heat out, and is throttled back down
to where it started. Everything anybody wants to know about a fridge, a
chiller or a heat pump is a difference between two of those four states.

The point of doing it here rather than on paper is that reading four states
off a chart is where the errors come from, not the arithmetic afterwards.
Two of the four are not on the saturation line at all: the compressor exit is
found at a pressure and an entropy, and the throttle exit at a pressure and
an enthalpy, and both of those mean interpolating across a table twice.

Two checks come free and are worth having. The heat rejected has to equal the
heat taken in plus the work put in, because energy does not go anywhere else;
and the heating coefficient of performance has to be exactly one more than the
cooling one, for the same reason. Neither is imposed - both are worked out
independently and compared.

The fluid is a parameter rather than a fixture. Anything shaped like the
r134a module - saturation line, states at a pressure and a temperature, an
entropy or an enthalpy - can be run round this loop, so a second refrigerant
is a second set of properties and not a second cycle.

**Transcritical.** One refrigerant does not fit that description, and it is
the one everybody is moving to. Carbon dioxide's critical temperature is
31 C, so a machine rejecting heat to outside air on a warm day is above it
and nothing condenses: the high side is a supercritical gas being cooled,
and the component is called a gas cooler rather than a condenser.

The difference that matters is not the name. Below the critical point the
condensing temperature *fixes* the pressure - they are the same fact, which
is why a subcritical cycle has one high-side variable. Above it they come
apart, and the high side has two: the pressure, which is chosen, and the
temperature the gas leaves at, which the ambient sets. And because the
pressure is now free, there is a best one - the coefficient of performance
rises with it at first, because more heat gets rejected, and then falls,
because the compressor is working harder for it. Finding that maximum is
what ``best_pressure`` does, and it has no equivalent in a subcritical
cycle, where the pressure was never anybody's to choose.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .parsing import ParseError


class CycleError(ParseError):
    """Raised when a cycle cannot be worked out."""


#: A discharge temperature above this is worth mentioning. Not a limit - the
#: number is still right - but compressor oil breaks down somewhere around
#: here and a cycle that runs this hot is usually a sign the pressure ratio
#: has been pushed further than one stage should go.
HOT_DISCHARGE = 273.15 + 120.0


@dataclass
class Cycle:
    """A single-stage vapour compression cycle.

    Temperatures in kelvin, *superheat* and *subcool* in kelvin of it, and
    *efficiency* the compressor's isentropic efficiency as a fraction.
    *duty* is what the machine is being asked for, in watts - the cooling
    taken in, or the heat given out if *heating* is set. It is the only
    thing here that sets a size; without it every answer is per kilogram.
    """

    fluid: object
    evaporating: float
    condensing: float = 0.0
    #: The transcritical pair. Set these instead of *condensing* when the
    #: high side is above the critical point: the pressure the gas cooler
    #: runs at, and the temperature the refrigerant leaves it at. Above
    #: the critical point those are two separate facts rather than one.
    gas_cooler_pressure: float = 0.0
    gas_cooler_out: float = 0.0
    superheat: float = 0.0
    subcool: float = 0.0
    efficiency: float = 1.0
    duty: float = 0.0
    #: Whether *duty* is the heat wanted out rather than the cooling wanted
    #: in. The same machine is sized on different ends of itself depending
    #: on which one you bought it for.
    heating: bool = False

    @property
    def transcritical(self) -> bool:
        """Whether the high side is above the critical point."""
        return self.gas_cooler_pressure > 0.0

    @property
    def sink(self) -> float:
        """The warm end, for a Carnot comparison.

        Subcritically that is the condensing temperature and there is
        nothing to argue about - the whole rejection happens there. Above
        the critical point the gas cooler glides from the discharge
        temperature down to its outlet, so there is no single temperature
        the heat is rejected at. The outlet is used, because that is the
        end the ambient sets, and the notes say so rather than leaving a
        Carnot number to be read as though it meant the same thing.
        """
        return self.gas_cooler_out if self.transcritical else self.condensing

    def check(self) -> None:
        if self.transcritical:
            self._check_transcritical()
            return
        critical = getattr(self.fluid, "T_critical", None)
        if critical is not None and self.condensing >= critical:
            raise CycleError(
                f"{getattr(self.fluid, 'name', 'This refrigerant')} has a "
                f"critical temperature of {critical - 273.15:.1f} C, and "
                f"nothing condenses above it - so a condensing temperature "
                f"of {self.condensing - 273.15:.1f} C does not describe "
                f"anything that happens. Give a gas cooler pressure and an "
                f"outlet temperature instead: the cycle is transcritical.")
        if self.condensing <= self.evaporating:
            raise CycleError(
                "The condenser has to be hotter than the evaporator, or the "
                "heat would be going the way it goes by itself and no "
                "machine would be needed.")
        if not 0.0 < self.efficiency <= 1.0:
            raise CycleError(
                "The isentropic efficiency runs from just above 0 to 1. A "
                "compressor cannot do better than the reversible one.")
        if self.superheat < 0 or self.subcool < 0:
            raise CycleError(
                "Superheat and subcooling are amounts, so neither is "
                "negative. Wet gas into a compressor is a different problem.")

    def _check_transcritical(self) -> None:
        low = self.fluid.saturation_pressure(self.evaporating)
        if self.gas_cooler_pressure <= low:
            raise CycleError(
                "The gas cooler has to be at a higher pressure than the "
                "evaporator, or there is nothing for the compressor to do.")
        if self.gas_cooler_out <= self.evaporating:
            raise CycleError(
                "The gas leaves the cooler warmer than the evaporator "
                "boils, or the heat would be going the way it goes by "
                "itself and no machine would be needed.")
        top = getattr(self.fluid, "p_max", None)
        if top is not None and self.gas_cooler_pressure > top:
            raise CycleError(
                f"{self.gas_cooler_pressure / 1e5:.0f} bar is past where "
                f"this equation of state was fitted "
                f"({top / 1e5:.0f} bar).")
        if not 0.0 < self.efficiency <= 1.0:
            raise CycleError(
                "The isentropic efficiency runs from just above 0 to 1. A "
                "compressor cannot do better than the reversible one.")
        if self.superheat < 0:
            raise CycleError(
                "Superheat is an amount, so it is not negative. Wet gas "
                "into a compressor is a different problem.")

    def pressures(self) -> tuple:
        """(evaporating, high). The low one is fixed by its temperature.

        So is the high one, subcritically - a condensing temperature and a
        condensing pressure are the same fact. Above the critical point
        they are not, and the pressure is given rather than derived.
        """
        low = self.fluid.saturation_pressure(self.evaporating)
        if self.transcritical:
            return (low, self.gas_cooler_pressure)
        return (low, self.fluid.saturation_pressure(self.condensing))

    def states(self) -> tuple:
        """The four corners, in the order the refrigerant goes round them.

        1 leaving the evaporator, 2 leaving the compressor, 3 leaving the
        condenser, 4 leaving the throttle.
        """
        self.check()
        low, high = self.pressures()

        # 1. Out of the evaporator. Dry saturated unless it is superheated,
        #    which it nearly always is - a compressor is not meant to be fed
        #    liquid and the superheat is what guarantees it is not.
        if self.superheat > 0:
            first = self.fluid.at_pressure_and_temperature(
                low, self.evaporating + self.superheat)
        else:
            _liquid, first = self.fluid.saturated(self.evaporating)

        # 2. Out of the compressor. Reversibly it would leave at the same
        #    entropy; the efficiency says how much of that ideal rise in
        #    enthalpy actually gets there, and the rest turns up as heat.
        ideal = self.fluid.at_pressure_and_entropy(high, first.s)
        second = self.fluid.at_pressure_and_enthalpy(
            high, first.h + (ideal.h - first.h) / self.efficiency)

        # 3. Out of the gas cooler, or out of the condenser.
        if self.transcritical:
            # Nothing condensed, so there is no saturation temperature to
            # measure subcooling from. What leaves is a gas at the
            # cooler's pressure and whatever the ambient cooled it to.
            third = self.fluid.at_pressure_and_temperature(
                high, self.gas_cooler_out)
        elif self.subcool > 0:
            third = self.fluid.at_pressure_and_temperature(
                high, self.condensing - self.subcool)
        else:
            third, _vapour = self.fluid.saturated(self.condensing)

        # 4. Out of the throttle. A throttle does no work and passes no heat,
        #    so the enthalpy it comes out at is the one it went in at. That
        #    is the whole of what a throttle is, and it is why some of the
        #    liquid flashes to gas on the way through.
        fourth = self.fluid.at_pressure_and_enthalpy(low, third.h)
        return first, second, third, fourth

    # -- what comes out of it ----------------------------------------------
    def performance(self) -> dict:
        first, second, third, fourth = self.states()
        taken_in = first.h - fourth.h            # the refrigerating effect
        work = second.h - first.h
        given_out = second.h - third.h
        if work <= 0:
            raise CycleError(
                "The compressor comes out with no more energy than it went "
                "in with, which is not a cycle. Check the two temperatures.")

        carnot = self.evaporating / (self.sink - self.evaporating)
        found = {
            "refrigerating effect": taken_in,
            "compressor work": work,
            "heat rejected": given_out,
            "cooling COP": taken_in / work,
            "heating COP": given_out / work,
            "Carnot COP": carnot,
            "fraction of Carnot": (taken_in / work) / carnot,
            "pressure ratio": second.p / first.p,
            "discharge temperature": second.T,
            "dryness after the throttle": fourth.quality,
        }
        if self.duty > 0:
            flow = self.duty / (given_out if self.heating else taken_in)
            found["mass flow"] = flow
            found["volume flow into the compressor"] = flow * first.v
            found["compressor power"] = flow * work
            found["condenser duty"] = flow * given_out
        return found

    def rows(self) -> list:
        """(label, value, unit) for the table under the diagram."""
        found = self.performance()
        rows = [
            ("refrigerating effect", found["refrigerating effect"] / 1000.0,
             "kJ/kg"),
            ("compressor work", found["compressor work"] / 1000.0, "kJ/kg"),
            ("heat rejected", found["heat rejected"] / 1000.0, "kJ/kg"),
            ("COP, cooling", found["cooling COP"], ""),
            ("COP, heating", found["heating COP"], ""),
            ("Carnot COP between the same two", found["Carnot COP"], ""),
            ("fraction of Carnot", found["fraction of Carnot"], ""),
            ("pressure ratio", found["pressure ratio"], ""),
            ("discharge temperature",
             found["discharge temperature"] - 273.15, "deg C"),
            ("dryness after the throttle",
             found["dryness after the throttle"], ""),
        ]
        if self.duty > 0:
            rows += [
                ("mass flow", found["mass flow"] * 1000.0, "g/s"),
                ("volume flow into the compressor",
                 found["volume flow into the compressor"] * 1000.0, "L/s"),
                ("compressor power", found["compressor power"] / 1000.0,
                 "kW"),
                ("condenser duty", found["condenser duty"] / 1000.0, "kW"),
            ]
        return rows

    def notes(self) -> list:
        """The checks, and anything worth saying about the answer."""
        found = self.performance()
        said = []

        # Energy in equals energy out. Worked out from the states rather
        # than imposed, so it is a check and not a restatement.
        closes = (found["refrigerating effect"] + found["compressor work"]
                  - found["heat rejected"])
        scale = max(abs(found["heat rejected"]), 1.0)
        if abs(closes) > 1e-9 * scale:
            said.append(
                f"The heat rejected does not equal the heat taken in plus "
                f"the work put in - it is out by {closes:.4g} J/kg. "
                f"Something in the four states is wrong.")
        if abs(found["heating COP"] - found["cooling COP"] - 1.0) > 1e-9:
            said.append(
                "The heating and cooling coefficients of performance differ "
                "by something other than exactly one, which they cannot.")

        if found["discharge temperature"] > HOT_DISCHARGE:
            said.append(
                f"It leaves the compressor at "
                f"{found['discharge temperature'] - 273.15:.0f} C. Oil "
                f"starts to break down around this temperature, so a real "
                f"machine working over this range would usually be "
                f"compounded rather than single stage.")
        if found["pressure ratio"] > 10:
            said.append(
                f"A pressure ratio of {found['pressure ratio']:.1f} is more "
                f"than one stage of compression normally does.")
        if self.superheat == 0:
            said.append(
                "With no superheat the compressor is fed saturated vapour, "
                "which is the textbook cycle and not what anybody builds - "
                "a few kelvin of superheat is what keeps liquid out of it.")
        said += self._transcritical_notes(found)
        return said

    def _transcritical_notes(self, found: dict) -> list:
        """What is different about a cycle with no condenser in it."""
        if not self.transcritical:
            return []
        name = getattr(self.fluid, "name", "the refrigerant")
        said = [
            f"This is a transcritical cycle: at "
            f"{self.gas_cooler_pressure / 1e5:.0f} bar the high side is "
            f"above {name}'s critical pressure, so nothing condenses. The "
            f"heat comes out of a gas being cooled, over a glide from "
            f"{found['discharge temperature'] - 273.15:.0f} C down to "
            f"{self.gas_cooler_out - 273.15:.0f} C, rather than at one "
            f"temperature.",
            "The Carnot figure above is taken between the evaporating "
            "temperature and the gas cooler outlet. There is no single "
            "temperature the heat is rejected at, so it is a comparison "
            "rather than the bound it is subcritically.",
        ]
        try:
            best = self.best_pressure()
        except CycleError:
            return said
        off = abs(best - self.gas_cooler_pressure) / self.gas_cooler_pressure
        if off > 0.01:
            try:
                there = self.at_pressure(best).performance()["cooling COP"]
            except CycleError:
                return said
            said.append(
                f"The best gas cooler pressure for this outlet temperature "
                f"is about {best / 1e5:.0f} bar, where the cooling "
                f"coefficient of performance is {there:.3f} against "
                f"{found['cooling COP']:.3f} here. Unlike a condensing "
                f"pressure this one is a choice, and it has a maximum: "
                f"raising it rejects more heat and costs more work, and "
                f"the two win in turn.")
        else:
            said.append(
                f"{self.gas_cooler_pressure / 1e5:.0f} bar is within a per "
                f"cent of the best pressure for this outlet temperature.")
        return said

    # -- the pressure that is a choice -------------------------------------
    def at_pressure(self, pressure: float) -> "Cycle":
        """The same cycle with the gas cooler at a different pressure."""
        return replace(self, gas_cooler_pressure=pressure)

    def best_pressure(self, low: float = 0.0, high: float = 0.0) -> float:
        """The gas cooler pressure that gets the most cooling per unit work.

        A golden-section search, because the coefficient of performance
        rises and then falls and the maximum is broad. A Newton step on a
        derivative taken by difference across a flat top finds noise; this
        only ever needs the value.
        """
        if not self.transcritical:
            raise CycleError(
                "A condensing pressure is not a choice - it is whatever "
                "the condensing temperature makes it. There is nothing to "
                "optimise until the cycle is transcritical.")
        critical = getattr(self.fluid, "p_critical", 0.0)
        ceiling = getattr(self.fluid, "p_max", 3.0e7)
        low = low or critical * 1.02
        high = high or min(ceiling, critical * 2.2)

        def cop(pressure: float) -> float:
            try:
                return self.at_pressure(pressure).performance()["cooling COP"]
            except Exception:                              # noqa: BLE001
                return -1.0

        golden = (math.sqrt(5.0) - 1.0) / 2.0
        left, right = low, high
        one, other = (right - golden * (right - left),
                      left + golden * (right - left))
        first, second = cop(one), cop(other)
        for _ in range(80):
            if right - left < 1000.0:          # a pascal in a hundred bar
                break
            if first > second:
                right, other, second = other, one, first
                one = right - golden * (right - left)
                first = cop(one)
            else:
                left, one, first = one, other, second
                other = left + golden * (right - left)
                second = cop(other)
        best = (left + right) / 2.0
        if cop(best) <= 0.0:
            raise CycleError(
                "No gas cooler pressure in the usable range gives a cycle "
                "at all. Check the evaporating and outlet temperatures.")
        return best
