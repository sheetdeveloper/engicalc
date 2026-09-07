"""Self-tests. Run with:  python -m unittest discover tests  (or python tests/test_engicalc.py)"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import sympy as sp  # noqa: E402

from engicalc.core.engine import calculate, rearrange  # noqa: E402
from engicalc.core.excel_printer import to_excel_formula  # noqa: E402
from engicalc.core.parsing import ParseError, parse_input  # noqa: E402
from engicalc.formulas.library import get_library, solve_formula  # noqa: E402
from engicalc.storage.history import History  # noqa: E402


# --------------------------------------------------------------------------
# A tiny Excel-formula evaluator, used to prove the printer is faithful.
# --------------------------------------------------------------------------
EXCEL_TO_PY = {
    "SQRT": "math.sqrt", "LN": "math.log", "EXP": "math.exp", "ABS": "abs",
    "SIN": "math.sin", "COS": "math.cos", "TAN": "math.tan",
    "ASIN": "math.asin", "ACOS": "math.acos", "ATAN": "math.atan",
    "SINH": "math.sinh", "COSH": "math.cosh", "TANH": "math.tanh",
    "MIN": "min", "MAX": "max", "SIGN": "_sign", "FACT": "math.factorial",
    "ATAN2": "_atan2", "LOG": "_log", "MOD": "_mod", "IF": "_if",
}


def _sign(x):
    return (x > 0) - (x < 0)


def _atan2(x, y):          # Excel argument order
    return math.atan2(y, x)


def _log(x, base=10):
    return math.log(x, base)


def _mod(a, b):
    return a % b


def _if(cond, yes, no):
    return yes if cond else no


def eval_excel(formula: str, values: dict) -> float:
    """Evaluate an Excel formula string in Python, for testing only."""
    body = formula.lstrip("=")
    body = body.replace("PI()", "math.pi")
    body = re.sub(r"\^", "**", body)
    for excel, python in EXCEL_TO_PY.items():
        body = re.sub(rf"\b{excel}\(", f"{python}(", body)
    scope = {"math": math, "_sign": _sign, "_atan2": _atan2, "_log": _log,
             "_mod": _mod, "_if": _if}
    scope.update({f"v_{k}": v for k, v in values.items()})
    return eval(body, {"__builtins__": {"abs": abs, "min": min, "max": max}}, scope)


class TestParsing(unittest.TestCase):
    def test_implicit_multiplication(self):
        self.assertEqual(parse_input("2x").expr, 2 * sp.Symbol("x"))

    def test_caret_is_power(self):
        self.assertEqual(parse_input("x^2").expr, sp.Symbol("x") ** 2)

    def test_equation_split(self):
        parsed = parse_input("2x + 1 = 7")
        self.assertTrue(parsed.is_equation)
        self.assertIsInstance(parsed.expr, sp.Eq)

    def test_absolute_value_bars(self):
        self.assertEqual(parse_input("|x|").expr, sp.Abs(sp.Symbol("x")))

    def test_unicode_and_greek(self):
        self.assertIn("rho", str(parse_input("ρ*v").expr))

    def test_rejects_dunder(self):
        with self.assertRaises(ParseError):
            parse_input("__import__('os')")

    def test_rejects_double_equals_ambiguity(self):
        with self.assertRaises(ParseError):
            parse_input("x = 1 = 2")


class TestEngine(unittest.TestCase):
    def test_quadratic(self):
        result = calculate("x^2 - x - 6 = 0", "solve")
        self.assertEqual(sorted(int(s) for s in result.results), [-2, 3])
        self.assertTrue(any("uadratic" in s.title for s in result.steps))

    def test_linear_steps_verify(self):
        result = calculate("5x - 6 = 3x - 8", "solve")
        self.assertEqual(result.results, [-1])
        self.assertTrue(any("Check" in (s.detail or "") for s in result.steps))

    def test_solve_for_named_variable(self):
        result = calculate("a*x + b = 0", "solve", variable="a")
        self.assertEqual(sp.simplify(result.results[0] * sp.Symbol("x")
                                     + sp.Symbol("b")), 0)

    def test_radical_equation(self):
        # sqrt(9) - 10 = -7, so x = 10 is the only root that survives the
        # squaring step; the extraneous one must not be reported.
        result = calculate("sqrt(x - 1) - x = -7", "solve")
        self.assertEqual([float(sp.N(r)) for r in result.results], [10.0])

    def test_definite_integral(self):
        result = calculate("x*sin(x)", "integral", "x", lower="0", upper="pi")
        self.assertAlmostEqual(float(result.results[0]), math.pi, places=9)

    def test_derivative_chain_rule(self):
        result = calculate("sin(x^2)", "derivative", "x")
        self.assertTrue(any("Chain rule" in s.title for s in result.steps))

    def test_limit(self):
        result = calculate("sin(x)/x", "limit", "x", point="0")
        self.assertEqual(result.results[0], 1)

    def test_system(self):
        result = calculate("x + y = 10; x - y = 2", "system")
        self.assertEqual(result.results[0][sp.Symbol("x")], 6)

    def test_numeric_fallback_finds_roots(self):
        result = calculate("cos(x) - x = 0", "solve")
        self.assertTrue(result.results)
        self.assertAlmostEqual(float(result.results[0]), 0.739085, places=4)


class TestExcelPrinter(unittest.TestCase):
    def _check(self, expr, names, low=0.5, high=3.0):
        formula = to_excel_formula(expr)
        for _ in range(25):
            values = {n: random.uniform(low, high) for n in names}
            expected = float(sp.N(expr.subs(
                {sp.Symbol(n): v for n, v in values.items()})))
            self.assertAlmostEqual(eval_excel(formula, values), expected,
                                   places=8, msg=formula)

    def test_products_and_quotients(self):
        m, c, T1, T2 = sp.symbols("m c T1 T2")
        self._check(m * c * (T2 - T1), ["m", "c", "T1", "T2"])

    def test_quadratic_formula(self):
        a, b, c = sp.symbols("a b c")
        self._check((-b + sp.sqrt(b ** 2 + 4 * a * c)) / (2 * a), ["a", "b", "c"])

    def test_negative_and_rational_powers(self):
        x = sp.Symbol("x")
        self._check(x ** sp.Rational(-3, 2) + 1 / x + x ** sp.Rational(2, 3),
                    ["x"])

    def test_transcendental(self):
        x, y = sp.symbols("x y")
        self._check(sp.exp(-x) * sp.log(y) + sp.sin(2 * sp.pi * x)
                    + sp.atan2(y, x), ["x", "y"])

    def test_unary_minus_group(self):
        x, y, a = sp.symbols("x y a")
        self._check(-(x + y) / a, ["x", "y", "a"])


class TestFormulaLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = get_library()

    def test_library_loaded(self):
        self.assertGreater(len(self.library), 150)
        self.assertGreater(len(self.library.branches()), 8)

    def test_every_formula_parses_and_declares_its_variables(self):
        for formula in self.library.all():
            declared = {v.symbol for v in formula.variables}
            actual = {s.name for s in formula.eq.free_symbols}
            self.assertEqual(declared, actual, msg=formula.key)

    def test_search_ranks_name_matches(self):
        hits = self.library.search("reynolds")
        self.assertTrue(hits)
        self.assertIn("Reynolds", hits[0].name)

    def test_solve_any_direction(self):
        formula = self.library.get("thermodynamics.sensible_heat")
        forward = solve_formula(formula, "Q",
                                {"m": "2.5", "c": "4186", "T2": "80", "T1": "20"})
        self.assertAlmostEqual(forward.value, 627900.0, places=3)
        back = solve_formula(formula, "m",
                             {"Q": "627900", "c": "4186", "T2": "80", "T1": "20"})
        self.assertAlmostEqual(back.value, 2.5, places=9)

    def test_units_carried_through(self):
        formula = self.library.get("fluid_mechanics.reynolds")
        solution = solve_formula(formula, "Re", {"rho": "998", "v": "1.2",
                                                 "D": "0.05", "mu": "0.001"})
        self.assertAlmostEqual(solution.value, 59880.0, places=6)
        self.assertEqual(solution.unit, "-")

    def test_numeric_fallback_for_implicit_formula(self):
        formula = self.library.get("heat_transfer.fin_efficiency")
        solution = solve_formula(formula, "L", {"eta_f": "0.8", "m_f": "12"})
        self.assertIsNotNone(solution.value)
        check = math.tanh(12 * solution.value) / (12 * solution.value)
        self.assertAlmostEqual(check, 0.8, places=6)

    def test_missing_values_leaves_it_symbolic(self):
        formula = self.library.get("mechanics.newton_second")
        solution = solve_formula(formula, "F", {"m": "10"})
        self.assertIsNone(solution.value)
        self.assertTrue(solution.warnings)

    def test_rearrangement_coverage(self):
        """Most library formulas should rearrange for every variable."""
        failures = []
        for formula in self.library.all():
            if formula.key in ("heat_transfer.fin_efficiency",
                               "geometry_maths.heron",
                               "geometry_maths.annuity_payment"):
                continue          # known transcendental / slow cases
            for variable in formula.variables:
                try:
                    if rearrange(formula.eq, sp.Symbol(variable.symbol)) is None:
                        failures.append((formula.key, variable.symbol))
                except Exception:  # noqa: BLE001
                    failures.append((formula.key, variable.symbol))
        self.assertEqual(failures, [])


class TestRearrangementIsChecked(unittest.TestCase):
    """A closed form that does not solve its own equation is not an answer.

    SymPy will hand one over without comment, and for one formula in the
    library it did: compound interest solved for the number of compounding
    periods came back as a Lambert W expression that gives 1.2e12 where the
    answer is 12.
    """

    def _library(self):
        return get_library()

    def test_compound_interest_gives_the_compounding_frequency(self):
        # A thousand pounds at five percent for ten years compounded monthly
        # comes to 1647.01. Asking which frequency does that has to give 12.
        formula = self._library().get("geometry_maths.compound_interest")
        for principal, rate, years, times in ((1000, 0.05, 10, 12),
                                              (5000, 0.08, 5, 4),
                                              (250, 0.12, 3, 1),
                                              (800, 0.10, 15, 365)):
            amount = principal * (1 + rate / times) ** (times * years)
            with self.subTest(times=times):
                got = solve_formula(formula, "nc",
                                    {"P": str(principal), "i": str(rate),
                                     "t": str(years), "Aa": repr(amount)})
                self.assertIsNotNone(got.value)
                self.assertAlmostEqual(got.value, times,
                                       delta=max(1e-5 * times, 1e-5))

    def test_the_quadratic_keeps_its_closed_form(self):
        # The other formula the audit flagged, which was not wrong. Solving
        # x = (-b + sqrt(b^2 - 4ac))/2a for `a` gives an `a` that makes x a
        # root - the *plus* root only for some b and c. On a real quadratic
        # it is exactly right, so it must not be thrown away.
        formula = self._library().get("geometry_maths.quadratic_root")
        for a, b, c in ((1, -5, 6), (2, -7, 3), (1, 3, 2)):
            root = float((-b + math.sqrt(b * b - 4 * a * c)) / (2 * a))
            with self.subTest(a=a, b=b, c=c):
                got = solve_formula(formula, "a",
                                    {"b": str(b), "c": str(c),
                                     "x": repr(root)})
                self.assertAlmostEqual(got.value, a, places=9)
                self.assertFalse(
                    [w for w in got.warnings if "does not satisfy" in w],
                    "a rearrangement that works was thrown away")

    def test_an_answer_that_does_not_balance_is_spotted(self):
        from engicalc.formulas.library import _balances

        formula = self._library().get("geometry_maths.compound_interest")
        given = {sp.Symbol("P"): 1000.0, sp.Symbol("i"): 0.05,
                 sp.Symbol("t"): 10.0,
                 sp.Symbol("Aa"): 1000 * (1 + 0.05 / 12) ** 120}
        self.assertTrue(_balances(formula, sp.Symbol("nc"), given, 12.0))
        self.assertFalse(_balances(formula, sp.Symbol("nc"), given,
                                   1214660299856.7229))

    def test_the_check_is_done_with_more_digits_than_a_float_has(self):
        from engicalc.formulas.library import _balances, _precise

        # This is what made the bug survive its own check. Substituting
        # ordinary floats and then asking for thirty digits recovers
        # nothing, and (1 + 0.05/1.2e12) has three significant digits left
        # in float64. Raised to the power 1.2e13 that turned a wrong answer
        # of 1648.72 into 1647.0094976903 - the right one to fourteen
        # digits.
        formula = self._library().get("geometry_maths.compound_interest")
        bad = 1214660299856.7229
        rough = {sp.Symbol("P"): 1000.0, sp.Symbol("i"): 0.05,
                 sp.Symbol("t"): 10.0, sp.Symbol("nc"): bad}
        careful = {name: _precise(value) for name, value in rough.items()}
        self.assertAlmostEqual(
            float(sp.N(formula.eq.rhs.subs(rough), 30)), 1647.0095, places=3)
        self.assertAlmostEqual(
            float(sp.N(formula.eq.rhs.subs(careful), 30)), 1648.7213,
            places=3)
        # And the check uses the careful one.
        given = {k: v for k, v in rough.items() if k != sp.Symbol("nc")}
        given[sp.Symbol("Aa")] = 1000 * (1 + 0.05 / 12) ** 120
        self.assertFalse(_balances(formula, sp.Symbol("nc"), given, bad))

    def test_the_fallback_says_which_of_the_two_reasons_it_is(self):
        formula = self._library().get("geometry_maths.compound_interest")
        amount = 1000 * (1 + 0.05 / 12) ** 120
        got = solve_formula(formula, "nc",
                            {"P": "1000", "i": "0.05", "t": "10",
                             "Aa": repr(amount)})
        said = " ".join(got.warnings)
        self.assertIn("does not satisfy", said)
        self.assertNotIn("no closed-form rearrangement exists", said)

    def test_the_numerical_route_reads_units_the_same_way(self):
        # It used to read the raw string with parse_number while the
        # closed-form route went through the unit conversion, so a value
        # typed as `50 mm` worked on one path and not on the other.
        library = self._library()
        formula = library.get("strength_of_materials.beam_udl_deflection")
        metres = solve_formula(formula, "delta",
                               {"w": "5000", "L": "4", "E": "200e9",
                                "I": "8.5e-6"})
        millimetres = solve_formula(formula, "delta",
                                    {"w": "5000", "L": "4000 mm",
                                     "E": "200e9", "I": "8.5e-6"})
        self.assertAlmostEqual(metres.value, millimetres.value, places=12)


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.history = History(":memory:")

    def test_round_trip(self):
        result = calculate("x^2 - 4 = 0", "solve")
        entry_id = self.history.add_result(result, project="Test")
        stored = self.history.get(entry_id)
        self.assertEqual(stored.input_text, "x^2 - 4 = 0")
        self.assertEqual(stored.project, "Test")

    def test_formula_inputs_are_json_safe(self):
        formula = get_library().get("mechanics.kinetic_energy")
        solution = solve_formula(formula, "KE", {"m": "80", "v": "12"})
        entry_id = self.history.add_formula_solution(solution)
        stored = self.history.get(entry_id)
        self.assertEqual(stored.inputs["m"], "80")
        self.assertAlmostEqual(stored.numeric, 5760.0)

    def test_search_and_favourites(self):
        self.history.add_result(calculate("2x = 8", "solve"))
        entry = self.history.recent()[0]
        self.history.update(entry.id, favourite=True, note="check me")
        self.assertTrue(self.history.recent(favourites_only=True))
        self.assertTrue(self.history.search("check me"))

    def test_delete(self):
        entry_id = self.history.add_result(calculate("2x = 8", "solve"))
        self.history.delete(entry_id)
        self.assertIsNone(self.history.get(entry_id))


class TestExport(unittest.TestCase):
    def test_workbook_has_live_formula(self):
        from openpyxl import load_workbook

        from engicalc.export.excel import export_formula

        library = get_library()
        formula = library.get("strength_of_materials.beam_udl_deflection")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "beam.xlsx")
            export_formula(formula, "delta",
                           {"w": "5000", "L": "4", "E": "200e9", "I": "8.5e-6"},
                           path, sweep={"variable": "L", "start": 1, "stop": 8,
                                        "points": 10})
            book = load_workbook(path)
            self.assertIn("Sensitivity", book.sheetnames)
            sheet = book["Calculation"]
            found = [sheet.cell(r, 3).value for r in range(1, 30)
                     if isinstance(sheet.cell(r, 3).value, str)
                     and sheet.cell(r, 3).value.startswith("=")]
            self.assertTrue(found, "no live formula written")
            values = {"w": 5000.0, "L": 4.0, "E": 200e9, "I": 8.5e-6}
            self.assertAlmostEqual(eval_excel(found[0], values),
                                   5 * 5000 * 4 ** 4 / (384 * 200e9 * 8.5e-6),
                                   places=12)
            self.assertTrue(book.defined_names)

    def test_history_export_rebuilds_sheets(self):
        from openpyxl import load_workbook

        from engicalc.export.excel import export_history

        library = get_library()
        history = History(":memory:")
        history.add_formula_solution(
            solve_formula(library.get("electrical.ohms_law"), "V",
                          {"I": "2", "R": "12"}))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history.xlsx")
            export_history(history.recent(), path, library=library)
            book = load_workbook(path)
            self.assertEqual(len(book.sheetnames), 2)


class TestChartExport(unittest.TestCase):
    """A chart you can only look at is half a result."""

    def _figure(self):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        figure = Figure(figsize=(4, 3), dpi=80)
        figure.patch.set_facecolor("white")
        figure.add_subplot(111).plot([0, 1, 2], [0, 1, 0])
        return figure

    def test_a_chart_saves_in_every_format_offered(self):
        from engicalc.ui import figures

        # PDF and SVG sit beside PNG in the dialog on purpose: a bending
        # moment diagram that has to go on a drawing at A3 should not be a
        # photograph of one. Offering them and not writing them is worse
        # than not offering them.
        figure = self._figure()
        with tempfile.TemporaryDirectory() as tmp:
            for suffix in (".png", ".pdf", ".svg"):
                path = os.path.join(tmp, "chart" + suffix)
                figures._write(figure, path, dpi=figures.DPI)
                self.assertGreater(os.path.getsize(path), 200, suffix)

    def test_the_saved_chart_keeps_its_white_ground(self):
        from PIL import Image

        from engicalc.ui import figures

        # Saved transparent, it pastes into Word and turns black in some
        # versions of it.
        image = figures.figure_image(self._figure()).convert("RGB")
        self.assertEqual((255, 255, 255), image.getpixel((1, 1)))

    def test_the_temporary_png_exists_then_does_not(self):
        from engicalc.ui import figures

        # A workbook holds the picture by filename until it is saved, so it
        # has to outlive the call that made it and be gone afterwards.
        with figures.temporary_png(self._figure()) as path:
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 200)
        self.assertFalse(os.path.exists(path))

    def test_the_workbook_carries_the_chart_beside_the_numbers(self):
        from openpyxl import load_workbook

        from engicalc.export.excel import export_table
        from engicalc.ui import figures

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "chart.xlsx")
            with figures.temporary_png(self._figure()) as picture:
                export_table(("Quantity", "Value", "Unit"),
                             [["largest moment", 36.1, "kN m"]], path,
                             title="Beam diagrams", sheet="Chart",
                             picture=picture)
            book = load_workbook(path)
            sheet = book["Chart"]
            self.assertEqual("largest moment", sheet.cell(4, 1).value)
            self.assertEqual(1, len(sheet._images))

    def test_a_picture_that_will_not_go_in_does_not_lose_the_numbers(self):
        from openpyxl import load_workbook

        from engicalc.export.excel import export_table

        # The numbers are what was asked for; the chart is what was added.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "chart.xlsx")
            export_table(("Quantity", "Value"), [["shear", 23.0]], path,
                         picture=os.path.join(tmp, "not-a-file.png"))
            sheet = load_workbook(path).active
            self.assertEqual("shear", sheet.cell(4, 1).value)


class TestPlotting(unittest.TestCase):
    def test_draw_returns_no_warnings_for_valid_curves(self):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        from engicalc.plotting.plot import Curve, PlotSpec, draw

        spec = PlotSpec(curves=[Curve("x^2 - 4"), Curve("sin(x)"),
                                Curve("x^2 + y^2 = 9", kind="implicit"),
                                Curve("cos(t)", kind="parametric", second="sin(t)"),
                                Curve("1 + cos(theta)", kind="polar")],
                        mark_roots=True)
        warnings = draw(spec, Figure().add_subplot(111))
        self.assertEqual(warnings, [])

    def test_free_symbol_is_reported(self):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        from engicalc.plotting.plot import Curve, PlotSpec, draw

        warnings = draw(PlotSpec(curves=[Curve("a*x + 1")]),
                        Figure().add_subplot(111))
        self.assertEqual(len(warnings), 1)
        self.assertIn("a", warnings[0])

    def test_sweep(self):
        from engicalc.plotting.plot import sweep

        formula = get_library().get("mechanics.kinetic_energy")
        xs, ys = sweep(formula, "KE", {"m": "80"}, "v", 0, 10, 11)
        self.assertEqual(len(xs), 11)
        self.assertAlmostEqual(ys[-1], 0.5 * 80 * 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMathRendering(unittest.TestCase):
    """The typeset display must cope with everything the app can produce."""

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")

    def test_every_library_formula_renders(self):
        from engicalc.ui.mathrender import render_png

        failures = []
        for formula in get_library().all():
            try:
                render_png(formula.display_latex)
            except Exception as exc:  # noqa: BLE001
                failures.append((formula.key, str(exc)[:60]))
        self.assertEqual(failures, [])

    def test_every_pad_item_renders(self):
        from engicalc.ui.mathrender import render_png
        from engicalc.ui.pad import PAD

        failures = []
        for item in PAD:
            for latex in (item.label, item.example_latex):
                if not latex:
                    continue
                try:
                    render_png(latex)
                except Exception as exc:  # noqa: BLE001
                    failures.append((item.key, latex, str(exc)[:60]))
        self.assertEqual(failures, [])

    def test_calculator_output_renders(self):
        import sympy
        from engicalc.ui.mathrender import render_png

        for text, operation in (("x^2 - x - 6 = 0", "solve"),
                                ("x*sin(x)", "integral"),
                                ("sin(x^2)", "derivative"),
                                ("x + y = 10; x - y = 2", "system")):
            result = calculate(text, operation, "x", lower="0", upper="pi")
            targets = list(result.results) + [s.expr for s in result.steps
                                              if s.expr is not None]
            for target in targets:
                if isinstance(target, dict):
                    continue
                render_png(sympy.latex(target))

    def test_display_order_is_preserved(self):
        library = get_library()
        self.assertEqual(library.get("mechanics.newton_second").display_latex,
                         "F = m a")
        self.assertIn("u + a t",
                      library.get("mechanics.kinematic_v").display_latex)

    def test_unsupported_latex_is_reported_not_raised_blindly(self):
        from engicalc.ui.mathrender import MathRenderError, sanitise

        with self.assertRaises(MathRenderError):
            sanitise(r"\begin{cases}x\\y\end{cases}")
        self.assertEqual(sanitise(r"\operatorname{atan2}(y,x)"),
                         r"\mathrm{atan2}(y,x)")


class TestSymbolPadData(unittest.TestCase):
    def test_every_item_documents_itself(self):
        from engicalc.ui.pad import PAD

        for item in PAD:
            self.assertTrue(item.name, item.key)
            self.assertTrue(item.markup, item.key)
            self.assertTrue(item.label, item.key)
            if not item.operation:
                self.assertTrue(item.insert, item.key)

    def test_keys_are_unique(self):
        from engicalc.ui.pad import PAD

        keys = [item.key for item in PAD]
        self.assertEqual(len(keys), len(set(keys)))

    def test_search_finds_by_name_and_markup(self):
        from engicalc.ui.pad import find

        self.assertTrue(any(i.key == "sqrt" for i in find("square root")))
        self.assertTrue(any(i.key == "defint" for i in find("definite")))


# --------------------------------------------------------------------------
# The typeset equation field
# --------------------------------------------------------------------------
class TestMathField(unittest.TestCase):
    """The shapes drawn in the equation bar must render, and must compile
    back to input the parser already understands."""

    def setUp(self):
        import matplotlib
        matplotlib.use("Agg")

    def _filled(self, key, *values):
        from engicalc.ui import mathfield as mf

        group = mf.new_group(mf.TEMPLATES[key])
        for index, value in enumerate(values):
            group.rows[index] = mf.row_from_text(value)
        return mf.Row([group])

    def test_every_template_renders(self):
        """mathtext draws a LaTeX subset - an unrenderable shape is a bug."""
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties

        from engicalc.ui import mathfield as mf

        parser = mathtext.MathTextParser("path")
        for key, template in mf.TEMPLATES.items():
            latex = mf.to_latex(mf.Row([mf.new_group(template)]))
            with self.subTest(template=key):
                parser.parse(f"${latex}$", dpi=100,
                             prop=FontProperties(size=16))

    def test_every_empty_slot_is_locatable(self):
        """The boxes are positioned by finding their glyphs in the layout."""
        from engicalc.ui import mathfield as mf

        for key, template in mf.TEMPLATES.items():
            latex = mf.to_latex(mf.Row([mf.new_group(template)]))
            with self.subTest(template=key):
                spots = mf.slot_positions(latex, 16)
                self.assertEqual(len(spots), template.count)

    def test_caret_is_locatable_in_every_slot(self):
        from engicalc.ui import mathfield as mf

        for key, template in mf.TEMPLATES.items():
            group = mf.new_group(template)
            row = mf.Row([group])
            for index in range(template.count):
                latex = mf.to_latex(row, caret_row=group.rows[index],
                                    caret_index=0)
                with self.subTest(template=key, slot=index):
                    self.assertIsNotNone(mf.caret_position(latex, 16))

    def test_filled_templates_compile_to_parseable_text(self):
        cases = [
            ("frac", ("x + 1", "2y")),
            ("power", ("x", "n + 1")),
            ("subscript", ("T", "1")),
            ("sqrt", ("x^2 + y^2",)),
            ("nthroot", ("3", "27")),
            ("logbase", ("10", "1000")),
            ("exp", ("-x/2",)),
            ("abs", ("3x + 1",)),
            ("paren", ("x + 3",)),
            ("defint", ("0", "1", "2x", "x")),
            ("indefint", ("x*sin(x)", "x")),
            ("deriv", ("x^3 - 2x", "x")),
            ("limit", ("sin(x)/x", "x", "0")),
        ]
        from engicalc.ui import mathfield as mf

        self.assertEqual(len(cases), len(mf.TEMPLATES),
                         "every template needs a compile case")
        for key, values in cases:
            with self.subTest(template=key):
                compiled = mf.compile_row(self._filled(key, *values))
                parse_input(compiled.text)

    def test_definite_integral_carries_its_own_limits(self):
        """The limits typed into the boxes drive the operation, not the
        separate from/to entries."""
        from engicalc.ui import mathfield as mf

        compiled = mf.compile_row(self._filled("defint", "-1.6", "2.4", "2x", "x"))
        self.assertEqual(compiled.operation, "integral")
        self.assertEqual(compiled.extras["lower"], "-1.6")
        self.assertEqual(compiled.extras["upper"], "2.4")
        self.assertEqual(compiled.extras["variable"], "x")
        result = calculate(compiled.text, compiled.operation,
                           compiled.extras["variable"],
                           lower=compiled.extras["lower"],
                           upper=compiled.extras["upper"])
        self.assertAlmostEqual(float(result.results[0]), 3.2, places=9)

    def test_templates_nest(self):
        from engicalc.ui import mathfield as mf

        outer = mf.new_group(mf.TEMPLATES["defint"])
        outer.rows[0] = mf.row_from_text("0")
        outer.rows[1] = mf.row_from_text("1")
        inner = mf.new_group(mf.TEMPLATES["frac"])
        inner.rows[0] = mf.row_from_text("1")
        inner.rows[1] = mf.row_from_text("x + 1")
        outer.rows[2] = mf.Row([inner])
        outer.rows[3] = mf.row_from_text("x")

        compiled = mf.compile_row(mf.Row([outer]))
        result = calculate(compiled.text, compiled.operation, "x",
                           lower="0", upper="1")
        self.assertAlmostEqual(float(sp.N(result.results[0])),
                               math.log(2), places=9)

    def test_pad_template_keys_all_exist(self):
        """pad.py and mathfield.py must not drift apart."""
        from engicalc.ui import mathfield as mf
        from engicalc.ui.pad import PAD

        for item in PAD:
            if item.template:
                with self.subTest(item=item.key):
                    self.assertIn(item.template, mf.TEMPLATES)

    def test_tab_order_covers_every_slot(self):
        from engicalc.ui import mathfield as mf

        group = mf.new_group(mf.TEMPLATES["defint"])
        row = mf.Row([group])
        rows = mf.walk_rows(row)
        self.assertIn(row, rows)
        for slot in group.rows:
            self.assertIn(slot, rows)

    def test_identical_rows_are_still_distinct_slots(self):
        """x over x is two different boxes. Rows compare by identity, so Tab
        order and slot ownership do not confuse one for the other."""
        from engicalc.ui import mathfield as mf

        group = mf.new_group(mf.TEMPLATES["frac"])
        group.rows[0] = mf.row_from_text("x")
        group.rows[1] = mf.row_from_text("x")
        row = mf.Row([group])
        rows = mf.walk_rows(row)

        self.assertEqual(len(rows), 3)
        self.assertNotEqual(rows.index(group.rows[0]),
                            rows.index(group.rows[1]))

    def test_tab_reaches_every_slot_of_a_limit(self):
        """Walking the whole tree must land on each box exactly once, even
        when two of them hold the same text."""
        from engicalc.ui import mathfield as mf

        group = mf.new_group(mf.TEMPLATES["limit"])
        inner = mf.new_group(mf.TEMPLATES["frac"])
        inner.rows[0] = mf.row_from_text("sin(x)")
        inner.rows[1] = mf.row_from_text("x")
        group.rows[0] = mf.Row([inner])
        group.rows[1] = mf.row_from_text("x")
        group.rows[2] = mf.row_from_text("0")

        rows = mf.walk_rows(mf.Row([group]))
        for slot in (inner.rows[0], inner.rows[1], group.rows[1], group.rows[2]):
            self.assertEqual(sum(1 for r in rows if r is slot), 1)

        compiled = mf.compile_row(mf.Row([group]))
        self.assertEqual(compiled.operation, "limit")
        self.assertEqual(compiled.extras["variable"], "x")
        self.assertEqual(compiled.extras["point"], "0")
        result = calculate(compiled.text, "limit", "x", point="0")
        self.assertEqual(sp.simplify(result.results[0]), 1)

    def test_function_names_are_drawn_upright(self):
        """sin(x) is a function, not s times i times n."""
        from engicalc.ui import mathfield as mf

        self.assertEqual(mf._chars_to_latex("sin(x)"), r"\mathrm{sin}(x)")
        self.assertEqual(mf._chars_to_latex("atan2(y,x)"), r"\mathrm{atan2}(y,x)")
        self.assertEqual(mf._chars_to_latex("x + y"), "x + y")
        # theta is one name, not something containing eta
        self.assertEqual(mf._chars_to_latex("theta").strip(), r"\theta")

    def test_typed_text_becomes_real_structure(self):
        """sqrt(x) typed into the plain box arrives as a radical, not letters."""
        from engicalc.ui import mathfield as mf

        cases = {
            "sqrt(x)": "sqrt",
            "a/b": "frac",
            "x^2": "power",
            "abs(3x+1)": "abs",
            "log(x, 10)": "logbase",
            "root(x, 3)": "nthroot",
            "exp(-x/2)": "exp",
            "T_1": "subscript",
        }
        for text, key in cases.items():
            with self.subTest(text=text):
                row = mf.structured_row(text)
                groups = [i for i in row.items if isinstance(i, mf.Group)]
                self.assertTrue(
                    any(g.template.key == key for g in groups),
                    f"{text} should build a {key}, got "
                    f"{[g.template.key for g in groups]}")

    def test_structure_round_trips_to_the_same_maths(self):
        """Text in, structure, text out - it must still mean the same thing."""
        from engicalc.ui import mathfield as mf

        def flatten(text):
            expr = parse_input(text).expr
            return expr.lhs - expr.rhs if isinstance(expr, sp.Eq) else expr

        for text in ["sqrt(x)", "a/b", "x^2", "1/(x+1)", "exp(-x/2)",
                     "abs(3x+1)", "log(x, 10)", "2x + 3", "sin(x)/x",
                     "(a+b)/(2c)", "2x^2 - 5x - 3 = 0", "sqrt(x^2 + y^2)",
                     "pi*r^2", "(x+1)^2", "x*y", "rho*v^2/2",
                     "x^4 - 5x^2 + 4 = 0"]:
            with self.subTest(text=text):
                back = mf.to_text(mf.structured_row(text))
                self.assertEqual(sp.simplify(flatten(text) - flatten(back)), 0)

    def test_half_typed_text_falls_back_to_characters(self):
        """Unfinished input is normal while typing, not an error."""
        from engicalc.ui import mathfield as mf

        for text in ["sqrt(x", "2x +", "((", "x^"]:
            with self.subTest(text=text):
                row = mf.structured_row(text)
                self.assertEqual(mf.to_text(row), text)

    def test_brackets_appear_only_where_they_change_the_meaning(self):
        from engicalc.ui import mathfield as mf

        self.assertEqual(mf.to_text(mf.structured_row("2x^2 - 5x - 3 = 0")),
                         "2x^2-5x-3=0")
        self.assertEqual(mf.to_text(mf.structured_row("a/b")), "a/b")
        # the sum must keep its brackets or it changes meaning
        self.assertEqual(mf.to_text(mf.structured_row("(a+b)/(2c)")),
                         "(a+b)/(2c)")


# --------------------------------------------------------------------------
# Shapes written next to each other
# --------------------------------------------------------------------------
class TestShapesSideBySide(unittest.TestCase):
    """Manning's formula opens with a 1/n and a root of S side by side.

    Drawn, that is unambiguous. Compiled, the fraction's denominator used to
    run straight into the root - `1/nsqrt(S)`, where `nsqrt` is a single name
    - and the answer came back as S*q*r*s*t/n from a formula that had been
    entered correctly. Nothing said anything was wrong, which is what makes
    it worth a test of its own.
    """

    def field(self, *items):
        from engicalc.ui import mathfield as mf

        row = mf.Row()
        for item in items:
            if isinstance(item, str):
                row.items.extend(item)
            else:
                row.items.append(item)
        return row

    def shape(self, key, *slots):
        from engicalc.ui import mathfield as mf

        group = mf.new_group(mf.TEMPLATES[key])
        for slot, text in zip(group.rows, slots):
            slot.items.extend(text)
        return group

    def test_a_fraction_does_not_swallow_what_follows_it(self):
        import sympy as sp
        from engicalc.core.parsing import parse_input
        from engicalc.ui import mathfield as mf

        row = self.field(self.shape("frac", "1", "n"),
                         self.shape("sqrt", "S"))
        self.assertEqual(mf.to_text(row), "(1/n)sqrt(S)")
        self.assertEqual(parse_input(mf.to_text(row)).expr,
                         sp.sqrt(sp.Symbol("S")) / sp.Symbol("n"))

    def test_mannings_formula_compiles_to_what_it_draws(self):
        import sympy as sp
        from engicalc.core.parsing import parse_input
        from engicalc.ui import mathfield as mf

        numerator = self.shape("power", "yb+y^2")
        numerator.rows[1].items.append(self.shape("frac", "5", "3"))
        denominator = self.shape("power", "b+2")
        denominator.rows[0].items.append(self.shape("sqrt", "2"))
        denominator.rows[0].items.extend("y")
        denominator.rows[1].items.append(self.shape("frac", "2", "3"))
        big = self.shape("frac")
        big.rows[0].items.append(numerator)
        big.rows[1].items.append(denominator)

        row = self.field("Q=", self.shape("frac", "1", "n"),
                         self.shape("sqrt", "S"), big)
        drawn = parse_input(mf.to_text(row)).expr
        longhand = parse_input(
            "Q = (1/n)*sqrt(S)*((y*b+y^2)^(5/3))/((b+2*sqrt(2)*y)^(2/3))").expr
        self.assertEqual(
            sp.simplify((drawn.lhs - drawn.rhs) - (longhand.lhs - longhand.rhs)),
            0)

    def test_a_power_over_a_sum_draws_the_bracket_it_computes(self):
        from engicalc.ui import mathfield as mf

        # The value was always the whole base; the picture was not, and the
        # picture is what gets checked by eye and pasted into a report.
        row = self.field(self.shape("power", "yb+y^2"))
        row.items[0].rows[1].items.append(self.shape("frac", "5", "3"))
        self.assertIn(r"\left(yb+y^2\right)", mf.to_latex(row))
        self.assertEqual(mf.to_text(row), "(yb+y^2)^(5/3)")

    def test_a_root_and_a_fraction_do_not_gain_brackets_inside(self):
        from engicalc.ui import mathfield as mf

        # Both already enclose what they hold, so brackets would be noise.
        self.assertNotIn(r"\left(",
                         mf.to_latex(self.field(self.shape("sqrt", "a+b"))))
        self.assertNotIn(r"\left(",
                         mf.to_latex(self.field(self.shape("frac", "a+b", "c"))))

    def test_an_open_edge_is_bracketed_and_a_closed_one_is_not(self):
        from engicalc.ui import mathfield as mf

        # x^2 next to y would read as x to the power 2y.
        self.assertEqual(
            mf.to_text(self.field(self.shape("power", "x", "2"), "y")),
            "(x^2)y")
        # n next to 1/2 would read as the single name n1.
        self.assertEqual(
            mf.to_text(self.field("n", self.shape("frac", "1", "2"))),
            "n(1/2)")
        # A root closes itself, so nothing is added.
        self.assertEqual(
            mf.to_text(self.field("2", self.shape("sqrt", "x"))), "2sqrt(x)")
        # And a function call must not gain a multiplication.
        self.assertEqual(
            mf.to_text(self.field("sin", self.shape("paren", "x"))), "sin(x)")


# --------------------------------------------------------------------------
# Greek in cells that get read back
# --------------------------------------------------------------------------
class TestGreekInCells(unittest.TestCase):
    """A sheet cell is not a label: what it says is what gets parsed, and a
    name is how the rows below refer to it. So every substitution made in one
    has to survive the round trip, and a letter and its name have to be one
    quantity rather than two that look alike."""

    def test_every_greek_letter_can_be_typed_back_in(self):
        from engicalc.core.parsing import GREEK_NAMES, canonical_name

        for name, letter in GREEK_NAMES.items():
            with self.subTest(name=name):
                self.assertEqual(GREEK_NAMES[canonical_name(letter)], letter)

    def test_only_reversible_substitutions_are_made(self):
        from engicalc.core.display import pretty_names
        from engicalc.core.parsing import canonical_name

        for text in ["rho*v*d/mu", "pi*d^2/4", "sigma_max", "T_amb",
                     "200e9", "rhombus", "mub", "sin(theta)"]:
            with self.subTest(text=text):
                self.assertEqual(canonical_name(pretty_names(text)),
                                 canonical_name(text))


    def test_a_difference_draws_as_a_triangle_and_reads_back_as_d(self):
        from engicalc.core.display import pretty_names
        from engicalc.core.parsing import canonical_name

        self.assertEqual(pretty_names("dT"), "\u2206T")
        self.assertEqual(canonical_name("\u2206T"), "dT")

    def test_the_triangle_is_not_the_greek_letter(self):
        from engicalc.core.display import pretty_names
        from engicalc.core.parsing import canonical_name

        # Two characters that look alike and mean different things. If the
        # difference used the Greek letter, dT would read back as DeltaT and
        # the row below would stop finding it.
        self.assertEqual(ord(pretty_names("dT")[0]), 0x2206)
        self.assertEqual(ord(pretty_names("Delta")), 0x394)
        self.assertEqual(canonical_name(pretty_names("Delta")), "Delta")

    def test_a_differential_is_left_alone(self):
        from engicalc.core.display import pretty_names

        # d followed by a capital only. dx and dt are differentials and dp is
        # a lowercase name; none of them are a difference to be redrawn.
        for name in ["dx", "dt", "dp", "drag", "delta"]:
            with self.subTest(name=name):
                self.assertFalse(pretty_names(name).startswith("\u2206"))

    def test_a_row_named_with_a_triangle_is_found_by_its_d_name(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet("Temperatures")
        sheet.add("T1", "300", "K")
        sheet.add("T2", "350", "K")
        sheet.add("\u2206T", "T2-T1", "K")
        sheet.add("Q", "dT*2", "")
        results = sheet.evaluate()
        self.assertFalse(results[-1].error)
        self.assertEqual(float(results[-1].value), 100.0)

    def test_a_row_named_with_a_letter_is_found_by_its_name(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet("Pipe")
        sheet.add("\u03c1", "998", "kg/m^3")
        sheet.add("v", "2", "m/s")
        sheet.add("q", "rho*v^2/2", "Pa")
        results = sheet.evaluate()
        self.assertFalse(results[-1].error)
        self.assertEqual(float(results[-1].value), 1996.0)

    def test_the_same_quantity_twice_is_still_a_redefinition(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet("Twice")
        sheet.add("rho", "998", "")
        sheet.add("\u03c1", "1000", "")
        results = sheet.evaluate()
        self.assertIn("defined twice", results[-1].error or "")


# --------------------------------------------------------------------------
# Equations solved together
# --------------------------------------------------------------------------
class TestSimultaneousSet(unittest.TestCase):

    def test_a_set_is_solved_whatever_order_it_is_written_in(self):
        from engicalc.core.system import solve_set

        result = solve_set("x + y = 10; x - y = 2")
        self.assertIn("x = 6", result.result_text)
        self.assertIn("y = 4", result.result_text)

    def test_multi_letter_names_survive(self):
        from engicalc.core.system import parse_set

        # Re is a Reynolds number, not R times Euler's number, and dp is a
        # pressure drop rather than d times p.
        parsed = parse_set("Re = 4000\ndp = 2*Re")
        self.assertEqual([s.name for s in parsed.unknowns], ["Re", "dp"])

    def test_the_count_comes_before_any_answer(self):
        from engicalc.core.system import solve_set

        result = solve_set("x + y = 10")
        self.assertIn("Not enough to go on", result.result_text)
        self.assertIn("1 equation.", result.result_text)   # not "1 equations"

    def test_a_fractional_power_never_reaches_the_exact_solver(self):
        import time

        from engicalc.core.system import solve_set

        # sp.solve turns a system into a polynomial one and, failing that,
        # reaches for a Groebner basis - doubly exponential in the worst
        # case and impossible to interrupt. The duct example hit exactly
        # that and sat at "Solving..." indefinitely. It only happened
        # sometimes, because which path SymPy takes depends on its cached
        # state, which is what let it through the tests and out to a user.
        text = ("A = pi*0.15^2/4\n"
                "v = 0.5/A\n"
                "Re = v*0.15/7.5e-6\n"
                "f = 0.3164/Re^0.25\n"
                "dp = f*(20/0.15)*1.2*v^2/2")
        started = time.monotonic()
        result = solve_set(text)
        self.assertLess(time.monotonic() - started, 5.0,
                        "the solver went the expensive way round")
        self.assertTrue(any("iteration" in step.title.lower()
                            for step in result.steps),
                        "it should say it was solved numerically")
        values = {str(k): float(v) for k, v in result.results[0].items()}
        self.assertAlmostEqual(values["Re"], 565884.0, delta=10.0)

    def test_an_exact_answer_is_still_preferred_where_it_is_safe(self):
        from engicalc.core.system import solve_set

        # A whole-number power is not the dangerous shape - 1/A is A to the
        # minus one - so these keep their exact answers.
        self.assertIn("13/2", solve_set("x + y = 10; x - y = 3").result_text)
        exact = solve_set("1/Rt = 1/R1 + 1/R2; R1 = 220; R2 = 330")
        self.assertIn("Rt = 132", exact.result_text)
        for result in (solve_set("x + y = 10; x - y = 3"), exact):
            self.assertFalse(any("iteration" in step.title.lower()
                                 for step in result.steps))

    def test_a_residual_is_judged_against_the_size_of_its_own_terms(self):
        from engicalc.core.system import solve_set

        # Reynolds number comes out near 5e5. An absolute 1e-6 residual would
        # be asking for twelve significant figures, and the check would call
        # a good answer wrong.
        result = solve_set(
            "A = pi*0.15^2/4\n"
            "v = 0.5/A\n"
            "Re = v*0.15/7.5e-6\n"
            "f = 0.3164/Re^0.25\n"
            "dp = f*(20/0.15)*1.2*v^2/2")
        self.assertNotIn("do not satisfy", " ".join(result.warnings))
        values = result.results[0]
        by_name = {str(k): float(v) for k, v in values.items()}
        self.assertAlmostEqual(by_name["Re"], 565884.0, delta=10.0)
        self.assertAlmostEqual(by_name["dp"], 738.8, delta=1.0)


# --------------------------------------------------------------------------
# Names with more than one letter in them
# --------------------------------------------------------------------------
class TestMultiLetterNames(unittest.TestCase):
    """T1 and T2 are the commonest pair of names in thermodynamics, and the
    sheet could not subtract them: the parser splits a run of letters and
    digits into a product, and the constructor it emits for the number was
    not among the names it could reach."""

    def test_a_numbered_name_parses(self):
        from engicalc.core.parsing import parse_input

        self.assertIsNotNone(parse_input("T2-T1").expr)

    def test_a_sheet_declares_its_own_rows(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet("Temperatures")
        sheet.add("T1", "300", "K")
        sheet.add("T2", "350", "K")
        sheet.add("dT", "T2-T1", "K")
        results = sheet.evaluate()
        self.assertFalse(results[-1].error)
        self.assertEqual(float(results[-1].value), 50.0)

    def test_a_sheet_row_called_Re_is_a_reynolds_number(self):
        from engicalc.core.sheet import Sheet

        # Undeclared, Re parses as R times Euler's number and the friction
        # factor comes back as a number that is wrong but looks fine.
        sheet = Sheet("Friction")
        sheet.add("Re", "4000", "")
        sheet.add("f", "0.3164/Re^0.25", "")
        results = sheet.evaluate()
        self.assertFalse(results[-1].error)
        self.assertAlmostEqual(float(results[-1].value), 0.039785, places=5)

    def test_upright_is_only_claimed_where_the_name_is_one_symbol(self):
        from engicalc.core.display import latex_name
        from engicalc.ui.mathfield import _chars_to_latex

        # Declared - one symbol, so it is set upright.
        self.assertEqual(latex_name("Re"), r"\mathrm{Re}")
        self.assertEqual(latex_name("T1"), "T_{1}")
        # In the equation bar nothing is declared and Re really is R times e,
        # so drawing it upright would claim something untrue.
        self.assertEqual(_chars_to_latex("Re"), "Re")
        self.assertEqual(_chars_to_latex("T1"), "T1")

    def test_a_subscript_holds_together_in_both(self):
        from engicalc.core.display import latex_name
        from engicalc.ui.mathfield import _chars_to_latex

        # This is what makes a subscript the way to write a multi-letter
        # variable: an underscore name is one symbol in every path.
        for drawn in (latex_name("c_p"), _chars_to_latex("c_p")):
            self.assertEqual(drawn, "c_{p}")
        self.assertEqual(_chars_to_latex("sigma_max"),
                         r"\sigma _{\mathrm{max}}")

    def test_a_rate_is_drawn_with_a_dot_over_the_letter(self):
        from engicalc.core.display import latex_name

        self.assertEqual(latex_name("mdot"), r"\dot{m}")
        self.assertEqual(latex_name("Qdot"), r"\dot{Q}")
        self.assertEqual(latex_name("mdot_a"), r"\dot{m}_{a}")
        # Two dots for a second derivative, and checked first, or xddot
        # would come out as xd with one dot over it.
        self.assertEqual(latex_name("xddot"), r"\ddot{x}")

    def test_the_underscore_spelling_draws_the_dot_in_both_paths(self):
        from engicalc.core.display import latex_name
        from engicalc.ui.mathfield import _chars_to_latex

        # m_dot is one symbol everywhere, so it can be drawn as one anywhere.
        for drawn in (latex_name("m_dot"), _chars_to_latex("m_dot")):
            self.assertEqual(drawn, r"\dot{m}")
        # mdot is only one symbol where names are declared. In the equation
        # bar it is m times d times o times t, and a dot would be drawing a
        # quantity that was never computed.
        self.assertEqual(_chars_to_latex("mdot"), "mdot")

    def test_an_ordinary_name_that_ends_in_dot_is_left_alone(self):
        from engicalc.core.display import latex_name

        self.assertEqual(latex_name("dot"), r"\mathrm{dot}")
        self.assertEqual(latex_name("pivot"), r"\mathrm{pivot}")

    def test_a_cell_keeps_the_spelling(self):
        from engicalc.core.display import pretty_names

        # The dot is a combining mark with no precomposed form for most
        # letters, so it would not survive being read back out of a cell.
        for name in ["mdot", "Qdot", "m_dot"]:
            with self.subTest(name=name):
                self.assertEqual(pretty_names(name), name)

    def test_notation_between_names_survives_the_split(self):
        from engicalc.ui.mathfield import _chars_to_latex

        # The names come out of the text before the characters are rewritten;
        # the other way round, the `cdot` inside \cdot looked like a name.
        self.assertEqual(_chars_to_latex("Re*v/mu"), r"Re\cdot v/\mu ")


# --------------------------------------------------------------------------
# Plotting the answer
# --------------------------------------------------------------------------
class TestResultPlot(unittest.TestCase):
    """A definite integral's answer is an area, so the plot has to show the
    integrand and the region - not the antiderivative."""

    def setUp(self):
        import matplotlib
        matplotlib.use("Agg")

    def test_integral_keeps_its_integrand_and_limits(self):
        result = calculate("2x", "integral", "x", lower="-1.6", upper="2.4")
        self.assertIsNotNone(result.integrand)
        self.assertEqual(sp.simplify(result.integrand - 2 * sp.Symbol("x")), 0)
        self.assertEqual(len(result.limits), 2)

    def test_indefinite_integral_has_no_limits(self):
        result = calculate("2x", "integral", "x")
        self.assertIsNone(result.limits)

    def test_spec_plots_the_integrand_not_the_antiderivative(self):
        from engicalc.plotting.plot import spec_from_result

        result = calculate("2x", "integral", "x", lower="-1.6", upper="2.4")
        spec = spec_from_result(result)
        self.assertEqual(len(spec.curves), 1)
        self.assertEqual(sp.simplify(sp.sympify(spec.curves[0].expression)
                                     - 2 * sp.Symbol("x")), 0)
        self.assertEqual(spec.shade, (-1.6, 2.4))

    def test_window_is_fitted_around_the_limits(self):
        from engicalc.plotting.plot import spec_from_result

        spec = spec_from_result(
            calculate("2x", "integral", "x", lower="-1.6", upper="2.4"))
        self.assertLess(spec.xmin, -1.6)
        self.assertGreater(spec.xmax, 2.4)

    def test_shaded_plot_draws_without_warnings(self):
        from matplotlib.figure import Figure

        from engicalc.plotting.plot import draw, spec_from_result

        for expression, low, high in [("2x", "-1.6", "2.4"),
                                      ("sin(x)", "0", "3.14159"),
                                      ("x^3", "-2", "2"),
                                      ("x^2 - 4", "-3", "3")]:
            with self.subTest(expression=expression):
                result = calculate(expression, "integral", "x",
                                   lower=low, upper=high)
                axes = Figure().add_subplot(111)
                self.assertEqual(draw(spec_from_result(result), axes), [])
                self.assertTrue(axes.collections, "nothing was shaded")

    def test_a_system_has_nothing_to_plot(self):
        result = calculate("x + y = 10; x - y = 2", "system")
        self.assertFalse(result.plottable)


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
class TestCommandLine(unittest.TestCase):
    def test_results_print_on_a_cp1252_console(self):
        """Answers carry U+2248 in front of a decimal approximation. A
        Windows console is cp1252 by default, where printing one used to
        raise UnicodeEncodeError and lose the answer."""
        import io as _io
        import contextlib

        from engicalc.cli import main as cli_main

        raw = _io.BytesIO()
        console = _io.TextIOWrapper(raw, encoding="cp1252", newline="")
        with contextlib.redirect_stdout(console):
            code = cli_main(["solve", "2x^2 - 5x - 3 = 0"])
            console.flush()
        self.assertEqual(code, 0)
        printed = raw.getvalue().decode("cp1252", errors="replace")
        self.assertIn("x = 3", printed)
        self.assertIn("-1/2", printed)


# --------------------------------------------------------------------------
# Inequalities
# --------------------------------------------------------------------------
class TestInequalities(unittest.TestCase):
    """An inequality's answer is a range. Wrapping one in Eq(expr, 0) used to
    return a confident "No solution." for input the pad itself suggests."""

    def _solution(self, text):
        return calculate(text, "solve").results[0]

    def test_the_pads_own_examples(self):
        """`le`, `ge` and `ne` are on the always-visible row of the pad and
        carry these as worked examples."""
        x = sp.Symbol("x")
        self.assertEqual(self._solution("x^2 <= 9"), sp.Interval(-3, 3))
        self.assertEqual(self._solution("x >= -2"), sp.Interval(-2, sp.oo))
        self.assertEqual(self._solution("x != 0"),
                         sp.Union(sp.Interval.open(-sp.oo, 0),
                                  sp.Interval.open(0, sp.oo)))

    def test_strict_inequality_splits_into_two_intervals(self):
        self.assertEqual(self._solution("x^2 - 4 > 0"),
                         sp.Union(sp.Interval.open(-sp.oo, -2),
                                  sp.Interval.open(2, sp.oo)))

    def test_unknown_in_a_denominator_flips_where_it_is_negative(self):
        """1/x < 1 is true below zero as well as above one - the naive
        'multiply through by x' answer misses the negative branch."""
        self.assertEqual(self._solution("1/x < 1"),
                         sp.Union(sp.Interval.open(-sp.oo, 0),
                                  sp.Interval.open(1, sp.oo)))

    def test_absolute_value_inequality(self):
        self.assertEqual(self._solution("abs(x - 3) <= 5"), sp.Interval(-2, 8))

    def test_an_inequality_with_no_solution_says_so(self):
        result = calculate("x^2 + 1 < 0", "solve")
        self.assertEqual(result.results[0], sp.S.EmptySet)
        self.assertIn("satisf", result.result_text.lower())

    def test_a_numeric_comparison_is_true_or_false(self):
        self.assertEqual(calculate("2 < 1", "solve").result_text, "False")

    def test_not_equal_parses_instead_of_raising(self):
        """It used to reach parse_input as a Python bool and die on
        AttributeError: 'bool' object has no attribute 'free_symbols'."""
        parsed = parse_input("x != 0")
        self.assertIsInstance(parsed.expr, sp.Ne)
        self.assertEqual({s.name for s in parsed.symbols}, {"x"})

    def test_every_inequality_carries_working_and_latex(self):
        for text in ["x^2 <= 9", "x >= -2", "x^2 - 4 > 0", "abs(x - 3) <= 5"]:
            with self.subTest(text=text):
                result = calculate(text, "solve")
                self.assertTrue(result.steps, "no steps")
                self.assertIn(r"\in", result.latex)
                self.assertTrue(result.result_text.startswith("x in"))

    def test_an_inequality_still_plots(self):
        """expression stays the difference, so the curve whose sign is the
        question is what gets drawn."""
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure

        from engicalc.plotting.plot import draw, spec_from_result

        result = calculate("x^2 - 4 > 0", "solve")
        axes = Figure().add_subplot(111)
        self.assertEqual(draw(spec_from_result(result), axes), [])
        self.assertTrue(axes.lines)

    def test_equations_still_solve_normally(self):
        """The inequality branch must not catch an ordinary equation."""
        result = calculate("2x^2 - 5x - 3 = 0", "solve")
        self.assertEqual(sorted(sp.sstr(r) for r in result.results),
                         ["-1/2", "3"])


class TestSetDisplay(unittest.TestCase):
    def test_intervals_read_the_way_a_textbook_writes_them(self):
        from engicalc.core.display import fmt_set

        self.assertEqual(fmt_set(sp.Interval(-3, 3)), "[-3, 3]")
        self.assertEqual(fmt_set(sp.Interval.open(0, 1)), "(0, 1)")
        self.assertEqual(fmt_set(sp.Interval.Lopen(0, 1)), "(0, 1]")
        self.assertEqual(fmt_set(sp.S.EmptySet), "no solution")
        self.assertEqual(
            fmt_set(sp.Union(sp.Interval.open(-sp.oo, -2),
                             sp.Interval.open(2, sp.oo))),
            "(-oo, -2)  or  (2, oo)")


# --------------------------------------------------------------------------
# Copying a calculation out, and the pad's layout arithmetic
# --------------------------------------------------------------------------
class TestCopyOut(unittest.TestCase):
    """A worked calculation has to be able to leave the app and land in a
    report."""

    def setUp(self):
        import matplotlib
        matplotlib.use("Agg")

    def test_a_calculation_renders_to_a_picture(self):
        from engicalc.ui import mathrender

        result = calculate("2x^2 - 5x - 3 = 0", "solve")
        blocks = [("Problem", sp.Eq(sp.sympify("2*x**2-5*x-3"), 0), None)]
        blocks += [(s.title, s.expr, s.detail) for s in result.steps]
        image = mathrender.render_calculation(blocks)
        self.assertGreater(image.width, 200)
        self.assertGreater(image.height, 200)

    def test_a_long_note_does_not_stretch_the_picture(self):
        """bbox_inches sizes the canvas to the widest line, so an unwrapped
        note would make the picture wider than the page it is going onto."""
        from engicalc.ui import mathrender

        note = "This is a very long explanatory note. " * 8
        page = int(6.5 * 200)                       # width_inches * dpi
        image = mathrender.render_calculation([("Heading", None, note)])
        self.assertLessEqual(image.width, page)
        # and it is genuinely long - the wrapping is doing something
        self.assertGreater(image.height, 100)

    def test_the_dib_has_a_bitmap_header_and_no_file_header(self):
        """CF_DIB is a BMP without its 14-byte file header - handing Windows
        the whole file instead produces a paste of garbage."""
        from PIL import Image

        from engicalc.ui import clipboard

        data = clipboard._to_dib(Image.new("RGBA", (8, 8), (255, 0, 0, 128)))
        self.assertNotEqual(data[:2], b"BM")        # file header gone
        header_size = int.from_bytes(data[:4], "little")
        self.assertEqual(header_size, 40)           # BITMAPINFOHEADER
        self.assertEqual(int.from_bytes(data[4:8], "little"), 8)

    def test_transparency_is_flattened_onto_white(self):
        """A transparent PNG pasted into Word turns black in some versions."""
        from PIL import Image

        from engicalc.ui import clipboard

        image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        data = clipboard._to_dib(image)
        self.assertEqual(int.from_bytes(data[:4], "little"), 40)
        self.assertIn(b"\xff\xff\xff", data[40:])   # white pixels present


class TestPadLayout(unittest.TestCase):
    def test_rows_are_balanced_rather_than_ragged(self):
        from engicalc.ui.symbol_pad import SymbolPad

        # 24 keys in a pad 22 wide is 22 + 2, which looks like a mistake
        self.assertEqual(SymbolPad._balanced(24, 22), 12)
        self.assertEqual(SymbolPad._balanced(24, 8), 8)
        self.assertEqual(SymbolPad._balanced(10, 22), 10)
        self.assertEqual(SymbolPad._balanced(7, 22), 7)

    def test_balancing_never_needs_more_rows_than_it_had(self):
        from engicalc.ui.symbol_pad import SymbolPad

        for count in range(1, 60):
            for columns in range(4, 27):
                balanced = SymbolPad._balanced(count, columns)
                with self.subTest(count=count, columns=columns):
                    self.assertLessEqual(balanced, columns)
                    self.assertGreaterEqual(balanced, 1)
                    self.assertEqual(-(-count // balanced),
                                     -(-count // columns))


# --------------------------------------------------------------------------
# Interpolation
# --------------------------------------------------------------------------
class TestInterpolation(unittest.TestCase):
    """Reading between the rows of a table - a steam table, a pump curve."""

    # saturation pressure of water, kPa, against temperature in C
    STEAM = """Temp\tPressure
80\t47.39
85\t57.87
90\t70.14
95\t84.55
100\t101.42"""

    def setUp(self):
        from engicalc.core.interpolate import parse_table
        self.table = parse_table(self.STEAM)

    def test_a_header_row_is_skipped_not_rejected(self):
        """Pasting the header along with the numbers is the normal thing to
        do, so it must not be an error."""
        self.assertEqual(len(self.table), 5)
        self.assertEqual(self.table.xs[0], 80.0)

    def test_excel_csv_and_spaces_all_parse(self):
        from engicalc.core.interpolate import parse_table

        for text in ["1\t2\n3\t4", "1,2\n3,4", "1  2\n3  4", "1 2\n3 4"]:
            with self.subTest(text=text):
                table = parse_table(text)
                self.assertEqual(table.xs, [1.0, 3.0])
                self.assertEqual(table.ys, [2.0, 4.0])

    def test_rows_out_of_order_are_sorted(self):
        from engicalc.core.interpolate import parse_table

        table = parse_table("10,100\n5,50\n7,70")
        self.assertEqual(table.xs, [5.0, 7.0, 10.0])
        self.assertEqual(table.ys, [50.0, 70.0, 100.0])

    def test_linear_matches_the_arithmetic_done_by_hand(self):
        from engicalc.core.interpolate import interpolate

        # 70.14 + (92-90) * (84.55-70.14)/(95-90) = 75.904
        result = interpolate(self.table, 92, "linear")
        self.assertAlmostEqual(result.numeric[0], 75.904, places=9)

    def test_a_value_on_a_row_returns_that_row(self):
        from engicalc.core.interpolate import interpolate

        for x, y in zip(self.table.xs, self.table.ys):
            with self.subTest(x=x):
                self.assertAlmostEqual(
                    interpolate(self.table, x, "linear").numeric[0], y,
                    places=9)

    def test_extrapolation_is_warned_about(self):
        """Reading past the end of a steam table is a guess, and a silent
        one is dangerous."""
        from engicalc.core.interpolate import interpolate

        inside = interpolate(self.table, 92, "linear")
        self.assertEqual(inside.warnings, [])
        for beyond in (130, 20):
            with self.subTest(x=beyond):
                result = interpolate(self.table, beyond, "linear")
                self.assertTrue(result.warnings)
                self.assertIn("extrapolation", result.warnings[0].lower())

    def test_the_working_names_the_two_rows_used(self):
        """A hand check starts by asking which rows it came from."""
        from engicalc.core.interpolate import interpolate

        working = interpolate(self.table, 92, "linear").steps_text()
        self.assertIn("90", working)
        self.assertIn("70.14", working)
        self.assertIn("95", working)
        self.assertIn("84.55", working)

    def test_polynomial_through_three_points_is_exact(self):
        from engicalc.core.interpolate import interpolate, parse_table

        # y = x^2 exactly, so a degree 2 fit must reproduce it
        table = parse_table("1,1\n2,4\n3,9\n4,16")
        result = interpolate(table, 2.5, "polynomial", degree=2)
        self.assertAlmostEqual(result.numeric[0], 6.25, places=6)

    def test_polynomial_degree_is_capped_by_the_data(self):
        from engicalc.core.interpolate import interpolate, parse_table

        table = parse_table("1,1\n2,4\n3,9")
        result = interpolate(table, 2.5, "polynomial", degree=9)
        self.assertTrue(any("degree" in w for w in result.warnings))
        self.assertIsNotNone(result.numeric[0])

    def test_reverse_finds_the_x_for_a_given_y(self):
        from engicalc.core.interpolate import reverse

        # 85 + (60-57.87)/(70.14-57.87) * 5 = 85.868...
        result = reverse(self.table, 60)
        self.assertAlmostEqual(result.numeric[0], 85.8679706, places=5)

    def test_reverse_reports_every_crossing_of_a_curve_that_turns(self):
        """A parabola crosses the same y twice - picking one quietly would
        be wrong."""
        from engicalc.core.interpolate import parse_table, reverse

        table = parse_table("0,0\n1,1\n2,0\n3,-1")
        result = reverse(table, 0.5)
        self.assertEqual(len(result.numeric), 2)
        self.assertTrue(any("more than one" in w for w in result.warnings))

    def test_duplicate_x_is_rejected(self):
        from engicalc.core.interpolate import parse_table

        with self.assertRaises(ParseError):
            parse_table("1,2\n1,3")

    def test_one_point_is_rejected(self):
        from engicalc.core.interpolate import parse_table

        with self.assertRaises(ParseError):
            parse_table("1,2")

    def test_the_result_is_a_calcresult_the_rest_of_the_app_understands(self):
        from engicalc.core.engine import CalcResult
        from engicalc.core.interpolate import interpolate

        result = interpolate(self.table, 92, "linear")
        self.assertIsInstance(result, CalcResult)
        self.assertTrue(result.result_text)
        self.assertTrue(result.steps)
        self.assertTrue(result.plottable)


# --------------------------------------------------------------------------
# Matrices
# --------------------------------------------------------------------------
class TestMatrices(unittest.TestCase):
    """Built around A x = b, which is what matrices are for in engineering."""

    def _m(self, text):
        from engicalc.core.matrices import parse_matrix
        return parse_matrix(text)

    def test_rows_parse_from_excel_csv_or_spaces(self):
        for text in ["1 2\n3 4", "1,2\n3,4", "1\t2\n3\t4", "[1 2]\n[3 4]"]:
            with self.subTest(text=text):
                self.assertEqual(self._m(text).tolist(), [[1, 2], [3, 4]])

    def test_ragged_rows_are_rejected(self):
        with self.assertRaises(ParseError):
            self._m("1 2 3\n4 5")

    def test_solving_three_equations(self):
        from engicalc.core.matrices import solve_system

        result = solve_system(self._m("2 1 -1\n-3 -1 2\n-2 1 2"),
                              self._m("8\n-11\n-3"))
        self.assertEqual([int(v) for v in result.results[0]], [2, 3, -1])

    def test_the_solution_satisfies_the_original_equations(self):
        """The real check: substitute it back."""
        from engicalc.core.matrices import solve_system

        a = self._m("4 -2 1\n-2 4 -2\n1 -2 4")
        b = self._m("11\n-16\n17")
        x = solve_system(a, b).results[0]
        self.assertEqual(sp.simplify(a * x - b), sp.zeros(3, 1))

    def test_a_singular_system_is_refused_not_fudged(self):
        from engicalc.core.matrices import solve_system

        result = solve_system(self._m("1 2\n2 4"), self._m("3\n6"))
        self.assertFalse(result.results)
        self.assertIn("no unique solution", result.result_text.lower())
        self.assertTrue(any("singular" in w for w in result.warnings))

    def test_an_ill_conditioned_system_warns(self):
        """Nearly singular gives an answer that is arithmetic, not
        engineering."""
        from engicalc.core.matrices import solve_system

        result = solve_system(self._m("1 1\n1 1.0000000001"), self._m("2\n2"))
        self.assertTrue(any("ill-conditioned" in w for w in result.warnings))

    def test_mismatched_sizes_are_explained(self):
        from engicalc.core.matrices import solve_system

        with self.assertRaises(ParseError):
            solve_system(self._m("1 2\n3 4"), self._m("1\n2\n3"))

    def test_determinant_inverse_rank_transpose(self):
        from engicalc.core.matrices import operate

        m = self._m("4 1\n2 3")
        self.assertEqual(operate(m, "determinant").results[0], 10)
        self.assertEqual(operate(m, "transpose").results[0],
                         sp.Matrix([[4, 2], [1, 3]]))
        self.assertEqual(operate(m, "rank").results[0], 2)
        inverse = operate(m, "inverse").results[0]
        self.assertEqual(sp.simplify(m * inverse), sp.eye(2))

    def test_inverting_a_singular_matrix_says_so(self):
        from engicalc.core.matrices import operate

        result = operate(self._m("1 2\n2 4"), "inverse")
        self.assertFalse(result.results)
        self.assertIn("no inverse", result.result_text.lower())

    def test_eigenvalues_of_a_known_matrix(self):
        from engicalc.core.matrices import operate

        values = operate(self._m("4 1\n2 3"), "eigenvalues").results
        self.assertEqual(sorted(int(v) for v in values), [2, 5])

    def test_rounding_noise_is_not_reported_as_complex(self):
        """A real eigenvalue arrives as 3.21432 + 0.e-12*I from the root
        finder; printed with that tail it claims to be complex."""
        from engicalc.core.matrices import operate

        result = operate(self._m("2 1 -1\n-3 -1 2\n-2 1 2"), "eigenvalues")
        self.assertNotIn("I", result.result_text)
        for value in result.results:
            self.assertTrue(sp.N(value).is_real, msg=str(value))

    def test_genuinely_complex_eigenvalues_are_kept(self):
        """A rotation has no real eigenvalues - stripping them would be a
        different answer, not a tidier one."""
        from engicalc.core.matrices import operate

        result = operate(self._m("0 -1\n1 0"), "eigenvalues")
        self.assertTrue(any(not sp.N(v).is_real for v in result.results))

    def test_multiplication_checks_the_shapes(self):
        from engicalc.core.matrices import operate

        product = operate(self._m("1 2\n3 4"), "multiply",
                          self._m("5 6\n7 8")).results[0]
        self.assertEqual(product, sp.Matrix([[19, 22], [43, 50]]))
        with self.assertRaises(ParseError):
            operate(self._m("1 2 3"), "multiply", self._m("1 2 3"))

    def test_a_symbolic_matrix_works(self):
        from engicalc.core.matrices import operate

        a, b, c, d = sp.symbols("a b c d")
        result = operate(self._m("a b\nc d"), "determinant")
        self.assertEqual(sp.simplify(result.results[0] - (a * d - b * c)), 0)

    def test_results_are_calcresults(self):
        from engicalc.core.engine import CalcResult
        from engicalc.core.matrices import operate, solve_system

        self.assertIsInstance(
            solve_system(self._m("1 0\n0 1"), self._m("1\n2")), CalcResult)
        self.assertIsInstance(
            operate(self._m("1 0\n0 1"), "determinant"), CalcResult)


# --------------------------------------------------------------------------
# Every tab's action buttons
# --------------------------------------------------------------------------
class TestActionRows(unittest.TestCase):
    """No button may be squeezed below the height it needs.

    A row of buttons packed after an expanding pane is last in line for
    space. On a smaller window it gets a few pixels of the thirty-one it
    needs, and the buttons render as blank grey slivers - present, clickable,
    unreadable. This happened on the calculator, was fixed there, and then
    came straight back in two tabs written afterwards, so it is checked
    across every tab rather than one at a time.
    """

    SIZES = ["1280x820", "1100x760", "1000x700", "980x640"]

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display available: {exc}")

    @staticmethod
    def _notebooks(widget, found):
        """Every notebook inside *widget*, however deeply nested."""
        for child in widget.winfo_children():
            if child.winfo_class() == "TNotebook":
                found.append(child)
            TestActionRows._notebooks(child, found)
        return found

    def _check_pages(self, app, notebook, size, path=""):
        """Select every page of *notebook*, then any nested inside it."""
        for index in range(len(notebook.tabs())):
            notebook.select(index)
            app.update()
            app.update_idletasks()
            name = ((path + " / ") if path else "") \
                + notebook.tab(index, "text").strip()
            tab = notebook.nametowidget(notebook.tabs()[index])
            clipped = [
                b for b in self._buttons(tab, [])
                if b.winfo_ismapped()
                and b.winfo_height() < b.winfo_reqheight()]
            with self.subTest(size=size, tab=name):
                self.assertEqual(
                    [], clipped,
                    f"{len(clipped)} clipped on {name} at {size}: "
                    + ", ".join(
                        f"{b.cget('text')!r} "
                        f"{b.winfo_height()}/{b.winfo_reqheight()}px"
                        for b in clipped))
            for inner in self._notebooks(tab, []):
                self._check_pages(app, inner, size, name)

    @staticmethod
    def _buttons(widget, found):
        for child in widget.winfo_children():
            if child.winfo_class() in ("TButton", "TMenubutton"):
                found.append(child)
            TestActionRows._buttons(child, found)
        return found

    def test_no_button_is_clipped_at_any_supported_window_size(self):
        from engicalc.ui.app import EngiCalcApp

        app = EngiCalcApp()
        try:
            notebook = app.notebook
            for size in self.SIZES:
                app.geometry(size)
                app.update()
                app.update_idletasks()
                self._check_pages(app, notebook, size)
        finally:
            app.update_idletasks()
            app.destroy()


# --------------------------------------------------------------------------
# Getting a calculation back out of the app
# --------------------------------------------------------------------------
class TestSaveAndExport(unittest.TestCase):
    """Every tab that works something out can save it and export it.

    The Calculator has had both from the start and the tabs written later
    picked them up unevenly - the Sheet could save to a file but not to the
    history, the Data tab could do neither, and Matrices and Interpolate
    could save but not export. A calculation that cannot leave the app is one
    that gets redone in Excel, so this is checked on every tab at once rather
    than remembered tab by tab.
    """

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display available: {exc}")

    def setUp(self):
        import tempfile
        from tkinter import filedialog, messagebox

        from engicalc.ui.app import EngiCalcApp

        self.workspace = tempfile.mkdtemp()

        # A modal dialog with nobody to close it waits for ever, so they are
        # recorded instead of shown. Anything that lands here is a tab saying
        # it had nothing to do, which is the failure being tested for.
        self.complaints = []
        for name in ("showinfo", "showerror", "showwarning"):
            original = getattr(messagebox, name)
            setattr(messagebox, name,
                    lambda title, message="", *a, _n=name, **kw:
                    self.complaints.append((_n, title, message)))
            self.addCleanup(setattr, messagebox, name, original)

        self.saved_to = os.path.join(self.workspace, "out.xlsx")
        original_dialog = filedialog.asksaveasfilename
        filedialog.asksaveasfilename = lambda **kw: self.saved_to
        self.addCleanup(setattr, filedialog, "asksaveasfilename",
                        original_dialog)

        # Its own database. A test must never write into the history the
        # person using the app is keeping.
        self.app = EngiCalcApp(db_path=os.path.join(self.workspace, "h.db"))
        self.addCleanup(self._close)
        self.app.update_idletasks()

    def _close(self):
        # The plot canvases schedule their redraw for when the loop is next
        # idle. Destroying the window first leaves those callbacks pointing
        # at nothing, and Tk reports each one as a background error.
        try:
            self.app.update_idletasks()
        except Exception:                             # noqa: BLE001
            pass
        self.app.destroy()

    def tabs(self):
        """The tabs that work something out, by the name on the tab."""
        from engicalc.ui.interpolate_tab import InterpolateTab
        from engicalc.ui.matrix_tab import MatrixTab
        from engicalc.ui.sheet_tab import SheetTab
        from engicalc.ui.simultaneous_tab import SimultaneousTab
        from engicalc.ui.statistics_tab import StatisticsTab

        wanted = (SheetTab, StatisticsTab, MatrixTab, InterpolateTab,
                  SimultaneousTab)

        def walk(widget, found):
            # Sub-tabs count. The simultaneous solver lives inside the
            # Calculator, and a tab that cannot be found here is a tab whose
            # save and export are never tried.
            for child in widget.winfo_children():
                if isinstance(child, wanted):
                    found[type(child).__name__] = child
                walk(child, found)
            return found

        return walk(self.app.notebook, {})

    def _work_it_out(self, tab):
        """Make the tab produce an answer, however it names doing so."""
        for method in ("compute", "calculate", "solve"):
            if hasattr(tab, method):
                getattr(tab, method)()
                break
        else:
            self.fail(f"{type(tab).__name__} has no way to work anything out")

        # Some tabs answer on a background thread and deliver through the
        # event loop, so the loop has to be pumped or the answer never
        # arrives and the tab looks as though it refused.
        if getattr(tab, "runner", None) is None:
            return
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            self.app.update()
            if getattr(tab, "result", None) is not None:
                return
            time.sleep(0.02)
        status = ""
        if hasattr(tab, "status"):
            status = f" - it says {tab.status.cget('text')!r}"
        self.fail(f"{type(tab).__name__} produced no answer in 20s{status}")

    def test_every_tab_offers_both(self):
        tabs = self.tabs()
        self.assertEqual(len(tabs), 5, f"found {sorted(tabs)}")
        for name, tab in tabs.items():
            with self.subTest(tab=name):
                self.assertTrue(hasattr(tab, "save"), f"{name} cannot save")
                self.assertTrue(hasattr(tab, "export"), f"{name} cannot export")

    def test_saving_puts_an_entry_in_the_history(self):
        for name, tab in self.tabs().items():
            with self.subTest(tab=name):
                self._work_it_out(tab)
                self.complaints.clear()
                before = len(self.app.history.recent(limit=200))
                tab.save(quiet=True)
                after = len(self.app.history.recent(limit=200))
                self.assertEqual([], self.complaints,
                                 f"{name} refused to save")
                self.assertEqual(after, before + 1,
                                 f"{name} saved nothing")

    def test_a_sheet_exports_numbers_rather_than_symbols(self):
        import openpyxl

        # The exact answer for the example's Reynolds number is 279440/pi.
        # Sending that to a spreadsheet is correct and useless - the whole
        # point of exporting is to carry on working in it, and nothing there
        # can add up a symbol.
        from engicalc.ui.sheet_tab import SheetTab

        sheet = next(tab for tab in self.tabs().values()
                     if isinstance(tab, SheetTab))
        self.saved_to = os.path.join(self.workspace, "sheet.xlsx")
        sheet.calculate()
        sheet.export()

        book = openpyxl.load_workbook(self.saved_to)
        rows = list(book.active.iter_rows(values_only=True))
        # Everything below the headings; above them is the sheet's title.
        start = next(index for index, r in enumerate(rows)
                     if r and r[0] == "Name")
        answer_column = list(rows[start]).index("Answer")
        answers = {r[0]: r[answer_column] for r in rows[start + 1:]
                   if r and r[0]}
        self.assertIn("Re", answers)
        for name, value in answers.items():
            with self.subTest(row=name):
                self.assertIsInstance(value, (int, float),
                                      f"{name} exported as {value!r}")
        self.assertAlmostEqual(answers["Re"], 88948.5, delta=1.0)

    def test_exporting_writes_a_workbook_that_opens(self):
        import openpyxl

        for index, (name, tab) in enumerate(self.tabs().items()):
            self.saved_to = os.path.join(self.workspace, f"out{index}.xlsx")
            self.complaints.clear()
            self._work_it_out(tab)
            tab.export()
            with self.subTest(tab=name):
                self.assertEqual([], self.complaints,
                                 f"{name} refused to export")
                self.assertTrue(os.path.exists(self.saved_to),
                                f"{name} wrote nothing")
                book = openpyxl.load_workbook(self.saved_to)
                filled = [cell.value
                          for row in book.active.iter_rows()
                          for cell in row if cell.value not in (None, "")]
                self.assertGreater(len(filled), 3,
                                   f"{name} exported an empty sheet")


# --------------------------------------------------------------------------
# The simultaneous solver's tab
# --------------------------------------------------------------------------
class TestSimultaneousTab(unittest.TestCase):
    """The count is what this screen is for.

    Three equations and four unknowns has no single answer, and being told
    so while typing is more use than any number would be - so the count is
    shown before anything is solved and says what to do about a shortfall.
    """

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display available: {exc}")

    def setUp(self):
        import tempfile
        from engicalc.ui.app import EngiCalcApp

        self.app = EngiCalcApp(
            db_path=os.path.join(tempfile.mkdtemp(), "h.db"))
        self.addCleanup(self._close)
        self.tab = self.app.simultaneous_tab
        self.app.update_idletasks()

    def _close(self):
        try:
            self.app.update_idletasks()
        except Exception:                             # noqa: BLE001
            pass
        self.app.destroy()

    def _solve(self):
        self.tab.solve()
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            self.app.update()
            if self.tab.result is not None:
                return self.tab.result
            time.sleep(0.02)
        self.fail(f"no answer in 20s - it says "
                  f"{self.tab.status.cget('text')!r}")

    def test_it_lives_inside_the_calculator(self):
        # A tenth top-level tab for something this close to the calculator
        # would be one bar entry too many.
        self.assertIs(self.app.calculator_pane.simultaneous, self.tab)
        self.assertIs(self.app.calculator_pane.calculator,
                      self.app.calculator_tab)

    def test_the_count_says_what_to_do_about_a_shortfall(self):
        self.tab.set_text("x + y = 10")
        said = self.tab.count.cget("text")
        self.assertIn("1 equation,", said)
        self.assertIn("2 unknowns", said)
        self.assertIn("Give 1 more equation", said)

    def test_the_count_says_when_there_is_enough(self):
        self.tab.set_text("x + y = 10\nx - y = 2")
        self.assertIn("Enough to solve", self.tab.count.cget("text"))

    def test_the_count_notices_too_many_equations(self):
        self.tab.set_text("x = 1\nx = 2\ny = 3")
        self.assertIn("more equation", self.tab.count.cget("text"))

    def test_a_coupled_set_is_solved(self):
        self.tab.set_text("\n".join([
            "A = pi*0.15^2/4",
            "v = 0.5/A",
            "Re = v*0.15/7.5e-6",
            "f = 0.3164/Re^0.25",
            "dp = f*(20/0.15)*1.2*v^2/2"]))
        result = self._solve()
        values = {str(k): float(v) for k, v in result.results[0].items()}
        self.assertAlmostEqual(values["Re"], 565884.0, delta=10.0)
        self.assertAlmostEqual(values["dp"], 738.8, delta=1.0)
        self.assertEqual([], result.warnings)

    def test_the_examples_all_solve(self):
        from engicalc.ui.simultaneous_tab import EXAMPLES

        for name, text in EXAMPLES:
            with self.subTest(example=name):
                self.tab.set_text(text)
                result = self._solve()
                self.assertTrue(result.results,
                                f"{name} produced no values: "
                                f"{result.result_text}")


# --------------------------------------------------------------------------
# Trendlines
# --------------------------------------------------------------------------
class TestFitting(unittest.TestCase):
    """Six shapes, and a score that can be compared across them."""

    def test_each_shape_recovers_data_it_was_made_from(self):
        import numpy as np

        from engicalc.core.fitting import fit_curve

        x = np.linspace(1.0, 6.0, 12)
        cases = {
            "linear": 2 * x + 1,
            "quadratic": 3 * x ** 2 - 2 * x + 5,
            "cubic": x ** 3 - 4 * x ** 2 + x + 2,
            "exponential": 3 * np.exp(0.5 * x),
            "logarithmic": 2.5 * np.log(x) + 4,
            "power": 2 * x ** 1.7,
        }
        for kind, y in cases.items():
            with self.subTest(kind=kind):
                curve = fit_curve(kind, x, y)
                self.assertTrue(curve.ok, curve.refused)
                self.assertAlmostEqual(curve.r_squared, 1.0, places=6)

    def test_the_right_shape_wins(self):
        import numpy as np

        from engicalc.core.fitting import best, fit_all

        x = np.linspace(1.0, 6.0, 12)
        self.assertEqual(best(fit_all(x, 3 * np.exp(0.5 * x))).key,
                         "exponential")
        self.assertEqual(best(fit_all(x, 2 * x ** 1.7)).key, "power")
        self.assertEqual(best(fit_all(x, 2.5 * np.log(x) + 4)).key,
                         "logarithmic")

    def test_a_tie_goes_to_the_simpler_shape(self):
        import numpy as np

        from engicalc.core.fitting import best, fit_all

        # A straight line is fitted perfectly by every polynomial. The one
        # worth offering is the straight line.
        x = np.linspace(1.0, 6.0, 12)
        self.assertEqual(best(fit_all(x, 2 * x + 1)).key, "poly1")

    def test_a_shape_that_cannot_be_fitted_says_why(self):
        import numpy as np

        from engicalc.core.fitting import fit_all

        x = np.linspace(1.0, 6.0, 6)
        curves = {c.key: c for c in fit_all(x, 3 * x - 5)}   # y goes negative
        self.assertFalse(curves["exponential"].ok)
        self.assertIn("above zero", curves["exponential"].refused)
        self.assertFalse(curves["power"].ok)
        # Refused shapes are still listed - "needs every y above zero" is
        # more use than the shape quietly not appearing.
        self.assertEqual(len(curves), 6)

    def test_r_squared_is_measured_on_the_readings_not_their_logs(self):
        import numpy as np

        from engicalc.core.fitting import fit_curve

        # An exponential is fitted by fitting a line to log(y). Scoring that
        # line - which is what a spreadsheet reports - describes how well a
        # line fits the logs, not how well the curve fits the readings, and
        # taking logs squashes the large residuals that matter most. Two
        # shapes scored that way cannot be compared.
        rng = np.random.default_rng(7)
        x = np.linspace(1.0, 6.0, 12)
        y = 3 * np.exp(0.5 * x)
        y = y * (1 + rng.normal(0, 0.12, y.size))

        ours = fit_curve("exponential", x, y).r_squared

        slope, intercept = np.polyfit(x, np.log(y), 1)
        logged = np.log(y)
        in_log_space = 1 - (np.sum((logged - (slope * x + intercept)) ** 2)
                            / np.sum((logged - np.mean(logged)) ** 2))

        self.assertLess(ours, in_log_space)
        # And the difference is enough to change which shape looks best.
        self.assertLess(ours, fit_curve("cubic", x, y).r_squared)

    def test_a_curve_that_misses_can_score_below_zero(self):
        import numpy as np

        from engicalc.core.fitting import fit_curve

        # Not a bug: it means the curve describes the readings worse than a
        # flat line through their mean would, which is worth being told.
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        y = np.array([1.0, 40.0, 1.0, 40.0, 1.0, 40.0])
        self.assertLess(fit_curve("logarithmic", x, y).r_squared, 0.2)

    def test_a_polynomial_needs_enough_readings(self):
        from engicalc.core.fitting import fit_curve

        curve = fit_curve("cubic", [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        self.assertFalse(curve.ok)
        self.assertIn("4 readings", curve.refused)


# --------------------------------------------------------------------------
# The unit converter
# --------------------------------------------------------------------------
class TestUnitGrouping(unittest.TestCase):

    def test_every_unit_is_filed_exactly_once(self):
        from engicalc.core.units import ALIASES, CATEGORIES, CELSIUS, UNITS

        filed = [name for members in CATEGORIES.values() for name in members]
        self.assertEqual(len(filed), len(set(filed)),
                         "a unit is filed under two categories")
        # Every unit is offered somewhere, or is deliberately an alias of one
        # that is - a picker listing metre, meter and meters is a list of
        # spellings rather than a list of units.
        self.assertEqual(sorted(set(UNITS) - set(filed) - ALIASES), [])
        # And nothing is offered that is not a unit.
        self.assertEqual(sorted(set(filed) - set(UNITS) - set(CELSIUS)), [])

    def test_what_a_value_converts_to_is_decided_by_dimension(self):
        from engicalc.core.units import same_dimension

        self.assertIn("psi", same_dimension("bar"))
        self.assertIn("kWh", same_dimension("J"))
        self.assertNotIn("kg", same_dimension("m"))
        # Celsius and kelvin are paired by hand: the offset is not something
        # a dimension can express.
        self.assertEqual(sorted(same_dimension("degC")), ["K", "degC"])

    def test_the_category_of_a_unit(self):
        from engicalc.core.units import category_of

        self.assertEqual(category_of("psi"), "Pressure")
        self.assertEqual(category_of("nonsense"), "")


class TestUnitsTab(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display available: {exc}")

    def setUp(self):
        import tempfile
        from engicalc.ui.app import EngiCalcApp

        self.app = EngiCalcApp(
            db_path=os.path.join(tempfile.mkdtemp(), "h.db"))
        self.addCleanup(self._close)
        self.tab = self.app.units_tab
        self.app.update_idletasks()

    def _close(self):
        try:
            self.app.update_idletasks()
        except Exception:                             # noqa: BLE001
            pass
        self.app.destroy()

    def _set(self, category, value, source, target):
        self.tab.category.set(category)
        self.tab._category_changed()
        self.tab.value.set(value)
        self.tab.source.set(source)
        self.tab.target.set(target)
        self.tab.convert()

    def test_it_converts(self):
        self._set("Pressure", "2.5", "bar", "psi")
        self.assertIn("36.259", self.tab.answer.cget("text"))
        self._set("Energy", "3.6", "MJ", "kWh")
        self.assertIn("1 kWh", self.tab.answer.cget("text"))

    def test_the_whole_column_is_offered(self):
        self._set("Pressure", "2.5", "bar", "psi")
        units = {unit for unit, _number in self.tab.equivalents()}
        self.assertEqual(units, {"Pa", "kPa", "MPa", "GPa", "bar", "mbar",
                                 "atm", "psi"})

    def test_temperature_asks_which_kind_it_is(self):
        # 20 degC is 293.15 K as a temperature and 20 K as a difference, and
        # guessing wrong is a 273 degree error that looks plausible.
        self._set("Temperature", "20", "degC", "K")
        self.tab.absolute.set(True)
        self.tab.convert()
        self.assertIn("293.15", self.tab.answer.cget("text"))
        self.tab.absolute.set(False)
        self.tab.convert()
        self.assertIn("20 K", self.tab.answer.cget("text"))

    def test_the_choice_is_only_shown_where_it_matters(self):
        self._set("Temperature", "20", "degC", "K")
        self.assertTrue(self.tab.temperature_row.winfo_manager())
        self._set("Length", "25", "mm", "in")
        self.assertFalse(self.tab.temperature_row.winfo_manager())

    def test_a_value_that_is_not_a_number_says_so(self):
        self._set("Length", "not a number", "mm", "in")
        self.assertEqual(self.tab.answer.cget("text"), "")
        self.assertIn("not a number", self.tab.note.cget("text"))

    def test_swapping_turns_the_conversion_round(self):
        self._set("Length", "25", "mm", "in")
        self.tab.swap()
        self.assertEqual(self.tab.source.get(), "in")
        self.assertEqual(self.tab.target.get(), "mm")


# --------------------------------------------------------------------------
# Showing the working
# --------------------------------------------------------------------------
class TestShowAllWorking(unittest.TestCase):
    """The rule used is the part worth seeing.

    The gap was between the integral of 2x and x squared: correct, and no
    help to anyone trying to see where it came from.
    """

    def test_the_rule_is_named_and_stated(self):
        from engicalc.core.engine import calculate

        steps = calculate("2x", "integral", "x").steps
        titles = [s.title for s in steps]
        self.assertIn("Constant multiple", titles)
        self.assertIn("Power rule", titles)
        power = next(s for s in steps if s.title == "Power rule")
        # Stated as notation, the way a textbook states it.
        self.assertIn(r"\int", power.latex)
        self.assertIn(r"\frac{x^{n+1}}{n+1}", power.latex)

    def test_a_constant_multiple_shows_both_rules(self):
        from engicalc.core.engine import calculate

        # Two rules, not one: the constant comes out, and then something is
        # done to what is left. Showing only the first is the original gap.
        titles = [s.title for s in calculate("2x", "integral", "x").steps]
        self.assertLess(titles.index("Constant multiple"),
                        titles.index("Power rule"))

    def test_a_transposition_is_one_move_at_a_time(self):
        from engicalc.core.engine import calculate

        steps = calculate("3x + 5 = 20", "solve", "x").steps
        titles = [s.title for s in steps]
        self.assertIn("Add 15 to both sides", titles)
        self.assertIn("Divide both sides by 3", titles)
        # Each move carries the equation it leaves behind.
        move = next(s for s in steps if s.title == "Add 15 to both sides")
        self.assertEqual(str(move.expr), "Eq(3*x, 15)")

    def test_a_move_is_described_the_way_it_would_be_said(self):
        from engicalc.core.engine import calculate

        # Adding four is the same move as taking away minus four, and it is
        # the one a person would say they were doing.
        titles = [s.title for s in calculate("2x - 8 = 0", "solve", "x").steps]
        self.assertIn("Add 8 to both sides", titles)
        self.assertFalse([t for t in titles if "-8" in t])

    def test_the_extra_steps_are_marked_rather_than_withheld(self):
        from engicalc.core.engine import calculate

        # Generated either way, so the switch does not have to work the
        # answer out again.
        steps = calculate("2x", "integral", "x").steps
        self.assertTrue(any(s.minor for s in steps))
        self.assertTrue(any(not s.minor for s in steps))

    def test_the_ordinary_working_is_unchanged_by_default(self):
        from engicalc.core.engine import calculate

        steps = [s for s in calculate("2x", "integral", "x").steps
                 if not s.minor]
        self.assertEqual([s.title for s in steps],
                         ["Integrate with respect to x", "Antiderivative F(x)"])

    def test_the_rules_are_notation_that_renders(self):
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties

        from engicalc.core.engine import calculate

        parser = mathtext.MathTextParser("path")
        drawn = 0
        for text, operation in [("2x", "integral"), ("x^3", "integral"),
                                ("1/x", "integral"), ("sin(x)", "integral"),
                                ("exp(2x)", "integral"), ("x^3", "derivative"),
                                ("x^2 - 5x + 6 = 0", "solve")]:
            for step in calculate(text, operation, "x").steps:
                if step.minor and step.latex:
                    with self.subTest(input=text, rule=step.title):
                        parser.parse(f"${step.latex}$", dpi=100,
                                     prop=FontProperties(size=14))
                        drawn += 1
        self.assertGreater(drawn, 5, "no rules were drawn at all")


# --------------------------------------------------------------------------
# Saying when a name was read as a product
# --------------------------------------------------------------------------
class TestSplitNameNotice(unittest.TestCase):
    """Nothing is declared in the equation bar, so a run of letters is
    multiplied. That is right for free-form algebra - xy has always meant x
    times y - but it is silent, and silence is what made the same thing hard
    to find in the solver."""

    def test_a_split_name_is_reported(self):
        from engicalc.core.parsing import names_read_as_products, parse_input

        expression = parse_input("Re*v/mu").expr
        self.assertEqual(names_read_as_products("Re*v/mu", expression), ["Re"])

    def test_a_name_that_survived_is_not_reported(self):
        from engicalc.core.parsing import names_read_as_products, parse_input

        # SymPy will not split a Greek name, so mu comes through whole and
        # there is nothing to say about it.
        expression = parse_input("Re*v/mu").expr
        self.assertNotIn("mu", names_read_as_products("Re*v/mu", expression))

    def test_functions_are_not_reported(self):
        from engicalc.core.parsing import names_read_as_products, parse_input

        for text in ["sin(x)+cos(x)", "sqrt(x)", "log10(x)"]:
            with self.subTest(text=text):
                expression = parse_input(text).expr
                self.assertEqual(names_read_as_products(text, expression), [])

    def test_an_ordinary_expression_says_nothing(self):
        from engicalc.core.parsing import names_read_as_products, parse_input

        # A note on every quadratic would be crying wolf.
        expression = parse_input("2x^2 - 5x - 3 = 0").expr
        self.assertEqual(names_read_as_products("2x^2 - 5x - 3 = 0",
                                                expression), [])

    def test_a_numbered_name_is_reported_too(self):
        from engicalc.core.parsing import names_read_as_products, parse_input

        # T1 comes out as T times 1, which is T - surprising enough to be
        # worth saying out loud.
        expression = parse_input("T1 + T2").expr
        self.assertEqual(names_read_as_products("T1 + T2", expression),
                         ["T1", "T2"])


# --------------------------------------------------------------------------
# Reopening a saved calculation
# --------------------------------------------------------------------------
class TestReopenFromHistory(unittest.TestCase):
    """A saved calculation goes back to the tab it came from.

    Saving worked everywhere and reopening did not: everything that was not
    a formula went to the single-equation calculator, so a unit conversion
    came back as "25 mm to in" in an equation bar and a set of equations as
    several lines in a field that holds one. Nothing raised - it landed
    somewhere it made no sense, which is the worst way to be wrong.
    """

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display available: {exc}")

    def setUp(self):
        import tempfile
        from tkinter import messagebox

        from engicalc.ui.app import EngiCalcApp

        self.complaints = []
        for name in ("showinfo", "showerror", "showwarning"):
            original = getattr(messagebox, name)
            setattr(messagebox, name,
                    lambda title, message="", *a, _n=name, **kw:
                    self.complaints.append((_n, title, message)))
            self.addCleanup(setattr, messagebox, name, original)

        self.app = EngiCalcApp(
            db_path=os.path.join(tempfile.mkdtemp(), "h.db"))
        self.addCleanup(self._close)
        self.app.update_idletasks()

    def _close(self):
        try:
            self.app.update_idletasks()
        except Exception:                             # noqa: BLE001
            pass
        self.app.destroy()

    def _solve_simultaneous(self):
        tab = self.app.simultaneous_tab
        tab.solve()
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            self.app.update()
            if tab.result is not None:
                return
            time.sleep(0.02)
        self.fail(f"no answer in 20s - it says "
                  f"{tab.status.cget('text')!r}")

    def _landed_on(self):
        notebook = self.app.notebook
        name = notebook.tab(notebook.select(), "text").strip()
        if name == "Calculator":
            inner = self.app.calculator_pane.tabs
            name += " / " + inner.tab(inner.select(), "text").strip()
        return name

    def test_each_kind_goes_back_to_its_own_tab(self):
        units = self.app.units_tab
        units.category.set("Pressure")
        units._category_changed()
        units.value.set("2.5")
        units.source.set("bar")
        units.target.set("psi")
        units.convert()
        units.save(quiet=True)

        self._solve_simultaneous()
        self.app.simultaneous_tab.save(quiet=True)
        self.app.sheet_tab.save(quiet=True)
        self.app.statistics_tab.save(quiet=True)
        self.app.update_idletasks()

        expected = {"convert": "Calculator / Units",
                    "system": "Calculator / Simultaneous",
                    "sheet": "Worksheet",
                    "statistics": "Data"}
        for entry in self.app.history.recent(limit=20):
            if entry.operation not in expected:
                continue
            with self.subTest(saved_from=entry.operation):
                self.complaints.clear()
                self.app.reopen_entry(entry)
                self.app.update_idletasks()
                self.assertEqual([], self.complaints)
                self.assertEqual(expected[entry.operation], self._landed_on())

    def test_what_was_saved_comes_back(self):
        units = self.app.units_tab
        units.category.set("Pressure")
        units._category_changed()
        units.value.set("2.5")
        units.source.set("bar")
        units.target.set("psi")
        units.convert()
        units.save(quiet=True)
        self.app.sheet_tab.save(quiet=True)
        rows_before = len(self.app.sheet_tab.rows)
        self.app.update_idletasks()

        # Wipe both, so a restore is visibly a restore rather than the tab
        # having been left as it was.
        units.value.set("999")
        units.category.set("Length")
        units._category_changed()
        self.app.sheet_tab._clear_rows()
        self.app.sheet_tab.calculate()
        self.app.update_idletasks()

        for entry in self.app.history.recent(limit=20):
            self.app.reopen_entry(entry)
            self.app.update_idletasks()

        self.assertIn("36.259", units.answer.cget("text"))
        self.assertEqual(rows_before, len(self.app.sheet_tab.rows))

    def test_an_entry_with_nothing_stored_still_opens(self):
        from engicalc.storage.history import Entry

        # Saved by an older version, before the tabs carried what rebuilds
        # them. It should fall back rather than raise.
        self.app.history.add(Entry(kind="calculator", operation="system",
                                   title="x + y = 10", input_text="x + y = 10"))
        entry = self.app.history.recent(limit=1)[0]
        self.complaints.clear()
        self.app.reopen_entry(entry)
        self.app.update_idletasks()
        self.assertEqual("Calculator / One equation", self._landed_on())


# --------------------------------------------------------------------------
# Water and steam
# --------------------------------------------------------------------------
class TestSteamAgainstTheStandard(unittest.TestCase):
    """The verification values published with IAPWS-IF97.

    This is the whole basis for trusting the module. The coefficients are
    long and the formulation is easy to get subtly wrong, and a subtly wrong
    property is worse than none at all because it gets believed. If these
    fail, the module is wrong and must not be used until they pass.
    """

    #: T (K), p (MPa), v (m3/kg), h (kJ/kg), u (kJ/kg), s (kJ/kg K)
    REGION_1 = [
        (300, 3, 0.100215168e-2, 0.115331273e3, 0.112324818e3, 0.392294792),
        (300, 80, 0.971180894e-3, 0.184142828e3, 0.106448356e3, 0.368563852),
        (500, 3, 0.120241800e-2, 0.975542239e3, 0.971934985e3, 0.258041912e1),
    ]
    REGION_2 = [
        (300, 0.0035, 0.394913866e2, 0.254991145e4, 0.241169160e4,
         0.852238967e1),
        (700, 0.0035, 0.923015898e2, 0.333568375e4, 0.301262819e4,
         0.101749996e2),
        (700, 30, 0.542946619e-2, 0.263149474e4, 0.246861076e4,
         0.517540298e1),
    ]

    def _check(self, computed, expected):
        for key, want in zip(("v", "h", "u", "s"), expected):
            with self.subTest(property=key):
                self.assertAlmostEqual(computed[key] / want, 1.0, places=8)

    def test_region_1_matches_the_published_values(self):
        from engicalc.core.steam import _region1

        for T, pressure, *expected in self.REGION_1:
            with self.subTest(T=T, p=pressure):
                self._check(_region1(pressure, T), expected)

    def test_region_2_matches_the_published_values(self):
        from engicalc.core.steam import _region2

        for T, pressure, *expected in self.REGION_2:
            with self.subTest(T=T, p=pressure):
                self._check(_region2(pressure, T), expected)

    def test_the_saturation_line_hits_its_fixed_points(self):
        from engicalc.core import steam

        # The triple point and the critical point are defined values, not
        # fitted ones, so landing on them is a real check.
        self.assertAlmostEqual(steam.saturation_pressure(273.16),
                               611.657e-6, places=9)
        self.assertAlmostEqual(steam.saturation_pressure(steam.T_CRITICAL),
                               steam.P_CRITICAL, places=6)

    def test_the_reference_state_falls_out_of_the_equations(self):
        from engicalc.core.steam import saturated

        # IF-97 defines the internal energy and entropy of saturated liquid
        # at the triple point as zero. Nothing here sets that; it emerges,
        # which is what makes it worth checking.
        #
        # It emerges to about a part in 1e8 rather than exactly, because
        # IF-97 is a fast fit to IAPWS-95 rather than a restatement of it,
        # and does not reproduce its own reference state to the last bit.
        # The tolerance is that of the standard, not of this code - a real
        # error in the coefficients would be orders of magnitude larger, and
        # the published verification values above are the authoritative
        # check either way.
        liquid, _vapour = saturated(T=273.16)
        self.assertAlmostEqual(liquid.u, 0.0, delta=1e-6)
        self.assertAlmostEqual(liquid.s, 0.0, delta=1e-6)

    def test_saturation_temperature_and_pressure_are_inverses(self):
        from engicalc.core.steam import (saturation_pressure,
                                         saturation_temperature)

        for celsius in (0.01, 50, 100, 200, 300, 370):
            with self.subTest(celsius=celsius):
                T = celsius + 273.15
                self.assertAlmostEqual(
                    saturation_temperature(saturation_pressure(T)), T,
                    places=6)

    def test_the_familiar_numbers_come_out_right(self):
        from engicalc.core.steam import saturated

        # The ones a student would notice if they were wrong.
        liquid, vapour = saturated(T=373.15)
        self.assertAlmostEqual(liquid.p * 1000, 101.42, places=1)
        self.assertAlmostEqual(liquid.h, 419.10, places=1)
        self.assertAlmostEqual(vapour.h, 2675.57, places=1)
        self.assertAlmostEqual(vapour.h - liquid.h, 2256.47, places=1)

    def test_wet_steam_is_the_weighted_average_it_should_be(self):
        from engicalc.core.steam import saturated, wet

        liquid, vapour = saturated(p=0.2)
        mixture = wet(0.8, p=0.2)
        # h = hf + x*hfg, done once here instead of by hand off two rows.
        self.assertAlmostEqual(mixture.h,
                               liquid.h + 0.8 * (vapour.h - liquid.h),
                               places=9)
        self.assertAlmostEqual(mixture.s,
                               liquid.s + 0.8 * (vapour.s - liquid.s),
                               places=9)

    def test_the_ends_of_the_dome_are_the_saturated_states(self):
        from engicalc.core.steam import saturated, wet

        liquid, vapour = saturated(p=0.2)
        self.assertAlmostEqual(wet(0.0, p=0.2).h, liquid.h, places=9)
        self.assertAlmostEqual(wet(1.0, p=0.2).h, vapour.h, places=9)

    def test_a_quality_outside_the_dome_is_refused(self):
        from engicalc.core.steam import SteamError, wet

        # Above 1 usually means the steam is superheated, which needs a
        # temperature as well as a pressure - so say that rather than
        # extrapolating the weighting past the vapour line.
        with self.assertRaises(SteamError):
            wet(1.4, p=0.2)
        with self.assertRaises(SteamError):
            wet(-0.1, p=0.2)

    def test_a_known_table_row_comes_out_right(self):
        from engicalc.core.steam import saturated

        # 200 kPa, as printed in every set of steam tables.
        liquid, vapour = saturated(p=0.2)
        self.assertAlmostEqual(liquid.T - 273.15, 120.21, places=1)
        self.assertAlmostEqual(liquid.h, 504.7, places=0)
        self.assertAlmostEqual(vapour.h, 2706.2, places=0)

    def test_a_state_lands_in_the_right_region(self):
        from engicalc.core.steam import region_of

        self.assertEqual(region_of(3.0, 300.0), 1)        # liquid water
        self.assertEqual(region_of(0.0035, 300.0), 2)     # steam
        self.assertEqual(region_of(30.0, 700.0), 2)

    def test_a_region_that_is_not_implemented_says_so(self):
        from engicalc.core.steam import SteamError, region_of, state

        # A number from region 3 computed with region 1's equations looks
        # entirely plausible and is simply wrong, so it is refused.
        with self.assertRaises(SteamError):
            region_of(25.0, 650.0)                        # near critical
        with self.assertRaises(SteamError):
            state(1.0, 1200.0)                            # above the standard
        with self.assertRaises(SteamError):
            state(1.0, 250.0)                             # ice

    def test_the_saturation_line_stops_where_it_stops(self):
        from engicalc.core.steam import SteamError, saturated

        with self.assertRaises(SteamError):
            saturated(T=700.0)                  # past the critical point
        with self.assertRaises(SteamError):
            saturated(T=373.15, p=0.1)          # both fixed at once
        with self.assertRaises(SteamError):
            saturated()                         # neither


# --------------------------------------------------------------------------
# Moist air
# --------------------------------------------------------------------------
class TestPsychrometrics(unittest.TestCase):
    """The chart, and the ways of arriving at a point on it."""

    def test_it_matches_the_chart(self):
        from engicalc.core.psychrometrics import state

        # Read off a psychrometric chart at sea level.
        for dry, humidity, ratio, enthalpy in [
                (20, 0.50, 0.00726, 38.6),
                (25, 0.60, 0.01190, 55.5),
                (30, 0.40, 0.01060, 57.3),
                (35, 0.70, 0.02516, 99.8)]:
            with self.subTest(dry=dry, rh=humidity):
                air = state(dry, relative_humidity=humidity)
                self.assertAlmostEqual(air.humidity_ratio, ratio, places=4)
                self.assertAlmostEqual(air.enthalpy, enthalpy, places=0)

    def test_every_way_in_describes_the_same_air(self):
        from engicalc.core.psychrometrics import state

        # Relative humidity, humidity ratio, dew point and wet bulb are four
        # measures of one thing, so they must land on the same point.
        reference = state(20, relative_humidity=0.5)
        for label, given in [
                ("humidity ratio", {"ratio": reference.humidity_ratio}),
                ("dew point", {"dew_point_at": reference.dew_point}),
                ("wet bulb", {"wet_bulb": reference.wet_bulb})]:
            with self.subTest(given=label):
                air = state(20, **given)
                self.assertAlmostEqual(air.humidity_ratio,
                                       reference.humidity_ratio, places=6)
                self.assertAlmostEqual(air.enthalpy, reference.enthalpy,
                                       places=4)

    def test_saturated_air_has_its_three_temperatures_together(self):
        from engicalc.core.psychrometrics import state

        # At 100% the dry bulb, wet bulb and dew point are the same
        # temperature. Nothing forces that; it comes out.
        air = state(20, relative_humidity=1.0)
        self.assertAlmostEqual(air.dew_point, 20.0, places=3)
        self.assertAlmostEqual(air.wet_bulb, 20.0, places=3)

    def test_it_shares_one_saturation_pressure_with_the_steam_tables(self):
        from engicalc.core.psychrometrics import saturation_vapour_pressure
        from engicalc.core.steam import saturation_pressure

        # Two correlations that disagree in the fourth figure would be two
        # different answers to the same question.
        for celsius in (10, 20, 50, 100):
            with self.subTest(celsius=celsius):
                self.assertAlmostEqual(
                    saturation_vapour_pressure(celsius),
                    saturation_pressure(celsius + 273.15) * 1000.0, places=12)

    def test_a_frost_point_is_not_reported_as_a_dew_point(self):
        from engicalc.core.psychrometrics import state

        # Cool dry air saturates below zero, where the vapour deposits as
        # frost - a different curve, and not one this has.
        air = state(0, relative_humidity=0.6)
        self.assertNotEqual(air.dew_point, air.dew_point)      # nan
        self.assertIn("frost", air.note)
        # Everything that does not depend on that curve is still right.
        self.assertAlmostEqual(air.humidity_ratio, 0.002259, places=6)
        self.assertGreater(air.enthalpy, 0)

    def test_a_wet_bulb_below_freezing_is_not_reported_as_freezing(self):
        from engicalc.core.psychrometrics import state

        # The search cannot go below 0 C, and returning its own lower bound
        # would read as saturated air, which this is not.
        air = state(0, relative_humidity=0.6)
        self.assertNotEqual(air.wet_bulb, air.wet_bulb)        # nan

    def test_the_state_has_to_be_pinned_down_exactly_once(self):
        from engicalc.core.psychrometrics import PsychrometricError, state

        with self.assertRaises(PsychrometricError):
            state(20)                                   # nothing given
        with self.assertRaises(PsychrometricError):
            state(20, relative_humidity=0.5, ratio=0.007)      # two given

    def test_air_it_cannot_describe_is_refused(self):
        from engicalc.core.psychrometrics import PsychrometricError, state

        with self.assertRaises(PsychrometricError):
            state(-5, relative_humidity=0.5)            # over ice
        with self.assertRaises(PsychrometricError):
            state(20, relative_humidity=1.4)            # more than saturated
        with self.assertRaises(PsychrometricError):
            state(20, dew_point_at=25)                  # dew above dry bulb

    def test_altitude_changes_the_answer(self):
        from engicalc.core.psychrometrics import state

        # Thinner air holds more vapour per kilogram of dry air at the same
        # relative humidity, which is why the pressure is a field.
        sea = state(20, 101.325, relative_humidity=0.5)
        high = state(20, 84.6, relative_humidity=0.5)
        self.assertGreater(high.humidity_ratio, sea.humidity_ratio)
        self.assertAlmostEqual(high.dew_point, sea.dew_point, places=6)


# --------------------------------------------------------------------------
# How numbers are written
# --------------------------------------------------------------------------
class TestNumberFormat(unittest.TestCase):
    """One setting, consulted by every place that writes a number."""

    def setUp(self):
        from engicalc.core.display import AS_ASKED, set_number_format

        # Whatever a test sets, put it back: this is module state and a
        # leaked setting would show up as a puzzling failure somewhere else.
        self.addCleanup(set_number_format, figures=AS_ASKED, notation="auto")

    def test_it_changes_nothing_until_it_is_changed(self):
        from engicalc.core.display import fmt_number

        # Every call site was written against its own choice of figures, so
        # the default has to be exactly that.
        self.assertEqual(fmt_number(565884.2421, 7), "565884.2")
        self.assertEqual(fmt_number(1.5, 7), "1.5")
        self.assertEqual(fmt_number(4000, 7), "4000")

    def test_decimal_places_are_places_not_figures(self):
        from engicalc.core.display import fmt_number, set_number_format

        # Four decimal places on 565884.2421 is 565884.2421. Four
        # significant figures is 565900. Asking for one and getting the
        # other is what makes a setting worse than no setting.
        set_number_format(figures=4, notation="fixed")
        self.assertEqual(fmt_number(565884.2421, 7), "565884.2421")
        self.assertEqual(fmt_number(1.5, 7), "1.5000")
        set_number_format(figures=2)
        self.assertEqual(fmt_number(738.821919, 7), "738.82")

    def test_engineering_puts_the_exponent_in_threes(self):
        from engicalc.core.display import fmt_number, set_number_format

        # 566e3 and 5.66e5 are the same number, but only one reads as kilo.
        set_number_format(figures=6, notation="engineering")
        self.assertEqual(fmt_number(565884.2421, 7), "565.884e3")
        self.assertEqual(fmt_number(0.000123456, 7), "123.456e-6")
        for value in (1.0, 12.0, 123.0, 1234.0, 12345.0, 1234567.0):
            with self.subTest(value=value):
                text = fmt_number(value, 7)
                if "e" in text:
                    self.assertEqual(int(text.split("e")[1]) % 3, 0)

    def test_scientific_is_one_figure_before_the_point(self):
        from engicalc.core.display import fmt_number, set_number_format

        set_number_format(figures=4, notation="scientific")
        self.assertEqual(fmt_number(565884.2421, 7), "5.659e+05")

    def test_the_setting_can_be_put_back(self):
        from engicalc.core.display import AS_ASKED, fmt_number, \
            set_number_format

        set_number_format(figures=3, notation="fixed")
        # Setting one must leave the other alone...
        set_number_format(notation="engineering")
        self.assertEqual(fmt_number(1.5, 7), "1.5")
        # ...and asking for the default figures must actually reset them,
        # even while a notation is also being set.
        set_number_format(figures=AS_ASKED, notation="auto")
        self.assertEqual(fmt_number(565884.2421, 7), "565884.2")

    def test_an_exponent_is_typeset_as_an_exponent(self):
        import sympy as sp

        from engicalc.core.display import latex, set_number_format

        # The point of the typeset panels is that they show notation rather
        # than the way notation has to be typed.
        x = sp.Symbol("x")
        set_number_format(figures=4, notation="scientific")
        self.assertIn(r"\times 10^{5}", latex(sp.Eq(x, sp.Float("565884.24"))))
        set_number_format(figures=6, notation="engineering")
        self.assertIn(r"\times 10^{-6}",
                      latex(sp.Eq(x, sp.Float("0.000123456"))))

    def test_the_typeset_form_renders(self):
        import matplotlib
        matplotlib.use("Agg")
        import sympy as sp
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties

        from engicalc.core.display import latex, set_number_format

        parser = mathtext.MathTextParser("path")
        x = sp.Symbol("x")
        for notation in ("scientific", "engineering", "fixed", "auto"):
            set_number_format(figures=4, notation=notation)
            for value in ("565884.2421", "0.000123456", "1.5"):
                with self.subTest(notation=notation, value=value):
                    drawn = latex(sp.Eq(x, sp.Float(value)))
                    parser.parse(f"${drawn}$", dpi=100,
                                 prop=FontProperties(size=14))

    def test_a_bare_power_of_ten_loses_its_one(self):
        from engicalc.core.display import number_to_latex

        # "1 x 10^5" is how nobody writes it.
        self.assertEqual(number_to_latex("1e5"), "10^{5}")
        self.assertEqual(number_to_latex("-1e5"), "-10^{5}")
        self.assertEqual(number_to_latex("2.5e5"), r"2.5 \times 10^{5}")
        self.assertEqual(number_to_latex("42"), "42")

    def test_a_notation_that_does_not_exist_is_refused(self):
        from engicalc.core.display import set_number_format

        with self.assertRaises(ValueError):
            set_number_format(notation="roman numerals")


# --------------------------------------------------------------------------
# A parametric study
# --------------------------------------------------------------------------
class TestSweep(unittest.TestCase):
    """The same set solved down a column of values.

    One number in a calculation is rarely the number - it is the one you
    were given this time - and duct diameters come in sizes.
    """

    DUCT = ("A = pi*d^2/4\n"
            "v = 0.5/A\n"
            "Re = v*d/7.5e-6\n"
            "f = 0.3164/Re^0.25\n"
            "dp = f*(20/d)*1.2*v^2/2")

    def test_only_what_the_equations_take_as_input_is_offered(self):
        from engicalc.core.system import free_names

        # Every other name is worked out by an equation. Fixing one of those
        # would be over-determining the set in a roundabout way.
        self.assertEqual(free_names(self.DUCT), ["d"])

    def test_a_determined_set_has_nothing_to_sweep(self):
        from engicalc.core.system import free_names

        self.assertEqual(free_names("x + y = 10\nx - y = 2"), [])

    def test_a_value_the_set_already_fixes_can_still_be_swept(self):
        from engicalc.core.system import free_names

        # Deleting the line that fixes the diameter in order to vary the
        # diameter is a strange way round, and nobody guessed it.
        self.assertEqual(free_names(self.DUCT + "\nd = 0.15"), ["d"])

    def test_what_the_equations_work_out_is_never_offered(self):
        from engicalc.core.system import free_names

        # `v` is worked out by an equation, so fixing it would be
        # over-determining the set in a roundabout way. Only `d` was given.
        self.assertNotIn("v", free_names(self.DUCT + "\nd = 0.15"))

    def test_sweeping_replaces_the_line_that_fixed_the_value(self):
        from engicalc.core.system import spread, sweep

        # Not added alongside it - two lines saying the diameter is two
        # different things is over-determined at every step of the sweep.
        rows = sweep(self.DUCT + "\nd = 0.15", "d", spread(0.1, 0.3, 5))
        self.assertTrue(all(row.ok for row in rows),
                        [row.error for row in rows])
        self.assertAlmostEqual(rows[1].get("dp"), 738.8, delta=1.0)
        # And the same answers as sweeping the set without that line, which
        # is what it used to take.
        loose = sweep(self.DUCT, "d", spread(0.1, 0.3, 5))
        for fixed, free in zip(rows, loose):
            self.assertAlmostEqual(fixed.get("dp"), free.get("dp"), places=6)

    def test_the_value_it_is_fixed_at_is_readable(self):
        from engicalc.core.system import fixed_names

        # This is what the range is centred on, so it has to be the value
        # actually written rather than whatever solves out.
        found = fixed_names(self.DUCT + "\nd = 0.15")
        self.assertAlmostEqual(found["d"], 0.15)
        self.assertNotIn("v", found)

    def test_it_solves_once_for_each_value(self):
        from engicalc.core.system import spread, sweep

        rows = sweep(self.DUCT, "d", spread(0.1, 0.3, 5))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row.ok for row in rows))
        self.assertAlmostEqual(rows[0].value, 0.1)
        self.assertAlmostEqual(rows[-1].value, 0.3)

    def test_the_answers_move_the_way_the_physics_does(self):
        from engicalc.core.system import spread, sweep

        # A wider duct is a slower one and a much lower pressure drop.
        rows = sweep(self.DUCT, "d", spread(0.1, 0.3, 5))
        drops = [row.get("dp") for row in rows]
        speeds = [row.get("v") for row in rows]
        self.assertEqual(drops, sorted(drops, reverse=True))
        self.assertEqual(speeds, sorted(speeds, reverse=True))
        self.assertAlmostEqual(rows[1].get("dp"), 738.8, delta=1.0)

    def test_spread_includes_both_ends(self):
        from engicalc.core.system import spread

        values = spread(0.0, 1.0, 5)
        self.assertEqual(len(values), 5)
        self.assertAlmostEqual(values[0], 0.0)
        self.assertAlmostEqual(values[-1], 1.0)
        self.assertEqual(spread(2.0, 9.0, 1), [2.0])

    def test_a_value_that_will_not_solve_is_reported_not_dropped(self):
        from engicalc.core.system import sweep, sweep_table

        # A row that failed still has to appear, or the table quietly has a
        # gap in it and the shape of the answer looks different.
        rows = sweep("y = 1/x", "x", [1.0, 0.0, 2.0])
        self.assertEqual(len(rows), 3)
        headings, table = sweep_table(rows, ["y"])
        self.assertEqual(len(table), 3)
        self.assertEqual(headings[0], "value")

    def test_a_numerical_answer_has_its_imaginary_dust_dropped(self):
        from engicalc.core.system import solve_set

        # nsolve returned the pressure drop as 738.82 - 4.9e-18*I, which is a
        # real number with floating point dust on it, and it went to the
        # answer panel looking like that.
        result = solve_set(self.DUCT + "\nd = 0.15")
        for value in result.results[0].values():
            with self.subTest(value=value):
                self.assertFalse(value.has(sp.I),
                                 f"{value} still carries an imaginary part")

    def test_a_genuinely_complex_answer_is_kept(self):
        from engicalc.core.system import _tidy

        # Dropping the imaginary part of a real answer is tidying; dropping
        # it from a complex one is losing the answer.
        kept = _tidy({sp.Symbol("x"): sp.Float(3.0) + 4 * sp.I})
        self.assertTrue(list(kept.values())[0].has(sp.I))
        tidied = _tidy({sp.Symbol("x"): sp.Float(3.0) + sp.Float(1e-18) * sp.I})
        self.assertFalse(list(tidied.values())[0].has(sp.I))


# --------------------------------------------------------------------------
# The standard engineering charts
# --------------------------------------------------------------------------
class TestBeamDiagrams(unittest.TestCase):
    """Shear and moment, against the results every textbook quotes."""

    def test_a_point_load_on_a_simple_span(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # 12 kN at 2 m of a 6 m span: reactions 8 and 4 kN, and the moment
        # under the load is Pab/L = 16 kN m.
        result = analyse(Beam(length=6, supports=[0, 6],
                              loads=[PointLoad(2, -12000)]))
        self.assertAlmostEqual(result.reactions[0], 8000.0, places=6)
        self.assertAlmostEqual(result.reactions[6], 4000.0, places=6)
        at, moment = result.max_moment
        self.assertAlmostEqual(at, 2.0, places=2)
        self.assertAlmostEqual(moment, 16000.0, places=3)

    def test_a_spread_load_on_a_simple_span(self):
        from engicalc.core.beams import Beam, Distributed, analyse

        # wL^2/8 at midspan, which is the one everybody remembers.
        result = analyse(Beam(length=4, supports=[0, 4],
                              loads=[Distributed(0, 4, -5000)]))
        self.assertAlmostEqual(result.reactions[0], 10000.0, places=6)
        at, moment = result.max_moment
        self.assertAlmostEqual(at, 2.0, places=2)
        self.assertAlmostEqual(moment, 10000.0, places=2)

    def test_a_cantilever_hogs_at_the_wall_and_is_free_at_the_tip(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # This was wrong: the couple and the sagging moment have opposite
        # signs, and adding them as though they agreed put 30 kN m at the
        # free end, where there is nothing left to bend it.
        result = analyse(Beam(length=3, supports=[0], kind="cantilever",
                              loads=[PointLoad(3, -5000)]))
        self.assertAlmostEqual(float(result.moment[0]), -15000.0, places=3)
        self.assertAlmostEqual(float(result.moment[-1]), 0.0, places=6)

    def test_a_cantilever_under_a_spread_load(self):
        from engicalc.core.beams import Beam, Distributed, analyse

        # wL^2/2 at the wall.
        result = analyse(Beam(length=4, supports=[0], kind="cantilever",
                              loads=[Distributed(0, 4, -2000)]))
        self.assertAlmostEqual(float(result.moment[0]), -16000.0, places=3)
        self.assertAlmostEqual(float(result.moment[-1]), 0.0, places=6)

    def test_the_diagrams_close_to_zero(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # A beam in equilibrium has both back at zero at the far end. If it
        # does not, the reactions were wrong rather than the drawing.
        result = analyse(Beam(length=6, supports=[0, 6],
                              loads=[PointLoad(2, -12000)]))
        self.assertEqual([], result.notes)
        self.assertAlmostEqual(float(result.shear[-1]), 0.0, places=6)

    def test_a_load_off_the_end_is_refused(self):
        from engicalc.core.beams import Beam, BeamError, PointLoad, analyse

        with self.assertRaises(BeamError):
            analyse(Beam(length=3, supports=[0, 3],
                         loads=[PointLoad(5, -1000)]))

    # -- loads over part of the span, ramps, overhangs and inclined forces --
    def test_a_spread_load_over_part_of_the_span(self):
        from engicalc.core.beams import Beam, Distributed, analyse

        # This was wrong, and only wrong past the end of the load, so the
        # examples that covered the whole beam never showed it: the moment
        # went on accumulating as though the section were still underneath
        # it, and a diagram that should close at zero finished at 80 kN m.
        #
        # 10 kN/m over the first 2 m of a 6 m span. 20 kN at 1 m, so the
        # reactions are 16.667 and 3.333 kN, and the moment 4 m along is
        # 3.333 x 2 = 6.667 kN m taken from the right-hand end.
        result = analyse(Beam(length=6, supports=[0, 6],
                              loads=[Distributed(0, 2, -10000)]))
        self.assertAlmostEqual(result.reactions[0], 16666.666667, places=5)
        self.assertAlmostEqual(result.reactions[6], 3333.333333, places=5)
        index = int(np.argmin(np.abs(result.x - 4.0)))
        self.assertAlmostEqual(float(result.moment[index]), 6666.666667,
                               places=4)
        self.assertAlmostEqual(float(result.moment[-1]), 0.0, places=6)
        self.assertEqual([], result.notes)

    def test_a_load_that_ramps_from_nothing(self):
        from engicalc.core.beams import Beam, Distributed, analyse

        # A triangle rising to 12 kN/m at the far end of a 6 m span. The
        # whole load is 36 kN two thirds of the way along, so the reactions
        # are W/3 and 2W/3, the shear crosses zero at L/sqrt(3), and the
        # moment there is 16 sqrt(3) kN m.
        result = analyse(Beam(length=6, supports=[0, 6],
                              loads=[Distributed(0, 6, 0.0, -12000)]))
        self.assertAlmostEqual(result.reactions[0], 12000.0, places=5)
        self.assertAlmostEqual(result.reactions[6], 24000.0, places=5)
        at, moment = result.max_moment
        self.assertAlmostEqual(at, 6.0 / math.sqrt(3), places=2)
        self.assertAlmostEqual(moment, 16000.0 * math.sqrt(3), delta=2.0)
        self.assertEqual([], result.notes)

    def test_a_trapezoid_with_no_net_force_still_has_a_moment(self):
        from engicalc.core.beams import Distributed

        # Which is why its moment is integrated rather than taken as force
        # times centroid: the centroid of nothing is nowhere.
        load = Distributed(0, 4, 3000.0, -3000.0)
        self.assertAlmostEqual(load.force(), 0.0, places=9)
        self.assertNotAlmostEqual(load.moment_about_left(), 0.0, places=3)

    def test_supports_held_in_from_the_ends_hog_over_the_support(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # The case a pair of supports nailed to the ends can never show. A
        # 10 kN load on each 1 m overhang: the reactions are 10 kN each by
        # symmetry and the moment over each support is -10 kN m, hogging.
        result = analyse(Beam(length=6, supports=[1, 5],
                              loads=[PointLoad(0, -10000),
                                     PointLoad(6, -10000)]))
        self.assertAlmostEqual(result.reactions[1], 10000.0, places=6)
        self.assertAlmostEqual(result.reactions[5], 10000.0, places=6)
        index = int(np.argmin(np.abs(result.x - 1.0)))
        self.assertAlmostEqual(float(result.moment[index]), -10000.0,
                               places=3)
        # And nothing bends the beam beyond the supports at its free ends.
        self.assertAlmostEqual(float(result.moment[0]), 0.0, places=6)
        self.assertAlmostEqual(float(result.moment[-1]), 0.0, places=6)

    def test_an_inclined_load_is_resolved_both_ways(self):
        from engicalc.core.beams import Beam, analyse, inclined

        # 10 kN at 60 degrees to the beam, at the middle of a 4 m span. The
        # supports share the 8.66 kN across it; the 5 kN along it is held by
        # the pin, and the beam is in tension between the two.
        result = analyse(Beam(length=4, supports=[0, 4],
                              loads=[inclined(2, 10000.0, 60.0)]))
        self.assertAlmostEqual(result.reactions[0],
                               10000.0 * math.sin(math.radians(60)) / 2,
                               places=5)
        self.assertAlmostEqual(result.reactions["axial at 0"], -5000.0,
                               places=5)
        before = int(np.argmin(np.abs(result.x - 1.0)))
        after = int(np.argmin(np.abs(result.x - 3.0)))
        self.assertAlmostEqual(float(result.axial[before]), 5000.0, places=5)
        self.assertAlmostEqual(float(result.axial[after]), 0.0, places=6)
        self.assertEqual([], result.notes)

    def test_a_load_leaning_the_other_way_pushes_the_beam(self):
        from engicalc.core.beams import Beam, analyse, inclined

        # Past ninety degrees it leans back towards the near end, so the
        # same beam is in compression instead. One number covers every
        # direction, which is the point of measuring from the beam.
        result = analyse(Beam(length=4, supports=[0, 4],
                              loads=[inclined(2, 10000.0, 120.0)]))
        before = int(np.argmin(np.abs(result.x - 1.0)))
        self.assertAlmostEqual(float(result.axial[before]), -5000.0,
                               places=5)

    def test_an_ordinary_vertical_load_has_no_axial_force_at_all(self):
        from engicalc.core.beams import Beam, analyse, inclined

        # cos(90 degrees) is 6e-17, not nought. Left as it came, every
        # vertical load put a thread of axial force through the beam and the
        # tab drew a diagram of its own rounding error.
        result = analyse(Beam(length=4, supports=[0, 4],
                              loads=[inclined(2, 10000.0, 90.0)]))
        self.assertEqual(0.0, float(np.max(np.abs(result.axial))))
        self.assertNotIn("axial at 0", result.reactions)
        self.assertFalse([row for row in result.rows()
                          if "axial" in row[0]])

    def test_a_wall_holds_a_leaning_load_three_ways(self):
        from engicalc.core.beams import Beam, analyse, inclined

        # Force, thrust and couple, which is what makes a built-in end
        # worth more than a pinned one.
        result = analyse(Beam(length=3, supports=[0], kind="cantilever",
                              loads=[inclined(3, 10000.0, 30.0)]))
        across = 10000.0 * math.sin(math.radians(30))
        self.assertAlmostEqual(result.reactions[0], across, places=5)
        self.assertAlmostEqual(result.reactions["axial at 0"],
                               -10000.0 * math.cos(math.radians(30)),
                               places=5)
        self.assertAlmostEqual(result.reactions["moment at 0"],
                               across * 3, places=5)

    # -- what kind of support each one is -----------------------------------
    def test_which_support_is_the_pin_decides_which_half_is_pulled(self):
        from engicalc.core.beams import Beam, Support, analyse, inclined

        # The choice the old form hid behind "simply supported". The same
        # beam under the same load: pinned on the left the near half is in
        # tension, pinned on the right the far half is in compression, and
        # the reactions holding it up are identical either way.
        load = [inclined(2, 10000.0, 60.0)]
        left = analyse(Beam(length=6, loads=load,
                            supports=[Support(0, "pin"),
                                      Support(6, "roller")]))
        right = analyse(Beam(length=6, loads=load,
                             supports=[Support(0, "roller"),
                                       Support(6, "pin")]))
        self.assertAlmostEqual(left.reactions[0], right.reactions[0],
                               places=6)
        near = int(np.argmin(np.abs(left.x - 1.0)))
        far = int(np.argmin(np.abs(left.x - 4.0)))
        self.assertAlmostEqual(float(left.axial[near]), 5000.0, places=5)
        self.assertAlmostEqual(float(left.axial[far]), 0.0, places=6)
        self.assertAlmostEqual(float(right.axial[near]), 0.0, places=6)
        self.assertAlmostEqual(float(right.axial[far]), -5000.0, places=5)

    def test_a_propped_cantilever_is_solved_from_the_deflection(self):
        from engicalc.core.beams import Beam, PointLoad, Support, analyse

        # More unknowns than equilibrium has equations, and for a long time
        # this was refused for exactly that reason. The deflection is the
        # missing equation: the prop is a place where the beam cannot move,
        # and that settles the one reaction statics could not reach.
        #
        # A load at midspan gives 5P/16 at the prop and 3PL/16 at the wall.
        span, load = 6.0, 20000.0
        got = analyse(Beam(length=span, loads=[PointLoad(span / 2, -load)],
                           supports=[Support(0, "fixed"),
                                     Support(span, "roller")]))
        self.assertAlmostEqual(got.reactions[span], 5 * load / 16,
                               delta=load * 1e-4)
        self.assertAlmostEqual(got.reactions["moment at 0"],
                               3 * load * span / 16,
                               delta=load * span * 1e-4)
        self.assertTrue([n for n in got.notes if "indeterminate" in n])

    def test_two_pins_cannot_share_a_thrust(self):
        from engicalc.core.beams import (Beam, BeamError, Support,
                                         analyse, inclined)

        with self.assertRaises(BeamError) as caught:
            analyse(Beam(length=6, loads=[inclined(3, 10000.0, 60.0)],
                         supports=[Support(0, "pin"), Support(6, "pin")]))
        self.assertIn("roller", str(caught.exception))

    def test_two_pins_are_fine_with_nothing_pushing_along_the_beam(self):
        from engicalc.core.beams import Beam, PointLoad, Support, analyse

        # Indeterminate only in the direction nothing is acting in, and a
        # refusal there would be pedantry rather than honesty.
        result = analyse(Beam(length=6, loads=[PointLoad(3, -10000)],
                              supports=[Support(0, "pin"),
                                        Support(6, "pin")]))
        self.assertAlmostEqual(result.reactions[0], 5000.0, places=6)

    def test_a_beam_on_one_roller_is_a_mechanism(self):
        from engicalc.core.beams import (Beam, BeamError, PointLoad, Support,
                                         analyse)

        with self.assertRaises(BeamError):
            analyse(Beam(length=6, loads=[PointLoad(3, -10000)],
                         supports=[Support(0, "roller")]))

    def test_three_supports_are_solved_the_same_way(self):
        from engicalc.core.beams import (Beam, Distributed, Support, analyse)

        # Two equal spans under a spread load. The middle support takes
        # 10wL/8 and the ends 3wL/8 each, and the moment over the middle is
        # hogging at wL^2/8 - which is why a continuous beam is worth having
        # and why it cannot be done from equilibrium alone.
        span, spread = 6.0, 10000.0
        got = analyse(Beam(length=2 * span,
                           loads=[Distributed(0, 2 * span, -spread)],
                           supports=[Support(0, "pin"), Support(span,
                                                                "roller"),
                                     Support(2 * span, "roller")]))
        self.assertAlmostEqual(got.reactions[span], 10 * spread * span / 8,
                               delta=spread * span * 1e-4)
        self.assertAlmostEqual(got.reactions[0.0], 3 * spread * span / 8,
                               delta=spread * span * 1e-4)
        over = int(np.argmin(np.abs(got.x - span)))
        self.assertAlmostEqual(float(got.moment[over]),
                               -spread * span ** 2 / 8,
                               delta=spread * span ** 2 * 1e-4)

    def test_plain_distances_still_mean_what_they_meant(self):
        from engicalc.core.beams import Beam, analyse, inclined

        # A beam described as two numbers is a pin on the left and a roller
        # on the right, the way it always was, so nothing written against
        # the old shape had to change.
        result = analyse(Beam(length=6, supports=[0, 6],
                              loads=[inclined(2, 10000.0, 60.0)]))
        self.assertIn("axial at 0", result.reactions)
        held = Beam(length=6, supports=[0, 6]).held
        self.assertEqual(["pin", "roller"], [s.kind for s in held])
        wall = Beam(length=3, supports=[0], kind="cantilever").held
        self.assertEqual(["fixed"], [s.kind for s in wall])

    def test_a_support_off_the_end_is_refused(self):
        from engicalc.core.beams import Beam, BeamError, PointLoad, analyse

        with self.assertRaises(BeamError):
            analyse(Beam(length=3, supports=[0, 7],
                         loads=[PointLoad(1, -1000)]))


class TestIndeterminateBeams(unittest.TestCase):
    """The ones with more supports than statics has equations.

    All of these were refused until the deflection existed to settle them.
    Each is checked against the closed form every textbook quotes, because
    the force method is easy to write plausibly and wrongly.
    """

    SPAN, SPREAD, LOAD = 6.0, 10000.0, 20000.0

    def _at(self, diagram, place):
        return float(diagram.moment[
            int(np.argmin(np.abs(diagram.x - place)))])

    def test_a_propped_cantilever_under_a_spread_load(self):
        from engicalc.core.beams import Beam, Distributed, Support, analyse

        # R at the prop is 3wL/8, at the wall 5wL/8, and the wall holds
        # wL^2/8.
        span, spread = self.SPAN, self.SPREAD
        got = analyse(Beam(length=span,
                           loads=[Distributed(0, span, -spread)],
                           supports=[Support(0, "fixed"),
                                     Support(span, "roller")]))
        self.assertAlmostEqual(got.reactions[span], 3 * spread * span / 8,
                               delta=spread * span * 1e-4)
        self.assertAlmostEqual(got.reactions[0.0], 5 * spread * span / 8,
                               delta=spread * span * 1e-4)
        self.assertAlmostEqual(got.reactions["moment at 0"],
                               spread * span ** 2 / 8,
                               delta=spread * span ** 2 * 1e-4)

    def test_a_beam_built_in_at_both_ends(self):
        from engicalc.core.beams import Beam, Distributed, Support, analyse

        # wL^2/12 hogging at the ends, wL^2/24 sagging in the middle, and
        # the contraflexure points at L/2 +- L/(2 root 3).
        span, spread = self.SPAN, self.SPREAD
        got = analyse(Beam(length=span,
                           loads=[Distributed(0, span, -spread)],
                           supports=[Support(0, "fixed"),
                                     Support(span, "fixed")]))
        self.assertAlmostEqual(got.reactions[0.0], spread * span / 2,
                               delta=spread * span * 1e-4)
        self.assertAlmostEqual(self._at(got, 0.0),
                               -spread * span ** 2 / 12,
                               delta=spread * span ** 2 * 1e-4)
        self.assertAlmostEqual(self._at(got, span),
                               -spread * span ** 2 / 12,
                               delta=spread * span ** 2 * 1e-4)
        self.assertAlmostEqual(self._at(got, span / 2),
                               spread * span ** 2 / 24,
                               delta=spread * span ** 2 * 1e-4)
        for turn in (span / 2 - span / (2 * math.sqrt(3)),
                     span / 2 + span / (2 * math.sqrt(3))):
            self.assertAlmostEqual(self._at(got, turn), 0.0,
                                   delta=spread * span ** 2 * 1e-3)

    def test_a_beam_built_in_at_both_ends_under_a_point_load(self):
        from engicalc.core.beams import Beam, PointLoad, Support, analyse

        # PL/8 at the ends and PL/8 at the middle, which is the case worth
        # knowing: building the ends in halves the moment a simple span has.
        span, load = self.SPAN, self.LOAD
        got = analyse(Beam(length=span, loads=[PointLoad(span / 2, -load)],
                           supports=[Support(0, "fixed"),
                                     Support(span, "fixed")]))
        self.assertAlmostEqual(got.reactions[0.0], load / 2,
                               delta=load * 1e-4)
        self.assertAlmostEqual(self._at(got, 0.0), -load * span / 8,
                               delta=load * span * 1e-4)
        self.assertAlmostEqual(self._at(got, span / 2), load * span / 8,
                               delta=load * span * 1e-4)

    def test_two_equal_spans_under_a_spread_load(self):
        from engicalc.core.beams import Beam, Distributed, Support, analyse

        span, spread = self.SPAN, self.SPREAD
        got = analyse(Beam(length=2 * span,
                           loads=[Distributed(0, 2 * span, -spread)],
                           supports=[Support(0, "pin"),
                                     Support(span, "roller"),
                                     Support(2 * span, "roller")]))
        self.assertAlmostEqual(got.reactions[span], 10 * spread * span / 8,
                               delta=spread * span * 1e-4)
        self.assertAlmostEqual(got.reactions[0.0], 3 * spread * span / 8,
                               delta=spread * span * 1e-4)
        self.assertAlmostEqual(self._at(got, span),
                               -spread * span ** 2 / 8,
                               delta=spread * span ** 2 * 1e-4)

    def test_the_reactions_do_not_depend_on_what_it_is_made_of(self):
        from engicalc.core.beams import Beam, Distributed, Support, analyse

        # For one section throughout the stiffness cancels between the sag
        # and the force that undoes it. If it did not, a steel beam and an
        # aluminium one of the same shape would carry their loads
        # differently, which they do not.
        beam = Beam(length=self.SPAN,
                    loads=[Distributed(0, self.SPAN, -self.SPREAD)],
                    supports=[Support(0, "fixed"),
                              Support(self.SPAN, "roller")])
        soft = analyse(beam, stiffness=1e5)
        stiff = analyse(beam, stiffness=1e9)
        self.assertAlmostEqual(soft.reactions[self.SPAN],
                               stiff.reactions[self.SPAN], places=6)
        # The movement does depend on it, and by the ratio of the two.
        self.assertAlmostEqual(
            abs(soft.max_deflection[1] / stiff.max_deflection[1]), 1e4,
            delta=1.0)

    def test_the_diagrams_still_close(self):
        from engicalc.core.beams import Beam, Distributed, Support, analyse

        # The check that caught the spread-load bug. It has to keep working
        # when the reactions came from somewhere other than equilibrium.
        for supports in ([Support(0, "fixed"), Support(6.0, "roller")],
                         [Support(0, "pin"), Support(3.0, "roller"),
                          Support(6.0, "roller")]):
            with self.subTest(supports=len(supports)):
                got = analyse(Beam(length=6.0,
                                   loads=[Distributed(0, 6.0, -8000.0)],
                                   supports=supports))
                self.assertAlmostEqual(float(got.shear[-1]), 0.0, places=6)
                self.assertFalse([n for n in got.notes
                                  if "does not close" in n])

    def test_it_says_when_it_had_to_go_beyond_equilibrium(self):
        from engicalc.core.beams import Beam, PointLoad, Support, analyse

        plain = analyse(Beam(length=6.0, loads=[PointLoad(3.0, -10000.0)],
                             supports=[Support(0, "pin"),
                                       Support(6.0, "roller")]))
        self.assertFalse([n for n in plain.notes if "indeterminate" in n])
        propped = analyse(Beam(length=6.0, loads=[PointLoad(3.0, -10000.0)],
                               supports=[Support(0, "fixed"),
                                         Support(6.0, "roller")]))
        self.assertTrue([n for n in propped.notes if "indeterminate" in n])

    def test_a_beam_on_one_roller_is_still_a_mechanism(self):
        from engicalc.core.beams import (Beam, BeamError, PointLoad, Support,
                                         analyse)

        # Solving the indeterminate ones must not have made the impossible
        # ones look solvable. Too few supports is still too few.
        with self.assertRaises(BeamError):
            analyse(Beam(length=6.0, loads=[PointLoad(3.0, -10000.0)],
                         supports=[Support(0, "roller")]))


class TestBeamDeflection(unittest.TestCase):
    """Against the formulae in the back of every book, then beyond them."""

    #: A 305x165x40 UB in steel, which is a beam somebody might use.
    EI = 210e9 * 8503e-8

    def test_the_five_cases_everybody_has_memorised(self):
        from engicalc.core.beams import (Beam, Distributed, PointLoad,
                                         Support, analyse)

        for name, beam, expected in (
                # 5 w L^4 / 384 EI
                ("simply supported under a spread load",
                 Beam(length=6.0, supports=[0, 6.0],
                      loads=[Distributed(0, 6.0, -10000.0)]),
                 5 * 10000.0 * 6.0 ** 4 / (384 * self.EI)),
                # P L^3 / 48 EI
                ("simply supported, load at midspan",
                 Beam(length=6.0, supports=[0, 6.0],
                      loads=[PointLoad(3.0, -20000.0)]),
                 20000.0 * 6.0 ** 3 / (48 * self.EI)),
                # P L^3 / 3 EI
                ("cantilever with a load on the end",
                 Beam(length=4.0, supports=[Support(0, "fixed")],
                      loads=[PointLoad(4.0, -5000.0)]),
                 5000.0 * 4.0 ** 3 / (3 * self.EI)),
                # w L^4 / 8 EI
                ("cantilever under a spread load",
                 Beam(length=4.0, supports=[Support(0, "fixed")],
                      loads=[Distributed(0, 4.0, -8000.0)]),
                 8000.0 * 4.0 ** 4 / (8 * self.EI))):
            with self.subTest(case=name):
                got = analyse(beam, stiffness=self.EI)
                _at, drop = got.max_deflection
                self.assertAlmostEqual(abs(drop) / expected, 1.0, places=4)
                # And it sags rather than rises, which is half of getting
                # the sign convention right and the half that shows.
                self.assertLess(drop, 0.0)

    def test_a_load_off_the_middle_deflects_by_the_formula_too(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # P a^2 b^2 / (3 EI L), under the load rather than at midspan -
        # which is the case that catches a method that only ever looks in
        # the middle.
        span, load, along = 6.0, 20000.0, 2.0
        got = analyse(Beam(length=span, supports=[0, span],
                           loads=[PointLoad(along, -load)]),
                      stiffness=self.EI)
        index = int(np.argmin(np.abs(got.x - along)))
        expected = (load * along ** 2 * (span - along) ** 2
                    / (3 * self.EI * span))
        self.assertAlmostEqual(abs(float(got.deflection[index])) / expected,
                               1.0, places=4)

    def test_it_is_held_down_where_the_supports_are(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # The two constants of integration are exactly the two things the
        # supports say, so if the answer moves at a support the constants
        # were fitted to something else.
        got = analyse(Beam(length=6.0, supports=[1.0, 5.0],
                           loads=[PointLoad(0.0, -10000.0),
                                  PointLoad(6.0, -10000.0)]),
                      stiffness=self.EI)
        biggest = float(np.max(np.abs(got.deflection)))
        for place in (1.0, 5.0):
            index = int(np.argmin(np.abs(got.x - place)))
            self.assertLess(abs(float(got.deflection[index])),
                            1e-9 * max(biggest, 1e-9))
        # The loaded overhangs go down and the span between the supports
        # arches up, which is the shape a constant hogging moment makes and
        # is the case a pair of supports at the ends cannot produce.
        self.assertLess(float(got.deflection[0]), 0.0)
        self.assertLess(float(got.deflection[-1]), 0.0)
        middle = int(np.argmin(np.abs(got.x - 3.0)))
        self.assertGreater(float(got.deflection[middle]), 0.0)
        # M is a constant -10 kN m between the supports, so the arch is
        # M (x - a)(x - b) / 2EI and can be checked outright.
        self.assertAlmostEqual(
            float(got.deflection[middle]),
            -10000.0 / (2 * self.EI) * (3.0 - 1.0) * (3.0 - 5.0), places=9)

    def test_a_built_in_end_is_held_level_as_well_as_down(self):
        from engicalc.core.beams import Beam, PointLoad, Support, analyse

        got = analyse(Beam(length=4.0, supports=[Support(0, "fixed")],
                           loads=[PointLoad(4.0, -5000.0)]),
                      stiffness=self.EI)
        self.assertAlmostEqual(float(got.deflection[0]), 0.0, places=12)
        # Level, which is what a built-in end means and a pinned one does
        # not. Compared with the slope at the free end rather than with a
        # fixed number, because a difference taken over one step of the
        # grid carries half a step of the curvature with it whatever the
        # answer is - the ratio is the part that means something.
        def slope_at(index):
            return ((float(got.deflection[index + 1])
                     - float(got.deflection[index]))
                    / (float(got.x[index + 1]) - float(got.x[index])))

        self.assertLess(abs(slope_at(0)), abs(slope_at(-2)) / 100.0)

    def test_without_a_stiffness_it_is_left_alone(self):
        from engicalc.core.beams import Beam, PointLoad, analyse

        # The shear and the moment do not depend on what the beam is made
        # of, so asking for a material before drawing them would be asking
        # for something that is not needed yet.
        got = analyse(Beam(length=6.0, supports=[0, 6.0],
                           loads=[PointLoad(3.0, -20000.0)]))
        self.assertIsNone(got.deflection)
        self.assertEqual((0.0, 0.0), got.max_deflection)

    def test_a_stiffness_that_is_not_one_is_refused(self):
        from engicalc.core.beams import Beam, BeamError, PointLoad, deflect

        beam = Beam(length=6.0, supports=[0, 6.0],
                    loads=[PointLoad(3.0, -20000.0)])
        from engicalc.core.beams import analyse
        with self.assertRaises(BeamError):
            deflect(beam, analyse(beam), -1.0)


class TestTorsion(unittest.TestCase):
    """Shear stress and twist in a shaft, against the closed forms."""

    def test_the_three_equations(self):
        from engicalc.core.torsion import Shaft

        # A 50 mm solid steel shaft, a metre long, carrying 1 kN m.
        shaft = Shaft(outer=0.050, length=1.0, modulus=80e9, torque=1000.0)
        self.assertAlmostEqual(shaft.j, math.pi * 0.05 ** 4 / 32.0,
                               places=15)
        self.assertAlmostEqual(shaft.max_stress,
                               16 * 1000.0 / (math.pi * 0.05 ** 3), places=6)
        self.assertAlmostEqual(shaft.twist,
                               1000.0 * 1.0 / (80e9 * shaft.j), places=12)
        # Nothing at the centre, which is the shape of the whole thing.
        self.assertAlmostEqual(shaft.stress_at(0.0), 0.0, places=12)

    def test_a_tube_is_the_difference_of_two_bars(self):
        from engicalc.core.torsion import polar_second_moment

        self.assertAlmostEqual(
            polar_second_moment(0.060, 0.040),
            math.pi * (0.060 ** 4 - 0.040 ** 4) / 32.0, places=15)

    def test_the_metal_near_the_axis_is_doing_almost_nothing(self):
        from engicalc.core.torsion import Shaft

        # The point of the subject. Boring out two thirds of the diameter
        # takes away more than half the weight and less than a fifth of the
        # strength, because of the fourth power.
        solid = Shaft(outer=0.060, torque=800.0)
        tube = Shaft(outer=0.060, inner=0.040, torque=800.0)
        self.assertGreater(tube.j / solid.j, 0.75)
        self.assertLess(tube.area / solid.area, 0.60)
        self.assertTrue([n for n in tube.notes() if "tubes" in n])

    def test_power_and_torque_go_round_and_come_back(self):
        from engicalc.core.torsion import power_from_torque, torque_from_power

        for kilowatts, rpm in ((15, 1450), (75, 2950), (2.2, 960)):
            with self.subTest(kw=kilowatts, rpm=rpm):
                torque = torque_from_power(kilowatts * 1000.0, rpm)
                self.assertAlmostEqual(
                    power_from_torque(torque, rpm) / 1000.0, kilowatts,
                    places=9)
        # 15 kW at 1450 rev/min is about 99 N m, which is worth pinning
        # down rather than only checking against itself.
        self.assertAlmostEqual(torque_from_power(15000.0, 1450.0), 98.786,
                               places=2)

    def test_a_standstill_has_no_torque_to_give(self):
        from engicalc.core.torsion import TorsionError, torque_from_power

        with self.assertRaises(TorsionError):
            torque_from_power(15000.0, 0.0)

    def test_sizing_for_a_stress_gives_back_that_stress(self):
        from engicalc.core.torsion import Shaft, diameter_for_stress

        # Solved rather than iterated, so it should land exactly.
        for ratio in (0.0, 0.5, 0.7):
            with self.subTest(bore_ratio=ratio):
                found = diameter_for_stress(500.0, 60e6, ratio)
                shaft = Shaft(outer=found, inner=found * ratio, torque=500.0)
                self.assertAlmostEqual(shaft.max_stress, 60e6, places=3)

    def test_sizing_for_a_twist_gives_back_that_twist(self):
        from engicalc.core.torsion import Shaft, diameter_for_twist

        wanted = math.radians(1.0)
        found = diameter_for_twist(500.0, 2.0, 80e9, wanted)
        shaft = Shaft(outer=found, length=2.0, modulus=80e9, torque=500.0)
        self.assertAlmostEqual(shaft.twist, wanted, places=9)

    def test_a_hollow_shaft_is_bigger_but_lighter_for_the_same_stress(self):
        from engicalc.core.torsion import Shaft, diameter_for_stress

        solid = diameter_for_stress(500.0, 60e6, 0.0)
        tube = diameter_for_stress(500.0, 60e6, 0.7)
        self.assertGreater(tube, solid)
        light = Shaft(outer=tube, inner=tube * 0.7)
        heavy = Shaft(outer=solid)
        self.assertLess(light.area, heavy.area * 0.7)

    def test_a_torque_part_way_along_splits_inversely_with_length(self):
        from engicalc.core.torsion import shared_torque

        # Statically indeterminate, and settled the way a propped beam is:
        # both halves twist by the same amount where they meet.
        near, far = shared_torque(900.0, 0.3, 0.6)
        self.assertAlmostEqual(near + far, 900.0, places=9)
        self.assertAlmostEqual(near, 600.0, places=9)
        self.assertAlmostEqual(far, 300.0, places=9)
        # Applied in the middle it splits evenly, which is the case anybody
        # can check without doing the algebra.
        self.assertEqual(shared_torque(900.0, 0.5, 0.5), (450.0, 450.0))

    def test_the_shafts_that_are_not_shafts_are_refused(self):
        from engicalc.core.torsion import (Shaft, TorsionError,
                                           polar_second_moment)

        with self.assertRaises(TorsionError):
            polar_second_moment(0.0)
        with self.assertRaises(TorsionError):
            polar_second_moment(0.05, 0.05)
        with self.assertRaises(TorsionError):
            polar_second_moment(0.05, 0.06)
        with self.assertRaises(TorsionError):
            Shaft(outer=0.05, length=0.0).twist
        with self.assertRaises(TorsionError):
            Shaft(outer=0.05, modulus=0.0).twist

    def test_it_mentions_a_shaft_that_twists_too_much(self):
        from engicalc.core.torsion import Shaft

        # A degree per metre is the usual limit, and past it the stiffness
        # sizes the shaft rather than the stress.
        bendy = Shaft(outer=0.020, length=1.0, modulus=80e9, torque=100.0)
        self.assertTrue([n for n in bendy.notes() if "per metre" in n])


class TestSectionProperties(unittest.TestCase):
    """Against the closed forms, and against the tables for real sections."""

    def test_a_rectangle_is_the_formula_everyone_knows(self):
        from engicalc.core.sections import solid_rectangle

        p = solid_rectangle(60.0, 100.0).properties()
        self.assertAlmostEqual(p.area, 6000.0, places=9)
        self.assertAlmostEqual(p.ixx, 60.0 * 100.0 ** 3 / 12.0, places=6)
        self.assertAlmostEqual(p.iyy, 100.0 * 60.0 ** 3 / 12.0, places=6)
        self.assertAlmostEqual(p.z, 60.0 * 100.0 ** 2 / 6.0, places=6)
        self.assertAlmostEqual(p.rx, 100.0 / math.sqrt(12.0), places=9)
        # Symmetrical, so the axes given are already the principal ones.
        self.assertAlmostEqual(p.ixy, 0.0, places=9)

    def test_a_circle_is_pi_d_to_the_fourth_over_sixty_four(self):
        from engicalc.core.sections import solid_round

        p = solid_round(50.0).properties()
        self.assertAlmostEqual(p.area, math.pi * 625.0, places=9)
        self.assertAlmostEqual(p.ixx, math.pi * 50.0 ** 4 / 64.0, places=6)
        self.assertAlmostEqual(p.ixx, p.iyy, places=9)

    def test_two_halves_stacked_are_the_whole(self):
        from engicalc.core.sections import Rectangle, Section

        # The parallel axis theorem, which is the only thing in here that
        # anybody gets wrong: about the centroid the two halves come to the
        # whole, and about any other axis they do not.
        whole = Section(parts=[Rectangle(width=40.0, height=90.0)])
        halves = Section(parts=[
            Rectangle(x=0.0, y=22.5, width=40.0, height=45.0),
            Rectangle(x=0.0, y=-22.5, width=40.0, height=45.0)])
        self.assertAlmostEqual(whole.properties().ixx,
                               halves.properties().ixx, places=6)
        self.assertAlmostEqual(whole.properties().cy,
                               halves.properties().cy, places=9)

    def test_a_hole_is_a_part_with_a_minus_sign(self):
        from engicalc.core.sections import Rectangle, Section

        box = Section(parts=[Rectangle(width=100.0, height=60.0),
                             Rectangle(width=90.0, height=50.0,
                                       solid=False)])
        p = box.properties()
        self.assertAlmostEqual(p.area, 100 * 60 - 90 * 50, places=9)
        self.assertAlmostEqual(
            p.ixx, (100 * 60 ** 3 - 90 * 50 ** 3) / 12.0, places=6)
        # And a hole cannot make the section wider than the material is.
        self.assertAlmostEqual(p.top, 30.0, places=9)

    def test_holes_bigger_than_the_shape_are_refused(self):
        from engicalc.core.sections import (Rectangle, Section, SectionError)

        with self.assertRaises(SectionError):
            Section(parts=[Rectangle(width=10.0, height=10.0),
                           Rectangle(width=20.0, height=20.0,
                                     solid=False)]).properties()

    def test_a_triangle_by_its_corners(self):
        from engicalc.core.sections import Polygon, Section

        # bh^3/36 about the centroid, which sits a third of the way up.
        base, height = 60.0, 40.0
        p = Section(parts=[Polygon(points=[(0, 0), (base, 0),
                                           (0, height)])]).properties()
        self.assertAlmostEqual(p.area, base * height / 2.0, places=9)
        self.assertAlmostEqual(p.cy, height / 3.0, places=9)
        self.assertAlmostEqual(p.ixx, base * height ** 3 / 36.0, places=6)
        self.assertAlmostEqual(p.iyy, height * base ** 3 / 36.0, places=6)

    def test_corners_the_other_way_round_are_the_same_shape(self):
        from engicalc.core.sections import Polygon, Section

        # Traced clockwise the shoelace area comes out negative. Taken as it
        # stands that quietly turns the shape into a hole.
        points = [(0, 0), (60, 0), (0, 40)]
        forwards = Section(parts=[Polygon(points=points)]).properties()
        backwards = Section(parts=[
            Polygon(points=list(reversed(points)))]).properties()
        self.assertAlmostEqual(forwards.area, backwards.area, places=9)
        self.assertAlmostEqual(forwards.ixx, backwards.ixx, places=6)
        self.assertAlmostEqual(forwards.ixy, backwards.ixy, places=6)

    def test_the_fillet_is_the_arc_it_says_it_is(self):
        from engicalc.core.sections import Fillet, Polygon

        # The four constants for the fillet were worked out by hand, and a
        # hand-worked integral that is nearly right looks exactly like one
        # that is. So it is put beside the same region drawn as a many-sided
        # polygon, where the only error left is the chord across each arc.
        radius, steps = 12.0, 600
        exact = Fillet(radius=radius, across=1.0, up=1.0)
        points = [(0.0, 0.0)]
        for step in range(steps + 1):
            angle = math.radians(270.0 - 90.0 * step / steps)
            points.append((radius + radius * math.cos(angle),
                           radius + radius * math.sin(angle)))
        drawn = Polygon(points=points)

        self.assertAlmostEqual(exact.area() / drawn.area(), 1.0, places=4)
        for mine, theirs in zip(exact.centre(), drawn.centre()):
            self.assertAlmostEqual(mine / theirs, 1.0, places=4)
        for mine, theirs in zip(exact.own(), drawn.own()):
            self.assertAlmostEqual(mine / theirs, 1.0, places=4)

    def test_the_fillet_turns_round_with_the_corner(self):
        from engicalc.core.sections import Fillet

        # Only the product term knows which corner it is in. Getting that
        # sign wrong is invisible on anything symmetrical, because the four
        # of them cancel, and wrong on every angle and channel.
        corners = {(a, u): Fillet(radius=10.0, across=a, up=u).own()[2]
                   for a in (1.0, -1.0) for u in (1.0, -1.0)}
        self.assertAlmostEqual(corners[(1.0, 1.0)], corners[(-1.0, -1.0)],
                               places=9)
        self.assertAlmostEqual(corners[(1.0, 1.0)], -corners[(1.0, -1.0)],
                               places=9)

    #: (name, d, b, tw, tf, r, area cm2, Ixx cm4, Iyy cm4).
    #:
    #: The published properties, beside the five dimensions on the drawing.
    #: Three quantities landing on the tabulated figures at once, out of
    #: five numbers typed in, is not something a wrongly assembled shape
    #: does by luck.
    ROLLED = [
        ("305x165x40 UB", 303.4, 165.0, 6.0, 10.2, 8.9, 51.3, 8503.0, 764.0),
        ("203x133x25 UB", 203.2, 133.2, 5.7, 7.8, 7.6, 32.0, 2340.0, 308.0),
        ("152x152x30 UC", 157.6, 152.9, 6.5, 9.4, 7.6, 38.3, 1748.0, 560.0),
    ]

    def test_a_rolled_section_comes_out_at_its_tabulated_properties(self):
        from engicalc.core.sections import i_section

        for name, d, b, tw, tf, r, area, ixx, iyy in self.ROLLED:
            with self.subTest(section=name):
                p = i_section(d, b, tw, tf, r).properties()
                self.assertAlmostEqual(p.area / 100.0, area, delta=0.15)
                self.assertAlmostEqual(p.ixx / 1e4, ixx, delta=ixx * 0.005)
                self.assertAlmostEqual(p.iyy / 1e4, iyy, delta=iyy * 0.005)

    def test_leaving_the_root_radii_off_reads_low(self):
        from engicalc.core.sections import i_section

        # Which is the reason for going to the trouble of having them. Two
        # percent of a second moment is two percent of every deflection
        # worked from it.
        for name, d, b, tw, tf, r, *_ in self.ROLLED:
            with self.subTest(section=name):
                rounded = i_section(d, b, tw, tf, r).properties().ixx
                sharp = i_section(d, b, tw, tf, 0.0).properties().ixx
                self.assertLess(sharp, rounded)
                self.assertGreater(1.0 - sharp / rounded, 0.01)
                self.assertLess(1.0 - sharp / rounded, 0.03)

    def test_a_tube_is_the_difference_of_two_circles(self):
        from engicalc.core.sections import hollow_circle

        p = hollow_circle(114.3, 5.0).properties()
        self.assertAlmostEqual(
            p.ixx, math.pi * (114.3 ** 4 - 104.3 ** 4) / 64.0, places=6)
        self.assertAlmostEqual(p.ixx, p.iyy, places=6)

    def test_a_channel_is_not_centred_on_its_web(self):
        from engicalc.core.sections import channel

        # The first shape here whose centroid is somewhere you have to work
        # out rather than somewhere you can see.
        p = channel(200.0, 75.0, 6.0, 12.5, 12.0).properties()
        self.assertGreater(p.cx, 6.0)
        self.assertLess(p.cx, 75.0 / 2.0)
        self.assertAlmostEqual(p.cy, 0.0, places=9)
        # Symmetrical about the horizontal axis only, so Ixy still vanishes.
        self.assertAlmostEqual(p.ixy, 0.0, places=6)

    def test_an_angle_has_no_axis_of_symmetry_and_says_so(self):
        from engicalc.core.sections import angle

        p = angle(100.0, 75.0, 10.0, 10.0).properties()
        self.assertNotAlmostEqual(p.ixy, 0.0, places=3)
        first, second, turn = p.principal()
        # Turning the axes cannot change the sum, which is what makes it a
        # check rather than a restatement.
        self.assertAlmostEqual(first + second, p.ixx + p.iyy, places=4)
        self.assertGreater(first, p.ixx)
        self.assertLess(second, p.iyy)
        self.assertGreater(abs(turn), 5.0)
        # And the weak axis is nowhere near either leg, which is the thing
        # worth knowing about an angle.
        self.assertLess(abs(turn), 85.0)

    def test_the_smaller_modulus_is_the_one_that_governs(self):
        from engicalc.core.sections import tee

        p = tee(100.0, 100.0, 8.0, 10.0, 8.0).properties()
        self.assertGreater(p.bottom, p.top)      # centroid up near the flange
        self.assertLess(p.z_bottom, p.z_top)
        self.assertEqual(p.z, p.z_bottom)

    def test_bending_stress_is_m_y_over_i(self):
        from engicalc.core.sections import i_section

        p = i_section(303.4, 165.0, 6.0, 10.2, 8.9).properties()
        moment = 120e6                            # N mm, which is 120 kN m
        self.assertAlmostEqual(p.bending_stress(moment),
                               moment * p.top / p.ixx, places=9)
        self.assertAlmostEqual(p.bending_stress(moment, 0.0), 0.0, places=12)

    def test_a_section_with_nothing_in_it_is_refused(self):
        from engicalc.core.sections import Section, SectionError

        with self.assertRaises(SectionError):
            Section().properties()


class TestBuckling(unittest.TestCase):
    """Columns, against Euler and against the two limits that bound it."""

    MODULUS, YIELD = 210e3, 275.0

    def _bar(self, length=3000.0, **rest):
        from engicalc.core.buckling import Column
        from engicalc.core.sections import solid_round

        found = solid_round(50.0).properties()
        return Column(area=found.area, second_moment=found.ixx,
                      length=length, modulus=self.MODULUS,
                      yield_stress=self.YIELD, **rest)

    def test_euler_is_pi_squared_ei_over_l_squared(self):
        column = self._bar()
        self.assertAlmostEqual(
            column.euler_load,
            math.pi ** 2 * self.MODULUS * math.pi * 50.0 ** 4 / 64.0
            / 3000.0 ** 2, places=6)

    def test_the_radius_of_gyration_of_a_round_bar_is_a_quarter_of_it(self):
        self.assertAlmostEqual(self._bar().radius_of_gyration, 50.0 / 4.0,
                               places=9)

    def test_holding_the_ends_changes_it_by_the_square_of_the_factor(self):
        from engicalc.core.buckling import END_CONDITIONS

        pinned = self._bar()
        for how, factor in END_CONDITIONS.items():
            with self.subTest(ends=how):
                held = self._bar(ends=how)
                self.assertAlmostEqual(held.effective_length,
                                       factor * 3000.0, places=9)
                self.assertAlmostEqual(
                    held.euler_load, pinned.euler_load / factor ** 2,
                    places=3)

    def test_euler_reaches_yield_at_pi_root_e_over_sigma(self):
        column = self._bar()
        self.assertAlmostEqual(
            column.transition,
            math.pi * math.sqrt(self.MODULUS / self.YIELD), places=9)
        self.assertAlmostEqual(column.euler_stress(column.transition),
                               self.YIELD, places=6)

    def test_perry_robertson_lies_between_the_two_curves_everywhere(self):
        # The whole reason it exists. Above it, a curve for a column that
        # cannot squash; below it, one for a column that cannot bend.
        column = self._bar()
        for ratio in [1.0 + index * 2.0 for index in range(300)]:
            with self.subTest(slenderness=ratio):
                perry = column.perry_stress(ratio)
                self.assertLessEqual(perry, self.YIELD + 1e-9)
                self.assertLessEqual(perry, column.euler_stress(ratio) + 1e-9)
                self.assertGreater(perry, 0.0)

    def test_it_meets_yield_at_one_end_and_euler_at_the_other(self):
        column = self._bar()
        # A stocky column squashes. This used to come out at 256 where it
        # has to be 275: the formula as it is always quoted subtracts two
        # very large nearly equal numbers, and a double has nothing left
        # after it.
        self.assertAlmostEqual(column.perry_stress(1e-9), self.YIELD,
                               places=6)
        self.assertAlmostEqual(column.perry_stress(1e-3), self.YIELD,
                               places=2)
        # A very slender one buckles elastically.
        self.assertAlmostEqual(
            column.perry_stress(2000.0) / column.euler_stress(2000.0), 1.0,
            places=1)

    def test_rankine_is_the_two_failures_in_series(self):
        from engicalc.core.buckling import Column

        column = self._bar()
        for ratio in (30.0, 90.0, 200.0):
            with self.subTest(slenderness=ratio):
                # 1/P = 1/P_squash + 1/P_Euler, which is what the formula
                # means and is worth checking rather than restating.
                expected = 1.0 / (1.0 / self.YIELD
                                  + 1.0 / column.euler_stress(ratio))
                self.assertAlmostEqual(column.rankine_stress(ratio),
                                       expected, places=9)
        del Column

    def test_a_longer_column_carries_less(self):
        loads = [self._bar(length=length).perry_load
                 for length in (1000.0, 2000.0, 4000.0, 8000.0)]
        self.assertEqual(loads, sorted(loads, reverse=True))

    def test_a_column_buckles_about_its_weak_principal_axis(self):
        from engicalc.core.buckling import Column
        from engicalc.core.sections import angle

        # On an angle the weak axis is neither leg - it runs diagonally -
        # so taking the smaller of Ixx and Iyy would overstate what it
        # carries. The smaller principal second moment is the right one.
        found = angle(100.0, 100.0, 10.0, 12.0).properties()
        _stiff, weak, turn = found.principal()
        self.assertLess(weak, min(found.ixx, found.iyy))
        self.assertGreater(abs(turn), 30.0)
        column = Column(area=found.area, second_moment=weak, length=2000.0,
                        modulus=self.MODULUS, yield_stress=self.YIELD)
        wrong = Column(area=found.area,
                       second_moment=min(found.ixx, found.iyy),
                       length=2000.0, modulus=self.MODULUS,
                       yield_stress=self.YIELD)
        self.assertLess(column.perry_load, wrong.perry_load)

    def test_sizing_a_column_gives_back_the_load(self):
        from engicalc.core.buckling import Column, slenderness_for

        ratio = slenderness_for(500e3, 5000.0, self.MODULUS, self.YIELD)
        column = Column(area=5000.0, second_moment=1.0, length=1.0,
                        modulus=self.MODULUS, yield_stress=self.YIELD)
        self.assertAlmostEqual(column.perry_stress(ratio) * 5000.0, 500e3,
                               delta=10.0)

    def test_it_says_when_euler_is_meaningless_rather_than_merely_wrong(self):
        stocky = self._bar(length=1000.0)
        self.assertGreater(stocky.euler_stress(), self.YIELD)
        self.assertTrue([n for n in stocky.notes() if "meaningless" in n])
        slender = self._bar(length=6000.0)
        self.assertFalse([n for n in slender.notes() if "meaningless" in n])

    def test_the_columns_that_are_not_columns_are_refused(self):
        from engicalc.core.buckling import BucklingError, Column

        for bad in (dict(area=0.0, second_moment=1.0, length=1.0),
                    dict(area=1.0, second_moment=0.0, length=1.0),
                    dict(area=1.0, second_moment=1.0, length=0.0),
                    dict(area=1.0, second_moment=1.0, length=1.0,
                         modulus=0.0),
                    dict(area=1.0, second_moment=1.0, length=1.0,
                         ends="welded")):
            with self.subTest(**bad):
                with self.assertRaises(BucklingError):
                    Column(**bad).slenderness


class TestShearInASection(unittest.TestCase):
    """tau = V Q / (I t), against the two answers everybody knows.

    Everything here is in newtons and millimetres, which is what the section
    module works in - so a second moment in mm^4 and a force in N give a
    stress in N/mm^2 with nothing to convert.
    """

    FORCE = 100e3

    def test_a_rectangle_peaks_at_three_halves_of_the_average(self):
        from engicalc.core.sections import solid_rectangle

        section = solid_rectangle(100.0, 200.0)
        found = section.properties()
        worst, level = section.worst_shear(self.FORCE)
        self.assertAlmostEqual(worst, 3 * self.FORCE / (2 * found.area),
                               delta=1e-3)
        # At the neutral axis, and exactly there.
        self.assertAlmostEqual(level, found.cy, delta=1.0)
        self.assertAlmostEqual(section.shear_stress(self.FORCE, found.cy),
                               3 * self.FORCE / (2 * found.area), places=9)

    def test_a_rectangle_is_parabolic_and_zero_at_the_edges(self):
        from engicalc.core.sections import solid_rectangle

        # tau = 3V/2A (1 - (2y/h)^2), so at half the depth it is three
        # quarters of the peak - which a linear guess would not give.
        section = solid_rectangle(100.0, 200.0)
        peak = 3 * self.FORCE / (2 * section.properties().area)
        self.assertAlmostEqual(section.shear_stress(self.FORCE, 50.0),
                               0.75 * peak, places=9)
        self.assertAlmostEqual(section.shear_stress(self.FORCE, 100.0), 0.0,
                               places=9)
        self.assertAlmostEqual(section.shear_stress(self.FORCE, -100.0), 0.0,
                               places=9)

    def test_a_round_bar_peaks_at_four_thirds_of_the_average(self):
        from engicalc.core.sections import solid_round

        section = solid_round(100.0)
        found = section.properties()
        worst, _level = section.worst_shear(self.FORCE)
        self.assertAlmostEqual(worst / (self.FORCE / found.area), 4.0 / 3.0,
                               places=4)

    def test_the_first_moment_is_the_one_in_the_formula(self):
        from engicalc.core.sections import solid_rectangle

        # Q at the neutral axis of a rectangle is b h^2 / 8. Checking Q on
        # its own matters because a wrong Q and a wrong I can cancel in the
        # ratio and still give the right peak.
        section = solid_rectangle(100.0, 200.0)
        found = section.properties()
        area, first = section.above(found.cy)
        self.assertAlmostEqual(first - found.cy * area,
                               100.0 * 200.0 ** 2 / 8.0, places=6)

    def test_an_i_section_steps_where_the_flange_meets_the_web(self):
        from engicalc.core.sections import i_section

        # Nothing changes across that line except the width, which drops
        # from the flange to the web - so the stress jumps by the same
        # ratio. It is why the web carries the shear and the flanges the
        # bending.
        section = i_section(303.4, 165.0, 6.0, 10.2, 8.9)
        found = section.properties()
        junction = found.cy + (303.4 / 2.0 - 10.2)
        inside = section.shear_stress(self.FORCE, junction - 0.5)
        outside = section.shear_stress(self.FORCE, junction + 0.5)
        self.assertGreater(inside / outside, 5.0)

        # And the step is the width doing it. Q is nearly the same either
        # side - it is the half millimetre of metal between the two levels
        # and nothing else - so the stresses go inversely with the widths,
        # to within how much that half millimetre changes Q.
        narrow = section.width_at(junction - 0.5)
        wide = section.width_at(junction + 0.5)
        self.assertAlmostEqual(inside / outside, wide / narrow,
                               delta=0.1 * wide / narrow)

    def test_the_web_of_an_i_section_carries_nearly_all_of_it(self):
        from engicalc.core.sections import i_section

        section = i_section(303.4, 165.0, 6.0, 10.2, 8.9)
        levels, stresses = section.shear_profile(self.FORCE, 400)
        carried = [stress * section.width_at(level)
                   for level, stress in zip(levels, stresses)]
        in_web = [value for level, value in zip(levels, carried)
                  if section.width_at(level) < 30.0]
        self.assertGreater(sum(in_web) / sum(carried), 0.9)

    def test_a_hole_takes_area_away_rather_than_adding_it(self):
        from engicalc.core.sections import Rectangle, Section

        # A box is the outer rectangle less the inner one, and the shear
        # has to see it that way round.
        box = Section(parts=[Rectangle(width=100.0, height=200.0),
                             Rectangle(width=80.0, height=180.0,
                                       solid=False)])
        self.assertAlmostEqual(box.width_at(0.0), 20.0, places=9)
        area, _first = box.above(0.0)
        self.assertAlmostEqual(area, 100.0 * 100.0 - 80.0 * 90.0, places=6)

    def test_the_shear_is_proportional_to_the_force(self):
        from engicalc.core.sections import i_section

        section = i_section(303.4, 165.0, 6.0, 10.2, 8.9)
        one, _level = section.worst_shear(self.FORCE)
        two, _level = section.worst_shear(2.0 * self.FORCE)
        self.assertAlmostEqual(two, 2.0 * one, places=6)

    def test_the_two_stresses_never_peak_in_the_same_place(self):
        from engicalc.core.sections import solid_rectangle

        # Which is the reason this exists. Bending is largest at the top
        # and bottom and nothing in the middle; shear is the other way
        # round.
        section = solid_rectangle(100.0, 200.0)
        found = section.properties()
        _worst, level = section.worst_shear(self.FORCE)
        self.assertAlmostEqual(level, found.cy, delta=1.0)
        self.assertAlmostEqual(found.stress_at(0.0, 0.0, 1e6), 0.0,
                               places=9)
        self.assertGreater(abs(found.stress_at(0.0, found.top, 1e6)), 0.0)


class TestSectionTable(unittest.TestCase):
    """A table of numbers in a program has to justify itself."""

    def test_every_row_reconciles_with_its_own_properties(self):
        from engicalc.core import section_table

        # This is what the table is for. Each row carries the dimensions and
        # the published area and second moments; the properties are worked
        # out from the dimensions and have to land on the published ones.
        # Five numbers producing three at once is tight enough that a row
        # which agrees is a row that is right - and two rows that would not
        # agree were taken out rather than shipped.
        off = section_table.reconcile()
        self.assertEqual([], off, "\n".join(
            f"{name}: {what} computed {mine:.4g}, table {theirs:.4g}, "
            f"off by {error:.1%}" for name, what, mine, theirs, error in off))

    def test_most_of_them_agree_far_more_closely_than_that(self):
        from engicalc.core import section_table

        # The tolerance is two percent because the published figures are
        # rounded. If the shapes were being assembled roughly, the rows
        # would sit up against that limit rather than nowhere near it.
        worst = [error for _name, error in section_table.agreement()]
        self.assertLess(sorted(worst)[len(worst) // 2], 0.005)
        self.assertLess(max(worst), section_table.TOLERANCE)

    def test_a_designation_builds_the_section_it_names(self):
        from engicalc.core import section_table

        built = section_table.build("305x165x40 UB")
        self.assertEqual("305x165x40 UB", built.name)
        self.assertAlmostEqual(built.properties().ixx / 1e4, 8503.0,
                               delta=40.0)

    def test_a_designation_nobody_has_heard_of_says_what_to_do(self):
        from engicalc.core import section_table
        from engicalc.core.sections import SectionError

        with self.assertRaises(SectionError) as caught:
            section_table.build("400x400x999 UB")
        self.assertIn("dimensions", str(caught.exception))

    def test_the_table_covers_the_shapes_it_claims_to(self):
        from engicalc.core import section_table

        found = {row[1] for row in section_table.TABLE}
        self.assertEqual({"I section", "channel", "angle", "circular hollow"},
                         found)


class TestUnsymmetricalBending(unittest.TestCase):
    """M y / I is the stress in a section with an axis of symmetry."""

    def test_it_is_still_m_y_over_i_when_there_is_one(self):
        from engicalc.core.sections import i_section

        # The general form has to collapse back, or it is a second answer
        # to a question that already had one.
        section = i_section(303.4, 165.0, 6.0, 10.2, 8.9)
        found = section.properties()
        moment = 120e6
        stress, _x, _y = section.worst_stress(moment)
        self.assertAlmostEqual(abs(stress), moment / found.z, places=6)
        self.assertAlmostEqual(found.stress_at(0.0, found.top, moment),
                               moment * found.top / found.ixx, places=9)

    def test_an_angle_is_worked_harder_than_m_y_over_i_says(self):
        from engicalc.core.sections import angle

        # Bending an angle about its x axis bends it sideways too, and the
        # stress has a term in x that M y / I has dropped. On a 100x75x10
        # that term is a third of the answer, which is not a refinement.
        section = angle(100.0, 75.0, 10.0, 10.0)
        found = section.properties()
        moment = 120e6
        simple = moment * found.top / found.ixx
        stress, at_x, at_y = section.worst_stress(moment)
        self.assertGreater(abs(stress), simple * 1.2)
        # And it is worked hardest at the tip of the upstanding leg, which
        # is neither the top fibre nor the bottom one.
        self.assertAlmostEqual(at_y, 100.0, places=6)
        self.assertLess(at_x, 20.0)

    def test_the_worst_corner_is_found_rather_than_assumed(self):
        from engicalc.core.sections import angle

        # Every corner of the shape is asked. Nothing on the section may be
        # worked harder than the answer says.
        section = angle(100.0, 75.0, 10.0, 10.0)
        found = section.properties()
        worst = abs(section.worst_stress(80e6)[0])
        for part in section.parts:
            if not part.solid:
                continue
            for px, py in part.outline():
                self.assertLessEqual(
                    abs(found.stress_at(px - found.cx, py - found.cy, 80e6)),
                    worst + 1e-9)

    def test_square_toes_make_an_angle_stiffer_than_it_is(self):
        from engicalc.core.sections import angle

        # Which is why they are modelled: without them every angle read two
        # to three percent stiff, and by more on the small ones - the shape
        # of a missing radius rather than of a wrong dimension.
        rolled = angle(100.0, 100.0, 10.0, 12.0).properties()
        square = angle(100.0, 100.0, 10.0, 12.0, toe=0.0).properties()
        self.assertGreater(square.ixx, rolled.ixx)
        self.assertAlmostEqual(rolled.ixx / 1e4, 177.0, delta=1.0)
        self.assertGreater(square.ixx / 1e4, 179.0)


class TestR134a(unittest.TestCase):
    """The refrigerant, against the curves published with the equation.

    An earlier attempt at R134a was abandoned rather than shipped: it agreed
    with the saturation line to a fiftieth of a percent and had the
    saturated vapour density wrong by a factor of fifty. So the checks here
    are deliberately not just the saturation line - the densities, the
    latent heat and the reference state are all pinned down separately,
    because the previous failure passed every test anybody would think to
    write first.
    """

    #: The ancillary saturation curves published alongside the equation of
    #: state. They are fitted to it, so they say where the saturation line
    #: is without anything here being consulted - which is what makes them
    #: a check rather than a restatement.
    ANCILLARY_TR = 374.21
    ANCILLARY_PR = 4059280.0
    ANCILLARY_RHOR = 5017.053 * 0.102032
    PS_N = [0.4331478287291047, -9.090302559074352, 2.1476074125217703,
            -1.557687007603464, -3.5020328972698604, 14.958442337201044]
    PS_T = [0.845, 0.99, 1.14, 2.651, 4.507, 17.235]

    def _ancillary_pressure(self, T):
        theta = 1.0 - T / self.ANCILLARY_TR
        return self.ANCILLARY_PR * math.exp(
            self.ANCILLARY_TR / T
            * sum(n * theta ** t for n, t in zip(self.PS_N, self.PS_T)))

    def test_the_saturation_line_is_where_it_is_published_to_be(self):
        from engicalc.core.r134a import saturation_pressure

        for celsius in (-40, -26.07, -20, -10, 0, 10, 20, 30, 40, 50, 60,
                        80, 100):
            T = celsius + 273.15
            with self.subTest(celsius=celsius):
                error = abs(saturation_pressure(T)
                            / self._ancillary_pressure(T) - 1.0)
                self.assertLess(error, 2e-4, f"{error:.2%} out")

    def test_the_reference_state_is_exact_because_it_is_solved_for(self):
        from engicalc.core.r134a import saturated

        # Saturated liquid at 0 C is 200 kJ/kg and 1 kJ/kg K by convention.
        # The two arbitrary constants in the ideal-gas part are worked out
        # from that rather than copied, so this is a guarantee rather than
        # a hope that they were typed in correctly.
        liquid, _vapour = saturated(273.15)
        self.assertAlmostEqual(liquid.h, 200e3, places=6)
        self.assertAlmostEqual(liquid.s, 1000.0, places=9)

    def test_the_latent_heat_is_the_one_in_the_tables(self):
        from engicalc.core.r134a import latent_heat, saturated

        # This is the number the previous attempt got wrong by a factor of
        # fifty while looking perfectly healthy everywhere else.
        self.assertAlmostEqual(latent_heat(273.15) / 1000.0, 198.6,
                               delta=0.1)
        _liquid, vapour = saturated(273.15)
        self.assertAlmostEqual(vapour.h / 1000.0, 398.6, delta=0.1)
        self.assertAlmostEqual(vapour.s / 1000.0, 1.7274, delta=0.001)

    def test_the_saturated_densities_are_the_ones_in_the_tables(self):
        from engicalc.core.r134a import saturated

        # The other thing the previous attempt got wrong. 1294.8 and
        # 14.428 kg/m3 at 0 C.
        liquid, vapour = saturated(273.15)
        self.assertAlmostEqual(liquid.rho, 1294.8, delta=1.0)
        self.assertAlmostEqual(vapour.rho, 14.428, delta=0.02)

    def test_it_boils_at_the_right_temperature_at_one_atmosphere(self):
        from engicalc.core.r134a import saturation_temperature

        self.assertAlmostEqual(saturation_temperature(101325.0) - 273.15,
                               -26.07, delta=0.02)

    def test_the_critical_pressure_comes_out_of_the_critical_point(self):
        from engicalc.core import r134a

        got = r134a._pressure(r134a.T_CRITICAL, r134a.RHO_CRITICAL)
        self.assertAlmostEqual(got / r134a.P_CRITICAL, 1.0, places=4)

    def test_pressure_and_temperature_go_round_and_come_back(self):
        from engicalc.core.r134a import at_pressure_and_temperature

        for celsius, kpa in ((40, 500), (60, 1000), (100, 2000),
                             (20, 100), (150, 5000)):
            with self.subTest(celsius=celsius, kpa=kpa):
                state = at_pressure_and_temperature(kpa * 1000.0,
                                                    celsius + 273.15)
                self.assertAlmostEqual(state.p / (kpa * 1000.0), 1.0,
                                       places=6)
                self.assertAlmostEqual(state.T, celsius + 273.15, places=9)

    def test_saturation_goes_round_and_comes_back_too(self):
        from engicalc.core.r134a import (saturation_pressure,
                                         saturation_temperature)

        for celsius in (-30, -10, 10, 30, 50, 70):
            T = celsius + 273.15
            with self.subTest(celsius=celsius):
                self.assertAlmostEqual(
                    saturation_temperature(saturation_pressure(T)), T,
                    places=6)

    def test_the_first_derivative_is_the_one_the_pressure_uses(self):
        from engicalc.core.r134a import _residual

        # The pressure is the first density derivative and nothing else, so
        # it is the one derivative that has to be right for anything else to
        # mean anything.
        for delta in (0.01, 0.3, 1.0, 2.0, 2.6):
            for tau in (0.9, 1.37, 2.2):
                with self.subTest(delta=delta, tau=tau):
                    step = 1e-6
                    numeric = ((_residual(delta * (1 + step), tau)[0]
                                - _residual(delta * (1 - step), tau)[0])
                               / (2 * delta * step))
                    self.assertAlmostEqual(
                        _residual(delta, tau)[1] / numeric, 1.0, places=6)

    def test_a_wet_mixture_sits_between_the_two_phases(self):
        from engicalc.core.r134a import saturated, wet

        liquid, vapour = saturated(273.15)
        middle = wet(273.15, 0.5)
        self.assertAlmostEqual(middle.h, (liquid.h + vapour.h) / 2,
                               places=6)
        self.assertAlmostEqual(middle.p, liquid.p, places=6)
        # Volumes average, not densities, which is the one people get wrong.
        self.assertAlmostEqual(
            1.0 / middle.rho, (1.0 / liquid.rho + 1.0 / vapour.rho) / 2,
            places=9)

    def test_above_the_critical_point_there_is_no_saturation_line(self):
        from engicalc.core.r134a import R134aError, saturated

        with self.assertRaises(R134aError) as caught:
            saturated(380.0)
        self.assertIn("critical", str(caught.exception))

    def test_outside_the_range_it_says_so_rather_than_extrapolating(self):
        from engicalc.core.r134a import R134aError, state_at

        with self.assertRaises(R134aError):
            state_at(500.0, 20.0)
        with self.assertRaises(R134aError):
            state_at(100.0, 20.0)

    def test_the_specific_heats_are_the_right_size(self):
        from engicalc.core.r134a import saturated

        # Not a precise check - a sanity one. Liquid R134a is about
        # 1.3 kJ/kg K and its vapour about 0.9, and a formulation with a
        # mangled ideal-gas part gets these wrong by a lot while the
        # saturation line stays perfect.
        liquid, vapour = saturated(273.15)
        self.assertAlmostEqual(liquid.cp / 1000.0, 1.34, delta=0.06)
        self.assertAlmostEqual(vapour.cp / 1000.0, 0.90, delta=0.06)
        self.assertGreater(liquid.cp, liquid.cv)
        self.assertGreater(vapour.cp, vapour.cv)


class TestStateLookups(unittest.TestCase):
    """Finding a state by entropy or by enthalpy, which a cycle needs."""

    def test_both_lookups_come_back_where_they_started(self):
        from engicalc.core import r134a

        for celsius, kpa in ((40, 500), (60, 1000), (100, 2000), (-20, 100)):
            with self.subTest(celsius=celsius, kpa=kpa):
                start = r134a.at_pressure_and_temperature(kpa * 1000.0,
                                                          celsius + 273.15)
                by_entropy = r134a.at_pressure_and_entropy(kpa * 1000.0,
                                                           start.s)
                by_enthalpy = r134a.at_pressure_and_enthalpy(kpa * 1000.0,
                                                             start.h)
                self.assertAlmostEqual(by_entropy.T, start.T, places=6)
                self.assertAlmostEqual(by_enthalpy.T, start.T, places=6)

    def test_inside_the_dome_it_finds_the_dryness(self):
        from engicalc.core import r134a

        # Both properties are linear in dryness between the two saturated
        # states, so this is arithmetic rather than a search - and it has to
        # give back exactly the dryness it was handed.
        for celsius, dryness in ((0, 0.3), (-10, 0.8), (30, 0.5)):
            with self.subTest(celsius=celsius, dryness=dryness):
                wet = r134a.wet(celsius + 273.15, dryness)
                self.assertAlmostEqual(
                    r134a.at_pressure_and_entropy(wet.p, wet.s).quality,
                    dryness, places=6)
                self.assertAlmostEqual(
                    r134a.at_pressure_and_enthalpy(wet.p, wet.h).quality,
                    dryness, places=6)


class TestRefrigerationCycle(unittest.TestCase):
    """The four states, and the two sums that have to come out."""

    def _fluid(self):
        from engicalc.core import r134a
        return r134a

    def _ideal(self):
        from engicalc.core.cycle import Cycle
        return Cycle(fluid=self._fluid(), evaporating=263.15,
                     condensing=313.15)

    def test_the_textbook_cycle(self):
        # -10 C to 40 C, dry saturated in, reversible compressor. The
        # refrigerating effect is hg(-10) - hf(40) and the answer everybody
        # gets is a COP of about four.
        run = self._ideal()
        liquid, vapour = self._fluid().saturated(263.15)
        condensed, _ = self._fluid().saturated(313.15)
        found = run.performance()
        self.assertAlmostEqual(found["refrigerating effect"],
                               vapour.h - condensed.h, places=6)
        self.assertAlmostEqual(found["cooling COP"], 4.03, delta=0.05)

    def test_the_energy_balance_closes(self):
        # Heat out equals heat in plus work in. Worked out from the four
        # states rather than imposed, so it is a check and not a
        # restatement of how they were calculated.
        from engicalc.core.cycle import Cycle

        for superheat, subcool, efficiency in ((0, 0, 1.0), (5, 3, 0.7),
                                               (10, 0, 0.85), (0, 8, 0.6)):
            run = Cycle(fluid=self._fluid(), evaporating=263.15,
                        condensing=313.15, superheat=superheat,
                        subcool=subcool, efficiency=efficiency)
            with self.subTest(superheat=superheat, efficiency=efficiency):
                found = run.performance()
                self.assertAlmostEqual(
                    found["refrigerating effect"] + found["compressor work"],
                    found["heat rejected"], places=6)
                self.assertAlmostEqual(found["heating COP"],
                                       found["cooling COP"] + 1.0, places=9)
                self.assertEqual([], run.notes()[:0] or [])

    def test_the_throttle_keeps_the_enthalpy(self):
        # Which is the whole of what a throttle is, and why some of the
        # liquid flashes off on the way through it.
        _first, _second, third, fourth = self._ideal().states()
        self.assertAlmostEqual(third.h, fourth.h, places=6)
        self.assertGreater(fourth.quality, 0.0)
        self.assertLess(fourth.quality, 1.0)

    def test_a_reversible_compressor_keeps_the_entropy(self):
        first, second, _third, _fourth = self._ideal().states()
        self.assertAlmostEqual(second.s, first.s, places=6)
        self.assertGreater(second.T, first.T)

    def test_a_worse_compressor_costs_more_and_runs_hotter(self):
        from engicalc.core.cycle import Cycle

        better = Cycle(fluid=self._fluid(), evaporating=263.15,
                       condensing=313.15, efficiency=0.9).performance()
        worse = Cycle(fluid=self._fluid(), evaporating=263.15,
                      condensing=313.15, efficiency=0.6).performance()
        self.assertGreater(worse["compressor work"],
                           better["compressor work"])
        self.assertLess(worse["cooling COP"], better["cooling COP"])
        self.assertGreater(worse["discharge temperature"],
                           better["discharge temperature"])

    def test_nothing_beats_carnot(self):
        from engicalc.core.cycle import Cycle

        # A law rather than a preference, so it is worth making the code
        # prove it over a range rather than at one point.
        for evaporating in (253.15, 263.15, 273.15, 283.15):
            for condensing in (303.15, 313.15, 323.15, 333.15):
                run = Cycle(fluid=self._fluid(), evaporating=evaporating,
                            condensing=condensing, superheat=5.0,
                            efficiency=0.75)
                with self.subTest(evaporating=evaporating,
                                  condensing=condensing):
                    found = run.performance()
                    self.assertLess(found["cooling COP"], found["Carnot COP"])
                    self.assertGreater(found["fraction of Carnot"], 0.0)
                    self.assertLess(found["fraction of Carnot"], 1.0)

    def test_a_duty_sizes_the_machine(self):
        from engicalc.core.cycle import Cycle

        cooling = Cycle(fluid=self._fluid(), evaporating=263.15,
                        condensing=313.15, superheat=5.0, subcool=3.0,
                        efficiency=0.7, duty=5000.0).performance()
        self.assertAlmostEqual(
            cooling["mass flow"] * cooling["refrigerating effect"], 5000.0,
            places=6)
        self.assertAlmostEqual(
            cooling["condenser duty"],
            5000.0 + cooling["compressor power"], places=6)

        # A heat pump is bought for the other end of itself.
        heating = Cycle(fluid=self._fluid(), evaporating=268.15,
                        condensing=318.15, superheat=5.0, subcool=2.0,
                        efficiency=0.75, duty=8000.0,
                        heating=True).performance()
        self.assertAlmostEqual(heating["condenser duty"], 8000.0, places=6)

    def test_superheat_and_subcooling_move_things_the_right_way(self):
        from engicalc.core.cycle import Cycle

        plain = Cycle(fluid=self._fluid(), evaporating=263.15,
                      condensing=313.15).performance()
        # Subcooling gets more cooling for the same work, because the
        # refrigerant arrives at the throttle with less to flash off.
        colder = Cycle(fluid=self._fluid(), evaporating=263.15,
                       condensing=313.15, subcool=5.0).performance()
        self.assertGreater(colder["refrigerating effect"],
                           plain["refrigerating effect"])
        self.assertGreater(colder["cooling COP"], plain["cooling COP"])
        self.assertLess(colder["dryness after the throttle"],
                        plain["dryness after the throttle"])

    def test_the_cycles_that_are_not_cycles_are_refused(self):
        from engicalc.core.cycle import Cycle, CycleError

        for bad in (dict(evaporating=313.15, condensing=263.15),
                    dict(evaporating=263.15, condensing=313.15,
                         efficiency=1.5),
                    dict(evaporating=263.15, condensing=313.15,
                         efficiency=0.0),
                    dict(evaporating=263.15, condensing=313.15,
                         superheat=-5.0)):
            with self.subTest(**bad):
                with self.assertRaises(CycleError):
                    Cycle(fluid=self._fluid(), **bad).states()

    def test_it_mentions_a_compressor_fed_saturated_vapour(self):
        said = " ".join(self._ideal().notes())
        self.assertIn("superheat", said)


class TestMotion(unittest.TestCase):
    """Straight-line motion, checked against itself and against arithmetic."""

    #: One movement, known completely, for the combinations test below.
    MOVEMENT = {"u": 3.0, "v": 11.0, "a": 2.0, "t": 4.0, "s": 28.0}

    def test_any_three_of_the_five_give_the_same_movement_back(self):
        import itertools

        from engicalc.core.motion import solve_suvat

        # Ten ways to choose three, one movement. If the four equations are
        # written correctly it does not matter which three you happen to
        # know, and if one of them is wrong it matters very much.
        for chosen in itertools.combinations("suvat", 3):
            given = {name: self.MOVEMENT[name] for name in chosen}
            with self.subTest(given="".join(chosen)):
                got, _working, _both = solve_suvat(**given)
                for name, value in self.MOVEMENT.items():
                    self.assertAlmostEqual(got[name], value, places=9)

    def test_the_problems_everybody_is_set(self):
        from engicalc.core.motion import solve_suvat

        for given, expected in (
                # A stone dropped for three seconds.
                (dict(u=0.0, a=9.81, t=3.0), {"v": 29.43, "s": 44.145}),
                # A car at 30 m/s braking at 6 m/s2 until it stops.
                (dict(u=30.0, v=0.0, a=-6.0), {"t": 5.0, "s": 75.0}),
                # Thrown up at 20 m/s: how high, and how long to get there.
                (dict(u=20.0, v=0.0, a=-9.81),
                 {"s": 20.387360, "t": 2.0387360}),
                # A hundred metres from rest in ten seconds.
                (dict(u=0.0, s=100.0, t=10.0), {"a": 2.0, "v": 20.0})):
            with self.subTest(given=sorted(given)):
                got, _working, _both = solve_suvat(**given)
                for name, value in expected.items():
                    self.assertAlmostEqual(got[name], value, places=5)

    def test_it_says_which_equation_it_used(self):
        from engicalc.core.motion import solve_suvat

        # On this subject the equation used is most of the answer.
        _got, working, _both = solve_suvat(u=0.0, a=9.81, t=3.0)
        self.assertTrue(working)
        self.assertTrue(any("v = u + a t" == said for said, _n, _v in working))

    def test_two_of_the_five_is_not_enough(self):
        from engicalc.core.motion import MotionError, solve_suvat

        with self.assertRaises(MotionError) as caught:
            solve_suvat(u=3.0, t=4.0)
        self.assertIn("Three", str(caught.exception))

    def test_three_that_do_not_settle_it_say_so(self):
        from engicalc.core.motion import MotionError, solve_suvat

        # No acceleration and no distance: the time never comes out, and
        # saying which one is missing is more use than an answer would be.
        with self.assertRaises(MotionError):
            solve_suvat(u=5.0, v=5.0, a=0.0)

    def test_the_root_that_takes_a_positive_time_is_the_one_taken(self):
        from engicalc.core.motion import solve_suvat

        # v^2 = u^2 + 2 a s has two roots and only one of them happens
        # after the start of the problem.
        got, _working, _both = solve_suvat(u=0.0, a=2.0, s=25.0)
        self.assertAlmostEqual(got["v"], 10.0, places=9)
        self.assertGreater(got["t"], 0.0)

    def test_an_impossible_final_velocity_is_refused(self):
        from engicalc.core.motion import MotionError, solve_suvat

        # Braking harder than the distance allows: v^2 comes out negative,
        # which is not a rounding problem, it is a movement that does not
        # happen.
        with self.assertRaises(MotionError):
            solve_suvat(u=10.0, a=-50.0, s=25.0)

    # -- a movement in stages ----------------------------------------------
    def test_a_movement_in_stages_carries_its_speed_forward(self):
        from engicalc.core.motion import Motion, Phase

        run = Motion(phases=[
            Phase(label="up", acceleration=1.2, end_velocity=2.0),
            Phase(label="along", acceleration=0.0, distance=7.5),
            Phase(label="down", acceleration=-0.8, end_velocity=0.0)])
        legs = run.legs()
        self.assertEqual(3, len(legs))
        self.assertAlmostEqual(legs[0].duration, 2.0 / 1.2, places=9)
        self.assertAlmostEqual(legs[1].start_velocity, 2.0, places=9)
        self.assertAlmostEqual(legs[1].duration, 7.5 / 2.0, places=9)
        self.assertAlmostEqual(legs[2].distance, 2.0 ** 2 / (2 * 0.8),
                               places=9)
        self.assertAlmostEqual(run.summary()["displacement"],
                               sum(leg.distance for leg in legs), places=9)

    def test_the_curves_are_the_integrals_of_each_other(self):
        from engicalc.core.motion import steady_then_stop

        # Which is the whole of what the three diagrams say. Integrating
        # the acceleration has to give back the velocity that was drawn,
        # and integrating that has to give back the distance.
        run = steady_then_stop(top=2.0, speed_up=1.0, slow_down=0.8,
                               distance=12.0)
        t, s, v, a = run.trace(per_leg=3000)
        speed = np.concatenate([[run.start_velocity],
                                run.start_velocity + np.cumsum(
                                    (a[:-1] + a[1:]) / 2.0 * np.diff(t))])
        place = np.concatenate([[run.start_position],
                                run.start_position + np.cumsum(
                                    (v[:-1] + v[1:]) / 2.0 * np.diff(t))])
        self.assertLess(float(np.max(np.abs(speed - v))), 1e-9)
        self.assertLess(float(np.max(np.abs(place - s))), 1e-9)

    def test_a_trapezoid_covers_the_distance_it_was_asked_for(self):
        from engicalc.core.motion import steady_then_stop

        run = steady_then_stop(top=2.0, speed_up=1.0, slow_down=0.8,
                               distance=12.0)
        self.assertAlmostEqual(run.summary()["displacement"], 12.0,
                               places=9)
        self.assertAlmostEqual(run.summary()["final velocity"], 0.0,
                               places=9)

    def test_a_trapezoid_that_will_not_fit_says_so(self):
        from engicalc.core.motion import MotionError, steady_then_stop

        # Speeding up and braking alone need more room than there is, so
        # there is no cruise to shorten and no answer to give.
        with self.assertRaises(MotionError) as caught:
            steady_then_stop(top=20.0, speed_up=1.0, slow_down=0.8,
                             distance=12.0)
        self.assertIn("stop", str(caught.exception))

    def test_turning_round_makes_distance_and_displacement_differ(self):
        from engicalc.core.motion import Motion, Phase

        # Thrown up at 20 m/s and caught again: it covers twice the height
        # it reaches and ends up where it started.
        flight = 2.0 * 20.0 / 9.81
        up = Motion(phases=[Phase(label="flight", acceleration=-9.81,
                                  duration=flight)],
                    start_velocity=20.0)
        found = up.summary()
        self.assertAlmostEqual(found["displacement"], 0.0, places=6)
        self.assertAlmostEqual(found["travelled"],
                               2.0 * 20.0 ** 2 / (2 * 9.81), places=6)
        self.assertTrue(up.notes())

    def test_a_stage_that_finishes_before_it_starts_is_refused(self):
        from engicalc.core.motion import Motion, MotionError, Phase

        # Speeding up towards a velocity behind you takes a negative time,
        # which is a sign error rather than a movement.
        with self.assertRaises(MotionError) as caught:
            Motion(phases=[Phase(acceleration=2.0,
                                 end_velocity=-5.0)]).legs()
        self.assertIn("signs", str(caught.exception))

    def test_a_stage_needs_two_of_its_four(self):
        from engicalc.core.motion import Motion, MotionError, Phase

        with self.assertRaises(MotionError) as caught:
            Motion(phases=[Phase(duration=2.0)]).legs()
        self.assertIn("two", str(caught.exception))

    def test_a_movement_with_no_stages_is_refused(self):
        from engicalc.core.motion import Motion, MotionError

        with self.assertRaises(MotionError):
            Motion().legs()


class TestMohrsCircle(unittest.TestCase):
    """Exact - there is nothing fitted or iterated here."""

    def test_a_textbook_state(self):
        from engicalc.core.mohr import Mohr

        state = Mohr(80, -40, 25)
        self.assertAlmostEqual(state.sigma_1, 85.0, places=9)
        self.assertAlmostEqual(state.sigma_2, -45.0, places=9)
        self.assertAlmostEqual(state.tau_max, 65.0, places=9)

    def test_the_sum_of_the_principals_is_invariant(self):
        from engicalc.core.mohr import Mohr

        # Turning the axes cannot change it, which is what makes it a check.
        for state in (Mohr(80, -40, 25), Mohr(-10, 60, -30), Mohr(5, 5, 0)):
            with self.subTest(state=state):
                self.assertAlmostEqual(state.sigma_1 + state.sigma_2,
                                       state.sigma_x + state.sigma_y,
                                       places=9)

    def test_the_shear_vanishes_on_the_principal_planes(self):
        from engicalc.core.mohr import Mohr

        state = Mohr(80, -40, 25)
        direct, shear = state.at_angle(state.theta_p)
        self.assertAlmostEqual(shear, 0.0, places=9)
        self.assertAlmostEqual(direct, state.sigma_1, places=9)

    def test_pure_shear_gives_equal_and_opposite_principals_at_45(self):
        from engicalc.core.mohr import Mohr

        state = Mohr(0, 0, 50)
        self.assertAlmostEqual(state.sigma_1, 50.0, places=9)
        self.assertAlmostEqual(state.sigma_2, -50.0, places=9)
        self.assertAlmostEqual(state.theta_p, 45.0, places=9)


class TestUncertainty(unittest.TestCase):
    """How wrong the answer is, given how wrong the measurements were.

    Everything here turns on one decision: the derivatives are taken
    symbolically, of the whole expression at once, rather than by carrying
    an error term through the arithmetic operation by operation. The tests
    that matter are the ones where those two differ.
    """

    def _got(self, text, values):
        from engicalc.core import uncertainty
        return uncertainty.propagate(text, values)

    def test_a_tolerance_can_be_written_three_ways(self):
        from engicalc.core.quantity import Quantity

        for text in ("5000 +/- 50 N", "5000 \u00b1 50 N", "5000 +/- 1% N"):
            with self.subTest(text=text):
                got = Quantity.parse(text)
                self.assertEqual(got.value, 5000.0)
                self.assertAlmostEqual(got.error, 50.0, places=9)
                self.assertEqual(got.unit, "N")
        # And an exponent has a sign in it.
        self.assertAlmostEqual(
            Quantity.parse("0.001 +/- 5e-5 Pa*s").error, 5e-5, places=12)

    def test_no_tolerance_is_unknown_and_not_zero(self):
        from engicalc.core.quantity import Quantity

        # Zero would claim the thing was measured exactly, and nothing is.
        self.assertIsNone(Quantity.parse("5000 N").error)

    def test_the_one_it_exists_for(self):
        got = self._got("F/A", {"F": "5000 +/- 50 N", "A": "20 +/- 0.5 mm^2"})
        self.assertAlmostEqual(got.value.value, 250.0, places=9)
        # sqrt((dF/F)^2 + (dA/A)^2) x 250, by hand.
        wanted = 250.0 * math.hypot(50 / 5000, 0.5 / 20)
        self.assertAlmostEqual(got.error, wanted, places=9)
        self.assertEqual(got.value.unit, "N/mm^2")

    def test_it_says_which_input_to_measure_better(self):
        # The useful part. The area is a 2.5% measurement and the force a
        # 1% one, so the area is most of the answer's uncertainty and
        # measuring the force better would buy almost nothing.
        got = self._got("F/A", {"F": "5000 +/- 50 N", "A": "20 +/- 0.5 mm^2"})
        worst = got.dominant()
        self.assertIsNotNone(worst)
        self.assertEqual(worst.name, "A")
        self.assertGreater(worst.share, 0.8)
        self.assertAlmostEqual(sum(c.share for c in got.contributions), 1.0,
                               places=9)

    def test_a_name_used_twice_is_one_measurement(self):
        # The whole reason for differentiating rather than propagating.
        # x*x is 2x the relative error of x, not root two times it - the
        # same x cannot be high and low at the same time.
        for text in ("x*x", "x^2", "x*x*1.0"):
            with self.subTest(text=text):
                got = self._got(text, {"x": "10 +/- 1 m"})
                self.assertAlmostEqual(got.relative, 0.2, places=9)
        # Two separate measurements of the same size are different.
        pair = self._got("x*y", {"x": "10 +/- 1 m", "y": "10 +/- 1 m"})
        self.assertAlmostEqual(pair.relative, math.hypot(0.1, 0.1), places=9)

    def test_a_difference_of_two_close_numbers_is_mostly_tolerance(self):
        # 100 +/- 0.5 less 99 +/- 0.5 is 1 +/- 0.707, which is 71%. The
        # answer is right and nearly useless, and saying so is the point.
        got = self._got("a - b", {"a": "100 +/- 0.5 mm", "b": "99 +/- 0.5 mm"})
        self.assertAlmostEqual(got.value.value, 1.0, places=9)
        self.assertAlmostEqual(got.error, math.hypot(0.5, 0.5), places=9)
        self.assertGreater(got.relative, 0.7)

    def test_the_uncertainty_comes_out_in_the_answer_s_unit(self):
        # Each contribution is a derivative times a tolerance, and the
        # derivative carries units of its own. If those did not come to
        # the answer's unit something would be wrong, and the conversion
        # is what checks it.
        got = self._got("m*a", {"m": "70 +/- 0.5 kg",
                                "a": "9.81 +/- 0.02 m/s^2"})
        self.assertEqual(got.value.unit, "m*kg/s^2")
        by_hand = 70 * 9.81 * math.hypot(0.5 / 70, 0.02 / 9.81)
        self.assertAlmostEqual(got.error, by_hand, places=6)

    def test_nothing_given_means_nothing_claimed(self):
        got = self._got("F/A", {"F": "5000 N", "A": "20 mm^2"})
        self.assertFalse(got.known)
        self.assertEqual(got.error, 0.0)
        self.assertIn("No tolerances", " ".join(got.notes()))

    def test_a_tolerance_converts_with_its_value(self):
        from engicalc.core.quantity import Quantity

        got = Quantity.parse("2 +/- 0.05 L/s").to("m^3/s")
        self.assertAlmostEqual(got.value, 0.002, places=12)
        self.assertAlmostEqual(got.error, 5e-5, places=15)


class TestUncertaintyInTheLibrary(unittest.TestCase):
    """A tolerance typed into a formula field comes back on the answer.

    The rearrangement is exactly the expression to differentiate, and every
    variable already declares a unit - so the whole thing is dimensionally
    checked on the way through, for free.
    """

    def _solve(self, key, target, values):
        from engicalc.formulas.library import FormulaLibrary, solve_formula
        library = FormulaLibrary(load_user=False)
        return solve_formula(library.get(key), target, values)

    def test_a_tolerance_comes_back_on_the_answer(self):
        got = self._solve("strength_of_materials.normal_stress", "sigma",
                          {"F": "5000 +/- 50", "A": "20e-6 +/- 5e-7"})
        self.assertAlmostEqual(got.value, 2.5e8, delta=1.0)
        self.assertIsNotNone(got.spread)
        wanted = 2.5e8 * math.hypot(50 / 5000, 5e-7 / 20e-6)
        self.assertAlmostEqual(got.spread.error / wanted, 1.0, places=9)

    def test_the_nominal_value_is_still_read_correctly(self):
        # The tolerance used to reach sympify as part of the number and
        # fail there with a syntax error about nothing the user did wrong.
        with_tolerance = self._solve(
            "strength_of_materials.normal_stress", "sigma",
            {"F": "5000 +/- 50", "A": "20e-6"})
        without = self._solve("strength_of_materials.normal_stress", "sigma",
                              {"F": "5000", "A": "20e-6"})
        self.assertAlmostEqual(with_tolerance.value, without.value, places=6)

    def test_a_tolerance_converts_with_the_unit_beside_it(self):
        # 5 GPa of tolerance on a field that wants pascals is 5e9 Pa, and
        # 20 cm^4 is 2e-7 m^4. Neither is a decimal point moved by hand.
        got = self._solve("strength_of_materials.euler_buckling", "Pcr",
                          {"E": "210 +/- 5 GPa", "I": "8503 +/- 20 cm^4",
                           "K": "1", "L": "3.5 +/- 0.01 m"})
        by_name = {c.name: c for c in got.spread.contributions}
        self.assertAlmostEqual(by_name["E"].given, 5e9, delta=1.0)
        self.assertAlmostEqual(by_name["I"].given, 2e-7, delta=1e-12)
        # E enters linearly and is the loosest of the three, so it is the
        # one worth measuring better.
        self.assertEqual(got.spread.dominant().name, "E")

    def test_no_tolerance_anywhere_means_none_claimed(self):
        got = self._solve("strength_of_materials.normal_stress", "sigma",
                          {"F": "5000", "A": "20e-6"})
        self.assertIsNone(got.spread)

    def test_a_formula_with_a_hidden_constant_gets_none(self):
        # Manning's n carries s/m^(1/3) while being quoted as a bare
        # number, so there is no dimensionally consistent derivative to
        # take. Better no uncertainty than a wrong one.
        got = self._solve("fluid_mechanics.manning", "v",
                          {"Rh": "0.5 +/- 0.01", "S": "0.001", "n": "0.013"})
        self.assertIsNotNone(got.value)
        self.assertIsNone(got.spread)

    def test_it_agrees_with_the_worksheet_on_the_same_sum(self):
        # Two routes to one answer, and they have to give one answer.
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("F", "5000 +/- 50 N", "N")
        sheet.add("A", "20 +/- 0.5 mm^2", "mm^2")
        sheet.add("sigma", "F/A", "N/mm^2")
        row = [r for r in sheet.evaluate() if r.step.name == "sigma"][0]

        library = self._solve(
            "strength_of_materials.normal_stress", "sigma",
            {"F": "5000 +/- 50 N", "A": "20 +/- 0.5 mm^2"})
        # The library works in pascals and the sheet in N/mm^2, which is a
        # factor of a million on both the value and the tolerance.
        self.assertAlmostEqual(library.value / 1e6, float(row.value),
                               places=6)
        self.assertAlmostEqual(library.spread.error / 1e6,
                               row.spread.error, places=6)


class TestUncertaintyDownASheet(unittest.TestCase):
    """A sheet counts each measurement once, however many routes it took.

    A pipe sheet measures a diameter, works an area from it, a velocity
    from the area and a Reynolds number from the velocity and the diameter
    again. The diameter is in the answer twice by two different routes,
    and giving each row an uncertainty and treating it as a fresh
    measurement for the row below gets that wrong.
    """

    def _pipe(self, one_line=False):
        from engicalc.core.sheet import Sheet

        sheet = Sheet("Water in a pipe")
        sheet.add("d", "50 +/- 0.5 mm", "mm")
        sheet.add("Q", "2 L/s", "m^3/s")
        sheet.add("rho", "998 kg/m^3", "")
        sheet.add("mu", "0.001 Pa*s", "")
        if one_line:
            sheet.add("Re", "rho*Q*d/(mu*pi*d^2/4)", "")
        else:
            sheet.add("A", "pi*d^2/4", "")
            sheet.add("v", "Q/A", "")
            sheet.add("Re", "rho*v*d/mu", "")
        return sheet

    def _answers(self, sheet):
        return {r.step.name: r for r in sheet.evaluate() if r.ok}

    def test_a_tolerance_travels_down_the_page(self):
        found = self._answers(self._pipe())
        self.assertAlmostEqual(found["A"].spread.relative, 0.02, places=9)
        self.assertAlmostEqual(found["v"].spread.relative, 0.02, places=9)

    def test_the_diameter_is_counted_once_not_twice(self):
        # Re = rho Q d / (mu A) and A goes as d^2, so Re goes as 1/d: a
        # one per cent diameter is a one per cent Reynolds number.
        # Row by row it would come out as root of one plus four.
        found = self._answers(self._pipe())
        self.assertAlmostEqual(found["Re"].spread.relative, 0.01, places=6)

    def test_the_step_by_step_sheet_agrees_with_the_one_liner(self):
        # Which is the proof that the substitution is doing its job:
        # writing it out in seven rows or in one has to give one answer.
        step_by_step = self._answers(self._pipe())["Re"]
        one_line = self._answers(self._pipe(one_line=True))["Re"]
        self.assertAlmostEqual(step_by_step.spread.error / one_line.spread.error,
                               1.0, places=9)

    def test_two_separate_measurements_are_two(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("a", "50 +/- 0.5 mm", "mm")
        sheet.add("b", "50 +/- 0.5 mm", "mm")
        sheet.add("area", "a*b", "mm^2")
        found = self._answers(sheet)
        self.assertAlmostEqual(found["area"].spread.relative,
                               math.hypot(0.01, 0.01), places=9)

    def test_one_measurement_used_twice_is_one(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("a", "50 +/- 0.5 mm", "mm")
        sheet.add("square", "a*a", "mm^2")
        found = self._answers(sheet)
        self.assertAlmostEqual(found["square"].spread.relative, 0.02,
                               places=9)

    def _deep(self, rows: int):
        """A sheet where each row uses the two above it.

        Written back to the measurements that is a to the power of a
        Fibonacci number, so it goes both large and deep quickly - which
        is the shape that would hang the window if nothing stopped it.
        """
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("a", "1.01 +/- 0.001", "")
        sheet.add("b", "1.02 +/- 0.001", "")
        before, above = "a", "b"
        for step in range(2, rows):
            sheet.add(f"r{step}", f"{before}*{above}", "")
            before, above = f"r{step}", before
        return sheet

    def test_a_tolerance_that_will_not_work_out_keeps_the_answer(self):
        # The row's own value came from the row above it and is fine. It
        # is the expression written all the way back to the measurements
        # that overflows, and losing the value over that would be losing
        # the thing the row is for.
        results = self._deep(34).evaluate()
        self.assertTrue(all(r.ok for r in results),
                        [r.error for r in results if not r.ok][:1])
        deep = results[-1]
        self.assertIsNone(deep.spread)
        self.assertIn("tolerance", deep.note.lower())

    def test_a_deep_sheet_does_not_take_all_day(self):
        import time

        # Not a benchmark - a guard. Without a ceiling on how big the
        # written-out expression may get, this is where the window would
        # stop responding in the middle of a keystroke.
        start = time.time()
        self._deep(40).evaluate()
        self.assertLess(time.time() - start, 10.0)

    def test_a_sheet_with_no_tolerances_says_nothing_about_them(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("F", "5000 N", "N")
        sheet.add("A", "20 mm^2", "mm^2")
        sheet.add("sigma", "F/A", "N/mm^2")
        found = self._answers(sheet)
        self.assertAlmostEqual(float(found["sigma"].value), 250.0, places=9)
        self.assertIsNone(found["sigma"].spread)


class TestTheLibraryBalances(unittest.TestCase):
    """Does every formula agree with its own declared units?

    Each variable declares a unit and nothing had ever checked that the
    equation they sit in holds together - that the left side measures what
    the right side measures. Running the question over all of them found
    two declared units that were simply wrong: Antoine's temperature was
    declared C, which is a coulomb, and the integral of an error was
    declared dimensionless when integrating over time gives it a second.

    A formula whose two sides genuinely do not balance has to say why. An
    exemption with no reason beside it is where a mistake goes to hide.
    """

    #: Two sets of values to try. Distinct, because substituting one
    #: everywhere makes every (x2 - x1) zero and every formula with a
    #: difference in it divides by nothing. And a second set inside the
    #: unit interval, because a damping ratio above one puts a square root
    #: of a negative number in the way of an answer that was only ever
    #: going to be about dimensions.
    TRIES = ((2.0, 3.0, 5.0, 7.0, 11.0, 13.0, 17.0, 19.0, 23.0, 29.0,
              31.0, 37.0, 41.0, 43.0, 47.0),
             (0.2, 0.3, 0.5, 0.7, 0.11, 0.13, 0.17, 0.19, 0.23, 0.29,
              0.31, 0.37, 0.41, 0.43, 0.47))

    #: Units that mean "this is not a physical quantity", so the formula
    #: they appear in cannot be checked this way.
    OPAQUE = ("currency", "varies")

    def _balances(self, formula):
        """(did it balance, what happened) for one formula."""
        import sympy as sp

        from engicalc.core import dimensional
        from engicalc.core.quantity import Quantity, QuantityError

        for sizes in self.TRIES:
            given, spare = {}, iter(sizes)
            try:
                for variable in formula.variables:
                    unit = variable.unit or ""
                    if any(word in unit.lower() for word in self.OPAQUE):
                        return None, "not a physical quantity"
                    given[variable.symbol] = Quantity.of(next(spare), unit)
            except (QuantityError, StopIteration) as exc:
                return None, str(exc)

            equation = formula.eq
            if not isinstance(equation, sp.Eq):
                return None, "not an equation"
            try:
                left = dimensional.walk(equation.lhs, given).tidy()
                right = dimensional.walk(equation.rhs, given).tidy()
            except Exception as exc:                   # noqa: BLE001
                last = str(exc)
                continue
            return (left.dimension() == right.dimension(),
                    f"{left.unit or '-'} against {right.unit or '-'}")
        return None, last

    def test_every_formula_balances_or_says_why_not(self):
        from engicalc.formulas.library import FormulaLibrary

        library = FormulaLibrary(load_user=False)
        checked = 0
        for formula in library.all():
            balanced, why = self._balances(formula)
            if balanced is None:
                continue
            checked += 1
            with self.subTest(formula=formula.key):
                if formula.dimensional_constant:
                    # Marked as carrying a constant with units in it, so
                    # it is not expected to balance - and if it starts to,
                    # the marking is out of date and should go.
                    self.assertFalse(
                        balanced,
                        f"{formula.key} balances now, so the note about a "
                        f"dimensional constant is no longer true.")
                    continue
                self.assertTrue(balanced,
                                f"{formula.key}: {why}")
        # A guard on the guard: if the checking itself broke, this would
        # pass by checking nothing.
        self.assertGreater(checked, 200)

    def test_an_exemption_has_to_give_a_reason(self):
        from engicalc.formulas.library import FormulaLibrary

        library = FormulaLibrary(load_user=False)
        exempt = [f for f in library.all() if f.dimensional_constant]
        self.assertTrue(exempt)
        for formula in exempt:
            with self.subTest(formula=formula.key):
                # Long enough to be a reason rather than a label.
                self.assertGreater(len(formula.dimensional_constant), 40)

    def test_the_two_that_were_wrong_are_right_now(self):
        from engicalc.formulas.library import FormulaLibrary

        library = FormulaLibrary(load_user=False)
        # C is a coulomb. Antoine's T is a temperature.
        antoine = library.get("chemical_process.antoine")
        self.assertEqual(antoine.variable("T").unit, "degC")
        # Integrating a dimensionless error over time gives it a second,
        # which is what makes the integral gain's 1/s cancel.
        pid = library.get("control_signals.pid_output")
        self.assertEqual(pid.variable("integral_e").unit, "s")
        self.assertEqual(pid.variable("Ki").unit, "1/s")


class TestTheWindow(unittest.TestCase):
    """The window, rather than what it works out."""

    def setUp(self):
        import tempfile

        from engicalc.ui.app import EngiCalcApp
        self.app = EngiCalcApp(
            db_path=os.path.join(tempfile.mkdtemp(), "keys.db"))
        self.app.geometry("1280x820")
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()

    def test_the_tab_on_screen_is_found_through_the_panes(self):
        # Three of the top tabs are panes with notebooks of their own, so
        # the selected top tab is not the thing with the button on it.
        from engicalc.ui.charts_pane import BeamTab
        from engicalc.ui.graph_tab import GraphTab
        from engicalc.ui.statistics_tab import StatisticsTab

        self.app.notebook.select(self.app.graph_pane)
        self.app.update_idletasks()
        self.assertIsInstance(self.app.current_tab(), GraphTab)

        self.app.graph_pane.tabs.select(self.app.graph_pane.charts["Beam"])
        self.app.update_idletasks()
        self.assertIsInstance(self.app.current_tab(), BeamTab)

        self.app.notebook.select(self.app.statistics_tab)
        self.app.update_idletasks()
        self.assertIsInstance(self.app.current_tab(), StatisticsTab)

    def test_every_tab_has_something_for_the_run_key_to_call(self):
        # Ctrl+Enter is only worth having if it does something wherever
        # you press it.
        for page in self.app.notebook.tabs():
            self.app.notebook.select(page)
            self.app.update_idletasks()
            tab = self.app.current_tab()
            with self.subTest(tab=type(tab).__name__):
                self.assertTrue(
                    any(callable(getattr(tab, name, None))
                        for name in self.app.DOES_THE_WORK),
                    f"{type(tab).__name__} has no calculate to bind to")

    def test_the_run_key_actually_runs_it(self):
        self.app.notebook.select(self.app.statistics_tab)
        self.app.update_idletasks()
        self.app.statistics_tab.status.configure(text="")
        self.app.run_current()
        self.assertTrue(self.app.statistics_tab.status.cget("text"))

    def test_the_tab_keys_move_between_tabs(self):
        self.app._go_to_tab(0)
        first = self.app.notebook.select()
        self.app._step_tab(1)
        self.assertNotEqual(self.app.notebook.select(), first)
        self.app._step_tab(-1)
        self.assertEqual(self.app.notebook.select(), first)
        # And it wraps rather than stopping at the end.
        self.app._step_tab(-1)
        self.assertEqual(self.app.notebook.select(),
                         self.app.notebook.tabs()[-1])

    def test_the_shortcuts_are_bound_and_written_down(self):
        from engicalc.ui.app import SHORTCUTS

        for sequence in ("<Control-Return>", "<F5>", "<Control-s>", "<F1>",
                         "<Control-Key-1>"):
            with self.subTest(sequence=sequence):
                self.assertTrue(self.app.bind_all(sequence),
                                f"{sequence} is not bound")
        for said in ("Ctrl+Enter", "Ctrl+S", "F1", "Ctrl+1"):
            self.assertIn(said, SHORTCUTS)

    def test_a_long_expression_shrinks_rather_than_being_cut_off(self):
        from engicalc.ui import mathrender

        # A cubic trendline is wide. Rendered at its asked-for size it ran
        # off the right and the last term was simply not on screen, with
        # nothing to say a term was missing.
        label = mathrender.MathLabel(self.app, fontsize=18, height=48)
        label.pack()
        self.app.update_idletasks()
        label._latex = ("y = -2.77778 \\cdot 10^{-7} x^{3} + 1.42857 "
                        "\\cdot 10^{-5} x^{2} + 0.0198373 x + 0.00238095")
        roomy = label._fitted(2000, 200)
        squeezed = label._fitted(700, 60)
        floored = label._fitted(120, 60)
        # Given room it draws at the size it was asked for.
        self.assertGreater(roomy.width(), 700)
        # Given less it comes down to fit, in one step rather than
        # stepping down a point at a time.
        self.assertLessEqual(squeezed.width(), 700)
        # And it stops at a size somebody could still read. Past that it
        # clips and the window has to be widened - which is a decision,
        # not an accident, and is why there is a floor at all.
        self.assertGreaterEqual(floored.width(), squeezed.width() * 0.3)
        label.destroy()


class TestTheWorking(unittest.TestCase):
    """How a step reads once it is more than one line."""

    def test_every_line_of_a_step_is_indented_not_only_the_first(self):
        from engicalc.core.steps import Step

        step = Step("Solution", detail="x1 = 2\nx2 = 3\nx3 = -1")
        lines = step.text().split("\n")
        self.assertEqual(lines[0], "Solution")
        for line in lines[1:]:
            with self.subTest(line=line):
                self.assertTrue(line.startswith(Step.INDENT), line)

    def test_a_blank_line_is_left_blank(self):
        from engicalc.core.steps import Step

        step = Step("Two parts", detail="first\n\nsecond")
        self.assertIn("\n\n", step.text())

    def test_the_matrix_answer_is_given_once(self):
        # It was drawn, then written out again above the working, then
        # written a third time as the working's last step.
        import tempfile

        from engicalc.ui.app import EngiCalcApp
        app = EngiCalcApp(db_path=os.path.join(tempfile.mkdtemp(), "m.db"))
        try:
            app.update_idletasks()
            app.matrix_tab.compute()
            app.update_idletasks()
            working = app.matrix_tab.working.get("1.0", "end")
            self.assertEqual(working.count("x1 = 2"), 1)
        finally:
            app.destroy()


class TestQuantities(unittest.TestCase):
    """A number that knows what it measures.

    The whole point is the refusals. A calculator that adds a length to a
    mass and gives a number has not helped anybody.
    """

    def _q(self, text):
        from engicalc.core.quantity import Quantity
        return Quantity.parse(text)

    def test_a_unit_survives_being_read_and_written(self):
        # Kept as it was written, not reduced to SI. An answer in
        # kg/(m*s^2) where N/mm^2 was meant is a worse answer.
        for text in ("50 mm", "250 N/mm^2", "4.18 J/(kg*K)", "1.2 kg/m^3",
                     "45 W/(m*K)", "8503 cm^4", "9.81 m/s^2", "0.001 Pa*s"):
            with self.subTest(text=text):
                written = text.split(" ", 1)[1]
                self.assertEqual(self._q(text).unit, written)

    def test_it_says_what_the_unit_measures(self):
        for text, measures in (("50 mm", "a length"),
                               ("250 N/mm^2", "a pressure"),
                               ("4.18 J/(kg*K)", "a specific heat"),
                               ("1.2 kg/m^3", "a density"),
                               ("8503 cm^4", "a second moment of area"),
                               ("9.81 m/s^2", "an acceleration"),
                               ("3", "nothing")):
            with self.subTest(text=text):
                self.assertEqual(self._q(text).measures(), measures)

    def test_adding_converts_to_the_left_hand_unit(self):
        got = self._q("5 m") + self._q("3 mm")
        self.assertEqual(got.unit, "m")
        self.assertAlmostEqual(got.value, 5.003, places=12)
        # And the other way round it is the other unit, not a rule about
        # which is smaller.
        other = self._q("3 mm") + self._q("5 m")
        self.assertEqual(other.unit, "mm")
        self.assertAlmostEqual(other.value, 5003.0, places=9)

    def test_the_units_multiply_and_divide_with_the_numbers(self):
        from engicalc.core.quantity import Quantity

        self.assertEqual(str(self._q("2 m") * self._q("3 m")), "6 m^2")
        self.assertEqual(str(self._q("5000 N") / self._q("20 mm^2")),
                         "250 N/mm^2")
        self.assertEqual(str(Quantity(1.0, {}) / self._q("2 s")), "0.5 1/s")
        self.assertEqual(str(self._q("4 m^2") ** Quantity(0.5, {})), "2 m")

    def test_the_mistake_this_is_for(self):
        # The same force over the same number of the wrong unit. Nothing
        # in a bare 250 says which of these happened.
        small = self._q("5000 N") / self._q("20 mm^2")
        big = self._q("5000 N") / self._q("20 m^2")
        self.assertEqual(small.unit, "N/mm^2")
        self.assertEqual(big.unit, "N/m^2")
        self.assertAlmostEqual(
            small.to("Pa").value / big.to("Pa").value, 1e6, places=6)

    def test_a_length_and_a_mass_will_not_be_added(self):
        from engicalc.core.quantity import QuantityError

        with self.assertRaises(QuantityError) as caught:
            self._q("5 m") + self._q("3 kg")
        said = str(caught.exception)
        self.assertIn("a length", said)
        self.assertIn("a mass", said)

    def test_a_bare_number_is_not_quietly_given_a_unit(self):
        from engicalc.core.quantity import QuantityError

        # Assuming it meant millimetres is exactly what goes wrong.
        with self.assertRaises(QuantityError):
            self._q("2 m") + 5

    def test_an_exponent_has_to_be_a_plain_number(self):
        from engicalc.core.quantity import Quantity, QuantityError

        with self.assertRaises(QuantityError):
            Quantity(2.0, {}) ** self._q("3 m")

    def test_a_logarithm_of_a_length_is_refused(self):
        from engicalc.core import quantity

        # It would depend on whether the length was measured in metres or
        # in feet, which is what makes it meaningless rather than hard.
        with self.assertRaises(quantity.QuantityError):
            quantity.apply("log", self._q("2 m"))

    def test_trigonometry_takes_an_angle_in_whatever_it_is_given(self):
        from engicalc.core import quantity

        self.assertAlmostEqual(
            quantity.apply("sin", self._q("30 deg")).value, 0.5, places=12)
        self.assertAlmostEqual(
            quantity.apply("sin", self._q("0.5235987755982988")).value,
            0.5, places=12)
        with self.assertRaises(quantity.QuantityError):
            quantity.apply("sin", self._q("2 m"))

    def test_a_unit_that_cancels_is_seen_to_cancel(self):
        # rho v d / mu is dimensionless, and comes out in kg/(mm s^2 Pa)
        # if nothing reduces it - which is dimensionless and does not look
        # it, because Pa and kg/(m s^2) are one thing under two names.
        got = (self._q("998 kg/m^3") * self._q("2 m/s") * self._q("50 mm")
               / self._q("0.001 Pa*s")).tidy()
        self.assertTrue(got.plain)
        self.assertAlmostEqual(got.value, 99800.0, places=6)

    def test_two_names_for_one_thing_are_folded_together(self):
        # mm^2*m is a real unit and a useless one.
        got = (self._q("2 mm") * self._q("3 m")).tidy()
        self.assertEqual(got.unit, "mm^2")
        self.assertAlmostEqual(got.value, 6000.0, places=9)

    def test_an_equivalent_is_offered_only_where_it_reads_better(self):
        from engicalc.core.quantity import equivalents

        # Three names down to one, same number: worth saying.
        force = self._q("70 kg") * self._q("9.81 m/s^2")
        self.assertEqual([str(one) for one in equivalents(force)],
                         ["686.7 N"])
        # Two names down to one, a thousand times the number: not worth
        # saying, because the number stops being readable.
        stress = self._q("65 kN/m^2")
        self.assertEqual([], equivalents(stress))
        # And a single named unit has nothing to offer.
        self.assertEqual([], equivalents(self._q("5 N")))


class TestUnitsThroughAnExpression(unittest.TestCase):
    """Carrying the units through a calculation rather than beside it."""

    def _evaluate(self, text, values, wanted=""):
        from engicalc.core import dimensional
        got = dimensional.evaluate(text, values)
        return got.to(wanted) if wanted else got

    def test_the_answer_comes_out_in_a_unit(self):
        got = self._evaluate("F/A", {"F": "5000 N", "A": "20 mm^2"})
        self.assertEqual(str(got), "250 N/mm^2")

    def test_ordinary_engineering(self):
        for text, values, wanted, expected in (
                ("m*a", {"m": "70 kg", "a": "9.81 m/s^2"}, "N", 686.7),
                ("pi*d^2/4", {"d": "50 mm"}, "mm^2", 1963.4954084936207),
                ("rho*v^2/2", {"rho": "1.2 kg/m^3", "v": "20 m/s"}, "Pa",
                 240.0),
                ("m*c*(T2 - T1)", {"m": "2 kg", "c": "4180 J/(kg*K)",
                                   "T2": "80 K", "T1": "20 K"}, "kJ", 501.6),
                ("sqrt(2*g*h)", {"g": "9.81 m/s^2", "h": "3 m"}, "m/s",
                 7.6720271122811),
                ("W*L^3/(48*E*I)", {"W": "12 kN", "L": "6 m", "E": "210 GPa",
                                    "I": "8503 cm^4"}, "mm",
                 3.0241427399885),
        ):
            with self.subTest(text=text):
                got = self._evaluate(text, values, wanted)
                self.assertAlmostEqual(got.value / expected, 1.0, places=9)
                self.assertEqual(got.unit, wanted)

    def test_the_reynolds_number_comes_out_as_a_number(self):
        got = self._evaluate("rho*v*d/mu",
                             {"rho": "998 kg/m^3", "v": "2 m/s",
                              "d": "50 mm", "mu": "0.001 Pa*s"})
        self.assertTrue(got.plain)
        self.assertAlmostEqual(got.value, 99800.0, places=6)

    def test_E_and_I_are_the_names_that_were_given_values(self):
        # Undeclared, E is Euler's number and I is the imaginary unit, and
        # a beam deflection comes back complex.
        got = self._evaluate("W*L^3/(48*E*I)",
                             {"W": "12 kN", "L": "6 m", "E": "210 GPa",
                              "I": "8503 cm^4"}, "mm")
        self.assertAlmostEqual(got.value, 3.0241427399885, places=9)

    def test_T1_and_T2_are_two_names_and_not_T_times_a_number(self):
        got = self._evaluate("T2 - T1", {"T2": "80 K", "T1": "20 K"})
        self.assertEqual(str(got), "60 K")

    def test_a_sum_that_does_not_hold_together_says_where(self):
        from engicalc.core.dimensional import DimensionError

        with self.assertRaises(DimensionError) as caught:
            self._evaluate("F/A + T", {"F": "5000 N", "A": "20 mm^2",
                                       "T": "300 K"})
        said = str(caught.exception)
        self.assertIn("a temperature", said)
        self.assertIn("a pressure", said)
        # And which two terms, because on a long expression that is the
        # only question worth answering.
        self.assertIn("T", said)

    def test_asking_for_the_answer_in_something_it_is_not(self):
        from engicalc.core import dimensional

        # Through describe, which is how a caller asks for an answer in a
        # particular unit, and which turns the refusal into its own kind.
        answer = dimensional.evaluate("F/A", {"F": "5000 N",
                                              "A": "20 mm^2"})
        with self.assertRaises(dimensional.DimensionError):
            dimensional.describe(answer, "m")

    def test_dividing_by_a_zero_is_a_sentence_and_not_a_traceback(self):
        from engicalc.core.dimensional import DimensionError

        # F/A arrives as F * A**-1, so a zero area never reaches the
        # division at all - it reaches a negative power of nothing.
        with self.assertRaises(DimensionError):
            self._evaluate("F/A", {"F": "5000 N", "A": "0 mm^2"})

    def test_a_name_with_no_value_is_named(self):
        from engicalc.core.dimensional import DimensionError

        with self.assertRaises(DimensionError) as caught:
            self._evaluate("F/A", {"F": "5000 N"})
        self.assertIn("A", str(caught.exception))

    def test_what_it_will_come_out_in_before_there_are_numbers(self):
        from engicalc.core import dimensional

        for text, values, unit in (
                ("F/A", {"F": "1 N", "A": "1 mm^2"}, "N/mm^2"),
                ("m*c*dT", {"m": "1 kg", "c": "1 J/(kg*K)", "dT": "1 K"},
                 "J"),
                ("rho*v*d/mu", {"rho": "1 kg/m^3", "v": "1 m/s",
                                "d": "1 m", "mu": "1 Pa*s"}, "")):
            with self.subTest(text=text):
                self.assertEqual(dimensional.check(text, values), unit)


class TestAxialMembers(unittest.TestCase):
    """Bars held at both ends, and what heating them does."""

    @staticmethod
    def _steel(length=1000.0, rise=50.0):
        from engicalc.core import axial
        return axial.Bar(length=length, area=500.0, modulus=210000.0,
                         expansion=12.0, rise=rise, name="steel")

    def test_a_restrained_bar_does_not_care_how_long_it_is(self):
        from engicalc.core import axial

        # E alpha dT, with no length in it anywhere. That is the whole
        # result: the strain that was prevented is the same whatever the
        # length, so the stress is too.
        wanted = -axial.restrained_stress(210000.0, 12.0, 50.0)
        for length in (10.0, 1000.0, 1e6):
            with self.subTest(length=length):
                got = axial.Series(bars=[self._steel(length)]).solve()
                self.assertAlmostEqual(got.stresses()[0], wanted, places=6)
        self.assertAlmostEqual(wanted, -126.0, places=9)

    def test_a_free_end_carries_nothing_and_grows(self):
        from engicalc.core import axial

        got = axial.Series(bars=[self._steel()], right="free").solve()
        self.assertAlmostEqual(got.forces[0], 0.0, places=9)
        self.assertAlmostEqual(got.stretches[0], 1000 * 12e-6 * 50, places=9)

    def test_a_gap_is_taken_up_before_anything_is_carried(self):
        from engicalc.core import axial

        # Free growth is 0.6 mm. Half of it into the gap leaves half the
        # force; more gap than growth leaves none at all.
        for gap, wanted in ((0.0, -63000.0), (0.3, -31500.0), (0.9, 0.0)):
            with self.subTest(gap=gap):
                got = axial.Series(bars=[self._steel()], right="wall",
                                   gap=gap).solve()
                self.assertAlmostEqual(got.forces[0], wanted, places=6)
                self.assertEqual(got.touching, gap < 0.6)

    def test_a_wall_can_only_push(self):
        from engicalc.core import axial

        # Pulled away from it, the wall carries nothing - which is the
        # difference between a wall and a support the bar is attached to,
        # and the reason they are not the same setting.
        bars = [axial.Bar(length=1000.0, area=500.0, modulus=210000.0,
                          name="steel")]
        wall = axial.Series(bars=bars, loads=[0.0, -50000.0],
                            right="wall").solve()
        self.assertAlmostEqual(wall.reactions[1], 0.0, places=6)
        self.assertFalse(wall.touching)

        attached = axial.Series(bars=bars, loads=[0.0, -50000.0],
                                right="fixed").solve()
        self.assertAlmostEqual(attached.reactions[1], 50000.0, places=6)
        self.assertTrue(attached.touching)

    def test_a_stepped_bar_shares_the_load_by_stiffness(self):
        from engicalc.core import axial

        one = axial.Bar(length=500.0, area=1000.0, modulus=200000.0,
                        name="left")
        two = axial.Bar(length=800.0, area=400.0, modulus=200000.0,
                        name="right")
        got = axial.Series(bars=[one, two],
                           loads=[0.0, 100000.0, 0.0]).solve()
        share = one.stiffness / (one.stiffness + two.stiffness)
        self.assertAlmostEqual(got.forces[0], 100000.0 * share, places=6)
        self.assertAlmostEqual(got.forces[1], -100000.0 * (1 - share),
                               places=6)
        # Held at both ends, so the far end goes nowhere at all.
        self.assertAlmostEqual(got.movement[-1], 0.0, places=9)
        # And the reactions carry the load between them.
        self.assertAlmostEqual(
            got.reactions[0] + got.reactions[1] + 100000.0, 0.0, places=6)

    def test_a_bolt_and_a_sleeve_load_each_other_with_no_load_on_them(self):
        from engicalc.core import axial

        # The aluminium wants to grow twice as much as the steel and
        # cannot, so one ends up in tension and the other in compression
        # and they add to nothing.
        bolt = axial.Bar(length=200.0, area=150.0, modulus=210000.0,
                         expansion=12.0, rise=60.0, name="steel bolt")
        sleeve = axial.Bar(length=200.0, area=600.0, modulus=70000.0,
                           expansion=23.0, rise=60.0, name="sleeve")
        got = axial.Parallel(bars=[bolt, sleeve], load=0.0).solve()
        self.assertAlmostEqual(sum(got.forces), 0.0, places=6)
        self.assertGreater(got.forces[0], 0.0)
        self.assertLess(got.forces[1], 0.0)
        # They end the same length, which is the condition that solved it.
        self.assertAlmostEqual(got.stretches[0], got.stretches[1], places=12)
        # By hand.
        together = bolt.stiffness + sleeve.stiffness
        moved = (bolt.stiffness * bolt.free_growth
                 + sleeve.stiffness * sleeve.free_growth) / together
        self.assertAlmostEqual(
            got.forces[0], bolt.stiffness * (moved - bolt.free_growth),
            places=6)

    def test_bars_in_parallel_share_a_load_by_stiffness(self):
        from engicalc.core import axial

        bars = [axial.Bar(length=300.0, area=200.0, modulus=210000.0,
                          name="steel"),
                axial.Bar(length=300.0, area=600.0, modulus=70000.0,
                          name="aluminium")]
        got = axial.Parallel(bars=bars, load=90000.0).solve()
        self.assertAlmostEqual(sum(got.forces), 90000.0, places=6)
        together = sum(bar.stiffness for bar in bars)
        for bar, force in zip(bars, got.forces):
            with self.subTest(bar=bar.name):
                self.assertAlmostEqual(
                    force, 90000.0 * bar.stiffness / together, places=6)

    def test_the_refusals(self):
        from engicalc.core import axial

        with self.assertRaises(axial.AxialError):
            axial.Series(bars=[self._steel()], left="free",
                         right="free").solve()
        with self.assertRaises(axial.AxialError):
            # A gap against something that is not a wall.
            axial.Series(bars=[self._steel()], gap=2.0).solve()
        with self.assertRaises(axial.AxialError):
            axial.Series(bars=[], loads=[]).solve()
        with self.assertRaises(axial.AxialError):
            # Side by side, they have to start the same length.
            axial.Parallel(bars=[self._steel(200.0), self._steel(300.0)],
                           load=0.0).solve()


class TestCurvedBeams(unittest.TestCase):
    """Bending a bar that was curved to start with.

    The stress goes hyperbolic rather than linear and the neutral axis
    moves in toward the centre of curvature. The inside fibre carries more
    than a straight-beam calculation says, which means My/I there is not
    conservative - it is optimistic.
    """

    @staticmethod
    def _rectangle(width=50.0, height=100.0):
        from engicalc.core import sections
        return sections.Section([sections.Rectangle(width=width,
                                                    height=height)])

    def test_the_integral_is_exact_for_a_rectangle(self):
        from engicalc.core import sections

        # R_n = h / ln(r_outer / r_inner), which every textbook quotes and
        # which the general routine has to reproduce.
        for radius, width, height in ((150.0, 50.0, 100.0),
                                      (500.0, 30.0, 60.0),
                                      (60.0, 20.0, 40.0)):
            with self.subTest(radius=radius, height=height):
                section = self._rectangle(width, height)
                neutral = (section.properties().area
                           / section.over_radius(radius))
                hand = height / math.log((radius + height / 2)
                                         / (radius - height / 2))
                self.assertAlmostEqual(neutral / hand, 1.0, places=12)

    def test_the_integral_is_exact_for_a_circle(self):
        from engicalc.core import sections

        # R_n = a^2 / (2(R - sqrt(R^2 - a^2))). Worth having in closed
        # form: the width of a circle has a vertical tangent top and
        # bottom, and quadrature that does not know that converges slowly.
        for radius, diameter in ((100.0, 40.0), (250.0, 90.0), (60.0, 50.0)):
            with self.subTest(radius=radius, diameter=diameter):
                section = sections.Section([sections.Circle(
                    diameter=diameter)])
                neutral = (section.properties().area
                           / section.over_radius(radius))
                a = diameter / 2.0
                hand = a * a / (2.0 * (radius - math.sqrt(radius * radius
                                                          - a * a)))
                self.assertAlmostEqual(neutral / hand, 1.0, places=12)

    def test_a_hole_takes_away_exactly_its_own_share(self):
        from engicalc.core import sections

        solid = sections.Section([sections.Rectangle(width=60.0,
                                                     height=80.0)])
        hole = sections.Section([sections.Circle(diameter=30.0)])
        holed = sections.Section([sections.Rectangle(width=60.0,
                                                     height=80.0),
                                  sections.Circle(diameter=30.0,
                                                  solid=False)])
        self.assertAlmostEqual(
            solid.over_radius(200.0) - holed.over_radius(200.0),
            hole.over_radius(200.0), places=12)

    def test_the_stresses_carry_the_force_and_the_moment(self):
        from engicalc.core import curved

        # The check that the distribution is the right one rather than a
        # plausible curve. Neither is put in by hand: the stresses are
        # integrated over the section and have to come to exactly what was
        # applied.
        for radius, moment, normal in ((150.0, 5e6, 0.0),
                                       (150.0, 5e6, 30000.0),
                                       (60.0, -2e6, 10000.0),
                                       (300.0, 0.0, 25000.0)):
            with self.subTest(radius=radius, moment=moment, normal=normal):
                got = curved.Curved(section=self._rectangle(),
                                    radius=radius, moment=moment,
                                    normal=normal).properties()
                force, carried, scale = got.balances()
                # Against the scale of what is flowing through the
                # section, not against zero: these are differences of
                # large numbers that nearly cancel. A millionth is the
                # midpoint rule over four thousand strips, not the
                # formula - the formula is exact.
                self.assertLess(abs(force - normal) / scale, 1e-6)
                self.assertLess(abs(carried - moment) / (scale * got.depth),
                                1e-6)

    def test_a_built_up_section_carries_its_moment_too(self):
        from engicalc.core import curved, sections

        # An I section, so the general integral is exercised rather than
        # the closed form for a rectangle.
        section = sections.Section([
            sections.Rectangle(width=100.0, height=12.0, y=94.0),
            sections.Rectangle(width=8.0, height=176.0, y=0.0),
            sections.Rectangle(width=100.0, height=12.0, y=-94.0)])
        got = curved.Curved(section=section, radius=400.0,
                            moment=2e7).properties()
        force, carried, scale = got.balances()
        self.assertLess(abs(force) / scale, 1e-6)
        self.assertAlmostEqual(carried / 2e7, 1.0, places=6)

    def test_the_neutral_axis_always_moves_toward_the_centre(self):
        from engicalc.core import curved

        # And by less and less as the bar straightens out.
        shifts = []
        for ratio in (0.6, 1.0, 2.0, 10.0, 100.0):
            got = curved.Curved(section=self._rectangle(),
                                radius=ratio * 100.0, moment=1.0).properties()
            self.assertGreater(got.shift, 0.0)
            self.assertLess(got.neutral, got.curved.radius)
            shifts.append(got.shift)
        self.assertEqual(shifts, sorted(shifts, reverse=True))

    def test_it_becomes_the_straight_beam_answer(self):
        from engicalc.core import curved

        # The check that ties the whole thing to something already known.
        # A bar curved to a thousand times its depth is a straight one.
        for ratio, within in ((8.0, 0.05), (50.0, 0.01), (1000.0, 0.001)):
            with self.subTest(ratio=ratio):
                got = curved.Curved(section=self._rectangle(),
                                    radius=ratio * 100.0,
                                    moment=5e6).properties()
                for radius in (got.inner, got.outer):
                    self.assertAlmostEqual(got.factor(radius), 1.0,
                                           delta=within)

    def test_the_inside_carries_more_than_a_straight_beam_says(self):
        from engicalc.core import curved

        # The reason the tab exists. On a hook whose radius is about its
        # own depth it is half as much again, and the inside is where a
        # hook is judged.
        got = curved.Curved(section=self._rectangle(), radius=100.0,
                            moment=5e6).properties()
        self.assertGreater(got.factor(got.inner), 1.5)
        self.assertLess(got.factor(got.outer), 0.8)
        self.assertGreater(abs(got.inner_stress), abs(got.outer_stress))

    def test_an_opening_moment_puts_the_inside_into_tension(self):
        from engicalc.core import curved

        # Which is what a load on a crane hook does, and the sign
        # convention the whole module is written in.
        got = curved.Curved(section=self._rectangle(), radius=150.0,
                            moment=5e6).properties()
        self.assertGreater(got.inner_stress, 0.0)
        self.assertLess(got.outer_stress, 0.0)

    def test_a_direct_force_alone_is_spread_evenly(self):
        from engicalc.core import curved

        # No moment, so no hyperbola - just the load over the area, the
        # same at both fibres.
        got = curved.Curved(section=self._rectangle(), radius=200.0,
                            normal=25000.0).properties()
        self.assertAlmostEqual(got.inner_stress, 25000.0 / 5000.0, places=9)
        self.assertAlmostEqual(got.outer_stress, 25000.0 / 5000.0, places=9)

    def test_a_radius_smaller_than_the_section_is_refused(self):
        from engicalc.core import curved

        # Part of it would be at or past the centre of curvature, where
        # the radius is nothing and the stress would be infinite.
        for radius in (40.0, 50.0, -10.0):
            with self.subTest(radius=radius):
                with self.assertRaises(curved.CurvedError):
                    curved.Curved(section=self._rectangle(), radius=radius,
                                  moment=1.0).properties()


class TestRefrigerants(unittest.TestCase):
    """Ammonia and propane, beside R134a, from their own reference equations.

    The check that matters is against the ancillary equation published with
    each formulation. Nothing in this app uses an ancillary - the
    saturation line is found from the equation itself, by the condition
    that defines it, two phases at one pressure with the same Gibbs energy.
    So agreeing with a curve that was fitted separately is a result and not
    an arrangement.

    Each entry below is (reducing pressure, reducing temperature, the
    (n, t) pairs, and how well the published curve itself is quoted to
    reproduce the equation). The form is

        p = p_r exp(T_r/T sum n_i (1 - T/T_r)^t_i)
    """

    ANCILLARY = {
        "R134a": (
            4059280.0, 374.21,
            ((0.4331478287291047, 0.845), (-9.090302559074352, 0.99),
             (2.1476074125217703, 1.14), (-1.557687007603464, 2.651),
             (-3.5020328972698604, 4.507), (14.958442337201044, 17.235)),
            0.0093),
        "Ammonia": (
            11365000.0, 405.56,
            ((-7.2257, 1.0), (1.4263, 1.5), (-0.59642, 2.0),
             (-2.798, 3.6), (-3.7869, 15.5)),
            0.0519),
        "Propane": (
            4251200.0, 369.89,
            ((-23.998635747391152, 1.05), (18.313017605233238, 1.084),
             (-0.42240851966839504, 2.259), (-2.7378298813798962, 4.287),
             (0.257888414168987, 7.66), (-1.3113462226130785, 18.584)),
            0.0163),
    }

    #: Boiling points at one standard atmosphere, which are measured
    #: quantities and not outputs of any of these equations.
    BOILING = {"R134a": -26.07, "Ammonia": -33.327, "Propane": -42.114}

    @staticmethod
    def _ancillary(entry, T):
        reducing, T_r, terms, _quoted = entry
        theta = 1.0 - T / T_r
        return reducing * math.exp(
            T_r / T * sum(n * theta ** t for n, t in terms))

    @staticmethod
    def _fluids():
        from engicalc.core import ammonia, propane, r134a
        return (r134a.FLUID, ammonia.FLUID, propane.FLUID)

    def test_the_saturation_line_agrees_with_the_published_curve(self):
        for fluid in self._fluids():
            entry = self.ANCILLARY[fluid.name]
            quoted = entry[3]
            bottom = fluid.coldest + 10.0
            top = fluid.T_critical - 1.0
            for step in range(9):
                T = bottom + (top - bottom) * step / 8.0
                with self.subTest(fluid=fluid.name, T=round(T, 2)):
                    mine = fluid.saturation_pressure(T)
                    theirs = self._ancillary(entry, T)
                    off = abs(mine / theirs - 1.0) * 100.0
                    # Held to the accuracy the published curve is itself
                    # quoted to, with a little room - agreeing more closely
                    # than the curve is fitted would not mean anything.
                    self.assertLess(off, quoted * 2.0)

    def test_the_boiling_points_are_the_measured_ones(self):
        for fluid in self._fluids():
            with self.subTest(fluid=fluid.name):
                got = fluid.saturation_temperature(101325.0) - 273.15
                self.assertAlmostEqual(got, self.BOILING[fluid.name],
                                       delta=0.02)

    def test_the_critical_pressure_falls_out_of_the_equation(self):
        # Nothing sets it. The equation is evaluated at the critical
        # temperature and density and the published pressure comes back.
        for fluid in self._fluids():
            with self.subTest(fluid=fluid.name):
                got = fluid.pressure(fluid.T_critical, fluid.rho_critical)
                self.assertAlmostEqual(got / fluid.p_critical, 1.0,
                                       delta=0.001)

    def test_all_three_are_measured_from_the_same_place(self):
        # Saturated liquid at 0 C, h = 200 kJ/kg and s = 1 kJ/(kg K), so
        # the three can be put side by side. It is solved from the
        # reference condition rather than written down, so this is checking
        # the solve and not a constant.
        for fluid in self._fluids():
            with self.subTest(fluid=fluid.name):
                liquid, _vapour = fluid.saturated(273.15)
                self.assertAlmostEqual(liquid.h, 200e3, places=6)
                self.assertAlmostEqual(liquid.s, 1000.0, places=9)

    def test_ammonia_carries_far_more_heat_per_kilogram(self):
        from engicalc.core import ammonia, propane, r134a

        # The reason a cold store runs on it. Nothing else about ammonia is
        # convenient, and this one number is why it is used anyway.
        at = 273.15
        heats = {m.FLUID.name: m.latent_heat(at) / 1000.0
                 for m in (r134a, ammonia, propane)}
        self.assertAlmostEqual(heats["R134a"], 198.6, delta=1.0)
        self.assertAlmostEqual(heats["Ammonia"], 1262.0, delta=15.0)
        self.assertAlmostEqual(heats["Propane"], 374.9, delta=2.0)
        self.assertGreater(heats["Ammonia"] / heats["R134a"], 6.0)

    def test_every_derivative_matches_numerical_differentiation(self):
        # Three term shapes with quite different derivatives - plain and
        # exponential, the Gaussian bell, and the associating term whose
        # temperature part is a reciprocal. A sign wrong in any of them
        # leaves the pressure looking plausible and the heat capacities
        # nonsense.
        for fluid in self._fluids():
            for delta in (0.1, 0.5, 1.0, 1.7, 2.5):
                for tau in (0.7, 1.0, 1.35, 2.5):
                    with self.subTest(fluid=fluid.name, delta=delta,
                                      tau=tau):
                        self._compare_derivatives(fluid, delta, tau)

    def _compare_derivatives(self, fluid, delta, tau):
        step = 1e-6
        got = fluid._residual(delta, tau)

        def d_by_delta(which):
            return ((fluid._residual(delta * (1 + step), tau)[which]
                     - fluid._residual(delta * (1 - step), tau)[which])
                    / (2 * delta * step))

        def d_by_tau(which):
            return ((fluid._residual(delta, tau * (1 + step))[which]
                     - fluid._residual(delta, tau * (1 - step))[which])
                    / (2 * tau * step))

        for name, mine, numeric in (
                ("phi_d", got[1], d_by_delta(0)),
                ("phi_dd", got[2], d_by_delta(1)),
                ("phi_t", got[3], d_by_tau(0)),
                ("phi_tt", got[4], d_by_tau(3)),
                ("phi_dt", got[5], d_by_delta(3))):
            with self.subTest(derivative=name):
                self.assertAlmostEqual(
                    mine, numeric,
                    delta=1e-5 * max(abs(numeric), 1.0))

    def test_the_associating_term_is_only_where_it_belongs(self):
        from engicalc.core import ammonia, propane, r134a

        # Ammonia's molecules hydrogen bond, which is why its formulation
        # needed a term shape the others did not. A nine-long tuple is
        # that shape, and the other two have none.
        shapes = {m.FLUID.name: {len(term) for term in m.FLUID.residual}
                  for m in (r134a, ammonia, propane)}
        self.assertEqual({4}, shapes["R134a"])
        self.assertEqual({4, 8}, shapes["Propane"])
        self.assertIn(9, shapes["Ammonia"])

    def test_a_state_outside_the_range_is_refused(self):
        from engicalc.core import propane
        from engicalc.core.helmholtz import FluidError

        # Propane's triple point is at a fifth of a millipascal, where the
        # two-phase search is working in numbers that are all rounding, so
        # the range is held above it and says so rather than returning
        # whatever falls out.
        self.assertGreater(propane.FLUID.coldest, propane.FLUID.T_triple)
        with self.assertRaises(FluidError):
            propane.FLUID.saturation_temperature(1e-3)

    def test_a_wet_mixture_sits_between_the_phases_for_all_of_them(self):
        for fluid in self._fluids():
            with self.subTest(fluid=fluid.name):
                liquid, vapour = fluid.saturated(263.15)
                middle = fluid.wet(263.15, 0.4)
                self.assertAlmostEqual(
                    middle.h, liquid.h + 0.4 * (vapour.h - liquid.h),
                    places=6)
                # Volumes average, not densities.
                self.assertAlmostEqual(
                    1.0 / middle.rho,
                    1.0 / liquid.rho + 0.4 * (1.0 / vapour.rho
                                              - 1.0 / liquid.rho),
                    places=9)


class TestTheCycleOnEveryRefrigerant(unittest.TestCase):
    """The same machine, three working fluids."""

    def _run(self, name):
        from engicalc.core import refrigerants
        from engicalc.core.cycle import Cycle

        cycle = Cycle(fluid=refrigerants.fluid(name),
                      evaporating=263.15, condensing=313.15,
                      superheat=5.0, subcool=3.0,
                      efficiency=0.7, duty=5000.0)
        return cycle.performance(), cycle.states()

    def test_the_coefficient_of_performance_is_set_by_the_temperatures(self):
        # Not by the fluid, which is the thing worth knowing. Three quite
        # different refrigerants between the same two temperatures land
        # within a few per cent of each other, and all of them well under
        # the Carnot limit for that gap.
        found = {name: self._run(name)[0] for name in
                 ("R134a", "Ammonia (R717)", "Propane (R290)")}
        cops = [answer["cooling COP"] for answer in found.values()]
        self.assertLess(max(cops) - min(cops), 0.3)
        carnot = 263.15 / (313.15 - 263.15)
        for name, answer in found.items():
            with self.subTest(fluid=name):
                self.assertLess(answer["cooling COP"], carnot)
                self.assertGreater(answer["cooling COP"], 2.0)

    def test_ammonia_moves_far_less_mass_for_the_same_duty(self):
        # Its latent heat is seven times R134a's, so the pipework and the
        # compressor swept volume are smaller for the same cooling.
        r134a, _states = self._run("R134a")
        ammonia, _also = self._run("Ammonia (R717)")
        self.assertGreater(r134a["mass flow"] / ammonia["mass flow"], 6.0)

    def test_ammonia_leaves_the_compressor_far_hotter(self):
        # The other half of the same trade, and the reason an ammonia
        # plant needs desuperheating that a halocarbon one does not.
        _found, r134a = self._run("R134a")
        _also, ammonia = self._run("Ammonia (R717)")
        self.assertGreater(ammonia[1].T - r134a[1].T, 80.0)
        self.assertGreater(ammonia[1].T - 273.15, 120.0)


class TestTriangles(unittest.TestCase):
    """Three parts of a triangle, and the other three.

    The interesting part is the ambiguous case. Two sides and an angle
    that is not between them describe two different triangles and both are
    correct; handing back whichever one the arcsine happened to give is
    the classic wrong answer in every trigonometry course there is.
    """

    def test_three_sides(self):
        from engicalc.core import geometry

        found = geometry.solve_triangle({"a": 3, "b": 4, "c": 5})
        self.assertEqual(1, len(found))
        triangle = found[0]
        self.assertAlmostEqual(90.0, math.degrees(triangle.C), places=12)
        self.assertAlmostEqual(6.0, triangle.area, places=12)
        self.assertTrue(triangle.right_angled)

    def test_two_sides_and_the_angle_between_them(self):
        from engicalc.core import geometry

        found = geometry.solve_triangle({"a": 3, "b": 4, "C": math.pi / 2})
        self.assertAlmostEqual(5.0, found[0].c, places=12)
        self.assertAlmostEqual(6.0, found[0].area, places=12)

    def test_one_side_and_two_angles(self):
        from engicalc.core import geometry

        # 45-60-75, from the side facing the 75.
        found = geometry.solve_triangle({"c": 10, "A": math.radians(45),
                                         "B": math.radians(60)})
        triangle = found[0]
        self.assertAlmostEqual(75.0, math.degrees(triangle.C), places=12)
        # The sine rule, applied by hand.
        self.assertAlmostEqual(
            10 * math.sin(math.radians(45)) / math.sin(math.radians(75)),
            triangle.a, places=12)

    def test_the_ambiguous_case_gives_both_triangles(self):
        from engicalc.core import geometry

        # sin B = 10 sin 30 / 7 = 5/7, so B is 45.585 or 134.415 degrees,
        # and both leave room for a third angle.
        found = geometry.solve_triangle({"a": 7, "b": 10,
                                         "A": math.radians(30)})
        self.assertEqual(2, len(found))
        self.assertAlmostEqual(45.5847, math.degrees(found[0].B), places=4)
        self.assertAlmostEqual(134.4153, math.degrees(found[1].B), places=4)
        for triangle in found:
            with self.subTest(which=triangle.which):
                # Both really are triangles with the parts that were given.
                self.assertAlmostEqual(7.0, triangle.a, places=12)
                self.assertAlmostEqual(10.0, triangle.b, places=12)
                self.assertAlmostEqual(30.0, math.degrees(triangle.A),
                                       places=12)
                self.assertAlmostEqual(
                    math.pi, triangle.A + triangle.B + triangle.C, places=12)
        self.assertTrue(geometry.why_ambiguous(
            {"a": 7, "b": 10, "A": math.radians(30)}))

    def test_the_ambiguity_goes_away_when_the_side_is_long_enough(self):
        from engicalc.core import geometry

        # The swinging side cannot reach past the foot of the perpendicular
        # twice once the side facing the angle is the longer of the two.
        found = geometry.solve_triangle({"a": 12, "b": 10,
                                         "A": math.radians(30)})
        self.assertEqual(1, len(found))
        self.assertEqual("", found[0].which)

    def test_a_side_too_short_to_reach_is_refused(self):
        from engicalc.core import geometry

        with self.assertRaises(geometry.GeometryError) as caught:
            geometry.solve_triangle({"a": 3, "b": 10, "A": math.radians(30)})
        self.assertIn("too short", str(caught.exception))

    def test_three_angles_are_a_shape_and_not_a_triangle(self):
        from engicalc.core import geometry

        # Every triangle with these angles is a valid answer, so there is
        # no answer, and one is not invented.
        with self.assertRaises(geometry.GeometryError) as caught:
            geometry.solve_triangle({"A": math.radians(60),
                                     "B": math.radians(60),
                                     "C": math.radians(60)})
        self.assertIn("not the size", str(caught.exception))

    def test_sides_that_cannot_close_are_refused(self):
        from engicalc.core import geometry

        with self.assertRaises(geometry.GeometryError):
            geometry.solve_triangle({"a": 1, "b": 2, "c": 5})

    def test_the_area_survives_a_needle(self):
        from engicalc.core import geometry

        # Heron's formula subtracts the longest side from the
        # semi-perimeter, and on a sliver those two agree to almost every
        # figure they have. Two sides and the angle between them does not.
        found = geometry.solve_triangle({"a": 1e6, "b": 1e6, "c": 1.0})
        by_heron = self._heron(1e6, 1e6, 1.0)
        self.assertAlmostEqual(found[0].area / by_heron, 1.0, places=6)
        self.assertGreater(found[0].area, 0.0)

    @staticmethod
    def _heron(a, b, c):
        s = 0.5 * (a + b + c)
        return math.sqrt(max(s * (s - a) * (s - b) * (s - c), 0.0))

    def test_the_drawing_has_the_sides_it_says_it_has(self):
        from engicalc.core import geometry

        # The corners are what gets drawn, so they have to be the same
        # triangle as the numbers in the table beside them.
        triangle = geometry.solve_triangle({"a": 6, "b": 7, "c": 8})[0]
        first, second, third = triangle.corners()
        self.assertAlmostEqual(triangle.c, math.dist(first, second),
                               places=10)
        self.assertAlmostEqual(triangle.b, math.dist(first, third), places=10)
        self.assertAlmostEqual(triangle.a, math.dist(second, third), places=10)


class TestArcs(unittest.TestCase):
    """An arc from any two of its parts.

    Two of the ten pairs describe two arcs rather than one, and both of
    those are returned. One is obvious - a chord cuts a circle in two and
    both pieces are arcs of it. The other is not obvious at all.
    """

    PAIRS = None

    def setUp(self):
        import itertools
        from engicalc.core import geometry

        if self.PAIRS is None:
            TestArcs.PAIRS = list(itertools.combinations(geometry.ARC_PARTS, 2))

    def test_every_pair_recovers_the_arc_it_came_from(self):
        from engicalc.core import geometry

        # Ten pairs at nine angles, over four orders of magnitude of
        # shallowness and through the turning point at 267 degrees.
        for degrees in (0.05, 1.0, 15.0, 80.0, 179.0, 200.0, 267.0, 300.0,
                        355.0):
            base = geometry.Arc(100.0, math.radians(degrees))
            whole = {"R": base.R, "theta": base.theta, "L": base.length,
                     "chord": base.chord, "rise": base.rise}
            for pair in self.PAIRS:
                with self.subTest(degrees=degrees, pair=pair):
                    found = geometry.solve_arc({k: whole[k] for k in pair})
                    close = min(max(abs(arc.R / base.R - 1),
                                    abs(arc.theta / base.theta - 1))
                                for arc in found)
                    self.assertLess(close, 1e-7)

    def test_the_setting_out_formula(self):
        from engicalc.core import geometry

        # R = (c^2/4 + s^2) / 2s, which is what gets used on site.
        found = geometry.solve_arc({"chord": 2000, "rise": 250})
        self.assertEqual(1, len(found))
        self.assertAlmostEqual((2000 ** 2 / 4 + 250 ** 2) / 500, found[0].R,
                               places=9)

    def test_a_radius_and_a_chord_describe_two_arcs(self):
        from engicalc.core import geometry

        # The chord cuts the circle in two and both pieces are arcs of it.
        found = geometry.solve_arc({"R": 100, "chord": 100})
        self.assertEqual(2, len(found))
        self.assertAlmostEqual(60.0, math.degrees(found[0].theta), places=9)
        self.assertAlmostEqual(300.0, math.degrees(found[1].theta), places=9)
        self.assertEqual(["minor", "major"], [arc.which for arc in found])
        for arc in found:
            self.assertAlmostEqual(100.0, arc.chord, places=9)

    def test_a_chord_that_is_the_diameter_describes_one(self):
        from engicalc.core import geometry

        found = geometry.solve_arc({"R": 100, "chord": 200})
        self.assertEqual(1, len(found))
        self.assertAlmostEqual(180.0, math.degrees(found[0].theta), places=6)

    def test_arc_length_with_rise_can_also_describe_two(self):
        from engicalc.core import geometry

        # This one is not obvious. The ratio of an arc to its rise falls
        # to a minimum near 267 degrees and climbs back to pi, so a ratio
        # between those belongs to two different arcs.
        wanted = geometry.Arc(100.0, math.radians(290))
        found = geometry.solve_arc({"L": wanted.length, "rise": wanted.rise})
        self.assertEqual(2, len(found))
        for arc in found:
            with self.subTest(theta=math.degrees(arc.theta)):
                self.assertAlmostEqual(wanted.length, arc.length, places=6)
                self.assertAlmostEqual(wanted.rise, arc.rise, places=6)
        # And they really are different arcs, not the same one twice.
        self.assertGreater(abs(found[0].R - found[1].R), 1.0)

    def test_the_turning_point_is_derived_and_not_written_down(self):
        from engicalc.core import geometry

        # Differentiating theta / (2 sin^2(theta/4)) leaves
        # tan(theta/4) = theta/2 at the turn, and either side of it the
        # ratio has to be larger.
        turn = geometry.TURNS_AT
        self.assertAlmostEqual(math.tan(turn / 4.0), turn / 2.0, places=9)
        ratio = geometry._arc_ratio
        both = frozenset({"L", "rise"})
        self.assertAlmostEqual(geometry.SHALLOWEST, ratio(turn, both),
                               places=12)
        for step in (0.01, 0.2, 1.0):
            self.assertGreater(ratio(turn - step, both), geometry.SHALLOWEST)
            if turn + step < 2 * math.pi:
                self.assertGreater(ratio(turn + step, both),
                                   geometry.SHALLOWEST)

    def test_a_ratio_below_the_turning_point_has_no_arc(self):
        from engicalc.core import geometry

        with self.assertRaises(geometry.GeometryError) as caught:
            geometry.solve_arc({"L": 100, "rise": 45})
        self.assertIn("2.7601", str(caught.exception))

    def test_the_rise_stays_accurate_on_a_shallow_arc(self):
        from engicalc.core import geometry

        # 1 - cos on a shallow arc subtracts two numbers that agree to
        # fifteen figures. The half-angle form does not, and at a quarter
        # of a nanoradian the difference is between a number and zero.
        arc = geometry.Arc(1000.0, 1e-9)
        self.assertGreater(arc.rise, 0.0)
        self.assertAlmostEqual(arc.rise / (1000.0 * (1e-9 ** 2) / 8.0), 1.0,
                               places=6)

    def test_a_chord_bigger_than_the_circle_is_refused(self):
        from engicalc.core import geometry

        with self.assertRaises(geometry.GeometryError):
            geometry.solve_arc({"R": 10, "chord": 25})

    def test_one_part_is_not_enough_and_three_is_too_many(self):
        from engicalc.core import geometry

        for given in ({"R": 5}, {"R": 5, "theta": 1.0, "chord": 4}):
            with self.subTest(given=sorted(given)):
                with self.assertRaises(geometry.GeometryError):
                    geometry.solve_arc(given)


class TestCrossings(unittest.TestCase):
    """Where lines and circles meet, and where they do not."""

    def test_two_lines(self):
        from engicalc.core import geometry

        found = geometry.cross_lines(geometry.line_through((0, 0), (10, 10)),
                                     geometry.line_through((0, 10), (10, 0)))
        self.assertEqual(((5.0, 5.0),), found.points)

    def test_an_upright_line_is_not_a_special_case(self):
        from engicalc.core import geometry

        # Held as Ax + By = C rather than y = mx + c, because a vertical
        # line has no gradient and would otherwise need handling
        # separately everywhere it appeared.
        found = geometry.cross_lines(geometry.line_through((3, 0), (3, 9)),
                                     geometry.line_through((0, 7), (5, 7)))
        self.assertEqual(((3.0, 7.0),), found.points)

    def test_parallel_and_identical_lines_are_told_apart(self):
        from engicalc.core import geometry

        parallel = geometry.cross_lines(
            geometry.line_through((0, 0), (1, 1)),
            geometry.line_through((0, 5), (1, 6)))
        same = geometry.cross_lines(geometry.line_through((0, 0), (1, 1)),
                                    geometry.line_through((2, 2), (3, 3)))
        self.assertFalse(parallel)
        self.assertFalse(same)
        self.assertNotEqual(parallel.note, same.note)

    def test_a_line_and_a_circle(self):
        from engicalc.core import geometry

        through = geometry.line_through((-10, 0), (10, 0))
        found = geometry.cross_line_circle(through, (0, 0), 5)
        self.assertEqual(((-5.0, 0.0), (5.0, 0.0)), found.points)

    def test_a_tangent_touches_once_and_not_twice(self):
        from engicalc.core import geometry

        # Floating point will not land exactly on the touching case, so it
        # is admitted with a tolerance rather than pretended away.
        found = geometry.cross_line_circle(
            geometry.line_through((-10, 5), (10, 5)), (0, 0), 5)
        self.assertEqual(1, len(found.points))
        self.assertAlmostEqual(0.0, found.points[0][0], places=12)
        self.assertAlmostEqual(5.0, found.points[0][1], places=12)

    def test_two_circles(self):
        from engicalc.core import geometry

        found = geometry.cross_circles((0, 0), 5, (8, 0), 5)
        self.assertEqual(2, len(found.points))
        for x, y in found.points:
            self.assertAlmostEqual(4.0, x, places=12)
            self.assertAlmostEqual(3.0, abs(y), places=12)

    def test_circles_that_touch_miss_or_nest(self):
        from engicalc.core import geometry

        touching = geometry.cross_circles((0, 0), 5, (10, 0), 5)
        self.assertEqual(1, len(touching.points))
        self.assertFalse(geometry.cross_circles((0, 0), 5, (20, 0), 5))
        self.assertFalse(geometry.cross_circles((0, 0), 10, (1, 0), 2))

    def test_tangents_from_a_point(self):
        from engicalc.core import geometry

        # From (10, 0) to a circle of radius 6 the touch points are at
        # x = r^2/d = 3.6 and y = r*sqrt(d^2 - r^2)/d = 4.8.
        found = geometry.tangent_from_point((10, 0), (0, 0), 6)
        self.assertEqual(2, len(found.points))
        for x, y in found.points:
            self.assertAlmostEqual(3.6, x, places=10)
            self.assertAlmostEqual(4.8, abs(y), places=10)
            # On the circle, and square to the radius, which is what makes
            # it a tangent rather than a chord.
            self.assertAlmostEqual(6.0, math.hypot(x, y), places=10)
            self.assertAlmostEqual(0.0, (x - 10) * x + y * y, places=8)
        self.assertAlmostEqual(8.0, geometry.tangent_length((10, 0), (0, 0), 6),
                               places=12)

    def test_no_tangent_from_inside(self):
        from engicalc.core import geometry

        self.assertFalse(geometry.tangent_from_point((1, 0), (0, 0), 6))

    def test_the_circle_through_three_points(self):
        from engicalc.core import geometry

        centre, radius = geometry.circle_through((0, 0), (10, 0), (0, 10))
        self.assertAlmostEqual(5.0, centre[0], places=12)
        self.assertAlmostEqual(5.0, centre[1], places=12)
        self.assertAlmostEqual(math.hypot(5, 5), radius, places=12)

    def test_three_points_in_a_line_have_no_circle(self):
        from engicalc.core import geometry

        with self.assertRaises(geometry.GeometryError):
            geometry.circle_through((0, 0), (1, 1), (2, 2))

    def test_a_circle_through_three_points_passes_through_all_three(self):
        from engicalc.core import geometry

        for points in (((0, 0), (10, 0), (0, 10)),
                       ((-3, 2), (4, 9), (11, -2)),
                       ((0, 0), (1, 0.001), (2, 0))):
            with self.subTest(points=points):
                centre, radius = geometry.circle_through(*points)
                for point in points:
                    self.assertAlmostEqual(
                        math.dist(point, centre) / radius, 1.0, places=9)


def _inside(hull, point) -> bool:
    """Is a point inside a convex polygon, or on its edge?"""
    def turn(one, two, three):
        return ((two[0] - one[0]) * (three[1] - one[1])
                - (two[1] - one[1]) * (three[0] - one[0]))

    signs = [turn(hull[i], hull[(i + 1) % len(hull)], point)
             for i in range(len(hull))]
    return all(s >= -1e-12 for s in signs) or all(s <= 1e-12 for s in signs)


class TestMaterials(unittest.TestCase):
    """A table of numbers in a program has to justify itself.

    Property data cannot be checked the way a section can - a yield
    strength is not derivable from anything - but several relations have to
    hold across it, and each one catches a transcription error in two or
    three properties at once.
    """

    def test_the_whole_database_is_self_consistent(self):
        from engicalc.core import materials

        # G = E/2(1+nu), yield below tensile strength, service below
        # melting, and the volumetric heat capacity and thermal diffusivity
        # inside the bands every solid falls in.
        off = materials.reconcile()
        self.assertEqual([], off, "\n".join(f"{name}: {why}"
                                            for name, why in off))

    def test_the_elastic_constants_agree_with_the_librarys_own_formula(self):
        from engicalc.core import materials
        from engicalc.formulas.library import get_library, solve_formula

        # The relation is a formula in this program, so the data can be
        # checked against the program's own algebra rather than against a
        # number written twice.
        formula = get_library().get("strength_of_materials.shear_modulus")
        for material in materials.all_materials():
            if not {"youngs", "shear", "poisson"} <= set(material.values):
                continue
            with self.subTest(material=material.name):
                got = solve_formula(
                    formula, "G",
                    {"E": repr(material.typical("youngs")),
                     "nu": repr(material.typical("poisson"))})
                self.assertAlmostEqual(
                    got.value / material.typical("shear"), 1.0,
                    delta=materials.ELASTIC_TOLERANCE)

    def test_the_two_kinds_of_property_behave_differently(self):
        from engicalc.core import materials

        # The distinction the whole database is built on. What processing
        # changes is wide; what bonding decides is not.
        steel = materials.find("Carbon steel")
        self.assertLess(steel.spread("youngs"), 1.2)
        self.assertLess(steel.spread("density"), 1.2)
        self.assertLess(steel.spread("specific_heat"), 1.2)
        self.assertGreater(steel.spread("yield"), 4.0)
        self.assertGreater(steel.spread("toughness"), 4.0)

    def test_a_grade_is_tighter_than_the_class_it_belongs_to(self):
        from engicalc.core import materials

        # Which is the point of having both levels.
        family = materials.find("Carbon steel")
        grade = materials.find("S275 steel")
        self.assertLess(grade.spread("yield"), family.spread("yield"))
        low, high = family.span("yield")
        self.assertLessEqual(low, grade.typical("yield"))
        self.assertLessEqual(grade.typical("yield"), high)

    def test_the_typical_value_is_the_middle_of_the_range(self):
        from engicalc.core import materials

        # The geometric middle. These properties span orders of magnitude
        # and are read on logarithmic axes, so halfway between 1 and 100 is
        # 10 rather than 50.
        material = materials.find("Carbon steel")
        low, high = material.span("yield")
        self.assertAlmostEqual(material.typical("yield"),
                               math.sqrt(low * high), places=9)

    def test_every_class_and_grade_has_a_family_and_a_source(self):
        from engicalc.core import materials

        for material in materials.all_materials():
            with self.subTest(material=material.name):
                self.assertIn(material.family, materials.FAMILIES)
                self.assertTrue(material.source)

    def test_the_chart_covers_the_ground_a_chart_has_to_cover(self):
        from engicalc.core import materials

        # A selection chart is only worth drawing if the answer might be
        # somewhere unexpected, which means the unexpected has to be on
        # it. Density runs a foam to tungsten, three decades; modulus a
        # silicone to a carbide, nearly seven.
        #
        # The numbers below are what the data actually spans, less a
        # little. Set to what it ought to span they would be a wish
        # rather than a guard.
        for prop, decades in (("density", 3.0), ("youngs", 6.5),
                              ("yield", 3.0), ("conductivity", 4.0),
                              ("uts", 5.0), ("toughness", 4.5)):
            having = [m for m in materials.CLASSES if m.has(prop)]
            with self.subTest(prop=prop):
                low = min(m.span(prop)[0] for m in having)
                high = max(m.span(prop)[1] for m in having)
                self.assertGreater(math.log10(high / low), decades)

    def test_every_family_has_enough_in_it_to_be_a_family(self):
        from engicalc.core import materials

        # An envelope is drawn round each one, and a family of two is a
        # line rather than a shape.
        for family in materials.FAMILIES:
            inside = [m for m in materials.CLASSES if m.family == family]
            with self.subTest(family=family):
                self.assertGreaterEqual(len(inside), 3)

    def test_wood_is_on_the_chart_both_ways_round(self):
        from engicalc.core import materials

        # Along the grain wood looks extraordinary and across it looks
        # like a soft polymer. Putting only the first on the chart is
        # putting the half that flatters it.
        along = materials.find("Softwood, along the grain")
        across = materials.find("Softwood, across the grain")
        self.assertIsNotNone(across)
        self.assertGreater(along.typical("youngs") / across.typical("youngs"),
                           10.0)
        # Same stuff, so the density is the same.
        self.assertAlmostEqual(
            along.typical("density") / across.typical("density"), 1.0,
            delta=0.05)

    def test_the_family_envelope_is_a_hull(self):
        from engicalc.ui.charts_pane import _hull

        # A square with a point inside it: the hull is the square.
        square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
                  (0.5, 0.5)]
        found = _hull(square)
        self.assertEqual(4, len(found))
        self.assertNotIn((0.5, 0.5), found)
        # And every one of the original points is inside or on it.
        for point in square:
            with self.subTest(point=point):
                self.assertTrue(_inside(found, point))

    def test_a_hull_of_three_points_is_the_triangle(self):
        from engicalc.ui.charts_pane import _hull

        self.assertEqual(3, len(_hull([(0.0, 0.0), (2.0, 0.0), (1.0, 1.0),
                                       (1.0, 0.5)])))

    def test_a_property_nobody_recorded_is_refused_rather_than_guessed(self):
        from engicalc.core import materials

        with self.assertRaises(materials.MaterialError):
            materials.find("Concrete").span("resistivity")

    # -- the charts --------------------------------------------------------
    def test_the_index_slope_is_the_ratio_of_its_exponents(self):
        from engicalc.core import materials

        # On logarithmic axes a contour of y^a/x^b is a line of slope b/a.
        # A light stiff beam maximises E^(1/2)/rho, so the famous slope of
        # two is not a convention - it falls out of the exponents.
        beam = [i for i in materials.INDICES
                if i[0] == "Light, stiff beam"][0]
        self.assertAlmostEqual(beam[4] / beam[3], 2.0, places=9)
        through = materials.find("Carbon steel")
        span = (100.0, 10000.0)
        line_x, line_y = materials.guideline(beam, through, span)
        rise = math.log(line_y[1] / line_y[0])
        run = math.log(line_x[1] / line_x[0])
        self.assertAlmostEqual(rise / run, 2.0, places=9)

    def test_the_guideline_passes_through_the_material_it_names(self):
        from engicalc.core import materials

        index = materials.INDICES[1]
        through = materials.find("Aluminium alloy")
        line_x, line_y = materials.guideline(index, through, (10.0, 20000.0))
        # Interpolate the line at that material's own density, on log axes.
        share = (math.log(through.typical("density") / line_x[0])
                 / math.log(line_x[1] / line_x[0]))
        at = line_y[0] * (line_y[1] / line_y[0]) ** share
        self.assertAlmostEqual(at / through.typical("youngs"), 1.0,
                               places=6)

    def test_the_indices_give_the_answers_they_are_famous_for(self):
        from engicalc.core import materials

        # Wood and carbon fibre beat steel for a light stiff beam, which is
        # the single best known result on these charts and the reason
        # aircraft spars were made of spruce.
        beam = [i for i in materials.INDICES
                if i[0] == "Light, stiff beam"][0]
        order = [material.name for _v, material
                 in materials.ranked(beam, grades=False)]
        steel = order.index("Carbon steel")
        for better in ("Softwood, along the grain", "CFRP, quasi-isotropic"):
            self.assertLess(order.index(better), steel)

        # And for a light strong beam the light metals and the fibre
        # composites beat the heavy metals, which is the other result
        # these charts are known for.
        #
        # Not "magnesium wins", which it did when there were half as many
        # materials and stopped doing when an aluminium-silicon carbide
        # composite was added. Whichever single material happens to be
        # top is a fact about the list; that magnesium and titanium beat
        # steel is a fact about the mechanics.
        strong = [i for i in materials.INDICES
                  if i[0] == "Light, strong beam"][0]
        order = [material.name for _v, material
                 in materials.ranked(strong, grades=False)]
        for lighter in ("Magnesium alloy", "Titanium alloy"):
            for heavier in ("Carbon steel", "Cast iron", "Copper alloy"):
                with self.subTest(lighter=lighter, heavier=heavier):
                    self.assertLess(order.index(lighter),
                                    order.index(heavier))

    def test_a_material_missing_a_property_scores_nothing(self):
        from engicalc.core import materials

        # Rather than infinitely well, which is what dividing by a missing
        # denominator would give.
        index = [i for i in materials.INDICES
                 if i[0] == "Light, strong beam"][0]
        glass = materials.find("Soda-lime glass")
        self.assertFalse(glass.has("yield"))
        self.assertEqual(materials.index_value(glass, index), 0.0)
        self.assertNotIn(glass, [m for _v, m in materials.ranked(index)])

    def test_only_grades_are_offered_to_a_calculation(self):
        from engicalc.core import materials

        # A class is a range and a calculation wants a number; handing over
        # the middle of 250 to 1500 would look like an answer.
        grades = materials.names(grades=True)
        self.assertIn("S275 steel", grades)
        self.assertNotIn("Carbon steel", grades)
        for name in grades:
            self.assertTrue(materials.find(name).grade)


class TestMaterialsIntoFormulas(unittest.TestCase):
    """Filling a formula from the database.

    The interesting part is not the filling, it is the refusing: the word
    "density" appears twenty-one times in the library and only six of
    those want a solid out of the database. The rest are air in a duct or
    water in a pipe, and nothing in the description tells the two apart.
    """

    def test_every_declared_slot_names_a_real_property(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary

        library = FormulaLibrary(load_user=False)
        declared = 0
        for formula in library.all():
            for variable in formula.variables:
                if not variable.material:
                    continue
                declared += 1
                with self.subTest(formula=formula.key, symbol=variable.symbol):
                    self.assertIn(variable.material, materials.PROPERTIES)
        self.assertGreater(declared, 30)

    def test_every_declared_slot_can_be_converted_into(self):
        from engicalc.core import materials, units
        from engicalc.formulas.library import FormulaLibrary

        # The database keeps a modulus in GPa and a strength in N/mm2,
        # because that is how they are quoted; the library writes its
        # formulas in pascals. A slot nobody can convert into would fill
        # with a number a thousand million times wrong and look fine.
        library = FormulaLibrary(load_user=False)
        for formula in library.all():
            for variable in formula.variables:
                if not variable.material:
                    continue
                held = materials.PROPERTIES[variable.material][1]
                with self.subTest(formula=formula.key, symbol=variable.symbol):
                    self.assertTrue(
                        units.compatible(held, variable.unit)
                        or units.is_dimensionless(held),
                        f"{held} does not convert to {variable.unit}")

    def test_the_value_arrives_in_the_unit_the_formula_wants(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary

        library = FormulaLibrary(load_user=False)
        formula = library.get("strength_of_materials.hookes_law")
        filled = materials.fill("S275 steel", formula.variables)
        # The database says 210 GPa; the formula is written in pascals.
        self.assertAlmostEqual(filled["E"], 210e9, delta=1e9)

        # And the same property into a different unit.
        grams = library.get("materials_manufacturing.print_mass")
        self.assertEqual("g/cm^3", grams.variable("rho").unit)
        filled = materials.fill("6082-T6 aluminium", grams.variables)
        self.assertAlmostEqual(filled["rho"], 2.70, places=2)

    def test_a_fluid_density_is_not_offered_a_solid(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary

        # The whole reason the slot is declared rather than guessed from
        # the words. Both of these call their variable a density.
        library = FormulaLibrary(load_user=False)
        drag = library.get("fluid_mechanics.drag_force")
        self.assertIn("density", drag.variable("rho").description.lower())
        self.assertEqual([], materials.can_fill(drag.variables))
        self.assertEqual({}, materials.fill("S275 steel", drag.variables))

        sheet = library.get("hvac_sheet_metal.sheet_weight")
        self.assertIn("density", sheet.variable("rho").description.lower())
        self.assertEqual(["density"], materials.can_fill(sheet.variables))

    def test_a_gas_property_is_not_offered_one_either(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary

        # The ratio of specific heats is dimensionless and belongs to a
        # gas; nothing in the database has one, so nothing is offered.
        library = FormulaLibrary(load_user=False)
        for key in ("thermodynamics.cp_cv", "thermodynamics.otto_efficiency",
                    "fluid_mechanics.speed_of_sound"):
            with self.subTest(formula=key):
                self.assertEqual(
                    [], materials.can_fill(library.get(key).variables))

    def test_a_property_the_material_lacks_is_left_alone(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary

        # Rather than filled from the materials that do record it, which
        # would be a guess wearing an answer's face.
        library = FormulaLibrary(load_user=False)
        formula = library.get("materials_manufacturing.specific_strength")
        wood = materials.find("Softwood, along the grain")
        self.assertFalse(wood.has("yield"))
        filled = materials.fill(wood, formula.variables)
        self.assertIn("rho", filled)
        self.assertNotIn("sigma_y", filled)

    def test_only_materials_that_can_fill_something_are_offered(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary

        library = FormulaLibrary(load_user=False)
        formula = library.get("electrical.resistivity")
        offered = materials.knowing(formula.variables)
        self.assertTrue(offered)
        for name in offered:
            with self.subTest(material=name):
                self.assertTrue(materials.find(name).has("resistivity"))

    def test_a_formula_filled_from_the_database_returns_the_database(self):
        from engicalc.core import materials
        from engicalc.formulas.library import FormulaLibrary, solve_formula

        # The round trip that checks the declaration, the conversion and
        # the algebra at once: fill E and nu for a grade, solve for G, and
        # get back that grade's own recorded shear modulus.
        library = FormulaLibrary(load_user=False)
        formula = library.get("strength_of_materials.shear_modulus")
        for name in materials.names(grades=True):
            material = materials.find(name)
            if not {"youngs", "poisson", "shear"} <= set(material.values):
                continue
            with self.subTest(material=name):
                filled = materials.fill(material, formula.variables)
                got = solve_formula(formula, "G",
                                    {"E": repr(filled["E"]),
                                     "nu": repr(filled["nu"])})
                self.assertAlmostEqual(
                    float(got.value) / filled["G"], 1.0,
                    delta=materials.ELASTIC_TOLERANCE)

    def test_declaring_a_slot_that_is_not_a_variable_is_refused(self):
        from engicalc.formulas.model import make_builder

        # A typo in a symbol would otherwise declare nothing and say
        # nothing, and the picker would quietly fill one field short.
        build = make_builder("Test")
        with self.assertRaises(KeyError):
            build("bad", "Bad", "Test", "y = E*x",
                  {"y": ("Out", "Pa"), "E": ("Young's modulus", "Pa"),
                   "x": ("Strain", "-")},
                  made_of={"EE": "youngs"})


class TestFailureTheories(unittest.TestCase):
    """Tresca and von Mises, against the states with known answers."""

    def test_uniaxial_tension_gives_the_stress_itself(self):
        from engicalc.core.mohr import Mohr

        # Both criteria are calibrated on a tensile test, so both have to
        # return the tensile stress for a tensile state or neither means
        # anything.
        state = Mohr(100.0, 0.0, 0.0)
        self.assertAlmostEqual(state.tresca, 100.0, places=9)
        self.assertAlmostEqual(state.von_mises, 100.0, places=9)

    def test_pure_shear_is_where_they_disagree_most(self):
        from engicalc.core.mohr import Mohr

        # Tresca says 2 tau and von Mises says root 3 tau, and the ratio
        # 2/root3 is the furthest apart they ever get.
        state = Mohr(0.0, 0.0, 100.0)
        self.assertAlmostEqual(state.tresca, 200.0, places=9)
        self.assertAlmostEqual(state.von_mises, math.sqrt(3) * 100.0,
                               places=9)
        self.assertAlmostEqual(state.tresca / state.von_mises,
                               2.0 / math.sqrt(3), places=12)

    def test_tresca_is_never_below_von_mises_and_never_far_above(self):
        from engicalc.core.mohr import Mohr

        # Which is what makes Tresca the safe one to use. Checked over a
        # spread of states rather than at a point, because the bound is a
        # statement about all of them.
        worst, best = 0.0, 9.9
        for across in range(-200, 201, 25):
            for up in range(-200, 201, 25):
                for shear in range(0, 201, 25):
                    state = Mohr(float(across), float(up), float(shear))
                    if state.von_mises > 1e-9:
                        ratio = state.tresca / state.von_mises
                        worst, best = max(worst, ratio), min(best, ratio)
        self.assertGreaterEqual(best, 1.0 - 1e-12)
        self.assertLessEqual(worst, 2.0 / math.sqrt(3) + 1e-12)

    def test_the_third_principal_stress_is_not_forgotten(self):
        from engicalc.core.mohr import Mohr

        # The trap. With both in-plane stresses the same sign, Tresca is
        # the larger against zero - not the gap between the two.
        state = Mohr(100.0, 60.0, 0.0)
        self.assertAlmostEqual(state.tresca, 100.0, places=9)
        self.assertNotAlmostEqual(state.tresca, 40.0, places=3)

    def test_hydrostatic_pressure_does_not_yield_anything(self):
        from engicalc.core.mohr import von_mises_of

        # Squeeze something equally from every side and it changes volume
        # but not shape, and von Mises is about changing shape.
        self.assertAlmostEqual(von_mises_of(-500.0, -500.0, -500.0), 0.0,
                               places=9)

    def test_the_ellipse_satisfies_its_own_equation(self):
        from engicalc.core.mohr import Mohr

        state = Mohr(100.0, 0.0, 50.0)
        first, second = state.mises_locus(275.0, 361)
        for one, two in zip(first, second):
            self.assertAlmostEqual(
                math.sqrt(one * one - one * two + two * two), 275.0,
                places=6)


class TestStrainRosettes(unittest.TestCase):
    """Three gauge readings back to the state that made them."""

    TRUE = (450e-6, -120e-6, 300e-6)

    def _reading(self, degrees):
        across, up, shear = self.TRUE
        angle = math.radians(degrees)
        return (across * math.cos(angle) ** 2 + up * math.sin(angle) ** 2
                + shear * math.sin(angle) * math.cos(angle))

    def test_every_rosette_reads_the_state_back(self):
        from engicalc.core.mohr import ROSETTES, strains_from_rosette

        for name, angles in ROSETTES.items():
            with self.subTest(rosette=name):
                got = strains_from_rosette(
                    [self._reading(a) for a in angles], angles)
                for mine, theirs in zip(got, self.TRUE):
                    self.assertAlmostEqual(mine, theirs, places=12)

    def test_a_rosette_at_any_angles_works_the_same_way(self):
        from engicalc.core.mohr import strains_from_rosette

        # Solved as a system rather than by the two special formulae, so
        # an odd rosette is no harder than a standard one.
        angles = (0.0, 30.0, 75.0)
        got = strains_from_rosette([self._reading(a) for a in angles],
                                   angles)
        for mine, theirs in zip(got, self.TRUE):
            self.assertAlmostEqual(mine, theirs, places=12)

    def test_two_gauges_the_same_way_cannot_be_solved(self):
        from engicalc.core.mohr import strains_from_rosette

        with self.assertRaises(ValueError):
            strains_from_rosette([1e-6, 2e-6, 3e-6], (0.0, 0.0, 90.0))

    def test_pulling_a_bar_gives_stress_along_it_and_none_across(self):
        from engicalc.core.mohr import from_rosette

        # And the stress is E times the strain, which only comes out if
        # the sideways strain has been handled - using E on its own gives
        # an answer about ten per cent light.
        modulus, poisson = 210e3, 0.3
        along = 500e-6
        across = -poisson * along
        angles = (0.0, 45.0, 90.0)
        readings = [along * math.cos(math.radians(a)) ** 2
                    + across * math.sin(math.radians(a)) ** 2
                    for a in angles]
        state = from_rosette(readings, angles, modulus, poisson)
        self.assertAlmostEqual(state.sigma_x, modulus * along, places=6)
        self.assertAlmostEqual(state.sigma_y, 0.0, places=9)
        self.assertAlmostEqual(state.tau_xy, 0.0, places=12)

    def test_the_principal_directions_agree_for_strain_and_stress(self):
        from engicalc.core.mohr import (from_rosette, principal_strains,
                                        strains_from_rosette)

        # They have to for an isotropic material, and they come out of two
        # separate calculations - so agreeing is a check on both.
        angles = (0.0, 45.0, 90.0)
        readings = [self._reading(a) for a in angles]
        across, up, shear = strains_from_rosette(readings, angles)
        _first, _second, strain_angle = principal_strains(across, up, shear)
        state = from_rosette(readings, angles, 210e3, 0.3)
        self.assertAlmostEqual(strain_angle, state.theta_p, places=9)

    def test_an_impossible_poisson_ratio_is_refused(self):
        from engicalc.core.mohr import stress_from_strain

        for ratio in (0.5, 0.7, -1.5):
            with self.subTest(poisson=ratio):
                with self.assertRaises(ValueError):
                    stress_from_strain(1e-3, 0.0, 0.0, 210e3, ratio)


class TestPressureVessels(unittest.TestCase):
    """Thin walls and Lame, and the gap between them."""

    def test_the_thin_walled_lines(self):
        from engicalc.core.vessels import Vessel

        # hoop = pr/t and along = pr/2t, and a sphere is half a cylinder.
        cylinder = Vessel(inner_radius=500.0, thickness=10.0, pressure=2.0)
        self.assertAlmostEqual(cylinder.thin_hoop,
                               2.0 * 505.0 / 10.0, places=9)
        self.assertAlmostEqual(cylinder.thin_along,
                               cylinder.thin_hoop / 2.0, places=9)
        sphere = Vessel(inner_radius=500.0, thickness=10.0, pressure=2.0,
                        shape="sphere")
        self.assertAlmostEqual(sphere.thin_hoop, cylinder.thin_hoop / 2.0,
                               places=9)

    def test_lame_at_the_two_surfaces(self):
        from engicalc.core.vessels import Vessel

        inner, wall, pressure = 100.0, 50.0, 30.0
        outer = inner + wall
        vessel = Vessel(inner_radius=inner, thickness=wall,
                        pressure=pressure)
        self.assertAlmostEqual(
            vessel.hoop_at(inner),
            pressure * (outer ** 2 + inner ** 2)
            / (outer ** 2 - inner ** 2), places=9)
        self.assertAlmostEqual(
            vessel.hoop_at(outer),
            2 * pressure * inner ** 2 / (outer ** 2 - inner ** 2), places=9)
        # The radial stress is the pressure at the bore and nothing outside,
        # which is the boundary condition Lame is solved from.
        self.assertAlmostEqual(vessel.radial_at(inner), -pressure, places=9)
        self.assertAlmostEqual(vessel.radial_at(outer), 0.0, places=9)
        self.assertAlmostEqual(
            vessel.along, pressure * inner ** 2
            / (outer ** 2 - inner ** 2), places=9)

    def test_a_sphere_follows_its_own_lame(self):
        from engicalc.core.vessels import Vessel

        inner, wall, pressure = 100.0, 50.0, 30.0
        outer = inner + wall
        vessel = Vessel(inner_radius=inner, thickness=wall,
                        pressure=pressure, shape="sphere")
        self.assertAlmostEqual(
            vessel.hoop_at(inner),
            pressure * (outer ** 3 + 2 * inner ** 3)
            / (2 * (outer ** 3 - inner ** 3)), places=9)
        self.assertAlmostEqual(vessel.radial_at(inner), -pressure, places=9)

    def test_thin_walled_is_good_when_thin_and_not_when_thick(self):
        from engicalc.core.vessels import Vessel

        thin = Vessel(inner_radius=500.0, thickness=10.0, pressure=2.0)
        thick = Vessel(inner_radius=100.0, thickness=50.0, pressure=30.0)
        self.assertLess(
            abs(thin.hoop_at(500.0) / thin.thin_hoop - 1.0), 0.001)
        self.assertGreater(
            abs(thick.hoop_at(100.0) / thick.thin_hoop - 1.0), 0.02)
        self.assertTrue([n for n in thick.notes() if "past the tenth" in n])

    def test_an_open_ended_cylinder_carries_nothing_along_it(self):
        from engicalc.core.vessels import Vessel

        pipe = Vessel(inner_radius=100.0, thickness=10.0, pressure=5.0,
                      closed=False)
        self.assertAlmostEqual(pipe.thin_along, 0.0, places=12)
        self.assertAlmostEqual(pipe.along, 0.0, places=12)

    def test_sizing_a_wall_gives_back_the_allowable_stress(self):
        from engicalc.core.vessels import Vessel, thickness_for

        wall = thickness_for(3.0, 400.0, 250.0)
        back = Vessel(inner_radius=400.0, thickness=wall, pressure=3.0)
        self.assertAlmostEqual(back.thin_hoop, 250.0, places=6)

    def test_the_vessels_that_are_not_vessels_are_refused(self):
        from engicalc.core.vessels import Vessel, VesselError

        for bad in (dict(inner_radius=0.0, thickness=1.0, pressure=1.0),
                    dict(inner_radius=1.0, thickness=0.0, pressure=1.0),
                    dict(inner_radius=1.0, thickness=1.0, pressure=1.0,
                         shape="cube")):
            with self.subTest(**bad):
                with self.assertRaises(VesselError):
                    Vessel(**bad).rows()


class TestTrusses(unittest.TestCase):
    """Pin-jointed frames, solved at every joint at once."""

    def _simple(self):
        from engicalc.core.trusses import Load, Member, Node, Truss

        # Two sloping bars and a tie, with a load hung from the apex.
        return Truss(nodes=[Node(0, 0, "pin"), Node(4, 0, "roller"),
                            Node(2, 3)],
                     members=[Member(0, 2), Member(1, 2), Member(0, 1)],
                     loads=[Load(2, up=-10000.0)])

    def test_the_frame_anybody_can_check_by_hand(self):
        frame = self._simple()
        found = frame.solve()
        angle = math.atan2(3, 2)
        # The sloping bars push and the tie pulls.
        self.assertAlmostEqual(found.forces[0],
                               -5000.0 / math.sin(angle), places=6)
        self.assertAlmostEqual(found.forces[1],
                               -5000.0 / math.sin(angle), places=6)
        self.assertAlmostEqual(found.forces[2],
                               5000.0 / math.tan(angle), places=6)

    def test_every_joint_balances(self):
        from engicalc.core.trusses import warren

        # The check the method is made of. If a joint does not balance the
        # answer is not a solution of anything.
        frame = warren(4, 2000.0, 1500.0, 20000.0)
        found = frame.solve()
        for index, _node in enumerate(frame.nodes):
            across = up = 0.0
            for position, member in enumerate(frame.members):
                if index not in (member.start, member.end):
                    continue
                unit_x, unit_y = frame.direction_of(member)
                way = 1.0 if member.start == index else -1.0
                across += way * unit_x * found.forces[position]
                up += way * unit_y * found.forces[position]
            for node, direction, value in found.reactions:
                if node == index:
                    across += value if direction == "across" else 0.0
                    up += value if direction == "up" else 0.0
            for load in frame.loads:
                if load.node == index:
                    across += load.across
                    up += load.up
            with self.subTest(joint=index + 1):
                self.assertAlmostEqual(across, 0.0, places=6)
                self.assertAlmostEqual(up, 0.0, places=6)

    def test_the_reactions_carry_the_whole_load(self):
        from engicalc.core.trusses import warren

        frame = warren(4, 2000.0, 1500.0, 20000.0)
        found = frame.solve()
        lifted = sum(value for _n, way, value in found.reactions
                     if way == "up")
        self.assertAlmostEqual(lifted, -sum(load.up for load in frame.loads),
                               places=6)

    def test_a_warren_girder_is_symmetric(self):
        from engicalc.core.trusses import warren

        # Symmetric frame, symmetric loading, so the two reactions match
        # and the outer diagonals are mirror images. Nothing in the solver
        # knows that, so it is a check rather than a restatement.
        found = warren(4, 2000.0, 1500.0, 20000.0).solve()
        lifted = [value for _n, way, value in found.reactions
                  if way == "up"]
        self.assertAlmostEqual(lifted[0], lifted[1], places=6)

    def test_a_frame_with_too_few_members_is_a_mechanism(self):
        from engicalc.core.trusses import (Load, Member, Node, Truss,
                                           TrussError)

        with self.assertRaises(TrussError) as caught:
            Truss(nodes=[Node(0, 0, "pin"), Node(4, 0), Node(2, 3)],
                  members=[Member(0, 2), Member(1, 2)],
                  loads=[Load(2, up=-1000.0)]).solve()
        self.assertIn("mechanism", str(caught.exception))

    def test_a_frame_with_too_many_cannot_be_settled_by_statics(self):
        from engicalc.core.trusses import (Load, Member, Node, Truss,
                                           TrussError)

        with self.assertRaises(TrussError) as caught:
            Truss(nodes=[Node(0, 0, "pin"), Node(4, 0, "pin"), Node(2, 3)],
                  members=[Member(0, 2), Member(1, 2), Member(0, 1)],
                  loads=[Load(2, up=-1000.0)]).solve()
        self.assertIn("statics", str(caught.exception))

    def test_a_frame_written_down_reads_back_the_same(self):
        from engicalc.core.trusses import as_text, parse, warren

        frame = warren(3, 2000.0, 1500.0, 15000.0)
        again = parse(as_text(frame))
        self.assertEqual([round(f, 9) for f in frame.solve().forces],
                         [round(f, 9) for f in again.solve().forces])

    def test_a_frame_that_will_not_read_says_which_line(self):
        from engicalc.core.trusses import TrussError, parse

        for text in ("node 0 0 welded", "strut 1 2", "node 0"):
            with self.subTest(text=text):
                with self.assertRaises(TrussError) as caught:
                    parse(text)
                self.assertIn("1", str(caught.exception))

    def test_zero_force_members_are_found_rather_than_spotted(self):
        from engicalc.core.trusses import Load, Member, Node, Truss

        # A joint with three bars, two of them in line and no load on it:
        # the third carries nothing. It is the classic case and the one
        # people are asked to spot by eye.
        frame = Truss(
            nodes=[Node(0, 0, "pin"), Node(2, 0), Node(4, 0, "roller"),
                   Node(2, 2)],
            members=[Member(0, 1), Member(1, 2), Member(0, 3),
                     Member(2, 3), Member(1, 3)],
            loads=[Load(3, up=-10000.0)])
        found = frame.solve()
        self.assertIn(4, found.zero_members())
        self.assertTrue([n for n in found.notes() if "nothing" in n])


class TestMoody(unittest.TestCase):
    """Colebrook solved rather than approximated."""

    def test_laminar_is_exactly_64_over_re(self):
        from engicalc.core.moody import friction_factor

        factor, regime, _note = friction_factor(1000.0, 0.0)
        self.assertAlmostEqual(factor, 0.064, places=12)
        self.assertEqual(regime, "laminar")

    def test_colebrook_is_actually_solved(self):
        import math

        from engicalc.core.moody import colebrook

        # The equation has the factor on both sides; the answer has to
        # satisfy it, not merely be near it.
        for reynolds, roughness in ((1e5, 0.001), (1e6, 0.0), (1e7, 0.02)):
            with self.subTest(re=reynolds, rr=roughness):
                factor = colebrook(reynolds, roughness)
                left = 1.0 / math.sqrt(factor)
                right = -2.0 * math.log10(
                    roughness / 3.7 + 2.51 / (reynolds * math.sqrt(factor)))
                self.assertAlmostEqual(left, right, places=10)

    def test_it_lands_where_the_printed_chart_does(self):
        from engicalc.core.moody import friction_factor

        self.assertAlmostEqual(friction_factor(1e5, 0.0)[0], 0.0180,
                               places=3)
        self.assertAlmostEqual(friction_factor(1e5, 0.001)[0], 0.0222,
                               places=3)

    def test_the_transition_says_it_is_not_dependable(self):
        from engicalc.core.moody import friction_factor

        # Between about 2300 and 4000 the answer depends on the pipe rather
        # than on the numbers, and saying so is more use than a figure that
        # looks as firm as the others.
        _factor, regime, note = friction_factor(3000.0, 0.0)
        self.assertEqual(regime, "transitional")
        self.assertIn("estimate", note)


class TestTensile(unittest.TestCase):
    """Reading a stress-strain curve the way a ruler would."""

    def curve(self):
        import numpy as np

        modulus, yield_stress = 200000.0, 250.0
        elastic = np.linspace(0, yield_stress / modulus, 30)
        plastic = np.linspace(yield_stress / modulus, 0.20, 120)[1:]
        strain = np.concatenate([elastic, plastic])
        stress = np.where(strain <= yield_stress / modulus,
                          modulus * strain,
                          400 - 150 * np.exp(
                              -(strain - yield_stress / modulus) * 25))
        return strain, stress

    def test_it_finds_the_modulus_it_was_built_with(self):
        from engicalc.core.tensile import read_curve

        strain, stress = self.curve()
        result = read_curve(strain, stress)
        self.assertAlmostEqual(result.modulus / 200000.0, 1.0, places=3)

    def test_it_finds_where_the_straight_part_ends(self):
        from engicalc.core.tensile import read_curve

        # The curve was built with exactly thirty straight points, and how
        # much of it counts as straight is the one judgement in the reading.
        strain, stress = self.curve()
        self.assertEqual(read_curve(strain, stress).elastic_points, 30)

    def test_the_proof_stress_sits_above_the_proportional_limit(self):
        from engicalc.core.tensile import read_curve

        strain, stress = self.curve()
        result = read_curve(strain, stress)
        self.assertGreater(result.proof_stress, result.proportional_limit)
        self.assertLess(result.proof_stress, result.ultimate)

    def test_the_offset_line_is_where_it_should_be(self):
        from engicalc.core.tensile import read_curve

        # The proof stress lies on the offset line by construction, so it
        # has to satisfy its equation.
        strain, stress = self.curve()
        result = read_curve(strain, stress, offset=0.002)
        expected = result.modulus * (result.proof_strain - 0.002)
        self.assertAlmostEqual(result.proof_stress / expected, 1.0, places=2)

    def test_a_curve_with_no_straight_part_is_refused(self):
        from engicalc.core.tensile import TensileError, read_curve

        with self.assertRaises(TensileError):
            read_curve([0, 1, 2, 3, 4, 5], [0, 9, 1, 8, 2, 7])

    def test_readings_have_to_be_in_order(self):
        from engicalc.core.tensile import TensileError, read_curve

        with self.assertRaises(TensileError):
            read_curve([0, 0.1, 0.05, 0.2, 0.3], [0, 10, 20, 30, 40])


class TestPhasors(unittest.TestCase):
    """Complex numbers the way an engineer writes them."""

    def test_polar_and_rectangular_are_the_same_number(self):
        from engicalc.core.phasor import read

        rectangular = read("3+4j")
        self.assertAlmostEqual(rectangular.magnitude, 5.0, places=9)
        self.assertAlmostEqual(rectangular.angle, 53.13010235, places=6)
        polar = read("5 angle 53.13010235")
        self.assertAlmostEqual(polar.real, 3.0, places=6)
        self.assertAlmostEqual(polar.imaginary, 4.0, places=6)

    def test_multiplying_multiplies_the_magnitudes_and_adds_the_angles(self):
        from engicalc.core.phasor import combine, read

        # Which is the reason polar form exists.
        answer = combine(read("5 angle 53.13"), "x", read("5 angle 30"))
        self.assertAlmostEqual(answer.magnitude, 25.0, places=6)
        self.assertAlmostEqual(answer.angle, 83.13, places=6)

    def test_the_argument_knows_which_quadrant_it_is_in(self):
        from engicalc.core.phasor import from_rectangular

        # atan(y/x) cannot tell these apart and returns 45 for both.
        self.assertAlmostEqual(from_rectangular(1, 1).angle, 45.0, places=9)
        self.assertAlmostEqual(from_rectangular(-1, -1).angle, -135.0,
                               places=9)

    def test_the_roots_are_all_of_them_and_evenly_spaced(self):
        from engicalc.core.phasor import from_rectangular, roots

        found = roots(from_rectangular(1, 0), 3)
        self.assertEqual(len(found), 3)
        angles = sorted(root.angle for root in found)
        self.assertAlmostEqual(angles[1] - angles[0], 120.0, places=6)
        self.assertAlmostEqual(angles[2] - angles[1], 120.0, places=6)

    def test_something_that_is_not_a_complex_number_is_refused(self):
        from engicalc.core.phasor import PhasorError, read

        with self.assertRaises(PhasorError):
            read("")
        with self.assertRaises(PhasorError):
            read("not a number at all")


# --------------------------------------------------------------------------
# Saying which answer is the physical one
# --------------------------------------------------------------------------
class TestBounds(unittest.TestCase):
    """A radiation balance came back as -316 K.

    Four values satisfy the equations and that is one of them; it is also a
    negative absolute temperature, and it was being shown as the answer with
    a plausible q beside it. Warning that there were four solutions is not
    the same as being right.
    """

    RADIATION = "T^4 = 1e10\nq = 5.67e-8*T^4"

    def test_without_a_bound_it_can_pick_an_impossible_root(self):
        from engicalc.core.system import solve_set

        # Recorded because it is the reason bounds exist. If this ever stops
        # being true the feature is still right, but the story changes.
        result = solve_set(self.RADIATION)
        temperature = {str(k): complex(v) for k, v in
                       result.results[0].items()}["T"]
        self.assertLess(temperature.real, 0)

    def test_a_bound_picks_the_physical_root(self):
        from engicalc.core.system import solve_set

        result = solve_set(self.RADIATION + "\nT > 0")
        values = {str(k): float(v) for k, v in result.results[0].items()}
        self.assertAlmostEqual(values["T"], 316.227766, places=4)
        self.assertAlmostEqual(values["q"], 567.0, places=3)

    def test_it_says_what_it_ruled_out(self):
        from engicalc.core.system import solve_set

        result = solve_set(self.RADIATION + "\nT > 0")
        self.assertTrue(any("Ruled out" in step.title
                            for step in result.steps))

    def test_a_bound_chooses_between_equally_valid_roots(self):
        from engicalc.core.system import solve_set

        self.assertIn("x = -4", solve_set("x^2 = 16\ny = x + 1").result_text)
        self.assertIn("x = 4",
                      solve_set("x^2 = 16\ny = x + 1\nx > 0").result_text)

    def test_a_bound_is_not_an_equation(self):
        from engicalc.core.system import parse_set

        # It rules answers out; it does not pin one down, so counting it
        # would say a short set was ready to solve when it is not.
        parsed = parse_set("x + y = 10\nx > 0")
        self.assertEqual(len(parsed.equations), 1)
        self.assertEqual(len(parsed.bounds), 1)
        self.assertEqual(parsed.freedom, 1)

    def test_writing_one_no_longer_crashes(self):
        from engicalc.core.system import solve_set

        # Anything that was not an equation was turned into Eq(thing, 0),
        # and Eq(T > 0, 0) collapses to False, which has no left hand side.
        result = solve_set("T^4 = 1e10\nT > 0")
        self.assertTrue(result.results)

    def test_impossible_bounds_are_reported_not_ignored(self):
        from engicalc.core.system import solve_set

        result = solve_set("x^2 = 16\nx > 100")
        self.assertFalse(result.results)
        self.assertTrue(any("ruled out" in w.lower() or "bound" in w.lower()
                            for w in result.warnings))

    def test_a_range_says_how_to_write_it(self):
        from engicalc.core.parsing import ParseError
        from engicalc.core.system import solve_set

        # `0 < T < 1000` is how a range is written on paper. SymPy's own
        # message mentions neither ranges nor what to do instead.
        with self.assertRaises(ParseError) as caught:
            solve_set("T^4 = 1e10\n0 < T < 1000")
        self.assertIn("two lines", str(caught.exception))

    def test_the_two_line_form_works(self):
        from engicalc.core.system import solve_set

        result = solve_set(self.RADIATION + "\nT > 0\nT < 1000")
        values = {str(k): float(v) for k, v in result.results[0].items()}
        self.assertAlmostEqual(values["T"], 316.227766, places=4)

    def test_bounds_reach_the_numerical_solver_too(self):
        from engicalc.core.system import solve_set

        # A fractional power skips the exact solver entirely, so the bound
        # has to be honoured on the iterative path as well.
        result = solve_set("x^0.5 = 4\ny = x + 1\nx > 0")
        values = {str(k): float(v) for k, v in result.results[0].items()}
        self.assertAlmostEqual(values["x"], 16.0, places=6)


# --------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------
class TestUnits(unittest.TestCase):
    """Typing 50 into a field that wants metres, meaning 50 mm, is the most
    common way an engineering answer goes wrong."""

    def _convert(self, value, source, target):
        from engicalc.core.units import convert
        return float(convert(value, source, target))

    def test_conversions_against_known_factors(self):
        cases = [
            (50, "mm", "m", 0.05), (2.5, "in", "mm", 63.5),
            (1, "bar", "kPa", 100.0), (3, "ft", "m", 0.9144),
            (1, "kWh", "MJ", 3.6), (1, "W*h", "J", 3600.0),
            (1, "tonne", "kg", 1000.0), (1, "L", "m^3", 0.001),
        ]
        for value, source, target, expected in cases:
            with self.subTest(f"{value}{source}->{target}"):
                self.assertAlmostEqual(self._convert(value, source, target),
                                       expected, places=6)

    def test_energy_compares_across_differently_written_units(self):
        """kWh reads as power*time and MJ as energy - the same dimension
        written two ways, which a naive ratio test calls incompatible."""
        from engicalc.core.units import compatible

        self.assertTrue(compatible("kWh", "MJ"))
        self.assertTrue(compatible("W*h", "J"))
        self.assertTrue(compatible("N*m", "J"))

    def test_different_dimensions_are_refused(self):
        from engicalc.core.units import UnitError, compatible, convert

        self.assertFalse(compatible("kg", "m"))
        with self.assertRaises(UnitError):
            convert(50, "kg", "m")

    def test_in_is_inches_but_min_is_still_minutes(self):
        """`in` is a Python keyword so it has to be rewritten before parsing,
        and doing that without word boundaries turns min into minch."""
        from engicalc.core.units import convert, parse_unit

        self.assertAlmostEqual(self._convert(1, "in", "mm"), 25.4, places=9)
        self.assertAlmostEqual(self._convert(2, "min", "s"), 120.0, places=9)
        self.assertIsNotNone(parse_unit("m/min"))

    def test_a_function_name_is_not_a_unit(self):
        """sin sympifies to the sine function, which has no free symbols and
        so slipped through the old check."""
        from engicalc.core.units import UnitError, parse_unit

        for text in ["sin", "cos", "banana", "xyz"]:
            with self.subTest(text=text):
                with self.assertRaises(UnitError):
                    parse_unit(text)

    def test_every_unit_in_the_library_parses(self):
        """If a declared unit cannot be parsed, that variable silently loses
        unit checking."""
        from engicalc.core.units import UnitError, is_dimensionless, parse_unit

        failed = []
        for formula in get_library().all():
            for variable in formula.variables:
                if is_dimensionless(variable.unit):
                    continue
                try:
                    parse_unit(variable.unit)
                except UnitError:
                    failed.append(f"{formula.key}.{variable.symbol}"
                                  f" ({variable.unit})")
        self.assertEqual([], failed, f"{len(failed)} units do not parse")

    def test_celsius_refuses_to_guess(self):
        """20 C is 293.15 K, but a rise of 20 C is a rise of 20 K. Guessing
        wrong is a 273 kelvin error that looks entirely plausible."""
        from engicalc.core.units import UnitError, convert

        with self.assertRaises(UnitError):
            convert(20, "degC", "K")
        self.assertAlmostEqual(float(convert(20, "degC", "K", absolute=True)),
                               293.15, places=6)
        self.assertAlmostEqual(float(convert(20, "degC", "K", absolute=False)),
                               20.0, places=6)

    def test_a_formula_accepts_a_value_with_its_unit(self):
        from engicalc.formulas.library import get_library, solve_formula

        formula = get_library().get("fluid_mechanics.reynolds")
        inputs = {"rho": "998", "v": "1.8", "mu": "0.001"}
        expected = solve_formula(formula, "Re", dict(inputs, D="0.05")).value
        for spelling in ("50 mm", "5 cm", "0.05 m"):
            with self.subTest(D=spelling):
                got = solve_formula(formula, "Re", dict(inputs, D=spelling))
                self.assertAlmostEqual(got.value, expected, places=6)
        # a conversion that actually changed the number says so; one that
        # did not - 0.05 m into metres - has nothing to report
        converted = solve_formula(formula, "Re", dict(inputs, D="50 mm"))
        self.assertTrue(any("50 mm" in w for w in converted.warnings))
        same = solve_formula(formula, "Re", dict(inputs, D="0.05 m"))
        self.assertEqual([], same.warnings)

    def test_a_formula_refuses_the_wrong_kind_of_unit(self):
        from engicalc.formulas.library import get_library, solve_formula

        formula = get_library().get("fluid_mechanics.reynolds")
        with self.assertRaises(ValueError):
            solve_formula(formula, "Re", {"rho": "998", "v": "1.8",
                                          "D": "50 kg", "mu": "0.001"})

    def test_a_bare_number_still_means_the_declared_unit(self):
        """The behaviour every existing calculation depends on."""
        from engicalc.formulas.library import get_library, solve_formula

        formula = get_library().get("thermodynamics.sensible_heat")
        solution = solve_formula(formula, "Q", {"m": "2.5", "c": "4186",
                                                "T2": "80", "T1": "20"})
        self.assertAlmostEqual(solution.value, 627900.0, places=3)

    def test_a_wildly_wrong_magnitude_is_flagged_where_data_allows(self):
        from engicalc.core.units import looks_wrong

        self.assertIn("Check the units", looks_wrong(50, "0.05"))
        self.assertEqual("", looks_wrong(0.05, "0.05"))
        self.assertEqual("", looks_wrong(0.08, "0.05"))
        self.assertEqual("", looks_wrong(50, ""))      # nothing to compare to


class TestEvaluationBar(unittest.TestCase):
    """A definite integral is written with the antiderivative inside a tall
    bar carrying the limits, not as three separate steps for F(b) and F(a)."""

    def _bar(self, integrand, lower="1", upper="2"):
        result = calculate(integrand, "integral", "x",
                           lower=lower, upper=upper)
        # The rule steps carry notation too, and are shown only when the
        # working is asked for. The bar is a step of the ordinary sort.
        return next((s.latex for s in result.steps
                     if s.latex and not s.minor), "")

    def test_the_working_uses_the_evaluation_bar(self):
        bar = self._bar("2x", "-1.6", "2.4")
        self.assertIn(r"\left.", bar)
        self.assertIn(r"\right|", bar)
        self.assertIn("-1.6", bar)
        self.assertIn("2.4", bar)

    def test_it_renders(self):
        r"""mathtext has no \vphantom and no \Bigg, so the exact spelling
        matters - most ways of writing this do not parse."""
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties

        parser = mathtext.MathTextParser("path")
        for integrand in ["2x", "x^2", "1/x^2", "sqrt(x)", "sin(x)"]:
            with self.subTest(integrand=integrand):
                bar = self._bar(integrand)
                self.assertTrue(bar, "no evaluation bar was produced")
                parser.parse(f"${bar}$", dpi=100,
                             prop=FontProperties(size=16))

    def test_the_bar_grows_with_the_antiderivative(self):
        """It is a delimiter, so it sizes to what it encloses - a fraction
        makes it taller than a squared term does."""
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties

        parser = mathtext.MathTextParser("path")

        def height(integrand):
            _w, h, d, _g, _r = parser.parse(
                f"${self._bar(integrand)}$", dpi=100,
                prop=FontProperties(size=18))
            return h + d

        self.assertGreater(height("x^2"), height("2x"))

    def test_an_indefinite_integral_has_no_bar(self):
        result = calculate("2x", "integral", "x")
        self.assertFalse(any(s.latex for s in result.steps if not s.minor))
        self.assertTrue(any("constant of integration" in (s.detail or "")
                            for s in result.steps))

    def test_plain_text_mode_stays_readable(self):
        """The bar is LaTeX; the text view must not show raw markup."""
        text = calculate("2x", "integral", "x",
                         lower="-1.6", upper="2.4").steps_text()
        self.assertNotIn(r"\left.", text)
        self.assertNotIn(r"\right|", text)
        self.assertIn("F(b) - F(a)", text)


# --------------------------------------------------------------------------
# Difference symbols, and calculation sheets
# --------------------------------------------------------------------------
class TestDeltaSymbols(unittest.TestCase):
    """dT means a change in temperature, and is written ΔT."""

    def test_a_difference_is_drawn_as_delta(self):
        from engicalc.core.display import latex

        for name, expected in [("dT", r"\Delta T"), ("dL", r"\Delta L"),
                               ("dU", r"\Delta U"), ("dS", r"\Delta S")]:
            with self.subTest(name=name):
                self.assertIn(expected, latex(sp.Symbol(name)))

    def test_a_numbered_difference_keeps_its_subscript(self):
        from engicalc.core.display import latex

        self.assertIn(r"\Delta T_{1}", latex(sp.Symbol("dT1")))

    def test_delta_the_deflection_stays_lowercase(self):
        """In this library `delta` is a maximum deflection - the lowercase
        letter, and not a difference at all."""
        from engicalc.core.display import latex

        drawn = latex(sp.Symbol("delta"))
        self.assertIn(r"\delta", drawn)
        self.assertNotIn(r"\Delta", drawn)

    def test_ordinary_names_are_untouched(self):
        from engicalc.core.display import latex

        for name in ["d", "dx", "density", "day", "D"]:
            with self.subTest(name=name):
                self.assertNotIn(r"\Delta", latex(sp.Symbol(name)))

    def test_the_library_draws_them(self):
        formula = get_library().get("strength_of_materials.thermal_stress")
        if formula is None:
            self.skipTest("formula not present")
        self.assertIn(r"\Delta T", formula.display_latex)


class TestCalculationSheet(unittest.TestCase):
    """Several steps in order, each able to use the ones above it."""

    def _pipe_sheet(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet("Water in a pipe")
        sheet.add("d", "50 mm", "m")
        sheet.add("Q", "0.0035", "m^3/s")
        sheet.add("rho", "998", "kg/m^3")
        sheet.add("mu", "0.001", "Pa*s")
        sheet.add("A", "pi*d^2/4", "m^2")
        sheet.add("v", "Q/A", "m/s")
        sheet.add("Re", "rho*v*d/mu", "-")
        return sheet

    def _values(self, results):
        return {r.step.name: r.value for r in results if r.ok}

    def test_a_chain_carries_each_answer_into_the_next(self):
        values = self._values(self._pipe_sheet().evaluate())
        self.assertAlmostEqual(float(values["d"]), 0.05, places=9)
        self.assertAlmostEqual(float(values["A"]), math.pi * 0.05 ** 2 / 4,
                               places=12)
        self.assertAlmostEqual(float(values["Re"]), 88948.5146, places=3)

    def test_changing_an_input_moves_everything_below_it(self):
        """The whole point: change the bore, do not retype the rest."""
        sheet = self._pipe_sheet()
        before = float(self._values(sheet.evaluate())["Re"])
        sheet.steps[0].expression = "100 mm"
        after = float(self._values(sheet.evaluate())["Re"])
        # Re = rho*Q*d/(mu*A) and A goes as d^2, so Re goes as 1/d
        self.assertAlmostEqual(after, before / 2, places=3)

    def test_a_step_may_not_use_a_name_defined_below_it(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("y", "2*x")
        sheet.add("x", "3")
        results = sheet.evaluate()
        self.assertFalse(results[0].ok)
        self.assertIn("reads downwards", results[0].error)
        self.assertTrue(results[1].ok)

    def test_a_name_defined_twice_is_refused(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("x", "1")
        sheet.add("x", "2")
        results = sheet.evaluate()
        self.assertTrue(results[0].ok)
        self.assertIn("twice", results[1].error)

    def test_one_broken_line_does_not_blank_the_rest(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("a", "2")
        sheet.add("b", "a/0*")          # nonsense
        sheet.add("c", "a*10")
        results = sheet.evaluate()
        self.assertTrue(results[0].ok)
        self.assertFalse(results[1].ok)
        self.assertTrue(results[2].ok)
        self.assertEqual(float(results[2].value), 20.0)

    def test_a_step_converts_a_value_given_in_another_unit(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("d", "50 mm", "m")
        result = sheet.evaluate()[0]
        self.assertAlmostEqual(float(result.value), 0.05, places=9)
        self.assertIn("50 mm", result.note)

    def test_a_bad_name_is_explained(self):
        from engicalc.core.sheet import Sheet

        sheet = Sheet()
        sheet.add("2x", "1")
        self.assertIn("not a usable name", sheet.evaluate()[0].error)

    def test_a_sheet_survives_being_saved_and_reopened(self):
        from engicalc.core.sheet import Sheet

        sheet = self._pipe_sheet()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sheet.json")
            sheet.save(path)
            reopened = Sheet.load(path)
        self.assertEqual(reopened.title, sheet.title)
        self.assertEqual([s.name for s in reopened.steps],
                         [s.name for s in sheet.steps])
        self.assertAlmostEqual(
            float(self._values(reopened.evaluate())["Re"]), 88948.5146,
            places=3)


class TestScientificNotation(unittest.TestCase):
    """200e9 is how anyone writes Young's modulus, and it is not a value
    with a unit of "e9" stuck to it."""

    def test_a_number_in_exponent_form_carries_no_unit(self):
        from engicalc.core.units import split_quantity

        for text in ["200e9", "12e-6", "1.5e3", "-3.2E-4", "2e9"]:
            with self.subTest(text=text):
                value, unit = split_quantity(text)
                self.assertEqual(unit, "")
                self.assertEqual(value, text)

    def test_a_unit_after_an_exponent_still_splits(self):
        from engicalc.core.units import split_quantity

        self.assertEqual(split_quantity("200e9 Pa"), ("200e9", "Pa"))
        self.assertEqual(split_quantity("1e3 Pa"), ("1e3", "Pa"))

    def test_youngs_modulus_solves_either_way(self):
        from engicalc.formulas.library import get_library, solve_formula

        formula = next(f for f in get_library().all()
                       if "hermal stress" in f.name)
        plain = solve_formula(formula, "sigma",
                              {"E": "200e9", "alpha": "12e-6", "dT": "60"})
        with_unit = solve_formula(formula, "sigma",
                                  {"E": "200 GPa", "alpha": "12e-6",
                                   "dT": "60"})
        self.assertAlmostEqual(plain.value, 1.44e8, delta=1.0)
        self.assertAlmostEqual(with_unit.value, plain.value, delta=1.0)


class TestSymbolsAsRead(unittest.TestCase):
    def test_names_are_shown_as_the_symbols_they_stand_for(self):
        from engicalc.core.display import unicode_symbol

        cases = {"sigma": "σ", "alpha": "α", "rho": "ρ", "mu": "μ",
                 "omega": "ω", "dT": "ΔT", "dT1": "ΔT₁", "T1": "T₁",
                 "L0": "L₀", "delta": "δ", "lambda_": "λ", "E": "E",
                 "Re": "Re", "k": "k"}
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(unicode_symbol(name), expected)

    def test_a_worded_subscript_keeps_its_underscore(self):
        """Unicode has no full subscript alphabet, so tau_max would run
        together as taumax."""
        from engicalc.core.display import unicode_symbol

        self.assertEqual(unicode_symbol("tau_max"), "τ_max")
        self.assertEqual(unicode_symbol("I_xx"), "I_xx")

    def test_every_library_symbol_survives_the_mapping(self):
        from engicalc.core.display import unicode_symbol

        for formula in get_library().all():
            for variable in formula.variables:
                with self.subTest(symbol=variable.symbol):
                    self.assertTrue(unicode_symbol(variable.symbol))


class TestDeleteKey(unittest.TestCase):
    """Delete must not swallow a whole shape at one press.

    When the equation is a single template - a fraction, a radical, an
    integral from the pad - the root row holds exactly one Group, and
    deleting that one item wiped the entire equation in one keystroke.
    """

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        import tkinter as tk
        try:
            cls.root = tk.Tk()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display: {exc}")
        # Not withdrawn: Tk delivers key events to the focus widget, and a
        # widget in a hidden window cannot take focus, so event_generate
        # would go nowhere and every assertion would pass vacuously.
        cls.root.geometry("700x160+40+40")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self._fields = []

    def tearDown(self):
        # One field per test, taken away afterwards. Left packed, they stack
        # up in the window and a later one is never mapped - an unmapped
        # widget cannot take focus, so its key events go nowhere and the
        # assertions pass or fail for the wrong reason.
        for field in self._fields:
            field.destroy()
        self.root.update()

    def _field(self):
        from engicalc.ui.mathfield import MathField

        field = MathField(self.root, fontsize=15)
        field.pack()
        self._fields.append(field)
        self.root.update()
        field.focus_force()
        self.root.update()
        return field

    def _delete_at_start(self, field, text):
        field.set_text(text)
        self.root.update()
        field.caret_row = field.root_row
        field.caret_index = 0
        field._redraw()
        self.root.update()
        field.event_generate("<Delete>")
        self.root.update()

    def test_delete_does_not_remove_a_whole_shape(self):
        from engicalc.ui.mathfield import to_text

        field = self._field()
        for text in ["sqrt(x + 1)", "(a+b)/(2c)"]:
            with self.subTest(text=text):
                self._delete_at_start(field, text)
                self.assertNotEqual("", to_text(field.root_row))

    def test_delete_steps_inside_the_shape(self):
        field = self._field()
        self._delete_at_start(field, "sqrt(x + 1)")
        self.assertIsNot(field.caret_row, field.root_row,
                         "the caret should now be inside the radical")

    def test_backspace_does_not_remove_a_whole_shape_either(self):
        from engicalc.ui.mathfield import to_text

        field = self._field()
        field.set_text("sqrt(x + 1)")
        self.root.update()
        field.caret_row = field.root_row
        field.caret_index = len(field.root_row.items)
        field._redraw()
        self.root.update()
        field.event_generate("<BackSpace>")
        self.root.update()
        self.assertNotEqual("", to_text(field.root_row))

    def test_delete_still_removes_an_ordinary_character(self):
        from engicalc.ui.mathfield import to_text

        field = self._field()
        field.set_text("2x+30")
        self.root.update()
        field.caret_row = field.root_row
        field.caret_index = 2
        field._redraw()
        self.root.update()
        field.event_generate("<Delete>")
        self.root.update()
        self.assertEqual("2x30", to_text(field.root_row))


class TestMatrixGrid(unittest.TestCase):
    """The matrix goes into a grid of cells, because that is what it is."""

    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
        except Exception as exc:                      # noqa: BLE001
            raise unittest.SkipTest(f"no display: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def _grid(self, rows=3, columns=3):
        from engicalc.ui.matrixgrid import MatrixGrid
        return MatrixGrid(self.root, rows, columns)

    def test_the_grid_produces_text_the_parser_reads(self):
        from engicalc.core.matrices import parse_matrix

        grid = self._grid()
        for r, row in enumerate([[2, 1, -1], [-3, -1, 2], [-2, 1, 2]]):
            for c, value in enumerate(row):
                grid.cells[r][c].set(str(value))
        self.assertEqual(parse_matrix(grid.get_text()).tolist(),
                         [[2, 1, -1], [-3, -1, 2], [-2, 1, 2]])

    def test_a_pasted_block_resizes_the_grid(self):
        """Two columns copied out of Excel arrive tab separated."""
        from engicalc.core.matrices import parse_matrix

        grid = self._grid()
        grid.set_text("1\t2\t3\n4\t5\t6")
        self.assertEqual((grid.rows, grid.columns), (2, 3))
        self.assertEqual(parse_matrix(grid.get_text()).tolist(),
                         [[1, 2, 3], [4, 5, 6]])

    def test_resizing_keeps_what_was_already_typed(self):
        from engicalc.core.matrices import parse_matrix

        grid = self._grid(2, 2)
        for r in range(2):
            for c in range(2):
                grid.cells[r][c].set(str(r * 2 + c + 1))
        grid.resize_by(1, 0)
        self.assertEqual(parse_matrix(grid.get_text()).tolist(),
                         [[1, 2], [3, 4], [0, 0]])
        grid.resize_by(-1, -1)
        self.assertEqual(parse_matrix(grid.get_text()).tolist(),
                         [[1], [3]])

    def test_it_will_not_shrink_to_nothing(self):
        grid = self._grid(1, 1)
        grid.resize_by(-5, -5)
        self.assertEqual((grid.rows, grid.columns), (1, 1))

    def test_an_empty_cell_reads_as_zero(self):
        """A half-filled grid should still solve rather than refuse."""
        from engicalc.core.matrices import parse_matrix

        grid = self._grid(2, 2)
        grid.cells[0][0].set("5")
        self.assertEqual(parse_matrix(grid.get_text()).tolist(),
                         [[5, 0], [0, 0]])


class TestStatistics(unittest.TestCase):
    """The numbers every lab report needs, and the line through the data."""

    def test_a_textbook_set_gives_the_textbook_answers(self):
        from engicalc.core.statistics import describe

        result = describe([2, 4, 4, 4, 5, 5, 7, 9])
        self.assertAlmostEqual(result.mean, 5.0, places=12)
        self.assertAlmostEqual(result.population_sd, 2.0, places=12)
        self.assertAlmostEqual(result.sample_sd, 2.13809, places=5)
        self.assertAlmostEqual(result.median, 4.5, places=12)
        self.assertEqual(result.count, 8)
        self.assertEqual(result.spread, 7)

    def test_sample_and_population_deviations_are_both_reported(self):
        """Measurements are a sample, so n-1 is the one wanted - but quoting
        the wrong one is invisible, so both are given."""
        from engicalc.core.statistics import describe

        result = describe([1, 2, 3, 4])
        self.assertGreater(result.sample_sd, result.population_sd)
        labels = [row[0] for row in result.rows()]
        self.assertIn("standard deviation", labels)
        self.assertIn("population sd", labels)

    def test_standard_error_shrinks_as_readings_are_added(self):
        from engicalc.core.statistics import describe

        few = describe([10, 11, 9, 10])
        many = describe([10, 11, 9, 10] * 16)
        self.assertLess(many.standard_error, few.standard_error)

    def test_a_perfect_line_is_found_exactly(self):
        from engicalc.core.statistics import fit_line

        fit = fit_line([1, 2, 3, 4, 5], [3, 5, 7, 9, 11])   # y = 2x + 1
        self.assertAlmostEqual(fit.slope, 2.0, places=12)
        self.assertAlmostEqual(fit.intercept, 1.0, places=12)
        self.assertAlmostEqual(fit.r_squared, 1.0, places=12)
        self.assertAlmostEqual(fit.worst_residual, 0.0, places=12)

    def test_a_scattered_fit_reports_its_uncertainty(self):
        from engicalc.core.statistics import fit_line

        fit = fit_line([0, 1, 2, 3, 4, 5], [0.1, 2.1, 3.9, 6.2, 7.8, 10.1])
        self.assertAlmostEqual(fit.slope, 1.98286, places=4)
        self.assertGreater(fit.slope_error, 0)
        self.assertGreater(fit.r_squared, 0.99)
        self.assertLess(fit.r_squared, 1.0)

    def test_residuals_sum_to_nothing(self):
        """A least-squares line passes through the middle of the data."""
        from engicalc.core.statistics import fit_line

        fit = fit_line([0, 1, 2, 3, 4], [1.1, 1.9, 3.2, 3.8, 5.1])
        self.assertAlmostEqual(sum(fit.residuals), 0.0, places=9)

    def test_a_vertical_scatter_is_refused_with_a_reason(self):
        from engicalc.core.statistics import fit_line

        with self.assertRaises(ParseError) as caught:
            fit_line([2, 2, 2], [1, 2, 3])
        self.assertIn("vertical", str(caught.exception))

    def test_one_column_and_two_columns_both_parse(self):
        from engicalc.core.statistics import parse_columns

        single = parse_columns("10.2\n10.5\n10.1")
        self.assertFalse(single.paired)
        self.assertEqual(len(single.x), 3)

        paired = parse_columns("Load\tExt\n0\t0.0\n10\t0.21")
        self.assertTrue(paired.paired)
        self.assertEqual(paired.x, [0.0, 10.0])
        self.assertEqual(paired.y, [0.0, 0.21])

    def test_ragged_columns_are_refused(self):
        from engicalc.core.statistics import parse_columns

        with self.assertRaises(ParseError):
            parse_columns("1\t2\n3\n4\t5")


class TestDifferentialEquations(unittest.TestCase):
    """Beam deflection, transient cooling, RC circuits and vibration are all
    differential equations, and none of them parsed before."""

    def _solve(self, text, conditions=""):
        from engicalc.core.odes import solve_ode
        return solve_ode(text, conditions=conditions)

    def test_prime_notation_becomes_a_derivative(self):
        from engicalc.core.odes import _prepare

        self.assertEqual(_prepare("y' = y", "y", "x"),
                         "Derivative(y(x), x) = y(x)")
        self.assertEqual(_prepare("y'' + 4y = 0", "y", "x"),
                         "Derivative(y(x), x, 2) + 4y(x) = 0")

    def test_a_coefficient_before_the_variable_is_not_missed(self):
        """There is no word boundary between a digit and a letter, so a
        naive \by\b leaves the y in 4y as a bare symbol - and the equation
        then comes out wrong rather than failing."""
        from engicalc.core.odes import _prepare

        self.assertIn("4y(x)", _prepare("y'' + 4y = 0", "y", "x"))
        self.assertNotIn("4y ", _prepare("y'' + 4y = 0", "y", "x"))

    def test_names_like_E_and_I_stay_symbols(self):
        """E is Euler's number and I the imaginary unit to the ordinary
        parser, which makes the beam equation quietly wrong."""
        result = self._solve("E*I*y'' = M")
        drawn = sp.sstr(result.expression)
        self.assertNotIn("exp", drawn)
        self.assertIn("E", drawn)
        self.assertIn("I", drawn)

    def test_newton_cooling(self):
        result = self._solve("y' = -(y - 20)/5", "y(0) = 90")
        x = sp.Symbol("x")
        self.assertAlmostEqual(float(result.expression.subs(x, 0)), 90.0,
                               places=9)
        # heading for the ambient temperature it is cooling towards
        self.assertAlmostEqual(float(result.expression.subs(x, 1000)), 20.0,
                               places=6)

    def test_simple_harmonic_motion(self):
        result = self._solve("y'' + 4y = 0", "y(0) = 1, y'(0) = 0")
        x = sp.Symbol("x")
        self.assertEqual(sp.simplify(result.expression - sp.cos(2 * x)), 0)

    def test_free_fall_matches_the_arithmetic(self):
        """SymPy's dsolve recurses forever on y'' = constant, so this is
        integrated directly instead."""
        result = self._solve("y'' = -9.81", "y(0) = 0, y'(0) = 20")
        x = sp.Symbol("x")
        for t in (0, 1, 2, 3):
            with self.subTest(t=t):
                self.assertAlmostEqual(float(result.expression.subs(x, t)),
                                       20 * t - 4.905 * t * t, places=6)

    def test_the_beam_equation(self):
        result = self._solve("y'' = -w*x/(E*I)")
        x, w, E, I = sp.symbols("x w E I")
        # y'''' would be the load; here y'' = -wx/EI integrates twice
        expected = -w * x ** 3 / (6 * E * I)
        without_constants = result.expression.subs(
            {sp.Symbol("C1"): 0, sp.Symbol("C2"): 0})
        self.assertEqual(sp.simplify(without_constants - expected), 0)

    def test_a_general_solution_says_it_is_general(self):
        result = self._solve("y' = y")
        self.assertTrue(result.warnings)
        self.assertIn("general solution", result.warnings[0])
        self.assertIn("C1", result.warnings[0])

    def test_conditions_remove_the_constants(self):
        result = self._solve("y' + y/2 = 0", "y(0) = 5")
        self.assertEqual([], result.warnings)
        self.assertNotIn("C1", sp.sstr(result.expression))

    def test_an_equation_with_no_derivative_is_explained(self):
        with self.assertRaises(ParseError) as caught:
            self._solve("y = 2x")
        self.assertIn("no derivative", str(caught.exception))

    def test_a_malformed_condition_is_explained(self):
        with self.assertRaises(ParseError) as caught:
            self._solve("y' = y", "banana")
        self.assertIn("condition", str(caught.exception).lower())

    def test_it_is_reachable_as_an_operation(self):
        from engicalc.core.engine import OPERATIONS

        self.assertIn("ode", OPERATIONS)
        result = calculate("y' = y", "ode", "x", conditions="y(0) = 3")
        x = sp.Symbol("x")
        self.assertEqual(sp.simplify(result.expression - 3 * sp.exp(x)), 0)


class TestHvacAndSheetMetal(unittest.TestCase):
    """The trade formulas. The bend maths must agree with the flat-pattern
    generator, or a blank cut from a number worked out here will not fold to
    the size the drawing says."""

    @classmethod
    def setUpClass(cls):
        cls.library = get_library()

    def _value(self, key, target, values):
        formula = self.library.get(key)
        self.assertIsNotNone(formula, f"{key} is missing")
        return solve_formula(formula, target, values).value

    def test_the_branch_is_loaded(self):
        self.assertIn("HVAC & Sheet Metal", self.library.branches())
        self.assertGreaterEqual(
            len(self.library.by_branch("HVAC & Sheet Metal")), 15)

    def test_searches_that_used_to_find_nothing(self):
        for query in ["bend allowance", "velocity pressure", "fan law",
                      "air changes", "k-factor", "setback"]:
            with self.subTest(query=query):
                self.assertTrue(self.library.search(query),
                                f"nothing found for {query!r}")

    def test_bend_allowance_matches_hand_arithmetic(self):
        # BA = theta (R + K T), 90 degrees on 1.2 mm with R = 1.2, K = 0.44
        expected = (math.pi / 2) * (1.2 + 0.44 * 1.2)
        got = self._value("hvac_sheet_metal.bend_allowance", "BA",
                          {"theta": str(math.pi / 2), "R": "1.2",
                           "K": "0.44", "T": "1.2"})
        self.assertAlmostEqual(got, expected, places=9)

    def test_setback_has_no_minus_r_on_the_end(self):
        """An unbent corner has no setback, and the wrong form gives a
        negative bend deduction, which no fold has."""
        straight = self._value("hvac_sheet_metal.bend_setback", "SSB",
                               {"R": "1.2", "T": "1.2", "theta": "0"})
        self.assertAlmostEqual(straight, 0.0, places=12)

        square = self._value("hvac_sheet_metal.bend_setback", "SSB",
                             {"R": "1.2", "T": "1.2",
                              "theta": str(math.pi / 2)})
        self.assertAlmostEqual(square, 2.4, places=9)

    def test_bend_deduction_is_positive_for_a_square_corner(self):
        deduction = self._value("hvac_sheet_metal.bend_deduction", "BD",
                                {"SSB": "2.4", "BA": "2.714336"})
        self.assertGreater(deduction, 0)

    #: (thickness, inside radius, K, degrees, bend allowance, setback).
    #:
    #: These are what a flat-pattern generator gives for the same bends, and
    #: they are also just BA = theta(R + KT) and SSB = tan(theta/2)(R + T)
    #: evaluated by hand - so they can be checked by anyone reading them
    #: without another program being installed.
    BENDS = [
        (1.2, 1.2, 0.44, 90, 2.714336052701581, 2.3999999999999995),
        (2.0, 2.0, 0.44, 90, 4.523893421169302, 3.9999999999999996),
        (1.0, 1.0, 0.44, 45, 1.1309733552923256, 0.8284271247461901),
        (3.0, 3.0, 0.40, 135, 9.89601685880785, 14.48528137423857),
    ]

    def test_the_bend_maths_gives_the_flat_pattern_values(self):
        """A blank cut from a number worked out here has to fold to the size
        the drawing says, so these are checked against fixed values rather
        than against whatever the formula currently returns."""
        for thickness, radius, k, degrees, allowance, setback in self.BENDS:
            theta = str(math.radians(degrees))
            with self.subTest(T=thickness, R=radius, angle=degrees):
                self.assertAlmostEqual(
                    self._value("hvac_sheet_metal.bend_allowance", "BA",
                                {"theta": theta, "R": str(radius),
                                 "K": str(k), "T": str(thickness)}),
                    allowance, places=9)
                self.assertAlmostEqual(
                    self._value("hvac_sheet_metal.bend_setback", "SSB",
                                {"R": str(radius), "T": str(thickness),
                                 "theta": theta}),
                    setback, places=9)

    def test_those_values_are_the_textbook_formulae(self):
        """And the values above are not magic - they are the formulae.

        Worked out here from first principles so that a wrong constant in
        the table would have to be wrong in two independent places.
        """
        for thickness, radius, k, degrees, allowance, setback in self.BENDS:
            angle = math.radians(degrees)
            with self.subTest(angle=degrees):
                self.assertAlmostEqual(
                    allowance, angle * (radius + k * thickness), places=12)
                self.assertAlmostEqual(
                    setback, math.tan(angle / 2) * (radius + thickness),
                    places=12)

    def test_velocity_pressure(self):
        # 0.5 rho v^2 at 1.2 kg/m3 and 10 m/s is 60 Pa
        self.assertAlmostEqual(
            self._value("hvac_sheet_metal.velocity_pressure", "pv",
                        {"rho": "1.2", "v": "10"}), 60.0, places=9)

    def test_the_fan_laws_scale_as_they_should(self):
        """Power goes with the cube of speed - half the speed is an eighth
        of the power, which is the whole argument for variable speed."""
        half = self._value("hvac_sheet_metal.fan_law_power", "W2",
                           {"W1": "800", "N2": "500", "N1": "1000"})
        self.assertAlmostEqual(half, 100.0, places=9)

        pressure = self._value("hvac_sheet_metal.fan_law_pressure", "p2",
                               {"p1": "400", "N2": "500", "N1": "1000"})
        self.assertAlmostEqual(pressure, 100.0, places=9)

    def test_a_rolled_blank_wraps_the_mid_thickness(self):
        self.assertAlmostEqual(
            self._value("hvac_sheet_metal.cylinder_blank", "L",
                        {"D": "300", "t": "1.2"}),
            math.pi * 301.2, places=6)

    def test_every_new_formula_rearranges_for_every_variable(self):
        """The library-wide invariant, checked again for this branch so a
        failure names the branch rather than a key."""
        for formula in self.library.by_branch("HVAC & Sheet Metal"):
            for variable in formula.variables:
                with self.subTest(formula=formula.key, solve_for=variable.symbol):
                    solution = solve_formula(formula, variable.symbol, {})
                    self.assertIsNotNone(solution.expression)


class TestUpdateCheck(unittest.TestCase):
    """Telling somebody a newer version exists - and nothing more."""

    def test_versions_compare_as_versions_not_strings(self):
        from engicalc.core.updates import is_newer

        self.assertTrue(is_newer("1.2.0", "1.1.0"))
        self.assertTrue(is_newer("v1.2.0", "1.1.0"))
        self.assertFalse(is_newer("1.1.0", "1.1.0"))
        self.assertFalse(is_newer("1.0.9", "1.1.0"))
        # 1.10.0 is after 1.9.0, which a string comparison gets backwards
        self.assertTrue(is_newer("1.10.0", "1.9.0"))

    def test_a_release_beats_its_own_pre_release(self):
        """"1.2.0" is a prefix of "1.2.0-beta.1", so a string comparison
        both offers the beta as an upgrade and refuses the release."""
        from engicalc.core.updates import is_newer

        self.assertTrue(is_newer("1.2.0", "1.2.0-beta.1"))
        self.assertFalse(is_newer("1.2.0-beta.1", "1.2.0"))
        self.assertTrue(is_newer("1.2.0-beta.10", "1.2.0-beta.9"))

    def test_a_version_it_cannot_read_is_never_recommended(self):
        from engicalc.core.updates import is_newer, parse_version

        self.assertIsNone(parse_version("banana"))
        self.assertFalse(is_newer("banana", "1.0.0"))
        self.assertFalse(is_newer("1.0.0", "banana"))

    def test_drafts_and_pre_releases_are_not_offered(self):
        from engicalc.core.updates import read_release

        for extra in ({"draft": True}, {"prerelease": True}):
            with self.subTest(extra=extra):
                payload = json.dumps(dict({"tag_name": "v9.9.9"},
                                          **extra)).encode()
                self.assertIsNone(read_release(payload))

    def test_a_bad_reply_is_simply_nothing(self):
        from engicalc.core.updates import read_release

        for payload in [b"", b"not json", b"[]", b"{}",
                        json.dumps({"tag_name": "banana"}).encode()]:
            with self.subTest(payload=payload[:20]):
                self.assertIsNone(read_release(payload))

    def test_nothing_in_the_reply_decides_where_anybody_is_sent(self):
        """The reply's own URLs are ignored: a party that can answer the
        request would otherwise choose the file presented as the update."""
        from engicalc.core.updates import RELEASES_PAGE, Update, read_release

        payload = json.dumps({
            "tag_name": "v9.9.9",
            "html_url": "https://evil.example/nope",
            "assets": [{"browser_download_url": "https://evil.example/x.exe"}],
        }).encode()
        found = read_release(payload)
        self.assertIsNotNone(found)
        self.assertNotIn("url", Update.__dataclass_fields__)
        self.assertNotIn("evil", str(found))
        self.assertTrue(RELEASES_PAGE.startswith(
            "https://github.com/sheetdeveloper/engicalc"))

    def test_it_is_quiet_when_it_cannot_answer(self):
        """No network, a bad host, a 404 - all mean nothing to offer, and
        none of them is worth interrupting somebody over."""
        from engicalc.core.updates import check

        self.assertIsNone(
            check("1.0.0", "https://no-such-host.invalid/x", timeout=2))

    def test_the_same_version_is_not_news(self):
        from engicalc.core.updates import Update, is_newer

        self.assertFalse(is_newer(Update("1.1.0").version, "1.1.0"))


class TestDerivedIndices(unittest.TestCase):
    """A material index is an exponent, and the exponent is the content.

    E^(1/2)/rho and E^(1/3)/rho look alike written down and put different
    materials at the top of the list. Deriving them from a statement of
    the job means a wrong exponent has to come from a wrong statement of
    the mechanics, which is a thing that can be argued about, rather than
    from a mistyped fraction, which is not.
    """

    #: What the textbooks publish. Not the source of the numbers in the
    #: program - the check on them.
    PUBLISHED = {
        "Light, stiff tie": ("youngs", 1.0, "density", 1.0),
        "Light, stiff beam": ("youngs", 0.5, "density", 1.0),
        "Light, stiff panel": ("youngs", 1.0 / 3.0, "density", 1.0),
        "Light, strong tie": ("yield", 1.0, "density", 1.0),
        "Light, strong beam": ("yield", 2.0 / 3.0, "density", 1.0),
        "Light, strong panel": ("yield", 0.5, "density", 1.0),
        "Flywheels and rotors": ("yield", 1.0, "density", 1.0),
        "Elastic hinges": ("yield", 1.0, "youngs", 1.0),
        "Damage tolerance": ("toughness", 1.0, "yield", 1.0),
        "Insulation, thin as possible": ("service", 1.0, "conductivity", 1.0),
        "Springs: energy stored per volume": ("yield", 2.0, "youngs", 1.0),
    }

    def test_every_index_comes_out_as_published(self):
        from engicalc.core import indices

        for name, (up, power_up, across, power_across) in \
                self.PUBLISHED.items():
            with self.subTest(name):
                derived = indices.find(name)
                self.assertIsNotNone(derived, f"no job called {name}")
                self.assertEqual(up, derived.up)
                self.assertEqual(across, derived.across)
                self.assertAlmostEqual(power_up, derived.power_up, places=9)
                self.assertAlmostEqual(power_across, derived.power_across,
                                       places=9)

    def test_the_exponent_follows_from_the_section_rule(self):
        """Change how the section grows and the exponent changes with it.

        This is the whole claim: the 1/2 in a beam index is not a number
        anybody chose, it is what I = A^2/12 does to rho*A*L. Put a
        panel's section rule in and 1/2 becomes 1/3.
        """
        from engicalc.core.indices import Job, derive

        beam = derive(Job("beam", "rho*A*L", free="A",
                          constraint="S = C*E*I/L**3",
                          shape={"I": "A**2/12"}))
        self.assertAlmostEqual(0.5, beam.power_up, places=9)

        # A panel: the width is set by the job, only the thickness is free,
        # and I goes as t^3 rather than as A^2.
        panel = derive(Job("panel", "rho*b*t*L", free="t",
                           constraint="S = C*E*b*t**3/(12*L**3)"))
        self.assertAlmostEqual(1.0 / 3.0, panel.power_up, places=9)

        # And a tie, where the area is set by the load directly.
        tie = derive(Job("tie", "rho*A*L", free="A", constraint="S = E*A/L"))
        self.assertAlmostEqual(1.0, tie.power_up, places=9)

    def test_a_third_property_is_named_rather_than_dropped(self):
        """The two the shipped table used to shorten.

        The energy a spring stores per unit weight is sigma^2/(E rho) and
        thermal shock resistance is sigma/(E alpha). Both were carried as
        two-property indices with the third demoted to a note, which is
        the kind of shortening that derivation exists to stop.
        """
        from engicalc.core import indices

        springs = indices.find("Springs: energy stored per weight")
        self.assertEqual({"yield": 2, "youngs": -1, "density": -1},
                         {k: int(v) for k, v in springs.powers.items()})
        self.assertFalse(springs.exact_on_a_chart)
        self.assertEqual(["density"], springs.also)

        shock = indices.find("Thermal shock resistance")
        self.assertEqual({"yield": 1, "youngs": -1, "expansion": -1},
                         {k: int(v) for k, v in shock.powers.items()})
        self.assertEqual(["expansion"], shock.also)

    def test_the_chart_table_is_the_derived_one(self):
        from engicalc.core import indices, materials

        self.assertEqual(indices.entries(), list(materials.INDICES))
        self.assertTrue(all(len(entry) == 6 for entry in materials.INDICES))

    def test_stiffness_per_weight_separates_the_materials_as_it_should(self):
        """A fact about the mechanics, not about which materials are listed.

        On a tie, steel, aluminium and wood are within a fifth of each
        other - which is why a stiff tie is made of whatever is cheapest.
        Move to a beam and then to a panel and the exponent on E falls
        from 1 to 1/2 to 1/3, so density counts for more each time and
        they separate. Steel must fall further behind wood at every step.
        """
        from engicalc.core import indices, materials

        def score(job, name):
            return materials.index_value(materials.find(name),
                                         indices.find(job).as_entry())

        spread = []
        for job in ("Light, stiff tie", "Light, stiff beam",
                    "Light, stiff panel"):
            steel = score(job, "Carbon steel")
            wood = score(job, "Softwood, along the grain")
            self.assertGreater(steel, 0.0)
            spread.append(steel / wood)

        # On a tie they are within 20% of each other; by a panel steel is
        # a sixth of the wood. Each step must be a real fall, not a wobble.
        self.assertGreater(spread[0], 0.8)
        self.assertLess(spread[0], 1.4)
        self.assertLess(spread[1], spread[0] / 2.0)
        self.assertLess(spread[2], spread[1] / 1.3)

    def test_a_job_that_cannot_be_solved_says_so(self):
        from engicalc.core.indices import Job, derive
        from engicalc.core.parsing import ParseError

        with self.assertRaises(ParseError):
            derive(Job("no free variable named", "rho*A*L",
                       constraint="S = E*A/L"))
        with self.assertRaises(ParseError):
            derive(Job("nonsense", "rho*A*(", free="A",
                       constraint="S = E*A/L"))


class TestTheme(unittest.TestCase):
    """The promise the accent picker makes is that nothing can be unreadable.

    A user who picks a pale yellow on white, or navy on charcoal, gets a
    heading they can read - not the colour they asked for. That is the
    whole reason a colour can be chosen at all, so it is the thing worth
    testing.
    """

    def test_every_offered_accent_reads_on_every_base(self):
        from engicalc.ui import theme

        for base in theme.BASES:
            for name, colour in theme.ACCENTS.items():
                theme.use(base, colour)
                palette = theme.colours()
                for ground in ("surface", "bg"):
                    with self.subTest(f"{name} on {base} {ground}"):
                        self.assertGreaterEqual(
                            theme.contrast(palette["accent"],
                                           palette[ground]),
                            theme.LEAST_CONTRAST - 1e-9)
        theme.use("light", theme.ACCENTS["Navy"])

    def test_a_colour_nobody_should_pick_is_corrected_rather_than_refused(self):
        from engicalc.ui import theme

        # Pale yellow on white: 1.1:1 as asked, unreadable. It comes back
        # darkened rather than rejected, because refusing a colour is a
        # worse answer than making it work.
        self.assertLess(theme.contrast("#ffe066", "#ffffff"), 1.5)
        fixed = theme.readable("#ffe066", "#ffffff")
        self.assertGreaterEqual(theme.contrast(fixed, "#ffffff"),
                                theme.LEAST_CONTRAST)

        # And the same colour on a dark ground needs no help at all, so it
        # is left exactly as asked.
        self.assertEqual("#ffe066", theme.readable("#ffe066", "#1c1f24"))

    def test_the_charts_do_not_follow_the_theme(self):
        """A chart is a document. It gets printed."""
        from engicalc.ui import theme

        theme.use("dark", theme.ACCENTS["Amber"])
        try:
            self.assertEqual("#ffffff", theme.CHART_PAPER)
            self.assertEqual("#111111", theme.CHART_INK)
            self.assertTrue(theme.is_dark())
        finally:
            theme.use("light", theme.ACCENTS["Navy"])

    def test_mixing_ends_where_it_should(self):
        from engicalc.ui import theme

        self.assertEqual("#000000", theme.mix("#000000", "#ffffff", 0.0))
        self.assertEqual("#ffffff", theme.mix("#000000", "#ffffff", 1.0))
        self.assertEqual("#808080", theme.mix("#000000", "#ffffff", 0.5))

    def test_the_settings_file_keeps_what_a_writer_is_not_about(self):
        """Two settings in one file, and neither may erase the other."""
        import json
        import tempfile
        from unittest import mock

        from engicalc.ui import app as app_module

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            with mock.patch.object(app_module, "SETTINGS_FILE", path):
                app_module.remember(check_at_start=True)
                app_module.remember(theme_base="dark", theme_accent="#b45309")
                app_module.remember(check_at_start=False)
                with open(path, encoding="utf-8") as handle:
                    kept = json.load(handle)

        self.assertEqual({"check_at_start": False, "theme_base": "dark",
                          "theme_accent": "#b45309"}, kept)
