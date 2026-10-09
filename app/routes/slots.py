from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from app import db
from app.models.slot import Slot
from app.models.service import Service
from app.utils.validators import validate_slot_data

slots_bp = Blueprint("slots", __name__)

def teacher_only():
    return current_user.is_authenticated and str(current_user.get_id()).startswith("teacher:")

@slots_bp.route("/add-slot", methods=["POST"])
@login_required
def add_slot():
    if not teacher_only():
        return jsonify({"success": False, "error": "Teacher login required."}), 403
    data = request.get_json(silent=True) or {}
    valid, error = validate_slot_data(data)
    if not valid:
        return jsonify({"success": False, "error": error}), 400
    service = Service.query.get(data["service_id"])
    if not service or not service.is_active:
        return jsonify({"success": False, "error": "Appointment purpose not found."}), 404
    if service.business_id != current_user.id:
        return jsonify({"success": False, "error": "Not authorized."}), 403
    d = date.fromisoformat(data["date"])

    # The appointment purpose controls the slot length. The teacher only
    # chooses a start time; the server calculates the end time from the
    # purpose duration so a 10-minute purpose can never become a 30-minute
    # or unlimited slot by accident.
    try:
        start_dt = datetime.strptime(data["start_time"], "%H:%M")
    except ValueError:
        return jsonify({"success": False, "error": "Invalid start time."}), 400

    end_dt = start_dt + timedelta(minutes=int(service.duration_minutes))
    if end_dt.date() != start_dt.date():
        return jsonify({"success": False, "error": "The selected start time plus the appointment duration must finish before midnight."}), 400

    calculated_end_time = end_dt.strftime("%H:%M")

    # Do not allow overlapping slots for the same purpose.
    existing_slots = Slot.query.filter_by(service_id=service.id, date=d).all()
    for existing in existing_slots:
        existing_start = datetime.strptime(existing.start_time, "%H:%M")
        existing_end = datetime.strptime(existing.end_time, "%H:%M")
        if start_dt < existing_end and end_dt > existing_start:
            return jsonify({"success": False, "error": "This time overlaps an existing slot for this purpose."}), 409

    slot = Slot(
        service_id=service.id,
        date=d,
        start_time=data["start_time"],
        end_time=calculated_end_time,
    )
    try:
        db.session.add(slot); db.session.commit()
        return jsonify({"success": True, "slot": slot.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@slots_bp.route("/slots/<int:service_id>")
def get_slots(service_id):
    service=Service.query.get(service_id)
    if not service or not service.is_active:
        return jsonify({"success": False, "error": "Appointment purpose not found."}), 404
    query=Slot.query.filter_by(service_id=service_id,is_booked=False).filter(Slot.date >= date.today())
    date_filter=request.args.get("date")
    if date_filter:
        try: query=query.filter(Slot.date==date.fromisoformat(date_filter))
        except ValueError: return jsonify({"success":False,"error":"Invalid date format."}),400
    slots=query.order_by(Slot.date,Slot.start_time).all()
    return jsonify({"success":True,"service":service.to_dict(),"slots":[s.to_dict() for s in slots]})

@slots_bp.route("/slots/<int:slot_id>", methods=["DELETE"])
@login_required
def delete_slot(slot_id):
    if not teacher_only(): return jsonify({"success":False,"error":"Teacher login required."}),403
    slot=Slot.query.get(slot_id)
    if not slot: return jsonify({"success":False,"error":"Slot not found."}),404
    if slot.service.business_id != current_user.id: return jsonify({"success":False,"error":"Not authorized."}),403
    if slot.is_booked: return jsonify({"success":False,"error":"Cannot delete a booked slot."}),409
    db.session.delete(slot); db.session.commit()
    return jsonify({"success":True,"message":"Slot deleted."})
