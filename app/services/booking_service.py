"""
app/services/booking_service.py - Core Booking Logic

This is the heart of the application.
All database writes go through this layer so that:
1. Business logic stays out of route handlers
2. Transactions are managed correctly
3. Double-booking is prevented atomically

The golden rule: slot.is_booked = True and Appointment creation
happen in the SAME transaction. If either fails, both roll back.
"""

from app import db
from app.models.slot import Slot
from app.models.appointment import Appointment
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from flask import current_app



def book_appointment(slot_id: int, customer_name: str, customer_phone: str, notes: str = "", student_id=None) -> dict:
    """
    Books an appointment for a customer.

    Steps:
    1. Fetch slot and lock it for update (prevents race conditions)
    2. Check it's not already booked
    3. Create Appointment record
    4. Mark slot as booked
    5. Commit both in one transaction
    6. Send email confirmation

    Args:
        slot_id: ID of the slot to book
        customer_name: Customer's full name
        customer_phone: Student phone contact stored on the booking
        notes: Optional message from customer

    Returns:
        dict with success status and appointment details

    Raises:
        ValueError: If slot is already booked or doesn't exist
    """

    # One request per student per calendar day. This is enforced here so UI,
    # multiple tabs, and direct API attempts all receive the same protection.
    request_date = None
    if student_id is not None:
        tz = ZoneInfo(current_app.config.get("APPOINTMENT_TIMEZONE", "Asia/Kolkata"))
        now_local = datetime.now(timezone.utc).astimezone(tz)
        request_date = now_local.date().isoformat()
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        existing = Appointment.query.filter(Appointment.student_id == student_id, Appointment.request_date == request_date).order_by(Appointment.booked_at.desc()).first()
        # Backward-compatible fallback for any legacy appointment not yet migrated.
        if existing is None:
            existing = Appointment.query.filter(Appointment.student_id == student_id, Appointment.request_date.is_(None), Appointment.booked_at >= start_utc, Appointment.booked_at < end_utc).order_by(Appointment.booked_at.desc()).first()
        if existing:
            remaining = max(0, int((end_local - now_local).total_seconds()))
            hours, rem = divmod(remaining, 3600); minutes, _ = divmod(rem, 60)
            raise ValueError(f"DAILY_LIMIT|{remaining}|{existing.tracking_id}|{hours}|{minutes}")

    # Use with_for_update() to lock the slot row in the DB during this transaction.
    # This prevents two simultaneous requests from both seeing is_booked=False
    # and both successfully booking the same slot (race condition / double booking).
    slot = Slot.query.with_for_update().get(slot_id)

    if not slot:
        raise ValueError("Slot not found.")

    if slot.is_booked:
        raise ValueError("This slot has already been booked. Please choose another.")

    try:
        # Create the appointment record
        appointment = Appointment(
            slot_id=slot.id,
            student_id=student_id,
            request_date=request_date,
            customer_name=customer_name.strip(),
            customer_phone=customer_phone.strip(),
            customer_notes=notes.strip() if notes else "",
            extra_data={"source": "web", "booking_timezone": current_app.config.get("APPOINTMENT_TIMEZONE", "Asia/Kolkata")},
            status="pending",
        )
        db.session.add(appointment)

        # Mark slot as booked — this happens in the SAME transaction
        slot.is_booked = True

        # Commit both changes atomically
        from app.services.audit_service import record_audit
        record_audit(
            "appointment.created",
            "appointment",
            appointment.id,
            {"tracking_id": appointment.tracking_id, "slot_id": slot.id, "status": appointment.status},
        )
        db.session.commit()

    except IntegrityError as e:
        db.session.rollback()
        # The unique student/day index is the final concurrency guard. If another
        # request won the race, report the same daily-limit response instead of
        # exposing a database error.
        if student_id is not None and request_date:
            tz = ZoneInfo(current_app.config.get("APPOINTMENT_TIMEZONE", "Asia/Kolkata"))
            now_local = datetime.now(timezone.utc).astimezone(tz)
            end_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            existing = Appointment.query.filter_by(student_id=student_id, request_date=request_date).order_by(Appointment.booked_at.desc()).first()
            if existing:
                remaining = max(0, int((end_local - now_local).total_seconds()))
                hours, rem = divmod(remaining, 3600); minutes, _ = divmod(rem, 60)
                raise ValueError(f"DAILY_LIMIT|{remaining}|{existing.tracking_id}|{hours}|{minutes}")
        raise RuntimeError(f"Booking failed due to a database constraint: {str(e)}")
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Booking failed due to a database error: {str(e)}")

    # Notify both student and teacher after the transaction succeeds.
    # Notification failure never rolls back a successful booking.
    from app.services.notification_service import notify_appointment
    notification_result = notify_appointment(appointment, "pending")

    return {
        "success": True,
        "tracking_id": appointment.tracking_id,
        "message": f"Appointment booked! Your tracking ID is {appointment.tracking_id}",
        "appointment": appointment.to_dict(),
        "notifications": notification_result,
    }


def get_appointment_by_tracking_id(tracking_id: str) -> dict:
    """
    Fetches appointment status using the tracking ID.

    Args:
        tracking_id: The unique tracking ID (e.g., "SL-A3F7C2")

    Returns:
        Appointment dict with full slot/service/business details

    Raises:
        ValueError: If no appointment found with that ID
    """
    appointment = Appointment.query.filter_by(tracking_id=tracking_id.upper()).first()

    if not appointment:
        raise ValueError(f"No appointment found with tracking ID: {tracking_id}")

    return appointment.to_dict()


def update_appointment_status(appointment_id: int, new_status: str, teacher_id=None, expected_version=None) -> dict:
    """
    Updates appointment status from the business dashboard.

    Valid statuses: pending → confirmed → completed / cancelled

    Args:
        appointment_id: Database ID of the appointment
        new_status: One of the STATUS_CHOICES
        expected_version: Optional optimistic-lock version from a phone action link

    Returns:
        Updated appointment dict
    """
    valid_statuses = ["pending", "confirmed", "completed", "cancelled"]
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        raise ValueError("Appointment not found.")

    if expected_version is not None and appointment.version != expected_version:
        raise ValueError(
            "This appointment was already updated. Refresh the teacher dashboard "
            "or open the latest notification link."
        )

    if teacher_id is not None and appointment.slot.service.business_id != teacher_id:
        raise ValueError("Not authorized to update this appointment.")

    appointment.status = new_status

    # A cancelled appointment releases its slot so another student can book it.
    # Completing/confirming an appointment keeps the slot unavailable.
    if new_status == "cancelled":
        appointment.slot.is_booked = False
    elif new_status in {"pending", "confirmed", "completed"}:
        appointment.slot.is_booked = True

    try:
        from app.services.audit_service import record_audit
        record_audit(
            "appointment.status_changed",
            "appointment",
            appointment.id,
            {"tracking_id": appointment.tracking_id, "new_status": new_status},
        )
        appointment.version = (appointment.version or 0) + 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Status update failed: {str(e)}")

    # Notify both parties after the database transaction succeeds.
    from app.services.notification_service import notify_appointment
    notification_result = notify_appointment(appointment, new_status)

    result = appointment.to_dict()
    result["notifications"] = notification_result
    return result
