"""Repair CampusSlot's local SQLite database.

This makes a timestamped backup of the current DB, removes the stale local DB,
then creates a fresh schema and demo teacher/student data.
"""
from pathlib import Path
from datetime import datetime
import shutil

from app import create_app
from config import LOCAL_DB

if LOCAL_DB.exists():
    backup = LOCAL_DB.with_name(f"campusslot_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
    shutil.copy2(LOCAL_DB, backup)
    LOCAL_DB.unlink()
    print(f"Backed up old database to: {backup}")

app = create_app("development")
print("\nDatabase repaired successfully.")
print(f"Database: {LOCAL_DB}")
print("Teacher: teacher@campusslot.com / password123")
print("Student: student@campusslot.com / password123")
