"""Complex numbers the way an engineer uses them: as phasors.

The arithmetic was already there - SymPy has done complex numbers all along,
and `(3+4j)*(1-2j)` has always given `11 - 2*I`. What was missing is
everything around it, which is most of what the subject is used for: the
magnitude and angle, the conjugate, and the picture.

An impedance is quoted as `5 angle 53.1 deg` at least as often as `3 + 4j`,
and converting between the two by hand is where the sign errors live - the
arctangent has to know which quadrant it is in, and `atan(y/x)` does not.
That is done here with a two-argument arctangent, which does.

`j` rather than `i` throughout, because that is what it is called wherever
there is also a current to talk about.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

import sympy as sp

from .parsing import ParseError, parse_input

#: How the angle is quoted. Degrees by default - a phasor diagram is marked
#: in degrees, whatever the maths underneath prefers.
DEGREES = "degrees"
RADIANS = "radians"


class PhasorError(ParseError):
    """Raised when something cannot be read as a complex number."""


@dataclass
class Phasor:
    """One complex number, in both the forms it gets written in."""

    real: float
    imaginary: float
    angle_unit: str = DEGREES

    @property
    def magnitude(self) -> float:
        return math.hypot(self.real, self.imaginary)

    @property
    def angle(self) -> float:
        """The argument, in whichever unit was asked for.

        From a two-argument arctangent, so it knows which quadrant it is in.
        `atan(y/x)` cannot tell 1+1j from -1-1j, and quietly returns the
        same 45 degrees for both.
        """
        radians = math.atan2(self.imaginary, self.real)
        return math.degrees(radians) if self.angle_unit == DEGREES \
            else radians

    @property
    def conjugate(self) -> "Phasor":
        return Phasor(self.real, -self.imaginary, self.angle_unit)

    def as_rectangular(self) -> str:
        sign = "+" if self.imaginary >= 0 else "-"
        return f"{self.real:g} {sign} {abs(self.imaginary):g}j"

    def as_polar(self) -> str:
        mark = "deg" if self.angle_unit == DEGREES else "rad"
        return f"{self.magnitude:g} ∠ {self.angle:g} {mark}"

    def rows(self) -> list:
        """(symbol, name, value, unit), the symbol first."""
        return [
            ("Re", "real part", self.real, ""),
            ("Im", "imaginary part", self.imaginary, ""),
            ("|z|", "magnitude", self.magnitude, ""),
            ("∠z", "argument", self.angle,
             "degrees" if self.angle_unit == DEGREES else "radians"),
            ("z*", "conjugate", self.conjugate.as_rectangular(), ""),
        ]


def from_rectangular(real: float, imaginary: float,
                     angle_unit: str = DEGREES) -> Phasor:
    return Phasor(float(real), float(imaginary), angle_unit)


def from_polar(magnitude: float, angle: float,
               angle_unit: str = DEGREES) -> Phasor:
    """Build a phasor from its magnitude and argument."""
    radians = math.radians(angle) if angle_unit == DEGREES else float(angle)
    return Phasor(magnitude * math.cos(radians),
                  magnitude * math.sin(radians), angle_unit)


def read(text: str, angle_unit: str = DEGREES) -> Phasor:
    """Read a complex number written any of the usual ways.

    `3+4j`, `3+4i`, and `5 angle 53.13` all mean the same thing and all get
    written, so all three are accepted. The angle form uses whatever unit is
    currently selected, since a number written `5 < 30` is meaningless
    without knowing which.
    """
    written = (text or "").strip()
    if not written:
        raise PhasorError("Nothing to read.")

    # The polar forms people actually type.
    for mark in ("∠", "<", "angle", "@"):
        if mark in written:
            left, _, right = written.partition(mark)
            try:
                return from_polar(float(sp.N(parse_input(left).expr)),
                                  float(sp.N(parse_input(right).expr)),
                                  angle_unit)
            except (ParseError, TypeError, ValueError) as exc:
                raise PhasorError(
                    f"Could not read {written!r} as a magnitude and an "
                    f"angle: {exc}") from exc

    try:
        value = complex(sp.N(parse_input(written).expr))
    except (ParseError, TypeError, ValueError) as exc:
        raise PhasorError(
            f"Could not read {written!r} as a complex number. Write it as "
            "3+4j, or as a magnitude and an angle like 5 angle 53.13.") \
            from exc
    return Phasor(value.real, value.imag, angle_unit)


#: What can be done with two of them.
OPERATIONS = ("+", "-", "x", "/")


def combine(left: Phasor, operation: str, right: Phasor) -> Phasor:
    """Two phasors, one operation, in the unit the first one is quoted in.

    Multiplication and division are the reason polar form exists: the
    magnitudes multiply and the angles add, which is a great deal easier
    than doing it in rectangular form and is why an impedance gets written
    that way.
    """
    a = complex(left.real, left.imaginary)
    b = complex(right.real, right.imaginary)
    if operation == "+":
        answer = a + b
    elif operation == "-":
        answer = a - b
    elif operation in ("x", "*"):
        answer = a * b
    elif operation == "/":
        if b == 0:
            raise PhasorError("Dividing by zero.")
        answer = a / b
    else:
        raise PhasorError(f"There is no {operation!r} to do here.")
    return Phasor(answer.real, answer.imag, left.angle_unit)


def roots(value: Phasor, n: int) -> list:
    """The n nth roots of a complex number, spaced evenly round the circle.

    All n of them, because there are n and a calculator that shows one is
    hiding the interesting part - they sit at equal angles on a circle, and
    seeing that is the point of the diagram.
    """
    if n < 1:
        raise PhasorError("Ask for at least one root.")
    a = complex(value.real, value.imaginary)
    if a == 0:
        return [Phasor(0.0, 0.0, value.angle_unit)]
    magnitude = abs(a) ** (1.0 / n)
    start = cmath.phase(a) / n
    step = 2.0 * math.pi / n
    return [Phasor(magnitude * math.cos(start + step * k),
                   magnitude * math.sin(start + step * k), value.angle_unit)
            for k in range(n)]
