"""CampusSlot configuration."""

import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
LOCAL_DB = INSTANCE_DIR / "campusslot.db"


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "campusslot-development-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "admin-secret-change-this")

    BASE_URL = (os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:5000").rstrip("/")
    # URL generation also happens in background email jobs, where Flask has no
    # active HTTP request. SERVER_NAME lets url_for() build endpoint paths there.
    _base_url_parts = urlsplit(BASE_URL)
    SERVER_NAME = _base_url_parts.netloc or "127.0.0.1:5000"
    PREFERRED_URL_SCHEME = _base_url_parts.scheme or "http"
    APPLICATION_ROOT = os.getenv("APPLICATION_ROOT", "/")
    APPOINTMENT_TIMEZONE = os.getenv("APPOINTMENT_TIMEZONE", "Asia/Kolkata")
    DAILY_APPOINTMENT_REQUEST_LIMIT = 1

    # Google Apps Script + Gmail HTTPS gateway (preferred when configured)
    APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "")
    APPS_SCRIPT_SECRET = os.getenv("APPS_SCRIPT_SECRET", "")

    # Email API (fallback on Render Free)
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "CampusSlot <onboarding@resend.dev>")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")

    # Email / SMTP notifications
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USERNAME)
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # If DATABASE_URL is supplied, development uses PostgreSQL too.
    # Otherwise keep the zero-setup SQLite fallback.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{LOCAL_DB.as_posix()}"
    )


class ProductionConfig:
    DEBUG = False
    SECRET_KEY = BaseConfig.SECRET_KEY
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_SECRET_KEY = BaseConfig.ADMIN_SECRET_KEY
    BASE_URL = BaseConfig.BASE_URL
    SERVER_NAME = BaseConfig.SERVER_NAME
    PREFERRED_URL_SCHEME = BaseConfig.PREFERRED_URL_SCHEME
    APPLICATION_ROOT = BaseConfig.APPLICATION_ROOT
    APPOINTMENT_TIMEZONE = BaseConfig.APPOINTMENT_TIMEZONE
    DAILY_APPOINTMENT_REQUEST_LIMIT = BaseConfig.DAILY_APPOINTMENT_REQUEST_LIMIT
    APPS_SCRIPT_URL = BaseConfig.APPS_SCRIPT_URL
    APPS_SCRIPT_SECRET = BaseConfig.APPS_SCRIPT_SECRET
    RESEND_API_KEY = BaseConfig.RESEND_API_KEY
    RESEND_FROM_EMAIL = BaseConfig.RESEND_FROM_EMAIL
    CELERY_BROKER_URL = BaseConfig.CELERY_BROKER_URL
    SMTP_HOST = BaseConfig.SMTP_HOST
    SMTP_PORT = BaseConfig.SMTP_PORT
    SMTP_USERNAME = BaseConfig.SMTP_USERNAME
    SMTP_PASSWORD = BaseConfig.SMTP_PASSWORD
    MAIL_FROM = BaseConfig.MAIL_FROM
    SMTP_USE_TLS = BaseConfig.SMTP_USE_TLS
    SMTP_USE_SSL = BaseConfig.SMTP_USE_SSL
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")

    @classmethod
    def init_app(cls, app):
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if uri.startswith("postgres://"):
            app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace("postgres://", "postgresql://", 1)


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
