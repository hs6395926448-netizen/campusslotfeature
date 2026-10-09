from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from app.models.business import Business
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.slot import Slot
from datetime import date, timedelta

dashboard_bp=Blueprint("dashboard",__name__)

@dashboard_bp.route("/")
def index():
    return render_template("home.html")

@dashboard_bp.route("/faculty")
def faculty():
    q=request.args.get('q','').strip(); department=request.args.get('department','').strip()
    query=Business.query.filter_by(is_active=True,registration_status='approved')
    if q:
        like=f'%{q}%'
        query=query.filter((Business.name.ilike(like))|(Business.subject.ilike(like))|(Business.department.ilike(like)))
    if department: query=query.filter_by(department=department)
    teachers=query.order_by(Business.name).all()
    departments=[x[0] for x in Business.query.with_entities(Business.department).filter(Business.is_active==True,Business.registration_status=='approved').filter(Business.department.isnot(None)).distinct().order_by(Business.department).all()]
    availability={}
    for t in teachers:
        total=Slot.query.join(Service).filter(Service.business_id==t.id,Slot.is_booked==False,Slot.date>=date.today(),Slot.date<=date.today()+timedelta(days=7)).count()
        availability[t.id]=total
    return render_template('faculty.html',teachers=teachers,departments=departments,q=q,department=department,availability=availability)

@dashboard_bp.route("/book/<string:slug>")
def booking_page(slug):
    business=Business.query.filter_by(slug=slug,is_active=True,registration_status='approved').first_or_404()
    services=Service.query.filter_by(business_id=business.id,is_active=True).order_by(Service.name).all()
    return render_template("booking.html",business=business,services=services,today=date.today().isoformat())

@dashboard_bp.route("/track")
@dashboard_bp.route("/track/<string:tracking_id>")
def tracking_page(tracking_id=None): return render_template("tracking.html",tracking_id=tracking_id)

@dashboard_bp.route('/calendar')
@login_required
def calendar():
    if str(current_user.get_id()).startswith('student:'):
        appointments=Appointment.query.filter_by(student_id=current_user.id).order_by(Appointment.booked_at.desc()).all()
    elif str(current_user.get_id()).startswith('teacher:'):
        appointments=(Appointment.query.join(Slot).join(Service).filter(Service.business_id==current_user.id).order_by(Slot.date,Slot.start_time).all())
    else: appointments=[]
    return render_template('calendar.html',appointments=appointments,today=date.today())

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    if not str(current_user.get_id()).startswith("teacher:"): return redirect(url_for("student.dashboard"))
    appointments=(Appointment.query.join(Slot,Appointment.slot_id==Slot.id).join(Service,Slot.service_id==Service.id).filter(Service.business_id==current_user.id).order_by(Slot.date,Slot.start_time).all())
    services=Service.query.filter_by(business_id=current_user.id,is_active=True).order_by(Service.name).all()
    today_count=sum(1 for a in appointments if a.slot.date==date.today())
    pending=sum(1 for a in appointments if a.status=='pending')
    upcoming=sum(1 for a in appointments if a.status in ('pending','confirmed') and a.slot.date>=date.today())
    return render_template("dashboard.html",business=current_user,appointments=appointments,services=services,today=date.today().isoformat(),today_count=today_count,pending_count=pending,upcoming_count=upcoming)
