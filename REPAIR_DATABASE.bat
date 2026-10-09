@echo off
cd /d "%~dp0"
python repair_database.py
if errorlevel 1 (
  echo.
  echo DATABASE REPAIR FAILED. Read the error above.
  pause
  exit /b 1
)
echo.
echo Database repaired. Now run start.bat
pause
