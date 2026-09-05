"""Geometry, mensuration and everyday maths."""

from ..model import make_builder

f = make_builder("Geometry & Maths")

FORMULAS = [
    f("circle_area", "Area of a circle", "Plane figures", "A = pi*r^2",
      {"A": ("Area", "m^2"), "r": ("Radius", "m")}),

    f("circle_circumference", "Circumference", "Plane figures", "C = 2*pi*r",
      {"C": ("Circumference", "m"), "r": ("Radius", "m")}),

    f("annulus_area", "Area of an annulus", "Plane figures",
      "A = pi*(ro^2 - ri^2)",
      {"A": ("Area", "m^2"), "ro": ("Outer radius", "m"),
       "ri": ("Inner radius", "m")}),

    f("triangle_area", "Area of a triangle", "Plane figures", "A = b*h/2",
      {"A": ("Area", "m^2"), "b": ("Base", "m"), "h": ("Height", "m")}),

    f("heron", "Heron's formula", "Plane figures",
      "A = sqrt(s*(s - a)*(s - b)*(s - c))",
      {"A": ("Area", "m^2"), "s": ("Semi-perimeter (a+b+c)/2", "m"),
       "a": ("Side a", "m"), "b": ("Side b", "m"), "c": ("Side c", "m")}),

    f("trapezoid_area", "Area of a trapezoid", "Plane figures",
      "A = (a + b)*h/2",
      {"A": ("Area", "m^2"), "a": ("Parallel side a", "m"),
       "b": ("Parallel side b", "m"), "h": ("Height", "m")}),

    f("pythagoras", "Pythagoras' theorem", "Triangles", "c^2 = a^2 + b^2",
      {"c": ("Hypotenuse", "m"), "a": ("Side a", "m"), "b": ("Side b", "m")}),

    f("cosine_rule", "Cosine rule", "Triangles",
      "c^2 = a^2 + b^2 - 2*a*b*cos(C)",
      {"c": ("Side opposite C", "m"), "a": ("Side a", "m"), "b": ("Side b", "m"),
       "C": ("Included angle", "rad")}),

    f("sine_rule", "Sine rule", "Triangles", "a/sin(A) = b/sin(B)",
      {"a": ("Side a", "m"), "A": ("Angle opposite a", "rad"),
       "b": ("Side b", "m"), "B": ("Angle opposite b", "rad")}),

    f("cylinder_volume", "Volume of a cylinder", "Solids", "V = pi*r^2*h",
      {"V": ("Volume", "m^3"), "r": ("Radius", "m"), "h": ("Height", "m")}),

    f("sphere_volume", "Volume of a sphere", "Solids", "V = 4*pi*r^3/3",
      {"V": ("Volume", "m^3"), "r": ("Radius", "m")}),

    f("sphere_area", "Surface area of a sphere", "Solids", "A = 4*pi*r^2",
      {"A": ("Surface area", "m^2"), "r": ("Radius", "m")}),

    f("cone_volume", "Volume of a cone", "Solids", "V = pi*r^2*h/3",
      {"V": ("Volume", "m^3"), "r": ("Base radius", "m"), "h": ("Height", "m")}),

    f("box_volume", "Volume of a rectangular prism", "Solids", "V = L*W*H",
      {"V": ("Volume", "m^3"), "L": ("Length", "m"), "W": ("Width", "m"),
       "H": ("Height", "m")}),

    f("distance_2d", "Distance between two points", "Coordinate geometry",
      "d = sqrt((x2 - x1)^2 + (y2 - y1)^2)",
      {"d": ("Distance", "m"), "x1": ("x1", "m"), "y1": ("y1", "m"),
       "x2": ("x2", "m"), "y2": ("y2", "m")}),

    f("line_slope", "Slope of a line", "Coordinate geometry",
      "m = (y2 - y1)/(x2 - x1)",
      {"m": ("Slope", "-"), "y2": ("y2", "-"), "y1": ("y1", "-"),
       "x2": ("x2", "-"), "x1": ("x1", "-")}),

    f("quadratic_root", "Quadratic formula (positive root)", "Algebra",
      "x = (-b + sqrt(b^2 - 4*a*c))/(2*a)",
      {"x": ("Root", "-"), "a": ("a", "-"), "b": ("b", "-"), "c": ("c", "-")}),

    f("percent_change", "Percentage change", "Arithmetic",
      "pc = (new_v - old_v)/old_v*100",
      {"pc": ("Percentage change", "%"), "new_v": ("New value", "-"),
       "old_v": ("Old value", "-")}),

    f("linear_interp", "Linear interpolation", "Arithmetic",
      "y = y1 + (x - x1)*(y2 - y1)/(x2 - x1)",
      {"y": ("Interpolated value", "-"), "x": ("Target x", "-"),
       "x1": ("Known x1", "-"), "y1": ("Known y1", "-"),
       "x2": ("Known x2", "-"), "y2": ("Known y2", "-")},
      tags=("interpolation", "table lookup")),

    f("compound_interest", "Compound growth", "Finance",
      "Aa = P*(1 + i/nc)^(nc*t)",
      {"Aa": ("Final amount", "currency"), "P": ("Principal", "currency"),
       "i": ("Annual rate as a fraction", "-", "0.05"),
       "nc": ("Compounds per year", "-", "12"), "t": ("Years", "-")}),

    f("npv_single", "Present value of a future sum", "Finance",
      "PV = FV/(1 + i)^n",
      {"PV": ("Present value", "currency"), "FV": ("Future value", "currency"),
       "i": ("Discount rate", "-", "0.08"), "n": ("Periods", "-")}),

    f("annuity_payment", "Loan/annuity payment", "Finance",
      "A = P*i*(1 + i)^n/((1 + i)^n - 1)",
      {"A": ("Payment per period", "currency"),
       "P": ("Principal", "currency"), "i": ("Rate per period", "-", "0.005"),
       "n": ("Number of periods", "-")},
      tags=("loan", "capital recovery")),

    f("breakeven", "Break-even quantity", "Finance",
      "Qb = FC/(price - vc)",
      {"Qb": ("Break-even units", "-"), "FC": ("Fixed costs", "currency"),
       "price": ("Selling price per unit", "currency"),
       "vc": ("Variable cost per unit", "currency")}),
]
