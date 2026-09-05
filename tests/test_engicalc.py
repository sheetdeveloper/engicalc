"""Self-tests. Run with:  python -m unittest discover tests  (or python tests/test_engicalc.py)"""

from __future__ import annotations

import math
import os
import random
import re
import sys
import tempfile
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
                for index in range(len(notebook.tabs())):
                    notebook.select(index)
                    app.update()
                    app.update_idletasks()
                    name = notebook.tab(index, "text").strip()
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
        finally:
            app.destroy()
