"""Control systems, signals and instrumentation."""

from ..model import make_builder

f = make_builder("Control & Signals")

FORMULAS = [
    f("second_order_wd", "Damped natural frequency", "Second order",
      "wd = wn*sqrt(1 - zeta^2)",
      {"wd": ("Damped natural frequency", "rad/s"),
       "wn": ("Undamped natural frequency", "rad/s"),
       "zeta": ("Damping ratio", "-", "0.7")}),

    f("overshoot", "Percentage overshoot", "Second order",
      "Mp = exp(-pi*zeta/sqrt(1 - zeta^2))*100",
      {"Mp": ("Overshoot", "%"), "zeta": ("Damping ratio", "-", "0.7")},
      assumptions="Step response of an underdamped second-order system."),

    f("settling_time", "2% settling time", "Second order",
      "ts = 4/(zeta*wn)",
      {"ts": ("Settling time", "s"), "zeta": ("Damping ratio", "-"),
       "wn": ("Natural frequency", "rad/s")}),

    f("rise_time", "Approximate rise time", "Second order",
      "tr = 1.8/wn",
      {"tr": ("Rise time", "s"), "wn": ("Natural frequency", "rad/s")},
      notes="Rule of thumb for a lightly damped second-order system."),

    f("first_order_step", "First-order step response", "First order",
      "y = K*U*(1 - exp(-t/tau))",
      {"y": ("Output", "-"), "K": ("Process gain", "-"),
       "U": ("Step size", "-"), "t": ("Time", "s"),
       "tau": ("Time constant", "s")}),

    f("steady_state_error", "Steady-state error, unity feedback step",
      "Performance", "ess = 1/(1 + Kp)",
      {"ess": ("Steady-state error", "-"), "Kp": ("Position error constant", "-")}),

    f("db_gain", "Gain in decibels", "Frequency response",
      "GdB = 20*log(G)/log(10)",
      {"GdB": ("Gain", "dB"), "G": ("Magnitude ratio", "-")}),

    f("bandwidth_rc", "First-order filter cutoff frequency",
      "Frequency response", "fc = 1/(2*pi*R*C)",
      {"fc": ("Cutoff frequency", "Hz"), "R": ("Resistance", "ohm"),
       "C": ("Capacitance", "F")}),

    f("nyquist_rate", "Nyquist sampling criterion", "Sampling",
      "fs = 2*fmax",
      {"fs": ("Minimum sampling rate", "Hz"),
       "fmax": ("Highest signal frequency", "Hz")},
      notes="Sample at 5-10x in practice to ease anti-alias filtering."),

    f("adc_resolution", "ADC resolution", "Instrumentation",
      "q = Vfs/2^Nb",
      {"q": ("Quantisation step", "V"), "Vfs": ("Full-scale range", "V"),
       "Nb": ("Number of bits", "-", "12")}),

    f("sensor_span", "Linear sensor scaling", "Instrumentation",
      "y = ymin + (x - xmin)*(ymax - ymin)/(xmax - xmin)",
      {"y": ("Engineering value", "-"), "ymin": ("Output at min", "-"),
       "ymax": ("Output at max", "-"), "x": ("Raw reading", "-"),
       "xmin": ("Raw minimum", "-"), "xmax": ("Raw maximum", "-")},
      notes="The classic 4-20 mA to engineering units conversion."),

    f("pid_output", "Parallel PID control law", "Controllers",
      "u = Kc*e + Ki*integral_e + Kd*de",
      {"u": ("Controller output", "-"), "Kc": ("Proportional gain", "-"),
       "e": ("Error", "-"), "Ki": ("Integral gain", "1/s"),
       "integral_e": ("Integral of error over time", "s"),
       "Kd": ("Derivative gain", "s"), "de": ("Derivative of error", "1/s")}),
]
