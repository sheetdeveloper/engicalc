"""Chemical and process engineering."""

from ..model import make_builder

f = make_builder("Chemical & Process")

FORMULAS = [
    f("moles", "Moles from mass", "Stoichiometry", "n = m/M",
      {"n": ("Moles", "mol"), "m": ("Mass", "g"), "M": ("Molar mass", "g/mol")}),

    f("molarity", "Molar concentration", "Solutions", "Cm = n/Vs",
      {"Cm": ("Concentration", "mol/L"), "n": ("Moles of solute", "mol"),
       "Vs": ("Solution volume", "L")}),

    f("dilution", "Dilution relation", "Solutions", "C1*V1 = C2*V2",
      {"C1": ("Initial concentration", "mol/L"), "V1": ("Initial volume", "L"),
       "C2": ("Final concentration", "mol/L"), "V2": ("Final volume", "L")}),

    f("mass_balance", "Steady-state mass balance", "Balances",
      "min_ - mout = macc",
      {"min_": ("Mass in", "kg"), "mout": ("Mass out", "kg"),
       "macc": ("Accumulation", "kg", "0")}),

    f("first_order_reaction", "First-order reaction decay", "Kinetics",
      "C = C0*exp(-kr*t)",
      {"C": ("Concentration at time t", "mol/L"),
       "C0": ("Initial concentration", "mol/L"),
       "kr": ("Rate constant", "1/s"), "t": ("Time", "s")}),

    f("half_life", "First-order half life", "Kinetics", "thalf = log(2)/kr",
      {"thalf": ("Half life", "s"), "kr": ("Rate constant", "1/s")},
      notes="log() is the natural logarithm."),

    f("cstr_volume", "CSTR design equation", "Reactors",
      "Vr = Fa0*X/(-ra)",
      {"Vr": ("Reactor volume", "m^3"),
       "Fa0": ("Inlet molar flow of A", "mol/s"), "X": ("Conversion", "-"),
       "ra": ("Rate of reaction of A", "mol/(m^3*s)")}),

    f("residence_time", "Mean residence time", "Reactors", "tau = Vr/Q",
      {"tau": ("Residence time", "s"), "Vr": ("Reactor volume", "m^3"),
       "Q": ("Volumetric flow rate", "m^3/s")}),

    f("ph", "pH from hydrogen ion activity", "Solutions",
      "pH = -log(aH)/log(10)",
      {"pH": ("pH", "-"), "aH": ("Hydrogen ion concentration", "mol/L")}),

    f("raoult", "Raoult's law", "Separations", "pi_p = xi*psat",
      {"pi_p": ("Partial pressure", "Pa"), "xi": ("Liquid mole fraction", "-"),
       "psat": ("Saturation pressure of the pure component", "Pa")}),

    f("relative_volatility", "Relative volatility", "Separations",
      "alpha = (y1/x1)/(y2/x2)",
      {"alpha": ("Relative volatility", "-"),
       "y1": ("Vapour fraction, light key", "-"),
       "x1": ("Liquid fraction, light key", "-"),
       "y2": ("Vapour fraction, heavy key", "-"),
       "x2": ("Liquid fraction, heavy key", "-")}),

    f("antoine", "Antoine equation", "Properties",
      "logP = Aa - Ba/(Ca + T)",
      {"logP": ("log10 of vapour pressure", "-"), "Aa": ("Antoine A", "-"),
       "Ba": ("Antoine B", "-"), "Ca": ("Antoine C", "-"),
       "T": ("Temperature", "C")},
      notes="Coefficients are specific to the units used - check the source."),
]
