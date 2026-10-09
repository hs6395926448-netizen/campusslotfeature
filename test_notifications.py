"""Email configuration smoke test; does not send a message."""
import os
from dotenv import load_dotenv

load_dotenv()
if os.getenv("RESEND_API_KEY"):
    sender = os.getenv("RESEND_FROM_EMAIL", "")
    if not sender:
        print("[WARN] RESEND_API_KEY is set but RESEND_FROM_EMAIL is missing.")
    else:
        print("[OK] Resend API key and sender are configured. Run the admin notification test to verify actual delivery.")
elif all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_FROM")):
    print("[OK] SMTP settings are present. Run the admin notification test to verify actual delivery.")
else:
    print("[SKIP] Email is not configured. Set RESEND_API_KEY + RESEND_FROM_EMAIL (recommended) or SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD + MAIL_FROM.")
    print("This test checks configuration only and does not send email.")
