"""Telling somebody a newer version exists. Nothing more than telling.

**It must not install anything.** A program that can replace its own
executable is a program that can be made to replace it with something else,
and this one is handed around a university - it will end up on machines whose
owners have no way to check what it did. So this reports, and a person
decides, and the deciding happens in a browser they can see.

**The download address is a constant here, not something the reply carries.**
That is the whole reason the equivalent module in the Sheet.Developments
project signs its manifest: a reply that names its own download URL lets
anybody who can answer the request - a hostile network, a captive portal -
choose the file that gets presented as the official new version. Ignoring the
address in the reply and using one compiled into the app removes that
question rather than defending against it.

**Quiet when it cannot answer.** No network, a 404, a rate limit, a truncated
reply, a version this app cannot parse: every one of those means "nothing to
offer" and none is worth interrupting anybody over. A check that pops an
error because a server is down teaches people to dismiss the box, which is
exactly the box you need them to read one day.

**It is off unless asked.** The app promises that nothing leaves the machine,
and a check is a request to GitHub carrying an IP address and the fact that
somebody is running this. That is a small thing, but it is not nothing, and
it is not the promise. So: a menu item that checks on demand, and a setting
for checking at startup that starts switched off.

The network call is kept apart from everything else so the rest can be tested
without one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .. import __version__

OWNER_REPO = "sheetdeveloper/engicalc"
API_URL = f"https://api.github.com/repos/{OWNER_REPO}/releases/latest"

#: Where a person is sent to see and fetch it. A constant on purpose - see
#: the note at the top of this module.
RELEASES_PAGE = f"https://github.com/{OWNER_REPO}/releases/latest"

TIMEOUT = 6.0


@dataclass(frozen=True)
class Update:
    """A version that exists."""

    version: str
    notes: str = ""
    released: str = ""

    @property
    def summary(self) -> str:
        when = f", {self.released[:10]}" if self.released else ""
        return f"Version {self.version}{when}"


def parse_version(text: str):
    """A version string as something comparable, or None.

    Pre-releases sort before the release they lead to, which is why this is
    not a string comparison: "1.2.0" is newer than "1.2.0-beta.1", and plain
    ``<`` on the strings says the opposite because one is a prefix of the
    other.
    """
    if not text:
        return None
    body = str(text).strip()
    if body.startswith("v"):
        body = body[1:]
    pre = ()
    if "-" in body:
        body, _, tag = body.partition("-")
        pre = tuple(_identifier(part) for part in tag.split("."))
    bits = body.split(".")
    if not 1 <= len(bits) <= 3:
        return None
    numbers = []
    for bit in bits:
        if not bit.isdigit():
            return None
        numbers.append(int(bit))
    while len(numbers) < 3:
        numbers.append(0)
    # 1 for a real release, 0 for a pre-release, so a release wins a tie.
    return (tuple(numbers), 0 if pre else 1, pre)


def _identifier(part: str):
    """Numeric identifiers sort before alphanumeric ones, and numerically
    among themselves - beta.9 before beta.10, which a string gets backwards."""
    return (0, int(part), "") if part.isdigit() else (1, 0, part)


def is_newer(candidate: str, current: str) -> bool:
    """Is *candidate* a later version than *current*?

    False when either will not parse. A version this app cannot read is not
    one it should be recommending.
    """
    left, right = parse_version(candidate), parse_version(current)
    if left is None or right is None:
        return False
    return left > right


def read_release(payload: bytes):
    """The Update a GitHub release reply describes, or None.

    None for every kind of wrong there is. Note what is *not* read: the
    reply's own download URLs. Nothing in here decides where a person is
    sent.
    """
    if not payload:
        return None
    try:
        body = json.loads(bytes(payload).decode("utf-8"))
    except Exception:                                     # noqa: BLE001
        return None
    if not isinstance(body, dict):
        return None
    if body.get("draft") or body.get("prerelease"):
        return None

    version = str(body.get("tag_name") or "").strip()
    if not version or parse_version(version) is None:
        return None
    return Update(version=version.lstrip("v"),
                  notes=str(body.get("body") or "")[:2000],
                  released=str(body.get("published_at") or ""))


def fetch(url: str = API_URL, timeout: float = TIMEOUT):
    """The reply bytes, or None. The only part of this that touches the
    network, kept alone so everything else can be tested without one."""
    import urllib.request

    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json",
                      "User-Agent": f"EngiCalc/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            if getattr(reply, "status", 200) != 200:
                return None
            return reply.read(1_000_000)
    except Exception:                                     # noqa: BLE001
        return None                                       # quiet, always


def check(current: str = None, url: str = API_URL,
          timeout: float = TIMEOUT):
    """The update worth mentioning, or None.

    Everything upstream can be right and this still returns None, because a
    release matching the version already running is not news.
    """
    found = read_release(fetch(url, timeout))
    if found is None:
        return None
    running = __version__ if current is None else current
    return found if is_newer(found.version, running) else None
