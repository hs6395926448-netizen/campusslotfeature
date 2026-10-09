from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.services.notification_service import enqueue_registration_notification
from app.models.business import Business
from app.models.student import Student
from app.models.admin import Admin
from uuid import uuid4

auth_bp = Blueprint("auth", __name__)

def _registration_id(prefix):
    return f"{prefix}-{uuid4().hex[:8].upper()}"

def _email_taken(email, except_model=None, except_id=None):
    for model in (Student, Business, Admin):
        q = model.query.filter_by(email=email)
        if except_model is model and except_id is not None:
            q = q.filter(model.id != except_id)
        if q.first():
            return True
    return False

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in (
            "name", "email", "phone", "department", "subject", "designation", "office", "address", "description"
        )}
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(data["name"]) < 2 or "@" not in data["email"] or len(data["phone"]) < 10 or len(data["department"]) < 2 or len(password) < 6:
            flash("Name, valid email, phone, department and a 6+ character password are required.", "danger")
            return render_template("auth/register.html", **data)
        if password != confirm:
            flash("Passwords do not match.", "danger"); return render_template("auth/register.html", **data)
        existing = Business.query.filter_by(email=data["email"].lower()).first()
        if existing:
            if existing.registration_status == "rejected":
                existing.name=data["name"]; existing.phone=data["phone"]; existing.department=data["department"]; existing.subject=data["subject"]; existing.designation=data["designation"]; existing.office=data["office"]; existing.address=data["address"]; existing.description=data["description"]; existing.set_password(password); existing.registration_status="pending"; existing.rejection_reason=None; existing.is_active=False; existing.registration_id=_registration_id("TR")
                db.session.commit(); enqueue_registration_notification(existing, "submitted"); flash(f"Teacher registration submitted. Registration ID: {existing.registration_id}", "success"); return redirect(url_for("auth.registration_status", registration_id=existing.registration_id))
            flash("That teacher email is already registered or awaiting approval.", "warning"); return render_template("auth/register.html", **data)
        if _email_taken(data["email"].lower()):
            flash("That email address is already registered.", "danger"); return render_template("auth/register.html", **data)
        teacher=Business(name=data["name"], email=data["email"].lower(), phone=data["phone"], department=data["department"], subject=data["subject"], designation=data["designation"], office=data["office"], address=data["address"], description=data["description"], password_hash="placeholder", is_active=False, registration_status="pending", registration_id=_registration_id("TR"))
        teacher.set_password(password); teacher.generate_slug(); db.session.add(teacher); db.session.commit(); enqueue_registration_notification(teacher, "submitted")
        flash(f"Teacher registration submitted. Registration ID: {teacher.registration_id}", "success")
        return redirect(url_for("auth.registration_status", registration_id=teacher.registration_id))
    return render_template("auth/register.html")

@auth_bp.route("/registration-status/<registration_id>")
def registration_status(registration_id):
    record = Business.query.filter_by(registration_id=registration_id.upper()).first() or Student.query.filter_by(registration_id=registration_id.upper()).first()
    if not record: return render_template("auth/registration_status.html", record=None, registration_id=registration_id, role=None)
    role = "teacher" if isinstance(record, Business) else "student"
    return render_template("auth/registration_status.html", record=record, registration_id=registration_id, role=role)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard") if str(current_user.get_id()).startswith("teacher:") else url_for("student.dashboard"))
    if request.method == "POST":
        email=request.form.get("email", "").strip().lower(); password=request.form.get("password", "")
        business=Business.query.filter_by(email=email).first()
        if not business or not business.check_password(password):
            flash("Invalid email or password. Please try again.", "danger"); return render_template("auth/login.html", email=email)
        if business.registration_status == "pending":
            flash(f"Your teacher registration is awaiting administrator approval. Registration ID: {business.registration_id}", "warning"); return render_template("auth/login.html", email=email)
        if business.registration_status == "rejected":
            flash(f"Registration rejected: {business.rejection_reason or 'No reason provided.'}", "danger"); return render_template("auth/login.html", email=email)
        if not business.is_active:
            flash("This account has been deactivated. Contact the administrator.", "danger"); return render_template("auth/login.html")
        login_user(business, remember=request.form.get("remember")=="on")
        flash(f"Welcome back, {business.name}!", "success")
        return redirect(request.args.get("next") or url_for("dashboard.dashboard"))
    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user(); flash("You have been logged out.", "info"); return redirect(url_for("auth.login"))
