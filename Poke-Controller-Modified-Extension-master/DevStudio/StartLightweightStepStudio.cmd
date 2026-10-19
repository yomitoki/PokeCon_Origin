@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
set "PYTHONW=%PROJECT_ROOT%\.venv314\Scripts\pythonw.exe"
if not exist "%PYTHONW%" set "PYTHONW=pythonw"
start "PokeCon Lightweight Step Studio" "%PYTHONW%" "%~dp0LightweightOperationStudio.py"
endlocal
