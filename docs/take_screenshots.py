"""Take the screenshots the README and the release page use.

Run from the project root with the virtualenv's Python. Each shot is the
window at the size the rest of them were taken at, so the release page does
not end up a patchwork of different sizes.

The window is raised before each grab: this captures the screen, so anything
sitting in front of it would otherwise end up in the picture.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

import matplotlib

matplotlib.use("Agg")

from PIL import ImageGrab                                       # noqa: E402

from engicalc.core.engine import calculate                      # noqa: E402
from engicalc.ui import theme
from engicalc.ui.app import EngiCalcApp                         # noqa: E402

SIZE = "1280x820+40+40"
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

DUCT = ("A = pi*d^2/4\n"
        "v = 0.5/A\n"
        "Re = v*d/7.5e-6\n"
        "f = 0.3164/Re^0.25\n"
        "dp = f*(20/d)*1.2*v^2/2")


def settle(app, seconds: float = 1.2) -> None:
    app.attributes("-topmost", True)
    app.lift()
    app.focus_force()
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        app.update_idletasks()
        time.sleep(0.05)


def grab(app, name: str) -> None:
    settle(app)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    width, height = app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + width, y + height)).save(
        os.path.join(HERE, name))
    print(f"  {name}  {width}x{height}")


def top_tab(app, label: str) -> None:
    for index in range(len(app.notebook.tabs())):
        if app.notebook.tab(index, "text").strip() == label:
            app.notebook.select(index)
            return
    raise SystemExit(f"no tab called {label!r}")


def wait_for(app, tab, seconds: float = 25.0) -> None:
    end = time.time() + seconds
    while time.time() < end and getattr(tab, "result", None) is None:
        app.update()
        time.sleep(0.02)


def main() -> None:
    os.makedirs(HERE, exist_ok=True)
    # The pictures in the README are of the app, not of whatever colours
    # this machine happens to be set to. Forced, or a developer who works
    # in dark rebuilds the documentation into a different-looking program.
    theme.use("light", theme.ACCENTS["Navy"])
    app = EngiCalcApp(db_path=os.path.join(tempfile.mkdtemp(), "shots.db"))
    app.geometry(SIZE)
    app.update()
    app.update_idletasks()

    # -- the calculator, on the definite integral -------------------------
    # The picture at the top of the README. The integral is the one that
    # shows the most in one frame: a real integral sign in the entry bar,
    # the area it measures shaded underneath with the negative part
    # hatched, and the working beside it naming the rule before applying
    # it.
    top_tab(app, "Calculator")
    app.calculator_pane.show_calculator()
    calculator = app.calculator_tab
    calculator.input_var.set("2x")
    app.update_idletasks()
    # Built the way a user builds it: type the integrand, press the
    # definite integral button, and Tab between the limit boxes. Setting
    # the text alone would leave a plain "2x" in the bar and lose the one
    # thing this picture is of.
    calculator.field.insert_template("defint")
    calculator.op_var.set("integral")
    calculator._sync_options()
    calculator.field.insert_text("-1.6")
    calculator.field._hop(1)
    calculator.field.insert_text("2.4")
    calculator.field._hop(1)
    calculator.field._hop(1)
    calculator.field.insert_text("x")
    app.update_idletasks()
    calculator.lower_var.set("-1.6")
    calculator.upper_var.set("2.4")
    calculator.var_var.set("x")
    calculator.result = calculate("2x", "integral", "x",
                                  lower="-1.6", upper="2.4")
    calculator._show(calculator.result)
    grab(app, "calculator.png")

    # -- equations solved together, typeset -------------------------------
    top_tab(app, "Calculator")
    app.calculator_pane.show_simultaneous()
    solver = app.simultaneous_tab
    solver.solve()
    wait_for(app, solver)
    grab(app, "simultaneous.png")

    # -- the parametric study ---------------------------------------------
    solver.set_text(DUCT)
    app.update_idletasks()
    solver.sweep_from.set("0.1")
    solver.sweep_to.set("0.3")
    solver.sweep_steps.set("9")
    solver.run_study()
    grab(app, "study.png")

    # -- the unit converter ------------------------------------------------
    app.calculator_pane.tabs.select(app.units_tab)
    units = app.units_tab
    units.category.set("Pressure")
    units._category_changed()
    units.value.set("2.5")
    units.source.set("bar")
    units.target.set("psi")
    units.convert()
    grab(app, "units.png")

    # -- the working, expanded --------------------------------------------
    app.calculator_pane.show_calculator()
    app.show_working.set(True)
    calculator = app.calculator_tab
    # The integral, because that is the gap this exists to fill: the jump
    # from 2x to x squared with nothing in between.
    calculator.input_var.set("2x")
    calculator.op_var.set("integral")
    calculator._sync_options()
    calculator.result = calculate("2x", "integral", "x")
    calculator._show(calculator.result)
    grab(app, "working.png")

    # -- an inequality, and a differential equation -----------------------
    # Both show their working, which is most of what makes them worth a
    # picture: an inequality is not one root but an interval, and an ODE
    # goes general solution then conditions then particular.
    calculator.input_var.set("x^2 <= 9")
    calculator.op_var.set("solve")
    calculator._sync_options()
    calculator.result = calculate("x^2 <= 9", "solve", "x")
    calculator._show(calculator.result)
    grab(app, "inequality.png")

    calculator.input_var.set("y' = -(y - 20)/5")
    calculator.op_var.set("ode")
    calculator._sync_options()
    calculator.conditions_var.set("y(0) = 90")
    calculator.result = calculate("y' = -(y - 20)/5", "ode", "x",
                                  conditions="y(0) = 90")
    calculator._show(calculator.result)
    grab(app, "ode.png")
    app.show_working.set(False)

    # -- the graph ---------------------------------------------------------
    top_tab(app, "Graph")
    curves = app.graph_tab
    curves.rows[0].expression.set("sin(x)*exp(-x/6)")
    if len(curves.rows) < 2:
        curves.add_row()
    curves.rows[1].expression.set("exp(-x/6)")
    curves.rows[1].kind.set("explicit")
    curves.xmin.set("0")
    curves.xmax.set("20")
    curves.replot()
    grab(app, "graph.png")

    # -- the formula library, with one solved ------------------------------
    top_tab(app, "Formula library")
    library = app.library_tab
    library.show_formula(app.library.get("strength_of_materials.euler_buckling"))
    library.target_var.set("Pcr")
    library._build_inputs()
    library.material.set("S275 steel")
    library.take_material()
    # A 254x254x73 UC about its weak axis, three and a half metres long,
    # pinned at both ends - so the answer is a load and not an algebraic
    # rearrangement with three names still in it.
    library.entries["I"].set("3.91e-5")
    library.entries["L"].set("3.5")
    library.entries["K"].set("1")
    library.calculate()
    wait_for(app, library)
    grab(app, "formula_library.png")

    # -- and the same library as cards to read -----------------------------
    top_tab(app, "Formula cards")
    app.cards_tab.search_var.set("beam")
    app.update_idletasks()
    grab(app, "formula_cards.png")

    # -- matrices ----------------------------------------------------------
    top_tab(app, "Matrices")
    app.matrix_tab.compute()
    grab(app, "matrices.png")

    # -- the worksheet -----------------------------------------------------
    top_tab(app, "Worksheet")
    # A pipe, measured rather than assumed. It shows the two things the
    # worksheet does that a column of sums does not: the unit comes out of
    # the arithmetic, and the tolerance comes down the page with each
    # measurement counted once however many rows it reached the answer
    # through - the bore is in the Reynolds number twice.
    sheet = app.sheet_tab
    sheet._clear_rows()
    # Replacing every row changes how much room the tab wants, and the
    # window manager takes that as leave to move the window. Put it back
    # now rather than in grab, which would be moving it on every capture
    # and reading the position while it was still travelling.
    app.geometry(SIZE)
    sheet.title_var.set("Water in a pipe, measured")
    for spec in (("d", "50 +/- 0.5 mm", "mm", "bore, off a vernier"),
                 ("A", "pi*d^2/4", "mm^2", "flow area"),
                 ("Q", "2 +/- 0.05 L/s", "m^3/s", "from the flowmeter"),
                 ("v", "Q/A", "m/s", "mean velocity"),
                 ("rho", "998 kg/m^3", "kg/m^3", "water at 20 C"),
                 ("mu", "0.001 Pa*s", "Pa*s", ""),
                 ("Re", "rho*v*d/mu", "", "Reynolds number")):
        sheet._add_widgets(*spec)
    sheet.calculate()
    grab(app, "sheet.png")

    # -- steam, with the chart --------------------------------------------
    top_tab(app, "Fluid properties")
    app.properties_pane.show_steam()
    grab(app, "steam.png")

    app.properties_pane.show_moist_air()
    grab(app, "moistair.png")

    app.properties_pane.show_r134a()
    grab(app, "r134a.png")

    app.properties_pane.show_cycle()
    grab(app, "cycle.png")

    # -- trendlines, on data that is not straight -------------------------
    top_tab(app, "Data")
    data = app.statistics_tab
    data.data_text.delete("1.0", "end")
    data.data_text.insert("1.0", "\n".join(
        f"{x}\t{3 * 2.718281828 ** (0.5 * x):.4f}" for x in range(1, 9)))
    data.compute()
    grab(app, "statistics.png")

    # -- interpolation, with typeset working ------------------------------
    top_tab(app, "Interpolate")
    app.interpolate_tab.compute()
    grab(app, "interpolate.png")

    # -- the standard charts ----------------------------------------------
    top_tab(app, "Graph")

    # The beam is taken with a section on it. Without one there is no
    # deflection diagram and no stress, which is most of what the tab now
    # does - a picture of it empty is a picture of the old tab.
    beam = app.graph_pane.charts["Beam"]
    app.graph_pane.tabs.select(beam)
    beam.section_name.set("305x165x40 UB")
    beam.refresh()
    grab(app, "beam.png")

    # The vessel is taken thick walled. On the default thin one the Lame
    # curves and the thin-wall lines agree to a hundredth of a percent, so
    # the picture is four flat lines on top of each other - which is the
    # right answer and a useless picture of what the tab is for.
    vessel = app.graph_pane.charts["Pressure vessel"]
    app.graph_pane.tabs.select(vessel)
    vessel.bore.set("100")
    vessel.wall.set("40")
    vessel.pressure.set("60")
    vessel.refresh()
    grab(app, "vessel.png")

    # The geometry tab is taken on the ambiguous triangle, which is the
    # one thing on it that a calculator normally gets wrong.
    geo = app.graph_pane.charts["Geometry"]
    app.graph_pane.tabs.select(geo)
    geo.side_c.set("")
    geo.side_a.set("7")
    geo.side_b.set("10")
    geo.angle_A.set("30")
    grab(app, "geometry.png")

    # The curved beam on a hook-like radius, where the inside fibre
    # carries half as much again as a straight-beam sum gives - which is
    # the whole reason the tab is there.
    hook = app.graph_pane.charts["Curved beam"]
    app.graph_pane.tabs.select(hook)
    hook.radius.set("100")
    grab(app, "curved.png")

    # And the axial tab on a stepped bar held at both ends, which is the
    # case statics alone cannot do.
    bars = app.graph_pane.charts["Axial"]
    app.graph_pane.tabs.select(bars)
    bars.bar_rows[0].values["rise"].set("0")
    bars.bar_rows[0].values["load"].set("100")
    bars.add_bar(length="800", area="300", modulus="210", expansion="12",
                 rise="0", load="0")
    grab(app, "axial.png")

    # The material chart narrowed to the two families a light structure is
    # actually chosen between, which is how it is meant to be used - all
    # six at once is a picture of the whole world and answers nothing.
    ashby = app.graph_pane.charts["Material chart"]
    app.graph_pane.tabs.select(ashby)
    for family in ("ceramic", "composite", "natural", "foam"):
        ashby.families[family].set(False)
    ashby.highlight.set("Magnesium alloy")
    ashby.refresh()
    grab(app, "materials.png")

    for label, name in (("Stress and strain", "tensile.png"),
                        ("Section", "section.png"),
                        ("Motion", "motion.png"),
                        ("Torsion", "torsion.png"),
                        ("Columns", "columns.png"),
                        ("Stress state", "mohr.png"),
                        ("Truss", "truss.png"),

                        ("Moody", "moody.png")):
        app.graph_pane.tabs.select(app.graph_pane.charts[label])
        grab(app, name)

    # -- complex numbers ---------------------------------------------------
    top_tab(app, "Calculator")
    app.calculator_pane.tabs.select(app.calculator_pane.complex)
    grab(app, "complex.png")

    app.update_idletasks()
    app.destroy()
    print("done")


if __name__ == "__main__":
    sys.exit(main())
