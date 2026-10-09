CampusSlot — B.Tech CSE Major Project (Advanced PostgreSQL + Notifications)

# CampusSlot — Teacher Appointment Booking System

This version has been repaired and reorganized as a complete Flask application for a college.

## Main features
- Student registration/login
- Teacher registration/login
- Teacher dashboard
- Teacher creates appointment purposes (Academic Discussion, Project Guidance, etc.)
- Teacher creates date/time slots
- Students see available teachers
- Students select purpose + date + available time
- Booking prevents double-booking
- Student dashboard with appointment history
- Student can cancel pending/confirmed appointments
- Teacher can confirm, complete or cancel appointments
- Tracking ID page
- Appointment tracking API
- Email-only notifications and signed teacher email actions
- SQLite for local development; PostgreSQL can be used in production
- Admin panel from `/admin/<ADMIN_SECRET_KEY>`

## Run locally

1. Extract the project.
2. Open a terminal in the `Slotify-main` folder.
3. Create/activate a virtual environment if desired.
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Optional: copy `.env.example` to `.env` and set `SECRET_KEY`.
6. Recommended first-time setup:

```bash
python setup.py
```

Or simply run `setup.bat` on Windows.

7. Start:

```bash
python run.py
```

8. Open `http://127.0.0.1:5000`.

The application imports all models before calling `db.create_all()`, uses one fixed local
SQLite file under `instance/campusslot.db`, and automatically creates demo users on an
empty development database. This prevents the previous `no such table: businesses` error.

## Demo data

To create a fresh demo database:

```bash
python seed.py
python run.py
```

Demo teacher:
- Email: `teacher@campusslot.com`
- Password: `password123`

Demo student:
- Email: `student@campusslot.com`
- Password: `password123`

The seed script prints the teacher booking URL.

## Important

The repaired version uses `instance/campusslot.db` instead of the old ambiguous
`slotify_dev.db` location. If you deliberately want a completely fresh demo database, run:

```bash
python setup.py --reset
```

On Windows you can use `RESET_DATABASE.bat`. The current project uses
`teacher:<id>` and `student:<id>` Flask-Login IDs consistently.


IMPORTANT WINDOWS FIX FOR "no such table: businesses"
=========================================================
If the browser still shows SQLAlchemy OperationalError: no such table: businesses,
you are almost certainly running an old/stale database or an older copy of the project.
1. Close every Python/Flask terminal running CampusSlot.
2. Make sure you extracted THIS ZIP and open its Slotify-main folder.
3. Double-click REPAIR_DATABASE.bat.
4. Then double-click start.bat.
5. Open http://127.0.0.1:5000
The launcher prints the exact SQLite database path it is using. It must end in:
Slotify-main\instance\campusslot.db
Do not run an older copy from another CampusSlot/Slotify folder.

ADMINISTRATOR ACCOUNT SYSTEM
============================
Student and teacher self-registration has been disabled.
Only a logged-in administrator can create:
- Student accounts
- Teacher accounts
- Additional administrator accounts

Administrator login:
URL: http://127.0.0.1:5000/admin/login
Default development bootstrap account:
Email: admin@campusslot.com
Password: admin123

After logging in, use the Administrator Dashboard to create all accounts.
For production, change the bootstrap password immediately and/or create a new administrator account, then disable the bootstrap account in the database.


POSTGRESQL + ADVANCED DATABASE FEATURES
========================================
The application is now PostgreSQL-ready in both development and production.

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a PostgreSQL database and set:
```env
DATABASE_URL=postgresql+psycopg2://USERNAME:PASSWORD@HOST:5432/campusslot
```

If DATABASE_URL is not set, local development continues to use SQLite.

PostgreSQL features added:
- Connection pooling + pre-ping/recycle for production reliability
- Row-level locking for race-free slot booking
- Composite indexes for appointment/status queries
- JSON metadata on appointments (JSONB-backed GIN index on PostgreSQL)
- JSON audit log storage with GIN indexing
- pg_trgm fuzzy/fast text-search indexes for teacher/service discovery
- Automatic audit trail for appointment creation/status changes
- Appointment optimistic-lock versioning
- Database health endpoint: `/api/advanced/health`
- Search endpoint: `/api/advanced/search?q=project`
- Staff analytics endpoint: `/api/advanced/analytics`

Example:
```text
GET /api/advanced/search?q=project
GET /api/advanced/health
GET /api/advanced/analytics
```

For production, use PostgreSQL instead of the bundled SQLite database and keep
DATABASE_URL/credentials in the hosting provider's secret environment variables.


EASY WINDOWS SETUP (UPDATED PACKAGE)
=====================================
For first run on Windows, read RUN_FIRST_WINDOWS.txt and double-click setup.bat, then start.bat. SQLite is used by default; Docker/PostgreSQL is optional. PostgreSQL driver is in requirements-postgres.txt and is not installed by the default setup.


## Real notifications
Run `configure_notifications.bat`, then `test_notifications.bat`. Real email requires provider credentials.


NOTIFICATIONS + TEACHER PHONE ACTIONS
----------------------------------------
See NOTIFICATIONS_SETUP.md. Booking sends email-only to both student and teacher. Teacher messages include secure mobile actions for Confirm, Cancel, and Complete.
