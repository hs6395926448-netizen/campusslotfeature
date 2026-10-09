"""
app/models/appointment.py - Appointment Model

An Appointment is the core booking record.
It stores who booked (name + phone — no login needed), which slot they took,
and a unique tracking_id they can use to check status via email or the web.

Status flow: pending → confirmed → completed / cancelled
"""

import uuid
from datetime import datetime
from app import db


def generate_tracking_id():
    """
    Creates a short, unique tracking ID.
    Example: "SL-A3F7C2"
    The 'SL-' prefix makes it recognisable in email notifications.
    """
    return "SL-" + str(uuid.uuid4()).upper()[:6]


class Appointment(db.Model):
    __tablename__ = "appointments"
    __table_args__ = (
        db.Index("ix_appointments_student_status", "student_id", "status"),
        db.Index("ix_appointments_booked_at_status", "booked_at", "status"),
        db.Index("ix_appointments_slot_status", "slot_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # The slot that was booked
    slot_id = db.Column(db.Integer, db.ForeignKey("slots.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    # Calendar day (in APPOINTMENT_TIMEZONE) used to enforce one request per student/day.
    # Kept nullable for legacy/admin-created appointments without a student account.
    request_date = db.Column(db.String(10), nullable=True)
    dataset_id = db.Column(db.String(30), unique=True)

    # Customer info — no login needed, just name + phone
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_notes = db.Column(db.Text)  # Optional: "I need a short haircut"

    # Extensible PostgreSQL JSON/JSONB payload for future integrations,
    # preferences, reminder state, source channel, etc.
    extra_data = db.Column("metadata", db.JSON, nullable=False, default=dict)

    # Unique ID sent to the student by email for tracking
    tracking_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False,
        default=generate_tracking_id
    )

    # Booking status lifecycle
    # pending → confirmed (business confirms) → completed / cancelled
    STATUS_CHOICES = ["pending", "confirmed", "completed", "cancelled"]
    status = db.Column(db.String(20), default="pending", nullable=False)

    # When the booking was made
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)

    # When the business last updated the status
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optimistic-lock version. Useful when two dashboard tabs edit the same
    # appointment at nearly the same time.
    version = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        """Full serialization including slot details for tracking page."""
        slot = self.slot
        service = slot.service if slot else None
        business = service.business if service else None

        return {
            "id": self.id,
            "tracking_id": self.tracking_id,
            "student_id": self.student_id,
            "dataset_id": self.dataset_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_notes": self.customer_notes,
            "metadata": self.extra_data or {},
            "version": self.version,
            "status": self.status,
            "booked_at": self.booked_at.isoformat(),
            "slot": slot.to_dict() if slot else None,
            "service": service.to_dict() if service else None,
            "business": business.to_dict() if business else None,
        }

    def __repr__(self):
        return f"<Appointment {self.tracking_id} - {self.customer_name}>"
