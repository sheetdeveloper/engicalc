# HANDOVER

State of EngiCalc as handed over, what was verified and how, what was not, and
what to do next. `CLAUDE.md` covers *how to work on the code*; this covers
*where the project stands*.

Written at the end of the initial build. Version 1.0.0.

---

## 1. What this is

A local desktop app for engineers: a symbolic equation solver with worked steps,
a grapher, a searchable library of 212 engineering formulas that rearrange for
any variable, a calculation history, and export to Excel workbooks that contain
live formulas rather than numbers.

The brief was "Symbolab, minus the AI, plus an engineering formula library, plus
history, plus formula-driven Excel export". All four parts are built.

Everything runs locally. No account, no network calls, no telemetry. Four pip
dependencies: sympy, matplotlib, numpy, openpyxl. Tkinter and sqlite3 ship with
Python.

**Scale:** ~7,700 lines of Python across 44 modules. 212 formulas, 804 variable
slots, 99 tests.

---

## 2. Current state, honestly

### Verified working

| Area | How it was checked |
|---|---|
| Solver, calculus, systems | 99 automated tests, all passing |
| All 212 formulas | Every one parses; declared variables match the equation exactly (enforced by test) |
| Rearrangement | 800 of 804 possible rearrangements resolve symbolically; the other 4 fall through to a numeric solver |
| Excel export | Generated workbooks recalculated in LibreOffice: **0 formula errors**. Values checked by hand |
| Excel printer fidelity | Round-trip tests evaluate the printed Excel string in Python against SymPy with random values, to 8 decimal places |
| Typeset rendering | Every library formula, every pad symbol and every calculator step rendered without failure |
| The GUI itself | Driven end-to-end under a virtual X server: all five tabs, solving, plotting, formula calculation, sensitivity sweep, saving, favouriting, reopening. Screenshots taken |
| **Windows** | Run on Windows 11, Python 3.14.6, matplotlib 3.11.1. Full suite passes. The window opens, all five tabs load, the calculator solves / integrates / takes limits, and the maths renderer draws correctly throughout. Screenshots taken |
| **The graph tab on Windows** | The flagged risk, now checked: matplotlib's Tk backend draws, two curves at once, roots marked and labelled, pan/zoom toolbar present |
| **The frozen build** | `build_exe.bat` run end to end on Windows. `dist\EngiCalc.exe` launches, loads the library, renders the typeset bar and the pad. Driven through `--cli` on the console build, the frozen engine solves, integrates (3.2 for the worked case), takes limits, and rearranges a library formula |
| **Inequalities** | `<=`, `>=`, `<`, `>` and `!=` solve to a range, checked against the pad's own worked examples, an absolute value, a sign flip across a denominator (`1/x < 1`), an empty solution and a plain numeric comparison |
| **Interpolation** | Linear checked against the arithmetic done by hand, a value on a row returning that row, an exact polynomial fit, reverse lookup, a curve that turns being reported as two answers, and extrapolation warning rather than answering quietly |
| **The installer** | `build_installer.bat` compiled `Output\EngiCalc_Setup.exe` (57.7 MB) with Inno Setup 6 |

### Not verified

- **`run_engicalc.bat` has never executed.** It is written carefully, with named
  failure paths for missing Python, blocked venv creation, no network and a
  Tkinter-less Python, but no one has double-clicked it. The app has only been
  started on Windows by calling `main.py` through an existing `.venv`.
- **Excel export on Windows.** The printer's round-trip tests pass there, but no
  workbook has been written and reopened on Windows.
- **The installer has been built but never run.** Nobody has installed from
  `EngiCalc_Setup.exe`, so the Start Menu entry, the desktop shortcut, the
  uninstaller and the per-user install path are all untested.
- **The build has only been made on this machine**, with Python 3.14 and its
  particular set of packages.
- **No performance work.** Rendering a card grid of 24 formulas takes a moment
  on first paint (about 19 ms per formula, cached afterwards). Fine in testing;
  unmeasured on a slower machine.
- **Long sessions.** The history database has never held more than a handful of
  rows. Nothing is known about how the History tab behaves with thousands.

---

## 3. Design decisions worth not undoing

These were deliberate. Each cost effort and each solves a problem that will come
back if reversed.

**The parser is a whitelist, not `sympify`.** `core/parsing.py` exposes a fixed
dictionary of SymPy names. A calculator that evaluates arbitrary user text is a
code-execution hole, and this app is meant to be handed to colleagues. Do not
widen it to a bare `eval` or `sympify` for convenience.

**Display parses separately from computation.** SymPy reorders terms as it
evaluates, so `F = m*a` prints as `F = a m`. Anything shown to the user goes
through `parse_for_display` (`evaluate=False`) and `sp.latex(..., order="none")`,
which keeps the arrangement engineers actually recognise. This is why
`Formula.display_latex` exists and why the cards read `F = ma`.

**The Excel printer targets Excel 2007.** No dynamic-array functions, nothing
modern. It costs nothing and means the workbooks recalculate in LibreOffice and
Google Sheets, which matters when a client opens your quote.

**Defined names, not cell references, in single-formula exports.** The result
cell reads `=v_c*v_m*(-v_T1+v_T2)` rather than `=C5*C4*(C7-C6)`. The `v_`
prefix is not decoration: Excel reserves `C`, `R` and anything resembling a cell
reference as names.

**One symbol list drives three things.** `ui/pad.py` generates the pad buttons,
the reference window and the syntax documentation. Add a symbol in one place and
it appears in all three, and they cannot drift apart. A `PadItem` now also
carries an optional `template`, which is the fourth thing it drives: the shape
the equation bar draws.

**The equation bar measures itself out of mathtext.** `ui/mathfield.py` puts its
boxes and its caret where they belong by reading glyph coordinates back out of
mathtext's own layout, rather than guessing at metrics. That is why it stays
correct at any font size and inside subscripts, and why it needs no dependency
beyond the four already here. The caret trick is worth knowing: the expression
is rendered a second time with a `|` at the cursor, and because everything ahead
of the marker is laid out as though it were absent, the position that render
reports is valid for the image actually drawn.

**The spec collects whole packages rather than listing modules.** Both the
formula library and SymPy import by name at runtime, so PyInstaller's import
scan misses them. The very first build of this app compiled cleanly and then
died on startup with `No module named 'engicalc.formulas.data'` - and because a
windowed frozen build has nowhere to print, it did so *silently*: the process
sat there alive, with no window and no error dialog. That is what
`build_exe.bat debug` is for. Listing the eleven branch modules by hand would
have worked and would have broken again the first time a twelfth was added.

**Rows and Groups in the field compare by identity.** They are dataclasses with
`eq=False` on purpose. Tab order and slot ownership are resolved with `.index()`
and `in`, and the two boxes of `x/x` hold equal contents while being entirely
different boxes. Removing `eq=False` makes Tab jump to the wrong slot, which is
exactly the bug it was added to fix.

**SymPy never runs on the Tk thread.** It can hang for tens of seconds on an
awkward rearrangement. `ui/widgets.py::AsyncRunner` moves the work to a worker
thread; `library.py::_timed` gives symbolic rearrangement six seconds before
dropping to the numeric solver.

**The formula library is data, not code.** Adding formulas means editing a list
in `formulas/data/`, and two tests enforce the invariants. This is the part most
likely to grow, so it was made the easiest part to extend.

---

## 4. Known issues and rough edges

**Nothing here is a blocker; all of it is worth knowing.**

1. **Units are labels, not enforced.** The app will happily let you enter mm in a
   field expecting m. This is the largest real gap. `sympy.physics.units` is the
   obvious fix and would need work in `model.py`, `library.py` and the input grid.
2. **Periodic roots are principal only.** `sin(x) = 0` returns 0 and pi, not the
   whole family. The graph marks only those.
3. **Four formulas have no closed-form rearrangement** for some variables:
   `heat_transfer.fin_efficiency` (for `m_f` and `L`), `geometry_maths.heron`
   (for `s`) and `geometry_maths.annuity_payment` (for `i`). They solve
   numerically and say so in the result panel. `test_rearrangement_coverage`
   skips them by name — if you fix one, remove it from that skip list.
4. **Complex results and infinities cannot go to Excel.** The exporter raises a
   readable error rather than writing something wrong. Correct behaviour, but a
   user hitting it gets a dialog and no workbook.
5. **`engicalc/cli.py` is unused by the GUI**, but it is reachable from the
   shipped exe as `EngiCalc.exe --cli`, so it is no longer dead weight that
   can be deleted without thought. It had a Windows-only bug until now: results
   carry U+2248 before a decimal approximation, a Windows console is cp1252,
   and printing one raised `UnicodeEncodeError` - so `solve` failed on the
   console while `integral` and `limit` worked. `cli.main` now reconfigures
   stdout and stderr to UTF-8.
6. **The maths renderer draws a LaTeX subset.** No `\begin{...}` environments, no
   `\operatorname`, no `\text`. `mathrender.sanitise` rewrites what it can and
   every display path falls back to monospace, so failures are ugly rather than
   fatal. If you add a symbol, check it renders.
7. **Civil and structural formulas carry no code factors.** They are the plain
   textbook forms. The assumption line on each is there for a reason.
8. **Inequalities give principal ranges, not periodic families.** `sin(x) > 0`
   answers `(0, pi)` rather than every interval where it holds. Same limitation
   as issue 2, and the same fix would serve both.

---

## 5. Suggested order of work

Roughly by value per unit of effort.

1. ~~**Run it on Windows and fix what breaks.**~~ Done. It runs; the graph tab
   and the maths rendering — the two things flagged as most likely to break —
   both behave. See the verified table above for exactly what was covered.
2. ~~**Fix inequalities.**~~ Done. `<=`, `>=` and `!=` now answer with the
   range that satisfies them, with the boundary points and interval test shown
   as working.
3. **Install from `EngiCalc_Setup.exe` on a second machine** and confirm the
   shortcuts, the uninstaller and a per-user install all behave. The installer
   builds but has never been run.
4. **Confirm `run_engicalc.bat` works from a cold machine** — no Python, then
   Python without Tkinter, then a normal install. Less urgent now the exe
   exists, but it is still the path a developer hits first.
5. **Units.** The biggest correctness win available. Even a soft version — warn
   when a value looks orders of magnitude off the typical value already stored
   against each variable — would catch most real mistakes.
6. **Chained calculations.** Let one formula's result feed the next, and export
   the chain as a single linked workbook. This is what turns the app from a
   calculator into a calculation sheet, and the Excel exporter already has the
   machinery.
7. **Import/export the user formula library** so it can be shared between
   machines or with colleagues.
8. **Periodic root families** on the graph.

---

## 6. How to verify a change

```
run_engicalc.bat test          # 99 tests, about 25 seconds
run_engicalc.bat               # then actually look at the window
```

Run the tests after every change, not at the end. They are fast and they cover
the things that break silently: the parser, all 212 formulas, the Excel
printer's numerical fidelity, and whether the notation still renders.

If you add formulas, the two invariants are enforced automatically — the symbols
in the equation must match the declared variables, and every variable must
rearrange. A mistake fails loudly.

If you change the Excel printer, `TestExcelPrinter` is the safety net: it
evaluates the printed string in Python against SymPy with random values. Keep it
passing and the workbooks stay correct.

---

## 7. Where things live

```
engicalc/
  core/
    parsing.py         text -> SymPy (whitelisted names) + display parsing
    engine.py          solve / calculus / systems -> CalcResult
    steps.py           the worked solution
    display.py         SymPy -> readable plain text
    excel_printer.py   SymPy -> Excel formula strings
  formulas/
    model.py           Formula, Variable, display_latex
    library.py         load, search, rearrange, numeric fallback, user formulas
    data/              11 modules, one per branch — add formulas here
  plotting/plot.py     explicit, implicit, parametric, polar, sweeps
  storage/history.py   SQLite at ~/.engicalc/history.db
  export/excel.py      the three workbook builders
  ui/
    app.py             window shell, cross-tab plumbing
    interpolate_tab.py the table reader
    clipboard.py       a picture on the clipboard, for Word
    mathrender.py      LaTeX -> PNG -> Tk, with fallback
    mathfield.py       the editable typeset equation bar
    pad.py             the symbol list (drives pad, reference, docs, shapes)
    symbol_pad.py  reference_window.py
    calculator_tab.py  graph_tab.py  library_tab.py  cards_tab.py
    history_tab.py  widgets.py
tests/test_engicalc.py
main.py  run_engicalc.bat  run_engicalc.sh  requirements.txt
README.md  CLAUDE.md  HANDOVER.md
examples/            two sample workbooks, both recalculated clean

EngiCalc.spec              PyInstaller build definition
build_exe.bat              -> dist\EngiCalc.exe   (also `debug`, `clean`)
installer.iss              Inno Setup definition
build_installer.bat        -> Output\EngiCalc_Setup.exe
stamp_installer_version.py copies __version__ into installer.iss
```

Two data files are created outside the project, both under `~/.engicalc/`:
`history.db` (saved calculations) and `user_formulas.json` (formulas added
through the UI). Neither is in the repository; deleting them resets the app
without touching the code.

---

## 8. Provenance

Built in a single Claude chat session, then handed to Claude Code to continue.
The GUI was exercised under a virtual X server before handover, which is how the
three bugs below were found and fixed rather than shipped:

- favouriting a history row cleared the selection, so the next button press
  silently did nothing;
- the history scrollbar was positioned over the detail pane and buttons;
- results displayed SymPy's raw notation (`Eq(2*x**2 - 5*x - 3, 0)`).

Three Tk traps found the same way, recorded so they are not rediscovered:
mathtext has no `\square` glyph; a Tk `Label`'s `width` is characters for text
but *pixels* once it holds an image; and ttk `Treeview` row height is a
theme-wide setting, so a derived style will not override it — the reference
table is built from plain frames instead.
