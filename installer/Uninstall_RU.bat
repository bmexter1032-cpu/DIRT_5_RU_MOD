@echo off
setlocal
if not exist "%~dp0_data\setup.ps1" (
    echo Extract the entire release ZIP before running this file.
    pause
    exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0_data\setup.ps1" -Mode uninstall
set "rc=%errorlevel%"
if not "%rc%"=="0" (
    echo Setup did not complete. See the message above.
    pause
)
exit /b %rc%
