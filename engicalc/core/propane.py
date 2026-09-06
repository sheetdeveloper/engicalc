"""Propane (R290) from its reference equation of state.

Lemmon, McLinden and Wagner, *Thermodynamic Properties of Propane. III. A
Reference Equation of State for Temperatures from the Melting Line to 650 K
and Pressures up to 1000 MPa*, J. Chem. Eng. Data 54 (2009) 3141.

Propane is here because it is R290: a refrigerant with no ozone effect and
a global warming potential of about three, against R134a's fourteen
hundred. It is flammable, which is why it is not simply better, and why the
charge in a system using it is limited.

The solving is all in ``helmholtz``. What is here is the table of numbers.
This formulation needs the Gaussian bell terms as well as the plain and
exponential ones - the newer equations use them to shape the critical
region, where the older exponential-only form struggles.

The reference state is the refrigerating one, so that enthalpy and entropy
read the way a refrigeration table reads: saturated liquid at 0 C has
h = 200 kJ/kg and s = 1 kJ/(kg K), the same convention as R134a. Any other
choice is equally valid and shifts every enthalpy by a constant; comparing
this app's numbers with a table measured from somewhere else means
comparing differences, not values.
"""

from __future__ import annotations

from .helmholtz import Fluid, FluidError, State  # noqa: F401

MOLAR_MASS = 0.04409562        # kg/mol
MOLAR_GAS = 8.314472           # J/(mol K)

#: This formulation reduces about the critical point itself.
T_REDUCING = 369.89                        # K
RHO_REDUCING = 5000.0 * MOLAR_MASS         # kg/m^3

T_CRITICAL = 369.89            # K
P_CRITICAL = 4251.2e3          # Pa
RHO_CRITICAL = RHO_REDUCING    # kg/m^3

#: The triple point. The pressure there is under a fifth of a millipascal,
#: which is a hard vacuum - propane at 85 K is a solid sitting under
#: essentially nothing.
T_TRIPLE = 85.525              # K
P_TRIPLE = 1.7184840809308612e-4   # Pa

R = MOLAR_GAS / MOLAR_MASS     # J/(kg K)

#: The equation is valid from the melting line to 650 K and to 1000 MPa.
#: The bottom is held at 140 K rather than the triple point: below that the
#: saturation pressure is under a pascal, the vapour density under a
#: millionth of a kilogram per cubic metre, and the two-phase search is
#: working in numbers where the answer is all rounding. Nothing that uses
#: propane goes near it.
T_MIN, T_MAX = 140.0, 650.0
P_MAX = 100e6
#: Saturated liquid at 140 K is about 690 kg/m^3, and compressed liquid at
#: a hundred megapascals goes further.
RHO_MAX = 1000.0

#: The residual part.
#:
#:   (n, d, t, c)                    n delta^d tau^t, times exp(-delta^c)
#:                                   when c is not zero
#:   (n, d, t, 0, eta, eps, bet, gam) times the Gaussian bell
RESIDUAL = (
    (0.042910051, 4, 1.0, 0),
    (1.7313671, 1, 0.33, 0),
    (-2.4516524, 1, 0.8, 0),
    (0.34157466, 2, 0.43, 0),
    (-0.46047898, 2, 0.9, 0),
    (-0.66847295, 1, 2.46, 1),
    (0.20889705, 3, 2.09, 1),
    (0.19421381, 6, 0.88, 1),
    (-0.22917851, 6, 1.09, 1),
    (-0.60405866, 2, 3.25, 2),
    (0.066680654, 3, 4.62, 2),
    (0.017534618, 1, 0.76, 0, 0.963, 1.283, 2.33, 0.684),
    (0.33874242, 1, 2.5, 0, 1.977, 0.6936, 3.47, 0.829),
    (0.22228777, 1, 2.75, 0, 1.917, 0.788, 3.15, 1.419),
    (-0.23219062, 2, 3.05, 0, 2.307, 0.473, 3.19, 0.817),
    (-0.09220694, 2, 2.55, 0, 2.546, 0.8577, 0.92, 1.5),
    (-0.47575718, 4, 8.4, 0, 3.28, 0.271, 18.8, 1.426),
    (-0.017486824, 1, 6.75, 0, 14.6, 0.948, 547.8, 1.093),
)

#: phi0 = ln(delta) + a1 + a2 tau + 3 ln(tau)
#:                  + sum n ln(1 - exp(-theta tau))
#: The four Planck-Einstein terms are the vibrational modes of the
#: molecule, and they are what makes the ideal-gas heat capacity of propane
#: climb from about 1.3 kJ/kg K at room temperature to over 2 by 500 K.
#: a1 and a2 are solved from the reference state rather than written down.
IDEAL_LOG_TAU = 3.0
EINSTEIN = (
    (3.043, 1.062478),
    (5.874, 3.344237),
    (9.337, 5.363757),
    (7.922, 11.762957),
)

REFERENCE_T = 273.15
REFERENCE_H = 200e3            # J/kg
REFERENCE_S = 1000.0           # J/(kg K)


PropaneError = FluidError


FLUID = Fluid(
    name="Propane",
    molar_mass=MOLAR_MASS,
    molar_gas=MOLAR_GAS,
    T_reducing=T_REDUCING,
    rho_reducing=RHO_REDUCING,
    T_critical=T_CRITICAL,
    p_critical=P_CRITICAL,
    rho_critical=RHO_CRITICAL,
    T_triple=T_TRIPLE,
    p_triple=P_TRIPLE,
    T_min=T_MIN,
    T_max=T_MAX,
    p_max=P_MAX,
    rho_max=RHO_MAX,
    residual=RESIDUAL,
    ideal_log_tau=IDEAL_LOG_TAU,
    ideal_einstein=EINSTEIN,
    reference_T=REFERENCE_T,
    reference_h=REFERENCE_H,
    reference_s=REFERENCE_S,
    source="Lemmon, McLinden & Wagner, J. Chem. Eng. Data 54 (2009) 3141",
)


def saturation_pressure(T: float) -> float:
    return FLUID.saturation_pressure(T)


def saturation_temperature(p: float) -> float:
    return FLUID.saturation_temperature(p)


def saturated(T: float) -> tuple:
    return FLUID.saturated(T)


def wet(T: float, quality: float) -> State:
    return FLUID.wet(T, quality)


def latent_heat(T: float) -> float:
    return FLUID.latent_heat(T)


def state_at(T: float, rho: float, quality: float | None = None) -> State:
    return FLUID.state_at(T, rho, quality)


def at_pressure_and_temperature(p: float, T: float) -> State:
    return FLUID.at_pressure_and_temperature(p, T)


def at_pressure_and_entropy(p: float, s: float) -> State:
    return FLUID.at_pressure_and_entropy(p, s)


def at_pressure_and_enthalpy(p: float, h: float) -> State:
    return FLUID.at_pressure_and_enthalpy(p, h)
