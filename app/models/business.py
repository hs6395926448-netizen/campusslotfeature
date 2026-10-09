"""
app/models/business.py - Business Model

A Business is the top-level entity — a salon, clinic, repair shop, etc.
Now includes:
  - Flask-Login mixin (is_authenticated, is_active, get_id)
  - password hashing via werkzeug
  - slug field for clean booking URLs (/book/style-hub)
"""

import re
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


def slugify(text):
    """Convert 'Style Hub Salon' → 'style-hub-salon' for clean URLs."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


class Business(UserMixin, db.Model):
    """
    UserMixin gives us: is_authenticated, is_active, is_anonymous, get_id
    Flask-Login needs these to manage sessions.
    """
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # Hashed password — never store plain text passwords
    password_hash = db.Column(db.String(256), nullable=False)

    # URL-friendly identifier — e.g. "style-hub-salon"
    # Used for booking page: /book/style-hub-salon
    slug = db.Column(db.String(150), unique=True, nullable=False)

    # Optional business details
    address = db.Column(db.String(250))
    description = db.Column(db.Text)
    # Relative path to the teacher profile photo under app/static.
    teacher_photo = db.Column(db.String(255))
    dataset_id = db.Column(db.String(30), unique=True)
    department = db.Column(db.String(150))
    subject = db.Column(db.String(150))
    office = db.Column(db.String(150))
    designation = db.Column(db.String(150))
    registration_status = db.Column(db.String(20), default='approved', nullable=False)
    rejection_reason = db.Column(db.Text)
    registration_id = db.Column(db.String(30), unique=True)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship: one business → many services
    services = db.relationship(
        "Service",
        backref="business",
        cascade="all, delete-orphan",
        lazy=True
    )

    def get_id(self):
        return f'teacher:{self.id}'

    def set_password(self, password):
        """Hash and store password securely using werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a plain-text password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def generate_slug(self):
        """
        Auto-generate a unique slug from the business name.
        If 'style-hub' exists, tries 'style-hub-2', 'style-hub-3', etc.
        """
        base_slug = slugify(self.name)
        slug = base_slug
        counter = 2
        while Business.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        self.slug = slug

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "description": self.description,
            "teacher_photo": self.teacher_photo,
            "dataset_id": self.dataset_id,
            "department": self.department,
            "subject": self.subject,
            "office": self.office,
            "slug": self.slug,
        }

    def __repr__(self):
        return f"<Business {self.name}>"
