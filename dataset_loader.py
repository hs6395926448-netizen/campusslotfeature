from pathlib import Path
import csv
from datetime import date, datetime, timedelta
from app import db
from app.models.business import Business
from app.models.student import Student
from app.models.service import Service
from app.models.slot import Slot
from app.models.appointment import Appointment

ROOT = Path(__file__).resolve().parent / "dataset"
DEFAULT_PASSWORD = "CampusSlot@123"

def _read(name):
    with open(ROOT / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def _next_weekday(day_name, start=date(2026,10,1)):
    names=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    target=names.index(day_name)
    return start + timedelta(days=(target-start.weekday()) % 7)

def _make_phone(prefix, number):
    return f"+9198{prefix:02d}{number:05d}"[-13:]

def _photo(teacher_id, name):
    static = Path(__file__).resolve().parent / "app" / "static" / "uploads" / "teachers"
    static.mkdir(parents=True, exist_ok=True)
    fn=f"dataset_{teacher_id.lower()}.svg"
    path=static/fn
    initials="".join(x[0] for x in name.split()[:2]).upper()
    svg=f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#e8eef8"/><circle cx="200" cy="145" r="75" fill="#7b8aa0"/><path d="M80 360c15-105 75-145 120-145s105 40 120 145" fill="#7b8aa0"/><text x="200" y="385" text-anchor="middle" font-family="Arial" font-size="28" fill="#24324a">{initials}</text></svg>"""
    if not path.exists(): path.write_text(svg, encoding="utf-8")
    return f"uploads/teachers/{fn}"

def load_dataset(reset=False):
    students = _read("students.csv"); teachers = _read("teachers.csv")
    availability = _read("availability.csv"); appointments = _read("appointments.csv")
    if reset:
        Appointment.query.delete(); Slot.query.delete(); Service.query.delete()
        Student.query.delete(); Business.query.delete(); db.session.commit()
    if not Business.query.first() and not Student.query.first():
        for r in teachers:
            t=Business(name=r["name"], email=r["email"].lower(),
                phone=_make_phone(1,int(r["teacher_id"][1:])), password_hash="placeholder",
                slug=r["teacher_id"].lower(), address=f'{r["department"]} · {r["office"]}',
                description=r["bio"], teacher_photo=_photo(r["teacher_id"],r["name"]),
                dataset_id=r["teacher_id"], department=r["department"], subject=r["subject"],
                office=r["office"], is_active=True)
            t.set_password(DEFAULT_PASSWORD); db.session.add(t)
        for r in students:
            s=Student(name=r["name"], email=r["email"].lower(),
                phone=_make_phone(2,int(r["student_id"][1:])), roll_number=r["roll_number"],
                department=r["department"], course=r["course"], semester=int(r["semester"]),
                dataset_id=r["student_id"], password_hash="placeholder", is_active=True)
            s.set_password(DEFAULT_PASSWORD); db.session.add(s)
        db.session.flush()
        service_map={}
        for t in Business.query.all():
            svc=Service(business_id=t.id,name=f'{t.subject} Consultation',
                description=f'Academic appointment with {t.name}. {t.description or ""}',
                duration_minutes=30,price=0,is_active=True,dataset_id=f'SVC-{t.dataset_id}')
            db.session.add(svc); db.session.flush(); service_map[t.dataset_id]=svc
        for r in availability:
            svc=service_map[r["teacher_id"]]; d=_next_weekday(r["day"])
            db.session.add(Slot(service_id=svc.id,date=d,start_time=r["start_time"],
                end_time=r["end_time"],is_booked=False,dataset_id=r["slot_id"],
                source="dataset_availability"))
        db.session.flush()
        student_map={s.dataset_id:s for s in Student.query.all()}
        for r in appointments:
            svc=service_map[r["teacher_id"]]; d=date.fromisoformat(r["date"])
            slot=Slot.query.filter_by(service_id=svc.id,date=d,start_time=r["start_time"],
                end_time=r["end_time"]).first()
            if not slot:
                slot=Slot(service_id=svc.id,date=d,start_time=r["start_time"],
                    end_time=r["end_time"],is_booked=True,
                    dataset_id=f'AP-SLOT-{r["appointment_id"]}',source="dataset_appointment")
                db.session.add(slot); db.session.flush()
            else: slot.is_booked=True
            st=student_map[r["student_id"]]
            ap=Appointment(slot_id=slot.id,student_id=st.id,customer_name=st.name,
                customer_phone=st.phone,customer_notes=r["reason"],tracking_id=r["appointment_id"],
                dataset_id=r["appointment_id"],
                status={"APPROVED":"confirmed","PENDING":"pending","COMPLETED":"completed",
                        "CANCELLED":"cancelled"}[r["status"]],
                booked_at=datetime.combine(d,datetime.min.time()),
                updated_at=datetime.combine(d,datetime.min.time()))
            db.session.add(ap)
        db.session.commit()
    return {"teachers":Business.query.count(),"students":Student.query.count(),
            "availability":Slot.query.filter_by(source="dataset_availability").count(),
            "appointments":Appointment.query.count()}

if __name__ == "__main__":
    from app import create_app
    app=create_app("development")
    with app.app_context(): print(load_dataset(reset=True))
