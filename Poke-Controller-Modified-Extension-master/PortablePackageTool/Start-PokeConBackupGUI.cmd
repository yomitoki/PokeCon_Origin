@echo off
setlocal
set "TOOL=%~dp0backup_gui.py"
if exist "%~dp0..\.venv312\Scripts\pythonw.exe" (
  start "" "%~dp0..\.venv312\Scripts\pythonw.exe" "%TOOL%"
  exit /b 0
)
if exist "%~dp0..\.venv314\Scripts\pythonw.exe" (
  start "" "%~dp0..\.venv314\Scripts\pythonw.exe" "%TOOL%"
  exit /b 0
)
if exist "%~dp0..\.venv314t\Scripts\pythonw.exe" (
  start "" "%~dp0..\.venv314t\Scripts\pythonw.exe" "%TOOL%"
  exit /b 0
)
where pyw.exe >nul 2>nul
if %errorlevel% equ 0 (
  start "" pyw.exe -3 "%TOOL%"
  exit /b 0
)
echo Python was not found.
echo Run SetupPokeConPythonEnvironments.bat first.
pause
exit /b 1
