"""R134a (1,1,1,2-tetrafluoroethane) from its reference equation of state.

Tillner-Roth and Baehr, *An International Standard Formulation for the
Thermodynamic Properties of 1,1,1,2-Tetrafluoroethane (HFC-134a) for
Temperatures from 170 K to 455 K and Pressures up to 70 MPa*, J. Phys.
Chem. Ref. Data 23 (1994) 657. This is the formulation the published
tables are generated from.

The solving is in ``helmholtz``; what is here is the table of numbers and
the constants that go with it, and a set of module-level functions so that
``r134a.saturation_pressure(T)`` keeps working the way it always has.

Two of these constants are worth reading twice.

**The reducing density is 4978.830171 mol/m^3**, written that way on
purpose. Taken from a secondary source as 507.6 kg/m^3 it is a twelfth of
a percent out, and a twelfth of a percent in the reducing density is a
twelfth of a percent in every saturation pressure the equation produces -
flat across ninety kelvin, which is what made it look like a constant
rather than a mistake. It reduces about slightly different values from the
critical point, and substituting the critical ones moves every answer.

**The liquid gets to 1590 kg/m^3** at the triple point, over three times
the critical density. A density search that stops at twice the critical
density finds no liquid at all, and looks like a broken equation rather
than a short bracket.
"""

from __future__ import annotations

from .helmholtz import Fluid, FluidError, State  # noqa: F401

MOLAR_MASS = 0.102032          # kg/mol
MOLAR_GAS = 8.314471           # J/(mol K)

#: Where the equation is reduced about - see the note above.
T_REDUCING = 374.18                        # K
RHO_REDUCING = 4978.830171 * MOLAR_MASS    # kg/m^3

#: The critical point itself.
T_CRITICAL = 374.21            # K
P_CRITICAL = 4059.28e3         # Pa
RHO_CRITICAL = 511.9           # kg/m^3

#: The triple point, which is the bottom of the range.
T_TRIPLE = 169.85              # K
P_TRIPLE = 389.6               # Pa

#: The specific gas constant, which is what everything here is written in.
R = MOLAR_GAS / MOLAR_MASS     # J/(kg K)

T_MIN, T_MAX = 169.85, 455.0
P_MAX = 70e6
RHO_MAX = 1700.0

CRITICAL_MARGIN = 0.05
CLEAR_OF_THE_LINE = 1e-3

#: The residual part: (n, d, t, c). Terms with c = 0 are plain powers; the
#: rest carry a factor exp(-delta^c).
RESIDUAL = (
    (0.5586817e-1, 2, -0.5, 0),
    (0.4982230e0, 1, 0.0, 0),
    (0.2458698e-1, 3, 0.0, 0),
    (0.8570145e-3, 6, 0.0, 0),
    (0.4788584e-3, 6, 1.5, 0),
    (-0.1800808e1, 1, 1.5, 0),
    (0.2671641e0, 1, 2.0, 0),
    (-0.4781652e-1, 2, 2.0, 0),
    (0.1423987e-1, 5, 1.0, 1),
    (0.3324062e0, 2, 3.0, 1),
    (-0.7485907e-2, 2, 5.0, 1),
    (0.1017263e-3, 4, 1.0, 2),
    (-0.5184567e0, 1, 5.0, 2),
    (-0.8692288e-1, 4, 5.0, 2),
    (0.2057144e0, 1, 6.0, 2),
    (-0.5000457e-2, 2, 10.0, 2),
    (0.4603262e-3, 4, 10.0, 2),
    (-0.3497836e-2, 1, 10.0, 3),
    (0.6995038e-2, 5, 18.0, 3),
    (-0.1452184e-1, 3, 22.0, 3),
    (-0.1285458e-3, 10, 50.0, 4),
)

#: The ideal-gas part, less its two arbitrary constants:
#: phi0 = ln(delta) + a1 + a2 tau + a3 ln(tau) + a4 tau^-0.5 + a5 tau^-0.75
#: a3, a4 and a5 shape the ideal-gas heat capacity and are part of the
#: formulation. a1 and a2 shift entropy and enthalpy by a constant and are
#: solved from the reference state.
A3 = -1.629789
A4 = -9.723916
A5 = -3.927170

#: Saturated liquid at 0 C, which is where refrigerant tables start.
REFERENCE_T = 273.15
REFERENCE_H = 200e3            # J/kg
REFERENCE_S = 1000.0           # J/(kg K)


#: One error type covers every fluid, since the caller does the same thing
#: with all of them. The old name still works, because it is the same class
#: and not a subclass - a subclass would not catch what the solver raises.
R134aError = FluidError


FLUID = Fluid(
    name="R134a",
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
    ideal_log_tau=A3,
    ideal_powers=((A4, -0.5), (A5, -0.75)),
    reference_T=REFERENCE_T,
    reference_h=REFERENCE_H,
    reference_s=REFERENCE_S,
    critical_margin=CRITICAL_MARGIN,
    clear_of_the_line=CLEAR_OF_THE_LINE,
    source="Tillner-Roth & Baehr, J. Phys. Chem. Ref. Data 23 (1994) 657",
)


# --------------------------------------------------------------------------
# The module reads the way it always did, whatever is underneath it
# --------------------------------------------------------------------------
def _pressure(T: float, rho: float) -> float:
    return FLUID.pressure(T, rho)


def _residual(delta: float, tau: float) -> tuple:
    """(phi, phi_d, phi_dd, phi_t, phi_tt, phi_dt) for the residual part."""
    return FLUID._residual(delta, tau)


def state_at(T: float, rho: float, quality: float | None = None) -> State:
    """Everything about the refrigerant at a temperature and a density."""
    return FLUID.state_at(T, rho, quality)


def saturation_pressure(T: float) -> float:
    """The pressure the two phases sit at together, in pascals."""
    return FLUID.saturation_pressure(T)


def saturation_temperature(p: float) -> float:
    """The temperature at which it boils at *p*."""
    return FLUID.saturation_temperature(p)


def saturated(T: float) -> tuple:
    """(liquid, vapour) states at *T*."""
    return FLUID.saturated(T)


def wet(T: float, quality: float) -> State:
    """A mixture of the two phases, *quality* of it vapour by mass."""
    return FLUID.wet(T, quality)


def latent_heat(T: float) -> float:
    """How much heat one kilogram takes to boil at *T*."""
    return FLUID.latent_heat(T)


def at_pressure_and_temperature(p: float, T: float) -> State:
    """A single-phase state, given the two things a gauge tells you."""
    return FLUID.at_pressure_and_temperature(p, T)


def at_pressure_and_entropy(p: float, s: float) -> State:
    """Where a reversible compression from *p* at entropy *s* comes out."""
    return FLUID.at_pressure_and_entropy(p, s)


def at_pressure_and_enthalpy(p: float, h: float) -> State:
    """Where a throttle to *p* comes out, since a throttle keeps enthalpy."""
    return FLUID.at_pressure_and_enthalpy(p, h)
