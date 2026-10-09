"""Advanced PostgreSQL-backed health, analytics and search endpoints."""

from datetime import date, timedelta
from flask import Blueprint, jsonify, request
from flask_login import current_user
from sqlalchemy import or_, text

from app import db
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.service import Service
from app.models.slot import Slot
from app.models.notification_log import NotificationLog

advanced_bp = Blueprint("advanced", __name__, url_prefix="/api/advanced")


def _staff_only():
    return current_user.is_authenticated and str(current_user.get_id()).startswith(("teacher:", "admin:"))


@advanced_bp.get("/health")
def health():
    """Database health check suitable for deployment monitoring."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({
            "status": "healthy",
            "database": db.engine.dialect.name,
            "pool": str(db.engine.pool.status()),
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({"status": "unhealthy", "error": str(exc)}), 503


@advanced_bp.get("/search")
def search():
    """Fast teacher/service discovery; PostgreSQL uses trigram indexes."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"success": False, "error": "q must contain at least 2 characters."}), 400

    teachers = Business.query.filter(
        Business.is_active.is_(True),
        or_(Business.name.ilike(f"%{q}%"), Business.department.ilike(f"%{q}%"), Business.subject.ilike(f"%{q}%"))
    ).limit(20).all()

    services = Service.query.filter(
        Service.is_active.is_(True),
        Service.name.ilike(f"%{q}%")
    ).limit(20).all()

    return jsonify({
        "success": True,
        "query": q,
        "teachers": [t.to_dict() for t in teachers],
        "services": [s.to_dict() for s in services],
    })


@advanced_bp.get("/analytics")
def analytics():
    if not _staff_only():
        return jsonify({"success": False, "error": "Staff login required."}), 403

    today = date.today()
    last_30 = today - timedelta(days=30)
    query = Appointment.query

    # Teachers only see appointments belonging to their own services.
    if str(current_user.get_id()).startswith("teacher:"):
        teacher_id = current_user.id
        query = query.join(Slot).join(Service).filter(Service.business_id == teacher_id)

    rows = query.filter(Appointment.booked_at >= last_30).all()
    by_status = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1

    return jsonify({
        "success": True,
        "period": {"from": last_30.isoformat(), "to": today.isoformat()},
        "total_bookings": len(rows),
        "by_status": by_status,
        "completion_rate": round(
            (by_status.get("completed", 0) / len(rows) * 100) if rows else 0, 2
        ),
        "cancellation_rate": round(
            (by_status.get("cancelled", 0) / len(rows) * 100) if rows else 0, 2
        ),
    })


@advanced_bp.get("/notification-logs")
def notification_logs():
    """Recent email delivery audit for teachers/admins."""
    if not _staff_only():
        return jsonify({"success": False, "error": "Staff login required."}), 403

    query = NotificationLog.query.join(Appointment).join(Slot).join(Service)
    if str(current_user.get_id()).startswith("teacher:"):
        query = query.filter(Service.business_id == current_user.id)

    rows = query.order_by(NotificationLog.created_at.desc()).limit(100).all()
    return jsonify({
        "success": True,
        "count": len(rows),
        "logs": [row.to_dict() for row in rows],
    })
