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
"""

from __future__ import annotations

from dataclasses import dataclass

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
    condensing: float
    superheat: float = 0.0
    subcool: float = 0.0
    efficiency: float = 1.0
    duty: float = 0.0
    #: Whether *duty* is the heat wanted out rather than the cooling wanted
    #: in. The same machine is sized on different ends of itself depending
    #: on which one you bought it for.
    heating: bool = False

    def check(self) -> None:
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

    def pressures(self) -> tuple:
        """(evaporating, condensing), which the temperatures fix."""
        return (self.fluid.saturation_pressure(self.evaporating),
                self.fluid.saturation_pressure(self.condensing))

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

        # 3. Out of the condenser: saturated liquid, or colder than that.
        if self.subcool > 0:
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

        carnot = self.evaporating / (self.condensing - self.evaporating)
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
        return said
