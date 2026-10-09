"""Durable notification delivery log for CampusSlot.

Every email attempt is recorded independently from the booking
transaction. This makes notification delivery auditable and gives the project
a clear production-grade integration boundary.
"""
from datetime import datetime
from app import db


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"
    __table_args__ = (
        db.Index("ix_notification_logs_appointment_channel", "appointment_id", "channel"),
        db.Index("ix_notification_logs_status_created", "status", "created_at"),
        db.Index("ix_notification_logs_event_created", "event", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    channel = db.Column(db.String(20), nullable=False)       # email
    recipient = db.Column(db.String(160), nullable=False)
    event = db.Column(db.String(30), nullable=False)         # pending / confirmed / ...
    status = db.Column(db.String(20), nullable=False)        # sent / failed / skipped
    provider_message_id = db.Column(db.String(160))
    error_message = db.Column(db.Text)
    attempt_count = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    appointment = db.relationship("Appointment", backref=db.backref(
        "notification_logs", lazy=True, cascade="all, delete-orphan"
    ))

    def to_dict(self):
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "event": self.event,
            "status": self.status,
            "provider_message_id": self.provider_message_id,
            "error_message": self.error_message,
            "attempt_count": self.attempt_count,
            "created_at": self.created_at.isoformat(),
        }
