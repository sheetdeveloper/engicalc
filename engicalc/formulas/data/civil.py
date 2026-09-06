"""Civil, structural and geotechnical."""

from ..model import make_builder

f = make_builder("Civil & Structural")

FORMULAS = [
    f("dead_load", "Distributed self weight of a slab", "Loading",
      "w = rho*g*t",
      {"w": ("Load per unit area", "N/m^2"), "rho": ("Density", "kg/m^3", "2400"),
       "g": ("Gravity", "m/s^2", "9.80665"), "t": ("Slab thickness", "m")},
      made_of={"rho": "density"},
      notes="Reinforced concrete is about 2400 kg/m^3."),

    f("udl_reaction", "End reaction - simply supported UDL", "Beams",
      "R = w*L/2",
      {"R": ("Reaction at each support", "N"),
       "w": ("Load per unit length", "N/m"), "L": ("Span", "m")}),

    f("point_load_moment", "Max moment - simply supported central point load",
      "Beams", "M = F*L/4",
      {"M": ("Maximum moment", "N*m"), "F": ("Point load", "N"),
       "L": ("Span", "m")}),

    f("bearing_pressure", "Bearing pressure under a footing", "Foundations",
      "q = P/(B*Lf)",
      {"q": ("Bearing pressure", "Pa"), "P": ("Vertical load", "N"),
       "B": ("Footing width", "m"), "Lf": ("Footing length", "m")}),

    f("effective_stress", "Terzaghi effective stress", "Geotechnical",
      "sigma_eff = sigma_tot - u",
      {"sigma_eff": ("Effective stress", "Pa"),
       "sigma_tot": ("Total stress", "Pa"), "u": ("Pore water pressure", "Pa")}),

    f("active_earth_pressure", "Rankine active earth pressure coefficient",
      "Geotechnical", "Ka = (1 - sin(phi))/(1 + sin(phi))",
      {"Ka": ("Active earth pressure coefficient", "-"),
       "phi": ("Angle of internal friction", "rad")}),

    f("darcy_seepage", "Darcy's law (seepage)", "Geotechnical", "q = k_p*i*A",
      {"q": ("Seepage flow rate", "m^3/s"),
       "k_p": ("Coefficient of permeability", "m/s"),
       "i": ("Hydraulic gradient", "-"), "A": ("Cross-sectional area", "m^2")}),

    f("concrete_capacity", "Axial capacity of a short concrete column",
      "Concrete", "N = 0.85*fc*Ac + fy*As",
      {"N": ("Squash load", "N"), "fc": ("Concrete strength", "Pa"),
       "Ac": ("Net concrete area", "m^2"), "fy": ("Steel yield strength", "Pa"),
       "As": ("Steel area", "m^2")},
      made_of={"fy": "yield"},
      notes="Unfactored, indicative only - apply the relevant code factors."),

    f("shrinkage_movement", "Thermal movement of a member", "Serviceability",
      "dL = alpha*L*dT",
      {"dL": ("Length change", "m"),
       "alpha": ("Coefficient of thermal expansion", "1/K", "12e-6"),
       "L": ("Member length", "m"), "dT": ("Temperature change", "K")},
      made_of={"alpha": "expansion"}),

    f("survey_grade", "Gradient between two points", "Surveying",
      "G = (h2 - h1)/D*100",
      {"G": ("Grade", "%"), "h2": ("Level at point 2", "m"),
       "h1": ("Level at point 1", "m"), "D": ("Horizontal distance", "m")}),

    f("concrete_volume", "Concrete volume for a rectangular pour", "Quantities",
      "V = L*W*t",
      {"V": ("Volume", "m^3"), "L": ("Length", "m"), "W": ("Width", "m"),
       "t": ("Thickness", "m")}),

    f("rainfall_runoff", "Rational method peak runoff", "Hydrology",
      "Qp = C*i_r*Ah/360",
      {"Qp": ("Peak flow", "m^3/s"), "C": ("Runoff coefficient", "-", "0.9"),
       "i_r": ("Rainfall intensity", "mm/h"),
       "Ah": ("Catchment area", "hectare")}),
]
