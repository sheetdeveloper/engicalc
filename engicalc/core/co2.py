"""Carbon dioxide (R744) from its reference equation of state.

Span and Wagner, *A New Equation of State for Carbon Dioxide Covering the
Fluid Region from the Triple-Point Temperature to 1100 K at Pressures up to
800 MPa*, J. Phys. Chem. Ref. Data 25 (1996) 1509.

CO2 is here because it is R744, and because it is the refrigerant that
behaves least like the others. Its critical temperature is 31 C - below a
warm afternoon - so a system rejecting heat to ambient air is often above
it, and there is no condensation to speak of: the high side is a
supercritical gas being cooled rather than a vapour being condensed. That
is what "transcritical" means, and it is why a CO2 cycle is drawn and sized
differently from an R134a one.

Its triple point is at 5.18 bar, so there is no liquid CO2 at atmospheric
pressure at all - it goes from solid straight to gas, which is what dry ice
does. The saturation line here therefore starts at 5.18 bar rather than at
a near-vacuum the way propane's does.

The solving is all in ``helmholtz``. What is here is the table of numbers,
and this formulation is the one that needed a fourth kind of term: three
**non-analytic** terms that reproduce the way the heat capacity diverges at
the critical point, which no sum of smooth terms can. See
``helmholtz.NonAnalytic``.

The coefficients are generated from the published table rather than typed.
Forty-two residual terms is four hundred numbers, and the way a table like
that goes wrong is one digit in one of them.

The reference state is the refrigerating one - saturated liquid at 0 C has
h = 200 kJ/kg and s = 1 kJ/(kg K) - the same convention as R134a, ammonia
and propane, so the four can be compared on one chart.
"""

from __future__ import annotations

from .helmholtz import Fluid, FluidError, NonAnalytic, State  # noqa: F401

MOLAR_MASS = 0.0440098        # kg/mol
MOLAR_GAS = 8.31451           # J/(mol K), as the formulation used it

#: This formulation reduces about the critical point itself.
T_REDUCING = 304.1282                        # K
RHO_REDUCING = 10624.9063 * MOLAR_MASS       # kg/m^3

T_CRITICAL = T_REDUCING        # K
P_CRITICAL = 7377300.0          # Pa
RHO_CRITICAL = RHO_REDUCING    # kg/m^3

#: The triple point, and the reason dry ice sublimes: at 5.18 bar, CO2 at
#: atmospheric pressure has no liquid phase to melt into.
T_TRIPLE = 216.592            # K
P_TRIPLE = 517964.34344772575        # Pa

R = MOLAR_GAS / MOLAR_MASS     # J/(kg K)

#: The equation is valid from the triple point to 1100 K and to 800 MPa.
T_MIN, T_MAX = T_TRIPLE, 1100.0
P_MAX = 800e6
#: Saturated liquid at the triple point is about 1178 kg/m^3, and
#: compressed liquid goes well past it.
RHO_MAX = 1600.0

#: The residual part: 34 plain and exponential terms, 5 Gaussian
#: bells, and 3 non-analytic ones.
#:
#:   (n, d, t, c)                     n delta^d tau^t, times exp(-delta^c)
#:                                    when c is not zero
#:   (n, d, t, 0, eta, eps, bet, gam) times the Gaussian bell
#:   NonAnalytic(...)                 the critical-region terms
RESIDUAL = (
    (0.388568232032, 1, 0, 0),
    (2.93854759427, 1, 0.75, 0),
    (-5.5867188535, 1, 1, 0),
    (-0.767531995925, 1, 2, 0),
    (0.317290055804, 2, 0.75, 0),
    (0.548033158978, 2, 2, 0),
    (0.122794112203, 3, 0.75, 0),
    (2.16589615432, 1, 1.5, 1),
    (1.58417351097, 2, 1.5, 1),
    (-0.231327054055, 4, 2.5, 1),
    (0.0581169164314, 5, 0, 1),
    (-0.553691372054, 5, 1.5, 1),
    (0.489466159094, 5, 2, 1),
    (-0.0242757398435, 6, 0, 1),
    (0.0624947905017, 6, 1, 1),
    (-0.121758602252, 6, 2, 1),
    (-0.370556852701, 1, 3, 2),
    (-0.0167758797004, 1, 6, 2),
    (-0.11960736638, 4, 3, 2),
    (-0.0456193625088, 4, 6, 2),
    (0.0356127892703, 4, 8, 2),
    (-0.00744277271321, 7, 6, 2),
    (-0.00173957049024, 8, 0, 2),
    (-0.0218101212895, 2, 7, 3),
    (0.0243321665592, 3, 12, 3),
    (-0.0374401334235, 3, 16, 3),
    (0.143387157569, 5, 22, 4),
    (-0.134919690833, 5, 24, 4),
    (-0.0231512250535, 6, 16, 4),
    (0.0123631254929, 7, 24, 4),
    (0.00210583219729, 8, 8, 4),
    (-0.000339585190264, 10, 2, 4),
    (0.00559936517716, 4, 28, 5),
    (-0.000303351180556, 8, 14, 6),
    (-213.654886883, 2, 1, 0, 25, 1, 325, 1.16),
    (26641.5691493, 2, 0, 0, 25, 1, 300, 1.19),
    (-24027.2122046, 2, 1, 0, 25, 1, 300, 1.19),
    (-283.41603424, 3, 3, 0, 15, 1, 275, 1.25),
    (212.472844002, 3, 3, 0, 20, 1, 275, 1.22),
    NonAnalytic(n=-0.666422765408, a=3.5, b=0.875, beta=0.3,
                A=0.7, B=0.3, C=10, D=275),
    NonAnalytic(n=0.726086323499, a=3.5, b=0.925, beta=0.3,
                A=0.7, B=0.3, C=10, D=275),
    NonAnalytic(n=0.0550686686128, a=3, b=0.875, beta=0.3,
                A=0.7, B=1, C=12.5, D=275),
)

#: phi0 = ln(delta) + a1 + a2 tau + 2.5 ln(tau)
#:                  + sum n ln(1 - exp(-theta tau))
#: 2.5 rather than 3: CO2 is linear, so it has two rotational degrees of
#: freedom rather than three, and its rigid-rotor cp/R is 7/2 rather than 4.
#: a1 and a2 are solved from the reference state rather than written down.
IDEAL_LOG_TAU = 2.5
EINSTEIN = (
    (1.99427042, 3.15163),
    (0.62105248, 6.1119),
    (0.41195293, 6.77708),
    (1.04028922, 11.32384),
    (0.08327678, 27.08792),
)

REFERENCE_T = 273.15
REFERENCE_H = 200e3            # J/kg
REFERENCE_S = 1000.0           # J/(kg K)


CarbonDioxideError = FluidError


FLUID = Fluid(
    name="Carbon dioxide",
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
    source="Span & Wagner, J. Phys. Chem. Ref. Data 25 (1996) 1509",
)


def saturation_pressure(T: float) -> float:
    return FLUID.saturation_pressure(T)


def saturation_temperature(p: float) -> float:
    return FLUID.saturation_temperature(p)
