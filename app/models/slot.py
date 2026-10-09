"""
app/models/slot.py - Slot Model

A Slot is a specific time window when a Service can be booked.
Example: "Haircut on 5th April at 10:00 AM"

is_booked prevents double-booking — it's set to True atomically
inside a database transaction when an appointment is created.
"""

from datetime import datetime
from app import db


class Slot(db.Model):
    __tablename__ = "slots"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to parent Service
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    dataset_id = db.Column(db.String(30), unique=True)
    source = db.Column(db.String(30), default="manual")

    # The date of the slot (e.g., 2025-04-05)
    date = db.Column(db.Date, nullable=False)

    # Start and end time as strings — stored as "HH:MM" for simplicity
    # In production you may use Time columns or timezone-aware datetimes
    start_time = db.Column(db.String(5), nullable=False)   # "10:00"
    end_time = db.Column(db.String(5), nullable=False)     # "10:30"

    # CRITICAL: This flag prevents double-booking
    # Changed to True only inside a DB transaction in booking_service.py
    is_booked = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship: one slot → at most one appointment
    appointment = db.relationship("Appointment", backref="slot", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "dataset_id": self.dataset_id,
            "source": self.source,
            "date": self.date.isoformat(),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_booked": self.is_booked,
        }

    def __repr__(self):
        return f"<Slot {self.date} {self.start_time}-{self.end_time}>"
