"""Dimensions for the sections people actually order, and a check on them.

A table of numbers in a program is a liability. Nobody can see where it came
from, it goes out of date quietly, and a single transposed digit reads like
an answer forever. This one carries its own check: beside the dimensions
sits what the section tables give for the area and the two second moments,
and :func:`reconcile` works those out from the dimensions and compares.

Five dimensions producing three published quantities at once is a tight
constraint. A mistyped web thickness moves the area; a mistyped flange moves
Ixx and Iyy by different amounts. So a row that reconciles is a row whose
dimensions are right, and a row that does not is removed rather than
shipped. The test suite runs the whole table.

What the check cannot do is tell you the name on the row is the right name
for those dimensions. It says the geometry is self-consistent, not that
anybody has looked it up correctly. Check the designation against your own
tables before you put it in a calculation that matters - and the properties
you get here are worked from the dimensions in any case, so a section that
is not in this list is served exactly as well by typing its dimensions in.
"""

from __future__ import annotations

from . import sections

#: How far a row may be from its tabulated properties before it is wrong.
#: The published figures are rounded, and the real section has toe radii
#: this does not model, so a fraction of a percent is expected and two is
#: not.
TOLERANCE = 0.02

#: (designation, profile, dimensions, area cm^2, Ixx cm^4, Iyy cm^4).
#:
#: Dimensions in millimetres, in the order the profile builder wants them:
#: I sections, channels and tees d, b, tw, tf, r; angles a, b, t, r; tubes
#: d, t.
#:
#: Two rows have been taken out of this list rather than shipped. A
#: 300x90x41 PFC came out 12% low on Ixx while its area agreed, and a
#: 219.1x8.0 CHS was 2% out on a second moment that is a closed form with
#: nothing in it to be 2% wrong about. In both cases something in the row
#: was wrong and there is no way to tell which number from here, so neither
#: is here. Both sections still work perfectly well by typing their
#: dimensions in.
TABLE = [
    # -- universal beams ---------------------------------------------------
    ("127x76x13 UB", "I section", (127.0, 76.0, 4.0, 7.6, 7.6),
     16.5, 473.0, 55.7),
    ("152x89x16 UB", "I section", (152.4, 88.7, 4.5, 7.7, 7.6),
     20.3, 834.0, 89.8),
    ("178x102x19 UB", "I section", (177.8, 101.2, 4.8, 7.9, 7.6),
     24.3, 1360.0, 137.0),
    ("203x102x23 UB", "I section", (203.2, 101.8, 5.4, 9.3, 7.6),
     29.4, 2105.0, 164.0),
    ("203x133x25 UB", "I section", (203.2, 133.2, 5.7, 7.8, 7.6),
     32.0, 2340.0, 308.0),
    ("203x133x30 UB", "I section", (206.8, 133.9, 6.4, 9.6, 7.6),
     38.2, 2896.0, 385.0),
    ("254x102x28 UB", "I section", (260.4, 102.2, 6.3, 10.0, 7.6),
     36.1, 4005.0, 179.0),
    ("254x146x31 UB", "I section", (251.4, 146.1, 6.0, 8.6, 7.6),
     39.7, 4413.0, 448.0),
    ("254x146x37 UB", "I section", (256.0, 146.4, 6.3, 10.9, 7.6),
     47.2, 5537.0, 571.0),
    ("305x102x25 UB", "I section", (305.1, 101.6, 5.8, 7.0, 7.6),
     31.6, 4455.0, 123.0),
    ("305x165x40 UB", "I section", (303.4, 165.0, 6.0, 10.2, 8.9),
     51.3, 8503.0, 764.0),
    ("356x171x51 UB", "I section", (355.0, 171.5, 7.4, 11.5, 10.2),
     64.9, 14140.0, 968.0),
    ("406x178x60 UB", "I section", (406.4, 177.9, 7.9, 12.8, 10.2),
     76.5, 21600.0, 1203.0),
    ("457x191x74 UB", "I section", (457.0, 190.4, 9.0, 14.5, 10.2),
     94.6, 33320.0, 1671.0),
    ("533x210x92 UB", "I section", (533.1, 209.3, 10.1, 15.6, 12.7),
     117.0, 55230.0, 2389.0),

    # -- universal columns -------------------------------------------------
    ("152x152x23 UC", "I section", (152.4, 152.2, 5.8, 6.8, 7.6),
     29.2, 1250.0, 400.0),
    ("152x152x30 UC", "I section", (157.6, 152.9, 6.5, 9.4, 7.6),
     38.3, 1748.0, 560.0),
    ("152x152x37 UC", "I section", (161.8, 154.4, 8.0, 11.5, 7.6),
     47.1, 2210.0, 706.0),
    ("203x203x46 UC", "I section", (203.2, 203.6, 7.2, 11.0, 10.2),
     58.7, 4568.0, 1548.0),
    ("203x203x60 UC", "I section", (209.6, 205.8, 9.4, 14.2, 10.2),
     76.4, 6125.0, 2065.0),
    ("254x254x73 UC", "I section", (254.1, 254.6, 8.6, 14.2, 12.7),
     93.1, 11410.0, 3908.0),
    ("254x254x89 UC", "I section", (260.3, 256.3, 10.3, 17.3, 12.7),
     113.0, 14270.0, 4857.0),
    ("305x305x97 UC", "I section", (307.9, 305.3, 9.9, 15.4, 15.2),
     123.0, 22250.0, 7308.0),
    ("305x305x118 UC", "I section", (314.5, 307.4, 12.0, 18.7, 15.2),
     150.0, 27670.0, 9059.0),

    # -- parallel flange channels ------------------------------------------
    ("100x50x10 PFC", "channel", (100.0, 50.0, 5.0, 8.5, 9.0),
     13.0, 208.0, 32.3),
    ("125x65x15 PFC", "channel", (125.0, 65.0, 5.5, 9.5, 12.0),
     19.0, 483.0, 80.0),
    ("150x75x18 PFC", "channel", (150.0, 75.0, 5.5, 10.0, 12.0),
     23.0, 861.0, 131.0),
    ("180x75x20 PFC", "channel", (180.0, 75.0, 6.0, 10.5, 12.0),
     25.9, 1370.0, 146.0),
    ("200x75x23 PFC", "channel", (200.0, 75.0, 6.0, 12.5, 12.0),
     29.9, 1960.0, 170.0),
    ("200x90x30 PFC", "channel", (200.0, 90.0, 7.0, 14.0, 12.0),
     38.0, 2520.0, 314.0),
    ("230x75x26 PFC", "channel", (230.0, 75.0, 6.5, 12.5, 12.0),
     32.7, 2750.0, 181.0),
    ("260x75x28 PFC", "channel", (260.0, 75.0, 7.0, 12.0, 12.0),
     35.1, 3620.0, 185.0),

    # -- equal angles ------------------------------------------------------
    ("50x50x6 EA", "angle", (50.0, 50.0, 6.0, 7.0), 5.69, 12.8, 12.8),
    ("60x60x6 EA", "angle", (60.0, 60.0, 6.0, 8.0), 6.91, 22.8, 22.8),
    ("70x70x7 EA", "angle", (70.0, 70.0, 7.0, 9.0), 9.40, 42.3, 42.3),
    ("75x75x8 EA", "angle", (75.0, 75.0, 8.0, 9.0), 11.4, 59.1, 59.1),
    ("80x80x8 EA", "angle", (80.0, 80.0, 8.0, 10.0), 12.3, 72.2, 72.2),
    ("90x90x10 EA", "angle", (90.0, 90.0, 10.0, 11.0), 17.1, 127.0, 127.0),
    ("100x100x10 EA", "angle", (100.0, 100.0, 10.0, 12.0),
     19.2, 177.0, 177.0),
    ("100x100x12 EA", "angle", (100.0, 100.0, 12.0, 12.0),
     22.7, 207.0, 207.0),
    ("120x120x12 EA", "angle", (120.0, 120.0, 12.0, 13.0),
     27.5, 368.0, 368.0),
    ("150x150x15 EA", "angle", (150.0, 150.0, 15.0, 16.0),
     43.0, 898.0, 898.0),

    # -- unequal angles, the long leg up -----------------------------------
    ("100x75x10 UA", "angle", (100.0, 75.0, 10.0, 10.0), 16.6, 162.0, 77.6),

    # -- circular hollow ---------------------------------------------------
    ("48.3x3.2 CHS", "circular hollow", (48.3, 3.2), 4.53, 11.6, 11.6),
    ("60.3x5.0 CHS", "circular hollow", (60.3, 5.0), 8.69, 33.5, 33.5),
    ("88.9x5.0 CHS", "circular hollow", (88.9, 5.0), 13.2, 116.0, 116.0),
    ("114.3x5.0 CHS", "circular hollow", (114.3, 5.0), 17.2, 257.0, 257.0),
    ("168.3x6.3 CHS", "circular hollow", (168.3, 6.3),
     32.1, 1053.0, 1053.0),
]


def names() -> list:
    """Every designation in the table, in the order it is listed."""
    return [row[0] for row in TABLE]


def find(designation: str):
    """(profile, dimensions) for a designation, or None if it is not here."""
    wanted = (designation or "").strip().lower()
    for name, profile, dimensions, *_ in TABLE:
        if name.lower() == wanted:
            return profile, dimensions
    return None


def build(designation: str) -> sections.Section:
    """The section for a designation, worked out from its dimensions."""
    found = find(designation)
    if found is None:
        raise sections.SectionError(
            f"{designation} is not in the table. Its dimensions can be typed "
            f"in instead - that is what happens to the ones that are.")
    profile, dimensions = found
    builder = sections.PROFILES[profile][0]
    return builder(*dimensions, name=designation)


def reconcile() -> list:
    """Work every row out from its dimensions and compare with the table.

    Returns a row per section: (designation, what, computed, tabulated,
    relative error), worst first. Empty means every row agrees.
    """
    off = []
    for name, profile, dimensions, area, ixx, iyy in TABLE:
        builder = sections.PROFILES[profile][0]
        got = builder(*dimensions).properties()
        for what, mine, theirs in (("area", got.area / 100.0, area),
                                   ("Ixx", got.ixx / 1e4, ixx),
                                   ("Iyy", got.iyy / 1e4, iyy)):
            error = abs(mine - theirs) / theirs
            if error > TOLERANCE:
                off.append((name, what, mine, theirs, error))
    return sorted(off, key=lambda row: -row[-1])


def agreement() -> list:
    """How closely each row agrees, worst first. For looking at."""
    found = []
    for name, profile, dimensions, area, ixx, iyy in TABLE:
        builder = sections.PROFILES[profile][0]
        got = builder(*dimensions).properties()
        worst = max(abs(got.area / 100.0 - area) / area,
                    abs(got.ixx / 1e4 - ixx) / ixx,
                    abs(got.iyy / 1e4 - iyy) / iyy)
        found.append((name, worst))
    return sorted(found, key=lambda row: -row[1])
