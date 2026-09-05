"""Stress, strain, beams, shafts, columns."""

from ..model import make_builder

f = make_builder("Strength of Materials")

FORMULAS = [
    f("normal_stress", "Direct (normal) stress", "Stress & strain", "sigma = F/A",
      {"sigma": ("Normal stress", "Pa"), "F": ("Axial force", "N"),
       "A": ("Cross-sectional area", "m^2")}),

    f("shear_stress", "Average shear stress", "Stress & strain", "tau = V/A",
      {"tau": ("Shear stress", "Pa"), "V": ("Shear force", "N"),
       "A": ("Area resisting shear", "m^2")}),

    f("strain", "Engineering strain", "Stress & strain", "epsilon = dL/L0",
      {"epsilon": ("Strain", "-"), "dL": ("Change in length", "m"),
       "L0": ("Original length", "m")}),

    f("hookes_law", "Hooke's law", "Stress & strain", "sigma = E*epsilon",
      {"sigma": ("Stress", "Pa"), "E": ("Young's modulus", "Pa"),
       "epsilon": ("Strain", "-")},
      assumptions="Linear-elastic region only."),

    f("axial_deflection", "Axial extension of a bar", "Deflection",
      "dL = F*L/(A*E)",
      {"dL": ("Extension", "m"), "F": ("Axial force", "N"), "L": ("Length", "m"),
       "A": ("Area", "m^2"), "E": ("Young's modulus", "Pa")}),

    f("poisson", "Poisson's ratio", "Stress & strain",
      "nu = -epsilon_lat/epsilon_long",
      {"nu": ("Poisson's ratio", "-"), "epsilon_lat": ("Lateral strain", "-"),
       "epsilon_long": ("Longitudinal strain", "-")}),

    f("shear_modulus", "Elastic constants relation", "Stress & strain",
      "G = E/(2*(1 + nu))",
      {"G": ("Shear modulus", "Pa"), "E": ("Young's modulus", "Pa"),
       "nu": ("Poisson's ratio", "-")}),

    f("bending_stress", "Bending (flexure) formula", "Beams",
      "sigma = M*y/I",
      {"sigma": ("Bending stress", "Pa"), "M": ("Bending moment", "N*m"),
       "y": ("Distance from neutral axis", "m"),
       "I": ("Second moment of area", "m^4")},
      notes="Maximum at y = c, the extreme fibre.",
      tags=("beam", "bending")),

    f("section_modulus", "Section modulus", "Beams", "Z = I/c",
      {"Z": ("Elastic section modulus", "m^3"),
       "I": ("Second moment of area", "m^4"),
       "c": ("Distance to extreme fibre", "m")}),

    f("second_moment_rect", "Second moment of area - rectangle", "Sections",
      "I = b*h^3/12",
      {"I": ("Second moment of area", "m^4"), "b": ("Width", "m"),
       "h": ("Depth", "m")},
      notes="About the centroidal axis parallel to b."),

    f("second_moment_circle", "Second moment of area - solid circle", "Sections",
      "I = pi*d^4/64",
      {"I": ("Second moment of area", "m^4"), "d": ("Diameter", "m")}),

    f("polar_moment_circle", "Polar second moment - solid shaft", "Shafts",
      "Jp = pi*d^4/32",
      {"Jp": ("Polar second moment of area", "m^4"), "d": ("Diameter", "m")}),

    f("torsion_stress", "Torsion formula", "Shafts", "tau = T*r/Jp",
      {"tau": ("Shear stress", "Pa"), "T": ("Applied torque", "N*m"),
       "r": ("Radius to point of interest", "m"),
       "Jp": ("Polar second moment of area", "m^4")}),

    f("angle_of_twist", "Angle of twist", "Shafts", "phi = T*L/(Jp*G)",
      {"phi": ("Angle of twist", "rad"), "T": ("Torque", "N*m"),
       "L": ("Shaft length", "m"), "Jp": ("Polar second moment", "m^4"),
       "G": ("Shear modulus", "Pa")}),

    f("beam_udl_deflection", "Max deflection - simply supported, UDL",
      "Beam deflection", "delta = 5*w*L^4/(384*E*I)",
      {"delta": ("Maximum deflection", "m"),
       "w": ("Uniform load per unit length", "N/m"), "L": ("Span", "m"),
       "E": ("Young's modulus", "Pa"), "I": ("Second moment of area", "m^4")},
      assumptions="Prismatic, linear-elastic, small deflections."),

    f("beam_point_deflection", "Max deflection - simply supported, central load",
      "Beam deflection", "delta = F*L^3/(48*E*I)",
      {"delta": ("Maximum deflection", "m"), "F": ("Central point load", "N"),
       "L": ("Span", "m"), "E": ("Young's modulus", "Pa"),
       "I": ("Second moment of area", "m^4")}),

    f("cantilever_point_deflection", "Max deflection - cantilever, end load",
      "Beam deflection", "delta = F*L^3/(3*E*I)",
      {"delta": ("Tip deflection", "m"), "F": ("End load", "N"),
       "L": ("Length", "m"), "E": ("Young's modulus", "Pa"),
       "I": ("Second moment of area", "m^4")}),

    f("cantilever_udl_deflection", "Max deflection - cantilever, UDL",
      "Beam deflection", "delta = w*L^4/(8*E*I)",
      {"delta": ("Tip deflection", "m"), "w": ("Load per unit length", "N/m"),
       "L": ("Length", "m"), "E": ("Young's modulus", "Pa"),
       "I": ("Second moment of area", "m^4")}),

    f("max_moment_udl", "Max bending moment - simply supported, UDL", "Beams",
      "M = w*L^2/8",
      {"M": ("Maximum bending moment", "N*m"),
       "w": ("Load per unit length", "N/m"), "L": ("Span", "m")}),

    f("euler_buckling", "Euler critical buckling load", "Columns",
      "Pcr = pi^2*E*I/(K*L)^2",
      {"Pcr": ("Critical load", "N"), "E": ("Young's modulus", "Pa"),
       "I": ("Least second moment of area", "m^4"),
       "K": ("Effective length factor", "-", "1"), "L": ("Length", "m")},
      notes="K = 1 pinned-pinned, 0.5 fixed-fixed, 0.7 fixed-pinned, 2 fixed-free.",
      assumptions="Slender column, elastic buckling."),

    f("slenderness", "Slenderness ratio", "Columns", "lambda_s = K*L/r_g",
      {"lambda_s": ("Slenderness ratio", "-"),
       "K": ("Effective length factor", "-", "1"), "L": ("Length", "m"),
       "r_g": ("Radius of gyration", "m")}),

    f("radius_of_gyration", "Radius of gyration", "Sections", "r_g = sqrt(I/A)",
      {"r_g": ("Radius of gyration", "m"),
       "I": ("Second moment of area", "m^4"), "A": ("Area", "m^2")}),

    f("factor_of_safety", "Factor of safety", "Design", "FS = sigma_y/sigma",
      {"FS": ("Factor of safety", "-"), "sigma_y": ("Yield strength", "Pa"),
       "sigma": ("Working stress", "Pa")}),

    f("thin_wall_hoop", "Thin-walled cylinder - hoop stress", "Pressure vessels",
      "sigma_h = p*d/(2*t)",
      {"sigma_h": ("Hoop stress", "Pa"), "p": ("Internal gauge pressure", "Pa"),
       "d": ("Internal diameter", "m"), "t": ("Wall thickness", "m")},
      assumptions="Valid for d/t greater than about 20."),

    f("thin_wall_long", "Thin-walled cylinder - longitudinal stress",
      "Pressure vessels", "sigma_l = p*d/(4*t)",
      {"sigma_l": ("Longitudinal stress", "Pa"),
       "p": ("Internal gauge pressure", "Pa"), "d": ("Internal diameter", "m"),
       "t": ("Wall thickness", "m")}),

    f("thermal_stress", "Fully restrained thermal stress", "Thermal effects",
      "sigma = E*alpha*dT",
      {"sigma": ("Thermal stress", "Pa"), "E": ("Young's modulus", "Pa"),
       "alpha": ("Coefficient of thermal expansion", "1/K"),
       "dT": ("Temperature change", "K")}),

    f("von_mises_2d", "Von Mises stress (plane stress)", "Failure theories",
      "sigma_vm = sqrt(sigma_x^2 - sigma_x*sigma_y + sigma_y^2 + 3*tau_xy^2)",
      {"sigma_vm": ("Von Mises equivalent stress", "Pa"),
       "sigma_x": ("Normal stress, x", "Pa"),
       "sigma_y": ("Normal stress, y", "Pa"),
       "tau_xy": ("Shear stress", "Pa")},
      notes="Compare against the yield strength for ductile materials."),
]
