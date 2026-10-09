"""Celery worker for durable background email notifications.

Run locally with: celery -A celery_app.celery worker --loglevel=INFO
Requires CELERY_BROKER_URL (Redis URL), DATABASE_URL, and email provider settings.
"""
import os
from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "").strip()
if not broker_url:
    # Allows importing the web app without queue infrastructure in local development.
    broker_url = "memory://"

celery = Celery("campusslot", broker=broker_url, backend=os.getenv("CELERY_RESULT_BACKEND") or None)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=os.getenv("APPOINTMENT_TIMEZONE", "Asia/Kolkata"),
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 5},
)


@celery.task(name="campusslot.send_appointment_notification", autoretry_for=(Exception,),
             retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_appointment_notification_task(appointment_id, event):
    from run import app
    from app import db
    from app.models.appointment import Appointment
    from app.services.notification_service import notify_appointment
    with app.app_context():
        appointment = db.session.get(Appointment, int(appointment_id))
        if appointment is None:
            app.logger.warning("Skipping queued email: appointment %s no longer exists", appointment_id)
            return {"skipped": True, "reason": "appointment_not_found"}
        result = notify_appointment(appointment, event)
        errors = result.get("email", {}).get("errors") or []
        if errors:
            raise RuntimeError("; ".join(errors[:3]))
        return result


@celery.task(name="campusslot.send_registration_notification", autoretry_for=(Exception,),
             retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_registration_notification_task(role, record_id, event):
    from run import app
    from app import db
    from app.models.business import Business
    from app.models.student import Student
    from app.services.notification_service import notify_registration
    model = Business if role == "teacher" else Student if role == "student" else None
    if model is None:
        raise ValueError("Unsupported registration role")
    with app.app_context():
        record = db.session.get(model, int(record_id))
        if record is None:
            app.logger.warning("Skipping queued email: %s %s no longer exists", role, record_id)
            return {"skipped": True, "reason": "record_not_found"}
        result = notify_registration(record, event)
        errors = result.get("email", {}).get("errors") or []
        if errors:
            raise RuntimeError("; ".join(errors[:3]))
        return result
