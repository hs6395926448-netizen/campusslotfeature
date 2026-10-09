import os
from pathlib import Path
from getpass import getpass

ROOT = Path(__file__).resolve().parent
env_path = ROOT / ".env"
example = ROOT / ".env.example"

def load_existing():
    data = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data

def write_env(data):
    lines = [
        "FLASK_ENV=development",
        f"SECRET_KEY={data.get('SECRET_KEY','campusslot-development-secret-change-me')}",
        f"ADMIN_SECRET_KEY={data.get('ADMIN_SECRET_KEY','admin-secret-change-this')}",
        f"BASE_URL={data.get('BASE_URL','http://127.0.0.1:5000')}",
        "APPOINTMENT_TIMEZONE=Asia/Kolkata",
        "",
        "# Gmail SMTP",
        f"SMTP_HOST={data.get('SMTP_HOST','smtp.gmail.com')}",
        f"SMTP_PORT={data.get('SMTP_PORT','587')}",
        f"SMTP_USERNAME={data.get('SMTP_USERNAME','')}",
        f"SMTP_PASSWORD={data.get('SMTP_PASSWORD','')}",
        f"MAIL_FROM={data.get('MAIL_FROM','')}",
        f"SMTP_USE_TLS={data.get('SMTP_USE_TLS','true')}",
        f"SMTP_USE_SSL={data.get('SMTP_USE_SSL','false')}",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

data = load_existing()
print("=" * 64)
print("CampusSlot - EMAIL NOTIFICATION SETUP")
print("=" * 64)
print()
print("Email uses Gmail SMTP. You MUST use a Gmail App Password,")
print("not your normal Gmail password.")
print()
gmail = input(f"Gmail address [{data.get('SMTP_USERNAME','')}]: ").strip()
if gmail:
    data["SMTP_USERNAME"] = gmail
    data["MAIL_FROM"] = f"CampusSlot <{gmail}>"

app_pw = getpass("Gmail App Password (leave blank to keep existing): ").strip()
if app_pw:
    data["SMTP_PASSWORD"] = app_pw.replace(" ", "")
data["SMTP_HOST"] = "smtp.gmail.com"
data["SMTP_PORT"] = "587"
data["SMTP_USE_TLS"] = "true"
data["SMTP_USE_SSL"] = "false"


write_env(data)
print()
print("Saved notification configuration to .env")
print("IMPORTANT: .env is local and should never be uploaded to GitHub.")
