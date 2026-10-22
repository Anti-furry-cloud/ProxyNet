@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"
endlocal

