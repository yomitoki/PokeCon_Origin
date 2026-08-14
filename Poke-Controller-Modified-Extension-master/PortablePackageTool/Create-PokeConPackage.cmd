@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Create-PokeConPackage.ps1" %*
exit /b %errorlevel%
