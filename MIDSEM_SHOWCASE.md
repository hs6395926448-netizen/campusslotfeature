# CampusSlot — Mid-Semester Showcase Build

This build contains the finalized mid-semester showcase scope.

## Implemented

1. Student and Teacher self-registration with Admin approval/rejection.
2. Registration status and registration ID tracking, including rejection reasons.
3. Role-based Student / Teacher / Admin authentication flow.
4. Student dashboard with appointment statistics and upcoming appointments.
5. Teacher dashboard with appointment statistics, requests, purposes and slots.
6. Admin dashboard with pending registrations, approval/rejection, users and appointment overview.
7. Faculty directory with search, department filtering and availability indicators.
8. Teacher profile page and Teacher Edit Profile.
9. Guided five-stage booking UI: Faculty → Purpose → Date → Time → Confirm.
10. Server-enforced one-appointment-request-per-student-per-calendar-day protection, including a database-level concurrency guard for new requests.
11. Daily-limit warning with remaining-time countdown and existing appointment link.
12. Appointment tracking and status timeline.
13. Calendar page for student/teacher appointments.
14. Appointment email notifications, plus registration submitted/approved/rejected email notifications and Admin notification configuration status.
15. Search/filter and dashboard statistics.
16. Modern landing homepage separated from the faculty directory.
17. Separate Student / Teacher / Admin login and signup entry points.
18. UI/UX cleanup and preservation of the existing database/data model wherever practical.

## Daily Request Rule

A student may submit at most one appointment request per calendar day. The restriction is enforced in the booking service, so changing teacher/purpose, cancelling the appointment, opening another tab, or calling the booking endpoint directly does not bypass it. The reset occurs at the next midnight in `APPOINTMENT_TIMEZONE` (default: `Asia/Kolkata`).

## Existing Data

The bundled SQLite database is migrated for the new registration fields while preserving the existing records. Existing imported accounts are marked `approved` so they continue to work normally.

## Local Run

Use the existing project setup instructions and environment variables. The default development timezone is Asia/Kolkata. Set `APPOINTMENT_TIMEZONE` if the college uses another timezone.
