# CampusSlot email buttons — fix notes and run guide

## What was found

- Email delivery is separate from email-button behavior. Each button needs a valid route and a base URL reachable from the device opening the email.
- Teacher action URLs are served by the `booking` blueprint with the `/api` prefix. Hard-coded paths can silently stop matching when a blueprint prefix changes. The action-link builder now asks Flask for the registered route with `url_for()`.
- Tracking and login links are now generated from Flask endpoint names instead of duplicated path strings. This reduces broken links when routes change.
- Teacher action links are signed, expire after 72 hours, and include the appointment ID, teacher ID, action, and appointment version. A GET opens a confirmation page; the database mutation occurs only on POST. After an action increments the appointment version, old links become stale.

## Important: configure BASE_URL correctly

Edit `.env` (copy `.env.example` first):

- Opening Gmail on the same PC that runs Flask: `BASE_URL=http://127.0.0.1:5000`
- Opening Gmail on a phone on the same Wi-Fi: use your PC's LAN IP, e.g. `BASE_URL=http://192.168.1.25:5000`, and allow port 5000 through Windows Firewall. Do not copy that example IP literally; find your PC's actual IPv4 address using `ipconfig`.
- Deployed app: use its public HTTPS address, e.g. `BASE_URL=https://your-real-app.onrender.com`.

`localhost` and `127.0.0.1` always refer to the device opening the link. They will not reach your PC when you tap the email from a phone or another computer.

## Windows commands (VS Code terminal / PowerShell)

Run these from the folder containing `run.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

If PowerShell blocks activation, use Command Prompt and run:

```bat
.venv\Scripts\activate.bat
```

Then open `http://127.0.0.1:5000` in the same PC. Keep the terminal running while testing email links.

## Manual acceptance checklist

1. Register a student and a teacher; each registration email's login button should open the corresponding login page.
2. Approve each account; the approval email should open the same role-specific login page.
3. Create a booking; `View Appointment` should open `/track/<tracking-id>` and auto-load the tracking details.
4. In the teacher booking email, open Confirm/Reject/Cancel/Complete/Update date & time. A confirmation page should appear first. The GET request alone must not change the appointment.
5. Submit the action on the confirmation page. Check the database-backed status, then check the student/teacher notification emails.
6. Try an old action link after successfully using a newer one; it should be rejected as stale. Try a damaged token; it should be rejected.

## Notes

- Email action links are bearer links: anyone who receives/forwards the link may be able to open the confirmation page until it expires. Treat them like password-reset links and do not share them.
- This patch does not configure SMTP credentials, deploy the application, or make a local server publicly reachable. Those depend on your environment.


## Render email URL configuration
Set `BASE_URL` to the exact public HTTPS URL of the deployed CampusSlot service (for example, `https://your-service.onrender.com`). Do not use localhost. The app config derives `SERVER_NAME`, `PREFERRED_URL_SCHEME`, and `APPLICATION_ROOT` from this setting so background email notifications can build appointment and action URLs without an active Flask request.

Resend restriction: `onboarding@resend.dev` is a testing sender and Resend may restrict recipients to the account owner email. To send to students/teachers, verify a domain in Resend and set `RESEND_FROM_EMAIL` to a sender address on that verified domain. Never put API keys into the ZIP or source control.
