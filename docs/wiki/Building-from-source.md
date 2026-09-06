# Building from source

## Running it

Python 3.11 or newer.

    git clone https://github.com/sheetdeveloper/engicalc.git
    cd engicalc
    python -m venv .venv
    .venv\Scripts\activate          # or: source .venv/bin/activate
    pip install -r requirements.txt
    python main.py

There are four dependencies - SymPy, matplotlib, numpy and openpyxl - and
that is on purpose. It is a small enough set to install in one step on a
university machine you do not have admin on.

There is a command line too:

    python main.py --cli solve "2x^2 - 5x - 3 = 0"

## The tests

    python -m unittest discover -s tests

332 of them, and they are the argument for trusting any of this. A good
number are not testing that something works but that a specific past mistake
has not come back: the steam verification values, the beam diagrams closing
to zero, a name with more than one letter surviving a parse.

If you change anything in `core/`, run them before believing the result.

## Building the installer

Windows only, and it needs
[Inno Setup](https://jrsoftware.org/isdl.php) on the PATH.

    build_exe.bat            # dist\EngiCalc.exe, about 59 MB
    build_installer.bat      # Output\EngiCalc_Setup.exe

`build_exe.bat debug` builds a console version instead, which is how you
find out why a frozen build fails when the source runs. PyInstaller cannot
see imports that happen at run time, so anything loaded dynamically has to
be named in `EngiCalc.spec` - that is what `collect_submodules` is doing
there.

Run the exe once before handing it out. A frozen build can fail on an import
that works perfectly from source, and it fails silently in a windowed build.

## How it is laid out

    engicalc/
      core/        the maths - parsing, solving, steps, units, properties
      formulas/    the formula library, one module per branch
      plotting/    curve and property plotting
      storage/     the SQLite history
      export/      the workbook builders
      ui/          the window, one module per tab
    tests/         all of them, in one file
    docs/          screenshots and these pages

`core/` knows nothing about `ui/`. Anything that could be wanted from the
command line, or tested without a window, lives there.

## The house style

Worth knowing before sending a change:

* Comments explain **why**, not what. If a line needs a comment saying what
  it does, rename something instead.
* When something is done a surprising way, say what goes wrong the obvious
  way. Most of the comments in `core/` are of that form, and they are the
  ones worth having.
* A number that could be wrong gets a test with a source for the right
  answer, not a test that pins whatever it currently returns.
* Prefer refusing to answer over answering from the wrong equations.
