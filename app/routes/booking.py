from flask import Blueprint, request, jsonify, render_template
from datetime import date, datetime, timedelta
from app import db
from app.models.slot import Slot
from app.models.service import Service
from flask_login import current_user
from app.services.booking_service import (
    book_appointment,
    get_appointment_by_tracking_id,
    update_appointment_status,
)
from app.services.teacher_action_service import read_action_token, action_label
from app.utils.validators import validate_name, validate_phone, sanitize_string

booking_bp = Blueprint("booking", __name__)


@booking_bp.route("/book-appointment", methods=["POST"])
def book_appointment_route():
    if not current_user.is_authenticated or not str(current_user.get_id()).startswith("student:"):
        return jsonify({"success": False, "error": "Please log in as a student before booking."}), 401
    data = request.get_json(silent=True) or {}
    slot_id = data.get("slot_id")
    if not isinstance(slot_id, int):
        return jsonify({"success": False, "error": "A valid slot is required."}), 400
    ok, err = validate_name(current_user.name)
    if not ok:
        return jsonify({"success": False, "error": err}), 400
    ok, err = validate_phone(current_user.phone)
    if not ok:
        return jsonify({"success": False, "error": err}), 400
    try:
        result = book_appointment(
            slot_id,
            current_user.name,
            current_user.phone,
            sanitize_string(data.get("notes", "")),
            current_user.id,
        )
        return jsonify(result), 201
    except ValueError as e:
        message = str(e)
        if message.startswith("DAILY_LIMIT|"):
            _, seconds, tracking_id, hours, minutes = message.split("|", 4)
            return jsonify({
                "success": False,
                "error": "Daily request limit reached.",
                "daily_limit": True,
                "remaining_seconds": int(seconds),
                "tracking_id": tracking_id,
                "remaining_label": f"{hours} hours {minutes} minutes",
            }), 429
        return jsonify({"success": False, "error": message}), 409
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 500


@booking_bp.route("/track/<string:tracking_id>")
def track_appointment(tracking_id):
    try:
        return jsonify({"success": True, "appointment": get_appointment_by_tracking_id(tracking_id)}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404


@booking_bp.route("/appointments/<int:appointment_id>/status", methods=["PATCH"])
def update_status(appointment_id):
    if not current_user.is_authenticated or not str(current_user.get_id()).startswith("teacher:"):
        return jsonify({"success": False, "error": "Teacher login required."}), 403
    data = request.get_json(silent=True) or {}
    try:
        result = update_appointment_status(
            appointment_id,
            data.get("status", ""),
            teacher_id=current_user.id,
            expected_version=data.get("version"),
        )
        return jsonify({"success": True, "appointment": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 409
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 500


# This page is intentionally outside /api. It is the phone-friendly bridge used
# by signed links delivered by email.
@booking_bp.route("/teacher/appointment-action/<token>", methods=["GET", "POST"])
def teacher_appointment_action(token):
    try:
        payload = read_action_token(token)
    except ValueError as exc:
        return render_template(
            "teacher_action.html",
            error=str(exc),
            appointment=None,
            action=None,
            action_label="Update meeting",
        ), 410

    from app.models.appointment import Appointment
    appointment = Appointment.query.get(payload.get("appointment_id"))
    if not appointment:
        return render_template(
            "teacher_action.html",
            error="Appointment not found.",
            appointment=None,
            action=None,
            action_label="Update meeting",
        ), 404

    teacher_id = appointment.slot.service.business_id
    if int(payload.get("teacher_id", -1)) != int(teacher_id):
        return render_template(
            "teacher_action.html",
            error="This action is not valid for this teacher.",
            appointment=None,
            action=None,
            action_label="Update meeting",
        ), 403

    action = payload.get("action")
    if action not in {"confirmed", "cancelled", "completed", "rejected", "reschedule"}:
        return render_template(
            "teacher_action.html",
            error="Unsupported appointment action.",
            appointment=None,
            action=None,
            action_label="Update meeting",
        ), 400

    if request.method == "GET":
        if appointment.version != payload.get("version"):
            return render_template(
                "teacher_action.html",
                error="This notification link is stale because the meeting was already updated.",
                appointment=appointment,
                action=action,
                action_label=action_label(action),
                stale=True,
            ), 409
        return render_template(
            "teacher_action.html",
            error=None,
            appointment=appointment,
            action=action,
            action_label=action_label(action),
            token=token,
        )

    # POST performs the actual mutation, avoiding state changes from link previews.
    # Rescheduling is handled separately because it updates the booked Slot itself.
    if action == "reschedule":
        if appointment.version != payload.get("version"):
            return render_template(
                "teacher_action.html", error="This notification link is stale because the meeting was already updated. Please use the latest email.",
                appointment=appointment, action=action, action_label=action_label(action), token=token,
            ), 409
        if request.method == "POST":
            if appointment.status not in {"pending", "confirmed"}:
                return render_template(
                    "teacher_action.html", error="Only pending or confirmed meetings can be rescheduled.",
                    appointment=appointment, action=action, action_label=action_label(action), token=token,
                ), 409
            try:
                new_date = date.fromisoformat((request.form.get("meeting_date") or "").strip())
                start_text = (request.form.get("start_time") or "").strip()
                start_dt = datetime.strptime(start_text, "%H:%M")
                if new_date < date.today():
                    raise ValueError("Please choose today or a future date.")
                service = appointment.slot.service
                duration = int(service.duration_minutes or 30)
                end_dt = start_dt + timedelta(minutes=duration)
                if end_dt.date() != start_dt.date():
                    raise ValueError("The meeting must finish before midnight.")
                new_start = start_dt.strftime("%H:%M")
                new_end = end_dt.strftime("%H:%M")
                # Check every service belonging to this teacher, not just this
                # appointment purpose, so one teacher cannot be double-booked.
                other_slots = Slot.query.join(Service, Slot.service_id == Service.id).filter(
                    Service.business_id == teacher_id,
                    Slot.date == new_date,
                    Slot.id != appointment.slot_id,
                ).all()
                for other in other_slots:
                    other_start = datetime.strptime(other.start_time, "%H:%M")
                    other_end = datetime.strptime(other.end_time, "%H:%M")
                    if start_dt < other_end and end_dt > other_start:
                        raise ValueError("That time overlaps another slot. Choose a different date or time.")
                slot = appointment.slot
                slot.date = new_date
                slot.start_time = new_start
                slot.end_time = new_end
                slot.is_booked = True
                appointment.version = (appointment.version or 0) + 1
                from app.services.audit_service import record_audit
                record_audit(
                    "appointment.rescheduled", "appointment", appointment.id,
                    {"tracking_id": appointment.tracking_id, "date": new_date.isoformat(), "start_time": new_start, "end_time": new_end},
                )
                db.session.commit()
                from app.services.notification_service import enqueue_appointment_notification
                enqueue_appointment_notification(appointment, "rescheduled")
                return render_template(
                    "teacher_action.html", success=True, appointment=appointment, action=action,
                    action_label=action_label(action), result={"status": appointment.status},
                )
            except ValueError as exc:
                db.session.rollback()
                return render_template(
                    "teacher_action.html", error=str(exc), appointment=appointment,
                    action=action, action_label=action_label(action), token=token,
                ), 400
            except Exception as exc:
                db.session.rollback()
                return render_template(
                    "teacher_action.html", error="The meeting could not be updated due to a server error. Please try again or use the teacher dashboard.",
                    appointment=appointment, action=action, action_label=action_label(action), token=token,
                ), 500
        return render_template(
            "teacher_action.html", error=None, appointment=appointment, action=action,
            action_label=action_label(action), token=token, reschedule=True, today=date.today().isoformat(),
        )

    try:
        result = update_appointment_status(
            appointment.id,
            ("cancelled" if action == "rejected" else action),
            teacher_id=teacher_id,
            expected_version=payload.get("version"),
        )
        return render_template(
            "teacher_action.html",
            success=True,
            appointment=appointment,
            action=action,
            action_label=action_label(action),
            result=result,
        )
    except ValueError as exc:
        return render_template(
            "teacher_action.html",
            error=str(exc),
            appointment=appointment,
            action=action,
            action_label=action_label(action),
        ), 409
    except RuntimeError as exc:
        return render_template(
            "teacher_action.html",
            error=str(exc),
            appointment=appointment,
            action=action,
            action_label=action_label(action),
        ), 500
