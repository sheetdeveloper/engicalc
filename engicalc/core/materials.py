"""What things are made of, and what that means for a calculation.

Two levels, because two different questions get asked and they want
different data.

A **class** - "carbon steel", "aluminium alloy" - carries wide ranges,
because the class really is that wide: steel yields anywhere from 250 to
1500 N/mm2 depending entirely on what was done to it. Those ranges are what
a property chart is drawn from, and there the width is the information
rather than a compromise. A chart spanning five orders of magnitude is not
troubled by a factor of two.

A **grade** - S275, 6082-T6, 316L - carries tight values with the condition
they apply at, and is what you pull into a calculation. That use is not
tolerant in the same way.

The other division that matters is between properties set by bonding and
crystal structure, which barely move within a class, and properties set by
microstructure, which are what processing exists to change:

    structure-insensitive    density, modulus, specific heat, expansion,
                             melting point - a plain carbon steel is
                             205-215 GPa whatever was done to it
    structure-sensitive      yield, tensile strength, hardness, toughness -
                             the same steel is 250 to 1500 N/mm2

The first are quoted as values and the second as ranges, and quoting the
second as values would be fiction.

Every row states where it came from and is checked against relations that
have to hold: G = E/2(1+nu), which is a formula in the library so the data
is checked against this program's own algebra; yield below tensile strength;
service temperature below melting; and the volumetric heat capacity and
thermal diffusivity inside the bands that every solid falls in. A row that
fails is removed rather than shipped.

Assembled from material standards and manufacturers' data. Nothing here is
taken from a commercial materials database, and the numbers are indicative -
for anything that matters, the certificate for the actual batch is the
authority and this is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import units
from .parsing import ParseError

#: (what it is, its unit, whether processing moves it). The unit strings are
#: the ones the units module reads, so a value can be converted into
#: whatever a formula asks for.
PROPERTIES = {
    "density": ("Density", "kg/m^3", "insensitive"),
    "youngs": ("Young's modulus", "GPa", "insensitive"),
    "shear": ("Shear modulus", "GPa", "insensitive"),
    "poisson": ("Poisson's ratio", "", "insensitive"),
    "yield": ("Yield strength", "N/mm^2", "sensitive"),
    "uts": ("Tensile strength", "N/mm^2", "sensitive"),
    "elongation": ("Elongation", "%", "sensitive"),
    "toughness": ("Fracture toughness", "MPa*m^0.5", "sensitive"),
    "conductivity": ("Thermal conductivity", "W/(m*K)", "insensitive"),
    "specific_heat": ("Specific heat", "J/(kg*K)", "insensitive"),
    "expansion": ("Thermal expansion", "1e-6/K", "insensitive"),
    "melting": ("Melting point", "deg C", "insensitive"),
    "service": ("Maximum service temperature", "deg C", "sensitive"),
    "resistivity": ("Resistivity", "ohm*m", "insensitive"),
}

#: The families, and the colour a chart draws each in.
FAMILIES = {
    "metal": "#1f4e79",
    "polymer": "#c0392b",
    "ceramic": "#0b7a3b",
    "composite": "#8a4fbf",
    "natural": "#8a6d0b",
    "foam": "#7f8c8d",
}


class MaterialError(ParseError):
    """Raised when a material cannot be used as asked."""


@dataclass
class Material:
    """One material, as a class of them or as a specific grade."""

    name: str
    family: str
    #: A range for every property: (low, high). The two are equal where the
    #: property does not move, which is itself worth seeing.
    values: dict = field(default_factory=dict)
    grade: bool = False
    condition: str = ""
    source: str = ""

    def has(self, name: str) -> bool:
        return name in self.values

    def span(self, name: str) -> tuple:
        if name not in self.values:
            raise MaterialError(
                f"No {PROPERTIES.get(name, (name,))[0].lower()} is recorded "
                f"for {self.name}.")
        return self.values[name]

    def typical(self, name: str) -> float:
        """The middle of the range, which is what a picker offers.

        The geometric middle rather than the arithmetic one. These
        properties span orders of magnitude and are read on logarithmic
        axes, so halfway between 1 and 100 is 10 rather than 50.
        """
        low, high = self.span(name)
        if low > 0 and high > 0:
            return (low * high) ** 0.5
        return (low + high) / 2.0

    def spread(self, name: str) -> float:
        """How much the property moves within this material, as a ratio."""
        low, high = self.span(name)
        return high / low if low > 0 else float("inf")

    def rows(self) -> list:
        """(what, low, high, unit) for every property recorded."""
        found = []
        for key, (label, unit, _kind) in PROPERTIES.items():
            if key in self.values:
                low, high = self.values[key]
                found.append((label, low, high, unit))
        return found

# --------------------------------------------------------------------------
# The materials
# --------------------------------------------------------------------------
# Each entry is (low, high). Where the two are equal the property does not
# move within the material, which is itself worth being able to see.
#
# The classes are deliberately wide. Steel really does yield anywhere from
# 250 to 1500 N/mm2, and narrowing that to a single number would be inventing
# a material rather than describing a family.


def _m(name, family, source, grade=False, condition="", **values):
    return Material(name=name, family=family, source=source, grade=grade,
                    condition=condition,
                    values={key: (float(v[0]), float(v[1]))
                            if isinstance(v, (tuple, list))
                            else (float(v), float(v))
                            for key, v in values.items()})


CLASSES = [
    # -- metals ------------------------------------------------------------
    _m("Carbon steel", "metal", "EN 10025, EN 10083",
       density=(7800, 7900), youngs=(200, 215), shear=(78, 82),
       poisson=(0.285, 0.300), **{"yield": (250, 1500)},
       uts=(350, 1800), elongation=(5, 30), toughness=(30, 200),
       conductivity=(40, 60), specific_heat=(460, 490),
       expansion=(11, 13), melting=(1425, 1540), service=(350, 550),
       resistivity=(1.5e-7, 2.5e-7)),
    _m("Stainless steel", "metal", "EN 10088",
       density=(7700, 8100), youngs=(190, 205), shear=(74, 80),
       poisson=(0.27, 0.30), **{"yield": (200, 1000)},
       uts=(500, 1500), elongation=(5, 60), toughness=(50, 150),
       conductivity=(13, 20), specific_heat=(480, 530),
       expansion=(15, 18), melting=(1370, 1450), service=(600, 900),
       resistivity=(6.9e-7, 8.0e-7)),
    _m("Cast iron", "metal", "EN 1561, EN 1563",
       density=(7050, 7300), youngs=(100, 160), poisson=(0.26, 0.28),
       **{"yield": (100, 500)}, uts=(150, 800), elongation=(0.3, 18),
       toughness=(10, 50), conductivity=(25, 55),
       specific_heat=(460, 540), expansion=(10, 13),
       melting=(1130, 1250), service=(350, 500)),
    _m("Aluminium alloy", "metal", "EN 573, EN 485",
       density=(2650, 2850), youngs=(68, 80), shear=(25, 29),
       poisson=(0.32, 0.35), **{"yield": (30, 550)},
       uts=(60, 600), elongation=(1, 30), toughness=(20, 45),
       conductivity=(100, 240), specific_heat=(880, 940),
       expansion=(22, 24), melting=(475, 660), service=(130, 200),
       resistivity=(2.7e-8, 5.5e-8)),
    _m("Copper alloy", "metal", "EN 1652, EN 12163",
       density=(8300, 8960), youngs=(100, 130), shear=(40, 48),
       poisson=(0.33, 0.35), **{"yield": (50, 900)},
       uts=(200, 1000), elongation=(3, 60), toughness=(30, 90),
       conductivity=(60, 400), specific_heat=(370, 400),
       expansion=(16, 19), melting=(900, 1085), service=(200, 300),
       resistivity=(1.7e-8, 8.0e-8)),
    _m("Titanium alloy", "metal", "EN 3352, ASTM B265",
       density=(4400, 4800), youngs=(100, 125), shear=(39, 47),
       poisson=(0.33, 0.36), **{"yield": (250, 1250)},
       uts=(350, 1400), elongation=(5, 25), toughness=(55, 115),
       conductivity=(6, 25), specific_heat=(500, 560),
       expansion=(8, 10), melting=(1600, 1680), service=(400, 550)),
    _m("Magnesium alloy", "metal", "ASTM B93",
       density=(1740, 1950), youngs=(42, 47), shear=(16, 18),
       poisson=(0.28, 0.30), **{"yield": (70, 400)},
       uts=(150, 450), elongation=(2, 15), toughness=(12, 18),
       conductivity=(50, 160), specific_heat=(950, 1060),
       expansion=(25, 28), melting=(440, 660), service=(120, 200)),
    _m("Nickel alloy", "metal", "ASTM B168",
       density=(8300, 8900), youngs=(190, 220), poisson=(0.30, 0.32),
       **{"yield": (200, 1200)}, uts=(400, 1600), elongation=(3, 50),
       toughness=(60, 150), conductivity=(10, 90),
       specific_heat=(420, 480), expansion=(12, 15),
       melting=(1300, 1450), service=(800, 1200)),

    _m("Zinc alloy", "metal", "EN 12844 (Zamak and ZA die castings)",
       density=(6600, 7200), youngs=(75, 96), shear=(30, 35.5),
       poisson=(0.28, 0.32), **{"yield": (200, 400)},
       uts=(250, 440), elongation=(1, 10), toughness=(10, 30),
       conductivity=(100, 125), specific_heat=(380, 420),
       expansion=(24, 30), melting=(380, 420), service=(80, 120),
       resistivity=(5.9e-8, 6.6e-8)),
    _m("Lead alloy", "metal", "EN 12659",
       density=(10600, 11400), youngs=(14, 18), shear=(5.2, 5.9),
       poisson=(0.42, 0.45), **{"yield": (5, 40)},
       uts=(12, 55), elongation=(20, 70), toughness=(5, 15),
       conductivity=(30, 36), specific_heat=(125, 135),
       expansion=(28, 30), melting=(320, 330), service=(30, 60),
       resistivity=(2.0e-7, 2.4e-7)),
    _m("Tungsten alloy", "metal", "ASTM B777",
       density=(17000, 19300), youngs=(340, 410), shear=(130, 160),
       poisson=(0.27, 0.30), **{"yield": (550, 1400)},
       uts=(700, 1800), elongation=(1, 15), toughness=(10, 40),
       conductivity=(140, 175), specific_heat=(130, 150),
       expansion=(4.3, 5.5), melting=(3380, 3420), service=(800, 1500),
       resistivity=(5.3e-8, 6.5e-8)),
    _m("Solder, tin-based", "metal", "EN ISO 9453 (SAC and SnPb)",
       density=(7300, 8900), youngs=(30, 55), shear=(11, 21),
       poisson=(0.33, 0.40), **{"yield": (20, 55)},
       uts=(30, 75), elongation=(20, 60), toughness=(5, 20),
       conductivity=(50, 65), specific_heat=(180, 230),
       expansion=(21, 27), melting=(180, 227), service=(60, 100),
       resistivity=(1.2e-7, 1.5e-7)),

    # -- polymers ----------------------------------------------------------
    _m("Polyethylene", "polymer", "ISO 1872",
       density=(930, 970), youngs=(0.6, 1.1), poisson=(0.42, 0.44),
       **{"yield": (18, 30)}, uts=(20, 45), elongation=(100, 1000),
       toughness=(1.4, 1.7), conductivity=(0.40, 0.50),
       specific_heat=(1750, 2100), expansion=(120, 200),
       service=(80, 100)),
    _m("Polypropylene", "polymer", "ISO 1873",
       density=(890, 920), youngs=(0.9, 1.6), poisson=(0.40, 0.43),
       **{"yield": (20, 40)}, uts=(27, 45), elongation=(100, 600),
       toughness=(3.0, 4.5), conductivity=(0.11, 0.17),
       specific_heat=(1870, 1960), expansion=(122, 180),
       service=(100, 115)),
    _m("PVC, rigid", "polymer", "ISO 1163",
       density=(1300, 1580), youngs=(2.4, 3.0), poisson=(0.38, 0.41),
       **{"yield": (35, 60)}, uts=(40, 65), elongation=(10, 80),
       toughness=(1.5, 4.0), conductivity=(0.15, 0.21),
       specific_heat=(1360, 1440), expansion=(50, 80), service=(60, 80)),
    _m("Nylon, PA66", "polymer", "ISO 1874",
       density=(1120, 1150), youngs=(2.6, 3.2), poisson=(0.39, 0.41),
       **{"yield": (50, 95)}, uts=(60, 100), elongation=(30, 100),
       toughness=(2.2, 5.6), conductivity=(0.23, 0.28),
       specific_heat=(1600, 1700), expansion=(80, 95),
       service=(100, 140)),
    _m("Polycarbonate", "polymer", "ISO 7391",
       density=(1140, 1210), youngs=(2.0, 2.4), poisson=(0.39, 0.41),
       **{"yield": (59, 70)}, uts=(60, 72), elongation=(70, 150),
       toughness=(2.1, 4.6), conductivity=(0.19, 0.22),
       specific_heat=(1500, 1600), expansion=(65, 70),
       service=(100, 130)),
    _m("PTFE", "polymer", "ISO 12086",
       density=(2140, 2200), youngs=(0.4, 0.6), poisson=(0.45, 0.47),
       **{"yield": (15, 25)}, uts=(20, 35), elongation=(200, 400),
       toughness=(1.3, 1.8), conductivity=(0.24, 0.26),
       specific_heat=(1000, 1050), expansion=(100, 160),
       service=(250, 260)),
    _m("PMMA, acrylic", "polymer", "ISO 7823",
       density=(1160, 1220), youngs=(2.9, 3.5), poisson=(0.35, 0.40),
       **{"yield": (55, 80)}, uts=(50, 80), elongation=(2, 6),
       toughness=(0.7, 1.6), conductivity=(0.17, 0.25),
       specific_heat=(1450, 1550), expansion=(65, 80), service=(60, 90)),
    _m("Epoxy", "polymer", "ISO 3673",
       density=(1110, 1400), youngs=(2.4, 4.0), **{"yield": (35, 90)},
       uts=(45, 90), elongation=(1, 6), toughness=(0.4, 2.2),
       conductivity=(0.18, 0.50), specific_heat=(1400, 1600),
       expansion=(55, 90), service=(100, 160)),
    _m("Natural rubber", "polymer", "ISO 2303",
       density=(920, 960), youngs=(0.0015, 0.0025),
       poisson=(0.490, 0.499), uts=(20, 30), elongation=(500, 850),
       conductivity=(0.10, 0.15), specific_heat=(1800, 2000),
       expansion=(150, 450), service=(70, 100)),

    _m("ABS", "polymer", "ISO 2580",
       density=(1020, 1080), youngs=(1.9, 2.9), poisson=(0.36, 0.40),
       **{"yield": (28, 55)}, uts=(30, 55), elongation=(5, 40),
       toughness=(1.2, 4.3), conductivity=(0.17, 0.25),
       specific_heat=(1400, 1600), expansion=(80, 110), service=(70, 95)),
    _m("Polystyrene", "polymer", "ISO 1622",
       density=(1030, 1060), youngs=(2.9, 3.5), poisson=(0.33, 0.38),
       **{"yield": (30, 55)}, uts=(35, 60), elongation=(1.2, 3.5),
       toughness=(0.7, 1.1), conductivity=(0.12, 0.17),
       specific_heat=(1200, 1400), expansion=(70, 100), service=(60, 80)),
    _m("PET", "polymer", "ISO 7792",
       density=(1290, 1400), youngs=(2.7, 4.1), poisson=(0.37, 0.44),
       **{"yield": (50, 75)}, uts=(50, 80), elongation=(30, 300),
       toughness=(4.5, 5.5), conductivity=(0.13, 0.25),
       specific_heat=(1100, 1300), expansion=(60, 80), service=(90, 115)),
    _m("Acetal, POM", "polymer", "ISO 9988",
       density=(1390, 1430), youngs=(2.5, 3.5), poisson=(0.35, 0.40),
       **{"yield": (48, 72)}, uts=(60, 75), elongation=(10, 75),
       toughness=(1.7, 4.2), conductivity=(0.22, 0.35),
       specific_heat=(1350, 1500), expansion=(90, 130), service=(85, 110)),
    _m("PEEK", "polymer", "ISO 29988",
       density=(1300, 1320), youngs=(3.5, 4.4), poisson=(0.36, 0.40),
       **{"yield": (90, 110)}, uts=(90, 115), elongation=(20, 50),
       toughness=(2.7, 4.5), conductivity=(0.24, 0.29),
       specific_heat=(1300, 1600), expansion=(45, 55), service=(240, 260)),
    _m("Phenolic", "polymer", "ISO 14526",
       density=(1240, 1320), youngs=(2.8, 4.8), poisson=(0.33, 0.40),
       **{"yield": (27, 50)}, uts=(35, 60), elongation=(0.5, 2.0),
       toughness=(0.7, 1.6), conductivity=(0.20, 0.50),
       specific_heat=(1400, 1700), expansion=(30, 60), service=(140, 180)),
    _m("Polyurethane elastomer", "polymer", "ISO 37",
       density=(1020, 1250), youngs=(0.002, 0.03), poisson=(0.48, 0.50),
       **{"yield": (2, 25)}, uts=(20, 55), elongation=(300, 700),
       toughness=(0.05, 0.5), conductivity=(0.20, 0.30),
       specific_heat=(1500, 1800), expansion=(150, 200), service=(70, 100)),
    _m("Silicone elastomer", "polymer", "ISO 3302",
       density=(1100, 1300), youngs=(0.001, 0.01), poisson=(0.48, 0.50),
       **{"yield": (2, 8)}, uts=(4, 10), elongation=(200, 800),
       toughness=(0.03, 0.2), conductivity=(0.20, 0.35),
       specific_heat=(1200, 1500), expansion=(200, 300), service=(200, 250)),

    # -- ceramics and glasses ----------------------------------------------
    _m("Alumina", "ceramic", "ISO 6474",
       density=(3800, 3980), youngs=(330, 400), poisson=(0.21, 0.23),
       uts=(250, 400), toughness=(3.3, 5.0), conductivity=(25, 35),
       specific_heat=(790, 880), expansion=(7.0, 8.5),
       melting=(2000, 2100), service=(1400, 1700)),
    _m("Silicon carbide", "ceramic", "manufacturer data",
       density=(3000, 3200), youngs=(400, 450), poisson=(0.15, 0.18),
       uts=(300, 600), toughness=(3.0, 4.5), conductivity=(80, 150),
       specific_heat=(650, 750), expansion=(4.0, 5.0),
       melting=(2500, 2800), service=(1300, 1600)),
    _m("Soda-lime glass", "ceramic", "EN 572",
       density=(2440, 2490), youngs=(68, 72), poisson=(0.21, 0.23),
       uts=(30, 90), toughness=(0.55, 0.75), conductivity=(0.9, 1.3),
       specific_heat=(800, 880), expansion=(8.5, 9.5),
       melting=(700, 900), service=(400, 500)),
    _m("Concrete", "ceramic", "EN 206",
       density=(2300, 2600), youngs=(25, 40), poisson=(0.18, 0.22),
       uts=(1, 5), toughness=(0.35, 0.45), conductivity=(0.8, 2.0),
       specific_heat=(850, 1000), expansion=(10, 13), service=(400, 500)),

    _m("Silicon nitride", "ceramic", "ISO 24370",
       density=(3150, 3300), youngs=(280, 320), shear=(110, 130),
       poisson=(0.22, 0.28), uts=(400, 900), toughness=(4, 8),
       conductivity=(22, 30), specific_heat=(670, 800),
       expansion=(3.0, 3.6), melting=(1800, 1900), service=(1000, 1300)),
    _m("Zirconia", "ceramic", "ISO 13356",
       density=(5700, 6100), youngs=(190, 220), shear=(74, 88),
       poisson=(0.27, 0.32), uts=(500, 1200), toughness=(6, 12),
       conductivity=(1.5, 3.0), specific_heat=(420, 500),
       expansion=(9.5, 11.0), melting=(2650, 2750), service=(900, 1400)),
    _m("Tungsten carbide", "ceramic", "ISO 4499 (WC-Co hardmetal)",
       density=(13800, 15200), youngs=(500, 650), shear=(200, 260),
       poisson=(0.20, 0.24), uts=(1000, 2500), toughness=(9, 18),
       conductivity=(60, 100), specific_heat=(180, 250),
       expansion=(4.5, 6.0), melting=(2600, 2870), service=(800, 1100)),
    _m("Borosilicate glass", "ceramic", "ISO 3585",
       density=(2200, 2300), youngs=(60, 68), shear=(25, 28),
       poisson=(0.19, 0.22), uts=(30, 90), toughness=(0.5, 0.9),
       conductivity=(1.0, 1.3), specific_heat=(750, 850),
       expansion=(3.2, 3.5), melting=(800, 850), service=(400, 500)),
    _m("Brick", "ceramic", "EN 771-1",
       density=(1700, 2200), youngs=(10, 25), poisson=(0.10, 0.20),
       uts=(1.5, 6.0), toughness=(0.5, 1.2), conductivity=(0.5, 1.2),
       specific_heat=(750, 950), expansion=(5, 8), melting=(1300, 1600),
       service=(700, 1000)),
    _m("Stone, granite", "ceramic", "EN 1936",
       density=(2600, 2800), youngs=(40, 70), poisson=(0.20, 0.30),
       uts=(5, 15), toughness=(0.6, 1.5), conductivity=(2.0, 3.5),
       specific_heat=(800, 900), expansion=(6, 9), melting=(1200, 1300),
       service=(500, 800)),

    # -- composites and natural --------------------------------------------
    _m("CFRP, quasi-isotropic", "composite", "manufacturer data",
       density=(1500, 1600), youngs=(50, 80), uts=(550, 1050),
       toughness=(6.1, 88), conductivity=(1.3, 2.6),
       specific_heat=(900, 1000), expansion=(1, 4), service=(140, 220)),
    _m("GFRP", "composite", "manufacturer data",
       density=(1750, 1970), youngs=(15, 28), uts=(110, 192),
       toughness=(7, 23), conductivity=(0.40, 0.55),
       specific_heat=(1000, 1200), expansion=(8, 14), service=(140, 220)),
    _m("Softwood, along the grain", "natural", "EN 338",
       density=(350, 700), youngs=(8, 15), uts=(30, 90),
       toughness=(5, 9), conductivity=(0.11, 0.17),
       specific_heat=(1600, 1700), expansion=(2, 11), service=(100, 140)),
    _m("Rigid polymer foam", "foam", "manufacturer data",
       density=(36, 70), youngs=(0.023, 0.080), uts=(0.4, 1.2),
       toughness=(0.02, 0.08), conductivity=(0.027, 0.038),
       specific_heat=(1200, 1800), expansion=(20, 80), service=(80, 110)),
    _m("Aramid-epoxy, unidirectional", "composite",
       "manufacturer data (Kevlar 49 / epoxy, 60% fibre)",
       density=(1300, 1420), youngs=(60, 85), poisson=(0.32, 0.36),
       uts=(1200, 1700), elongation=(1.5, 2.2), toughness=(20, 40),
       conductivity=(0.5, 1.5), specific_heat=(1000, 1500),
       expansion=(1, 3), service=(150, 180)),
    _m("Aluminium-SiC composite", "composite",
       "manufacturer data (20-30% SiC particulate)",
       density=(2760, 2950), youngs=(95, 135), shear=(36, 52),
       poisson=(0.29, 0.32), **{"yield": (250, 450)},
       uts=(300, 550), elongation=(1, 6), toughness=(12, 22),
       conductivity=(140, 190), specific_heat=(800, 900),
       expansion=(13, 18), melting=(560, 640), service=(200, 300)),
    _m("Softwood, across the grain", "natural", "EN 338, EN 1995-1-1",
       density=(350, 700), youngs=(0.4, 1.0), poisson=(0.30, 0.50),
       uts=(1.5, 6.0), elongation=(1, 3), toughness=(0.3, 0.8),
       conductivity=(0.10, 0.16), specific_heat=(1600, 1700),
       expansion=(30, 60), service=(100, 140)),
    _m("Hardwood, along the grain", "natural", "EN 338, EN 1995-1-1",
       density=(600, 900), youngs=(9, 16), poisson=(0.30, 0.45),
       uts=(60, 130), elongation=(1, 3), toughness=(5, 12),
       conductivity=(0.15, 0.25), specific_heat=(1600, 1700),
       expansion=(3, 6), service=(100, 140)),
    _m("Plywood", "natural", "EN 636",
       density=(450, 700), youngs=(5, 12), poisson=(0.25, 0.40),
       uts=(25, 60), elongation=(1, 3), toughness=(3, 8),
       conductivity=(0.12, 0.18), specific_heat=(1600, 1700),
       expansion=(6, 12), service=(90, 130)),
    _m("Bamboo", "natural", "ISO 22157",
       density=(600, 900), youngs=(10, 20), poisson=(0.25, 0.40),
       uts=(100, 250), elongation=(1, 3), toughness=(4, 10),
       conductivity=(0.15, 0.25), specific_heat=(1600, 1700),
       expansion=(4, 8), service=(90, 130)),
    _m("Cork", "natural", "EN 12104",
       density=(120, 240), youngs=(0.013, 0.05), poisson=(0.00, 0.05),
       uts=(0.5, 2.5), elongation=(10, 40), toughness=(0.05, 0.15),
       conductivity=(0.035, 0.05), specific_heat=(1700, 2000),
       expansion=(130, 180), service=(90, 120)),
    _m("Flexible polymer foam", "foam", "EN ISO 845 (open-cell PU)",
       density=(16, 80), youngs=(0.0001, 0.003), poisson=(0.10, 0.35),
       uts=(0.02, 0.3), elongation=(50, 200), toughness=(0.005, 0.05),
       conductivity=(0.035, 0.05), specific_heat=(1500, 1800),
       expansion=(100, 200), service=(80, 110)),
    _m("Aluminium foam", "foam", "manufacturer data (closed cell)",
       density=(150, 700), youngs=(0.3, 6.0), poisson=(0.30, 0.35),
       **{"yield": (0.8, 20)}, uts=(1.2, 25), elongation=(1, 10),
       toughness=(0.3, 2.0), conductivity=(3, 30),
       specific_heat=(880, 940), expansion=(20, 24), melting=(560, 660),
       service=(150, 250)),
]


GRADES = [
    _m("S275 steel", "metal", "EN 10025-2", grade=True,
       condition="hot rolled, thickness up to 16 mm",
       density=7850, youngs=210, shear=81, poisson=0.30,
       **{"yield": 275}, uts=(410, 560), elongation=23,
       toughness=(50, 150), conductivity=50, specific_heat=470,
       expansion=12, melting=(1425, 1520), service=400),
    _m("S355 steel", "metal", "EN 10025-2", grade=True,
       condition="hot rolled, thickness up to 16 mm",
       density=7850, youngs=210, shear=81, poisson=0.30,
       **{"yield": 355}, uts=(470, 630), elongation=22,
       toughness=(50, 150), conductivity=45, specific_heat=470,
       expansion=12, melting=(1425, 1520), service=400),
    _m("304 stainless", "metal", "EN 10088-2 / ASTM A240", grade=True,
       condition="annealed",
       density=8000, youngs=193, shear=77, poisson=0.29,
       **{"yield": (205, 310)}, uts=(515, 620), elongation=(40, 60),
       toughness=(100, 150), conductivity=16.2, specific_heat=500,
       expansion=17.3, melting=(1400, 1450), service=870),
    _m("316L stainless", "metal", "EN 10088-2 / ASTM A240", grade=True,
       condition="annealed",
       density=8000, youngs=193, shear=77, poisson=0.29,
       **{"yield": (170, 290)}, uts=(485, 620), elongation=40,
       toughness=(100, 150), conductivity=16.3, specific_heat=500,
       expansion=16.0, melting=(1375, 1400), service=870),
    _m("6082-T6 aluminium", "metal", "EN 755-2", grade=True,
       condition="solution treated and artificially aged",
       density=2700, youngs=70, shear=26, poisson=0.33,
       **{"yield": (255, 260)}, uts=(290, 310), elongation=(8, 10),
       toughness=(25, 32), conductivity=(170, 180), specific_heat=900,
       expansion=23.4, melting=(555, 650), service=150),
    _m("6061-T6 aluminium", "metal", "ASTM B221", grade=True,
       condition="solution treated and artificially aged",
       density=2700, youngs=69, shear=26, poisson=0.33,
       **{"yield": (240, 276)}, uts=(290, 310), elongation=(8, 12),
       toughness=(29, 32), conductivity=167, specific_heat=896,
       expansion=23.6, melting=(582, 652), service=150),
    _m("7075-T6 aluminium", "metal", "ASTM B209", grade=True,
       condition="solution treated and artificially aged",
       density=2810, youngs=71.7, shear=26.9, poisson=0.33,
       **{"yield": (460, 505)}, uts=(524, 572), elongation=(5, 11),
       toughness=(23, 26), conductivity=130, specific_heat=960,
       expansion=23.6, melting=(477, 635), service=120),
    _m("5083-H111 aluminium", "metal", "EN 485-2", grade=True,
       condition="as fabricated",
       density=2660, youngs=71, shear=26.4, poisson=0.33,
       **{"yield": (125, 145)}, uts=(275, 350), elongation=(12, 16),
       toughness=(28, 43), conductivity=117, specific_heat=900,
       expansion=24.2, melting=(570, 640), service=150),
    _m("Ti-6Al-4V", "metal", "ASTM B265 grade 5", grade=True,
       condition="annealed",
       density=4430, youngs=(110, 114), shear=(41, 44), poisson=0.34,
       **{"yield": (830, 910)}, uts=(900, 950), elongation=(10, 14),
       toughness=75, conductivity=6.7, specific_heat=526,
       expansion=8.6, melting=(1600, 1660), service=400),
    _m("C101 copper", "metal", "EN 13601", grade=True,
       condition="from annealed to hard drawn",
       density=8940, youngs=117, shear=44, poisson=0.34,
       **{"yield": (60, 350)}, uts=(220, 390), elongation=(4, 45),
       conductivity=(388, 391), specific_heat=385, expansion=17.0,
       melting=1083, service=200),
    _m("Grey cast iron, EN-GJL-250", "metal", "EN 1561", grade=True,
       condition="as cast",
       density=7200, youngs=(110, 130), poisson=0.26,
       uts=(250, 350), elongation=(0.3, 0.8), toughness=(10, 20),
       conductivity=(45, 50), specific_heat=500, expansion=11,
       melting=(1150, 1200), service=350),
]


def all_materials() -> list:
    return CLASSES + GRADES


def find(name: str):
    """A material by name, whichever level it is at."""
    wanted = (name or "").strip().lower()
    for material in all_materials():
        if material.name.lower() == wanted:
            return material
    return None


def names(grades=None) -> list:
    """Every name, or only the classes, or only the grades."""
    if grades is None:
        found = all_materials()
    else:
        found = [m for m in all_materials() if m.grade == grades]
    return [material.name for material in found]


def with_property(name: str, grades=None) -> list:
    """Every material that records a given property."""
    return [material for material in all_materials()
            if material.has(name) and (grades is None
                                       or material.grade == grades)]


def value_in(material, prop: str, unit: str) -> float:
    """One property of one material, in whatever unit is being asked for.

    The database keeps each property in the unit it is normally quoted in
    - a modulus in GPa, a strength in N/mm2 - and a formula asks in
    whatever unit that formula is written in, which is usually pascals.
    Converting here rather than storing a second copy means the two can
    never drift apart.
    """
    if isinstance(material, str):
        found = find(material)
        if found is None:
            raise MaterialError(f"No material called {material!r}.")
        material = found
    if prop not in PROPERTIES:
        raise MaterialError(f"{prop!r} is not a material property.")
    held = PROPERTIES[prop][1]
    value = material.typical(prop)
    if not unit or not held or unit == held:
        return value
    return float(units.convert(value, held, unit))


def fill(material, variables) -> dict:
    """Every slot in *variables* this material can fill, in the slot's unit.

    A material that does not record a property fills nothing for it,
    rather than filling it with the middle of the ones that do.
    """
    if isinstance(material, str):
        material = find(material)
    if material is None:
        return {}
    filled = {}
    for variable in variables:
        prop = getattr(variable, "material", "")
        if prop and material.has(prop):
            filled[variable.symbol] = value_in(material, prop, variable.unit)
    return filled


def can_fill(variables) -> list:
    """The material properties a set of slots between them ask for."""
    wanted = []
    for variable in variables:
        prop = getattr(variable, "material", "")
        if prop and prop not in wanted:
            wanted.append(prop)
    return wanted


def knowing(variables, grades=None) -> list:
    """The materials that can fill at least one of these slots."""
    wanted = can_fill(variables)
    if not wanted:
        return []
    return [material.name for material in all_materials()
            if (grades is None or material.grade == grades)
            and any(material.has(prop) for prop in wanted)]


# --------------------------------------------------------------------------
# Checking it
# --------------------------------------------------------------------------
#: How far the elastic constants may be from G = E/2(1+nu). The three are
#: measured separately and quoted rounded, so a few per cent is expected.
ELASTIC_TOLERANCE = 0.06

#: Volumetric heat capacity, in J/(m^3 K). Nearly every solid falls between
#: these, which makes it a real check: a density and a specific heat that
#: disagree with each other show up here.
#:
#: It is a check on material, though, and a cubic metre of a porous thing is
#: not a cubic metre of material. Softwood is about a third cellulose and two
#: thirds air and lands at 0.82, which is a third of the way into the band
#: rather than outside it, and a foam is further down again for the same
#: reason. Those families are exempt rather than the band being widened
#: until nothing fails, because widening it would remove the check.
HEAT_CAPACITY_BAND = (1.0e6, 4.5e6)

#: The families that are mostly air by volume.
POROUS = ("foam", "natural")

#: Thermal diffusivity, k/(rho c), in m^2/s.
DIFFUSIVITY_BAND = (1e-8, 3e-4)


def reconcile() -> list:
    """Every relation that has to hold, checked on every material.

    Returns a line per failure, worst first, and nothing when the data is
    self-consistent. Property data cannot be checked the way a section can -
    a yield strength is not derivable from anything - but these four
    relations catch a transcription error in several properties at once,
    which is what most of them would be.
    """
    off = []
    for material in all_materials():
        name = material.name
        values = material.values

        for key, (low, high) in values.items():
            if high < low:
                off.append((name, f"{key} runs backwards: {low} to {high}"))

        if {"youngs", "shear", "poisson"} <= set(values):
            modulus = material.typical("youngs")
            shear = material.typical("shear")
            ratio = material.typical("poisson")
            expected = modulus / (2.0 * (1.0 + ratio))
            error = abs(shear - expected) / expected
            if error > ELASTIC_TOLERANCE:
                off.append((name, f"G = E/2(1+nu) gives {expected:.1f} GPa "
                                  f"but {shear:.1f} is recorded "
                                  f"({error:.1%} out)"))

        if {"yield", "uts"} <= set(values):
            if values["yield"][0] > values["uts"][1]:
                off.append((name, "the yield strength is above the tensile "
                                  "strength"))

        if {"service", "melting"} <= set(values):
            if values["service"][1] > values["melting"][0]:
                off.append((name, "the service temperature reaches the "
                                  "melting point"))

        if {"density", "specific_heat"} <= set(values):
            capacity = material.typical("density") * \
                material.typical("specific_heat")
            low, high = HEAT_CAPACITY_BAND
            if material.family not in POROUS and not low <= capacity <= high:
                off.append((name, f"rho c is {capacity / 1e6:.2f} MJ/m3K, "
                                  f"outside the band every solid is in"))
            if "conductivity" in values:
                spread = material.typical("conductivity") / capacity
                low, high = DIFFUSIVITY_BAND
                if not low <= spread <= high:
                    off.append((name, f"thermal diffusivity is "
                                      f"{spread:.2e} m2/s, outside the band"))
    return off

# --------------------------------------------------------------------------
# Performance indices
# --------------------------------------------------------------------------
def _indices() -> list:
    """The indices, derived. Imported here rather than at the top of the
    file because `indices` needs `materials` for nothing at all and this
    keeps it that way round: properties know nothing about what anybody
    wants to make out of them.
    """
    from .indices import entries
    return entries()


class _Indices(list):
    """The derived indices, worked out the first time anybody looks.

    A list, because every caller treats it as one and there is no reason
    to make them stop. Filled late, because deriving thirteen indices is
    a second of SymPy and the app should not spend it before the window
    is up if nobody opens a chart.
    """

    def _fill(self):
        if not list.__len__(self):
            self.extend(_indices())
        return self

    def __iter__(self):
        return list.__iter__(self._fill())

    def __len__(self):
        return list.__len__(self._fill())

    def __getitem__(self, at):
        return list.__getitem__(self._fill(), at)


#: (what it is for, x property, y property, exponent on y, exponent on x,
#: how it is written).
#:
#: The index is y^ny / x^nx, and it is maximised. On logarithmic axes a
#: contour of it is a straight line of slope nx/ny, so choosing a material
#: is laying that edge on the chart and taking what is above it.
#:
#: Derived in `core.indices` from a statement of the job rather than
#: written out here - see that file for why the exponent is the part worth
#: computing.
INDICES = _Indices()


def index_value(material: "Material", index) -> float:
    """How well a material scores on an index, at its typical properties.

    Returns nought when it has not got both properties, so a material with
    no yield strength recorded does not come out infinitely good at a
    strength index.
    """
    _label, across, up, power_up, power_across, _written = index
    if not (material.has(across) and material.has(up)):
        return 0.0
    bottom = material.typical(across)
    if bottom <= 0:
        return 0.0
    return material.typical(up) ** power_up / bottom ** power_across


def ranked(index, grades=None) -> list:
    """Every material that has both properties, best first."""
    found = [(index_value(material, index), material)
             for material in all_materials()
             if (grades is None or material.grade == grades)]
    found = [(value, material) for value, material in found if value > 0]
    found.sort(key=lambda pair: -pair[0])
    return found


def guideline(index, through, span) -> tuple:
    """A contour of the index passing through one material.

    (x values, y values) for a straight line on logarithmic axes. Its slope
    is the ratio of the two exponents and nothing else - the material only
    decides where it sits, not how it leans.
    """
    _label, across, up, power_up, power_across, _written = index
    slope = power_across / power_up
    middle_x = through.typical(across)
    middle_y = through.typical(up)
    low, high = span
    return ([low, high],
            [middle_y * (low / middle_x) ** slope,
             middle_y * (high / middle_x) ** slope])
