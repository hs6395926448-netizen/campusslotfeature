"""Centralized audit logging helpers."""

from flask import request
from flask_login import current_user
from app import db
from app.models.audit_log import AuditLog


def record_audit(action, entity_type=None, entity_id=None, details=None):
    actor_type = "anonymous"
    actor_id = None
    if current_user.is_authenticated:
        raw = str(current_user.get_id())
        if ":" in raw:
            actor_type, raw_id = raw.split(":", 1)
            try:
                actor_id = int(raw_id)
            except ValueError:
                actor_id = None

    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    db.session.add(entry)
    return entry
