"""Ductwork, fans and sheet metal - the trade formulas.

The bend maths matches the K-factor method the flat-pattern generator in the
Sheet.Developments project uses, deliberately: if the two disagreed, a blank
cut from a number worked out here would not fold to the size the drawing
says. The outside setback is ``(R + T) tan(a/2)`` with no ``- R`` on the end,
which is the correction that project had to make after wrong blanks reached
the shop floor.

Air-side figures are the standard textbook forms at sea level. Where a
constant folds in a density - the 1.2 in the sensible heat load - it is
written out as a density instead, so the assumption is on the screen rather
than buried in a number.
"""

from ..model import make_builder

f = make_builder("HVAC & Sheet Metal")

FORMULAS = [
    # -- air in ducts ---------------------------------------------------
    f("duct_flow", "Duct volume flow", "Airflow", "Q = A*v",
      {"Q": ("Volume flow", "m^3/s", "0.5"),
       "A": ("Duct cross-sectional area", "m^2", "0.09"),
       "v": ("Mean air velocity", "m/s", "5")},
      notes="The continuity equation, in the form a duct is sized with.",
      assumptions="Uniform velocity across the section; incompressible.",
      tags=("duct", "hvac", "airflow", "sizing")),

    f("velocity_pressure", "Velocity pressure", "Airflow",
      "pv = rho*v^2/2",
      {"pv": ("Velocity pressure", "Pa", "15"),
       "rho": ("Air density", "kg/m^3", "1.2"),
       "v": ("Air velocity", "m/s", "5")},
      notes="What a pitot tube reads. At 1.2 kg/m^3 this is about 0.6 v^2.",
      assumptions="Standard air, 20 C at sea level, 1.2 kg/m^3.",
      tags=("duct", "hvac", "pitot", "velocity pressure")),

    f("duct_hydraulic_diameter", "Hydraulic diameter", "Duct sizing",
      "Dh = 4*A/P",
      {"Dh": ("Hydraulic diameter", "m", "0.3"),
       "A": ("Cross-sectional area", "m^2", "0.09"),
       "P": ("Wetted perimeter", "m", "1.2")},
      notes="The diameter a non-round duct behaves like for friction.",
      tags=("duct", "hvac", "sizing")),

    f("rect_aspect_ratio", "Duct aspect ratio", "Duct sizing", "AR = a/b",
      {"AR": ("Aspect ratio", "-", "1.5"),
       "a": ("Long side", "m", "0.45"), "b": ("Short side", "m", "0.3")},
      notes="Above about 4:1 the extra friction and metal stop being worth "
            "the saved depth.",
      tags=("duct", "hvac", "sheet", "sizing")),

    f("duct_friction", "Duct pressure drop (Darcy-Weisbach)", "Airflow",
      "dp = fD*L*rho*v^2/(2*D)",
      {"dp": ("Pressure drop", "Pa", "25"),
       "fD": ("Darcy friction factor", "-", "0.02"),
       "L": ("Duct length", "m", "10"),
       "rho": ("Air density", "kg/m^3", "1.2"),
       "v": ("Mean velocity", "m/s", "5"),
       "D": ("Hydraulic diameter", "m", "0.3")},
      assumptions="Fully developed turbulent flow; use the hydraulic "
                  "diameter for a rectangular duct.",
      tags=("duct", "hvac", "pressure drop", "friction")),

    f("air_changes", "Air changes per hour", "Ventilation",
      "ACH = 3600*Q/V",
      {"ACH": ("Air changes per hour", "1/h", "6"),
       "Q": ("Supply volume flow", "m^3/s", "0.5"),
       "V": ("Room volume", "m^3", "300")},
      notes="The 3600 turns flow in m^3/s into an hourly count.",
      tags=("hvac", "ventilation", "air changes")),

    f("air_sensible_load", "Sensible heat carried by air", "Loads",
      "Qs = rho*cp*V*dT",
      {"Qs": ("Sensible heat rate", "W", "6000"),
       "rho": ("Air density", "kg/m^3", "1.2"),
       "cp": ("Specific heat of air", "J/(kg*K)", "1005"),
       "V": ("Volume flow", "m^3/s", "0.5"),
       "dT": ("Temperature rise", "K", "10")},
      notes="The familiar Q = 1.2 x flow x dT is this with the density and "
            "specific heat already multiplied out.",
      assumptions="Dry air at 1.2 kg/m^3; no moisture change, so this is "
                  "the sensible part only.",
      tags=("hvac", "load", "heating", "cooling")),

    # -- fans ------------------------------------------------------------
    f("fan_power", "Fan power", "Fans", "W = Q*dp/eta",
      {"W": ("Shaft power", "W", "750"),
       "Q": ("Volume flow", "m^3/s", "0.5"),
       "dp": ("Total pressure rise", "Pa", "600"),
       "eta": ("Fan total efficiency", "-", "0.65")},
      assumptions="Total pressure, not static. Efficiency includes the fan "
                  "only, not the motor or drive.",
      tags=("fan", "hvac", "power")),

    f("fan_law_flow", "Fan law - flow against speed", "Fans",
      "Q2 = Q1*N2/N1",
      {"Q2": ("New volume flow", "m^3/s"), "Q1": ("Original flow", "m^3/s"),
       "N2": ("New speed", "rev/min"), "N1": ("Original speed", "rev/min")},
      notes="Flow goes with speed.",
      assumptions="Same fan, same duct, same air density.",
      tags=("fan", "hvac", "fan laws")),

    f("fan_law_pressure", "Fan law - pressure against speed", "Fans",
      "p2 = p1*(N2/N1)^2",
      {"p2": ("New pressure", "Pa"), "p1": ("Original pressure", "Pa"),
       "N2": ("New speed", "rev/min"), "N1": ("Original speed", "rev/min")},
      notes="Pressure goes with the square of speed.",
      assumptions="Same fan, same duct, same air density.",
      tags=("fan", "hvac", "fan laws")),

    f("fan_law_power", "Fan law - power against speed", "Fans",
      "W2 = W1*(N2/N1)^3",
      {"W2": ("New power", "W"), "W1": ("Original power", "W"),
       "N2": ("New speed", "rev/min"), "N1": ("Original speed", "rev/min")},
      notes="Power goes with the cube of speed - halving the speed leaves an "
            "eighth of the power, which is where variable speed pays.",
      assumptions="Same fan, same duct, same air density.",
      tags=("fan", "hvac", "fan laws", "energy")),

    # -- sheet metal -----------------------------------------------------
    f("bend_allowance", "Bend allowance", "Sheet metal",
      "BA = theta*(R + K*T)",
      {"BA": ("Bend allowance - arc length of the neutral axis", "mm", "8.2"),
       "theta": ("Bend angle", "rad", "1.5708"),
       "R": ("Inside bend radius", "mm", "1.2"),
       "K": ("K-factor - neutral axis as a fraction of thickness", "-",
             "0.44"),
       "T": ("Material thickness", "mm", "1.2")},
      notes="The metal that goes round the corner. K = 0.44 is a common "
            "starting point for air bending mild steel; calibrate it against "
            "your own press brake before trusting it.",
      assumptions="Angle in radians - the bend angle is how far the metal "
                  "turns away from flat, so a square corner is pi/2.",
      tags=("sheet", "bend", "flat pattern", "k-factor", "press brake")),

    f("bend_setback", "Outside setback", "Sheet metal",
      "SSB = (R + T)*tan(theta/2)",
      {"SSB": ("Setback to the outside corner", "mm", "2.4"),
       "R": ("Inside bend radius", "mm", "1.2"),
       "T": ("Material thickness", "mm", "1.2"),
       "theta": ("Bend angle", "rad", "1.5708")},
      notes="From the bend tangent line to where the two outside faces "
            "would meet if the metal turned square - the corner a drawing "
            "dimensions to.",
      assumptions="There is no minus R on the end of this. A corner that is "
                  "not bent has no setback, and adding one gives a negative "
                  "bend deduction, which no fold has.",
      tags=("sheet", "bend", "setback", "flat pattern")),

    f("bend_deduction", "Bend deduction", "Sheet metal",
      "BD = 2*SSB - BA",
      {"BD": ("Bend deduction", "mm", "1.4"),
       "SSB": ("Outside setback", "mm", "2.4"),
       "BA": ("Bend allowance", "mm", "3.4")},
      notes="How much shorter the flat blank is than the two sharp-corner "
            "legs added together.",
      tags=("sheet", "bend", "flat pattern", "blank")),

    f("k_factor", "K-factor from the neutral axis", "Sheet metal",
      "K = d/T",
      {"K": ("K-factor", "-", "0.44"),
       "d": ("Neutral axis depth from the inside face", "mm", "0.53"),
       "T": ("Material thickness", "mm", "1.2")},
      notes="Where the metal is neither stretched nor compressed. Between "
            "0.3 and 0.5 in practice; it moves with tooling and material.",
      tags=("sheet", "bend", "k-factor")),

    f("sheet_weight", "Sheet weight", "Sheet metal", "m = rho*t*A",
      {"m": ("Mass", "kg", "9.4"),
       "rho": ("Material density", "kg/m^3", "7850"),
       "t": ("Thickness", "m", "0.0012"),
       "A": ("Sheet area", "m^2", "1")},
      notes="Mild steel is about 7850 kg/m^3, aluminium 2700, stainless "
            "8000. Watch the thickness unit - it is metres here, so 1.2 mm "
            "is 0.0012, or type 1.2 mm and it will convert.",
      tags=("sheet", "weight", "material", "estimating")),

    f("cylinder_blank", "Rolled cylinder blank length", "Sheet metal",
      "L = pi*(D + t)",
      {"L": ("Flat blank length", "mm", "957"),
       "D": ("Inside diameter", "mm", "300"),
       "t": ("Material thickness", "mm", "1.2")},
      notes="Round the neutral axis, taken at mid-thickness - which is what "
            "rolling does, unlike a press brake.",
      assumptions="Neutral axis at mid-thickness, so K = 0.5. For a tight "
                  "radius on thick plate use the bend allowance instead.",
      tags=("sheet", "duct", "blank", "rolling", "flat pattern")),
]
