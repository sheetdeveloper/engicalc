"""Thermodynamics: gas laws, energy balances, cycles."""

from ..model import make_builder

f = make_builder("Thermodynamics")

FORMULAS = [
    f("ideal_gas", "Ideal gas law", "Gas laws", "p*V = n*Ru*T",
      {"p": ("Absolute pressure", "Pa"), "V": ("Volume", "m^3"),
       "n": ("Amount of substance", "mol"),
       "Ru": ("Universal gas constant", "J/(mol*K)", "8.314462618"),
       "T": ("Absolute temperature", "K")},
      tags=("gas", "state")),

    f("ideal_gas_specific", "Ideal gas law (specific form)", "Gas laws",
      "p*v = R*T",
      {"p": ("Absolute pressure", "Pa"), "v": ("Specific volume", "m^3/kg"),
       "R": ("Specific gas constant", "J/(kg*K)", "287.05"),
       "T": ("Absolute temperature", "K")},
      notes="R = 287.05 J/(kg*K) for dry air."),

    f("combined_gas", "Combined gas law", "Gas laws", "p1*V1/T1 = p2*V2/T2",
      {"p1": ("Initial pressure", "Pa"), "V1": ("Initial volume", "m^3"),
       "T1": ("Initial temperature", "K"), "p2": ("Final pressure", "Pa"),
       "V2": ("Final volume", "m^3"), "T2": ("Final temperature", "K")}),

    f("sensible_heat", "Sensible heat", "Heat & energy", "Q = m*c*(T2 - T1)",
      {"Q": ("Heat transferred", "J"), "m": ("Mass", "kg"),
       "c": ("Specific heat capacity", "J/(kg*K)", "4186"),
       "T2": ("Final temperature", "K"), "T1": ("Initial temperature", "K")},
      made_of={"c": "specific_heat"},
      assumptions="No phase change; c constant over the range.",
      tags=("heat", "calorimetry")),

    f("latent_heat", "Latent heat", "Heat & energy", "Q = m*L",
      {"Q": ("Heat transferred", "J"), "m": ("Mass", "kg"),
       "L": ("Specific latent heat", "J/kg")}),

    f("first_law", "First law (closed system)", "Laws", "dU = Q - W",
      {"dU": ("Change in internal energy", "J"),
       "Q": ("Heat added to the system", "J"),
       "W": ("Work done by the system", "J")}),

    f("sfee", "Steady flow energy equation (simplified)", "Laws",
      "Qdot - Wdot = mdot*(h2 - h1)",
      {"Qdot": ("Heat rate in", "W"), "Wdot": ("Shaft power out", "W"),
       "mdot": ("Mass flow rate", "kg/s"),
       "h2": ("Outlet specific enthalpy", "J/kg"),
       "h1": ("Inlet specific enthalpy", "J/kg")},
      assumptions="Steady state, negligible kinetic and potential energy change."),

    f("enthalpy", "Enthalpy", "Properties", "H = U + p*V",
      {"H": ("Enthalpy", "J"), "U": ("Internal energy", "J"),
       "p": ("Pressure", "Pa"), "V": ("Volume", "m^3")}),

    f("cp_cv", "Mayer's relation", "Properties", "cp - cv = R",
      {"cp": ("Specific heat at constant pressure", "J/(kg*K)"),
       "cv": ("Specific heat at constant volume", "J/(kg*K)"),
       "R": ("Specific gas constant", "J/(kg*K)")}),

    f("gamma_ratio", "Ratio of specific heats", "Properties", "k = cp/cv",
      {"k": ("Ratio of specific heats", "-", "1.4"),
       "cp": ("cp", "J/(kg*K)"), "cv": ("cv", "J/(kg*K)")}),

    f("isentropic_pt", "Isentropic relation (p-T)", "Processes",
      "T2/T1 = (p2/p1)^((k - 1)/k)",
      {"T2": ("Final temperature", "K"), "T1": ("Initial temperature", "K"),
       "p2": ("Final pressure", "Pa"), "p1": ("Initial pressure", "Pa"),
       "k": ("Ratio of specific heats", "-", "1.4")},
      assumptions="Reversible adiabatic, ideal gas, constant k."),

    f("isentropic_pv", "Isentropic relation (p-V)", "Processes",
      "p1*V1^k = p2*V2^k",
      {"p1": ("Initial pressure", "Pa"), "V1": ("Initial volume", "m^3"),
       "p2": ("Final pressure", "Pa"), "V2": ("Final volume", "m^3"),
       "k": ("Ratio of specific heats", "-", "1.4")}),

    f("isothermal_work", "Work in an isothermal process", "Processes",
      "W = n*Ru*T*log(V2/V1)",
      {"W": ("Work done by the gas", "J"), "n": ("Moles", "mol"),
       "Ru": ("Universal gas constant", "J/(mol*K)", "8.314462618"),
       "T": ("Temperature", "K"), "V2": ("Final volume", "m^3"),
       "V1": ("Initial volume", "m^3")},
      notes="log() is the natural logarithm."),

    f("carnot_efficiency", "Carnot efficiency", "Cycles",
      "eta = 1 - Tc/Th",
      {"eta": ("Thermal efficiency", "-"), "Tc": ("Cold reservoir temp", "K"),
       "Th": ("Hot reservoir temp", "K")},
      notes="Upper bound on any heat engine between the same two reservoirs.",
      tags=("cycle", "efficiency")),

    f("thermal_efficiency", "Thermal efficiency", "Cycles", "eta = Wnet/Qin",
      {"eta": ("Thermal efficiency", "-"), "Wnet": ("Net work output", "J"),
       "Qin": ("Heat input", "J")}),

    f("cop_refrigerator", "Coefficient of performance - refrigerator", "Cycles",
      "COP = Qc/Win",
      {"COP": ("Coefficient of performance", "-"),
       "Qc": ("Heat removed from cold space", "J"), "Win": ("Work input", "J")}),

    f("cop_heatpump", "Coefficient of performance - heat pump", "Cycles",
      "COP = Qh/Win",
      {"COP": ("Coefficient of performance", "-"),
       "Qh": ("Heat delivered", "J"), "Win": ("Work input", "J")}),

    f("otto_efficiency", "Otto cycle efficiency", "Cycles",
      "eta = 1 - 1/r^(k - 1)",
      {"eta": ("Air-standard efficiency", "-"), "r": ("Compression ratio", "-"),
       "k": ("Ratio of specific heats", "-", "1.4")}),

    f("entropy_change", "Entropy change of an ideal gas", "Entropy",
      "ds = cp*log(T2/T1) - R*log(p2/p1)",
      {"ds": ("Specific entropy change", "J/(kg*K)"),
       "cp": ("cp", "J/(kg*K)"), "T2": ("Final temperature", "K"),
       "T1": ("Initial temperature", "K"), "R": ("Gas constant", "J/(kg*K)"),
       "p2": ("Final pressure", "Pa"), "p1": ("Initial pressure", "Pa")}),

    f("heat_reversible", "Entropy from reversible heat transfer", "Entropy",
      "dS = Q/T",
      {"dS": ("Entropy change", "J/K"), "Q": ("Heat transferred", "J"),
       "T": ("Absolute temperature", "K")}),

    f("mixing_temperature", "Equilibrium temperature of two mixed masses",
      "Heat & energy",
      "Tf = (m1*c1*T1 + m2*c2*T2)/(m1*c1 + m2*c2)",
      {"Tf": ("Final mixture temperature", "K"), "m1": ("Mass 1", "kg"),
       "c1": ("Specific heat 1", "J/(kg*K)"), "T1": ("Temperature 1", "K"),
       "m2": ("Mass 2", "kg"), "c2": ("Specific heat 2", "J/(kg*K)"),
       "T2": ("Temperature 2", "K")},
      made_of={"c1": "specific_heat", "c2": "specific_heat"},
      assumptions="Adiabatic mixing, no phase change."),
]
