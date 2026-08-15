@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "RECOVERY_SCRIPT=%ROOT_DIR%SerialController\PokeConRecovery.py"
set "RECOVERY_PYTHON=%ROOT_DIR%.venv314\Scripts\pythonw.exe"

if not exist "%RECOVERY_PYTHON%" set "RECOVERY_PYTHON=%ROOT_DIR%.venv312\Scripts\pythonw.exe"
if not exist "%RECOVERY_PYTHON%" set "RECOVERY_PYTHON=%ROOT_DIR%.venv37\Scripts\pythonw.exe"

if not exist "%RECOVERY_SCRIPT%" (
    echo [ERROR] PokeCon recovery screen was not found:
    echo %RECOVERY_SCRIPT%
    pause
    exit /b 2
)

if not exist "%RECOVERY_PYTHON%" (
    echo [ERROR] Python for the PokeCon recovery screen was not found.
    echo Please run SetupPokeConPythonEnvironments.bat first.
    pause
    exit /b 3
)

start "PokeCon Recovery" "%RECOVERY_PYTHON%" "%RECOVERY_SCRIPT%"
exit /b 0
