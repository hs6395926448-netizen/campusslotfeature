"""CampusSlot administrator authentication and management panel."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.admin import Admin
from app.models.business import Business
from app.models.student import Student
from app.models.service import Service
from app.models.slot import Slot
from app.models.appointment import Appointment
from app.services.notification_service import notify_appointment, enqueue_registration_notification
from werkzeug.utils import secure_filename
from uuid import uuid4
from pathlib import Path

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def _save_teacher_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    original = secure_filename(file_storage.filename)
    if "." not in original:
        raise ValueError("Teacher photo must be JPG, JPEG, PNG or WEBP.")
    ext = original.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise ValueError("Teacher photo must be JPG, JPEG, PNG or WEBP.")
    upload_dir = Path(current_app.static_folder) / "uploads" / "teachers"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    file_storage.save(upload_dir / filename)
    return f"uploads/teachers/{filename}"

def admin_required(view):
    from functools import wraps
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not str(current_user.get_id()).startswith('admin:'):
            flash('Administrator access is required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return view(*args, **kwargs)
    return wrapped

@admin_bp.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        if str(current_user.get_id()).startswith('admin:'):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email=request.form.get('email','').strip().lower()
        password=request.form.get('password','')
        admin=Admin.query.filter_by(email=email).first()
        if not admin or not admin.check_password(password):
            flash('Invalid administrator email or password.', 'danger')
            return render_template('admin/login.html', email=email)
        if not admin.is_active:
            flash('This administrator account is inactive.', 'danger')
            return render_template('admin/login.html', email=email)
        login_user(admin, remember=request.form.get('remember')=='on')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@login_required
def logout():
    if not str(current_user.get_id()).startswith('admin:'):
        return redirect(url_for('dashboard.index'))
    logout_user()
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    teachers=Business.query.filter_by(is_active=True).order_by(Business.created_at.desc()).all()
    students=Student.query.filter_by(is_active=True).order_by(Student.created_at.desc()).all()
    admins=Admin.query.order_by(Admin.created_at.desc()).all()
    appointments=Appointment.query.order_by(Appointment.booked_at.desc()).limit(20).all()
    pending_teachers=Business.query.filter_by(registration_status='pending').order_by(Business.created_at.asc()).all()
    pending_students=Student.query.filter_by(registration_status='pending').order_by(Student.created_at.asc()).all()
    today = __import__('datetime').date.today()
    today_appointments=sum(1 for a in appointments if a.slot and a.slot.date==today)
    return render_template('admin/dashboard.html', teachers=teachers, students=students, admins=admins, appointments=appointments, pending_teachers=pending_teachers, pending_students=pending_students, today_appointments=today_appointments)



@admin_bp.route('/notifications/status')
@admin_required
def notification_status():
    """Show whether the required notification credentials are loaded."""
    return {
        "email": {
            "configured": bool(
                (current_app.config.get("APPS_SCRIPT_URL") and current_app.config.get("APPS_SCRIPT_SECRET"))
                or current_app.config.get("RESEND_API_KEY")
                or (current_app.config.get("SMTP_HOST") and current_app.config.get("SMTP_USERNAME") and current_app.config.get("SMTP_PASSWORD") and current_app.config.get("MAIL_FROM"))
            ),
            "provider": (
                "Google Apps Script + Gmail"
                if current_app.config.get("APPS_SCRIPT_URL") and current_app.config.get("APPS_SCRIPT_SECRET")
                else "Resend API" if current_app.config.get("RESEND_API_KEY") else "SMTP"
            ),
            "smtp_host": current_app.config.get("SMTP_HOST", ""),
            "mail_from": (
                "Gmail account configured in Apps Script"
                if current_app.config.get("APPS_SCRIPT_URL") and current_app.config.get("APPS_SCRIPT_SECRET")
                else current_app.config.get("RESEND_FROM_EMAIL") if current_app.config.get("RESEND_API_KEY") else current_app.config.get("MAIL_FROM", "")
            ),
        },
        "base_url": current_app.config.get("BASE_URL", ""),
    }


@admin_bp.route('/notifications/test/<int:appointment_id>', methods=['POST'])
@admin_required
def test_notification(appointment_id):
    """Send a real confirmation notification for an existing appointment."""
    appointment = Appointment.query.get_or_404(appointment_id)
    result = notify_appointment(appointment, appointment.status or "confirmed")
    email_sent = result["email"]["sent"]
    errors = result["email"]["errors"]
    if email_sent:
        flash(f"Notification test finished: {email_sent} email(s) sent.", "success")
    else:
        flash("Notification test failed. " + " | ".join(errors[:4]), "danger")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/teachers/create', methods=['POST'])
@admin_required
def create_teacher():
    name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower()
    phone=request.form.get('phone','').strip(); password=request.form.get('password','')
    address=request.form.get('address','').strip(); description=request.form.get('description','').strip()
    if not name or '@' not in email or len(phone)<10 or len(password)<6:
        flash('Teacher name, valid email, phone and password (6+ characters) are required.', 'danger')
        return redirect(url_for('admin.dashboard'))
    if Business.query.filter_by(email=email).first() or Student.query.filter_by(email=email).first() or Admin.query.filter_by(email=email).first():
        flash('That email address is already registered.', 'danger'); return redirect(url_for('admin.dashboard'))
    try:
        photo_path = _save_teacher_photo(request.files.get('teacher_photo'))
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('admin.dashboard'))
    teacher=Business(name=name,email=email,phone=phone,address=address,description=description,teacher_photo=photo_path,password_hash='placeholder')
    teacher.set_password(password); teacher.generate_slug(); db.session.add(teacher); db.session.commit()
    flash(f'Teacher account created for {name}.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/students/create', methods=['POST'])
@admin_required
def create_student():
    name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower()
    phone=request.form.get('phone','').strip(); roll=request.form.get('roll_number','').strip()
    dept=request.form.get('department','').strip(); password=request.form.get('password','')
    if len(name)<2 or '@' not in email or len(phone)<10 or not roll or not dept or len(password)<6:
        flash('All student fields are required and password must be 6+ characters.', 'danger'); return redirect(url_for('admin.dashboard'))
    if Student.query.filter((Student.email==email)|(Student.roll_number==roll)).first() or Business.query.filter_by(email=email).first() or Admin.query.filter_by(email=email).first():
        flash('Email or roll number is already registered.', 'danger'); return redirect(url_for('admin.dashboard'))
    student=Student(name=name,email=email,phone=phone,roll_number=roll,department=dept,password_hash='placeholder')
    student.set_password(password); db.session.add(student); db.session.commit()
    flash(f'Student account created for {name}.', 'success'); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/administrators/create', methods=['POST'])
@admin_required
def create_admin():
    name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
    if len(name)<2 or '@' not in email or len(password)<6:
        flash('Administrator name, valid email and password (6+ characters) are required.', 'danger'); return redirect(url_for('admin.dashboard'))
    if Admin.query.filter_by(email=email).first() or Business.query.filter_by(email=email).first() or Student.query.filter_by(email=email).first():
        flash('That email address is already registered.', 'danger'); return redirect(url_for('admin.dashboard'))
    admin=Admin(name=name,email=email,password_hash='placeholder'); admin.set_password(password); db.session.add(admin); db.session.commit()
    flash(f'Administrator account created for {name}.', 'success'); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/teacher/<int:teacher_id>/toggle', methods=['POST'])
@admin_required
def toggle_teacher(teacher_id):
    teacher=Business.query.get_or_404(teacher_id); teacher.is_active=not teacher.is_active; db.session.commit()
    flash(f'Teacher {"activated" if teacher.is_active else "deactivated"}.', 'success'); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/student/<int:student_id>/toggle', methods=['POST'])
@admin_required
def toggle_student(student_id):
    student=Student.query.get_or_404(student_id); student.is_active=not student.is_active; db.session.commit()
    flash(f'Student {"activated" if student.is_active else "deactivated"}.', 'success'); return redirect(url_for('admin.dashboard'))

@admin_bp.route('/teacher/<int:teacher_id>/remove', methods=['POST'])
@admin_required
def remove_teacher(teacher_id):
    """Safely retire a teacher login while preserving appointment history."""
    teacher = Business.query.get_or_404(teacher_id)
    if request.form.get('confirm') != 'REMOVE':
        flash('Teacher removal was not confirmed.', 'warning')
        return redirect(url_for('admin.dashboard'))
    teacher.is_active = False
    teacher.registration_status = 'removed'
    teacher.rejection_reason = 'Account removed by administrator'
    # Release the email for a future test/new account without deleting history.
    teacher.email = f'removed-teacher-{teacher.id}@accounts.invalid'
    db.session.commit()
    flash(f'Teacher account removed. Past appointments and records were preserved; the original email can now be registered again.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/student/<int:student_id>/remove', methods=['POST'])
@admin_required
def remove_student(student_id):
    """Safely retire a student login while preserving appointment history."""
    student = Student.query.get_or_404(student_id)
    if request.form.get('confirm') != 'REMOVE':
        flash('Student removal was not confirmed.', 'warning')
        return redirect(url_for('admin.dashboard'))
    student.is_active = False
    student.registration_status = 'removed'
    student.rejection_reason = 'Account removed by administrator'
    # Free unique email and roll number for another registration.
    student.email = f'removed-student-{student.id}@accounts.invalid'
    student.roll_number = f'removed-{student.id}'
    db.session.commit()
    flash('Student account removed. Past appointment history was preserved; the original email and roll number can now be reused.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/registration/<string:role>/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_registration(role, user_id):
    model = Business if role == 'teacher' else Student if role == 'student' else None
    if model is None: return redirect(url_for('admin.dashboard'))
    record=model.query.get_or_404(user_id)
    record.registration_status='approved'; record.rejection_reason=None; record.is_active=True
    db.session.commit(); enqueue_registration_notification(record, 'approved')
    flash(f'{"Teacher" if role=="teacher" else "Student"} registration approved for {record.name}.','success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/registration/<string:role>/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_registration(role, user_id):
    model = Business if role == 'teacher' else Student if role == 'student' else None
    if model is None: return redirect(url_for('admin.dashboard'))
    record=model.query.get_or_404(user_id); reason=request.form.get('reason','').strip()
    if not reason: flash('A rejection reason is required.','warning'); return redirect(url_for('admin.dashboard'))
    record.registration_status='rejected'; record.rejection_reason=reason; record.is_active=False
    db.session.commit(); enqueue_registration_notification(record, 'rejected')
    flash(f'Registration rejected for {record.name}.','success')
    return redirect(url_for('admin.dashboard'))
