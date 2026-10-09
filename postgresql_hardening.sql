-- CampusSlot PostgreSQL hardening reference
-- The Flask startup migration applies these safely when possible.

CREATE INDEX IF NOT EXISTS ix_slots_available_lookup
    ON slots (service_id, date, start_time)
    WHERE is_booked = FALSE;

CREATE INDEX IF NOT EXISTS ix_appointments_active_student
    ON appointments (student_id, booked_at DESC)
    WHERE status IN ('pending', 'confirmed');

CREATE INDEX IF NOT EXISTS ix_notification_logs_failed
    ON notification_logs (created_at DESC)
    WHERE status = 'failed';

CREATE INDEX IF NOT EXISTS ix_appointments_metadata_gin
    ON appointments USING GIN (metadata);

CREATE INDEX IF NOT EXISTS ix_audit_logs_details_gin
    ON audit_logs USING GIN (details);

-- Optional if your PostgreSQL role permits extensions:
CREATE EXTENSION IF NOT EXISTS pg_trgm;
