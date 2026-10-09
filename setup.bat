@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo CampusSlot - one-time Windows setup
echo ==========================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found. Install Python from python.org and enable the launcher.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  echo Reusing existing .venv.
) else (
  py -3.12 -m venv .venv >nul 2>nul
  if errorlevel 1 py -3.13 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 (
    echo Could not create virtual environment. Check Python installation.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
if not exist ".env" copy /Y ".env.example" ".env" >nul
if errorlevel 1 goto :fail
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
python -c "from zoneinfo import ZoneInfo; ZoneInfo(\"Asia/Kolkata\"); print(\"Timezone data OK\")"
if errorlevel 1 goto :fail
python setup.py
if errorlevel 1 goto :fail
echo.
echo Setup complete! Run start.bat to start CampusSlot.
echo Demo teacher: teacher@campusslot.com / password123
echo Demo student: student@campusslot.com / password123
echo Demo admin: admin@campusslot.com / admin123
echo URL: http://127.0.0.1:5000
pause
exit /b 0
:fail
echo.
echo Setup failed. Copy the last 15 lines of this window to ChatGPT.
pause
exit /b 1
