"""
FastAPI entry point — clean architecture.
- Admin panel at /admin  (FastAPI router, Jinja2)
- Chainlit chat at /      (mount_chainlit)

CHAINLIT_ROOT_PATH must be "" so frontend JS gets correct rootPath (not null).
Run: uvicorn main:app --host 0.0.0.0 --port 8080
"""
import sys
import os
from pathlib import Path

# ── Path setup — must happen before any local imports ──────────────────────
BASE_DIR = Path(__file__).parent
MCP_SERVER_DIR = BASE_DIR / "mcp-server"
sys.path.insert(0, str(MCP_SERVER_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

# ── CRITICAL: set before ANY chainlit import ────────────────────────────────
# Without this, chainlit sends rootPath=null to the frontend → startsWith crash
os.environ["CHAINLIT_ROOT_PATH"] = ""

# Also unify API keys so google-genai SDK picks the right one
_api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
if _api_key:
    os.environ["GOOGLE_API_KEY"] = _api_key
    os.environ["GEMINI_API_KEY"] = _api_key

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from chainlit.utils import mount_chainlit

from shared.db import init_admin_tables
from admin.router import router as admin_router

init_admin_tables()

app = FastAPI(title="Alex Insurance Broker")

# ── Admin routes — BEFORE mount_chainlit ───────────────────────────────────
app.include_router(admin_router, prefix="/admin")

@app.get("/admin")
async def admin_redirect():
    return RedirectResponse("/admin/", status_code=302)

# ── Health check for Cloud Run ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

# ── API endpoints for n8n / external automation ─────────────────────────────
# These endpoints expose broker tools as REST API for workflow automation.
# n8n connects via HTTP Request nodes to trigger renewals, reports, etc.

from fastapi import Query
from fastapi.responses import JSONResponse
import json

from insurance_broker_mcp.tools.policy_tools import get_renewals_due_fn, list_policies_fn
from insurance_broker_mcp.tools.compliance_tools import asf_summary_fn, bafin_summary_fn
from insurance_broker_mcp.tools.claims_tools import get_claim_status_fn
from insurance_broker_mcp.tools.client_tools import search_clients_fn

@app.get("/api/renewals")
async def api_renewals(days: int = Query(default=45, ge=1, le=365)):
    """Get policies expiring within N days — structured JSON for n8n automation."""
    import sqlite3 as _sq3
    from datetime import date as _date, timedelta as _td
    from pathlib import Path as _Path
    _db = _Path(__file__).parent / "mcp-server" / "insurance_broker.db"
    try:
        _conn = _sq3.connect(str(_db))
        _conn.row_factory = _sq3.Row
        _today = _date.today().isoformat()
        _cutoff = (_date.today() + _td(days=days)).isoformat()
        _rows = _conn.execute("""
            SELECT p.id, p.client_id, c.name as client_name, c.email as client_email,
                   c.phone as client_phone,
                   p.policy_type, p.insurer, p.policy_number, p.end_date, p.annual_premium, p.currency,
                   CAST(julianday(p.end_date) - julianday('now') AS INTEGER) as days_left
            FROM policies p
            JOIN clients c ON c.id = p.client_id
            WHERE p.status = 'active' AND p.end_date BETWEEN ? AND ?
            ORDER BY p.end_date ASC
        """, (_today, _cutoff)).fetchall()
        _conn.close()
        _items = [dict(r) for r in _rows]
        return JSONResponse({
            "as_of": _today,
            "days_ahead": days,
            "total": len(_items),
            "urgent": [i for i in _items if i["days_left"] <= 7],
            "upcoming": [i for i in _items if i["days_left"] > 7],
            "all": _items,
        })
    except Exception as _ex:
        return JSONResponse({"error": str(_ex)}, status_code=500)

@app.get("/api/reports/asf")
async def api_asf_report(month: int = Query(..., ge=1, le=12), year: int = Query(..., ge=2020, le=2030)):
    """Generate ASF monthly report. Used by n8n cron on 1st of each month."""
    result = asf_summary_fn(month=month, year=year)
    return JSONResponse(content={"report": result})

@app.get("/api/reports/bafin")
async def api_bafin_report(month: int = Query(..., ge=1, le=12), year: int = Query(..., ge=2020, le=2030)):
    """Generate BaFin monthly report. Used by n8n cron on 1st of each month."""
    result = bafin_summary_fn(month=month, year=year)
    return JSONResponse(content={"report": result})

@app.get("/api/claims/open")
async def api_open_claims(max_age_days: int = Query(default=90, ge=1, le=365)):
    """Return open/investigating claims — useful for n8n follow-up automation."""
    import sqlite3 as _sq3
    from datetime import date as _date, timedelta as _td
    from pathlib import Path as _Path
    _db = _Path(__file__).parent / "mcp-server" / "insurance_broker.db"
    try:
        _conn = _sq3.connect(str(_db))
        _conn.row_factory = _sq3.Row
        _cutoff = (_date.today() - _td(days=max_age_days)).isoformat()
        _rows = _conn.execute("""
            SELECT cl.id, cl.client_id, c.name as client_name, c.email as client_email,
                   c.phone as client_phone,
                   cl.incident_date, cl.reported_date, cl.description, cl.status,
                   cl.damage_estimate, cl.insurer_claim_number,
                   CAST(julianday('now') - julianday(cl.reported_date) AS INTEGER) as days_open
            FROM claims cl
            JOIN clients c ON c.id = cl.client_id
            WHERE cl.status IN ('open', 'investigating') AND cl.reported_date >= ?
            ORDER BY cl.reported_date ASC
        """, (_cutoff,)).fetchall()
        _conn.close()
        _items = [dict(r) for r in _rows]
        return JSONResponse({"total": len(_items), "claims": _items})
    except Exception as _ex:
        return JSONResponse({"error": str(_ex)}, status_code=500)

@app.get("/api/dashboard")
async def api_dashboard():
    """Dashboard summary stats — active policies, clients, open claims, expiring soon."""
    import sqlite3 as _sq3
    from datetime import date as _date, timedelta as _td
    from pathlib import Path as _Path
    _db = _Path(__file__).parent / "mcp-server" / "insurance_broker.db"
    try:
        _conn = _sq3.connect(str(_db))
        _conn.row_factory = _sq3.Row
        _today = _date.today().isoformat()
        _7d    = (_date.today() + _td(days=7)).isoformat()
        _30d   = (_date.today() + _td(days=30)).isoformat()
        stats = {
            "active_policies": _conn.execute("SELECT COUNT(*) FROM policies WHERE status='active'").fetchone()[0],
            "clients":         _conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
            "open_claims":     _conn.execute("SELECT COUNT(*) FROM claims WHERE status IN ('open','investigating')").fetchone()[0],
            "expiring_7":      _conn.execute("SELECT COUNT(*) FROM policies WHERE status='active' AND end_date BETWEEN ? AND ?", (_today, _7d)).fetchone()[0],
            "expiring_30":     _conn.execute("SELECT COUNT(*) FROM policies WHERE status='active' AND end_date BETWEEN ? AND ?", (_today, _30d)).fetchone()[0],
            "offers_total":    _conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0],
        }
        _conn.close()
        return JSONResponse(stats)
    except Exception as _ex:
        return JSONResponse({"error": str(_ex)}, status_code=500)

@app.get("/api/claims/overdue")
async def api_overdue_claims(days: int = Query(default=14, ge=1, le=180)):
    """Deprecated — use /api/claims/open instead."""
    return JSONResponse({"deprecated": True, "use_instead": "/api/claims/open"})

@app.get("/api/clients/search")
async def api_search_clients(q: str = Query(..., min_length=1), limit: int = Query(default=20, ge=1, le=100)):
    """Search clients. Used by n8n for client lookup in workflows."""
    result = search_clients_fn(query=q, limit=limit)
    return JSONResponse(content={"clients": json.loads(result) if result.startswith("[") else result})

# ── Computer Use REST API ────────────────────────────────────────────────────
# Local agents (running on employee computers) poll these endpoints.
# In-memory queues — survives for the lifetime of this process.
import uuid as _uuid
import asyncio as _asyncio
from datetime import datetime as _dt
from collections import defaultdict as _defaultdict
from fastapi import Request as _Request
from typing import Optional as _Opt

from cu_state import _cu_tasks, _cu_results, _cu_agents, _cu_pending


@app.get("/cu/tasks")
async def cu_get_tasks(request: _Request):
    """Local agent polls this for pending tasks. Uses /cu/ prefix to avoid Chainlit /api/ conflict."""
    agent_id = request.headers.get("X-Agent-ID", "default")
    pending_ids = _cu_pending.get(agent_id, [])
    tasks = []
    remaining = []
    for tid in pending_ids:
        task = _cu_tasks.get(tid)
        if task and task.get("status") == "pending":
            task["status"] = "dispatched"
            tasks.append(task)
        else:
            remaining.append(tid)
    _cu_pending[agent_id] = remaining
    if agent_id in _cu_agents:
        _cu_agents[agent_id]["last_seen"] = _dt.utcnow().isoformat()
    return JSONResponse({"tasks": tasks, "agent_id": agent_id})


@app.post("/cu/results")
async def cu_post_result(request: _Request):
    """Local agent posts task results here."""
    try:
        body = await request.json()
        task_id = body.get("task_id")
        if not task_id:
            return JSONResponse({"error": "task_id required"}, status_code=400)
        _cu_results[task_id] = {
            "result": body.get("result", {}),
            "agent_id": body.get("agent_id"),
            "completed_at": body.get("completed_at", _dt.utcnow().isoformat()),
        }
        if task_id in _cu_tasks:
            _cu_tasks[task_id]["status"] = "completed"
        return JSONResponse({"ok": True, "task_id": task_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/cu/heartbeat")
async def cu_heartbeat(request: _Request):
    """Local agent sends heartbeat to show it's online."""
    try:
        body = await request.json()
        agent_id = body.get("agent_id", "unknown")
        _cu_agents[agent_id] = {
            "agent_id": agent_id,
            "platform": body.get("platform", ""),
            "connectors": body.get("connectors", []),
            "last_seen": _dt.utcnow().isoformat(),
            "python": body.get("python", ""),
        }
        return JSONResponse({"ok": True, "agent_id": agent_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/cu/enqueue")
async def cu_enqueue(request: _Request):
    """app.py enqueues a task here (inter-process: app.py subprocess → main.py process)."""
    try:
        body = await request.json()
        task = body.get("task", {})
        agent_id = body.get("agent_id", "default")
        task_id = task.get("task_id")
        if not task_id:
            return JSONResponse({"error": "task_id required"}, status_code=400)
        _cu_tasks[task_id] = task
        _cu_pending[agent_id].append(task_id)
        return JSONResponse({"ok": True, "task_id": task_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/cu/result/{task_id}")
async def cu_get_result(task_id: str):
    """app.py polls here to check if a task result is ready."""
    if task_id in _cu_results:
        return JSONResponse({"ready": True, "result": _cu_results[task_id].get("result", {})})
    return JSONResponse({"ready": False})


@app.get("/cu/status")
async def cu_status():
    """Returns all online agents and their capabilities."""
    online = []
    for agent_id, info in _cu_agents.items():
        try:
            last = _dt.fromisoformat(info["last_seen"])
            delta = (_dt.utcnow() - last).total_seconds()
            if delta < 120:
                online.append({**info, "online": True, "seconds_ago": round(delta)})
        except Exception:
            pass
    return JSONResponse({
        "agents_online": len(online),
        "agents": online,
        "total_tasks": len(_cu_tasks),
    })


# Expose shared state to app.py tools via module-level refs
# app.py imports these via: from main import _cu_tasks, _cu_results, _cu_agents, _cu_pending
# (only works when running via uvicorn main:app — which is how Cloud Run works)


# ── Debug endpoint — test Playwright directly ───────────────────────────────
@app.get("/cu/test-playwright")
async def cu_test_playwright():
    """Quick smoke-test: can Playwright launch Chromium and load a page?"""
    import asyncio as _aio
    import os
    try:
        from playwright.async_api import async_playwright as _apw
        async def _run():
            async with _apw() as pw:
                chromium_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
                kwargs = dict(headless=True, args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu","--single-process"])
                if chromium_path and os.path.exists(chromium_path):
                    kwargs["executable_path"] = chromium_path
                browser = await pw.chromium.launch(**kwargs)
                page = await browser.new_page()
                await page.goto("https://example.com", wait_until="domcontentloaded", timeout=15000)
                title = await page.title()
                await browser.close()
                return {"ok": True, "page_title": title, "chromium": chromium_path or "playwright-bundled"}
        result = await _aio.wait_for(_run(), timeout=30)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "type": type(e).__name__}, status_code=500)


@app.get("/cu/test-rca")
async def cu_test_rca(plate: str = "B123ABC"):
    """Test RCA check directly via Playwright — bypasses Gemini/Alex."""
    import sys, json as _json
    sys.path.insert(0, "/app/mcp-server")
    try:
        from insurance_broker_mcp.tools.web_tools import _check_rca_async
        import asyncio as _aio
        result = await _aio.wait_for(_check_rca_async(plate), timeout=55)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "type": type(e).__name__}, status_code=500)


@app.get("/cu/debug-localhost")
async def cu_debug_localhost():
    """Test if app.py subprocess can reach main.py via localhost."""
    import requests as _r
    import asyncio as _a
    port = os.environ.get("PORT", "8080")
    results = {}

    def _check(path):
        try:
            resp = _r.get(f"http://localhost:{port}{path}", timeout=3)
            return {"status": resp.status_code, "ok": resp.status_code < 400, "body": resp.text[:100]}
        except Exception as e:
            return {"error": str(e)}

    loop = _a.get_event_loop()
    for path in ["/health", "/cu/status"]:
        results[path] = await loop.run_in_executor(None, lambda p=path: _check(p))

    return JSONResponse({"port": port, "pid": os.getpid(), "results": results})


# ══════════════════════════════════════════════════════════════════════════════
# APPROVAL DASHBOARD — Web UI for broker to review/approve/reject items
# ══════════════════════════════════════════════════════════════════════════════

from fastapi.responses import HTMLResponse, Response
from fastapi import Body
import sqlite3 as _sqlite3

_DB_PATH = str(BASE_DIR / "mcp-server" / "insurance_broker.db")

def _approval_db():
    conn = _sqlite3.connect(_DB_PATH)
    conn.row_factory = _sqlite3.Row
    return conn


@app.get("/api/approvals/stats")
async def api_approval_stats():
    """Get approval queue statistics."""
    conn = _approval_db()
    stats = {}
    for status in ["pending", "sent", "rejected", "expired"]:
        row = conn.execute("SELECT COUNT(*) as cnt FROM approval_queue WHERE status = ?", (status,)).fetchone()
        stats[status] = row["cnt"]
    conn.close()
    return stats


@app.get("/api/approvals")
async def api_list_approvals(status: str = Query(default="pending"), limit: int = Query(default=50)):
    """List approval queue items. Filter by status. Use status='all' for everything."""
    conn = _approval_db()
    if status == "all":
        rows = conn.execute(
            "SELECT * FROM approval_queue ORDER BY "
            "CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, "
            "created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM approval_queue WHERE status = ? ORDER BY "
            "CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, "
            "created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/approvals/{approval_id}")
async def api_get_approval(approval_id: str):
    """Get details of a single approval item."""
    conn = _approval_db()
    row = conn.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return dict(row)


@app.post("/api/approvals/{approval_id}/approve")
async def api_approve_item(approval_id: str):
    """Approve an item and send the email to the client."""
    conn = _approval_db()
    row = conn.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Not found"}, status_code=404)
    if row["status"] != "pending":
        conn.close()
        return JSONResponse({"error": f"Item is {row['status']}, not pending"}, status_code=400)

    # Send email
    email_sent = False
    tracking_id = None
    recipient = row["client_email"]
    if recipient:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASS", "")
            smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            from_name = os.environ.get("SMTP_FROM_NAME", "Alex Broker")

            # Create tracking record
            tracking_id = f"TRK-{os.urandom(4).hex().upper()}"
            conn.execute(
                "INSERT INTO email_tracking (id, approval_id, client_id, recipient, sent_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (tracking_id, approval_id, row["client_id"], recipient),
            )

            # Add tracking pixel + response buttons to email body
            base_url = os.environ.get("ALEX_API_URL", "https://insurance-broker-alex-elo6xae6nq-ey.a.run.app")
            body_html = row["email_body_html"] or ""
            tracking_footer = f"""
            <br/><hr style="border:1px solid #eee; margin:20px 0"/>
            <div style="text-align:center; font-family:sans-serif;">
                <p style="color:#666; font-size:13px;">Sunteti interesat de aceasta oferta?</p>
                <a href="{base_url}/api/respond/{tracking_id}/accept"
                   style="display:inline-block; padding:10px 25px; background:#28a745; color:white;
                          text-decoration:none; border-radius:5px; margin:5px; font-weight:bold;">
                    Da, sunt interesat
                </a>
                <a href="{base_url}/api/respond/{tracking_id}/reject"
                   style="display:inline-block; padding:10px 25px; background:#dc3545; color:white;
                          text-decoration:none; border-radius:5px; margin:5px; font-weight:bold;">
                    Nu, multumesc
                </a>
            </div>
            <img src="{base_url}/api/track/open/{tracking_id}" width="1" height="1" style="display:none"/>
            """
            full_body = body_html + tracking_footer

            if smtp_user and smtp_pass:
                msg = MIMEMultipart("alternative")
                msg["From"] = f"{from_name} <{smtp_user}>"
                msg["To"] = recipient
                msg["Subject"] = row["subject"] or "Oferta de asigurare"
                msg.attach(MIMEText(full_body, "html", "utf-8"))

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
                email_sent = True
            else:
                # Dry run — just log
                email_sent = True  # Consider it "sent" for status update
        except Exception as e:
            return JSONResponse({"error": f"Email failed: {e}"}, status_code=500)

    # Update status
    conn.execute(
        "UPDATE approval_queue SET status = 'sent', approved_at = datetime('now'), "
        "sent_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (approval_id,),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "email_sent": email_sent, "tracking_id": tracking_id,
            "recipient": recipient}


@app.post("/api/approvals/{approval_id}/reject")
async def api_reject_item(approval_id: str, reason: str = Body(default="", embed=True)):
    """Reject an approval item."""
    conn = _approval_db()
    conn.execute(
        "UPDATE approval_queue SET status = 'rejected', rejected_reason = ?, "
        "updated_at = datetime('now') WHERE id = ? AND status = 'pending'",
        (reason, approval_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.put("/api/approvals/{approval_id}/edit")
async def api_edit_approval(approval_id: str, subject: str = Body(default=None),
                             email_body_html: str = Body(default=None)):
    """Edit email subject and/or body before approving."""
    conn = _approval_db()
    if subject is not None:
        conn.execute("UPDATE approval_queue SET subject = ?, updated_at = datetime('now') WHERE id = ?",
                     (subject, approval_id))
    if email_body_html is not None:
        conn.execute("UPDATE approval_queue SET email_body_html = ?, updated_at = datetime('now') WHERE id = ?",
                     (email_body_html, approval_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Email tracking & client response endpoints ──────────────────────────────

@app.get("/api/track/open/{tracking_id}")
async def track_email_open(tracking_id: str):
    """1x1 tracking pixel — records email open."""
    conn = _approval_db()
    conn.execute(
        "UPDATE email_tracking SET open_count = open_count + 1, "
        "opened_at = COALESCE(opened_at, datetime('now')) WHERE id = ?",
        (tracking_id,),
    )
    conn.commit()
    conn.close()
    # Return 1x1 transparent GIF
    gif_bytes = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return Response(content=gif_bytes, media_type="image/gif")


@app.get("/api/respond/{tracking_id}/{response}")
async def client_respond(tracking_id: str, response: str):
    """Client clicks accept/reject link in email."""
    if response not in ("accept", "reject"):
        return HTMLResponse("<h2>Link invalid</h2>", status_code=400)

    conn = _approval_db()
    # Update tracking
    conn.execute(
        "UPDATE email_tracking SET responded = ?, responded_at = datetime('now') WHERE id = ?",
        (response + "ed", tracking_id),  # "accepted" / "rejected"
    )

    # Find related approval and update offer status
    tracking_row = conn.execute("SELECT * FROM email_tracking WHERE id = ?", (tracking_id,)).fetchone()
    if tracking_row and tracking_row["approval_id"]:
        approval_id = tracking_row["approval_id"]
        if response == "accept":
            conn.execute(
                "UPDATE approval_queue SET status = 'accepted', updated_at = datetime('now') WHERE id = ?",
                (approval_id,),
            )
        # Update offer if exists
        approval_row = conn.execute("SELECT offer_id FROM approval_queue WHERE id = ?", (approval_id,)).fetchone()
        if approval_row and approval_row["offer_id"]:
            conn.execute(
                "UPDATE offers SET client_response = ?, client_response_at = datetime('now') WHERE id = ?",
                (response + "ed", approval_row["offer_id"]),
            )

    conn.commit()
    conn.close()

    # HTML response page
    if response == "accept":
        html = """<!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;
        min-height:100vh;margin:0;background:#f0f8f0;}
        .card{background:white;padding:40px;border-radius:10px;text-align:center;box-shadow:0 2px 20px rgba(0,0,0,0.1);}
        h1{color:#28a745;}</style></head><body>
        <div class="card"><h1>Multumim!</h1>
        <p>Am primit raspunsul dumneavoastra. Va vom contacta in curand cu detalii.</p>
        <p style="color:#666;">Alex - Broker de Asigurari</p></div></body></html>"""
    else:
        html = """<!DOCTYPE html><html><head><meta charset="UTF-8">
        <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;
        min-height:100vh;margin:0;background:#f8f8f8;}
        .card{background:white;padding:40px;border-radius:10px;text-align:center;box-shadow:0 2px 20px rgba(0,0,0,0.1);}
        h1{color:#666;}</style></head><body>
        <div class="card"><h1>Intelegem</h1>
        <p>Multumim pentru raspuns. Daca va razganditi, nu ezitati sa ne contactati.</p>
        <p style="color:#666;">Alex - Broker de Asigurari</p></div></body></html>"""

    return HTMLResponse(html)


# ── Approval Dashboard HTML ─────────────────────────────────────────────────

@app.get("/dashboard/approvals", response_class=HTMLResponse)
async def dashboard_approvals():
    """Web dashboard for broker to review and approve queued items."""
    return HTMLResponse(_APPROVAL_DASHBOARD_HTML)


_APPROVAL_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alex — Aprobari</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }
        .header { background: linear-gradient(135deg, #2c3e50, #3498db); color: white;
                   padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.5em; font-weight: 300; }
        .badge { background: #e74c3c; color: white; border-radius: 20px; padding: 4px 12px;
                 font-size: 0.9em; font-weight: bold; }
        .filters { padding: 15px 30px; background: white; border-bottom: 1px solid #e9ecef;
                    display: flex; gap: 10px; flex-wrap: wrap; }
        .filter-btn { padding: 6px 16px; border: 2px solid #ddd; background: white; border-radius: 20px;
                      cursor: pointer; font-size: 0.9em; transition: all 0.2s; }
        .filter-btn.active { border-color: #3498db; background: #e3f2fd; color: #1976d2; font-weight: 600; }
        .filter-btn:hover { border-color: #3498db; }
        .container { max-width: 1200px; margin: 20px auto; padding: 0 20px; }
        .cards { display: grid; gap: 15px; }
        .card { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                overflow: hidden; border-left: 5px solid #ccc; }
        .card.urgent { border-left-color: #e74c3c; }
        .card.high { border-left-color: #f39c12; }
        .card.medium { border-left-color: #3498db; }
        .card.low { border-left-color: #95a5a6; }
        .card-header { padding: 15px 20px; display: flex; justify-content: space-between;
                       align-items: center; cursor: pointer; }
        .card-header:hover { background: #f8f9fa; }
        .card-meta { display: flex; gap: 10px; align-items: center; }
        .type-tag { padding: 3px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }
        .type-tag.renewal { background: #fff3cd; color: #856404; }
        .type-tag.cross_sell { background: #d4edda; color: #155724; }
        .type-tag.claim_followup { background: #cce5ff; color: #004085; }
        .type-tag.follow_up { background: #e2e3e5; color: #383d41; }
        .priority-dot { width: 10px; height: 10px; border-radius: 50%; }
        .priority-dot.urgent { background: #e74c3c; }
        .priority-dot.high { background: #f39c12; }
        .priority-dot.medium { background: #3498db; }
        .priority-dot.low { background: #95a5a6; }
        .card-body { padding: 0 20px 20px; display: none; }
        .card-body.open { display: block; }
        .email-preview { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 5px;
                         padding: 15px; margin: 10px 0; max-height: 300px; overflow-y: auto; }
        .subject-input { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 5px;
                         font-size: 1em; margin: 5px 0; }
        .actions { display: flex; gap: 10px; margin-top: 15px; }
        .btn { padding: 8px 20px; border: none; border-radius: 5px; cursor: pointer;
               font-size: 0.95em; font-weight: 600; transition: all 0.2s; }
        .btn-approve { background: #28a745; color: white; }
        .btn-approve:hover { background: #218838; }
        .btn-reject { background: #dc3545; color: white; }
        .btn-reject:hover { background: #c82333; }
        .btn-edit { background: #ffc107; color: #333; }
        .btn-edit:hover { background: #e0a800; }
        .empty { text-align: center; padding: 60px; color: #999; }
        .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 24px; border-radius: 8px;
                 color: white; font-weight: 600; z-index: 999; display: none; }
        .toast.success { background: #28a745; }
        .toast.error { background: #dc3545; }
        .client-info { color: #666; font-size: 0.9em; }
        .date-info { color: #999; font-size: 0.8em; }
        .stats-bar { display: flex; gap: 20px; padding: 15px 30px; background: #f8f9fa; }
        .stat { text-align: center; }
        .stat-num { font-size: 1.5em; font-weight: bold; color: #2c3e50; }
        .stat-label { font-size: 0.8em; color: #666; }
        .editing textarea { width: 100%; min-height: 200px; font-family: monospace; font-size: 0.9em;
                            padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Alex — Dashboard Aprobari</h1>
        <span class="badge" id="pending-count">...</span>
    </div>
    <div class="stats-bar" id="stats-bar"></div>
    <div class="filters">
        <button class="filter-btn active" data-status="pending" onclick="filterBy('pending', this)">De aprobat</button>
        <button class="filter-btn" data-status="sent" onclick="filterBy('sent', this)">Trimise</button>
        <button class="filter-btn" data-status="rejected" onclick="filterBy('rejected', this)">Respinse</button>
        <button class="filter-btn" data-status="all" onclick="filterBy('all', this)">Toate</button>
    </div>
    <div class="container">
        <div class="cards" id="cards"></div>
    </div>
    <div class="toast" id="toast"></div>

    <script>
    let currentStatus = 'pending';

    async function loadStats() {
        const r = await fetch('/api/approvals/stats');
        const stats = await r.json();
        document.getElementById('pending-count').textContent = stats.pending || 0;
        document.getElementById('stats-bar').innerHTML =
            `<div class="stat"><div class="stat-num">${stats.pending||0}</div><div class="stat-label">De aprobat</div></div>
             <div class="stat"><div class="stat-num">${stats.sent||0}</div><div class="stat-label">Trimise</div></div>
             <div class="stat"><div class="stat-num">${stats.rejected||0}</div><div class="stat-label">Respinse</div></div>`;
        document.title = stats.pending > 0 ? `Aprobari (${stats.pending})` : 'Alex — Aprobari';
    }

    async function loadItems(status) {
        const url = `/api/approvals?status=${status}&limit=100`;
        const r = await fetch(url);
        const items = await r.json();
        const container = document.getElementById('cards');

        if (items.length === 0) {
            container.innerHTML = '<div class="empty"><h2>Nimic aici</h2><p>Nu exista elemente cu acest status.</p></div>';
            return;
        }

        container.innerHTML = items.map(item => `
            <div class="card ${item.priority}" id="card-${item.id}">
                <div class="card-header" onclick="toggleCard('${item.id}')">
                    <div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="priority-dot ${item.priority}"></span>
                            <strong>${item.client_name || 'Client'}</strong>
                            <span class="type-tag ${item.type}">${item.type.replace('_',' ')}</span>
                        </div>
                        <div class="client-info">${item.subject || ''}</div>
                    </div>
                    <div style="text-align:right;">
                        <div class="client-info">${item.client_email || 'fara email'}</div>
                        <div class="date-info">${item.created_at || ''}</div>
                    </div>
                </div>
                <div class="card-body" id="body-${item.id}">
                    <label><strong>Subiect:</strong></label>
                    <input class="subject-input" id="subj-${item.id}" value="${(item.subject||'').replace(/"/g,'&quot;')}" />
                    <label><strong>Email preview:</strong></label>
                    <div class="email-preview" id="preview-${item.id}">${item.email_body_html || '<em>Fara continut</em>'}</div>
                    <div id="edit-area-${item.id}"></div>
                    ${item.status === 'pending' ? `
                    <div class="actions">
                        <button class="btn btn-approve" onclick="approveItem('${item.id}')">Aproba si Trimite</button>
                        <button class="btn btn-reject" onclick="rejectItem('${item.id}')">Respinge</button>
                        <button class="btn btn-edit" onclick="editItem('${item.id}')">Editeaza</button>
                    </div>` : `<div class="client-info" style="margin-top:10px;">Status: ${item.status}</div>`}
                </div>
            </div>
        `).join('');
    }

    function toggleCard(id) {
        document.getElementById('body-' + id).classList.toggle('open');
    }

    function filterBy(status, btn) {
        currentStatus = status;
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        loadItems(status);
    }

    function showToast(msg, type) {
        const t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast ' + type;
        t.style.display = 'block';
        setTimeout(() => t.style.display = 'none', 3000);
    }

    async function approveItem(id) {
        // Save any edits first
        const subj = document.getElementById('subj-' + id).value;
        await fetch(`/api/approvals/${id}/edit`, {
            method: 'PUT', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({subject: subj})
        });

        const r = await fetch(`/api/approvals/${id}/approve`, {method:'POST'});
        const data = await r.json();
        if (data.ok) {
            showToast('Email trimis cu succes!', 'success');
            document.getElementById('card-' + id).style.opacity = '0.5';
            loadStats();
        } else {
            showToast('Eroare: ' + (data.error||'necunoscuta'), 'error');
        }
    }

    async function rejectItem(id) {
        const reason = prompt('Motiv respingere (optional):');
        if (reason === null) return;
        await fetch(`/api/approvals/${id}/reject`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({reason: reason})
        });
        showToast('Respins', 'success');
        document.getElementById('card-' + id).style.opacity = '0.5';
        loadStats();
    }

    function editItem(id) {
        const area = document.getElementById('edit-area-' + id);
        const preview = document.getElementById('preview-' + id);
        if (area.innerHTML) { area.innerHTML = ''; return; }
        area.innerHTML = `<div class="editing">
            <label><strong>Editeaza HTML-ul emailului:</strong></label>
            <textarea id="html-edit-${id}">${preview.innerHTML}</textarea>
            <button class="btn btn-edit" style="margin-top:8px" onclick="saveEdit('${id}')">Salveaza</button>
        </div>`;
    }

    async function saveEdit(id) {
        const html = document.getElementById('html-edit-' + id).value;
        const subj = document.getElementById('subj-' + id).value;
        await fetch(`/api/approvals/${id}/edit`, {
            method: 'PUT', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({subject: subj, email_body_html: html})
        });
        document.getElementById('preview-' + id).innerHTML = html;
        document.getElementById('edit-area-' + id).innerHTML = '';
        showToast('Salvat!', 'success');
    }

    // Auto-refresh every 30s
    setInterval(() => { loadStats(); loadItems(currentStatus); }, 30000);
    loadStats();
    loadItems('pending');
    </script>
</body>
</html>"""


# ── Chainlit at root — MUST be last ────────────────────────────────────────
mount_chainlit(app=app, target="app.py", path="/")
