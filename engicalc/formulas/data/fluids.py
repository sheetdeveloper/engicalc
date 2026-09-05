"""Fluid statics, pipe flow, pumps and dimensionless groups."""

from ..model import make_builder

f = make_builder("Fluid Mechanics")

FORMULAS = [
    f("density", "Density", "Properties", "rho = m/V",
      {"rho": ("Density", "kg/m^3"), "m": ("Mass", "kg"), "V": ("Volume", "m^3")}),

    f("specific_weight", "Specific weight", "Properties", "gamma = rho*g",
      {"gamma": ("Specific weight", "N/m^3"), "rho": ("Density", "kg/m^3"),
       "g": ("Gravity", "m/s^2", "9.80665")}),

    f("hydrostatic", "Hydrostatic pressure", "Statics", "p = rho*g*h",
      {"p": ("Gauge pressure", "Pa"), "rho": ("Density", "kg/m^3", "998"),
       "g": ("Gravity", "m/s^2", "9.80665"), "h": ("Depth below surface", "m")},
      tags=("pressure", "head")),

    f("buoyancy", "Archimedes' principle", "Statics", "Fb = rho*g*Vd",
      {"Fb": ("Buoyant force", "N"), "rho": ("Fluid density", "kg/m^3"),
       "g": ("Gravity", "m/s^2", "9.80665"),
       "Vd": ("Displaced volume", "m^3")}),

    f("continuity", "Continuity (incompressible)", "Flow", "A1*v1 = A2*v2",
      {"A1": ("Inlet area", "m^2"), "v1": ("Inlet velocity", "m/s"),
       "A2": ("Outlet area", "m^2"), "v2": ("Outlet velocity", "m/s")}),

    f("mass_flow", "Mass flow rate", "Flow", "mdot = rho*A*v",
      {"mdot": ("Mass flow rate", "kg/s"), "rho": ("Density", "kg/m^3"),
       "A": ("Cross-sectional area", "m^2"), "v": ("Mean velocity", "m/s")}),

    f("volumetric_flow", "Volumetric flow rate", "Flow", "Q = A*v",
      {"Q": ("Volumetric flow rate", "m^3/s"), "A": ("Area", "m^2"),
       "v": ("Mean velocity", "m/s")}),

    f("bernoulli", "Bernoulli equation (head form)", "Flow",
      "p1/(rho*g) + v1^2/(2*g) + z1 = p2/(rho*g) + v2^2/(2*g) + z2 + hL",
      {"p1": ("Pressure at 1", "Pa"), "v1": ("Velocity at 1", "m/s"),
       "z1": ("Elevation at 1", "m"), "p2": ("Pressure at 2", "Pa"),
       "v2": ("Velocity at 2", "m/s"), "z2": ("Elevation at 2", "m"),
       "hL": ("Head loss between 1 and 2", "m", "0"),
       "rho": ("Density", "kg/m^3", "998"), "g": ("Gravity", "m/s^2", "9.80665")},
      assumptions="Steady, incompressible, along a streamline.",
      tags=("bernoulli", "head")),

    f("reynolds", "Reynolds number (pipe)", "Dimensionless",
      "Re = rho*v*D/mu",
      {"Re": ("Reynolds number", "-"), "rho": ("Density", "kg/m^3", "998"),
       "v": ("Mean velocity", "m/s"), "D": ("Pipe diameter", "m"),
       "mu": ("Dynamic viscosity", "Pa*s", "0.001")},
      notes="Laminar below ~2300, turbulent above ~4000.",
      tags=("reynolds", "turbulence")),

    f("kinematic_viscosity", "Kinematic viscosity", "Properties",
      "nu = mu/rho",
      {"nu": ("Kinematic viscosity", "m^2/s"),
       "mu": ("Dynamic viscosity", "Pa*s"), "rho": ("Density", "kg/m^3")}),

    f("darcy_weisbach", "Darcy-Weisbach head loss", "Pipe flow",
      "hf = fD*L*v^2/(D*2*g)",
      {"hf": ("Friction head loss", "m"), "fD": ("Darcy friction factor", "-"),
       "L": ("Pipe length", "m"), "v": ("Mean velocity", "m/s"),
       "D": ("Pipe diameter", "m"), "g": ("Gravity", "m/s^2", "9.80665")},
      tags=("head loss", "friction")),

    f("laminar_friction", "Friction factor, laminar flow", "Pipe flow",
      "fD = 64/Re",
      {"fD": ("Darcy friction factor", "-"), "Re": ("Reynolds number", "-")},
      assumptions="Re < 2300."),

    f("blasius", "Blasius friction factor", "Pipe flow",
      "fD = 0.316/Re^(1/4)",
      {"fD": ("Darcy friction factor", "-"), "Re": ("Reynolds number", "-")},
      assumptions="Smooth pipe, 4000 < Re < 100000."),

    f("minor_loss", "Minor (fitting) loss", "Pipe flow", "hm = K*v^2/(2*g)",
      {"hm": ("Minor head loss", "m"), "K": ("Loss coefficient", "-"),
       "v": ("Mean velocity", "m/s"), "g": ("Gravity", "m/s^2", "9.80665")}),

    f("hagen_poiseuille", "Hagen-Poiseuille flow", "Pipe flow",
      "Q = pi*dp*R^4/(8*mu*L)",
      {"Q": ("Volumetric flow rate", "m^3/s"), "dp": ("Pressure drop", "Pa"),
       "R": ("Pipe radius", "m"), "mu": ("Dynamic viscosity", "Pa*s"),
       "L": ("Pipe length", "m")},
      assumptions="Fully developed laminar flow in a circular pipe."),

    f("pump_power", "Hydraulic power of a pump", "Pumps",
      "P = rho*g*Q*H/eta",
      {"P": ("Shaft power", "W"), "rho": ("Density", "kg/m^3", "998"),
       "g": ("Gravity", "m/s^2", "9.80665"), "Q": ("Flow rate", "m^3/s"),
       "H": ("Total head", "m"), "eta": ("Pump efficiency", "-", "0.7")},
      tags=("pump", "power")),

    f("torricelli", "Torricelli's law", "Flow", "v = sqrt(2*g*h)",
      {"v": ("Efflux velocity", "m/s"), "g": ("Gravity", "m/s^2", "9.80665"),
       "h": ("Head above the orifice", "m")}),

    f("orifice_flow", "Orifice discharge", "Flow meters",
      "Q = Cd*A*sqrt(2*dp/rho)",
      {"Q": ("Flow rate", "m^3/s"), "Cd": ("Discharge coefficient", "-", "0.62"),
       "A": ("Orifice area", "m^2"), "dp": ("Pressure drop", "Pa"),
       "rho": ("Density", "kg/m^3", "998")}),

    f("drag_force", "Drag force", "External flow",
      "Fd = Cd*rho*v^2*A/2",
      {"Fd": ("Drag force", "N"), "Cd": ("Drag coefficient", "-"),
       "rho": ("Fluid density", "kg/m^3", "1.225"),
       "v": ("Relative velocity", "m/s"), "A": ("Reference area", "m^2")}),

    f("lift_force", "Lift force", "External flow",
      "Fl = Cl*rho*v^2*A/2",
      {"Fl": ("Lift force", "N"), "Cl": ("Lift coefficient", "-"),
       "rho": ("Fluid density", "kg/m^3", "1.225"), "v": ("Airspeed", "m/s"),
       "A": ("Wing area", "m^2")}),

    f("mach", "Mach number", "Compressible", "Ma = v/a",
      {"Ma": ("Mach number", "-"), "v": ("Flow velocity", "m/s"),
       "a": ("Speed of sound", "m/s", "343")}),

    f("speed_of_sound", "Speed of sound in an ideal gas", "Compressible",
      "a = sqrt(k*R*T)",
      {"a": ("Speed of sound", "m/s"),
       "k": ("Ratio of specific heats", "-", "1.4"),
       "R": ("Specific gas constant", "J/(kg*K)", "287.05"),
       "T": ("Absolute temperature", "K")}),

    f("froude", "Froude number", "Dimensionless", "Fr = v/sqrt(g*L)",
      {"Fr": ("Froude number", "-"), "v": ("Velocity", "m/s"),
       "g": ("Gravity", "m/s^2", "9.80665"), "L": ("Characteristic length", "m")}),

    f("manning", "Manning's equation (open channel)", "Open channel",
      "v = Rh^(2/3)*S^(1/2)/n",
      {"v": ("Mean velocity", "m/s"), "Rh": ("Hydraulic radius", "m"),
       "S": ("Channel slope", "m/m"), "n": ("Manning roughness", "-", "0.013")},
      notes="SI form. Rh = area / wetted perimeter."),

    f("hydraulic_diameter", "Hydraulic diameter", "Pipe flow",
      "Dh = 4*A/P",
      {"Dh": ("Hydraulic diameter", "m"), "A": ("Flow area", "m^2"),
       "P": ("Wetted perimeter", "m")}),
]
