"""Audit logging for security and traceability."""

from datetime import datetime
from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_type = db.Column(db.String(20), nullable=False, index=True)
    actor_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details or {},
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(),
        }
