@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "SETUP_SCRIPT=%ROOT_DIR%SetupPokeConPythonEnvironments.ps1"

if not exist "%SETUP_SCRIPT%" (
    echo [ERROR] Python environment setup script was not found:
    echo %SETUP_SCRIPT%
    pause
    exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo PokeCon Python environment setup finished successfully.
) else (
    echo PokeCon Python environment setup failed with exit code %EXIT_CODE%.
    echo Review the messages above, then run this BAT again.
)
pause
exit /b %EXIT_CODE%
