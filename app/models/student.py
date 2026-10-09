from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class Student(UserMixin, db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(80))
    semester = db.Column(db.Integer)
    dataset_id = db.Column(db.String(30), unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    registration_status = db.Column(db.String(20), default='approved', nullable=False)
    rejection_reason = db.Column(db.Text)
    registration_id = db.Column(db.String(30), unique=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='student', lazy=True)

    def get_id(self):
        return f'student:{self.id}'
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
