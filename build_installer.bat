@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0build_installer.ps1"
endlocal

