@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "LAUNCHER=%ROOT_DIR%PokeConRuntimeLauncher.ps1"

if not exist "%LAUNCHER%" (
    echo [ERROR] Runtime launcher was not found:
    echo %LAUNCHER%
    pause
    exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo PokeCon finished with exit code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
