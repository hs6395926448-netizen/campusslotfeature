"""
app/utils/validators.py - Input Validation Helpers

All user input is validated here before touching the database.
This keeps route handlers clean and ensures consistency.

Returns (is_valid: bool, error_message: str) tuples.
"""

import re
from datetime import date, datetime


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validates a phone number.
    Expects international format with country code: +919876543210
    Accepts: +91..., 0091..., plain 10-digit numbers (assumed Indian)
    
    Returns: (is_valid, error_message)
    """
    if not phone:
        return False, "Phone number is required."

    # Remove spaces and dashes for checking
    cleaned = phone.replace(" ", "").replace("-", "")

    # Check for valid international format or 10-digit local number
    pattern = r"^\+?[1-9]\d{9,14}$"
    if not re.match(pattern, cleaned):
        return False, "Invalid phone number. Use format: +91XXXXXXXXXX"

    return True, ""


def validate_name(name: str) -> tuple[bool, str]:
    """
    Validates a person's name.
    Must be 2-100 characters, letters and spaces only.
    """
    if not name or not name.strip():
        return False, "Name is required."

    if len(name.strip()) < 2:
        return False, "Name must be at least 2 characters."

    if len(name.strip()) > 100:
        return False, "Name must be under 100 characters."

    if not re.match(r"^[A-Za-z\s'-]+$", name.strip()):
        return False, "Name can only contain letters, spaces, hyphens, and apostrophes."

    return True, ""


def validate_service_data(data: dict) -> tuple[bool, str]:
    """
    Validates the payload for creating a new service.
    business_id is no longer validated here — it comes from current_user
    server-side, so we don't accept or check it from the request body.
    """
    if not data.get("name") or not data["name"].strip():
        return False, "Service name is required."

    if len(data["name"].strip()) > 120:
        return False, "Service name must be under 120 characters."

    try:
        duration = int(data.get("duration_minutes", 0))
        if duration < 5 or duration > 480:
            return False, "Duration must be between 5 and 480 minutes."
    except (ValueError, TypeError):
        return False, "Duration must be a whole number of minutes."

    return True, ""


def validate_slot_data(data: dict) -> tuple[bool, str]:
    """
    Validates the payload for creating a new slot.
    
    Expected keys: service_id, date, start_time, end_time
    """
    if not data.get("service_id"):
        return False, "Service ID is required."

    # Validate date
    try:
        slot_date = date.fromisoformat(data.get("date", ""))
        if slot_date < date.today():
            return False, "Slot date cannot be in the past."
    except (ValueError, TypeError):
        return False, "Date must be in YYYY-MM-DD format."

    # Validate time format
    time_pattern = r"^\d{2}:\d{2}$"

    start_time = data.get("start_time", "")
    if not re.match(time_pattern, start_time):
        return False, "Start time must be in HH:MM format (e.g., 09:30)."

    # End time is calculated from the selected appointment purpose on the
    # server. Keep accepting it for backward compatibility with the frontend,
    # but only require a valid value when the caller supplies one.
    end_time = data.get("end_time", "")
    if end_time and not re.match(time_pattern, end_time):
        return False, "End time must be in HH:MM format (e.g., 10:00)."

    try:
        datetime.strptime(start_time, "%H:%M")
        if end_time:
            datetime.strptime(end_time, "%H:%M")
    except ValueError:
        return False, "Invalid time values."

    return True, ""


def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    Strips whitespace and truncates to max_length.
    Use for optional fields like notes/descriptions.
    """
    if not value:
        return ""
    return str(value).strip()[:max_length]
