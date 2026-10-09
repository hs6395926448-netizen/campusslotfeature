"""Signed, phone-friendly teacher actions for appointment status updates.

The links generated here are short-lived signed capabilities. They allow a
teacher to confirm/cancel/complete an appointment directly from a phone without
requiring a second login, while still binding the action to the exact teacher,
appointment and appointment version.
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app, url_for


_SALT = "campusslot-teacher-appointment-action-v1"
_MAX_AGE_SECONDS = 72 * 60 * 60  # 72 hours


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def make_action_token(appointment, action):
    allowed = {"confirmed", "cancelled", "completed", "rejected", "reschedule"}
    if action not in allowed:
        raise ValueError("Unsupported teacher action.")
    teacher_id = appointment.slot.service.business_id
    payload = {
        "appointment_id": appointment.id,
        "teacher_id": teacher_id,
        "action": action,
        "version": appointment.version,
    }
    return _serializer().dumps(payload)


def read_action_token(token):
    try:
        return _serializer().loads(token, max_age=_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise ValueError("This teacher action link has expired. Please open the teacher dashboard for the latest action.") from exc
    except BadSignature as exc:
        raise ValueError("This teacher action link is invalid.") from exc


def make_action_url(appointment, action):
    token = make_action_token(appointment, action)
    # Build the path from Flask's registered endpoint so blueprint prefixes stay
    # in sync with the actual route. BASE_URL must be reachable by the person
    # opening the email (localhost only works on the same computer).
    path = url_for("booking.teacher_appointment_action", token=token, _external=False)
    return f"{current_app.config['BASE_URL'].rstrip('/')}{path}"


def action_label(action):
    return {
        "confirmed": "Confirm meeting",
        "cancelled": "Cancel meeting",
        "rejected": "Reject booking request",
        "completed": "Mark completed",
        "reschedule": "Update meeting date and time",
    }.get(action, "Update meeting")
