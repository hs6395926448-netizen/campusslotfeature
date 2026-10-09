from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.services.notification_service import enqueue_registration_notification
from app.models.student import Student
from app.models.business import Business
from app.models.admin import Admin
from app.models.appointment import Appointment
from uuid import uuid4
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import current_app

student_bp = Blueprint('student', __name__)

def registration_id(): return f"ST-{uuid4().hex[:8].upper()}"

def email_taken(email, existing_id=None):
    for model in (Student, Business, Admin):
        q=model.query.filter_by(email=email)
        if model is Student and existing_id: q=q.filter(Student.id != existing_id)
        if q.first(): return True
    return False

@student_bp.route('/student/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        data={k:request.form.get(k,'').strip() for k in ('name','email','phone','roll_number','department','course')}
        semester=request.form.get('semester','').strip(); password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(data['name'])<2 or '@' not in data['email'] or len(data['phone'])<10 or not data['roll_number'] or not data['department'] or len(password)<6:
            flash('Name, valid email, phone, roll number, department and a 6+ character password are required.','danger'); return render_template('student/register.html', **data, semester=semester)
        if password!=confirm: flash('Passwords do not match.','danger'); return render_template('student/register.html', **data, semester=semester)
        email=data['email'].lower()
        existing=Student.query.filter_by(email=email).first()
        if existing:
            if existing.registration_status=='rejected':
                existing.name=data['name']; existing.phone=data['phone']; existing.roll_number=data['roll_number']; existing.department=data['department']; existing.course=data['course']; existing.semester=int(semester) if semester.isdigit() else None; existing.set_password(password); existing.registration_status='pending'; existing.rejection_reason=None; existing.is_active=False; existing.registration_id=registration_id(); db.session.commit(); enqueue_registration_notification(existing, 'submitted'); flash(f'Registration resubmitted. Registration ID: {existing.registration_id}','success'); return redirect(url_for('auth.registration_status', registration_id=existing.registration_id))
            flash('That student email is already registered or awaiting approval.','warning'); return render_template('student/register.html', **data, semester=semester)
        if email_taken(email) or Student.query.filter_by(roll_number=data['roll_number']).first():
            flash('Email or roll number is already registered.','danger'); return render_template('student/register.html', **data, semester=semester)
        student=Student(name=data['name'],email=email,phone=data['phone'],roll_number=data['roll_number'],department=data['department'],course=data['course'],semester=int(semester) if semester.isdigit() else None,password_hash='placeholder',is_active=False,registration_status='pending',registration_id=registration_id())
        student.set_password(password); db.session.add(student); db.session.commit(); enqueue_registration_notification(student, 'submitted'); flash(f'Registration submitted. Registration ID: {student.registration_id}','success'); return redirect(url_for('auth.registration_status', registration_id=student.registration_id))
    return render_template('student/register.html')

@student_bp.route('/student/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('student.dashboard'))
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); s=Student.query.filter_by(email=email).first()
        if not s or not s.check_password(password): flash('Invalid email or password.','danger'); return render_template('student/login.html',email=email)
        if s.registration_status=='pending': flash(f'Your registration is awaiting administrator approval. Registration ID: {s.registration_id}','warning'); return render_template('student/login.html',email=email)
        if s.registration_status=='rejected': flash(f'Registration rejected: {s.rejection_reason or "No reason provided."}','danger'); return render_template('student/login.html',email=email)
        if not s.is_active: flash('Student account is inactive.','danger'); return render_template('student/login.html')
        login_user(s, remember=request.form.get('remember')=='on'); flash(f'Welcome, {s.name}!','success'); return redirect(request.args.get('next') or url_for('student.dashboard'))
    return render_template('student/login.html')

@student_bp.route('/student/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('student.login'))

@student_bp.route('/student/appointments/<int:appointment_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    if not str(current_user.get_id()).startswith('student:'): return redirect(url_for('dashboard.dashboard'))
    appt=Appointment.query.get_or_404(appointment_id)
    if appt.student_id != current_user.id: flash('You are not allowed to modify this appointment.','danger'); return redirect(url_for('student.dashboard'))
    if appt.status in ('completed','cancelled'): flash('This appointment cannot be cancelled.','warning'); return redirect(url_for('student.dashboard'))
    appt.status='cancelled'; appt.slot.is_booked=False; db.session.commit()
    from app.services.notification_service import enqueue_appointment_notification
    enqueue_appointment_notification(appt,'cancelled')
    flash('Appointment cancelled. Your daily request limit remains in effect until the next calendar day.','success')
    return redirect(url_for('student.dashboard'))

@student_bp.route('/student/dashboard')
@login_required
def dashboard():
    if not current_user.get_id().startswith('student:'): return redirect(url_for('dashboard.dashboard'))
    appointments=sorted(current_user.appointments,key=lambda a:a.booked_at,reverse=True)
    upcoming=[a for a in appointments if a.status in ('pending','confirmed') and a.slot.date]
    tz=ZoneInfo(current_app.config.get('APPOINTMENT_TIMEZONE','Asia/Kolkata'))
    now_local=datetime.now(timezone.utc).astimezone(tz)
    today_count=0
    for a in appointments:
        if a.booked_at:
            booked_local=a.booked_at.replace(tzinfo=timezone.utc).astimezone(tz)
            if booked_local.date()==now_local.date(): today_count += 1
    return render_template('student/dashboard.html',student=current_user,appointments=appointments,upcoming=upcoming,today_count=today_count)
