@echo off
REM ===================================================================
REM  EngiCalc launcher (Windows)
REM
REM  Double-click this file to start the app.
REM  First run creates a private Python environment in .venv and
REM  installs SymPy, matplotlib, NumPy and openpyxl into it - that
REM  takes a couple of minutes. Every run after that is instant.
REM
REM  run_engicalc.bat            start the app
REM  run_engicalc.bat reinstall  rebuild the environment from scratch
REM  run_engicalc.bat test       run the self-tests
REM ===================================================================

setlocal EnableExtensions
cd /d "%~dp0"
title EngiCalc

set "VENV=.venv"
set "VPY=%VENV%\Scripts\python.exe"

REM ---- find a Python to bootstrap with -------------------------------
py -3 --version >nul 2>&1
if %errorlevel%==0 (set "PYCMD=py -3") else (set "PYCMD=python")
%PYCMD% --version >nul 2>&1
if errorlevel 1 goto :nopython

REM ---- optional: forced rebuild --------------------------------------
if /i "%~1"=="reinstall" (
    echo Removing the old environment...
    if exist "%VENV%" rmdir /s /q "%VENV%"
)

REM ---- create the environment on first run ---------------------------
if not exist "%VPY%" (
    echo.
    echo First run - setting up EngiCalc. This happens once.
    echo Creating a private Python environment in "%VENV%"...
    %PYCMD% -m venv "%VENV%"
    if errorlevel 1 goto :novenv
    echo Installing SymPy, matplotlib, NumPy and openpyxl...
    "%VPY%" -m pip install --upgrade pip --quiet
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :nodeps
    echo Setup finished.
    echo.
)

REM ---- tkinter must be present ---------------------------------------
"%VPY%" -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :notk

REM ---- run -----------------------------------------------------------
if /i "%~1"=="test" (
    "%VPY%" -m unittest discover -s tests -v
    echo.
    pause
    goto :eof
)

"%VPY%" main.py %*
if errorlevel 1 (
    echo.
    echo EngiCalc closed with an error. The message above says why.
    pause
)
goto :eof

REM ---- failure paths --------------------------------------------------
:nopython
echo.
echo Python was not found on this machine.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this
echo file again.
echo.
pause
goto :eof

:novenv
echo.
echo Could not create the Python environment in "%VENV%".
echo If this folder is inside OneDrive or a network drive, copy it to a
echo local folder such as C:\EngiCalc and try again.
echo.
pause
goto :eof

:nodeps
echo.
echo The dependencies could not be installed. This is usually a network
echo or proxy problem. You can retry with:
echo     run_engicalc.bat reinstall
echo.
pause
goto :eof

:notk
echo.
echo This Python was installed without Tkinter, so the window cannot open.
echo Reinstall Python from python.org (the standard installer includes it)
echo and then run:  run_engicalc.bat reinstall
echo.
pause
goto :eof
