#!/usr/bin/env bash
# EngiCalc launcher (macOS / Linux). Mirrors run_engicalc.bat.
#   ./run_engicalc.sh             start the app
#   ./run_engicalc.sh reinstall   rebuild the environment
#   ./run_engicalc.sh test        run the self-tests
set -e
cd "$(dirname "$0")"
VENV=".venv"
PY="${PYTHON:-python3}"

if [ "$1" = "reinstall" ]; then rm -rf "$VENV"; fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "First run - creating a private Python environment in $VENV ..."
  "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip --quiet
  "$VENV/bin/python" -m pip install -r requirements.txt
fi

if ! "$VENV/bin/python" -c "import tkinter" 2>/dev/null; then
  echo "Tkinter is missing from this Python."
  echo "  Debian/Ubuntu: sudo apt install python3-tk, then ./run_engicalc.sh reinstall"
  echo "  Fedora:        sudo dnf install python3-tkinter"
  echo "  macOS:         install Python from python.org rather than Homebrew's bare build"
  exit 2
fi

if [ "$1" = "test" ]; then exec "$VENV/bin/python" -m unittest discover -s tests -v; fi
exec "$VENV/bin/python" main.py "$@"
