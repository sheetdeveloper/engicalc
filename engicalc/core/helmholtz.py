"""A Helmholtz equation of state, and everything that gets solved on one.

Every modern reference formulation for a pure fluid has the same shape: the
Helmholtz free energy as a function of reduced density and reduced
temperature, split into an ideal-gas part and a residual part, with every
other property falling out of its derivatives. What differs between fluids
is a table of coefficients and a handful of constants.

So the machinery lives here once - the Maxwell construction that finds the
saturation line, the safeguarded Newton that finds a density at a pressure,
the reference state solved from where the tables are measured - and each
fluid is a table of numbers with a note saying where it came from.

None of this uses an ancillary equation for the saturation line. The
saturation pressure is found from the equation itself, by the condition
that defines it: the two phases at one pressure with the same Gibbs energy.
That is slower than evaluating a fitted curve, and it means the published
ancillary can be used to *check* the answer rather than to produce it -
which is the whole reason to trust the result.

The residual terms come in three shapes, told apart by how long the tuple
is, and a fluid uses whichever its formulation was published with:

    (n, d, t, c)                        n delta^d tau^t, times exp(-delta^c)
                                        when c is not zero

    (n, d, t, 0, eta, eps, bet, gam)    times exp(-eta(delta-eps)^2
                                                  -beta(tau-gamma)^2)

    (n, d, t, 0, eta, eps, bet, gam, b) times exp(+eta(delta-eps)^2
                                                  + 1/(b + beta(tau-gamma)^2))

The second is the Gaussian bell the newer formulations use to shape the
critical region. The third is the associating term of Gao and others, for a
fluid whose molecules hydrogen bond - ammonia does, which is why its
equation needed a shape the others do not. Note the signs: in that one eta
is used with a plus and is published negative, and the temperature part is
a reciprocal rather than a Gaussian.

A fluid whose published equation needs a shape not listed here has to have
it added rather than approximated by one of these.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

from .parsing import ParseError


class FluidError(ParseError):
    """Raised when a state cannot be worked out."""


@dataclass
class State:
    """One state of a fluid, with everything about it."""

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


@dataclass(frozen=True, eq=False)
class Fluid:
    """One pure fluid: its constants, its coefficients, and its states.

    Compared by identity rather than by value, so that the caches below can
    key on it without hashing several hundred coefficients every call.
    """

    name: str
    molar_mass: float          # kg/mol
    molar_gas: float           # J/(mol K), as the formulation used it

    #: What the equation is reduced about. Often close to the critical
    #: point but not equal to it - the fitted values are part of the
    #: formulation, and substituting the critical ones moves every answer.
    T_reducing: float
    rho_reducing: float

    T_critical: float
    p_critical: float
    rho_critical: float
    T_triple: float
    p_triple: float

    T_min: float
    T_max: float
    p_max: float
    #: The densest the liquid gets, which a density search has to reach.
    #: Saturated liquid at the triple point can be over three times the
    #: critical density, and a search that stops at twice it finds no
    #: liquid at all and looks like a broken equation rather than a short
    #: bracket.
    rho_max: float

    residual: tuple

    #: phi0 = ln(delta) + a1 + a2 tau + log_tau ln(tau) + sum a tau^t
    #:                  + sum a ln(1 - exp(-theta tau))
    #: a1 and a2 shift entropy and enthalpy by a constant and are solved
    #: from the reference state rather than written down.
    ideal_log_tau: float
    ideal_powers: tuple = ()
    ideal_einstein: tuple = ()

    #: Where the published tables are measured from.
    reference_T: float = 273.15
    reference_h: float = 200e3
    reference_s: float = 1000.0

    #: How far below the critical temperature the saturation line is
    #: followed. The loop in the isotherm shrinks to nothing at the
    #: critical point and the equation's own critical point is a hair away
    #: from the tabulated one, so the last fraction of a kelvin has no two
    #: phases in it to find.
    critical_margin: float = 0.05

    #: How far off the saturation line a single-phase search starts.
    clear_of_the_line: float = 1e-3

    #: Where the data came from, quoted on screen and in the tests.
    source: str = ""

    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    # -- the equation ------------------------------------------------------
    @property
    def R(self) -> float:
        """The specific gas constant, which is what everything is in."""
        return self.molar_gas / self.molar_mass

    def _residual(self, delta: float, tau: float) -> tuple:
        """(phi, phi_d, phi_dd, phi_t, phi_tt, phi_dt), residual part."""
        phi = phi_d = phi_dd = phi_t = phi_tt = phi_dt = 0.0
        for term in self.residual:
            n, d, t, c = term[:4]
            power = n * delta ** d * tau ** t
            if len(term) == 9:
                # The associating term. It factorises into a part in delta
                # and a part in tau, so each derivative is that factor's
                # own logarithmic derivative and the cross derivative is
                # simply the product of the two.
                eta, epsilon, beta, gamma, b = term[4:]
                bottom = b + beta * (tau - gamma) ** 2
                damped = power * math.exp(eta * (delta - epsilon) ** 2
                                          + 1.0 / bottom)
                first = d / delta + 2.0 * eta * (delta - epsilon)
                slope = -2.0 * beta * (tau - gamma) / (bottom * bottom)
                curve = (-2.0 * beta / (bottom * bottom)
                         + 8.0 * beta * beta * (tau - gamma) ** 2
                         / bottom ** 3)
                second = t / tau + slope
                phi += damped
                phi_d += damped * first
                phi_dd += damped * (first * first - d / (delta * delta)
                                    + 2.0 * eta)
                phi_t += damped * second
                phi_tt += damped * (second * second - t / (tau * tau)
                                    + curve)
                phi_dt += damped * first * second
            elif len(term) == 8:
                # The Gaussian bell. Both exponents are quadratic, so each
                # derivative picks up a linear factor rather than the
                # delta^c one the exponential terms have.
                eta, epsilon, beta, gamma = term[4:]
                damped = power * math.exp(-eta * (delta - epsilon) ** 2
                                          - beta * (tau - gamma) ** 2)
                first = d / delta - 2.0 * eta * (delta - epsilon)
                second = t / tau - 2.0 * beta * (tau - gamma)
                phi += damped
                phi_d += damped * first
                phi_dd += damped * (first * first - d / (delta * delta)
                                    - 2.0 * eta)
                phi_t += damped * second
                phi_tt += damped * (second * second - t / (tau * tau)
                                    - 2.0 * beta)
                phi_dt += damped * first * second
            elif c == 0:
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

    def _ideal(self, delta: float, tau: float,
               a1: float, a2: float) -> tuple:
        """(phi0, phi0_t, phi0_tt). The density part is only ever ln(delta)."""
        log_tau = self.ideal_log_tau
        phi = math.log(delta) + a1 + a2 * tau + log_tau * math.log(tau)
        phi_t = a2 + log_tau / tau
        phi_tt = -log_tau / (tau * tau)
        for a, t in self.ideal_powers:
            phi += a * tau ** t
            phi_t += a * t * tau ** (t - 1)
            phi_tt += a * t * (t - 1) * tau ** (t - 2)
        for a, theta in self.ideal_einstein:
            # A Planck-Einstein term: one vibrational mode of the molecule,
            # which is what makes the ideal-gas heat capacity rise with
            # temperature instead of sitting at its rigid-rotor value.
            gone = math.exp(-theta * tau)
            phi += a * math.log(1.0 - gone)
            phi_t += a * theta * gone / (1.0 - gone)
            phi_tt -= a * theta * theta * gone / (1.0 - gone) ** 2
        return phi, phi_t, phi_tt

    # -- pressure, and its slope -------------------------------------------
    def pressure(self, T: float, rho: float) -> float:
        """p = rho R T (1 + delta phir_delta). No reference state in it."""
        delta, tau = rho / self.rho_reducing, self.T_reducing / T
        _phi, phi_d, *_rest = self._residual(delta, tau)
        return rho * self.R * T * (1.0 + delta * phi_d)

    def _pressure_and_slope(self, T: float, rho: float) -> tuple:
        """(p, dp/drho), both out of the one differentiation.

        The slope costs nothing extra - it is the same residual evaluation
        with the second density derivative used as well - and having it
        turns the root finding from bisection into Newton.
        """
        delta, tau = rho / self.rho_reducing, self.T_reducing / T
        _phi, phi_d, phi_dd, *_rest = self._residual(delta, tau)
        return (rho * self.R * T * (1.0 + delta * phi_d),
                self.R * T * (1.0 + 2.0 * delta * phi_d
                              + delta * delta * phi_dd))

    def _gibbs_over_rt(self, T: float, rho: float) -> float:
        """g / RT, less the ideal constants, which cancel between phases."""
        delta, tau = rho / self.rho_reducing, self.T_reducing / T
        phi, phi_d, *_rest = self._residual(delta, tau)
        return math.log(delta) + phi + delta * phi_d

    # -- the reference state -----------------------------------------------
    def _reference(self) -> tuple:
        """The two ideal-gas constants, from where the tables are measured.

        Solved rather than looked up, and they separate cleanly. Entropy
        carries a1 and nothing else - the a2 terms cancel between
        tau phi0_tau and phi0 - so a1 comes straight out of the entropy
        condition. Enthalpy is then linear in a2. Two one-line solves, and
        the reference state becomes something this guarantees instead of
        something it hopes it typed in.
        """
        if "reference" in self._cache:
            return self._cache["reference"]
        T = self.reference_T
        rho, _vapour = self._saturation_densities(T, guessing=True)
        delta, tau = rho / self.rho_reducing, self.T_reducing / T
        phi, phi_d, _dd, phi_t, _tt, _dt = self._residual(delta, tau)

        # With a1 = a2 = 0: s/R = tau (phi0_tau + phir_tau) - phi0 - phir.
        bare = self._ideal(delta, tau, 0.0, 0.0)
        entropy = tau * (bare[1] + phi_t) - bare[0] - phi
        a1 = entropy - self.reference_s / self.R

        # h/RT = 1 + tau (phi0_tau + phir_tau) + delta phir_delta, and
        # phi0_tau carries a2 straight.
        enthalpy = self.R * T * (1.0 + tau * (bare[1] + phi_t)
                                 + delta * phi_d)
        a2 = (self.reference_h - enthalpy) / (self.R * T * tau)
        self._cache["reference"] = (a1, a2)
        return a1, a2

    # -- a state -----------------------------------------------------------
    def state_at(self, T: float, rho: float,
                 quality: float | None = None) -> State:
        """Everything about the fluid at a temperature and a density."""
        if not self.T_min - 1e-9 <= T <= self.T_max:
            raise FluidError(
                f"{T:.2f} K is outside the range the {self.name} equation "
                f"covers, which is {self.T_min:g} K to {self.T_max:g} K.")
        if rho <= 0:
            raise FluidError("Density has to be positive.")
        a1, a2 = self._reference()
        R = self.R
        delta, tau = rho / self.rho_reducing, self.T_reducing / T
        phi, phi_d, phi_dd, phi_t, phi_tt, phi_dt = self._residual(delta, tau)
        zero, zero_t, zero_tt = self._ideal(delta, tau, a1, a2)

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

    # -- the saturation line -----------------------------------------------
    def _turning_points(self, T: float) -> tuple:
        """The two densities where dp/drho is nought, either side of the dome.

        Below the critical temperature an isotherm has a loop in it and the
        saturation pressure lies between the pressures at the two ends of
        that loop. Finding them by walking the isotherm needs no starting
        guess and no ancillary equation, which is one less table of
        coefficients to be wrong about.

        Walked in from each end and stopped at the first turning point
        found, rather than taking the first and the last of all of them.
        Between the two spinodals the equation is far outside anything it
        was fitted to and wanders through tens of gigapascals; there are
        several turning points in there and only the outermost pair bounds
        the part that is real.
        """
        found = self._cache.setdefault("turns", {})
        if T in found:
            return found[T]
        steps = 300
        lo, hi = 1e-3, self.rho_max
        walk = [lo * (hi / lo) ** (index / steps)
                for index in range(steps + 1)]
        # The pressures alone, once. Asking for the slope at every point
        # instead costs two of these apiece, and a cycle wants several
        # saturation solves.
        along = [self.pressure(T, rho) for rho in walk]

        def first_turn(order, pressures) -> float | None:
            """The first place the slope of the isotherm changes sign.

            Where two consecutive differences disagree, the slope crosses
            zero somewhere between the *outer* two densities. Bracketing
            between the inner two is half a step away from the crossing and
            misses it half the time.
            """
            changes = [second - first
                       for first, second in zip(pressures, pressures[1:])]
            for index, (before, after) in enumerate(zip(changes, changes[1:])):
                if before * after <= 0:
                    low, high = sorted((order[index], order[index + 2]))
                    try:
                        return _bisect(lambda rho: self._dp_drho(T, rho),
                                       low, high)
                    except FluidError:
                        continue     # flat to within rounding; keep looking
            return None

        vapour_side = first_turn(walk, along)
        liquid_side = first_turn(list(reversed(walk)), list(reversed(along)))
        if vapour_side is None or liquid_side is None or \
                liquid_side <= vapour_side:
            raise FluidError(
                f"No two-phase region at {T:.2f} K - the isotherm rises all "
                f"the way, which is what it does above the critical "
                f"temperature.")
        if len(found) > 2048:
            found.clear()
        found[T] = (vapour_side, liquid_side)
        return found[T]

    def _dp_drho(self, T: float, rho: float, step: float = 1e-4) -> float:
        return (self.pressure(T, rho * (1 + step))
                - self.pressure(T, rho * (1 - step))) / (2 * rho * step)

    def _root_on_branch(self, T: float, p: float,
                        lo: float, hi: float) -> float:
        """The density on one branch of the isotherm where the pressure is p.

        Newton, kept inside the bracket it started with. A step that would
        leave the bracket is replaced by the bisection step, so this is as
        fast as Newton where Newton behaves and as sure as bisection where
        it does not - which matters, because the two ends of this bracket
        are spinodals and the slope goes to nothing at both of them.
        """
        low, high = lo, hi
        at_low = self.pressure(T, low) - p
        if at_low * (self.pressure(T, high) - p) > 0:
            raise FluidError("Nothing to solve for between those two.")

        rho = 0.5 * (low + high)
        for _step in range(90):
            here, slope = self._pressure_and_slope(T, rho)
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

    def _saturation_densities(self, T: float,
                              guessing: bool = False) -> tuple:
        """(liquid, vapour) density at T, where the two phases agree.

        Two conditions: the pressures match, which is what makes it one
        pressure, and the Gibbs energies match, which is what makes neither
        phase want to become the other. Solved by moving the pressure
        between the two ends of the loop until the second condition is met.
        """
        found = self._cache.setdefault("saturation", {})
        if T in found:
            return found[T]
        if T >= self.T_critical:
            raise FluidError(
                f"{T:.2f} K is at or above the critical temperature of "
                f"{self.name} ({self.T_critical:g} K), where liquid and "
                f"vapour are the same thing and there is no saturation "
                f"line.")
        vapour_side, liquid_side = self._turning_points(T)
        top = self.pressure(T, vapour_side)
        bottom = self.pressure(T, liquid_side)

        def mismatch(p: float) -> float:
            vapour = self._root_on_branch(T, p, 1e-10, vapour_side)
            liquid = self._root_on_branch(T, p, liquid_side, self.rho_max)
            return (self._gibbs_over_rt(T, liquid)
                    - self._gibbs_over_rt(T, vapour))

        # The liquid end of the loop is at a large negative pressure, which
        # is real and is no use as a bracket: at a pressure of nothing the
        # vapour root is a density of nothing and there is no root to find.
        # So the bottom of the search is a millionth of the top instead,
        # which is well below any saturation pressure and still a pressure.
        low = max(bottom, top * 1e-6)
        p = _bisect(mismatch, low, top * (1 - 1e-9))
        answer = (self._root_on_branch(T, p, liquid_side, self.rho_max),
                  self._root_on_branch(T, p, 1e-6, vapour_side))
        if len(found) > 2048:
            found.clear()
        found[T] = answer
        return answer

    def saturation_pressure(self, T: float) -> float:
        """The pressure the two phases sit at together, in pascals."""
        liquid, _vapour = self._saturation_densities(T)
        return self.pressure(T, liquid)

    @property
    def coldest(self) -> float:
        """The coldest temperature the saturation line is followed to.

        The triple point for most fluids, but not for one whose range has
        been held above it. Propane's triple point is at a fifth of a
        millipascal, where the vapour density is a millionth of a kilogram
        per cubic metre and the two-phase search is working in numbers that
        are all rounding - so its range starts at 140 K instead, and the
        boiling point search has to start there too rather than at a
        temperature the equation is not being asked about.
        """
        return max(self.T_triple, self.T_min)

    def saturation_temperature(self, p: float) -> float:
        """The temperature at which it boils at p."""
        bottom = self.coldest
        top = self.saturation_pressure(self.T_critical - self.critical_margin)
        lowest = (self.p_triple if bottom <= self.T_triple + 1e-9
                  else self.saturation_pressure(bottom))
        if not lowest * 0.99 <= p <= top:
            raise FluidError(
                f"{p / 1000.0:.4g} kPa is outside the {self.name} saturation "
                f"line, which this follows from {lowest / 1000.0:.4g} kPa at "
                f"{bottom:g} K to {self.p_critical / 1000.0:.4g} kPa at the "
                f"critical point.")
        # Stopping short of the critical point on purpose. The loop in the
        # isotherm shrinks to nothing there, and the equation's own
        # critical point is not exactly the tabulated one - so the last
        # fraction of a kelvin has no two phases to find.
        return _bisect(lambda T: self.saturation_pressure(T) - p,
                       bottom + 1e-6,
                       self.T_critical - self.critical_margin,
                       tolerance=1e-11)

    def saturated(self, T: float) -> tuple:
        """(liquid, vapour) states at T."""
        liquid, vapour = self._saturation_densities(T)
        return (self.state_at(T, liquid, quality=0.0),
                self.state_at(T, vapour, quality=1.0))

    def wet(self, T: float, quality: float) -> State:
        """A mixture of the two phases, quality of it vapour by mass."""
        if not 0.0 <= quality <= 1.0:
            raise FluidError(
                "Quality runs from 0, all liquid, to 1, all vapour.")
        liquid, vapour = self.saturated(T)
        blend = (lambda a, b: a + quality * (b - a))
        rho = 1.0 / blend(1.0 / liquid.rho, 1.0 / vapour.rho)
        return State(T=T, rho=rho, p=liquid.p,
                     h=blend(liquid.h, vapour.h),
                     s=blend(liquid.s, vapour.s),
                     u=blend(liquid.u, vapour.u),
                     cv=float("nan"), cp=float("nan"), w=float("nan"),
                     quality=quality)

    def latent_heat(self, T: float) -> float:
        """How much heat one kilogram takes to boil at T."""
        liquid, vapour = self.saturated(T)
        return vapour.h - liquid.h

    # -- states from the two things a gauge tells you ----------------------
    def at_pressure_and_temperature(self, p: float, T: float) -> State:
        """A single-phase state, given a pressure and a temperature."""
        if p <= 0 or p > self.p_max:
            raise FluidError(
                f"The {self.name} equation covers up to "
                f"{self.p_max / 1e6:g} MPa.")
        if T < self.T_critical:
            try:
                boils_at = self.saturation_pressure(T)
            except FluidError:
                boils_at = None
            if boils_at is not None and abs(p - boils_at) < 1e-6 * boils_at:
                raise FluidError(
                    f"At {T - 273.15:.2f} C and {p / 1000.0:.4g} kPa it is "
                    f"on the saturation line, where the temperature and "
                    f"pressure together do not say which phase it is. Give "
                    f"the quality instead.")
            if boils_at is not None:
                liquid, vapour = self._saturation_densities(T)
                if p > boils_at:
                    return self.state_at(T, self._root_on_branch(
                        T, p, liquid * 0.999, self.rho_max))
                return self.state_at(
                    T, self._root_on_branch(T, p, 1e-8, vapour * 1.001))
        # Above the critical temperature, or above the critical pressure,
        # there is only the one root to find.
        return self.state_at(T, self._root_on_branch(T, p, 1e-8,
                                                     self.rho_max))

    def _by_property(self, p: float, wanted: float, of, name: str) -> State:
        """The state at pressure p where the property of equals wanted.

        Inside the dome both enthalpy and entropy are linear in dryness, so
        the answer there is arithmetic rather than a search. Outside it, the
        temperature is solved for.
        """
        if p <= 0 or p > self.p_max:
            raise FluidError(
                f"The {self.name} equation covers up to "
                f"{self.p_max / 1e6:g} MPa.")

        if p < self.saturation_pressure(self.T_critical
                                        - self.critical_margin):
            boils_at = self.saturation_temperature(p)
            liquid, vapour = self.saturated(boils_at)
            low, high = of(liquid), of(vapour)
            if low <= wanted <= high:
                # Between the two, so it is wet and the dryness follows.
                dryness = ((wanted - low) / (high - low)
                           if high != low else 0.0)
                return self.wet(boils_at, dryness)
            # Started clear of the saturation line rather than on it. A
            # state at (p, T) exactly on the line does not say which phase
            # it is and is refused, which is right - and a thousandth of a
            # kelvin either side is the same state to anybody, the dome
            # having already caught the case that really is saturated.
            if wanted > high:
                lo, hi = boils_at + self.clear_of_the_line, self.T_max
            else:
                lo, hi = self.T_min, boils_at - self.clear_of_the_line
        else:
            lo, hi = self.T_min, self.T_max

        def missing(T: float) -> float:
            return of(self.at_pressure_and_temperature(p, T)) - wanted

        try:
            return self.at_pressure_and_temperature(
                p, _bisect(missing, lo, hi - 1e-6, tolerance=1e-11))
        except FluidError as exc:
            raise FluidError(
                f"No state of {self.name} at {p / 1000.0:.4g} kPa has {name} "
                f"of {wanted:.6g} within the range the equation covers."
            ) from exc

    def at_pressure_and_entropy(self, p: float, s: float) -> State:
        """Where a reversible compression from p at entropy s comes out."""
        return self._by_property(p, s, lambda state: state.s, "an entropy")

    def at_pressure_and_enthalpy(self, p: float, h: float) -> State:
        """Where a throttle to p comes out, since a throttle keeps enthalpy."""
        return self._by_property(p, h, lambda state: state.h, "an enthalpy")


def _bisect(f, lo: float, hi: float, tolerance: float = 1e-12) -> float:
    """Plain bisection. Slow, and it cannot fail to converge on a bracket."""
    low, high = f(lo), f(hi)
    if low * high > 0:
        raise FluidError("Nothing to solve for between those two.")
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
