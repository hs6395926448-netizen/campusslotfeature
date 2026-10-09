"""
app/models/service.py - Service Model

A Service is something a business offers — e.g., "Haircut", "X-Ray", "Oil Change".
Each service has a duration and price, and it owns multiple time Slots.
"""

from datetime import datetime
from app import db


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key links this service to its parent business
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    dataset_id = db.Column(db.String(30), unique=True)

    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)

    # Duration in minutes — used to show users how long the appointment is
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)

    # Price in lowest currency unit (e.g., paise / cents) OR as decimal
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

    # Soft-delete: deactivating a service hides it without losing history
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship: one service → many slots
    slots = db.relationship(
        "Slot",
        backref="service",
        cascade="all, delete-orphan",
        lazy=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "business_id": self.business_id,
            "dataset_id": self.dataset_id,
            "name": self.name,
            "description": self.description,
            "duration_minutes": self.duration_minutes,
            "price": float(self.price),
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<Service {self.name}>"
