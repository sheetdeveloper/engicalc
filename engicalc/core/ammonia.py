"""Ammonia (R717) from its reference equation of state.

Gao, Wu, Bell, Lemmon, Weber and Harvey, *A Reference Equation of State
with an Associating Term for the Thermodynamic Properties of Ammonia*, J.
Phys. Chem. Ref. Data 52 (2023) 013102, doi:10.1063/5.0128269. This
replaced the Tillner-Roth, Harms-Watzenberg and Baehr equation of 1993 that
stood as the reference for a quarter of a century.

Ammonia is the oldest refrigerant still in wide industrial use, and the one
that keeps coming back: no ozone effect, a global warming potential of
zero, and a latent heat several times that of any halocarbon, which is why
a cold store the size of a warehouse runs on it. It is toxic and it attacks
copper, which is why a domestic fridge does not.

Its molecules hydrogen bond, and that is why this formulation needed a term
shape the others do not - an associating term, whose temperature part is a
reciprocal rather than a Gaussian. See ``helmholtz`` for the three shapes.

The reference state is the refrigerating one - saturated liquid at 0 C with
h = 200 kJ/kg and s = 1 kJ/(kg K) - the same as R134a and propane here, so
the three can be compared. Ammonia tables in the wild are more often
measured from -40 C, which shifts every enthalpy by a constant and leaves
every difference alone.
"""

from __future__ import annotations

from .helmholtz import Fluid, FluidError, State  # noqa: F401

MOLAR_MASS = 0.01703052        # kg/mol
MOLAR_GAS = 8.3144598          # J/(mol K)

#: This formulation reduces about the critical point itself.
T_REDUCING = 405.56                        # K
RHO_REDUCING = 13696.0 * MOLAR_MASS        # kg/m^3

T_CRITICAL = 405.56            # K
P_CRITICAL = 11363391.162815327    # Pa
RHO_CRITICAL = RHO_REDUCING    # kg/m^3

T_TRIPLE = 195.49              # K
P_TRIPLE = 6055.81357453296    # Pa

R = MOLAR_GAS / MOLAR_MASS     # J/(kg K)

#: The equation is valid from the triple point to 725 K. The pressure is
#: held to 100 MPa here rather than the thousand the paper covers, because
#: nothing this app is for goes near a thousand and the density search
#: would have to reach much further to hold it.
T_MIN, T_MAX = 195.49, 725.0
P_MAX = 100e6
#: Saturated liquid at the triple point is about 734 kg/m^3.
RHO_MAX = 1000.0

#: The residual part. Tuples of four are plain or exponential terms, of
#: eight the Gaussian bell, and of nine the associating term - see
#: ``helmholtz`` for the three shapes and their signs.
RESIDUAL = (
    (0.006132232, 4, 1.0, 0),
    (1.7395866, 1, 0.382, 0),
    (-2.2261792, 1, 1.0, 0),
    (-0.30127553, 2, 1.0, 0),
    (0.08967023, 3, 0.677, 0),
    (-0.076387037, 3, 2.915, 2),
    (-0.84063963, 2, 3.51, 2),
    (-0.27026327, 3, 1.063, 1),
    (6.212578, 1, 0.655, 0, 0.42776, -0.0726, 1.708, 1.036),
    (-5.7844357, 1, 1.3, 0, 0.6424, -0.1274, 1.4865, 1.2777),
    (2.4817542, 1, 3.1, 0, 0.8175, 0.7527, 2.0915, 1.083),
    (-2.3739168, 2, 1.4395, 0, 0.7995, 0.57, 2.43, 1.2906),
    (0.01493697, 2, 1.623, 0, 0.91, 2.2, 0.488, 0.928),
    (-3.7749264, 1, 0.643, 0, 0.3574, -0.243, 1.1, 0.934),
    (0.0006254348, 3, 1.13, 0, 1.21, 2.96, 0.85, 0.919),
    (-1.7359e-05, 3, 4.5, 0, 4.14, 3.02, 1.14, 1.852),
    (-0.13462033, 1, 1.0, 0, 22.56, 0.9574, 945.64, 1.05897),
    (0.07749072839, 1, 4.0, 0, 22.68, 0.9576, 993.85, 1.05277),
    (-1.6909858, 1, 4.3315, 0, -2.8452, 0.4478, 0.3696, 1.108, 1.244),
    (0.93739074, 1, 4.015, 0, -2.8342, 0.44689, 0.2962, 1.313, 0.6826),
)

#: phi0 = ln(delta) + a1 + a2 tau + 3 ln(tau)
#:                  + sum n ln(1 - exp(-theta tau))
IDEAL_LOG_TAU = 3.0
EINSTEIN = (
    (2.224, 4.0585856593352405),
    (3.148, 9.776605187888352),
    (0.9579, 17.829667620080876),
)

REFERENCE_T = 273.15
REFERENCE_H = 200e3            # J/kg
REFERENCE_S = 1000.0           # J/(kg K)


AmmoniaError = FluidError


FLUID = Fluid(
    name="Ammonia",
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
    source="Gao et al., J. Phys. Chem. Ref. Data 52 (2023) 013102",
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
