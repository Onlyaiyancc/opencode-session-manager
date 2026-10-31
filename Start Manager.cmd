@echo off
setlocal
cd /d "%~dp0"
if exist "%USERPROFILE%\anaconda3\python.exe" (
  "%USERPROFILE%\anaconda3\python.exe" server.py --open
) else (
  python server.py --open
)
if errorlevel 1 pause
