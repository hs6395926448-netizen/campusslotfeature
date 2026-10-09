# Import all models here so SQLAlchemy can discover them
# when db.create_all() is called from run.py

from app.models.business import Business
from app.models.service import Service
from app.models.slot import Slot
from app.models.appointment import Appointment

from app.models.student import Student

from app.models.audit_log import AuditLog

from app.models.notification_log import NotificationLog
