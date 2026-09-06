"""Conduction, convection, radiation and exchangers."""

from ..model import make_builder

f = make_builder("Heat Transfer")

FORMULAS = [
    f("fourier", "Fourier's law (plane wall)", "Conduction",
      "Q = k*A*dT/L",
      {"Q": ("Heat transfer rate", "W"),
       "k": ("Thermal conductivity", "W/(m*K)"), "A": ("Area", "m^2"),
       "dT": ("Temperature difference", "K"), "L": ("Wall thickness", "m")},
      made_of={"k": "conductivity"},
      assumptions="Steady, one-dimensional, constant k.",
      tags=("conduction",)),

    f("wall_resistance", "Conduction resistance - plane wall", "Resistance",
      "Rth = L/(k*A)",
      {"Rth": ("Thermal resistance", "K/W"), "L": ("Thickness", "m"),
       "k": ("Thermal conductivity", "W/(m*K)"), "A": ("Area", "m^2")},
      made_of={"k": "conductivity"}),

    f("cylinder_conduction", "Conduction through a cylindrical wall",
      "Conduction", "Q = 2*pi*k*L*dT/log(r2/r1)",
      {"Q": ("Heat transfer rate", "W"),
       "k": ("Thermal conductivity", "W/(m*K)"), "L": ("Cylinder length", "m"),
       "dT": ("Temperature difference", "K"), "r2": ("Outer radius", "m"),
       "r1": ("Inner radius", "m")},
      made_of={"k": "conductivity"},
      notes="log() is the natural logarithm."),

    f("newton_cooling", "Newton's law of cooling", "Convection",
      "Q = h*A*(Ts - Tinf)",
      {"Q": ("Heat transfer rate", "W"),
       "h": ("Convective coefficient", "W/(m^2*K)"), "A": ("Surface area", "m^2"),
       "Ts": ("Surface temperature", "K"), "Tinf": ("Fluid temperature", "K")},
      tags=("convection",)),

    f("convection_resistance", "Convection resistance", "Resistance",
      "Rth = 1/(h*A)",
      {"Rth": ("Thermal resistance", "K/W"),
       "h": ("Convective coefficient", "W/(m^2*K)"), "A": ("Area", "m^2")}),

    f("overall_u", "Overall heat transfer coefficient", "Resistance",
      "Q = U*A*dT",
      {"Q": ("Heat transfer rate", "W"),
       "U": ("Overall coefficient", "W/(m^2*K)"), "A": ("Area", "m^2"),
       "dT": ("Overall temperature difference", "K")}),

    f("u_series", "U-value of a layered wall", "Resistance",
      "1/U = 1/hi + L1/k1 + L2/k2 + 1/ho",
      {"U": ("Overall coefficient", "W/(m^2*K)"),
       "hi": ("Inside film coefficient", "W/(m^2*K)"),
       "L1": ("Layer 1 thickness", "m"), "k1": ("Layer 1 conductivity", "W/(m*K)"),
       "L2": ("Layer 2 thickness", "m"), "k2": ("Layer 2 conductivity", "W/(m*K)"),
       "ho": ("Outside film coefficient", "W/(m^2*K)")}),

    f("stefan_boltzmann", "Radiation from a grey surface", "Radiation",
      "Q = epsilon*sigma_sb*A*(Ts^4 - Tsur^4)",
      {"Q": ("Net radiated power", "W"), "epsilon": ("Emissivity", "-", "0.9"),
       "sigma_sb": ("Stefan-Boltzmann constant", "W/(m^2*K^4)", "5.670374419e-8"),
       "A": ("Surface area", "m^2"), "Ts": ("Surface temperature", "K"),
       "Tsur": ("Surroundings temperature", "K")},
      tags=("radiation",)),

    f("lmtd", "Log mean temperature difference", "Heat exchangers",
      "LMTD = (dT1 - dT2)/log(dT1/dT2)",
      {"LMTD": ("Log mean temperature difference", "K"),
       "dT1": ("Terminal temperature difference 1", "K"),
       "dT2": ("Terminal temperature difference 2", "K")},
      notes="Counter-flow or parallel-flow; apply a correction factor F for "
            "shell-and-tube geometries."),

    f("exchanger_duty", "Heat exchanger duty", "Heat exchangers",
      "Q = U*A*F*LMTD",
      {"Q": ("Duty", "W"), "U": ("Overall coefficient", "W/(m^2*K)"),
       "A": ("Heat transfer area", "m^2"), "F": ("Correction factor", "-", "1"),
       "LMTD": ("Log mean temperature difference", "K")}),

    f("sensible_duty", "Duty from a fluid stream", "Heat exchangers",
      "Q = mdot*cp*(Tout - Tin)",
      {"Q": ("Heat rate", "W"), "mdot": ("Mass flow rate", "kg/s"),
       "cp": ("Specific heat", "J/(kg*K)", "4186"),
       "Tout": ("Outlet temperature", "K"), "Tin": ("Inlet temperature", "K")}),

    f("biot", "Biot number", "Dimensionless", "Bi = h*Lc/k",
      {"Bi": ("Biot number", "-"), "h": ("Convective coefficient", "W/(m^2*K)"),
       "Lc": ("Characteristic length (V/A)", "m"),
       "k": ("Thermal conductivity of the solid", "W/(m*K)")},
      made_of={"k": "conductivity"},
      notes="Bi < 0.1 justifies the lumped capacitance model."),

    f("lumped_capacitance", "Lumped capacitance cooling", "Transient",
      "T = Tinf + (T0 - Tinf)*exp(-h*A*t/(rho*V*cp))",
      {"T": ("Temperature at time t", "K"), "Tinf": ("Ambient temperature", "K"),
       "T0": ("Initial temperature", "K"),
       "h": ("Convective coefficient", "W/(m^2*K)"), "A": ("Surface area", "m^2"),
       "t": ("Time", "s"), "rho": ("Density", "kg/m^3"), "V": ("Volume", "m^3"),
       "cp": ("Specific heat", "J/(kg*K)")},
      made_of={"rho": "density", "cp": "specific_heat"},
      assumptions="Bi < 0.1."),

    f("nusselt", "Nusselt number", "Dimensionless", "Nu = h*L/k",
      {"Nu": ("Nusselt number", "-"),
       "h": ("Convective coefficient", "W/(m^2*K)"),
       "L": ("Characteristic length", "m"),
       "k": ("Fluid thermal conductivity", "W/(m*K)")}),

    f("prandtl", "Prandtl number", "Dimensionless", "Pr = cp*mu/k",
      {"Pr": ("Prandtl number", "-"), "cp": ("Specific heat", "J/(kg*K)"),
       "mu": ("Dynamic viscosity", "Pa*s"),
       "k": ("Thermal conductivity", "W/(m*K)")}),

    f("dittus_boelter", "Dittus-Boelter correlation", "Correlations",
      "Nu = 0.023*Re^(4/5)*Pr^n",
      {"Nu": ("Nusselt number", "-"), "Re": ("Reynolds number", "-"),
       "Pr": ("Prandtl number", "-"),
       "n": ("0.4 heating, 0.3 cooling", "-", "0.4")},
      assumptions="Turbulent, fully developed pipe flow, Re > 10000."),

    f("fin_efficiency", "Straight fin efficiency", "Fins",
      "eta_f = tanh(m_f*L)/(m_f*L)",
      {"eta_f": ("Fin efficiency", "-"),
       "m_f": ("Fin parameter sqrt(h*P/(k*Ac))", "1/m"),
       "L": ("Fin length", "m")}),

    f("thermal_diffusivity", "Thermal diffusivity", "Properties",
      "alpha = k/(rho*cp)",
      {"alpha": ("Thermal diffusivity", "m^2/s"),
       "k": ("Thermal conductivity", "W/(m*K)"), "rho": ("Density", "kg/m^3"),
       "cp": ("Specific heat", "J/(kg*K)")},
      made_of={"k": "conductivity", "rho": "density", "cp": "specific_heat"}),
]
