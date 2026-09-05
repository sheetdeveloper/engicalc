# CLAUDE.md

Context for working on EngiCalc. Read this before changing anything.

`HANDOVER.md` is the companion document: project state, what was verified and
how, known issues, and the suggested order of work. Read it once at the start of
a session; this file is the reference you come back to.

## What this is

A local desktop app (Tkinter + SymPy + matplotlib + openpyxl): equation solver
with worked steps, grapher, engineering formula library, SQLite calculation
history, and export to live formula-driven Excel workbooks. No web service, no
API keys, no telemetry.

## Commands

    run_engicalc.bat            start the app (Windows; .sh on mac/linux)
    run_engicalc.bat test       run the suite
    .venv\Scripts\python -m unittest discover -s tests -v
    .venv\Scripts\python main.py

    build_exe.bat               dist\EngiCalc.exe (runs the suite first)
    build_exe.bat debug         console build, for reading a frozen traceback
    build_installer.bat         Output\EngiCalc_Setup.exe (needs Inno Setup)

Dependencies: sympy, matplotlib, numpy, openpyxl. Tkinter and sqlite3 come with
Python. Keep it to these four - a big part of the point is that it installs in
one step on a work machine.

## Architecture

Everything flows through two result objects, and the UI, history and exporters
all consume them:

- `core/engine.py::CalcResult` - free-form calculator results
- `formulas/library.py::FormulaSolution` - library formula results

If you add a feature, produce one of these rather than a new shape.

    core/parsing.py       text -> SymPy. Whitelisted names only (see GLOBAL_DICT).
                          Never widen this to a bare eval or sympify of user text.
    core/engine.py        solve/simplify/calculus/systems. Falls back to numeric
                          root finding when solve() returns nothing. A
                          relational that is not an Eq goes to
                          _solve_inequality instead, which answers with a set -
                          never wrap one in Eq(expr, 0).
    core/steps.py         worked solutions. Defensive by design: unknown cases
                          return fewer steps, never raise.
    core/interpolate.py   reading between the rows of a table. Parses a pasted
                          two-column table, interpolates, and returns a
                          CalcResult like everything else.
    core/display.py       SymPy -> readable text (** becomes ^, Eq becomes =).
                          Cosmetic only, never parsed back.
    core/excel_printer.py SymPy -> Excel formula strings. See the rules below.
    formulas/data/*.py    the library data, one module per engineering branch.
    plotting/plot.py      draws onto an Axes the caller owns, so the same code
                          serves the window and headless PNG export.
    storage/history.py    SQLite at ~/.engicalc/history.db.
    export/excel.py       workbook builders.
    ui/mathrender.py      LaTeX -> PNG -> Tk PhotoImage, cached. MathLabel is
                          one expression, MathList is a scrollable stack of
                          (heading, expression, detail) blocks.
    ui/mathfield.py       the editable equation bar. A tree of Row (characters
                          and nested Groups) renders to LaTeX; empty slots draw
                          as a hollow box you Tab between and type into. It
                          compiles back to the ASCII the parser already takes,
                          and `structured_row` goes the other way, turning
                          typed text into the same tree.
    ui/clipboard.py       CF_DIB on the Windows clipboard, so a worked
                          calculation can be pasted into Word as a picture.
    ui/pad.py             the symbol list. Buttons, the reference window and the
                          syntax docs are all generated from PAD, so they cannot
                          drift apart - add a symbol here and it appears in all
                          three. A PadItem's `template` names a mathfield shape.
    ui/                   app.py owns cross-tab plumbing; tabs talk to each other
                          only through the app object, never directly.

## Rules that are easy to break

**Excel printer.** Only emit functions that Excel *and* LibreOffice both
evaluate, and nothing post-2007. Never `XLOOKUP`, `FILTER`, `SORT`, `UNIQUE`,
`SEQUENCE` or other dynamic-array functions. Excel reserves `C`, `R` and
anything that looks like a cell reference as defined names, which is why every
name is prefixed `v_`. `ATAN2` takes its arguments in the opposite order to
SymPy's. If you change this module, the round-trip tests in
`TestExcelPrinter` must still pass - they evaluate the printed string in Python
against SymPy with random values.

**Formula data invariants**, both enforced by tests:
1. The symbols in `equation` must exactly match the declared `variables`.
2. Every formula must rearrange for every one of its variables (four known
   exceptions are skipped by name in `test_rearrangement_coverage`).

Symbols shadowing SymPy names (`E`, `I`, `e`) are safe *because*
`Formula.eq` passes the declared variables as `local_dict`. Don't remove that.

**Typeset output.** Matplotlib mathtext draws a LaTeX *subset*: no
`\begin{...}` environments, no `\operatorname`, no `\text`. `mathrender.sanitise`
rewrites what it can and raises for the rest, and every display path falls back
to plain text rather than showing an error. If you add a symbol to `pad.py`,
check its `label` and `example_latex` actually render.

**The equation field measures itself.** `mathfield` places its boxes and its
caret by reading glyph coordinates out of mathtext's own layout
(`MathTextParser("path")`), so both parsers must see the same string. Positions
come back in pixels at the dpi passed in, `oy` is measured up from the baseline,
and the baseline sits `height - depth` below the top of the bitmap. The caret is
found by rendering a second copy with a `|` at the cursor: everything ahead of
it is laid out as though it were absent, which is what makes that position valid
for the image actually drawn. The placeholder is a literal `□` because mathtext
has neither `\square` nor `\Box` - if you change it, change `PLACEHOLDER_CP`
with it, or the boxes stop being locatable.

**Anything imported by name has to be declared to PyInstaller.** The formula
library loads its eleven branch modules with `importlib.import_module`, and
SymPy reaches for modules by name all through `solve` and `integrate`. A static
import scan sees none of it, so `EngiCalc.spec` collects both packages
wholesale. Add a branch module to `_DATA_MODULES` and the source build is fine
while the frozen one dies on startup - which is why the spec collects the
package rather than listing modules. A windowed frozen build fails *silently*
here: no window, no error, process still alive. `build_exe.bat debug` gives a
console build that prints the traceback.

**Term order.** SymPy reorders as it evaluates, so `F = m*a` prints as `F = a m`.
Anything shown to the user goes through `parsing.parse_for_display`
(`evaluate=False`) and `sp.latex(..., order="none")` - see `Formula.display_latex`.
Never use the evaluated form for display.

**Threading.** SymPy can hang on an awkward rearrangement. UI work goes through
`ui/widgets.py::AsyncRunner` (worker thread, results delivered on the Tk thread
via `after`); `library.py::_timed` gives symbolic rearrangement a 6 second budget
before dropping to the numeric solver. Never call `sp.solve` directly from a
button handler.

**History writes.** Values stored in `inputs` must be JSON-serialisable - convert
SymPy objects with `sp.sstr` before they get near the database.

## Style

Plain, boring Python. Type hints on public functions, dataclasses for data,
comments only where the reason isn't obvious from the code. Failure paths tell
the user what to do next rather than dumping a traceback.

## Worth building next

- Unit handling (`sympy.physics.units`) so mm and m can't be silently mixed.
- Multi-step calculation sheets: chain formulas so one result feeds the next,
  and export the chain as a single linked workbook.
- Periodic root families on the graph rather than principal solutions only.
- Import/export of the user formula library so it can be shared between machines.
