"""DC and AC circuits, machines and power."""

from ..model import make_builder

f = make_builder("Electrical")

FORMULAS = [
    f("ohms_law", "Ohm's law", "DC circuits", "V = I*R",
      {"V": ("Voltage", "V"), "I": ("Current", "A"), "R": ("Resistance", "ohm")},
      tags=("ohm", "resistance")),

    f("power_dc", "DC power", "DC circuits", "P = V*I",
      {"P": ("Power", "W"), "V": ("Voltage", "V"), "I": ("Current", "A")}),

    f("power_resistive", "Power dissipated in a resistor", "DC circuits",
      "P = I^2*R",
      {"P": ("Power", "W"), "I": ("Current", "A"), "R": ("Resistance", "ohm")}),

    f("resistivity", "Resistance of a conductor", "DC circuits",
      "R = rho_e*L/A",
      {"R": ("Resistance", "ohm"), "rho_e": ("Resistivity", "ohm*m", "1.68e-8"),
       "L": ("Conductor length", "m"),
       "A": ("Cross-sectional area", "m^2")},
      made_of={"rho_e": "resistivity"},
      notes="Copper resistivity at 20 C is about 1.68e-8 ohm*m."),

    f("series_resistance", "Resistors in series", "Networks",
      "Rt = R1 + R2 + R3",
      {"Rt": ("Total resistance", "ohm"), "R1": ("R1", "ohm"),
       "R2": ("R2", "ohm"), "R3": ("R3", "ohm", "0")}),

    f("parallel_resistance", "Two resistors in parallel", "Networks",
      "Rt = R1*R2/(R1 + R2)",
      {"Rt": ("Total resistance", "ohm"), "R1": ("R1", "ohm"),
       "R2": ("R2", "ohm")}),

    f("voltage_divider", "Voltage divider", "Networks",
      "Vout = Vin*R2/(R1 + R2)",
      {"Vout": ("Output voltage", "V"), "Vin": ("Input voltage", "V"),
       "R1": ("Upper resistor", "ohm"), "R2": ("Lower resistor", "ohm")}),

    f("capacitance_energy", "Energy stored in a capacitor", "Storage",
      "E = C*V^2/2",
      {"E": ("Stored energy", "J"), "C": ("Capacitance", "F"),
       "V": ("Voltage", "V")}),

    f("inductor_energy", "Energy stored in an inductor", "Storage",
      "E = L*I^2/2",
      {"E": ("Stored energy", "J"), "L": ("Inductance", "H"),
       "I": ("Current", "A")}),

    f("rc_time_constant", "RC time constant", "Transients", "tau = R*C",
      {"tau": ("Time constant", "s"), "R": ("Resistance", "ohm"),
       "C": ("Capacitance", "F")},
      notes="Reaches 63.2% of the final value in one time constant."),

    f("rc_charging", "Capacitor charging voltage", "Transients",
      "Vc = Vs*(1 - exp(-t/(R*C)))",
      {"Vc": ("Capacitor voltage", "V"), "Vs": ("Supply voltage", "V"),
       "t": ("Time", "s"), "R": ("Resistance", "ohm"),
       "C": ("Capacitance", "F")}),

    f("capacitive_reactance", "Capacitive reactance", "AC circuits",
      "Xc = 1/(2*pi*fr*C)",
      {"Xc": ("Capacitive reactance", "ohm"), "fr": ("Frequency", "Hz"),
       "C": ("Capacitance", "F")}),

    f("inductive_reactance", "Inductive reactance", "AC circuits",
      "Xl = 2*pi*fr*L",
      {"Xl": ("Inductive reactance", "ohm"), "fr": ("Frequency", "Hz"),
       "L": ("Inductance", "H")}),

    f("impedance_rlc", "Series RLC impedance magnitude", "AC circuits",
      "Z = sqrt(R^2 + (Xl - Xc)^2)",
      {"Z": ("Impedance magnitude", "ohm"), "R": ("Resistance", "ohm"),
       "Xl": ("Inductive reactance", "ohm"),
       "Xc": ("Capacitive reactance", "ohm")}),

    f("resonant_frequency", "LC resonant frequency", "AC circuits",
      "fr = 1/(2*pi*sqrt(L*C))",
      {"fr": ("Resonant frequency", "Hz"), "L": ("Inductance", "H"),
       "C": ("Capacitance", "F")},
      tags=("resonance",)),

    f("rms_sine", "RMS value of a sine wave", "AC circuits",
      "Vrms = Vpk/sqrt(2)",
      {"Vrms": ("RMS voltage", "V"), "Vpk": ("Peak voltage", "V")}),

    f("ac_power", "Single-phase real power", "Power",
      "P = V*I*cos(phi)",
      {"P": ("Real power", "W"), "V": ("RMS voltage", "V"),
       "I": ("RMS current", "A"), "phi": ("Phase angle", "rad")},
      notes="cos(phi) is the power factor."),

    f("three_phase_power", "Three-phase real power", "Power",
      "P = sqrt(3)*VL*IL*pf",
      {"P": ("Real power", "W"), "VL": ("Line voltage", "V"),
       "IL": ("Line current", "A"), "pf": ("Power factor", "-", "0.85")}),

    f("transformer_ratio", "Ideal transformer ratio", "Machines",
      "Vs/Vp = Ns/Np",
      {"Vs": ("Secondary voltage", "V"), "Vp": ("Primary voltage", "V"),
       "Ns": ("Secondary turns", "-"), "Np": ("Primary turns", "-")}),

    f("motor_speed", "Synchronous speed of an AC machine", "Machines",
      "Ns = 120*fr/P",
      {"Ns": ("Synchronous speed", "rev/min"), "fr": ("Supply frequency", "Hz"),
       "P": ("Number of poles", "-")}),

    f("slip", "Induction motor slip", "Machines", "s = (Ns - Nr)/Ns",
      {"s": ("Slip", "-"), "Ns": ("Synchronous speed", "rev/min"),
       "Nr": ("Rotor speed", "rev/min")}),

    f("voltage_drop_cable", "Cable voltage drop (single phase)",
      "Installation", "Vd = 2*I*rho_e*L/A",
      {"Vd": ("Voltage drop", "V"), "I": ("Current", "A"),
       "rho_e": ("Resistivity", "ohm*m", "1.68e-8"),
       "L": ("One-way cable length", "m"), "A": ("Conductor area", "m^2")},
      made_of={"rho_e": "resistivity"}),

    f("energy_cost", "Energy cost of running a load", "Power",
      "Cost = P*t*rate/1000",
      {"Cost": ("Cost", "currency"), "P": ("Power", "W"),
       "t": ("Hours of operation", "h"),
       "rate": ("Tariff per kWh", "currency/kWh", "0.28")}),
]
