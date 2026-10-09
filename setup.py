"""One-command local setup for CampusSlot.

Run: python setup.py
It creates the complete database and demo accounts without deleting an
existing database. Use --reset if you deliberately want a fresh demo DB.
"""

import argparse
from datetime import date, timedelta
from app import create_app, db
from app.models.business import Business
from app.models.service import Service
from app.models.slot import Slot
from app.models.appointment import Appointment
from app.models.student import Student


def seed_demo(reset=False):
    app = create_app("development")
    with app.app_context():
        if reset:
            db.drop_all()
            db.create_all()

        teacher = Business.query.filter_by(email="teacher@campusslot.com").first()
        if not teacher:
            teacher = Business(
                name="Dr. Amit Sharma",
                email="teacher@campusslot.com",
                phone="+919876543210",
                password_hash="placeholder",
                address="CSE Department, Campus",
                description="CSE faculty teacher available for academic appointments.",
            )
            teacher.set_password("password123")
            teacher.generate_slug()
            db.session.add(teacher)
            db.session.flush()

        student = Student.query.filter_by(email="student@campusslot.com").first()
        if not student:
            student = Student(
                name="Rahul Sharma",
                email="student@campusslot.com",
                phone="+919123456789",
                roll_number="CSE2027-001",
                department="CSE",
                password_hash="placeholder",
            )
            student.set_password("password123")
            db.session.add(student)
            db.session.flush()

        purposes = [
            ("Academic Discussion", "Discuss syllabus, concepts and academic progress.", 20),
            ("Project Guidance", "Project and final-year project guidance.", 30),
            ("Career Guidance", "Placement, internship and career discussion.", 20),
        ]
        services = []
        for name, description, duration in purposes:
            service = Service.query.filter_by(business_id=teacher.id, name=name).first()
            if not service:
                service = Service(
                    business_id=teacher.id,
                    name=name,
                    description=description,
                    duration_minutes=duration,
                    price=0,
                    is_active=True,
                )
                db.session.add(service)
                db.session.flush()
            services.append(service)

        today = date.today()
        times = [
            ("09:00", "09:20"), ("09:30", "09:50"),
            ("10:00", "10:20"), ("10:30", "10:50"),
            ("11:00", "11:20"), ("14:00", "14:20"),
            ("14:30", "14:50"), ("15:00", "15:20"),
        ]
        for service in services:
            for day in (today, today + timedelta(days=1)):
                for start, end in times:
                    exists = Slot.query.filter_by(
                        service_id=service.id, date=day, start_time=start
                    ).first()
                    if not exists:
                        db.session.add(Slot(
                            service_id=service.id,
                            date=day,
                            start_time=start,
                            end_time=end,
                            is_booked=False,
                        ))

        db.session.commit()
        print("\nCampusSlot setup complete.")
        print("Teacher: teacher@campusslot.com / password123")
        print("Student: student@campusslot.com / password123")
        print(f"Teacher booking page: http://127.0.0.1:5000/book/{teacher.slug}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the local demo database")
    args = parser.parse_args()
    seed_demo(args.reset)
