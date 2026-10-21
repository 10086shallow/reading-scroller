@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH="
set "PYTHONHOME="

if not exist "%~dp0runtime\pythonw.exe" goto missing
start "" "%~dp0runtime\pythonw.exe" "%~dp0app.py"
exit /b

:missing
echo [ERROR] runtime folder is missing or incomplete.
echo Please extract the whole folder again.
pause
