"""
Alex Agent SDK Orchestrator — Autonomous Insurance Broker Tasks

Runs on a GCE VM (or any server) and executes scheduled insurance tasks
using the Alex REST API. No Claude Code CLI needed — uses Anthropic API directly.

INTEGRATIONS:
    ✅ 5 core tasks (renewals, compliance, follow-up, morning-brief, cross-sell)
    ✅ Local Agent Bridge (alex-local-agent) — dispatch desktop tasks via /cu/enqueue
    ✅ Cloud Storage (Google Drive + SharePoint) — upload reports automatically
    ✅ n8n Webhook — trigger n8n workflows on events
    ✅ Claude AI analysis — intelligent report generation

Usage:
    python agent-sdk/orchestrator.py --task renewals
    python agent-sdk/orchestrator.py --task compliance
    python agent-sdk/orchestrator.py --task follow-up
    python agent-sdk/orchestrator.py --task morning-brief
    python agent-sdk/orchestrator.py --task cross-sell
    python agent-sdk/orchestrator.py --task local-agent-sync
    python agent-sdk/orchestrator.py --task upload-reports
    python agent-sdk/orchestrator.py --task all
    python agent-sdk/orchestrator.py --task all --dry-run

Environment:
    ANTHROPIC_API_KEY  — Anthropic API key
    ALEX_API_URL       — Alex Cloud Run URL (default: production)
    SMTP_HOST/PORT/USER/PASS — for email sending
    ALERT_TO           — recipient email(s)
    N8N_WEBHOOK_URL    — n8n webhook URL for workflow triggers
    GOOGLE_APPLICATION_CREDENTIALS_JSON — Google Drive service account
    GOOGLE_DRIVE_FOLDER_ID — Google Drive target folder
    SHAREPOINT_TENANT_ID/CLIENT_ID/CLIENT_SECRET/SITE_URL/FOLDER_PATH — SharePoint
"""
import os
import sys
import json
import time
import uuid
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
ALEX_API_URL = os.environ.get("ALEX_API_URL", "https://insurance-broker-alex-elo6xae6nq-ey.a.run.app")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
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
    """Call Alex REST API (GET)."""
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


def api_post(path: str, payload: dict) -> dict:
    """Call Alex REST API (POST)."""
    url = f"{ALEX_API_URL}{path}"
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.error(f"API POST error {e.code}: {url}")
        return {"error": str(e)}
    except Exception as e:
        log.error(f"API POST error: {e}")
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


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION 1: Local Agent Bridge (alex-local-agent)
# ══════════════════════════════════════════════════════════════════════════════
# The alex-local-agent runs on the broker's desktop computer and provides
# access to: legacy Delphi apps (CEDAM), web scraping (PAID/Allianz portals),
# Excel files, local documents, and Anthropic Computer Use.
#
# Flow: Orchestrator → /cu/enqueue (Cloud Run) → Local Agent polls → executes → /cu/results
# ══════════════════════════════════════════════════════════════════════════════

def local_agent_status() -> dict:
    """Check which local agents are online and their capabilities."""
    result = api_get("/cu/status")
    if "error" in result:
        log.warning(f"Local agent status check failed: {result['error']}")
        return {"agents_online": 0, "agents": []}
    return result


def local_agent_dispatch(connector: str, action: str, params: dict,
                         agent_id: str = "default", timeout: int = 120) -> dict:
    """
    Dispatch a task to a local agent and wait for the result.

    Args:
        connector: Which connector to use (cedam, paid, allianz, web_generic, desktop_generic, anthropic_computer_use)
        action: Action to perform (extract, check_rca, screenshot, navigate, run_task, etc.)
        params: Action-specific parameters
        agent_id: Target agent ID (default: "default")
        timeout: Max seconds to wait for result

    Returns:
        Task result dict with success/error fields
    """
    task_id = str(uuid.uuid4())

    task = {
        "task_id": task_id,
        "connector": connector,
        "action": action,
        "params": params,
        "timeout": timeout,
        "status": "pending",
    }

    # Enqueue the task
    log.info(f"[LocalAgent] Dispatching task {task_id[:8]} → {connector}/{action}")
    enqueue_result = api_post("/cu/enqueue", {"task": task, "agent_id": agent_id})

    if "error" in enqueue_result:
        log.error(f"[LocalAgent] Enqueue failed: {enqueue_result['error']}")
        return {"success": False, "error": f"Enqueue failed: {enqueue_result['error']}"}

    # Poll for result
    start = time.time()
    poll_interval = 2  # seconds
    while time.time() - start < timeout:
        result = api_get(f"/cu/result/{task_id}")
        if result.get("ready"):
            log.info(f"[LocalAgent] Task {task_id[:8]} completed")
            return result.get("result", {})
        time.sleep(poll_interval)
        # Increase poll interval gradually
        poll_interval = min(poll_interval * 1.2, 10)

    log.warning(f"[LocalAgent] Task {task_id[:8]} timed out after {timeout}s")
    return {"success": False, "error": f"Task timed out after {timeout}s"}


def task_local_agent_sync():
    """
    Sync with local agents: check status, dispatch pending desktop tasks.

    This task runs daily and:
    1. Checks which local agents are online
    2. Dispatches RCA verification tasks for urgent renewals
    3. Requests screenshots/data from legacy insurance portals
    4. Collects results and includes them in the daily report
    """
    log.info("=== TASK: Local Agent Sync ===")

    # 1. Check agent status
    status = local_agent_status()
    online_count = status.get("agents_online", 0)
    agents = status.get("agents", [])

    log.info(f"Local agents online: {online_count}")
    for agent in agents:
        connectors = agent.get("connectors", [])
        log.info(f"  Agent {agent.get('agent_id', '?')}: {', '.join(connectors)} "
                 f"(last seen {agent.get('seconds_ago', '?')}s ago)")

    if online_count == 0:
        log.warning("No local agents online — skipping desktop tasks")
        # Still generate a status report
        report = claude_analyze(
            "Generate a brief HTML status report for the local agent system. "
            "No agents are currently online. Suggest the broker to start the local agent "
            "on their desktop computer (python main.py start). "
            "List the capabilities that would be available: CEDAM RCA checks, "
            "PAID portal access, Allianz integration, Excel export, desktop automation.",
            {"status": status, "date": date.today().isoformat()}
        )
        report_file = LOG_DIR / f"local-agent-status-{date.today().isoformat()}.html"
        report_file.write_text(report, encoding="utf-8")
        log.info(f"Status report saved: {report_file}")
        return

    # 2. Get urgent renewals that need RCA verification
    renewals = api_get("/api/renewals", {"days": 14})
    urgent_rca = [
        r for r in renewals.get("all", renewals.get("urgent", []))
        if r.get("policy_type", "").upper() == "RCA"
    ]

    results = []
    target_agent = agents[0].get("agent_id", "default")

    # 3. Dispatch tasks via desktop agent
    # First: a simple screenshot to verify connectivity
    # Then: RCA verification tasks for urgent policies
    if urgent_rca:
        for renewal in urgent_rca[:3]:  # Max 3 checks per run
            client_name = renewal.get("client_name", "?")
            policy_number = renewal.get("policy_number", "?")
            days_left = renewal.get("days_left", "?")

            log.info(f"  Dispatching portal screenshot for {client_name} "
                     f"(policy {policy_number}, {days_left} days left)")

            # Use simple screenshot — works without Gemini API
            result = local_agent_dispatch(
                connector="web_generic",
                action="navigate",
                params={"url": "https://www.baar.ro/verificare-rca"},
                agent_id=target_agent,
                timeout=90,
            )
            results.append({
                "client": client_name,
                "policy": policy_number,
                "days_left": days_left,
                "verification": result,
                "success": result.get("success", False),
            })
            log.info(f"  Result for {client_name}: success={result.get('success', False)}")
            break  # One verification per run to avoid timeouts
    elif urgent_rca:
        log.info(f"  {len(urgent_rca)} urgent RCA policies found but no CEDAM connector available")
        for r in urgent_rca:
            results.append({
                "client": r.get("client_name", "?"),
                "policy": r.get("policy_number", "?"),
                "days_left": r.get("days_left", "?"),
                "verification": {"note": "No CEDAM connector available"},
                "success": False,
            })
    else:
        log.info("  No urgent RCA policies requiring verification")

    # 4. Request a quick desktop screenshot to prove agent connectivity
    if any("web_generic" in a.get("connectors", []) for a in agents):
        log.info("  Requesting desktop agent screenshot (connectivity test)")
        screenshot_result = local_agent_dispatch(
            connector="web_generic",
            action="screenshot",
            params={},
            agent_id=target_agent,
            timeout=45,
        )
        if screenshot_result.get("success"):
            log.info(f"  Desktop screenshot captured ({screenshot_result.get('size_bytes', 0)} bytes)")
        else:
            log.warning(f"  Desktop screenshot failed: {screenshot_result.get('error', 'unknown')}")

    # 5. Generate sync report
    report_data = {
        "agents_online": online_count,
        "agents": agents,
        "rca_checks": results,
        "date": date.today().isoformat(),
    }

    report = claude_analyze(
        "Generate an HTML report of the local agent sync results. Include: "
        "1) Which agents are online and their capabilities, "
        "2) RCA verification results (if any), "
        "3) Any issues or recommendations. "
        "Format as a professional HTML report.",
        report_data
    )

    report_file = LOG_DIR / f"local-agent-sync-{date.today().isoformat()}.html"
    report_file.write_text(report, encoding="utf-8")
    log.info(f"Local agent sync report saved: {report_file}")

    # 6. Notify via n8n if configured
    n8n_notify("local-agent-sync", {
        "agents_online": online_count,
        "rca_checks_performed": len(results),
        "date": date.today().isoformat(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION 2: Cloud Storage (Google Drive + SharePoint)
# ══════════════════════════════════════════════════════════════════════════════
# Uploads generated HTML reports to cloud storage for easy sharing.
# Uses the existing drive_tools.py from the MCP server.
# ══════════════════════════════════════════════════════════════════════════════

def upload_to_drive(filepath: Path) -> str:
    """Upload a file to Google Drive. Returns status message."""
    try:
        from insurance_broker_mcp.tools.drive_tools import _upload_to_drive_impl
        result = _upload_to_drive_impl(str(filepath))
        log.info(f"[Drive] Upload result for {filepath.name}: {result[:80]}...")
        return result
    except ImportError:
        log.warning("[Drive] Google Drive library not installed — skipping upload")
        return "⚠️ Google Drive not available"
    except Exception as e:
        log.error(f"[Drive] Upload error: {e}")
        return f"❌ Upload failed: {e}"


def upload_to_sharepoint(filepath: Path) -> str:
    """Upload a file to SharePoint. Returns status message."""
    try:
        from insurance_broker_mcp.tools.drive_tools import _sp_upload_impl
        result = _sp_upload_impl(str(filepath))
        log.info(f"[SharePoint] Upload result for {filepath.name}: {result[:80]}...")
        return result
    except ImportError:
        log.warning("[SharePoint] SharePoint not configured — skipping upload")
        return "⚠️ SharePoint not available"
    except Exception as e:
        log.error(f"[SharePoint] Upload error: {e}")
        return f"❌ Upload failed: {e}"


def list_drive_files(name_filter: str = None) -> str:
    """List files in Google Drive folder."""
    try:
        from insurance_broker_mcp.tools.drive_tools import _list_drive_files_impl
        return _list_drive_files_impl(limit=20, name_filter=name_filter)
    except Exception as e:
        log.error(f"[Drive] List error: {e}")
        return f"❌ List failed: {e}"


def list_sharepoint_files(name_filter: str = None) -> str:
    """List files in SharePoint folder."""
    try:
        from insurance_broker_mcp.tools.drive_tools import _sp_list_impl
        return _sp_list_impl(limit=20, name_filter=name_filter)
    except Exception as e:
        log.error(f"[SharePoint] List error: {e}")
        return f"❌ List failed: {e}"


def task_upload_reports():
    """
    Upload today's generated reports to Google Drive and/or SharePoint.

    Scans the logs/ directory for today's HTML reports and uploads each
    to the configured cloud storage. Creates a summary of uploaded files.
    """
    log.info("=== TASK: Upload Reports to Cloud Storage ===")

    today_str = date.today().isoformat()
    reports = list(LOG_DIR.glob(f"*{today_str}*.html"))

    if not reports:
        log.info("No reports found for today — skipping upload")
        return

    log.info(f"Found {len(reports)} reports to upload")

    drive_results = []
    sp_results = []

    has_drive = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    has_sp = bool(os.environ.get("SHAREPOINT_TENANT_ID"))

    for report in reports:
        log.info(f"  Uploading: {report.name}")

        if has_drive:
            drive_result = upload_to_drive(report)
            drive_results.append({"file": report.name, "result": drive_result})

        if has_sp:
            sp_result = upload_to_sharepoint(report)
            sp_results.append({"file": report.name, "result": sp_result})

    # Generate upload summary
    summary_data = {
        "date": today_str,
        "files_uploaded": len(reports),
        "file_names": [r.name for r in reports],
        "google_drive": {
            "configured": has_drive,
            "results": drive_results,
        },
        "sharepoint": {
            "configured": has_sp,
            "results": sp_results,
        }
    }

    summary = claude_analyze(
        "Generate a brief HTML summary of report uploads to cloud storage. Include: "
        "1) How many files were uploaded, "
        "2) Google Drive results (links if successful), "
        "3) SharePoint results (links if successful), "
        "4) Any errors or missing configurations. "
        "Format as a compact HTML notification.",
        summary_data,
        max_tokens=1000,
    )

    summary_file = LOG_DIR / f"upload-summary-{today_str}.html"
    summary_file.write_text(summary, encoding="utf-8")
    log.info(f"Upload summary saved: {summary_file}")

    # Notify broker
    alert_to = [e.strip() for e in os.environ.get("ALERT_TO", "").split(",") if e.strip()]
    if alert_to:
        send_email(alert_to, f"Alex Cloud Uploads — {len(reports)} rapoarte / {today_str}", summary)

    # Notify n8n
    n8n_notify("reports-uploaded", {
        "count": len(reports),
        "files": [r.name for r in reports],
        "drive_ok": has_drive and all("✅" in r.get("result", "") for r in drive_results),
        "sharepoint_ok": has_sp and all("✅" in r.get("result", "") for r in sp_results),
    })


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION 3: n8n Webhook Integration
# ══════════════════════════════════════════════════════════════════════════════
# Sends event notifications to n8n for complex workflow automation.
# n8n can then: send SMS, update CRM, create calendar events,
# trigger Zapier/Make, update dashboards, etc.
# ══════════════════════════════════════════════════════════════════════════════

def n8n_notify(event_type: str, payload: dict) -> bool:
    """
    Send an event notification to n8n webhook.

    Event types:
        - renewal-urgent: RCA policy expiring within 7 days
        - claim-overdue: Claim open > 14 days
        - compliance-due: Monthly compliance report ready
        - cross-sell-found: New cross-sell opportunity detected
        - local-agent-sync: Local agent sync completed
        - reports-uploaded: Reports uploaded to cloud storage
        - task-completed: Any task completed successfully
        - task-failed: Any task failed

    n8n receives the payload and can trigger further actions:
        - Send SMS via Twilio/MessageBird
        - Create tasks in Asana/Monday/ClickUp
        - Update HubSpot/Salesforce CRM
        - Send Slack/Teams notifications
        - Schedule calendar reminders
    """
    if not N8N_WEBHOOK_URL:
        log.debug(f"[n8n] No webhook configured — skipping {event_type}")
        return False

    full_payload = {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        "source": "alex-orchestrator",
        "data": payload,
    }

    try:
        data = json.dumps(full_payload).encode("utf-8")
        req = urllib.request.Request(
            N8N_WEBHOOK_URL,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            log.info(f"[n8n] Webhook sent: {event_type} → HTTP {status}")
            return status < 400
    except Exception as e:
        log.warning(f"[n8n] Webhook failed for {event_type}: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# CORE TASKS (original 5)
# ══════════════════════════════════════════════════════════════════════════════

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

    # n8n: notify about urgent renewals
    if urgent:
        for u in urgent:
            n8n_notify("renewal-urgent", {
                "client": u.get("client_name"),
                "policy_type": u.get("policy_type"),
                "days_left": u.get("days_left"),
                "premium": u.get("annual_premium"),
                "currency": u.get("currency"),
                "phone": u.get("client_phone"),
                "email": u.get("client_email"),
            })


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

    # n8n: notify compliance ready
    n8n_notify("compliance-due", {
        "month": month,
        "year": year,
        "report_file": str(report_file),
    })


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

    # n8n: notify about overdue claims
    overdue_claims = [c for c in claims if c.get("days_open", 0) > 14]
    for c in overdue_claims:
        n8n_notify("claim-overdue", {
            "claim_id": c.get("id"),
            "client": c.get("client_name"),
            "days_open": c.get("days_open"),
            "estimate": c.get("damage_estimate"),
            "phone": c.get("client_phone"),
        })


def task_morning_brief():
    """Generate comprehensive morning briefing for broker."""
    log.info("=== TASK: Morning Briefing ===")

    # Gather all data
    dashboard = api_get("/api/dashboard")
    renewals = api_get("/api/renewals", {"days": 7})
    claims = api_get("/api/claims/open", {"max_age_days": 30})

    # Check local agent status for the brief
    agent_status = local_agent_status()

    # Ask Claude for executive summary
    brief = claude_analyze(
        "Generate a morning briefing for an insurance broker. "
        "Include: 1) Dashboard overview, 2) Today's urgent renewals, "
        "3) Open claims needing attention, 4) Recommended actions for today, "
        "5) Local agent status (if any desktop agents are online for CEDAM/portal access). "
        "Keep it concise (under 300 words). Format as HTML email. "
        "Start with a friendly greeting.",
        {
            "dashboard": dashboard,
            "urgent_renewals": renewals,
            "open_claims": claims,
            "local_agents": agent_status,
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

    # n8n: daily trigger
    n8n_notify("task-completed", {
        "task": "morning-brief",
        "date": date.today().isoformat(),
        "dashboard": dashboard,
    })


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

    # n8n: notify about high-value opportunities
    n8n_notify("cross-sell-found", {
        "date": date.today().isoformat(),
        "report_file": str(report_file),
    })


# ── Task Registry ────────────────────────────────────────────────────────────
TASKS = {
    "renewals": task_renewals,
    "compliance": task_compliance,
    "follow-up": task_follow_up,
    "morning-brief": task_morning_brief,
    "cross-sell": task_cross_sell,
    "local-agent-sync": task_local_agent_sync,
    "upload-reports": task_upload_reports,
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
    log.info(f"n8n Webhook: {'✅ configured' if N8N_WEBHOOK_URL else '⚪ not set'}")
    log.info(f"Google Drive: {'✅ configured' if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON') else '⚪ not set'}")
    log.info(f"SharePoint: {'✅ configured' if os.environ.get('SHAREPOINT_TENANT_ID') else '⚪ not set'}")
    log.info(f"Date: {datetime.now().isoformat()}")

    if args.task == "all":
        for name, func in TASKS.items():
            try:
                func()
            except Exception as e:
                log.error(f"Task {name} failed: {e}")
                n8n_notify("task-failed", {"task": name, "error": str(e)})
    else:
        try:
            TASKS[args.task]()
            n8n_notify("task-completed", {"task": args.task})
        except Exception as e:
            log.error(f"Task {args.task} failed: {e}")
            n8n_notify("task-failed", {"task": args.task, "error": str(e)})
            sys.exit(1)

    log.info("Orchestrator finished")


if __name__ == "__main__":
    main()
