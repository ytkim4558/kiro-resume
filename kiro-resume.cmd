@echo off
rem kiro-resume.cmd — CMD shim for the PowerShell wrapper.
chcp 65001 >nul 2>nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.kiro\scripts\kiro-resume.ps1" %*
exit /b %ERRORLEVEL%
