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
    app = EngiCalcApp(db_path=os.path.join(tempfile.mkdtemp(), "shots.db"))
    app.geometry(SIZE)
    app.update()
    app.update_idletasks()

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
    app.show_working.set(False)

    # -- steam, with the chart --------------------------------------------
    top_tab(app, "Fluid properties")
    app.properties_pane.show_steam()
    grab(app, "steam.png")

    app.properties_pane.show_moist_air()
    grab(app, "moistair.png")

    app.properties_pane.show_r134a()
    grab(app, "r134a.png")

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

    for label, name in (("Stress and strain", "tensile.png"),
                        ("Section", "section.png"),
                        ("Motion", "motion.png"),
                        ("Torsion", "torsion.png"),
                        ("Columns", "columns.png"),
                        ("Stress state", "mohr.png"),
                        ("Pressure vessel", "vessel.png"),
                        ("Truss", "truss.png"),
                        ("Material chart", "materials.png"),
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
