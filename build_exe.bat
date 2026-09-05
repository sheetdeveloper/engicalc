@echo off
REM ===================================================================
REM  EngiCalc - build a standalone Windows .exe
REM
REM  Double-click this, or run it from a command prompt in this folder.
REM  Produces dist\EngiCalc.exe, which runs on a machine with no Python
REM  installed at all.
REM
REM  Requires Python 3.10+ on PATH. Everything else (the build venv,
REM  PyInstaller, the four app dependencies) is installed here.
REM
REM    build_exe.bat            build it
REM    build_exe.bat clean      throw away the build folders first
REM    build_exe.bat debug      build a console version instead
REM
REM  About the debug build: a windowed frozen app that fails on startup
REM  does so silently - the process sits there with no window and no
REM  error. dist\EngiCalc-debug.exe is the same program with a console
REM  attached, so run that from a command prompt to see the traceback.
REM ===================================================================

setlocal EnableExtensions
cd /d "%~dp0"
title EngiCalc - build

set "VENV=.venv-build"
set "VPY=%VENV%\Scripts\python.exe"

echo ============================================
echo  EngiCalc - build script
echo ============================================

REM ---- find a Python ------------------------------------------------
py -3 --version >nul 2>&1
if %errorlevel%==0 (set "PYCMD=py -3") else (set "PYCMD=python")
%PYCMD% --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found on PATH.
    echo Install it from python.org and tick "Add Python to PATH".
    pause
    exit /b 1
)

REM ---- optional clean -----------------------------------------------
if /i "%~1"=="clean" (
    echo Removing previous build output...
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    if exist "%VENV%" rmdir /s /q "%VENV%"
)

REM ---- optional console build ---------------------------------------
set "EXENAME=EngiCalc"
if /i "%~1"=="debug" (
    set "ENGICALC_BUILD_DEBUG=1"
    set "EXENAME=EngiCalc-debug"
    echo.
    echo Building the CONSOLE version, for reading tracebacks.
)

REM ---- [1/5] stamp the version --------------------------------------
REM  Before anything slow, so a version problem costs two seconds
REM  rather than a full PyInstaller run.
echo.
echo [1/5] Stamping the version...
%PYCMD% stamp_installer_version.py
if errorlevel 1 (
    echo.
    echo REFUSING TO BUILD - see the message above.
    pause
    exit /b 1
)

REM ---- [2/5] build environment --------------------------------------
REM  Kept separate from the .venv the app runs from, so installing
REM  PyInstaller cannot disturb a working install of the app.
echo.
echo [2/5] Preparing the build environment...
if not exist "%VPY%" (
    echo   Creating %VENV% - this takes a minute the first time.
    %PYCMD% -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo ERROR: could not create the build environment.
        echo If this machine blocks venv creation, see your IT policy.
        pause
        exit /b 1
    )
)
"%VPY%" -m pip install --upgrade pip --quiet
"%VPY%" -m pip install --quiet -r requirements.txt pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: could not install the build dependencies.
    echo Check the network connection, or any proxy this machine needs.
    pause
    exit /b 1
)

REM ---- [3/5] tests ---------------------------------------------------
REM  A build that ships a broken solver is worse than no build. The
REM  suite takes about twenty seconds, which is nothing next to the
REM  compile that follows.
echo.
echo [3/5] Running the self-tests...
"%VPY%" -m unittest discover -s tests
if errorlevel 1 (
    echo.
    echo ============================================
    echo  REFUSING TO BUILD - the tests failed.
    echo ============================================
    echo  Fix them first. Shipping a build whose tests
    echo  fail means shipping wrong answers, and this
    echo  app is used to size real things.
    pause
    exit /b 1
)

REM ---- [4/5] compile -------------------------------------------------
echo.
echo [4/5] Building the executable - this takes a few minutes.
if exist build rmdir /s /q build
"%VPY%" -m PyInstaller --noconfirm --clean EngiCalc.spec
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed - see the messages above.
    pause
    exit /b 1
)

REM ---- [5/5] check it is really there --------------------------------
echo.
echo [5/5] Checking the result...
if not exist "dist\%EXENAME%.exe" (
    echo.
    echo ERROR: PyInstaller reported success but dist\%EXENAME%.exe
    echo is not there. Check the output above.
    pause
    exit /b 1
)

for %%F in ("dist\%EXENAME%.exe") do set "EXESIZE=%%~zF"
echo.
echo ============================================
echo  SUCCESS
echo ============================================
echo  Built:  dist\%EXENAME%.exe
echo  Size:   %EXESIZE% bytes
echo.
echo  Run it once yourself before handing it out - a frozen build
echo  can fail on an import that works from source.
echo.
echo  To make an installer as well, run build_installer.bat.
echo ============================================
pause
