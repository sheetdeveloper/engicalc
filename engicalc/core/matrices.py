"""Matrices, for the thing engineers actually use them for.

A frame with a dozen joints gives a dozen equations that have to hold at
once. Writing them as ``A x = b`` and solving in one step is the whole reason
matrices earn their place, so that is the operation this is built around.
Eigenvalues come next - natural frequencies, buckling loads, principal
stresses - and the rest are the building blocks those two stand on.

Everything returns a :class:`core.engine.CalcResult`, like the rest of the
app.

Two warnings this goes out of its way to give, because both produce answers
that look perfectly reasonable and are worthless:

* **A singular matrix has no unique solution.** The equations are either
  contradictory or redundant, and the right answer is to say so rather than
  return whatever a division by almost-zero produced.
* **An ill-conditioned matrix loses precision.** If the condition number is
  large, small changes in the input make large changes in the answer, and a
  stiffness matrix that is nearly singular gives numbers that are arithmetic
  rather than engineering.
"""

from __future__ import annotations

import re

import sympy as sp

from .display import fmt_number
from .engine import CalcResult
from .parsing import ParseError, parse_number
from .steps import Step

OPERATIONS = [
    "solve", "determinant", "inverse", "transpose", "eigenvalues",
    "rank", "multiply",
]

# Above this, the answer is arithmetic rather than engineering.
CONDITION_LIMIT = 1e8

_SPLIT = re.compile(r"[,;\t]| +")


def parse_matrix(text: str) -> sp.Matrix:
    """Read a matrix from typed or pasted text, one row per line.

    Accepts the same shapes the interpolation table does - tabs out of Excel,
    commas from a CSV, or plain spaces - because they arrive on the clipboard
    the same way. Entries may be expressions, not just numbers, so a symbolic
    stiffness matrix works too.
    """
    rows = []
    for number, raw in enumerate(text.strip().splitlines(), 1):
        line = raw.strip().strip("[]")
        if not line:
            continue
        parts = [p for p in _SPLIT.split(line) if p]
        try:
            rows.append([parse_number(p) for p in parts])
        except Exception as exc:                      # noqa: BLE001
            raise ParseError(
                f"Row {number} is not a row of numbers: {raw!r}") from exc

    if not rows:
        raise ParseError("No matrix here - put one row on each line.")
    width = len(rows[0])
    for index, row in enumerate(rows, 1):
        if len(row) != width:
            raise ParseError(
                f"Row {index} has {len(row)} entries but row 1 has {width}. "
                "Every row must be the same length.")
    return sp.Matrix(rows)


def matrix_text(matrix: sp.Matrix) -> str:
    """A matrix as aligned plain text, for the working and for history."""
    cells = [[_cell(matrix[r, c]) for c in range(matrix.cols)]
             for r in range(matrix.rows)]
    widths = [max(len(cells[r][c]) for r in range(matrix.rows))
              for c in range(matrix.cols)]
    return "\n".join(
        "[ " + "  ".join(cell.rjust(widths[c]) for c, cell in enumerate(row))
        + " ]" for row in cells)


def _tidy(value):
    """Drop an imaginary part that is only rounding error.

    Numerically found eigenvalues of a real matrix come back as things like
    ``3.21432 + 0.e-12*I``. The imaginary part is noise from the root finding,
    but printed it says "complex" - which for a natural frequency or a
    principal stress is a different engineering claim entirely.
    """
    try:
        number = sp.N(value)
        if not number.is_number:
            return value
        real, imaginary = float(sp.re(number)), float(sp.im(number))
    except (TypeError, ValueError):
        return value
    if imaginary != 0 and abs(imaginary) < 1e-9 * max(1.0, abs(real)):
        return sp.re(value) if not value.is_number else sp.Float(real)
    return value


def _cell(value) -> str:
    if getattr(value, "is_number", False):
        return fmt_number(value, 6)
    return sp.sstr(value).replace("**", "^")


def _condition(matrix: sp.Matrix):
    """Condition number, or None for a symbolic matrix.

    Done with numpy rather than SymPy's ``condition_number``, which goes via
    singular values symbolically and raises on ordinary numeric input - it
    fails comparing a complex intermediate on a matrix as plain as
    ``[[1, 1], [1, 1.0000000001]]``, which is exactly the near-singular case
    worth warning about.
    """
    import numpy as np

    try:
        values = np.array(matrix.evalf().tolist(), dtype=float)
        return float(np.linalg.cond(values))
    except Exception:                                 # noqa: BLE001
        return None                                   # symbolic, or singular


def _check_square(matrix: sp.Matrix, what: str) -> None:
    if matrix.rows != matrix.cols:
        raise ParseError(
            f"{what} needs a square matrix; this one is "
            f"{matrix.rows} by {matrix.cols}.")


def solve_system(a: sp.Matrix, b: sp.Matrix) -> CalcResult:
    """Solve ``A x = b`` - a set of equations that all hold at once."""
    if b.cols != 1:
        b = b.T
    if a.rows != b.rows:
        raise ParseError(
            f"A has {a.rows} rows but b has {b.rows}. There must be one "
            "right-hand side value per equation.")

    result = CalcResult(operation="matrix", input_text="A x = b")
    result.steps.append(Step(f"{a.rows} equations in {a.cols} unknowns",
                             detail=matrix_text(a.row_join(b))))

    if a.rows == a.cols:
        determinant = sp.simplify(a.det())
        result.steps.append(Step("Determinant of A",
                                 detail=_cell(determinant)))
        if determinant == 0:
            result.result_text = (
                "No unique solution - the determinant is zero.")
            result.warnings.append(
                "A singular matrix means the equations are either "
                "contradictory or say the same thing twice, so there is no "
                "one answer. Check the equations rather than the arithmetic.")
            return result

    try:
        solution = a.solve(b)
    except Exception as exc:                          # noqa: BLE001
        result.result_text = "Could not solve this system."
        result.warnings.append(str(exc))
        return result

    solution = solution.applyfunc(sp.simplify)
    names = [f"x{i + 1}" for i in range(solution.rows)]
    result.results = [solution]
    result.result_text = "\n".join(
        f"{name} = {_cell(value)}"
        for name, value in zip(names, solution))
    result.latex = sp.latex(solution)
    result.numeric = [float(sp.N(v)) if sp.N(v).is_real else None
                      for v in solution]
    result.steps.append(Step("Solution", detail=result.result_text))

    condition = _condition(a) if a.rows == a.cols else None
    if condition and condition > CONDITION_LIMIT:
        result.warnings.append(
            f"A is ill-conditioned (condition number {condition:.3g}). Small "
            "changes in the inputs will make large changes in this answer, "
            "so treat the figures as indicative rather than exact.")
    return result


def operate(matrix: sp.Matrix, operation: str,
            other: sp.Matrix | None = None) -> CalcResult:
    """Run a single-matrix operation and describe what it means."""
    result = CalcResult(operation="matrix",
                        input_text=f"{operation} of a {matrix.rows} by "
                                   f"{matrix.cols} matrix")
    result.steps.append(Step("Matrix", detail=matrix_text(matrix)))

    if operation == "determinant":
        _check_square(matrix, "A determinant")
        value = sp.simplify(matrix.det())
        result.results = [value]
        result.result_text = f"det = {_cell(value)}"
        result.latex = r"\det = " + sp.latex(value)
        if value == 0:
            result.warnings.append(
                "A zero determinant means the rows are not independent - the "
                "matrix has no inverse and the system it represents has no "
                "unique solution.")
        if value.is_number:
            result.numeric = [float(sp.N(value))]

    elif operation == "inverse":
        _check_square(matrix, "An inverse")
        if sp.simplify(matrix.det()) == 0:
            result.result_text = "This matrix has no inverse."
            result.warnings.append(
                "The determinant is zero, so the matrix is singular and "
                "cannot be inverted.")
            return result
        inverse = matrix.inv().applyfunc(sp.simplify)
        result.results = [inverse]
        result.result_text = matrix_text(inverse)
        result.latex = sp.latex(inverse)

    elif operation == "transpose":
        transposed = matrix.T
        result.results = [transposed]
        result.result_text = matrix_text(transposed)
        result.latex = sp.latex(transposed)

    elif operation == "rank":
        value = matrix.rank()
        result.results = [sp.Integer(value)]
        result.numeric = [float(value)]
        full = min(matrix.rows, matrix.cols)
        result.result_text = f"rank = {value}  (of a possible {full})"
        if value < full:
            result.warnings.append(
                f"The rank is below {full}, so {full - value} of the rows say "
                "nothing the others do not. The equations are not all "
                "independent.")

    elif operation == "eigenvalues":
        _check_square(matrix, "Eigenvalues")
        pairs = matrix.eigenvals()
        values = []
        for value, multiplicity in pairs.items():
            values.extend([_tidy(sp.simplify(value))] * multiplicity)
        values.sort(key=lambda v: (float(sp.re(sp.N(v))),
                                   float(sp.im(sp.N(v)))))
        result.results = values
        lines = []
        for index, value in enumerate(values, 1):
            approximate = sp.N(value, 8)
            text = f"lambda{index} = {_cell(value)}"
            if _cell(value) != _cell(approximate):
                text += f"   ~ {_cell(approximate)}"
            lines.append(text)
        result.result_text = "\n".join(lines)
        result.numeric = [float(sp.N(v)) if sp.N(v).is_real else None
                          for v in values]
        result.steps.append(Step(
            "What these are for",
            detail="Natural frequencies of a vibrating structure, buckling "
                   "loads, and principal stresses are all eigenvalue "
                   "problems."))

    elif operation == "multiply":
        if other is None:
            raise ParseError("Multiplying needs a second matrix.")
        if matrix.cols != other.rows:
            raise ParseError(
                f"Cannot multiply: A is {matrix.rows} by {matrix.cols} and B "
                f"is {other.rows} by {other.cols}. A's column count must "
                "match B's row count.")
        product = (matrix * other).applyfunc(sp.simplify)
        result.results = [product]
        result.result_text = matrix_text(product)
        result.latex = sp.latex(product)

    else:
        raise ParseError(f"Unknown operation {operation!r}.")

    return result
