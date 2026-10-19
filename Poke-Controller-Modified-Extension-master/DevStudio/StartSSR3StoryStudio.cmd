@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
set "SSR3_SESSION=%PROJECT_ROOT%\SerialController\CommandsRecording\SSR3_Story\20260811_213326_311128_SS3_Story"
set "SSR3_SOURCE=%PROJECT_ROOT%\SerialController\Commands\PythonCommands\SSR\SSR3_Story\SSR3_Story.py"
set "PYTHONW=%PROJECT_ROOT%\.venv314\Scripts\pythonw.exe"
if not exist "%PYTHONW%" set "PYTHONW=pythonw"
start "SSR3 Story Step Studio" "%PYTHONW%" "%~dp0LightweightOperationStudio.py" --session "%SSR3_SESSION%" --source "%SSR3_SOURCE%"
endlocal
