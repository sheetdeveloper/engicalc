@echo off
REM ===================================================================
REM  EngiCalc - compile installer.iss into Output\EngiCalc_Setup.exe
REM
REM  Requires Inno Setup: https://jrsoftware.org/isdl.php (free)
REM  Run build_exe.bat first, so dist\EngiCalc.exe exists.
REM ===================================================================

setlocal EnableExtensions
cd /d "%~dp0"
title EngiCalc - installer

REM  Inno Setup's usual homes, newest first. Set ISCC yourself if it
REM  lives somewhere else on this machine.
set ISCC=
for %%P in (
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
REM  %%~P strips the quotes the list needs; they go back on at the point
REM  of use, so a path with a space in it survives either way.
) do if not defined ISCC if exist %%P set "ISCC=%%~P"

if not defined ISCC (
    echo.
    echo ERROR: Inno Setup was not found in any of the usual places.
    echo Install it from https://jrsoftware.org/isdl.php ^(free^), or
    echo edit the ISCC path near the top of this script.
    pause
    exit /b 1
)

if not exist dist\EngiCalc\EngiCalc.exe (
    echo.
    echo ERROR: dist\EngiCalc\EngiCalc.exe not found.
    echo Run build_exe.bat first.
    pause
    exit /b 1
)

REM  build_exe.bat already stamped the version. Doing it again here
REM  costs nothing and covers compiling the installer on its own.
echo.
echo Stamping installer.iss with the current app version...
py -3 stamp_installer_version.py 2>nul || python stamp_installer_version.py
if errorlevel 1 (
    echo.
    echo ERROR: failed to stamp installer.iss - see the message above.
    pause
    exit /b 1
)

echo.
echo Compiling the installer...
"%ISCC%" installer.iss
if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup failed - see the messages above.
    pause
    exit /b 1
)

echo.
if exist Output\EngiCalc_Setup.exe (
    for %%F in (Output\EngiCalc_Setup.exe) do set "SETUPSIZE=%%~zF"
    echo ============================================
    echo  SUCCESS
    echo ============================================
    echo  Installer: Output\EngiCalc_Setup.exe
    echo  This is the single file you hand to anyone.
    echo ============================================
) else (
    echo Something went wrong - check the messages above.
)

pause
