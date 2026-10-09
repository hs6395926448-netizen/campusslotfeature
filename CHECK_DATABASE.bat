@echo off
cd /d "%~dp0"
python -c "from config import LOCAL_DB; print('CampusSlot folder:', __import__('pathlib').Path.cwd()); print('Database file:', LOCAL_DB); print('Exists:', LOCAL_DB.exists())"
pause
