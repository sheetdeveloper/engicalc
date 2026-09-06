"""R134a, from the international standard equation of state.

The refrigerant every fridge, car and heat pump course is taught on, and the
one every set of tables in a college library is for.

This is Tillner-Roth and Baehr's formulation - a Helmholtz free energy in
reduced density and reduced temperature, from which every other property
follows by differentiating. It is the same shape as the IF-97 steam
formulation already here and is used the same way: nothing is interpolated,
nothing is fitted, and pressure, enthalpy, entropy and the specific heats
are all one function differentiated in different directions, so they cannot
disagree with each other.

An earlier attempt at this was abandoned rather than shipped. It used a
correlation written from memory that got the saturation line right to a
fiftieth of a percent and the saturated vapour density wrong by a factor of
fifty, which is exactly the sort of failure that looks like success from the
one number anybody checks. The difference now is that this is the actual
equation, and that every published value it can be checked against, it is.

Two of the constants are not taken from anywhere. The ideal-gas part carries
two arbitrary constants that fix nothing except where enthalpy and entropy
are measured from, and the convention for refrigerants is that saturated
liquid at 0 C has an enthalpy of 200 kJ/kg and an entropy of 1 kJ/kg K. So
those two are solved for from that condition rather than copied, which makes
the reference state a thing this program guarantees rather than a thing it
hopes it typed in correctly.

Range: 170 K to 455 K, up to 70 MPa. Outside that it raises rather than
extrapolating.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from .parsing import ParseError

MOLAR_MASS = 0.102032          # kg/mol
MOLAR_GAS = 8.314471           # J/(mol K)

#: Where the equation is reduced about. Not the critical point - the
#: formulation reduces about slightly different values, and using the
#: critical ones instead moves every answer.
#:
#: The density is given as 4978.830171 mol/m^3 in the standard, and it is
#: written that way here on purpose. Taken from a secondary source as
#: 507.6 kg/m^3 it is a twelfth of a percent out, and a twelfth of a percent
#: in the reducing density is a twelfth of a percent in every saturation
#: pressure the equation produces - flat across ninety kelvin, which is what
#: made it look like a constant rather than a mistake.
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

#: The densest it gets. Saturated liquid at the triple point is about
#: 1590 kg/m^3, which is over three times the critical density - worth
#: writing down, because a search for the liquid that stops at twice the
#: critical density finds no liquid at all and looks like a broken equation.
RHO_MAX = 1700.0

#: How far below the critical temperature the saturation line is followed.
#: The loop in the isotherm shrinks to nothing at the critical point and the
#: equation's own critical point is a hair away from the tabulated one, so
#: the last fraction of a kelvin has no two phases in it to find.
CRITICAL_MARGIN = 0.05

#: How far off the saturation line a single-phase search starts. The
#: pressure changes by about 30 kPa per kelvin near room temperature, so a
#: thousandth of a kelvin is thirty pascals - well clear of the tolerance
#: that decides a state is on the line, and far too small to be a different
#: state.
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
#: worked out below from where the tables are measured from.
A3 = -1.629789
A4 = -9.723916
A5 = -3.927170

#: Saturated liquid at 0 C, which is where refrigerant tables start.
REFERENCE_T = 273.15
REFERENCE_H = 200e3            # J/kg
REFERENCE_S = 1000.0           # J/(kg K)


class R134aError(ParseError):
    """Raised when a state cannot be worked out."""


# --------------------------------------------------------------------------
# The equation itself
# --------------------------------------------------------------------------
def _residual(delta: float, tau: float) -> tuple:
    """(phi, phi_d, phi_dd, phi_t, phi_tt, phi_dt) for the residual part."""
    phi = phi_d = phi_dd = phi_t = phi_tt = phi_dt = 0.0
    for n, d, t, c in RESIDUAL:
        power = n * delta ** d * tau ** t
        if c == 0:
            phi += power
            phi_d += power * d / delta
            phi_dd += power * d * (d - 1) / (delta * delta)
            phi_t += power * t / tau
            phi_tt += power * t * (t - 1) / (tau * tau)
            phi_dt += power * d * t / (delta * tau)
        else:
            shape = delta ** c
            damped = power * math.exp(-shape)
            first = d - c * shape
            phi += damped
            phi_d += damped * first / delta
            phi_dd += (damped
                       * (first * (first - 1) - c * c * shape)
                       / (delta * delta))
            phi_t += damped * t / tau
            phi_tt += damped * t * (t - 1) / (tau * tau)
            phi_dt += damped * first * t / (delta * tau)
    return phi, phi_d, phi_dd, phi_t, phi_tt, phi_dt


def _ideal(delta: float, tau: float, a1: float, a2: float) -> tuple:
    """(phi0, phi0_t, phi0_tt). The density part is only ever ln(delta)."""
    return (math.log(delta) + a1 + a2 * tau + A3 * math.log(tau)
            + A4 * tau ** -0.5 + A5 * tau ** -0.75,
            a2 + A3 / tau - 0.5 * A4 * tau ** -1.5
            - 0.75 * A5 * tau ** -1.75,
            -A3 / (tau * tau) + 0.75 * A4 * tau ** -2.5
            + 1.3125 * A5 * tau ** -2.75)


@dataclass
class State:
    """One state of the refrigerant, with everything about it."""

    T: float                   # K
    rho: float                 # kg/m^3
    p: float                   # Pa
    h: float                   # J/kg
    s: float                   # J/(kg K)
    u: float                   # J/kg
    cv: float                  # J/(kg K)
    cp: float                  # J/(kg K)
    w: float                   # m/s, speed of sound
    quality: float | None = None

    @property
    def v(self) -> float:
        return 1.0 / self.rho


def _pressure(T: float, rho: float) -> float:
    """p = rho R T (1 + delta phir_delta). No reference state in it."""
    delta, tau = rho / RHO_REDUCING, T_REDUCING / T
    _phi, phi_d, *_rest = _residual(delta, tau)
    return rho * R * T * (1.0 + delta * phi_d)


def _pressure_and_slope(T: float, rho: float) -> tuple:
    """(p, dp/drho), both out of the one differentiation.

    The slope costs nothing extra - it is the same residual evaluation with
    the second density derivative used as well - and having it turns the
    root finding from bisection into Newton.
    """
    delta, tau = rho / RHO_REDUCING, T_REDUCING / T
    _phi, phi_d, phi_dd, *_rest = _residual(delta, tau)
    return (rho * R * T * (1.0 + delta * phi_d),
            R * T * (1.0 + 2.0 * delta * phi_d + delta * delta * phi_dd))


def _gibbs_over_rt(T: float, rho: float) -> float:
    """g / RT, less the ideal-gas constants, which cancel between phases."""
    delta, tau = rho / RHO_REDUCING, T_REDUCING / T
    phi, phi_d, *_rest = _residual(delta, tau)
    return math.log(delta) + phi + delta * phi_d


@lru_cache(maxsize=1)
def _reference() -> tuple:
    """The two ideal-gas constants, from where the tables are measured.

    Solved rather than looked up, and they separate cleanly. Entropy carries
    a1 and nothing else - the a2 terms cancel between tau phi0_tau and phi0 -
    so a1 comes straight out of the entropy condition. Enthalpy is then
    linear in a2. Two one-line solves, and the reference state becomes
    something this guarantees instead of something it hopes it typed in.
    """
    T = REFERENCE_T
    rho, _vapour = _saturation_densities(T, guessing=True)
    delta, tau = rho / RHO_REDUCING, T_REDUCING / T
    phi, phi_d, _dd, phi_t, _tt, _dt = _residual(delta, tau)

    # With a1 = a2 = 0: s/R = tau (phi0_tau + phir_tau) - phi0 - phir.
    bare = _ideal(delta, tau, 0.0, 0.0)
    entropy = tau * (bare[1] + phi_t) - bare[0] - phi
    a1 = entropy - REFERENCE_S / R          # phi0 carries a1 with a minus

    # h/RT = 1 + tau (phi0_tau + phir_tau) + delta phir_delta, and phi0_tau
    # carries a2 straight.
    enthalpy = R * T * (1.0 + tau * (bare[1] + phi_t) + delta * phi_d)
    a2 = (REFERENCE_H - enthalpy) / (R * T * tau)
    return a1, a2


def state_at(T: float, rho: float, quality: float | None = None) -> State:
    """Everything about the refrigerant at a temperature and a density."""
    if not T_MIN - 1e-9 <= T <= T_MAX:
        raise R134aError(
            f"{T:.2f} K is outside the range the equation covers, which is "
            f"{T_MIN:g} K to {T_MAX:g} K.")
    if rho <= 0:
        raise R134aError("Density has to be positive.")
    a1, a2 = _reference()
    delta, tau = rho / RHO_REDUCING, T_REDUCING / T
    phi, phi_d, phi_dd, phi_t, phi_tt, phi_dt = _residual(delta, tau)
    zero, zero_t, zero_tt = _ideal(delta, tau, a1, a2)

    p = rho * R * T * (1.0 + delta * phi_d)
    u = R * T * tau * (zero_t + phi_t)
    h = R * T * (1.0 + tau * (zero_t + phi_t) + delta * phi_d)
    s = R * (tau * (zero_t + phi_t) - zero - phi)
    cv = -R * tau * tau * (zero_tt + phi_tt)
    bottom = 1.0 + 2.0 * delta * phi_d + delta * delta * phi_dd
    top = (1.0 + delta * phi_d - delta * tau * phi_dt) ** 2
    cp = cv + R * top / bottom if abs(bottom) > 1e-12 else float("nan")
    speed_squared = R * T * (bottom + top / (-tau * tau
                                             * (zero_tt + phi_tt)))
    return State(T=T, rho=rho, p=p, h=h, s=s, u=u, cv=cv, cp=cp,
                 w=math.sqrt(speed_squared) if speed_squared > 0
                 else float("nan"),
                 quality=quality)


# --------------------------------------------------------------------------
# The saturation line
# --------------------------------------------------------------------------
@lru_cache(maxsize=1024)
def _turning_points(T: float) -> tuple:
    """The two densities where dp/drho is nought, either side of the dome.

    Below the critical temperature an isotherm has a loop in it and the
    saturation pressure lies between the pressures at the two ends of that
    loop. Finding them by walking the isotherm needs no starting guess and
    no ancillary equation, which is one less table of coefficients to be
    wrong about.

    Walked in from each end and stopped at the first turning point found,
    rather than taking the first and the last of all of them. Between the
    two spinodals the equation is far outside anything it was fitted to and
    wanders through tens of gigapascals; there are several turning points
    in there and only the outermost pair bounds the part that is real.
    """
    steps = 300
    lo, hi = 1e-3, RHO_MAX
    walk = [lo * (hi / lo) ** (index / steps) for index in range(steps + 1)]
    # The pressures alone, once. Asking for the slope at every point instead
    # costs two of these apiece, and a cycle wants several saturation solves.
    along = [_pressure(T, rho) for rho in walk]

    def first_turn(order, pressures) -> float | None:
        """The first place the slope of the isotherm changes sign.

        Where two consecutive differences disagree, the slope crosses zero
        somewhere between the *outer* two densities. Bracketing between the
        inner two is half a step away from the crossing and misses it half
        the time, which is the mistake this had before.
        """
        changes = [second - first
                   for first, second in zip(pressures, pressures[1:])]
        for index, (before, after) in enumerate(zip(changes, changes[1:])):
            if before * after <= 0:
                low, high = sorted((order[index], order[index + 2]))
                try:
                    return _bisect(lambda rho: _dp_drho(T, rho), low, high)
                except R134aError:
                    continue         # flat to within rounding; keep looking
        return None

    vapour_side = first_turn(walk, along)
    liquid_side = first_turn(list(reversed(walk)),
                             list(reversed(along)))
    if vapour_side is None or liquid_side is None or \
            liquid_side <= vapour_side:
        raise R134aError(
            f"No two-phase region at {T:.2f} K - the isotherm rises all the "
            f"way, which is what it does above the critical temperature.")
    return vapour_side, liquid_side


def _dp_drho(T: float, rho: float, step: float = 1e-4) -> float:
    return (_pressure(T, rho * (1 + step))
            - _pressure(T, rho * (1 - step))) / (2 * rho * step)


def _bisect(f, lo: float, hi: float, tolerance: float = 1e-12) -> float:
    """Plain bisection. Slow, and it cannot fail to converge on a bracket."""
    low, high = f(lo), f(hi)
    if low * high > 0:
        raise R134aError("Nothing to solve for between those two.")
    for _step in range(200):
        middle = 0.5 * (lo + hi)
        value = f(middle)
        if abs(hi - lo) < tolerance * max(abs(middle), 1e-9):
            return middle
        if low * value <= 0:
            hi, high = middle, value
        else:
            lo, low = middle, value
    return 0.5 * (lo + hi)


def _root_on_branch(T: float, p: float, lo: float, hi: float) -> float:
    """The density on one branch of the isotherm where the pressure is *p*.

    Newton, kept inside the bracket it started with. A step that would
    leave the bracket is replaced by the bisection step, so this is as fast
    as Newton where Newton behaves and as sure as bisection where it does
    not - which matters, because the two ends of this bracket are spinodals
    and the slope goes to nothing at both of them.
    """
    low, high = lo, hi
    at_low = _pressure(T, low) - p
    if at_low * (_pressure(T, high) - p) > 0:
        raise R134aError("Nothing to solve for between those two.")

    rho = 0.5 * (low + high)
    for _step in range(90):
        here, slope = _pressure_and_slope(T, rho)
        gap = here - p
        if at_low * gap <= 0:
            high = rho
        else:
            low, at_low = rho, gap
        moved = rho - gap / slope if slope else None
        if moved is None or not low < moved < high:
            moved = 0.5 * (low + high)
        if abs(moved - rho) <= 1e-13 * max(abs(rho), 1e-9):
            return moved
        rho = moved
    return rho


@lru_cache(maxsize=512)
def _saturation_densities(T: float, guessing: bool = False) -> tuple:
    """(liquid, vapour) density at *T*, where the two phases agree.

    Two conditions: the pressures match, which is what makes it one
    pressure, and the Gibbs energies match, which is what makes neither
    phase want to become the other. Solved by moving the pressure between
    the two ends of the loop until the second condition is met.
    """
    if T >= T_CRITICAL:
        raise R134aError(
            f"{T:.2f} K is at or above the critical temperature "
            f"({T_CRITICAL:g} K), where liquid and vapour are the same "
            f"thing and there is no saturation line.")
    vapour_side, liquid_side = _turning_points(T)
    top = _pressure(T, vapour_side)
    bottom = _pressure(T, liquid_side)

    def mismatch(p: float) -> float:
        vapour = _root_on_branch(T, p, 1e-10, vapour_side)
        liquid = _root_on_branch(T, p, liquid_side, RHO_MAX)
        return _gibbs_over_rt(T, liquid) - _gibbs_over_rt(T, vapour)

    # The liquid end of the loop is at a large negative pressure, which is
    # real and is no use as a bracket: at a pressure of nothing the vapour
    # root is a density of nothing and there is no root to find. So the
    # bottom of the search is a millionth of the top instead, which is well
    # below any saturation pressure and still a pressure.
    low = max(bottom, top * 1e-6)
    p = _bisect(mismatch, low, top * (1 - 1e-9))
    return (_root_on_branch(T, p, liquid_side, RHO_MAX),
            _root_on_branch(T, p, 1e-6, vapour_side))


def saturation_pressure(T: float) -> float:
    """The pressure the two phases sit at together, in pascals."""
    liquid, _vapour = _saturation_densities(T)
    return _pressure(T, liquid)


def saturation_temperature(p: float) -> float:
    """The temperature at which it boils at *p*."""
    if not P_TRIPLE * 0.99 <= p <= saturation_pressure(
            T_CRITICAL - CRITICAL_MARGIN):
        raise R134aError(
            f"{p / 1000.0:.4g} kPa is outside the saturation line, which "
            f"runs from {P_TRIPLE / 1000.0:.4g} kPa at the triple point to "
            f"{P_CRITICAL / 1000.0:.4g} kPa at the critical point.")
    # Stopping short of the critical point on purpose. The loop in the
    # isotherm shrinks to nothing there, and the equation's own critical
    # point is not exactly the tabulated one - so the last fraction of a
    # kelvin has no two phases to find and asking for them raises.
    return _bisect(lambda T: saturation_pressure(T) - p,
                   T_TRIPLE + 1e-6, T_CRITICAL - CRITICAL_MARGIN,
                   tolerance=1e-11)


def saturated(T: float) -> tuple:
    """(liquid, vapour) states at *T*."""
    liquid, vapour = _saturation_densities(T)
    return (state_at(T, liquid, quality=0.0),
            state_at(T, vapour, quality=1.0))


def wet(T: float, quality: float) -> State:
    """A mixture of the two phases, *quality* of it vapour by mass."""
    if not 0.0 <= quality <= 1.0:
        raise R134aError("Quality runs from 0, all liquid, to 1, all vapour.")
    liquid, vapour = saturated(T)
    blend = (lambda a, b: a + quality * (b - a))
    rho = 1.0 / blend(1.0 / liquid.rho, 1.0 / vapour.rho)
    return State(T=T, rho=rho, p=liquid.p,
                 h=blend(liquid.h, vapour.h), s=blend(liquid.s, vapour.s),
                 u=blend(liquid.u, vapour.u),
                 cv=float("nan"), cp=float("nan"), w=float("nan"),
                 quality=quality)


def latent_heat(T: float) -> float:
    """How much heat one kilogram takes to boil at *T*."""
    liquid, vapour = saturated(T)
    return vapour.h - liquid.h


def _by_property(p: float, wanted: float, of, name: str) -> State:
    """The state at pressure *p* where the property *of* equals *wanted*.

    Inside the dome both enthalpy and entropy are linear in dryness, so the
    answer there is arithmetic rather than a search. Outside it, the
    temperature is solved for.
    """
    if p <= 0 or p > P_MAX:
        raise R134aError(f"The equation covers up to {P_MAX / 1e6:g} MPa.")

    if p < saturation_pressure(T_CRITICAL - CRITICAL_MARGIN):
        boils_at = saturation_temperature(p)
        liquid, vapour = saturated(boils_at)
        low, high = of(liquid), of(vapour)
        if low <= wanted <= high:
            # Between the two, so it is wet and the dryness follows.
            dryness = ((wanted - low) / (high - low)
                       if high != low else 0.0)
            return wet(boils_at, dryness)
        # Started clear of the saturation line rather than on it. A state
        # at (p, T) exactly on the line does not say which phase it is and
        # is refused, which is right - and a thousandth of a kelvin either
        # side is the same state to anybody, the dome having already caught
        # the case that really is saturated.
        if wanted > high:
            lo, hi = boils_at + CLEAR_OF_THE_LINE, T_MAX
        else:
            lo, hi = T_MIN, boils_at - CLEAR_OF_THE_LINE
    else:
        lo, hi = T_MIN, T_MAX

    def missing(T: float) -> float:
        return of(at_pressure_and_temperature(p, T)) - wanted

    try:
        return at_pressure_and_temperature(
            p, _bisect(missing, lo, hi - 1e-6, tolerance=1e-11))
    except R134aError as exc:
        raise R134aError(
            f"No state at {p / 1000.0:.4g} kPa has {name} of "
            f"{wanted:.6g} within the range the equation covers.") from exc


def at_pressure_and_entropy(p: float, s: float) -> State:
    """Where a reversible compression from *p* at entropy *s* comes out."""
    return _by_property(p, s, lambda state: state.s, "an entropy")


def at_pressure_and_enthalpy(p: float, h: float) -> State:
    """Where a throttle to *p* comes out, since a throttle keeps enthalpy."""
    return _by_property(p, h, lambda state: state.h, "an enthalpy")


def at_pressure_and_temperature(p: float, T: float) -> State:
    """A single-phase state, given the two things a gauge tells you."""
    if p <= 0 or p > P_MAX:
        raise R134aError(
            f"The equation covers up to {P_MAX / 1e6:g} MPa.")
    if T < T_CRITICAL:
        try:
            boils_at = saturation_pressure(T)
        except R134aError:
            boils_at = None
        if boils_at is not None and abs(p - boils_at) < 1e-6 * boils_at:
            raise R134aError(
                f"At {T - 273.15:.2f} C and {p / 1000.0:.4g} kPa it is on "
                f"the saturation line, where the temperature and pressure "
                f"together do not say which phase it is. Give the quality "
                f"instead.")
        if boils_at is not None:
            liquid, vapour = _saturation_densities(T)
            if p > boils_at:
                return state_at(T, _root_on_branch(
                    T, p, liquid * 0.999, RHO_MAX))
            return state_at(T, _root_on_branch(T, p, 1e-8, vapour * 1.001))
    # Above the critical temperature, or above the critical pressure, there
    # is only the one root to find.
    return state_at(T, _root_on_branch(T, p, 1e-8, RHO_MAX))
