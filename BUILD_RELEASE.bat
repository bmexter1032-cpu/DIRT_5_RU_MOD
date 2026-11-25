@echo off
setlocal
py -3 "%~dp0tools\build_easy_release.py"
set "rc=%errorlevel%"
if not "%rc%"=="0" echo BUILD FAILED. See message above.
pause
exit /b %rc%
