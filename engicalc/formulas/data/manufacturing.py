"""Materials, machining and additive manufacturing."""

from ..model import make_builder

f = make_builder("Materials & Manufacturing")

FORMULAS = [
    f("cutting_speed", "Cutting speed from spindle speed", "Machining",
      "Vc = pi*D*Nrpm/1000",
      {"Vc": ("Cutting speed", "m/min"), "D": ("Tool or work diameter", "mm"),
       "Nrpm": ("Spindle speed", "rev/min")}),

    f("feed_rate", "Milling feed rate", "Machining",
      "Vf = Nrpm*z*fz",
      {"Vf": ("Table feed", "mm/min"), "Nrpm": ("Spindle speed", "rev/min"),
       "z": ("Number of teeth", "-"), "fz": ("Feed per tooth", "mm")}),

    f("mrr_milling", "Material removal rate - milling", "Machining",
      "MRR = ap*ae*Vf",
      {"MRR": ("Removal rate", "mm^3/min"), "ap": ("Axial depth of cut", "mm"),
       "ae": ("Radial width of cut", "mm"), "Vf": ("Feed rate", "mm/min")}),

    f("machining_time", "Machining time for a pass", "Machining",
      "t = Lt/Vf",
      {"t": ("Time", "min"), "Lt": ("Length of cut", "mm"),
       "Vf": ("Feed rate", "mm/min")}),

    f("hardness_strength", "Tensile strength from Brinell hardness",
      "Materials", "UTS = 3.45*HB",
      {"UTS": ("Approx. tensile strength", "MPa"),
       "HB": ("Brinell hardness number", "-")},
      notes="Rule of thumb for steels only; +/- 10% is typical.",
      assumptions="Carbon and low-alloy steels."),

    f("resilience", "Modulus of resilience", "Materials",
      "Ur = sigma_y^2/(2*E)",
      {"Ur": ("Modulus of resilience", "J/m^3"),
       "sigma_y": ("Yield strength", "Pa"), "E": ("Young's modulus", "Pa")}),

    f("specific_strength", "Specific strength", "Materials",
      "SS = sigma_y/rho",
      {"SS": ("Specific strength", "N*m/kg"),
       "sigma_y": ("Yield strength", "Pa"), "rho": ("Density", "kg/m^3")}),

    f("arrhenius", "Arrhenius rate (diffusion, creep, ageing)", "Materials",
      "K = A*exp(-Ea/(Ru*T))",
      {"K": ("Rate constant", "varies"), "A": ("Pre-exponential factor", "varies"),
       "Ea": ("Activation energy", "J/mol"),
       "Ru": ("Gas constant", "J/(mol*K)", "8.314462618"),
       "T": ("Absolute temperature", "K")}),

    # -- Additive manufacturing -------------------------------------------
    f("filament_volumetric_flow", "Extruder volumetric flow rate", "3D printing",
      "Qv = w_l*h_l*v_p",
      {"Qv": ("Volumetric flow", "mm^3/s"), "w_l": ("Extrusion width", "mm"),
       "h_l": ("Layer height", "mm"), "v_p": ("Print speed", "mm/s")},
      notes="Compare against the hot end's rated maximum flow.",
      tags=("3d printing", "fdm", "flow")),

    f("filament_feed_rate", "Filament feed rate for a given flow", "3D printing",
      "vf = 4*Qv/(pi*df^2)",
      {"vf": ("Filament feed speed", "mm/s"),
       "Qv": ("Volumetric flow", "mm^3/s"),
       "df": ("Filament diameter", "mm", "1.75")},
      tags=("3d printing", "extrusion")),

    f("filament_length", "Filament length used by a print", "3D printing",
      "Lf = 4*Vpart/(pi*df^2)",
      {"Lf": ("Filament length", "mm"),
       "Vpart": ("Extruded volume", "mm^3"),
       "df": ("Filament diameter", "mm", "1.75")},
      tags=("3d printing", "estimating")),

    f("print_mass", "Mass of a printed part", "3D printing",
      "m = rho*Vpart*IF/1000",
      {"m": ("Part mass", "g"), "rho": ("Material density", "g/cm^3", "1.24"),
       "Vpart": ("Bounding solid volume", "mm^3"),
       "IF": ("Effective infill/solidity fraction", "-", "0.2")},
      notes="PLA ~1.24, PETG ~1.27, ABS ~1.04 g/cm^3.",
      tags=("3d printing", "quoting")),

    f("layer_count", "Number of layers", "3D printing", "n = Hp/h_l",
      {"n": ("Layer count", "-"), "Hp": ("Part height", "mm"),
       "h_l": ("Layer height", "mm")},
      tags=("3d printing",)),

    f("print_time_estimate", "First-order print time from flow rate",
      "3D printing", "t = Vpart/(Qv*3600)",
      {"t": ("Print time", "h"), "Vpart": ("Extruded volume", "mm^3"),
       "Qv": ("Average volumetric flow", "mm^3/s")},
      notes="Ignores travel moves and non-print time - multiply by 1.2-1.5 "
            "for a realistic quote.",
      tags=("3d printing", "quoting")),

    f("job_price", "Job price from material, time and margin", "3D printing",
      "Price = (m*mat_rate/1000 + t*machine_rate + setup)*(1 + margin)",
      {"Price": ("Quoted price", "currency"), "m": ("Material used", "g"),
       "mat_rate": ("Material cost per kg", "currency/kg", "35"),
       "t": ("Machine time", "h"),
       "machine_rate": ("Machine + overhead rate per hour", "currency/h", "4"),
       "setup": ("Setup and post-processing labour", "currency", "10"),
       "margin": ("Margin as a fraction", "-", "0.35")},
      tags=("3d printing", "quoting", "cost")),

    f("nozzle_pressure_drop", "Pressure drop through a nozzle (Newtonian)",
      "3D printing", "dp = 8*mu*Ln*Qv/(pi*Rn^4)",
      {"dp": ("Pressure drop", "Pa"), "mu": ("Melt viscosity", "Pa*s"),
       "Ln": ("Nozzle land length", "m"),
       "Qv": ("Volumetric flow", "m^3/s"), "Rn": ("Nozzle radius", "m")},
      assumptions="Newtonian approximation; real polymer melts shear thin."),

    f("shrinkage_allowance", "Mould/print shrinkage allowance", "3D printing",
      "Lmould = Lpart*(1 + s_f)",
      {"Lmould": ("Tool or model dimension", "mm"),
       "Lpart": ("Target part dimension", "mm"),
       "s_f": ("Shrinkage fraction", "-", "0.005")}),
]
