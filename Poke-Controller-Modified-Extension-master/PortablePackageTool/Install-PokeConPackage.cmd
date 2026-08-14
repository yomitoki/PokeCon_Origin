@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Restore-PokeConPackage.ps1" %*
exit /b %errorlevel%
