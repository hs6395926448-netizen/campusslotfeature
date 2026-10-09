# CampusSlot email notification and teacher actions

## Implemented
- Email notifications to student and teacher for new bookings and meeting updates.
- Email-only notification delivery; no WhatsApp/Twilio sending integration or credentials are used.
- Teacher email actions: Confirm, Reject request, Cancel, Complete, and Update date/time.
- Signed, time-limited action links are bound to the teacher, appointment and appointment version.
- Action links open a review form; state changes occur only after a POST confirmation, not on link preview.
- Rescheduling validates dates, appointment duration and overlapping slots, preserves the booking, writes an audit event, and emails both parties with updated details.
- Student/teacher sign-in links and dashboard access are included in notification emails.

## Existing features preserved
- Student/teacher/admin authentication
- Existing dashboards and booking UI
- Slot locking / double-booking protection
- Daily booking limit and tracking IDs
- SQLite and PostgreSQL support

## Runtime setup
Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM and BASE_URL in `.env`. The BASE_URL must be reachable by the teacher's device for email action links to work. Use HTTPS on a deployed/public system. Never commit `.env` or publish app passwords.
