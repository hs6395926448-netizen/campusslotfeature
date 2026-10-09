"""Email-only notification dispatcher for CampusSlot.

Normal user actions never wait for a provider's network request. If a Celery/Redis
broker is configured, notifications use Celery; otherwise they run in a small
in-process background pool. The in-process fallback is fast but not durable
across a process restart, so a broker is recommended for high-volume production.
"""
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from app.services.email_service import send_appointment_email, send_registration_email
from app import db
from app.models.notification_log import NotificationLog


# Each Gunicorn worker owns a tiny pool. Email I/O stays off the request path.
_email_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="campusslot-email")


def notify_appointment(appointment, event="confirmed"):
    """Synchronous delivery used by the admin's explicit test-email action."""
    result = {"email": {"sent": 0, "attempted": 0, "errors": []}}
    try:
        result["email"] = send_appointment_email(appointment, event)
    except Exception as exc:
        result["email"]["errors"] = [str(exc)]
        current_app.logger.exception(
            "CampusSlot email dispatcher failed | appointment=%s | event=%s",
            getattr(appointment, "tracking_id", appointment.id), event
        )
    try:
        channel_result = result["email"]
        errors = channel_result.get("errors") or []
        attempted = int(channel_result.get("attempted") or 0)
        sent = int(channel_result.get("sent") or 0)
        status = "sent" if sent else ("failed" if errors else "skipped")
        db.session.add(NotificationLog(
            appointment_id=appointment.id, channel="email",
            recipient="multiple" if attempted > 1 else "configured-recipient",
            event=event, status=status,
            error_message=" | ".join(errors[:5]) if errors else None,
            attempt_count=max(attempted, 1),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "CampusSlot email audit logging failed | appointment=%s | event=%s",
            getattr(appointment, "tracking_id", appointment.id), event
        )
    current_app.logger.info(
        "CampusSlot EMAIL RESULT | appointment=%s | event=%s | email=%s/%s",
        getattr(appointment, "tracking_id", appointment.id), event,
        result["email"]["sent"], result["email"]["attempted"]
    )
    return result


def notify_registration(record, event="submitted"):
    try:
        return {"email": send_registration_email(record, event)}
    except Exception as exc:
        current_app.logger.exception(
            "CampusSlot registration email failed | registration=%s | event=%s",
            getattr(record, "registration_id", None), event
        )
        return {"email": {"sent": 0, "attempted": 1, "errors": [str(exc)]}}


def _background_appointment_delivery(app, appointment_id, event):
    """Re-fetch the record inside its own app/database context."""
    from app.models.appointment import Appointment

    with app.app_context():
        try:
            appointment = db.session.get(Appointment, int(appointment_id))
            if appointment is None:
                app.logger.warning(
                    "Skipping background email: appointment %s no longer exists", appointment_id
                )
                return
            result = notify_appointment(appointment, event)
            errors = result.get("email", {}).get("errors") or []
            if errors:
                app.logger.error(
                    "Background appointment email failed | appointment=%s | event=%s | errors=%s",
                    appointment_id, event, " | ".join(errors[:3])
                )
        except Exception:
            app.logger.exception(
                "Background appointment email crashed | appointment=%s | event=%s",
                appointment_id, event
            )
        finally:
            db.session.remove()


def _background_registration_delivery(app, role, record_id, event):
    """Re-fetch the record inside its own app/database context."""
    from app.models.business import Business
    from app.models.student import Student

    model = Business if role == "teacher" else Student if role == "student" else None
    if model is None:
        app.logger.error("Skipping background email for unsupported role %r", role)
        return
    with app.app_context():
        try:
            record = db.session.get(model, int(record_id))
            if record is None:
                app.logger.warning(
                    "Skipping background registration email: %s %s no longer exists",
                    role, record_id
                )
                return
            result = notify_registration(record, event)
            errors = result.get("email", {}).get("errors") or []
            if errors:
                app.logger.error(
                    "Background registration email failed | role=%s | id=%s | errors=%s",
                    role, record_id, " | ".join(errors[:3])
                )
        except Exception:
            app.logger.exception(
                "Background registration email crashed | role=%s | id=%s | event=%s",
                role, record_id, event
            )
        finally:
            db.session.remove()


def _submit_in_process(task_name, *args):
    app = current_app._get_current_object()
    try:
        _email_executor.submit(task_name, app, *args)
        return True
    except Exception:
        current_app.logger.exception("Could not schedule background email task")
        return False


def enqueue_appointment_notification(appointment, event="confirmed"):
    """Schedule email without holding up the booking/cancel response."""
    broker_url = (current_app.config.get("CELERY_BROKER_URL") or "").strip()
    if broker_url:
        try:
            from celery_app import send_appointment_notification_task
            send_appointment_notification_task.delay(appointment.id, event)
            current_app.logger.info(
                "CampusSlot email queued with Celery | appointment=%s | event=%s",
                appointment.tracking_id, event
            )
            return {"email": {"sent": 0, "attempted": 0, "errors": [], "queued": True, "queue": "celery"}}
        except Exception:
            # A broken optional broker must not turn a fast user action into a
            # slow SMTP/API request. Log the issue and use the in-process pool.
            current_app.logger.exception("Email broker unavailable; using background fallback")

    scheduled = _submit_in_process(
        _background_appointment_delivery, appointment.id, event
    )
    return {
        "email": {
            "sent": 0, "attempted": 0,
            "errors": [] if scheduled else ["Could not schedule background email."],
            "queued": scheduled, "queue": "in-process" if scheduled else None,
        }
    }


def enqueue_registration_notification(record, event="submitted"):
    """Queue registration email by stable database ID, never by passing ORM objects."""
    role = "teacher" if record.__class__.__name__ == "Business" else "student"
    broker_url = (current_app.config.get("CELERY_BROKER_URL") or "").strip()
    if broker_url:
        try:
            from celery_app import send_registration_notification_task
            send_registration_notification_task.delay(role, record.id, event)
            current_app.logger.info(
                "CampusSlot registration email queued with Celery | role=%s | id=%s | event=%s",
                role, record.id, event
            )
            return {"email": {"sent": 0, "attempted": 0, "errors": [], "queued": True, "queue": "celery"}}
        except Exception:
            current_app.logger.exception("Registration email broker unavailable; using background fallback")

    scheduled = _submit_in_process(
        _background_registration_delivery, role, record.id, event
    )
    return {
        "email": {
            "sent": 0, "attempted": 0,
            "errors": [] if scheduled else ["Could not schedule background email."],
            "queued": scheduled, "queue": "in-process" if scheduled else None,
        }
    }
