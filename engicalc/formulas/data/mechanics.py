"""Statics, kinematics and dynamics."""

from ..model import make_builder

f = make_builder("Mechanics")

FORMULAS = [
    f("newton_second", "Newton's second law", "Dynamics", "F = m*a",
      {"F": ("Resultant force", "N"), "m": ("Mass", "kg"),
       "a": ("Acceleration", "m/s^2")},
      tags=("force", "acceleration")),

    f("kinematic_v", "Velocity after time (constant a)", "Kinematics",
      "v = u + a*t",
      {"v": ("Final velocity", "m/s"), "u": ("Initial velocity", "m/s"),
       "a": ("Acceleration", "m/s^2"), "t": ("Time", "s")},
      assumptions="Constant acceleration, straight line motion."),

    f("kinematic_s", "Displacement (constant a)", "Kinematics",
      "s = u*t + a*t^2/2",
      {"s": ("Displacement", "m"), "u": ("Initial velocity", "m/s"),
       "a": ("Acceleration", "m/s^2"), "t": ("Time", "s")},
      assumptions="Constant acceleration."),

    f("kinematic_v2", "Velocity-displacement relation", "Kinematics",
      "v^2 = u^2 + 2*a*s",
      {"v": ("Final velocity", "m/s"), "u": ("Initial velocity", "m/s"),
       "a": ("Acceleration", "m/s^2"), "s": ("Displacement", "m")},
      assumptions="Constant acceleration."),

    f("projectile_range", "Projectile range on level ground", "Kinematics",
      "R = v0^2*sin(2*theta)/g",
      {"R": ("Horizontal range", "m"), "v0": ("Launch speed", "m/s"),
       "theta": ("Launch angle", "rad"), "g": ("Gravity", "m/s^2", "9.80665")},
      assumptions="No drag, launch and landing at the same height."),

    f("kinetic_energy", "Kinetic energy", "Energy", "KE = m*v^2/2",
      {"KE": ("Kinetic energy", "J"), "m": ("Mass", "kg"),
       "v": ("Speed", "m/s")}),

    f("potential_energy", "Gravitational potential energy", "Energy",
      "PE = m*g*h",
      {"PE": ("Potential energy", "J"), "m": ("Mass", "kg"),
       "g": ("Gravity", "m/s^2", "9.80665"), "h": ("Height", "m")}),

    f("work_done", "Work done by a force", "Energy", "W = F*d*cos(theta)",
      {"W": ("Work", "J"), "F": ("Force", "N"), "d": ("Displacement", "m"),
       "theta": ("Angle between force and displacement", "rad")}),

    f("power_force", "Mechanical power", "Energy", "P = F*v",
      {"P": ("Power", "W"), "F": ("Force", "N"), "v": ("Velocity", "m/s")}),

    f("momentum", "Linear momentum", "Dynamics", "p = m*v",
      {"p": ("Momentum", "kg*m/s"), "m": ("Mass", "kg"), "v": ("Velocity", "m/s")}),

    f("impulse", "Impulse-momentum", "Dynamics", "J = F*dt",
      {"J": ("Impulse", "N*s"), "F": ("Average force", "N"),
       "dt": ("Duration", "s")}),

    f("torque", "Torque about a point", "Statics", "T = F*r*sin(theta)",
      {"T": ("Torque", "N*m"), "F": ("Force", "N"), "r": ("Lever arm", "m"),
       "theta": ("Angle between r and F", "rad")}),

    f("friction", "Coulomb friction", "Statics", "Ff = mu*N",
      {"Ff": ("Friction force", "N"), "mu": ("Coefficient of friction", "-"),
       "N": ("Normal force", "N")},
      notes="Use the static coefficient up to impending motion, kinetic after."),

    f("centripetal", "Centripetal force", "Dynamics", "Fc = m*v^2/r",
      {"Fc": ("Centripetal force", "N"), "m": ("Mass", "kg"),
       "v": ("Tangential speed", "m/s"), "r": ("Radius", "m")}),

    f("angular_kinematics", "Rotational analogue of F = ma", "Rotation",
      "T = I*alpha",
      {"T": ("Torque", "N*m"), "I": ("Mass moment of inertia", "kg*m^2"),
       "alpha": ("Angular acceleration", "rad/s^2")}),

    f("rotational_ke", "Rotational kinetic energy", "Rotation",
      "KE = I*omega^2/2",
      {"KE": ("Rotational kinetic energy", "J"),
       "I": ("Mass moment of inertia", "kg*m^2"),
       "omega": ("Angular velocity", "rad/s")}),

    f("shaft_power", "Shaft power from torque and speed", "Rotation",
      "P = T*omega",
      {"P": ("Power", "W"), "T": ("Torque", "N*m"),
       "omega": ("Angular velocity", "rad/s")},
      notes="omega = 2*pi*N/60 when N is in rev/min."),

    f("gear_ratio", "Gear ratio", "Machines", "i = N2/N1",
      {"i": ("Gear ratio", "-"), "N2": ("Teeth on driven gear", "-"),
       "N1": ("Teeth on driving gear", "-")}),

    f("spring_force", "Hooke's law (spring)", "Vibration", "F = k*x",
      {"F": ("Spring force", "N"), "k": ("Spring stiffness", "N/m"),
       "x": ("Deflection", "m")}),

    f("natural_frequency", "Undamped natural frequency", "Vibration",
      "fn = sqrt(k/m)/(2*pi)",
      {"fn": ("Natural frequency", "Hz"), "k": ("Stiffness", "N/m"),
       "m": ("Mass", "kg")},
      tags=("vibration", "resonance")),

    f("damping_ratio", "Damping ratio", "Vibration", "zeta = c/(2*sqrt(k*m))",
      {"zeta": ("Damping ratio", "-"), "c": ("Damping coefficient", "N*s/m"),
       "k": ("Stiffness", "N/m"), "m": ("Mass", "kg")},
      notes="zeta < 1 underdamped, = 1 critical, > 1 overdamped."),

    f("belt_friction", "Capstan (belt friction) equation", "Machines",
      "T1 = T2*exp(mu*beta)",
      {"T1": ("Tight side tension", "N"), "T2": ("Slack side tension", "N"),
       "mu": ("Coefficient of friction", "-"),
       "beta": ("Angle of wrap", "rad")}),
]
