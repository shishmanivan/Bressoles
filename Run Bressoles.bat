@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" "%CD%\.venv\Scripts\pythonw.exe" "%CD%\Main.py"
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" "%CD%\.venv\Scripts\python.exe" "%CD%\Main.py"
    exit /b 0
)

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pythonw.exe "%CD%\Main.py"
    exit /b 0
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    python.exe "%CD%\Main.py"
    pause
    exit /b %ERRORLEVEL%
)

echo Python was not found.
echo Install Python or restore the .venv folder, then run this file again.
pause
exit /b 1
