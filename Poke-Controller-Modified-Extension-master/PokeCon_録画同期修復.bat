@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "REPAIR_SCRIPT=%ROOT_DIR%SerialController\RecordingSyncRepair.py"
set "REPAIR_PYTHON=%ROOT_DIR%.venv314\Scripts\python.exe"

if not exist "%REPAIR_PYTHON%" set "REPAIR_PYTHON=%ROOT_DIR%.venv312\Scripts\python.exe"

if not exist "%REPAIR_SCRIPT%" (
    echo [ERROR] Recording repair tool was not found:
    echo %REPAIR_SCRIPT%
    pause
    exit /b 2
)

if not exist "%REPAIR_PYTHON%" (
    echo [ERROR] Python for the recording repair tool was not found.
    pause
    exit /b 3
)

if "%~1"=="" (
    "%REPAIR_PYTHON%" "%REPAIR_SCRIPT%"
) else (
    "%REPAIR_PYTHON%" "%REPAIR_SCRIPT%" "%~1"
)
set "REPAIR_EXIT=%ERRORLEVEL%"

echo.
echo Finished. Original AVI/WAV/MP4 files were not overwritten.
pause
exit /b %REPAIR_EXIT%
