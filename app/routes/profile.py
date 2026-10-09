from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from app import db
from app.models.business import Business
from app.models.student import Student
from app.models.appointment import Appointment
from app.models.slot import Slot
from app.models.service import Service
from werkzeug.utils import secure_filename
from pathlib import Path
from uuid import uuid4

profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/teacher/<string:slug>/profile")
def teacher_profile(slug):
    teacher=Business.query.filter_by(slug=slug,is_active=True,registration_status='approved').first_or_404()
    slots=Slot.query.join(Service).filter(Service.business_id==teacher.id,Slot.is_booked==False,Slot.date>=__import__('datetime').date.today()).order_by(Slot.date,Slot.start_time).limit(20).all()
    return render_template("teacher_profile.html",teacher=teacher,available_slots=slots)

@profile_bp.route("/profile", methods=["GET","POST"])
@login_required
def my_profile():
    user_id=str(current_user.get_id())
    if user_id.startswith("student:"):
        appointments=Appointment.query.filter_by(student_id=current_user.id).order_by(Appointment.booked_at.desc()).all()
        return render_template("student_profile.html",student=current_user,appointments=appointments)
    if user_id.startswith("teacher:"):
        if request.method=='POST':
            current_user.name=request.form.get('name','').strip() or current_user.name
            current_user.phone=request.form.get('phone','').strip()
            current_user.designation=request.form.get('designation','').strip()
            current_user.department=request.form.get('department','').strip()
            current_user.subject=request.form.get('subject','').strip()
            current_user.office=request.form.get('office','').strip()
            current_user.description=request.form.get('description','').strip()
            photo=request.files.get('teacher_photo')
            if photo and photo.filename:
                ext=secure_filename(photo.filename).rsplit('.',1)[-1].lower() if '.' in secure_filename(photo.filename) else ''
                if ext not in {'jpg','jpeg','png','webp'}:
                    flash('Photo must be JPG, JPEG, PNG or WEBP.','danger'); return redirect(url_for('profile.my_profile'))
                upload=Path(current_app.static_folder)/'uploads'/'teachers'; upload.mkdir(parents=True,exist_ok=True)
                filename=f'{uuid4().hex}.{ext}'; photo.save(upload/filename); current_user.teacher_photo=f'uploads/teachers/{filename}'
            db.session.commit(); flash('Teacher profile updated successfully.','success')
        slots=Slot.query.join(Service).filter(Service.business_id==current_user.id,Slot.is_booked==False,Slot.date>=__import__('datetime').date.today()).order_by(Slot.date,Slot.start_time).limit(20).all()
        return render_template("teacher_profile.html",teacher=current_user,own_profile=True,available_slots=slots)
    return redirect(url_for("dashboard.index"))
