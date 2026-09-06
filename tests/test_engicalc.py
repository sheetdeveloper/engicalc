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
