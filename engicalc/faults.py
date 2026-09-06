"""Somewhere for an error to go when there is no console to print it to.

A windowed build has no stderr. Python writes the traceback there anyway,
which means that in the installed app every unhandled error is thrown into a
void: something goes wrong, a dialog flashes up or nothing at all happens,
and there is nothing left afterwards to look at. The one time it matters -
somebody says "it gave an error" - there is no way to find out which.

So every unhandled error is appended to a file, with the time, the version
and the whole traceback, and the dialog says where that file is. Then "it
gave an error" becomes a line somebody can send.

Two ways in, because there are two ways out of a Tk program. Anything a
widget's callback throws goes through Tk's own handler, and anything thrown
before the window exists goes through the interpreter's. Both are covered:
an error during startup is exactly the one nobody can screenshot, because
the window it would have appeared in never opened.
"""

from __future__ import annotations

import datetime
import os
import sys
import traceback

#: Beside the history and the settings, in the folder the app already owns.
LOG_PATH = os.path.join(os.path.expanduser("~"), ".engicalc", "errors.log")

#: How much of the log to keep. Errors tend to repeat, and a file nobody
#: ever truncates is one nobody can read.
KEEP_BYTES = 256 * 1024


def _version() -> str:
    try:
        from . import __version__
        return __version__
    except Exception:                                     # noqa: BLE001
        return "unknown"


def record(kind, value, tb, doing: str = "") -> str:
    """Append one error to the log. Returns where it was written.

    Deliberately catches everything itself. An error handler that raises
    replaces a problem somebody could report with one they cannot.
    """
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if (os.path.exists(LOG_PATH)
                and os.path.getsize(LOG_PATH) > KEEP_BYTES):
            with open(LOG_PATH, "r", encoding="utf-8",
                      errors="replace") as handle:
                tail = handle.read()[-KEEP_BYTES // 2:]
            with open(LOG_PATH, "w", encoding="utf-8") as handle:
                handle.write("... earlier entries dropped ...\n" + tail)

        when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"\n{'-' * 70}\n{when}  EngiCalc {_version()}"
                         f"  Python {sys.version.split()[0]}\n")
            if doing:
                handle.write(f"while {doing}\n")
            handle.write("".join(
                traceback.format_exception(kind, value, tb)))
    except Exception:                                     # noqa: BLE001
        pass
    return LOG_PATH


def _tell(value, where: str) -> None:
    """Say what happened and where it was written down."""
    try:
        from tkinter import messagebox
        messagebox.showerror(
            "EngiCalc hit a problem",
            f"{type(value).__name__}: {value}\n\n"
            f"The details have been written to:\n{where}\n\n"
            f"The rest of the program should still work. If it does not, "
            f"that file is the thing to send.")
    except Exception:                                     # noqa: BLE001
        print(f"EngiCalc error, written to {where}", file=sys.stderr)


def install() -> None:
    """Catch anything thrown outside the window - including before it."""
    def handler(kind, value, tb):
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, value, tb)
            return
        _tell(value, record(kind, value, tb, "starting up"))
        sys.__excepthook__(kind, value, tb)

    sys.excepthook = handler


def attach(root) -> None:
    """Catch anything a widget's callback throws.

    Tk swallows these by default in a windowed build - the traceback goes to
    a stderr that is not connected to anything - so a tab that fails leaves
    no trace at all.
    """
    def handler(kind, value, tb):
        _tell(value, record(kind, value, tb, "running"))

    root.report_callback_exception = handler
