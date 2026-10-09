@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run setup.bat, then run start.bat again.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python run.py
pause
