"""
Daily Renewal Alert — trimite email brokerilor cu politele ce expira curand.

Poate fi rulat:
  1. Manual: python scripts/daily_renewal_alert.py
  2. Cloud Run Job + Cloud Scheduler (zilnic la 08:00)
  3. n8n HTTP Request → Code node → Send Email

Configurare (env vars sau .env):
  ALEX_API_URL    — URL-ul aplicatiei Alex (ex: https://insurance-broker-alex-....run.app)
  SMTP_HOST       — server SMTP (ex: smtp.gmail.com)
  SMTP_PORT       — 587 (TLS) sau 465 (SSL)
  SMTP_USER       — user SMTP (adresa email)
  SMTP_PASS       — parola / app password
  ALERT_TO        — email(uri) destinatar, separate cu virgula (ex: broker@firma.ro,manager@firma.ro)
  ALERT_DAYS      — zile inainte de expirare pentru alerta (default: 30)
  SMTP_FROM_NAME  — numele expeditorului (default: Alex Insurance Broker)
"""
import os
import sys
import json
import smtplib
import urllib.request
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Load .env if present (only needed when running locally)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

ALEX_API_URL = os.environ.get("ALEX_API_URL", "https://insurance-broker-alex-603810013022.europe-west3.run.app")
SMTP_HOST    = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER    = os.environ.get("SMTP_USER", "")
SMTP_PASS    = os.environ.get("SMTP_PASS", "")
FROM_NAME    = os.environ.get("SMTP_FROM_NAME", "Alex Insurance Broker")
ALERT_TO     = [e.strip() for e in os.environ.get("ALERT_TO", "").split(",") if e.strip()]
ALERT_DAYS   = int(os.environ.get("ALERT_DAYS", "30"))


def fetch_renewals(days: int) -> dict:
    url = f"{ALEX_API_URL}/api/renewals?days={days}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"ERROR fetching renewals: {e}")
        sys.exit(1)


def build_html(data: dict) -> str:
    today = date.today().strftime("%d %B %Y")
    urgent   = data.get("urgent", [])
    upcoming = data.get("upcoming", [])
    total    = data.get("total", 0)

    def row(p: dict, urgent: bool) -> str:
        bg     = "#fff3cd" if urgent else "#ffffff"
        badge  = "🔴 URGENT" if urgent else "🟡"
        days   = p.get("days_left", "?")
        return f"""
        <tr style="background:{bg}">
          <td style="padding:8px;border:1px solid #dee2e6">{badge}</td>
          <td style="padding:8px;border:1px solid #dee2e6"><b>{p.get('client_name','')}</b><br>
              <small>{p.get('client_email','—')} | {p.get('client_phone','—')}</small></td>
          <td style="padding:8px;border:1px solid #dee2e6">{p.get('policy_type','')}</td>
          <td style="padding:8px;border:1px solid #dee2e6">{p.get('insurer','')}</td>
          <td style="padding:8px;border:1px solid #dee2e6">{p.get('end_date','')}</td>
          <td style="padding:8px;border:1px solid #dee2e6"><b>{days} zile</b></td>
          <td style="padding:8px;border:1px solid #dee2e6">{p.get('annual_premium',''):.0f} {p.get('currency','RON')}</td>
        </tr>"""

    rows = "".join(row(p, True) for p in urgent) + "".join(row(p, False) for p in upcoming)

    if not rows:
        rows = '<tr><td colspan="7" style="padding:16px;text-align:center;color:#6c757d">Nicio polita nu expira in urmatoarele {} zile.</td></tr>'.format(ALERT_DAYS)

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body {{ font-family: Arial, sans-serif; color: #212529; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #0d6efd; color: white; padding: 10px 8px; text-align: left; border: 1px solid #0a58ca; }}
</style></head>
<body>
<h2 style="color:#0d6efd">📊 Alex — Reinnoiri Polite / {today}</h2>
<p>Buna ziua,</p>
<p>Urmatoarele polite expira in urmatoarele <b>{ALERT_DAYS} zile</b>:
   <b>{len(urgent)} urgente</b> (≤7 zile) si <b>{len(upcoming)} apropiate</b>.</p>

<table>
  <thead>
    <tr>
      <th>Status</th><th>Client</th><th>Tip</th><th>Asigurator</th>
      <th>Expira</th><th>Zile ramase</th><th>Prima anuala</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<br>
<p style="color:#6c757d;font-size:12px">
  Generat automat de Alex Insurance Broker AI.<br>
  Dashboard live: <a href="{ALEX_API_URL}">{ALEX_API_URL}</a>
</p>
</body>
</html>"""


def send_email(to_list: list[str], subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print("WARN: SMTP not configured — printing email to stdout instead\n")
        print(f"To: {', '.join(to_list)}")
        print(f"Subject: {subject}")
        print("(HTML body omitted in stdout mode)")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"]      = ", ".join(to_list)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, to_list, msg.as_string())
        print(f"Email sent to {', '.join(to_list)}")
        return True
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False


def main():
    print(f"Fetching renewals for next {ALERT_DAYS} days from {ALEX_API_URL}...")
    data = fetch_renewals(ALERT_DAYS)

    urgent   = data.get("urgent", [])
    upcoming = data.get("upcoming", [])
    total    = data.get("total", 0)

    print(f"Found: {len(urgent)} urgent, {len(upcoming)} upcoming, {total} total")

    today   = date.today().strftime("%d %B %Y")
    subject = f"Alex Reinnoiri — {len(urgent)} urgente, {total} total / {today}"
    html    = build_html(data)

    recipients = ALERT_TO or ["broker@demo.ro"]  # fallback for dry-run
    ok = send_email(recipients, subject, html)

    # Exit code 0 = success (Cloud Run Job expects this)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
