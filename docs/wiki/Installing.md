# Installing

## Windows

Download `EngiCalc_Setup.exe` from the
[latest release](https://github.com/sheetdeveloper/engicalc/releases/latest)
and run it. That is the whole thing - Python, SymPy, matplotlib and the rest
are inside it, so nothing else needs installing and nothing is added to your
PATH.

Windows will probably warn about an unrecognised publisher. That is because
the installer is not code-signed, which costs a few hundred pounds a year.
Choose **More info** then **Run anyway**.

It installs to `C:\Program Files\EngiCalc` and adds a Start menu entry.
Uninstall it the usual way, through Settings or Add/Remove Programs.

## Checking which version you have

The version is in the bottom-right corner of the window, and on the splash
screen while it starts. **Help -> Check for updates** asks GitHub whether
there is a newer one.

That check is off by default and only happens when you ask for it. You can
turn on a check at startup under **Options -> Check for updates at
startup**. Either way the app only ever *tells* you - it opens the release
page and you decide. It never downloads or installs anything by itself.

## Where it keeps things

Everything lives under `%USERPROFILE%\.engicalc`:

* `history.db` - the calculations you saved, in SQLite
* `sheets\` - worksheets saved as files
* `settings.json` - whether the startup update check is on

Nothing leaves the machine. The only outbound request the app ever makes is
the update check, and that is a single call to the GitHub releases API.

## Running from source

See [Building from source](Building-from-source). Short version: Python 3.11
or newer, `pip install -r requirements.txt`, `python main.py`.

## macOS and Linux

There is no installer, but the source runs. You need Tkinter, which is not
always included:

    sudo apt install python3-tk        # Debian, Ubuntu
    sudo dnf install python3-tkinter   # Fedora

then `pip install -r requirements.txt` and `python main.py`. The app is
tested on Windows; the others should work but are not part of the test runs,
so treat anything odd as a bug worth reporting rather than as expected.

## If it goes wrong

Every unhandled error is written to:

    %USERPROFILE%\.engicalc\errors.log

with the time, the version and the whole traceback, and the dialog that
appears says where that file is. Send that file rather than describing the
message - it says which line, which is the part a description cannot carry.

The log is capped at a quarter of a megabyte and the oldest entries are
dropped, so it will not grow without limit.

## Why the installed program is a folder

It used to be a single packed executable. That is convenient to hand
somebody directly, and it has two costs that only show up once it is
installed: it unpacks sixty megabytes to a temporary folder on **every**
launch, which took twenty or thirty seconds with no window and nothing to
look at, and a packed executable that writes files and runs code out of them
is the shape of a dropper, so antivirus software flagged it.

Since there is an installer anyway, the folder costs nothing. It opens in
about two and a half seconds and the download is smaller than it was.
