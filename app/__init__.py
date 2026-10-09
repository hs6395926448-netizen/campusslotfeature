"""CampusSlot application factory and database initialization."""

from flask import Flask
from datetime import timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config
import os


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access your dashboard."
login_manager.login_message_category = "warning"


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Normalize legacy Render/Postgres URLs.
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = uri

    # Production-grade connection handling for PostgreSQL.
    if uri.startswith(("postgresql://", "postgresql+psycopg2://")):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "pool_size": int(__import__("os").getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(__import__("os").getenv("DB_MAX_OVERFLOW", "10")),
        }

    db.init_app(app)
    login_manager.init_app(app)

    # IMPORTANT: import every model before create_all().  SQLAlchemy only
    # creates tables for models that have been registered with its metadata.
    # This fixes the old "no such table: businesses" error on a fresh/partial DB.
    from app import models  # noqa: F401
    from app.models.business import Business
    from app.models.student import Student
    from app.models.admin import Admin

    @login_manager.user_loader
    def load_user(user_id):
        value = str(user_id)
        try:
            if value.startswith("student:"):
                return db.session.get(Student, int(value.split(":", 1)[1]))
            if value.startswith("teacher:"):
                return db.session.get(Business, int(value.split(":", 1)[1]))
            if value.startswith("admin:"):
                return db.session.get(Admin, int(value.split(":", 1)[1]))
        except (ValueError, TypeError):
            return None
        return None

    from app.routes.booking import booking_bp
    from app.routes.services import services_bp
    from app.routes.slots import slots_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.student import student_bp
    from app.routes.profile import profile_bp
    from app.routes.advanced import advanced_bp

    app.register_blueprint(booking_bp, url_prefix="/api")
    app.register_blueprint(services_bp, url_prefix="/api")
    app.register_blueprint(slots_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(advanced_bp)

    # Always make sure the local database schema exists before any request can
    # execute a query. This is intentionally safe for an existing database:
    # create_all() adds missing tables but does not delete existing data.
    with app.app_context():
        # First create any missing tables.
        db.create_all()

        # Lightweight schema migration for installations created before teacher photos.
        # db.create_all() does not add new columns to an existing table.
        from sqlalchemy import inspect, text
        business_columns = {c["name"] for c in inspect(db.engine).get_columns("businesses")}
        if "teacher_photo" not in business_columns:
            db.session.execute(text("ALTER TABLE businesses ADD COLUMN teacher_photo VARCHAR(255)"))
            db.session.commit()
        # Dataset integration fields. create_all() does not add columns to an
        # existing SQLite database, so migrate them explicitly.
        # Mid-semester registration workflow columns. Existing imported accounts
        # remain approved; new self-registrations are pending until admin review.
        registration_columns = {
            "businesses": {
                "designation": "VARCHAR(150)", "registration_status": "VARCHAR(20)",
                "rejection_reason": "TEXT", "registration_id": "VARCHAR(30)"
            },
            "students": {
                "registration_status": "VARCHAR(20)", "rejection_reason": "TEXT",
                "registration_id": "VARCHAR(30)"
            }
        }
        for table_name, columns in registration_columns.items():
            existing = {c["name"] for c in inspect(db.engine).get_columns(table_name)}
            for col_name, col_type in columns.items():
                if col_name not in existing:
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
        db.session.execute(text("UPDATE businesses SET registration_status='approved' WHERE registration_status IS NULL"))
        db.session.execute(text("UPDATE students SET registration_status='approved' WHERE registration_status IS NULL"))

        # Daily request protection: add a per-student calendar-day key. Existing
        # appointments are backfilled using the configured application timezone.
        appointment_columns = {c["name"] for c in inspect(db.engine).get_columns("appointments")}
        if "request_date" not in appointment_columns:
            db.session.execute(text("ALTER TABLE appointments ADD COLUMN request_date VARCHAR(10)"))
        # Advanced booking fields added after the original schema.
        if "metadata" not in appointment_columns:
            db.session.execute(text("ALTER TABLE appointments ADD COLUMN metadata JSON"))
        if "version" not in appointment_columns:
            db.session.execute(text("ALTER TABLE appointments ADD COLUMN version INTEGER DEFAULT 1"))
        db.session.execute(text("UPDATE appointments SET version=1 WHERE version IS NULL"))
        db.session.execute(text("UPDATE appointments SET metadata='{}' WHERE metadata IS NULL"))
        tz_name = app.config.get("APPOINTMENT_TIMEZONE", "Asia/Kolkata")
        from zoneinfo import ZoneInfo
        try:
            migration_tz = ZoneInfo(tz_name)
        except Exception:
            # Windows may not have the IANA tz database available. tzdata is
            # included in requirements, but keep a safe fallback for older
            # installations so the app can still boot.
            migration_tz = timezone.utc
        from app.models.appointment import Appointment
        legacy_appointments = Appointment.query.filter(Appointment.student_id.isnot(None), Appointment.request_date.is_(None)).all()
        for appt in legacy_appointments:
            if appt.booked_at:
                booked = appt.booked_at.replace(tzinfo=timezone.utc).astimezone(migration_tz)
                appt.request_date = booked.date().isoformat()
        db.session.commit()
        # Existing imported data can legitimately contain more than one appointment
        # for a student on the same historical day. Preserve that history. For new
        # rows, a partial unique index closes the concurrent-request race that an
        # application-level existence check alone cannot prevent. SQLite and
        # PostgreSQL both support this form.
        max_existing_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM appointments")).scalar() or 0
        index_sql = (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_new_appointments_student_request_date "
            f"ON appointments(student_id, request_date) WHERE id > {int(max_existing_id)}"
        )
        db.session.execute(text(index_sql))
        db.session.commit()

        dataset_columns = {
            "businesses": {
                "dataset_id": "VARCHAR(30)", "department": "VARCHAR(150)",
                "subject": "VARCHAR(150)", "office": "VARCHAR(150)"
            },
            "students": {
                "course": "VARCHAR(80)", "semester": "INTEGER", "dataset_id": "VARCHAR(30)"
            },
            "services": {"dataset_id": "VARCHAR(30)"},
            "slots": {"dataset_id": "VARCHAR(30)", "source": "VARCHAR(30)"},
            "appointments": {"dataset_id": "VARCHAR(30)"}
        }
        for table_name, columns in dataset_columns.items():
            existing = {c["name"] for c in inspect(db.engine).get_columns(table_name)}
            for col_name, col_type in columns.items():
                if col_name not in existing:
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
        db.session.commit()

        # Always make a defensive second schema pass.
        required_tables = {"businesses", "students", "admins", "services", "slots", "appointments", "audit_logs", "notification_logs"}
        existing_tables = set(inspect(db.engine).get_table_names())
        missing_tables = required_tables - existing_tables
        if missing_tables:
            # A very defensive second pass for partially-created SQLite databases.
            db.create_all()
            existing_tables = set(inspect(db.engine).get_table_names())
            missing_tables = required_tables - existing_tables
        if missing_tables:
            raise RuntimeError(
                "CampusSlot database initialization failed. Missing tables: "
                + ", ".join(sorted(missing_tables))
                + f". Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}"
            )

        # Advanced PostgreSQL capabilities. These are created only on PostgreSQL,
        # while portable SQLAlchemy indexes remain usable on SQLite.
        if db.engine.dialect.name == "postgresql":
            try:
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_appointments_metadata_gin
                    ON appointments USING GIN (metadata)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_audit_logs_details_gin
                    ON audit_logs USING GIN (details)
                """))
                # Fast case-insensitive search for teacher/service discovery.
                db.session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_businesses_name_trgm
                    ON businesses USING GIN (name gin_trgm_ops)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_services_name_trgm
                    ON services USING GIN (name gin_trgm_ops)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_slots_available_lookup
                    ON slots (service_id, date, start_time)
                    WHERE is_booked = FALSE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_appointments_active_student
                    ON appointments (student_id, booked_at DESC)
                    WHERE status IN ('pending', 'confirmed')
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_notification_logs_failed
                    ON notification_logs (created_at DESC)
                    WHERE status = 'failed'
                """))
                db.session.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'ck_appointments_status'
                        ) THEN
                            ALTER TABLE appointments
                            ADD CONSTRAINT ck_appointments_status
                            CHECK (status IN ('pending','confirmed','completed','cancelled'));
                        END IF;
                    END $$;
                """))
                db.session.commit()
            except Exception:
                # Some managed PostgreSQL roles disallow CREATE EXTENSION.
                # Core application functionality must still start normally.
                db.session.rollback()

        # First local launch convenience: create one bootstrap administrator in debug mode.
        # All additional administrator, teacher and student accounts are created from the admin panel.
        
        # Create an admin when Render bootstrap variables are configured.
        bootstrap_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        bootstrap_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        bootstrap_name = os.getenv(
            "BOOTSTRAP_ADMIN_NAME", "CampusSlot Administrator"
        ).strip()

        if bootstrap_email and bootstrap_password:
            if not Admin.query.filter_by(email=bootstrap_email).first():
                if len(bootstrap_password) < 12 or "@" not in bootstrap_email:
                    raise RuntimeError("Invalid bootstrap admin configuration")

                admin = Admin(
                    name=bootstrap_name or "CampusSlot Administrator",
                    email=bootstrap_email,
                    password_hash="placeholder",
                )
                admin.set_password(bootstrap_password)
                db.session.add(admin)
                db.session.commit()
    

        # First local launch: load the bundled engineering-college dataset into
        # the real CampusSlot tables. This is actual seed data, not a disconnected CSV.
        # Existing databases are never overwritten automatically.
        if app.config.get("DEBUG") and not Business.query.first() and not Student.query.first():
            # Optional CSV dataset: only import it when all required files are bundled.
            # Fresh ZIPs may intentionally omit the private/demo CSVs; setup.py then
            # creates the built-in demo accounts and slots without crashing startup.
            from pathlib import Path
            dataset_dir = Path(app.root_path).parent / "dataset"
            required_csv = ("students.csv", "teachers.csv", "availability.csv", "appointments.csv")
            if all((dataset_dir / filename).is_file() for filename in required_csv):
                from dataset_loader import load_dataset
                load_dataset(reset=False)

    return app
