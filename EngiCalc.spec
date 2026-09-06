# PyInstaller spec for EngiCalc.
#
# Build with:  pyinstaller EngiCalc.spec
# (or run build_exe.bat, which is the one-click version on Windows)
#
# Produces a single windowed EngiCalc.exe in dist\ with no Python
# installation needed on the target machine.

import os

from PyInstaller.utils.hooks import collect_submodules

icon_path = 'app_icon.ico' if os.path.exists('app_icon.ico') else None

# `build_exe.bat debug` sets this to get a console build, which is the only
# way to see a traceback from a frozen run -- the windowed build fails
# silently, with the process alive and no window.
DEBUG = os.environ.get('ENGICALC_BUILD_DEBUG') == '1'

# The formula library imports its eleven branch modules by name
# (library.py::load_builtin uses importlib), so a static import scan sees
# none of them and the frozen app dies on startup with
# "No module named 'engicalc.formulas.data'". Collecting the whole package
# also covers the next branch module added to _DATA_MODULES, which would
# otherwise break the build again in exactly the same way.
hidden = collect_submodules('engicalc')

# SymPy reaches for modules by name at runtime -- `solve` and `integrate`
# between them pull in large parts of the library that no static import
# scan can see, and a missing one surfaces as a solver that works on the
# development machine and fails on a customer's. Collecting the package
# wholesale costs build time and about 40 MB in the exe, and buys back
# the guarantee that anything the solver reaches for is actually there.
hidden += collect_submodules('sympy')
hidden += [
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_agg',
    'openpyxl',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Nothing here is used by the app. matplotlib in particular will
    # happily drag in every GUI toolkit it can find a backend for, and
    # each one adds tens of megabytes to a build that only ever draws
    # into Tk.
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        'IPython', 'jupyter', 'notebook', 'tornado',
        'pytest', 'unittest2', 'pandas', 'scipy',
        'matplotlib.backends.backend_webagg',
        'matplotlib.backends.backend_qtagg',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# A folder rather than one packed file. A one-file build unpacks the whole
# sixty megabytes to a temporary directory on every launch and shows nothing
# while it does it - twenty or thirty seconds on a cold start, which reads as
# a program that has failed to open. It is also the shape of a dropper, and
# with UPX on top it is about as close to a guaranteed antivirus false
# positive as an unsigned build gets.
#
# One-file earns its keep when somebody is handed a bare executable. There is
# an installer here, so it earns nothing.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EngiCalc-debug' if DEBUG else 'EngiCalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=DEBUG,          # windowed normally, console for a debug build
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

collected = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EngiCalc-debug' if DEBUG else 'EngiCalc',
)
