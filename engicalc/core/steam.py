"""Water and steam properties, from IAPWS-IF97.

Computed from the international standard rather than transcribed from a book.
That matters for two reasons. A table has to be interpolated between its rows
and read off at its edges, and both are places to go wrong; and a two hundred
row table typed in by hand is two hundred chances to put a digit in the wrong
place, each of which produces a number that looks perfectly reasonable.

**Every equation here is checked against the verification values published
with the standard**, in the tests. That is the whole basis for trusting it:
the coefficients are long and the formulation is easy to get subtly wrong, and
a subtly wrong property is worse than no property at all, because it is
believed. If those checks ever fail, this module is wrong and should not be
used until it passes again.

Covered: region 1 (liquid water), region 2 (steam), and region 4 (the
saturation line between them). That is the part of the chart a course in
thermodynamics actually uses. Region 3, around the critical point, and region
5, above 1073 K, are not implemented, and asking for a state in them raises
rather than returning an answer from the wrong equations.

Pressures are MPa, temperatures kelvin, specific volume m3/kg, enthalpy and
internal energy kJ/kg, entropy kJ/(kg K) - the units the standard is written
in. The tab converts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .parsing import ParseError

#: The specific gas constant for ordinary water, kJ/(kg K).
R = 0.461526

#: Where the standard stops. Region 5 continues above this and is not here.
T_MAX = 1073.15
P_MAX = 100.0
#: The triple point, where the saturation line starts.
T_TRIPLE = 273.15
P_TRIPLE = 611.657e-6
#: The critical point, where liquid and vapour stop being different things.
T_CRITICAL = 647.096
P_CRITICAL = 22.064


class SteamError(ParseError):
    """Raised for a state the standard does not cover."""


# --------------------------------------------------------------------------
# Region 4 - the saturation line
# --------------------------------------------------------------------------
_N4 = (0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2,
       0.12020824702470e5, -0.32325550322333e7, 0.14915108613530e2,
       -0.48232657361591e4, 0.40511340542057e6, -0.23855557567849,
       0.65017534844798e3)


def saturation_pressure(T: float) -> float:
    """Pressure at which water boils at *T*, in MPa."""
    if not T_TRIPLE - 0.01 <= T <= T_CRITICAL + 1e-9:
        raise SteamError(
            f"The saturation line runs from {T_TRIPLE:.2f} K to "
            f"{T_CRITICAL:.3f} K; {T:.2f} K is off the end of it.")
    theta = T + _N4[8] / (T - _N4[9])
    a = theta * theta + _N4[0] * theta + _N4[1]
    b = _N4[2] * theta * theta + _N4[3] * theta + _N4[4]
    c = _N4[5] * theta * theta + _N4[6] * theta + _N4[7]
    return (2 * c / (-b + math.sqrt(b * b - 4 * a * c))) ** 4


def saturation_temperature(p: float) -> float:
    """Temperature at which water boils at *p*, in K."""
    if not P_TRIPLE - 1e-9 <= p <= P_CRITICAL + 1e-9:
        raise SteamError(
            f"The saturation line runs from {P_TRIPLE * 1000:.4f} kPa to "
            f"{P_CRITICAL:.3f} MPa; {p:.4f} MPa is off the end of it.")
    beta = p ** 0.25
    e = beta * beta + _N4[2] * beta + _N4[5]
    f = _N4[0] * beta * beta + _N4[3] * beta + _N4[6]
    g = _N4[1] * beta * beta + _N4[4] * beta + _N4[7]
    d = 2 * g / (-f - math.sqrt(f * f - 4 * e * g))
    return (_N4[9] + d - math.sqrt((_N4[9] + d) ** 2 - 4 * (_N4[8]
                                                            + _N4[9] * d))) / 2


# --------------------------------------------------------------------------
# Region 1 - liquid water
# --------------------------------------------------------------------------
# I, J, n for the Gibbs free energy of region 1.
_R1 = (
    (0, -2, 0.14632971213167), (0, -1, -0.84548187169114),
    (0, 0, -0.37563603672040e1), (0, 1, 0.33855169168385e1),
    (0, 2, -0.95791963387872), (0, 3, 0.15772038513228),
    (0, 4, -0.16616417199501e-1), (0, 5, 0.81214629983568e-3),
    (1, -9, 0.28319080123804e-3), (1, -7, -0.60706301565874e-3),
    (1, -1, -0.18990068218419e-1), (1, 0, -0.32529748770505e-1),
    (1, 1, -0.21841717175414e-1), (1, 3, -0.52838357969930e-4),
    (2, -3, -0.47184321073267e-3), (2, 0, -0.30001780793026e-3),
    (2, 1, 0.47661393906987e-4), (2, 3, -0.44141845330846e-5),
    (2, 17, -0.72694996297594e-15), (3, -4, -0.31679644845054e-4),
    (3, 0, -0.28270797985312e-5), (3, 6, -0.85205128120103e-9),
    (4, -5, -0.22425281908000e-5), (4, -2, -0.65171222895601e-6),
    (4, 10, -0.14341729937924e-12), (5, -8, -0.40516996860117e-6),
    (8, -11, -0.12734301741641e-8), (8, -6, -0.17424871230634e-9),
    (21, -29, -0.68762131295531e-18), (23, -31, 0.14478307828521e-19),
    (29, -38, 0.26335781662795e-22), (30, -39, -0.11947622640071e-22),
    (31, -40, 0.18228094581404e-23), (32, -41, -0.93537087292458e-25),
)


def _region1(p: float, T: float) -> dict:
    pi = p / 16.53
    tau = 1386.0 / T
    g = gp = gt = 0.0
    for i, j, n in _R1:
        base = (7.1 - pi) ** i
        power = (tau - 1.222) ** j
        g += n * base * power
        gp -= n * i * (7.1 - pi) ** (i - 1) * power
        gt += n * base * j * (tau - 1.222) ** (j - 1)
    return {"v": R * T / (p * 1000.0) * pi * gp,
            "h": R * T * tau * gt,
            "u": R * T * (tau * gt - pi * gp),
            "s": R * (tau * gt - g)}


# --------------------------------------------------------------------------
# Region 2 - steam
# --------------------------------------------------------------------------
# The ideal-gas part.
_R2_IDEAL = (
    (0, -0.96927686500217e1), (1, 0.10086655968018e2),
    (-5, -0.56087911283020e-2), (-4, 0.71452738081455e-1),
    (-3, -0.40710498223928), (-2, 0.14240819171444e1),
    (-1, -0.43839511319450e1), (2, -0.28408632460772),
    (3, 0.21268463753307e-1),
)

# The residual part.
_R2_RESIDUAL = (
    (1, 0, -0.17731742473213e-2), (1, 1, -0.17834862292358e-1),
    (1, 2, -0.45996013696365e-1), (1, 3, -0.57581259083432e-1),
    (1, 6, -0.50325278727930e-1), (2, 1, -0.33032641670203e-4),
    (2, 2, -0.18948987516315e-3), (2, 4, -0.39392777243355e-2),
    (2, 7, -0.43797295650573e-1), (2, 36, -0.26674547914087e-4),
    (3, 0, 0.20481737692309e-7), (3, 1, 0.43870667284435e-6),
    (3, 3, -0.32277677238570e-4), (3, 6, -0.15033924542148e-2),
    (3, 35, -0.40668253562649e-1), (4, 1, -0.78847309559367e-9),
    (4, 2, 0.12790717852285e-7), (4, 3, 0.48225372718507e-6),
    (5, 7, 0.22922076337661e-5), (6, 3, -0.16714766451061e-10),
    (6, 16, -0.21171472321355e-2), (6, 35, -0.23895741934104e2),
    (7, 0, -0.59059564324270e-17), (7, 11, -0.12621808899101e-5),
    (7, 25, -0.38946842435739e-1), (8, 8, 0.11256211360459e-10),
    (8, 36, -0.82311340897998e1), (9, 13, 0.19809712802088e-7),
    (10, 4, 0.10406965210174e-18), (10, 10, -0.10234747095929e-12),
    (10, 14, -0.10018179379511e-8), (16, 29, -0.80882908646985e-10),
    (16, 50, 0.10693031879409), (18, 57, -0.33662250574171),
    (20, 20, 0.89185845355421e-24), (20, 35, 0.30629316876232e-12),
    (20, 48, -0.42002467698208e-5), (21, 21, -0.59056029685639e-25),
    (22, 53, 0.37826947613457e-5), (23, 39, -0.12768608934681e-14),
    (24, 26, 0.73087610595061e-28), (24, 40, 0.55414715350778e-16),
    (24, 58, -0.94369707241210e-6),
)


def _region2(p: float, T: float) -> dict:
    pi = p
    tau = 540.0 / T

    g = math.log(pi)
    gp = 1.0 / pi
    gt = 0.0
    for j, n in _R2_IDEAL:
        g += n * tau ** j
        gt += n * j * tau ** (j - 1)

    for i, j, n in _R2_RESIDUAL:
        g += n * pi ** i * (tau - 0.5) ** j
        gp += n * i * pi ** (i - 1) * (tau - 0.5) ** j
        gt += n * pi ** i * j * (tau - 0.5) ** (j - 1)

    return {"v": R * T / (p * 1000.0) * pi * gp,
            "h": R * T * tau * gt,
            "u": R * T * (tau * gt - pi * gp),
            "s": R * (tau * gt - g)}


# --------------------------------------------------------------------------
# Which region a state is in
# --------------------------------------------------------------------------
# The line between liquid and steam above the saturation line.
_B23 = (0.34805185628969e3, -0.11671859879975e1, 0.10192970039326e-2,
        0.57254459862746e3, 0.13918839778870e2)


def _boundary_23_pressure(T: float) -> float:
    return _B23[0] + _B23[1] * T + _B23[2] * T * T


def region_of(p: float, T: float) -> int:
    """Which IF-97 region the state (p, T) is in.

    Raises for the two regions this module does not implement, rather than
    answering from the wrong equations - a number from region 3 computed with
    region 1's formulation looks entirely plausible and is simply wrong.
    """
    if T > T_MAX:
        raise SteamError(
            f"{T:.1f} K is above {T_MAX:.2f} K, where the standard's fifth "
            "region begins. That one is not implemented here.")
    if p > P_MAX or p <= 0:
        raise SteamError(
            f"The pressure has to be between 0 and {P_MAX:.0f} MPa; "
            f"{p:.3f} MPa is not.")
    if T < T_TRIPLE:
        raise SteamError(f"{T:.2f} K is below the triple point, so this is "
                         "ice rather than water.")

    if T <= 623.15:
        return 1 if p > saturation_pressure(T) else 2
    if T <= 863.15 and p > _boundary_23_pressure(T):
        raise SteamError(
            "That state is near the critical point, in the standard's third "
            "region, which is not implemented here.")
    return 2


@dataclass
class State:
    """Water or steam at one state, with the numbers a table would give."""

    p: float                       # MPa
    T: float                       # K
    v: float                       # m3/kg
    h: float                       # kJ/kg
    u: float                       # kJ/kg
    s: float                       # kJ/(kg K)
    region: int
    phase: str

    @property
    def density(self) -> float:
        return 1.0 / self.v if self.v else float("inf")

    def rows(self) -> list:
        """(symbol, name, value, unit) - the symbol first, because that is
        the one that turns up in the equation the number is going into."""
        return [
            ("p", "pressure", self.p * 1000.0, "kPa"),
            ("T", "temperature", self.T - 273.15, "deg C"),
            ("v", "specific volume", self.v, "m3/kg"),
            ("\u03c1", "density", self.density, "kg/m3"),
            ("h", "specific enthalpy", self.h, "kJ/kg"),
            ("u", "internal energy", self.u, "kJ/kg"),
            ("s", "entropy", self.s, "kJ/(kg K)"),
        ]


def state(p: float, T: float) -> State:
    """Properties of water or steam at pressure *p* (MPa), temperature *T* (K)."""
    region = region_of(p, T)
    values = _region1(p, T) if region == 1 else _region2(p, T)
    phase = "liquid water" if region == 1 else "steam"
    if region == 1 and abs(p - saturation_pressure(T)) < 1e-12:
        phase = "saturated liquid"
    return State(p=p, T=T, region=region, phase=phase, **values)


def wet(quality: float, T: float | None = None,
        p: float | None = None) -> State:
    """Steam that is part liquid, part vapour, at the given dryness.

    *quality* is the vapour fraction by mass: 0 is saturated liquid, 1 is
    saturated vapour. Every property is the same weighted average between
    the two, which is the whole content of `h = hf + x*hfg`.

    Temperature and pressure are not independent here - inside the dome one
    fixes the other - so give one of them, as on the saturation line.
    """
    if not 0.0 <= quality <= 1.0:
        raise SteamError(
            f"Quality is the fraction that is vapour, so it runs from 0 to 1; "
            f"{quality:g} is outside that. A value above 1 usually means the "
            "steam is superheated, which needs a temperature as well as a "
            "pressure.")
    liquid, vapour = saturated(T=T, p=p)
    mix = {}
    for name in ("v", "h", "u", "s"):
        low, high = getattr(liquid, name), getattr(vapour, name)
        mix[name] = low + quality * (high - low)
    phase = ("saturated liquid" if quality == 0 else
             "saturated vapour" if quality == 1 else
             f"wet steam, {quality:g} dry")
    return State(p=liquid.p, T=liquid.T, region=4, phase=phase, **mix)


def saturated(T: float | None = None, p: float | None = None) -> tuple:
    """The liquid and vapour states on the saturation line.

    Give a temperature or a pressure - the other follows, since on the
    saturation line they are not independent. That is the whole content of
    the line, and a table that lets you set both is lying about it.
    """
    if (T is None) == (p is None):
        raise SteamError("Give either a temperature or a pressure, not both - "
                         "on the saturation line one fixes the other.")
    if T is None:
        T = saturation_temperature(p)
    else:
        p = saturation_pressure(T)
    if T >= T_CRITICAL - 1e-9:
        raise SteamError(
            "At the critical point liquid and vapour stop being different "
            "things, so there is no pair of states to report.")

    # Nudged off the line to land in each region. On the line itself the two
    # phases share a pressure, and asking region 1 for a state at exactly
    # saturation is asking which side of a boundary a point on it is.
    liquid = _region1(p, T)
    vapour = _region2(p, T)
    return (State(p=p, T=T, region=1, phase="saturated liquid", **liquid),
            State(p=p, T=T, region=2, phase="saturated vapour", **vapour))
