"""Text -> SymPy parsing.

Accepts the kind of input people actually type: ``2x^2 - 3x = 5``, ``sqrt(x-1)``,
``3e-4``, ``|x|``, ``pi``. Parsing is restricted to a whitelist of SymPy names so
that a stray ``__import__`` in the entry box cannot do anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMATIONS = standard_transformations + (
    convert_xor,                            # ^ means power, not xor
    implicit_multiplication_application,    # 2x, 3sin(x), x(x+1)
)

# Only these names are visible to the parser.
SAFE_FUNCTIONS = {
    # elementary
    "sqrt": sp.sqrt, "cbrt": sp.cbrt, "root": sp.root, "exp": sp.exp,
    "log": sp.log, "ln": sp.log, "log10": lambda x: sp.log(x, 10),
    "log2": lambda x: sp.log(x, 2), "Abs": sp.Abs, "abs": sp.Abs,
    "sign": sp.sign, "factorial": sp.factorial, "gamma": sp.gamma,
    # trig
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
    "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan, "atan2": sp.atan2,
    "acot": sp.acot, "asec": sp.asec, "acsc": sp.acsc,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    # hyperbolic
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "coth": sp.coth,
    "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
    # rounding / selection
    "floor": sp.floor, "ceiling": sp.ceiling, "ceil": sp.ceiling,
    "Min": sp.Min, "Max": sp.Max, "min": sp.Min, "max": sp.Max,
    "Mod": sp.Mod, "mod": sp.Mod,
    # special
    "erf": sp.erf, "erfc": sp.erfc, "besselj": sp.besselj, "bessely": sp.bessely,
    "Piecewise": sp.Piecewise, "re": sp.re, "im": sp.im, "conjugate": sp.conjugate,
    "deg": lambda x: x * sp.pi / 180, "rad": lambda x: x * 180 / sp.pi,
}

SAFE_CONSTANTS = {
    "pi": sp.pi, "PI": sp.pi, "E": sp.E, "e": sp.E, "I": sp.I, "j": sp.I,
    "oo": sp.oo, "inf": sp.oo, "infinity": sp.oo, "nan": sp.nan,
    "GoldenRatio": sp.GoldenRatio, "EulerGamma": sp.EulerGamma,
}

# The standard transformations rewrite literals as Integer(...)/Float(...) and
# bare names as Symbol(...), so those constructors must be reachable too.
_PARSER_INTERNALS = {
    "Symbol": sp.Symbol, "Integer": sp.Integer, "Float": sp.Float,
    "Rational": sp.Rational, "Function": sp.Function, "Eq": sp.Eq,
    # Written when a name with a digit in it is split into a product, which
    # is how `2x` works. Without it `T2 - T1` raised NameError rather than
    # parsing - the commonest pair of names in thermodynamics.
    "Number": sp.Number,
    # Written by core/odes.py when it turns y' into a derivative. Safe: it
    # builds an expression, it does not evaluate anything.
    "Derivative": sp.Derivative,
    # emitted when parsing with evaluate=False (display parsing)
    "Add": sp.Add, "Mul": sp.Mul, "Pow": sp.Pow,
}

GLOBAL_DICT = {**SAFE_FUNCTIONS, **SAFE_CONSTANTS, **_PARSER_INTERNALS}


#: Names SymPy would read as constants, but which engineers use as variables
#: at least as often: E for Young's modulus, I for second moment of area, e
#: for eccentricity. Left as symbols when a name is declared from free text.
AMBIGUOUS_CONSTANTS = {"E", "I", "e", "j"}

_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def symbols_in(text: str, skip=()) -> dict:
    """Every bare name in *text* declared as a plain symbol.

    Without this, implicit multiplication tears multi-letter names apart -
    `Re` becomes R times e, `dp` becomes d times p - and the equation is then
    quietly about different quantities than the one that was typed. Function
    names and the unambiguous constants (pi, oo) are left alone; E, I and e
    are not, because they are variables far more often than they are Euler's
    number or the square root of minus one.
    """
    reserved = set(SAFE_FUNCTIONS) | set(_PARSER_INTERNALS) | set(skip)
    constants = set(SAFE_CONSTANTS) - AMBIGUOUS_CONSTANTS
    found = {}
    # Preprocessed first, so a typed sigma is found under the name the
    # parser will actually see.
    for name in set(_NAME.findall(_preprocess(text or ""))):
        if name in reserved or name in constants:
            continue
        found[name] = sp.Symbol(name)
    return found

#: Greek names and their letters. The one place either is written down:
#: display.py reads it to draw a name, and UNICODE_MAP below is built by
#: reversing it so that anything shown can also be typed back in.
GREEK_NAMES = {
    "alpha": "\u03b1", "beta": "\u03b2", "gamma": "\u03b3",
    "delta": "\u03b4", "epsilon": "\u03b5", "zeta": "\u03b6",
    "eta": "\u03b7", "theta": "\u03b8", "iota": "\u03b9",
    "kappa": "\u03ba", "lambda": "\u03bb", "lambda_": "\u03bb",
    "mu": "\u03bc", "nu": "\u03bd", "xi": "\u03be", "pi": "\u03c0",
    "rho": "\u03c1", "sigma": "\u03c3", "tau": "\u03c4",
    "upsilon": "\u03c5", "phi": "\u03c6", "chi": "\u03c7",
    "psi": "\u03c8", "omega": "\u03c9",
    "Alpha": "\u0391", "Beta": "\u0392", "Gamma": "\u0393",
    "Delta": "\u0394", "Theta": "\u0398", "Lambda": "\u039b",
    "Xi": "\u039e", "Pi": "\u03a0", "Sigma": "\u03a3", "Phi": "\u03a6",
    "Psi": "\u03a8", "Omega": "\u03a9",
}

#: The letters a name may be spelled with, once Greek is allowed.
NAME_PATTERN = r"[A-Za-z_\u0370-\u03ff][A-Za-z0-9_\u0370-\u03ff]*"

# Unicode conveniences -> ASCII the parser understands.
UNICODE_MAP = {
    "−": "-", "–": "-", "—": "-", "×": "*", "·": "*", "÷": "/",
    "≤": "<=", "≥": ">=", "≠": "!=", "√": "sqrt", "π": "pi", "∞": "oo",
    "θ": "theta", "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
    "ε": "epsilon", "ζ": "zeta", "η": "eta", "λ": "lambda_", "μ": "mu",
    "ν": "nu", "ξ": "xi", "ρ": "rho", "σ": "sigma", "τ": "tau", "φ": "phi",
    "ϕ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega", "Δ": "Delta",
    "Ω": "Omega", "Σ": "Sigma", "Φ": "Phi", "²": "^2", "³": "^3", "½": "(1/2)",
    # U+2206 INCREMENT, not U+0394 GREEK CAPITAL LETTER DELTA. The two look
    # alike and mean different things: this one is a difference, so it reads
    # back as the d it was written with, and a variable genuinely called
    # Delta keeps the Greek letter and reads back as Delta.
    "\u2206": "d",
}

# Every Greek letter reads back as its name, so a letter put into a cell can
# be typed, parsed and re-read unchanged. The entries written by hand above
# take priority: lambda_ keeps clear of the Python keyword, and pi has to
# stay the constant rather than become a symbol called pi.
for _name, _letter in GREEK_NAMES.items():
    UNICODE_MAP.setdefault(_letter, _name)



def canonical_name(name: str) -> str:
    """The ASCII spelling of a name that may have been typed in Greek.

    ``rho`` and its letter are the same quantity, and anything keying off a
    name - a sheet resolving what its rows call each other - has to agree
    with the parser about that or the two spellings become two variables.
    """
    text = str(name or "").strip()
    for letter, ascii_name in UNICODE_MAP.items():
        if letter in text:
            text = text.replace(letter, ascii_name)
    return text


class ParseError(ValueError):
    """Raised when input cannot be turned into a SymPy object."""


@dataclass
class ParsedInput:
    """Result of parsing a line of user input."""

    raw: str
    expr: sp.Basic                      # Expr, Eq or Relational
    is_equation: bool = False
    symbols: list = field(default_factory=list)

    @property
    def free_symbol_names(self) -> list:
        return [s.name for s in self.symbols]


def _preprocess(text: str) -> str:
    s = text.strip()
    for bad, good in UNICODE_MAP.items():
        s = s.replace(bad, good)
    # |x + 1|  ->  Abs(x + 1)   (only for well-balanced simple cases)
    if s.count("|") >= 2 and s.count("|") % 2 == 0:
        parts = s.split("|")
        rebuilt = parts[0]
        for i in range(1, len(parts)):
            rebuilt += ("Abs(" if i % 2 == 1 else ")") + parts[i]
        s = rebuilt
    # 5x --> 5*x is handled by the transformation, but "3 4" is ambiguous: reject.
    s = re.sub(r"\s+", " ", s)
    return s


def parse_input(text: str, extra_symbols: dict | None = None) -> ParsedInput:
    """Parse ``text`` into an expression, equation or inequality."""
    if not text or not text.strip():
        raise ParseError("Nothing to parse.")

    s = _preprocess(text)
    local = dict(extra_symbols or {})

    # '!=' has to be built by hand. Python's `!=` is not overridable the way
    # `<=` is - SymPy returns Le(...) for one and a plain True/False for the
    # other - so parsing "x != 0" the ordinary way yields a bool, and the
    # free_symbols lookup below then fails with an AttributeError rather than
    # anything a user could act on.
    ne_positions = [m.start() for m in re.finditer(r"!=", s)]
    if ne_positions:
        if len(ne_positions) > 1:
            raise ParseError("Only one '!=' is understood at a time.")
        index = ne_positions[0]
        try:
            expr = sp.Ne(_parse_side(s[:index], local),
                         _parse_side(s[index + 2:], local))
        except ParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ParseError(f"Could not parse {text!r}: {exc}") from exc
        syms = sorted(expr.free_symbols, key=lambda x: x.name)
        return ParsedInput(raw=text, expr=expr, is_equation=True, symbols=syms)

    # Split on a single '=' that is not part of ==, <=, >=, !=
    eq_positions = [
        m.start() for m in re.finditer(r"(?<![<>!=])=(?!=)", s)
    ]
    try:
        if len(eq_positions) > 1:
            raise ParseError("More than one '=' found. Use ';' to separate equations.")
        if eq_positions:
            i = eq_positions[0]
            lhs = _parse_side(s[:i], local)
            rhs = _parse_side(s[i + 1:], local)
            expr = sp.Eq(lhs, rhs)
            is_eq = True
        else:
            expr = _parse_side(s, local)
            is_eq = isinstance(expr, sp.Eq) or isinstance(expr, sp.Rel)
    except ParseError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface a readable message
        raise ParseError(f"Could not parse {text!r}: {exc}") from exc

    syms = sorted(expr.free_symbols, key=lambda x: x.name)
    return ParsedInput(raw=text, expr=expr, is_equation=is_eq, symbols=syms)


def _parse_side(text: str, local: dict, evaluate: bool = True) -> sp.Expr:
    text = text.strip()
    if not text:
        raise ParseError("Empty side of an equation.")
    if "__" in text or "lambda" == text.strip():
        raise ParseError("Illegal token.")
    return parse_expr(
        text,
        local_dict=local,
        global_dict=GLOBAL_DICT,
        transformations=TRANSFORMATIONS,
        evaluate=evaluate,
    )


#: A run of two or more letters, which the parser reads as a product unless
#: the name has been declared. Digits count as part of the run: `T1` is read
#: as T times 1.
_RUN = re.compile(r"[A-Za-z][A-Za-z0-9]+")


def names_read_as_products(text: str, expression=None) -> list:
    """Multi-letter runs in *text* that were read as several things.

    Only the ones that really were split, checked against what came out
    rather than guessed at from the spelling - `sin` is a function and `mm`
    might be a declared name, and neither should be reported.
    """
    if not text:
        return []
    survived = set()
    if expression is not None:
        try:
            survived = {s.name for s in expression.free_symbols}
        except AttributeError:
            survived = set()
    found = []
    for run in _RUN.findall(_preprocess(text)):
        if run in survived or run in GLOBAL_DICT or run in found:
            continue
        found.append(run)
    return found


def parse_for_display(text: str, extra_symbols: dict | None = None):
    """Parse without simplifying, so the terms keep the order they were typed.

    SymPy normally reorders as it evaluates - ``u + a*t`` comes back as
    ``a*t + u``. For anything shown to the user we want their own arrangement,
    so this variant parses with ``evaluate=False``. Falls back to the normal
    parse if the unevaluated form cannot be built.
    """
    local = dict(extra_symbols or {})
    cleaned = _preprocess(text)
    positions = [m.start() for m in re.finditer(r"(?<![<>!=])=(?!=)", cleaned)]
    try:
        if len(positions) == 1:
            index = positions[0]
            lhs = _parse_side(cleaned[:index], local, evaluate=False)
            rhs = _parse_side(cleaned[index + 1:], local, evaluate=False)
            return sp.Eq(lhs, rhs, evaluate=False)
        if not positions:
            return _parse_side(cleaned, local, evaluate=False)
    except Exception:  # noqa: BLE001 - fall back to the evaluated form
        pass
    return parse_input(text, extra_symbols).expr


def parse_system(text: str, extra_symbols: dict | None = None) -> list:
    """Parse several equations separated by ';' or newlines."""
    chunks = [c for c in re.split(r"[;\n]+", text) if c.strip()]
    return [parse_input(c, extra_symbols) for c in chunks]


def parse_number(text: str):
    """Parse a single numeric entry (accepts ``2/3``, ``1.5e3``, ``pi/4``)."""
    if text is None or str(text).strip() == "":
        return None
    return _parse_side(str(text), {})
