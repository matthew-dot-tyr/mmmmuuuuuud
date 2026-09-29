@echo off
rem Double-click to run the project. Demo without keys: start.bat -Demo
rem Bypass only for this script: Windows blocks .ps1 files by default.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
