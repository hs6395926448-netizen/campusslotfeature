"""Reliable professional email notifications for CampusSlot."""
from email.message import EmailMessage
from html import escape
import json
import smtplib
import ssl
from urllib.request import Request, urlopen
from flask import current_app, url_for
from app.services.teacher_action_service import make_action_url


def _smtp_ready():
    required = [
        current_app.config.get("SMTP_HOST"),
        current_app.config.get("MAIL_FROM"),
        current_app.config.get("SMTP_USERNAME"),
        current_app.config.get("SMTP_PASSWORD"),
    ]
    return all(required)


def _send_email(to_email, subject, text_body, html_body):
    if not to_email:
        raise RuntimeError("Recipient email address is missing.")

    # Google Apps Script + Gmail gateway uses HTTPS, so it works on Render Free
    # without SMTP ports or a custom email domain. Configure both variables.
    gateway_url = (current_app.config.get("APPS_SCRIPT_URL") or "").strip()
    gateway_secret = current_app.config.get("APPS_SCRIPT_SECRET") or ""
    if gateway_url or gateway_secret:
        if not gateway_url or not gateway_secret:
            raise RuntimeError(
                "Google Apps Script email gateway needs both APPS_SCRIPT_URL and APPS_SCRIPT_SECRET."
            )
        payload = json.dumps({
            "token": gateway_secret,
            "to": to_email,
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }).encode("utf-8")
        request = Request(
            gateway_url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=25) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Google Apps Script email gateway request failed: {exc}") from exc
        if not isinstance(result, dict) or not result.get("ok"):
            message = result.get("error", "Unknown gateway error") if isinstance(result, dict) else "Invalid gateway response"
            raise RuntimeError(f"Google Apps Script email gateway rejected the email: {message}")
        current_app.logger.info("CampusSlot Google Apps Script gateway accepted email")
        return True

    # Prefer Resend's HTTPS API when configured. This avoids outbound SMTP
    # ports, which are blocked on Render Free services.
    resend_api_key = current_app.config.get("RESEND_API_KEY")
    if resend_api_key:
        import resend
        resend.api_key = resend_api_key
        sender = current_app.config.get("RESEND_FROM_EMAIL") or "CampusSlot <onboarding@resend.dev>"
        result = resend.Emails.send({
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        })
        current_app.logger.info("CampusSlot Resend API accepted email | id=%s", result.get("id", "unknown") if isinstance(result, dict) else "accepted")
        return True

    # Fall back to SMTP for local development or other hosting providers.
    if not _smtp_ready():
        raise RuntimeError(
            "Email is not configured. Create a .env file and set SMTP_HOST, "
            "SMTP_USERNAME, SMTP_PASSWORD and MAIL_FROM. For Gmail use an App Password."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config["MAIL_FROM"]
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    host = current_app.config["SMTP_HOST"]
    port = int(current_app.config.get("SMTP_PORT", 587))
    username = current_app.config["SMTP_USERNAME"]
    password = current_app.config["SMTP_PASSWORD"]
    use_tls = current_app.config.get("SMTP_USE_TLS", True)
    use_ssl = current_app.config.get("SMTP_USE_SSL", False)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=25) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=25) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(msg)
    return True


def send_appointment_email(appointment, event="confirmed"):
    slot = appointment.slot
    service = slot.service
    teacher = service.business
    student_email = getattr(appointment.student, "email", None)

    status_text = {
        "pending": "Booking request received",
        "confirmed": "Meeting confirmed",
        "cancelled": "Meeting cancelled",
        "completed": "Meeting completed",
        "rescheduled": "Meeting rescheduled",
    }.get(event, "Appointment update")

    date_text = slot.date.strftime("%A, %d %B %Y")
    time_text = f"{slot.start_time} – {slot.end_time}"
    tracking_path = url_for("dashboard.tracking_page", tracking_id=appointment.tracking_id, _external=False)
    tracking_url = f"{current_app.config['BASE_URL'].rstrip('/')}{tracking_path}"
    teacher_actions = {
        "confirmed": make_action_url(appointment, "confirmed"),
        "rejected": make_action_url(appointment, "rejected"),
        "cancelled": make_action_url(appointment, "cancelled"),
        "completed": make_action_url(appointment, "completed"),
        "reschedule": make_action_url(appointment, "reschedule"),
    }
    teacher_login_path = url_for("auth.login", next="/dashboard", _external=False)
    teacher_login_url = f"{current_app.config['BASE_URL'].rstrip('/')}{teacher_login_path}"
    student_login_path = url_for("student.login", next="/student/dashboard", _external=False)
    student_login_url = f"{current_app.config['BASE_URL'].rstrip('/')}{student_login_path}"
    teacher_dashboard_path = url_for("dashboard.dashboard", _external=False)
    teacher_dashboard_url = f"{current_app.config['BASE_URL'].rstrip('/')}{teacher_dashboard_path}"

    intro = {
        "confirmed": "Your CampusSlot meeting has been confirmed by the teacher.",
        "cancelled": "This CampusSlot meeting has been cancelled. The time slot is available again.",
        "pending": "A new CampusSlot booking request has been created and is waiting for teacher confirmation.",
        "completed": "This CampusSlot appointment has been marked as completed.",
        "rescheduled": "The teacher updated the date or time for this CampusSlot meeting. Please review the new details below.",
    }.get(event, "This CampusSlot appointment has been updated.")

    recipients = [student_email, teacher.email]
    unique_recipients = []
    seen = set()
    for email in recipients:
        key = (email or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique_recipients.append(email.strip())

    sent = 0
    errors = []
    for recipient in unique_recipients:
        is_teacher = recipient.lower() == (teacher.email or "").lower()
        greeting = f"Dear {teacher.name if is_teacher else appointment.customer_name},"
        subject = f"CampusSlot | {status_text} | {appointment.tracking_id}"
        text = (
            f"{greeting}\n\n{intro}\n\n"
            f"Meeting details\nTeacher: {teacher.name}\nStudent: {appointment.customer_name}\n"
            f"Purpose: {service.name}\nDate: {date_text}\nTime: {time_text}\n"
            f"Status: {event.upper()}\nTracking ID: {appointment.tracking_id}\n\n"
            f"View appointment: {tracking_url}\n"
            + (
                f"\nTeacher quick actions (from your phone):\n"
                f"Confirm: {teacher_actions['confirmed']}\n"
                f"Reject request: {teacher_actions['rejected']}\n"
                f"Cancel: {teacher_actions['cancelled']}\n"
                f"Complete: {teacher_actions['completed']}\n"
                f"Update meeting date/time: {teacher_actions['reschedule']}\n"
                f"Update/manage meeting (sign in): {teacher_dashboard_url}\n"
                if is_teacher and event in {"pending", "rescheduled"} else ""
            )
            + "\nCampusSlot automated notification."
        )
        html = f"""
        <div style='margin:0;background:#f4f7fb;padding:32px 12px;font-family:Arial,sans-serif;color:#172033'>
          <div style='max-width:620px;margin:auto;background:#fff;border:1px solid #e7ebf2;border-radius:16px;overflow:hidden'>
            <div style='padding:24px 28px;background:#0d6efd;color:#fff'>
              <div style='font-size:24px;font-weight:700'>CampusSlot</div>
              <div style='opacity:.9;margin-top:5px'>{escape(status_text)}</div>
            </div>
            <div style='padding:28px'>
              <p style='font-size:16px'>{escape(greeting)}</p>
              <p style='font-size:15px;line-height:1.6'>{escape(intro)}</p>
              <div style='background:#f8fafc;border:1px solid #e7ebf2;border-radius:12px;padding:18px;margin:20px 0'>
                <p><strong>Teacher:</strong> {escape(teacher.name)}</p>
                <p><strong>Student:</strong> {escape(appointment.customer_name)}</p>
                <p><strong>Purpose:</strong> {escape(service.name)}</p>
                <p><strong>Date:</strong> {escape(date_text)}</p>
                <p><strong>Time:</strong> {escape(time_text)}</p>
                <p><strong>Status:</strong> {escape(event.upper())}</p>
                <p style='margin-bottom:0'><strong>Tracking ID:</strong> {escape(appointment.tracking_id)}</p>
              </div>
              <a href='{escape(tracking_url)}' style='display:inline-block;background:#0d6efd;color:#fff;text-decoration:none;padding:12px 18px;border-radius:8px;font-weight:700'>View Appointment</a>
              <div style='margin-top:18px;font-size:13px'><a href='{escape(student_login_url)}'>Student sign in</a> &nbsp;·&nbsp; <a href='{escape(teacher_login_url)}'>Teacher sign in</a></div>
              {(
                "<div style='margin-top:22px;padding:16px;border:1px solid #e7ebf2;border-radius:12px;background:#fbfcfe'>"
                "<strong>Teacher quick actions</strong><p style='font-size:13px;color:#667085'>Use these links directly from your phone.</p>"
                f"<a href='{escape(teacher_actions['confirmed'])}' style='display:inline-block;margin:4px 6px 4px 0;padding:10px 14px;background:#198754;color:#fff;text-decoration:none;border-radius:7px'>Confirm</a>"
                f"<a href='{escape(teacher_actions['rejected'])}' style='display:inline-block;margin:4px 6px 4px 0;padding:10px 14px;background:#dc3545;color:#fff;text-decoration:none;border-radius:7px'>Reject request</a>"
                f"<a href='{escape(teacher_actions['cancelled'])}' style='display:inline-block;margin:4px 6px 4px 0;padding:10px 14px;background:#b02a37;color:#fff;text-decoration:none;border-radius:7px'>Cancel</a>"
                f"<a href='{escape(teacher_actions['completed'])}' style='display:inline-block;margin:4px 0;padding:10px 14px;background:#6f42c1;color:#fff;text-decoration:none;border-radius:7px'>Complete</a>"
                f"<p><a href='{escape(teacher_actions['reschedule'])}' style='display:inline-block;padding:10px 14px;background:#0d6efd;color:#fff;text-decoration:none;border-radius:7px'>Update date &amp; time</a></p>"
                f"<p><a href='{escape(teacher_dashboard_url)}'>Sign in to update/manage meeting</a></p>"
                "</div>"
                if is_teacher and event in {"pending", "rescheduled"} else ""
              )}
              <p style='font-size:12px;color:#667085;margin-top:28px'>Automated notification from CampusSlot.</p>
            </div>
          </div>
        </div>"""
        try:
            _send_email(recipient, subject, text, html)
            sent += 1
            current_app.logger.info("CampusSlot EMAIL SENT | event=%s | to=%s | appointment=%s", event, recipient, appointment.tracking_id)
        except Exception as exc:
            errors.append(f"{recipient}: {exc}")
            current_app.logger.exception("CampusSlot EMAIL FAILED | event=%s | to=%s | appointment=%s", event, recipient, appointment.tracking_id)

    return {"sent": sent, "attempted": len(unique_recipients), "errors": errors}


def send_registration_email(record, event="submitted"):
    """Send registration lifecycle email to a student or teacher."""
    if not getattr(record, "email", None):
        return {"sent": 0, "attempted": 0, "errors": ["Recipient email address is missing."]}
    labels = {
        "submitted": ("Registration submitted", "Your CampusSlot registration request has been received and is waiting for administrator approval."),
        "approved": ("Registration approved", "Your CampusSlot account has been approved. You can now sign in."),
        "rejected": ("Registration rejected", f"Your CampusSlot registration was rejected. Reason: {getattr(record, 'rejection_reason', None) or 'No reason provided.'}"),
    }
    subject_label, intro = labels.get(event, ("Registration update", "Your CampusSlot registration status has been updated."))
    role = "Teacher" if record.__class__.__name__ == "Business" else "Student"
    registration_id = getattr(record, "registration_id", None) or "Not assigned"
    login_path = url_for("auth.login" if role == "Teacher" else "student.login", _external=False)
    login_url = f"{current_app.config['BASE_URL'].rstrip('/')}{login_path}"
    text = (
        f"Dear {record.name},\n\n{intro}\n\nRole: {role}\nRegistration ID: {registration_id}\n\n"
        f"Sign in: {login_url}\n\nCampusSlot automated notification."
    )
    html = f"""
    <div style='font-family:Arial,sans-serif;max-width:620px;margin:30px auto;padding:28px;border:1px solid #e7ebf2;border-radius:16px'>
      <h2 style='color:#0d6efd;margin-top:0'>CampusSlot</h2>
      <h3>{escape(subject_label)}</h3>
      <p>{escape(intro)}</p>
      <p><strong>Role:</strong> {escape(role)}<br><strong>Registration ID:</strong> {escape(registration_id)}</p>
      <a href='{escape(login_url)}' style='display:inline-block;background:#0d6efd;color:#fff;text-decoration:none;padding:12px 18px;border-radius:8px;font-weight:700'>CampusSlot Login</a>
    </div>"""
    try:
        _send_email(record.email, f"CampusSlot | {subject_label} | {registration_id}", text, html)
        return {"sent": 1, "attempted": 1, "errors": []}
    except Exception as exc:
        current_app.logger.exception("CampusSlot REGISTRATION EMAIL FAILED | event=%s | to=%s", event, record.email)
        return {"sent": 0, "attempted": 1, "errors": [str(exc)]}
