"""The symbol pad.

One list of items drives three things: the buttons on the calculator, the
searchable reference window, and the syntax documentation. They cannot drift
apart because they are all built from :data:`PAD`.

``insert``      text pushed into the entry box
``back``        how many characters to move the caret left afterwards, so the
                caret lands inside the brackets
``operation``   for the calculus items - switches the operation selector
                instead of typing anything
``template``    a :mod:`ui.mathfield` template key. When set, the button draws
                the shape in the equation bar with empty boxes to type into,
                rather than inserting ASCII. ``insert`` remains the fallback
                for anywhere the typeset field is not in use.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PadItem:
    key: str
    label: str                  # LaTeX drawn on the button
    name: str                   # plain-English name
    markup: str                 # what the user types
    insert: str = ""            # what the button inserts
    back: int = 0               # caret offset from the end of the insertion
    example: str = ""
    example_latex: str = ""
    group: str = "Basic"
    operation: str = ""         # sets the operation selector instead
    note: str = ""
    common: bool = False        # shown on the compact one-row pad
    template: str = ""          # mathfield template key, if it has a shape

    def inserted_text(self) -> str:
        return self.insert or self.markup


def _i(key, label, name, markup, insert=None, back=0, example="",
       example_latex="", group="Basic", operation="", note="", common=False,
       template=""):
    return PadItem(key=key, label=label, name=name, markup=markup,
                   insert=markup if insert is None else insert, back=back,
                   example=example, example_latex=example_latex, group=group,
                   operation=operation, note=note, common=common,
                   template=template)


PAD: list[PadItem] = [
    # -- powers and roots -------------------------------------------------
    _i("square", r"x^2", "Square", "^2", "^2", 0, "3x^2 - 5",
       r"3x^{2}-5", "Powers & roots", common=True,
       template="power"),
    _i("power", r"x^{n}", "Power", "^( )", "^()", 1, "x^(n + 1)",
       r"x^{n+1}", "Powers & roots",
       note="Brackets keep the whole exponent together.", common=True,
       template="power"),
    _i("sqrt", r"\sqrt{x}", "Square root", "sqrt( )", "sqrt()", 1,
       "sqrt(x^2 + y^2)", r"\sqrt{x^{2}+y^{2}}", "Powers & roots", common=True,
       template="sqrt"),
    _i("nthroot", r"\sqrt[n]{x}", "nth root", "root( , n)", "root(,3)", 3,
       "root(x, 3)", r"\sqrt[3]{x}", "Powers & roots",
       note="Or use a fractional power: x^(1/3).", common=True,
       template="nthroot"),
    _i("cbrt", r"\sqrt[3]{x}", "Cube root", "cbrt( )", "cbrt()", 1,
       "cbrt(27)", r"\sqrt[3]{27}", "Powers & roots"),
    _i("exp", r"e^{x}", "Exponential", "exp( )", "exp()", 1, "exp(-x/tau)",
       r"e^{-x/\tau}", "Powers & roots", note="e^x works too.",
       template="exp"),

    # -- basic arithmetic --------------------------------------------------
    _i("frac", r"\frac{a}{b}", "Fraction", "( )/( )", "()/()", 4,
       "(a + b)/(2c)", r"\frac{a+b}{2c}", "Basic", common=True,
       template="frac"),
    _i("times", r"\cdot", "Multiply", "*", "*", 0, "2*pi*r", r"2\pi r",
       "Basic", note="2x and 3sin(x) are understood without the *.", common=True),
    _i("divide", r"\div", "Divide", "/", "/", 0, "Q/A", r"\frac{Q}{A}",
       "Basic", common=True),
    _i("abs", r"\left|x\right|", "Absolute value", "abs( )", "abs()", 1,
       "abs(3x + 1) = 4", r"\left|3x+1\right|=4", "Basic",
       note="Vertical bars work as well: |3x + 1|.", template="abs"),
    _i("paren", r"(x)", "Brackets", "( )", "()", 1, "2(x + 3)",
       r"2(x+3)", "Basic", template="paren"),
    _i("degree", r"x^{\circ}", "Degrees to radians", "deg( )", "deg()", 1,
       "sin(deg(30))", r"\sin\left(30^{\circ}\right)", "Basic",
       note="Trig functions work in radians; deg() converts for you."),

    # -- logs --------------------------------------------------------------
    _i("ln", r"\ln", "Natural log", "log( )", "log()", 1, "log(x) = 2",
       r"\ln x = 2", "Logarithms",
       note="log() is the natural log, as in most engineering texts.",
       common=True),
    _i("log_base", r"\log_{b}", "Log to a base", "log( , b)", "log(,10)", 4,
       "log(1000, 10)", r"\log_{10}1000", "Logarithms", common=True,
       template="logbase"),
    _i("log10", r"\log_{10}", "Log base 10", "log10( )", "log10()", 1,
       "log10(x)", r"\log_{10}x", "Logarithms"),
    _i("log2", r"\log_{2}", "Log base 2", "log2( )", "log2()", 1, "log2(x)",
       r"\log_{2}x", "Logarithms"),

    # -- calculus ----------------------------------------------------------
    _i("prime", r"f'(x)", "Derivative", "derivative", "", 0, "sin(x^2)",
       r"\frac{d}{dx}\sin\left(x^{2}\right)", "Calculus", operation="derivative",
       note="Sets the operation to derivative; type just the expression.",
       common=True),
    _i("ddx", r"\frac{d}{dx}", "Derivative in x", "derivative", "", 0,
       "x^3 - 2x", r"\frac{d}{dx}\left(x^{3}-2x\right)", "Calculus",
       operation="derivative", common=True, template="deriv"),
    _i("partial", r"\frac{\partial}{\partial x}", "Partial derivative",
       "derivative + variable", "", 0, "x^2*y",
       r"\frac{\partial}{\partial x}\left(x^{2}y\right)", "Calculus",
       operation="derivative",
       note="Set Variable to the one you are differentiating with respect to."),
    _i("integral", r"\int", "Indefinite integral", "integral", "", 0,
       "x*sin(x)", r"\int x\sin x\,dx", "Calculus", operation="integral",
       common=True, template="indefint"),
    _i("defint", r"\int_{a}^{b}", "Definite integral", "integral + from/to",
       "", 0, "x*sin(x) from 0 to pi", r"\int_{0}^{\pi}x\sin x\,dx",
       "Calculus", operation="integral",
       note="Type the limits straight into the boxes.", common=True,
       template="defint"),
    _i("limit", r"\lim", "Limit", "limit", "", 0, "sin(x)/x at 0",
       r"\lim_{x\to 0}\frac{\sin x}{x}", "Calculus", operation="limit",
       common=True, template="limit"),
    _i("series", r"\sum", "Series expansion", "series", "", 0, "exp(x) at 0",
       r"1+x+\frac{x^{2}}{2}+\ldots", "Calculus", operation="series",
       note="Taylor expansion about the point you give.", common=True),

    # -- trig --------------------------------------------------------------
    _i("sin", r"\sin", "Sine", "sin( )", "sin()", 1, "sin(x) + cos(x) = 1",
       r"\sin x+\cos x=1", "Trigonometry", common=True),
    _i("cos", r"\cos", "Cosine", "cos( )", "cos()", 1, "cos(2x)",
       r"\cos 2x", "Trigonometry", common=True),
    _i("tan", r"\tan", "Tangent", "tan( )", "tan()", 1, "tan(theta) = 0.5",
       r"\tan\theta=0.5", "Trigonometry"),
    _i("asin", r"\sin^{-1}", "Inverse sine", "asin( )", "asin()", 1,
       "asin(0.5)", r"\sin^{-1}0.5", "Trigonometry"),
    _i("acos", r"\cos^{-1}", "Inverse cosine", "acos( )", "acos()", 1,
       "acos(x)", r"\cos^{-1}x", "Trigonometry"),
    _i("atan", r"\tan^{-1}", "Inverse tangent", "atan( )", "atan()", 1,
       "atan(y/x)", r"\tan^{-1}\frac{y}{x}", "Trigonometry"),
    _i("atan2", r"\mathrm{atan2}", "Two-argument arctangent", "atan2(y, x)",
       "atan2(,)", 3, "atan2(3, 4)", r"\mathrm{atan2}(3,4)", "Trigonometry",
       note="Gives the angle in the correct quadrant."),
    _i("sinh", r"\sinh", "Hyperbolic sine", "sinh( )", "sinh()", 1, "sinh(x)",
       r"\sinh x", "Trigonometry",
       note="cosh, tanh and the inverses asinh, acosh, atanh all work."),

    # -- constants and Greek ----------------------------------------------
    _i("pi", r"\pi", "Pi", "pi", "pi", 0, "2*pi*r", r"2\pi r",
       "Constants & Greek", common=True),
    _i("euler", r"e", "Euler's number", "E", "E", 0, "E^x", r"e^{x}",
       "Constants & Greek",
       note="Capital E, because lowercase e is free to use as a variable."),
    _i("infinity", r"\infty", "Infinity", "oo", "oo", 0, "limit at oo",
       r"\lim_{x\to\infty}", "Constants & Greek", common=True),
    _i("imag", r"i", "Imaginary unit", "I", "I", 0, "2 + 3I", r"2+3i",
       "Constants & Greek"),
    _i("theta", r"\theta", "Theta", "theta", "theta", 0, "sin(theta)",
       r"\sin\theta", "Constants & Greek", common=True),
    _i("alpha", r"\alpha", "Alpha", "alpha", "alpha", 0, "alpha*L*dT",
       r"\alpha L\Delta T", "Constants & Greek"),
    _i("rho", r"\rho", "Rho", "rho", "rho", 0, "rho*g*h", r"\rho gh",
       "Constants & Greek"),
    _i("mu", r"\mu", "Mu", "mu", "mu", 0, "rho*v*D/mu",
       r"\frac{\rho vD}{\mu}", "Constants & Greek"),
    _i("sigma", r"\sigma", "Sigma", "sigma", "sigma", 0, "sigma = F/A",
       r"\sigma=\frac{F}{A}", "Constants & Greek"),
    _i("omega", r"\omega", "Omega", "omega", "omega", 0, "P = T*omega",
       r"P=T\omega", "Constants & Greek",
       note="Type any Greek name: beta, gamma, delta, eta, lambda_, nu, phi, tau."),

    # -- relations ---------------------------------------------------------
    _i("equals", r"=", "Equation", "=", "=", 0, "2x + 1 = 7", r"2x+1=7",
       "Relations", note="One '=' per line.", common=True),
    _i("le", r"\leq", "Less than or equal", "<=", "<=", 0, "x^2 <= 9",
       r"x^{2}\leq 9", "Relations", common=True),
    _i("ge", r"\geq", "Greater than or equal", ">=", ">=", 0, "x >= -2",
       r"x\geq -2", "Relations", common=True),
    _i("ne", r"\neq", "Not equal", "!=", "!=", 0, "x != 0", r"x\neq 0",
       "Relations"),
    _i("system", r";", "Simultaneous equations", ";", "; ", 0,
       "x + y = 10; x - y = 2", r"x+y=10 \quad\mathrm{and}\quad x-y=2",
       "Relations", note="Separate each equation with a semicolon.",
       common=True),

    # -- functions and misc ------------------------------------------------
    _i("compose", r"(f \circ g)", "Composition", "f(g(x))", "f(g(x))", 0,
       "sin(log(x))", r"\sin\left(\ln x\right)", "Functions",
       note="Just nest the brackets."),
    _i("fx", r"f(x)", "Function of x", "f(x)", "f(x)", 0, "f(x) = 2x + 1",
       r"f(x)=2x+1", "Functions"),
    _i("min", r"\min", "Minimum", "min( , )", "min(,)", 3, "min(a, b)",
       r"\min(a,b)", "Functions"),
    _i("max", r"\max", "Maximum", "max( , )", "max(,)", 3, "max(a, b)",
       r"\max(a,b)", "Functions"),
    _i("floor", r"\lfloor x \rfloor", "Round down", "floor( )",
       "floor()", 1, "floor(7/2)", r"\lfloor 3.5 \rfloor", "Functions"),
    _i("ceil", r"\lceil x \rceil", "Round up", "ceiling( )",
       "ceiling()", 1, "ceiling(7/2)", r"\lceil 3.5 \rceil", "Functions"),
    _i("factorial", r"n!", "Factorial", "factorial( )", "factorial()", 1,
       "factorial(5)", r"5!", "Functions"),
    _i("sci", r"\times 10^{n}", "Scientific notation", "1.5e-3", "e-3", 0,
       "E = 200e9", r"E=200\times 10^{9}", "Functions",
       note="Write the mantissa, then e, then the exponent."),
]

GROUPS = ["Basic", "Powers & roots", "Logarithms", "Calculus", "Trigonometry",
          "Constants & Greek", "Relations", "Functions"]

SYNTAX_NOTES = [
    ("Implicit multiplication",
     "2x, 3sin(x) and 2(x + 1) all mean what you expect - the * is optional "
     "between a number and a symbol."),
    ("Powers", "Use ^ or **. Wrap anything longer than one character in "
               "brackets: x^(n + 1), not x^n + 1."),
    ("Exact vs decimal",
     "2/3 stays exact and prints as a fraction; 0.667 is treated as a decimal. "
     "Mixing them is fine."),
    ("Variable names",
     "Any letters and digits: T2, fD, m_f, sigma_y. Trailing digits and "
     "anything after an underscore are drawn as subscripts."),
    ("Greek letters",
     "Type the name (rho, mu, theta) or paste the character itself - both are "
     "understood. Use lambda_ for lambda, since lambda is reserved in Python."),
    ("Reserved names",
     "E is Euler's number, I is the imaginary unit and oo is infinity. "
     "Lowercase e, i and o are free to use as variables."),
    ("Solving for a variable",
     "Put the letter you want in the Variable box. Leave it as x for ordinary "
     "algebra."),
    ("Simultaneous equations",
     "Separate them with semicolons and the operation switches to system "
     "automatically: x + y = 10; x - y = 2"),
]


def by_group() -> dict:
    out: dict = {}
    for item in PAD:
        out.setdefault(item.group, []).append(item)
    return {group: out[group] for group in GROUPS if group in out}


def common_items() -> list:
    return [item for item in PAD if item.common]


def find(query: str) -> list:
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return list(PAD)
    results = []
    for item in PAD:
        text = " ".join([item.name, item.markup, item.example, item.note,
                         item.group]).lower()
        if all(term in text for term in terms):
            results.append(item)
    return results
