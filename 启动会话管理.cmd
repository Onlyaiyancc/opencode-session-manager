@echo off
setlocal
cd /d "%~dp0"
if exist "%USERPROFILE%\anaconda3\python.exe" (
  "%USERPROFILE%\anaconda3\python.exe" main.py --open
) else (
  python main.py --open
)
if errorlevel 1 pause
