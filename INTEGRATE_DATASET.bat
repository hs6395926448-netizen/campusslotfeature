@echo off
cd /d "%~dp0"
echo Integrating Engineering College dataset into CampusSlot...
python integrate_dataset.py
pause
