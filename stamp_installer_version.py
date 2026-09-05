#!/usr/bin/env python3
"""Copy the app's version into installer.iss.

The version lives in one place - ``engicalc/__init__.py`` - and everything
else is stamped from it. Bumping a version by hand in two files is how an
installer ends up reporting one number while the About box reports another.

Run by build_exe.bat and build_installer.bat; safe to run twice.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INIT = ROOT / "engicalc" / "__init__.py"
ISS = ROOT / "installer.iss"


def read_version() -> str:
    text = INIT.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not match:
        raise SystemExit(f"No __version__ found in {INIT}")
    return match.group(1)


def stamp(version: str) -> bool:
    """Write *version* into installer.iss. True if the file changed."""
    if not ISS.exists():
        raise SystemExit(f"{ISS} not found - cannot stamp the installer.")
    text = ISS.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(#define MyAppVersion\s+")([^"]*)(")',
        lambda m: m.group(1) + version + m.group(3), text)
    if not count:
        raise SystemExit(
            'installer.iss has no `#define MyAppVersion "..."` line to stamp.')
    if updated == text:
        return False
    ISS.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    version = read_version()
    changed = stamp(version)
    print(f"Version {version} "
          + ("stamped into installer.iss." if changed
             else "already current in installer.iss."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
