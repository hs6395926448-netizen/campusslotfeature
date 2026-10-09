# CampusSlot Major Project — Advanced Database & Notifications

## What is implemented

- PostgreSQL-ready Flask + SQLAlchemy architecture
- Atomic slot booking using `SELECT ... FOR UPDATE`
- Student/day uniqueness guard to reduce spam and concurrent duplicate requests
- PostgreSQL GIN indexes for JSON/JSONB-style metadata and audit details
- PostgreSQL trigram search indexes for teacher/service discovery
- Partial indexes for available slots and active appointments
- Appointment status constraint: pending → confirmed → completed/cancelled
- Audit logging for booking/status changes
- Durable `notification_logs` table for email delivery outcomes
- Automatic email-only notification after a successful booking transaction
- Automatic notification again when teacher confirms/cancels/completes
- Teacher and student receive appointment details and tracking link
- Admin notification configuration/test endpoints
- Staff-only notification delivery audit API: `/api/advanced/notification-logs`

## Notification flow

1. Student selects a teacher slot.
2. PostgreSQL transaction locks the slot.
3. Appointment is inserted and slot is marked booked.
4. Transaction commits.
5. CampusSlot immediately sends email-only to the teacher and student.
6. Delivery result is written to `notification_logs`.
7. If a provider is down, the booking remains valid; the failure is visible in logs/admin tools.

## Provider setup

### Email
Use SMTP credentials in `.env`. For Gmail, use a Google App Password.

### Notifications
CampusSlot sends notifications by email only. Teacher emails include signed links to confirm, reject, cancel, complete, or reschedule a meeting.
