@echo off
cd /d "%~dp0"
echo WARNING: This deletes the local CampusSlot database and recreates demo data.
choice /M "Continue"
if errorlevel 2 exit /b 0
python setup.py --reset
pause
