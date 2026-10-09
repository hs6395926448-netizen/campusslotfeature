from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.service import Service
from app.models.business import Business
from app.utils.validators import validate_service_data, sanitize_string

services_bp = Blueprint("services", __name__)

def teacher_only():
    return current_user.is_authenticated and str(current_user.get_id()).startswith("teacher:")

@services_bp.route("/add-service", methods=["POST"])
@login_required
def add_service():
    if not teacher_only():
        return jsonify({"success": False, "error": "Teacher login required."}), 403
    data = request.get_json(silent=True) or {}
    valid, error = validate_service_data(data)
    if not valid:
        return jsonify({"success": False, "error": error}), 400
    service = Service(
        business_id=current_user.id,
        name=data["name"].strip(),
        description=sanitize_string(data.get("description", "")),
        duration_minutes=int(data["duration_minutes"]),
        price=0,
        is_active=True,
    )
    try:
        db.session.add(service); db.session.commit()
        return jsonify({"success": True, "service": service.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500

@services_bp.route("/services/<string:slug>")
def get_services(slug):
    business = Business.query.filter_by(slug=slug, is_active=True).first()
    if not business:
        return jsonify({"success": False, "error": "Teacher not found."}), 404
    services = Service.query.filter_by(business_id=business.id, is_active=True).order_by(Service.name).all()
    return jsonify({"success": True, "business": business.to_dict(), "services": [s.to_dict() for s in services]})

@services_bp.route("/services/<int:service_id>", methods=["DELETE"])
@login_required
def delete_service(service_id):
    if not teacher_only():
        return jsonify({"success": False, "error": "Teacher login required."}), 403
    service = Service.query.get(service_id)
    if not service:
        return jsonify({"success": False, "error": "Appointment purpose not found."}), 404
    if service.business_id != current_user.id:
        return jsonify({"success": False, "error": "Not authorized."}), 403
    service.is_active = False
    db.session.commit()
    return jsonify({"success": True, "message": "Appointment purpose deactivated."})
