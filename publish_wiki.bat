@echo off
rem Publish docs\wiki to the GitHub wiki.
rem
rem GitHub only creates the wiki repository once the first page has been made
rem through the web interface, and there is no API for that - so this cannot
rem run until somebody has clicked once:
rem
rem     https://github.com/sheetdeveloper/engicalc/wiki  ->  Create the first page
rem     (type anything, Save)
rem
rem After that this replaces whatever is there with docs\wiki, and can be run
rem again whenever those pages change.

setlocal
set REPO=https://github.com/sheetdeveloper/engicalc.wiki.git
set WORK=%TEMP%\engicalc-wiki

echo.
echo Publishing docs\wiki to %REPO%
echo.

if exist "%WORK%" rmdir /s /q "%WORK%"
git clone "%REPO%" "%WORK%"
if errorlevel 1 (
    echo.
    echo ============================================
    echo  The wiki does not exist yet.
    echo ============================================
    echo  GitHub creates it when the first page is
    echo  made by hand, and there is no API for it:
    echo.
    echo    1. open the repo's Wiki tab
    echo    2. Create the first page
    echo    3. type anything and Save
    echo.
    echo  Then run this again.
    echo ============================================
    exit /b 1
)

rem Everything in docs\wiki, and nothing that used to be there and is not.
del /q "%WORK%\*.md" 2>nul
copy /y "%~dp0docs\wiki\*.md" "%WORK%\" >nul

pushd "%WORK%"
git add -A
git diff --cached --quiet && (echo Nothing to publish - already up to date. & popd & exit /b 0)
git commit -m "Update the wiki from docs/wiki"
git push
popd

echo.
echo ============================================
echo  Published.
echo  https://github.com/sheetdeveloper/engicalc/wiki
echo ============================================
endlocal
