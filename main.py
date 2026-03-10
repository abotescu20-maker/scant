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
load_dotenv(BASE_DIR / ".env")

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
    """Get policies expiring within N days. Used by n8n for renewal reminders."""
    result = get_renewals_due_fn(days_ahead=days)
    return JSONResponse(content={"renewals": json.loads(result) if result.startswith("[") else result})

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

@app.get("/api/claims/overdue")
async def api_overdue_claims(days: int = Query(default=14, ge=1, le=180)):
    """Get claims older than N days still open. Used by n8n for follow-up alerts."""
    # List all policies to find claims — reuses existing tool
    policies = list_policies_fn(status="active")
    return JSONResponse(content={"overdue_threshold_days": days, "data": policies})

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


# ── Chainlit at root — MUST be last ────────────────────────────────────────
mount_chainlit(app=app, target="app.py", path="/")
