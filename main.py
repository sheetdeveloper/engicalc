#!/usr/bin/env python3
"""EngiCalc launcher.

    python main.py            start the window
    python main.py --cli ...  use the command line instead

The CLI is also reachable as ``python -m engicalc.cli``.
"""

import sys


def _missing(package: str, exc: Exception) -> None:
    print(f"EngiCalc needs {package}, which is not installed.\n"
          f"  ({exc})\n\n"
          f"Install everything with:\n"
          f"    pip install -r requirements.txt\n", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from engicalc.cli import main as cli_main
        return cli_main(sys.argv[2:])

    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        print("Tkinter is not available in this Python installation.\n"
              "On Debian/Ubuntu:   sudo apt install python3-tk\n"
              "On Fedora:          sudo dnf install python3-tkinter\n"
              "On macOS/Windows:   reinstall Python from python.org\n\n"
              "You can still use the command line:  python main.py --cli --help\n"
              f"  ({exc})", file=sys.stderr)
        return 2

    try:
        import matplotlib  # noqa: F401
        import sympy  # noqa: F401
    except ImportError as exc:
        _missing("SymPy and matplotlib", exc)

    # Before the window, because an error during startup is the one nobody
    # can screenshot - the window it would have appeared in never opens.
    from engicalc import faults
    faults.install()

    from engicalc.ui.app import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
