"""
Alex Agent SDK Orchestrator — Autonomous Insurance Broker Tasks

Runs on a GCE VM (or any server) and executes scheduled insurance tasks
using the Alex REST API. No Claude Code CLI needed — uses Anthropic API directly.

Usage:
    python agent-sdk/orchestrator.py --task renewals
    python agent-sdk/orchestrator.py --task compliance
    python agent-sdk/orchestrator.py --task follow-up
    python agent-sdk/orchestrator.py --task morning-brief
    python agent-sdk/orchestrator.py --task all

Environment:
    ANTHROPIC_API_KEY  — Anthropic API key
    ALEX_API_URL       — Alex Cloud Run URL (default: production)
    SMTP_HOST/PORT/USER/PASS — for email sending
    ALERT_TO           — recipient email(s)
"""
import os
import sys
import json
import asyncio
import logging
from datetime import datetime, date
from pathlib import Path

# Add parent to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-server"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import anthropic

# ── Config ───────────────────────────────────────────────────────────────────
ALEX_API_URL = os.environ.get("ALEX_API_URL", "https://insurance-broker-alex-603810013022.europe-west3.run.app")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f"orchestrator-{date.today().isoformat()}.log"),
    ]
)
log = logging.getLogger("alex-orchestrator")


# ── API Client ───────────────────────────────────────────────────────────────
import urllib.request
import urllib.error

def api_get(path: str, params: dict = None) -> dict:
    """Call Alex REST API."""
    url = f"{ALEX_API_URL}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.error(f"API error {e.code}: {url}")
        return {"error": str(e)}
    except Exception as e:
        log.error(f"API error: {e}")
        return {"error": str(e)}


# ── Claude Analysis ─────────────────────────────────────────────────────────
def claude_analyze(prompt: str, data: dict, max_tokens: int = 2000) -> str:
    """Send data to Claude for analysis/summarization."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\nData:\n```json\n{json.dumps(data, indent=2, default=str)}\n```"
        }],
        system="You are Alex, an insurance broker AI assistant. Be concise, actionable, and professional. Respond in Romanian when the data contains Romanian clients, German for German clients, English otherwise. IMPORTANT: Output raw HTML only — no markdown, no ```html``` code fences, no backticks. Start directly with <!DOCTYPE html> or <html> or the first HTML tag."
    )
    result = message.content[0].text
    # Strip markdown code fences if Claude wraps the output
    if result.startswith("```"):
        lines = result.split("\n")
        # Remove first line (```html) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        elif lines[0].startswith("```"):
            lines = lines[1:]
        result = "\n".join(lines)
    return result.strip()


# ── Email Sending ────────────────────────────────────────────────────────────
def send_email(to_list: list, subject: str, html: str) -> bool:
    """Send HTML email via SMTP."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_name = os.environ.get("SMTP_FROM_NAME", "Alex Insurance Broker")

    if not smtp_user or not smtp_pass:
        log.warning("SMTP not configured — printing to stdout")
        print(f"To: {', '.join(to_list)}")
        print(f"Subject: {subject}")
        print(f"Body length: {len(html)} chars")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.ehlo()
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, to_list, msg.as_string())
        log.info(f"Email sent to {', '.join(to_list)}")
        return True
    except Exception as e:
        log.error(f"Email error: {e}")
        return False


# ── Tasks ────────────────────────────────────────────────────────────────────

def task_renewals():
    """Check policy renewals and generate alert."""
    log.info("=== TASK: Renewal Check ===")

    data = api_get("/api/renewals", {"days": 45})
    if "error" in data:
        log.error(f"Failed to fetch renewals: {data['error']}")
        return

    urgent = data.get("urgent", [])
    upcoming = data.get("upcoming", [])
    total = data.get("total", 0)

    log.info(f"Found {len(urgent)} urgent, {len(upcoming)} upcoming, {total} total")

    if total == 0:
        log.info("No renewals due — skipping")
        return

    # Ask Claude to generate a prioritized action plan
    analysis = claude_analyze(
        "Analyze these upcoming insurance policy renewals. "
        "Prioritize by: 1) RCA policies (mandatory, fines if expired), "
        "2) Urgent (<7 days), 3) High premium value. "
        "For each, suggest: action needed, who to contact, urgency level. "
        "Format as a brief HTML email body with a table.",
        data
    )

    # Send alert
    alert_to = [e.strip() for e in os.environ.get("ALERT_TO", "").split(",") if e.strip()]
    if alert_to:
        today = date.today().strftime("%d.%m.%Y")
        subject = f"Alex Reinnoiri — {len(urgent)} urgente, {total} total / {today}"
        send_email(alert_to, subject, analysis)

    # Save report
    report_file = LOG_DIR / f"renewals-{date.today().isoformat()}.html"
    report_file.write_text(analysis, encoding="utf-8")
    log.info(f"Report saved: {report_file}")


def task_compliance():
    """Monthly compliance report generation (ASF + BaFin)."""
    log.info("=== TASK: Compliance Reports ===")

    today = date.today()
    month = today.month
    year = today.year

    # If it's the first few days of the month, report on previous month
    if today.day <= 5:
        month = month - 1 if month > 1 else 12
        year = year if month < 12 else year - 1

    asf = api_get("/api/reports/asf", {"month": month, "year": year})
    bafin = api_get("/api/reports/bafin", {"month": month, "year": year})

    # Ask Claude to summarize and highlight issues
    analysis = claude_analyze(
        f"Summarize these monthly compliance reports for {month}/{year}. "
        "Highlight: any regulatory issues, deadlines approaching, "
        "missing documentation, and recommended actions. "
        "Format as professional HTML report with ASF and BaFin sections.",
        {"asf_report": asf, "bafin_report": bafin, "month": month, "year": year}
    )

    # Save and optionally email
    report_file = LOG_DIR / f"compliance-{year}-{month:02d}.html"
    report_file.write_text(analysis, encoding="utf-8")
    log.info(f"Compliance report saved: {report_file}")

    alert_to = [e.strip() for e in os.environ.get("ALERT_TO", "").split(",") if e.strip()]
    if alert_to:
        send_email(alert_to, f"Alex Compliance Report — {month}/{year}", analysis)


def task_follow_up():
    """Check open claims and suggest follow-up actions."""
    log.info("=== TASK: Claims Follow-up ===")

    data = api_get("/api/claims/open", {"max_age_days": 90})
    if "error" in data:
        log.error(f"Failed to fetch claims: {data['error']}")
        return

    claims = data.get("claims", [])
    log.info(f"Found {len(claims)} open claims")

    if not claims:
        log.info("No open claims — skipping")
        return

    # Ask Claude to prioritize and suggest actions
    analysis = claude_analyze(
        "These insurance claims are open and need follow-up. "
        "For each claim: assess urgency based on days_open, "
        "suggest next action (call insurer, request documents, update client), "
        "flag any that are overdue (>14 days). "
        "Format as actionable HTML email with priority levels.",
        data
    )

    alert_to = [e.strip() for e in os.environ.get("ALERT_TO", "").split(",") if e.strip()]
    if alert_to:
        today = date.today().strftime("%d.%m.%Y")
        overdue = len([c for c in claims if c.get("days_open", 0) > 14])
        subject = f"Alex Claims Follow-up — {overdue} overdue, {len(claims)} total / {today}"
        send_email(alert_to, subject, analysis)

    report_file = LOG_DIR / f"claims-followup-{date.today().isoformat()}.html"
    report_file.write_text(analysis, encoding="utf-8")
    log.info(f"Claims report saved: {report_file}")


def task_morning_brief():
    """Generate comprehensive morning briefing for broker."""
    log.info("=== TASK: Morning Briefing ===")

    # Gather all data
    dashboard = api_get("/api/dashboard")
    renewals = api_get("/api/renewals", {"days": 7})
    claims = api_get("/api/claims/open", {"max_age_days": 30})

    # Ask Claude for executive summary
    brief = claude_analyze(
        "Generate a morning briefing for an insurance broker. "
        "Include: 1) Dashboard overview, 2) Today's urgent renewals, "
        "3) Open claims needing attention, 4) Recommended actions for today. "
        "Keep it concise (under 300 words). Format as HTML email. "
        "Start with a friendly greeting.",
        {
            "dashboard": dashboard,
            "urgent_renewals": renewals,
            "open_claims": claims,
            "date": date.today().isoformat()
        }
    )

    alert_to = [e.strip() for e in os.environ.get("ALERT_TO", "").split(",") if e.strip()]
    if alert_to:
        today = date.today().strftime("%d.%m.%Y")
        send_email(alert_to, f"☀️ Alex Morning Brief — {today}", brief)

    report_file = LOG_DIR / f"morning-brief-{date.today().isoformat()}.html"
    report_file.write_text(brief, encoding="utf-8")
    log.info(f"Morning brief saved: {report_file}")


def task_cross_sell():
    """Analyze all clients for cross-sell opportunities."""
    log.info("=== TASK: Cross-sell Analysis ===")

    # Get all clients
    clients_data = api_get("/api/clients/search", {"q": "%", "limit": 100})
    if "error" in clients_data:
        log.error(f"Failed to fetch clients: {clients_data['error']}")
        return

    dashboard = api_get("/api/dashboard")

    analysis = claude_analyze(
        "Analyze this insurance portfolio for cross-sell opportunities. "
        "Identify clients who: 1) Have RCA but no CASCO, "
        "2) Have motor insurance but no home insurance (PAD), "
        "3) Are companies without CMR/liability coverage, "
        "4) Have single-product relationships (opportunity for bundling). "
        "Generate a prioritized action list with estimated premium uplift. "
        "Format as HTML report with a table.",
        {"clients": clients_data, "dashboard": dashboard}
    )

    report_file = LOG_DIR / f"cross-sell-{date.today().isoformat()}.html"
    report_file.write_text(analysis, encoding="utf-8")
    log.info(f"Cross-sell report saved: {report_file}")


# ── Task Registry ────────────────────────────────────────────────────────────
TASKS = {
    "renewals": task_renewals,
    "compliance": task_compliance,
    "follow-up": task_follow_up,
    "morning-brief": task_morning_brief,
    "cross-sell": task_cross_sell,
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alex Agent SDK Orchestrator")
    parser.add_argument("--task", required=True, choices=list(TASKS.keys()) + ["all"],
                        help="Task to run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't send emails, just log")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    if args.dry_run:
        os.environ["SMTP_USER"] = ""  # Force stdout mode
        log.info("DRY RUN mode — no emails will be sent")

    log.info(f"Alex Orchestrator starting — task: {args.task}")
    log.info(f"API URL: {ALEX_API_URL}")
    log.info(f"Date: {datetime.now().isoformat()}")

    if args.task == "all":
        for name, func in TASKS.items():
            try:
                func()
            except Exception as e:
                log.error(f"Task {name} failed: {e}")
    else:
        try:
            TASKS[args.task]()
        except Exception as e:
            log.error(f"Task {args.task} failed: {e}")
            sys.exit(1)

    log.info("Orchestrator finished")


if __name__ == "__main__":
    main()
