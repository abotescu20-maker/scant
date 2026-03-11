"""
Insurance Broker AI Assistant — Chainlit UI
============================================
Chat interface for non-technical insurance broker employees.
Uses Anthropic Claude API (anthropic SDK).
Features: PDF/image upload (Claude Vision), email offers, export PDF/XLSX/DOCX
"""
import sys
import os
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv

import chainlit as cl
import anthropic
import base64

# ── Admin DB helpers (imported only if tables exist) ──────────────────────────
try:
    from shared.db import (
        get_user_by_email, get_user_tools, log_audit, record_token_usage,
        init_admin_tables,
        # Projects & persistent conversations
        create_project, list_projects,
        create_conversation, list_conversations,
        update_conversation_title,
        save_conversation_history, load_conversation_history,
        # Client-linked conversations
        set_conversation_client,
        list_clients_with_conversations,
        list_conversations_for_client,
        get_all_clients_for_picker,
    )
    from shared.auth import verify_password
    init_admin_tables()
    ADMIN_ENABLED = True
except Exception:
    ADMIN_ENABLED = False

# ── Session key constants ──────────────────────────────────────────────────────
_SK_HISTORY    = "history"
_SK_CONV_ID    = "conversation_id"
_SK_PROJECT_ID = "project_id"
_SK_CLIENT_ID  = "linked_client_id"   # client the conversation is about
_SK_TITLE_SET  = "title_set"
_SK_SAVE_NUDGE = "save_nudge_shown"   # show "save conversation" button only once per session

# ── Load .env ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

# ── Paths ──────────────────────────────────────────────────────────────────
MCP_SERVER_DIR = BASE_DIR / "mcp-server"
DB_PATH = MCP_SERVER_DIR / "insurance_broker.db"
OUTPUT_DIR = MCP_SERVER_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(MCP_SERVER_DIR))

# ── Import broker tools directly ────────────────────────────────────────────
from insurance_broker_mcp.tools.client_tools import search_clients_fn, get_client_fn, create_client_fn, update_client_fn, delete_client_fn
from insurance_broker_mcp.tools.policy_tools import get_renewals_due_fn, list_policies_fn
from insurance_broker_mcp.tools.product_tools import search_products_fn, compare_products_fn
from insurance_broker_mcp.tools.offer_tools import create_offer_fn, list_offers_fn
from insurance_broker_mcp.tools.claims_tools import log_claim_fn, get_claim_status_fn
from insurance_broker_mcp.tools.compliance_tools import asf_summary_fn, bafin_summary_fn, check_rca_validity_fn
from insurance_broker_mcp.tools.email_tools import send_offer_email_fn
from insurance_broker_mcp.tools.analytics_tools import cross_sell_fn
from insurance_broker_mcp.tools.calculator_tools import calculate_premium_fn
from insurance_broker_mcp.tools.compliance_check_tools import compliance_check_fn
from insurance_broker_mcp.tools.web_tools import check_rca_fn as _playwright_check_rca_fn, browse_web_fn as _playwright_browse_web_fn
from insurance_broker_mcp.tools.drive_tools import (
    upload_to_drive_fn, list_drive_files_fn, get_drive_link_fn,
    sp_upload_fn, sp_list_fn, sp_get_link_fn,
)
from insurance_broker_mcp.tools.rag_tools import (
    broker_search_knowledge_fn,
    broker_upload_document_fn,
    broker_analyze_document_fn,
    broker_kb_status_fn,
    broker_kb_reindex_fn,
)

# ── REST API endpoints for n8n / external automation ─────────────────────────
# Added on chainlit.server.app — only /api/* and /health paths, no Chainlit conflicts
try:
    from chainlit.server import app as _cl_app
    from fastapi import Query as _Query
    from fastapi.responses import JSONResponse as _JSONResponse

    @_cl_app.get("/health")
    async def _health():
        return _JSONResponse({"status": "ok"})

    @_cl_app.get("/api/renewals")
    async def _api_renewals(days: int = _Query(default=45, ge=1, le=365)):
        """Structured renewal list — useful for n8n automation.
        Returns JSON with urgent (≤7 days) and upcoming (≤days) lists.
        """
        import sqlite3 as _sqlite3
        from datetime import date as _date, timedelta as _td
        from pathlib import Path as _Path
        _db = _Path(__file__).parent / "mcp-server" / "insurance_broker.db"
        try:
            _conn = _sqlite3.connect(str(_db))
            _conn.row_factory = _sqlite3.Row
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
            return _JSONResponse({
                "as_of": _today,
                "days_ahead": days,
                "total": len(_items),
                "urgent": [i for i in _items if i["days_left"] <= 7],
                "upcoming": [i for i in _items if i["days_left"] > 7],
                "all": _items,
            })
        except Exception as _ex:
            return _JSONResponse({"error": str(_ex)}, status_code=500)

    @_cl_app.get("/api/claims/open")
    async def _api_open_claims(max_age_days: int = _Query(default=90, ge=1, le=365)):
        """Return open/investigating claims — useful for n8n follow-up automation."""
        import sqlite3 as _sqlite3
        from pathlib import Path as _Path
        _db = _Path(__file__).parent / "mcp-server" / "insurance_broker.db"
        try:
            _conn = _sqlite3.connect(str(_db))
            _conn.row_factory = _sqlite3.Row
            _rows = _conn.execute("""
                SELECT cl.id as claim_id, cl.client_id, c.name as client_name,
                       c.email as client_email, c.phone as client_phone,
                       cl.policy_id, cl.incident_date, cl.status,
                       cl.damage_estimate, cl.description,
                       cl.insurer_claim_number, cl.notes,
                       CAST(julianday('now') - julianday(cl.incident_date) AS INTEGER) as days_open
                FROM claims cl
                JOIN clients c ON c.id = cl.client_id
                WHERE cl.status IN ('open', 'investigating')
                ORDER BY cl.incident_date ASC
            """).fetchall()
            _conn.close()
            _items = [dict(r) for r in _rows]
            return _JSONResponse({
                "total_open": len(_items),
                "overdue": [i for i in _items if i["days_open"] > max_age_days],
                "claims": _items,
            })
        except Exception as _ex:
            return _JSONResponse({"error": str(_ex)}, status_code=500)

    @_cl_app.get("/api/reports/asf")
    async def _api_asf(month: int = _Query(..., ge=1, le=12), year: int = _Query(..., ge=2020, le=2030)):
        result = asf_summary_fn(month=month, year=year)
        return _JSONResponse({"report": result})

    @_cl_app.get("/api/reports/bafin")
    async def _api_bafin(month: int = _Query(..., ge=1, le=12), year: int = _Query(..., ge=2020, le=2030)):
        result = bafin_summary_fn(month=month, year=year)
        return _JSONResponse({"report": result})

    @_cl_app.get("/api/clients/search")
    async def _api_clients(q: str = _Query(..., min_length=1), limit: int = _Query(default=20, ge=1, le=100)):
        result = search_clients_fn(query=q, limit=limit)
        return _JSONResponse({"clients": result})

    @_cl_app.get("/api/dashboard")
    async def _api_dashboard():
        """Summary dashboard stats — for embedding in external tools."""
        import sqlite3 as _sqlite3
        from datetime import date as _date
        from pathlib import Path as _Path
        _db = _Path(__file__).parent / "mcp-server" / "insurance_broker.db"
        try:
            _conn = _sqlite3.connect(str(_db))
            _conn.row_factory = _sqlite3.Row
            _today = _date.today()
            stats = {
                "as_of": _today.isoformat(),
                "active_policies": _conn.execute("SELECT COUNT(*) FROM policies WHERE status='active'").fetchone()[0],
                "clients": _conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
                "open_claims": _conn.execute("SELECT COUNT(*) FROM claims WHERE status IN ('open','investigating')").fetchone()[0],
                "expiring_7":  _conn.execute(
                    "SELECT COUNT(*) FROM policies WHERE status='active' AND julianday(end_date)-julianday('now') BETWEEN 0 AND 7"
                ).fetchone()[0],
                "expiring_30": _conn.execute(
                    "SELECT COUNT(*) FROM policies WHERE status='active' AND julianday(end_date)-julianday('now') BETWEEN 0 AND 30"
                ).fetchone()[0],
                "offers_total": _conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0],
            }
            _conn.close()
            return _JSONResponse(stats)
        except Exception as _ex:
            return _JSONResponse({"error": str(_ex)}, status_code=500)

    @_cl_app.get("/api/debug-from-app")
    async def _debug_from_app():
        """Test if app.py subprocess can reach main.py via localhost."""
        import requests as _rr, asyncio as _aa, os as _os
        port = _os.environ.get("PORT", "8080")
        results = {}
        loop = _aa.get_event_loop()
        def _chk(path):
            try:
                r = _rr.get(f"http://localhost:{port}{path}", timeout=3)
                return {"status": r.status_code, "body": r.text[:100]}
            except Exception as e:
                return {"error": str(e)}
        for path in ["/health", "/cu/status"]:
            results[path] = await loop.run_in_executor(None, lambda p=path: _chk(p))
        return _JSONResponse({"port": port, "pid": __import__("os").getpid(), "results": results})

    print("[INFO] /api/* endpoints mounted on chainlit.server.app")
except Exception as _e:
    print(f"[WARN] API endpoints not mounted: {_e}")

# ── Computer Use shared state ─────────────────────────────────────────────────
# When running via `uvicorn main:app`, the state lives in main.py.
# When running standalone via `chainlit run app.py`, we own the state here.
import asyncio as _asyncio
import uuid as _uuid
from datetime import datetime as _datetime
from collections import defaultdict as _defaultdict

# State for computer-use tasks — shared with main.py via cu_state module
# DO NOT import main here — circular import deadlock (main→chainlit→app→main)
# cu_state is a neutral module with no imports from main/chainlit
from cu_state import _cu_tasks, _cu_results, _cu_agents, _cu_pending

try:
    from chainlit.server import app as _cl_app2
    from fastapi import Request as _Request, Header as _Header
    from fastapi.responses import JSONResponse as _JSONResponse2
    from typing import Optional as _Optional

    @_cl_app2.get("/api/computer-use/tasks")
    async def _cu_get_tasks(
        request: _Request,
        x_agent_id: _Optional[str] = _Header(None),
    ):
        """Local agent polls this to get pending tasks."""
        agent_id = x_agent_id or request.headers.get("X-Agent-ID", "unknown")

        # Return tasks queued for this agent
        pending_ids = _cu_pending.get(agent_id, [])
        tasks = []
        remaining_ids = []
        for tid in pending_ids:
            task = _cu_tasks.get(tid)
            if task and task.get("status") == "pending":
                task["status"] = "dispatched"
                tasks.append(task)
            else:
                remaining_ids.append(tid)
        _cu_pending[agent_id] = remaining_ids

        # Update agent last-seen
        if agent_id in _cu_agents:
            _cu_agents[agent_id]["last_seen"] = _datetime.utcnow().isoformat()

        return _JSONResponse2({"tasks": tasks, "agent_id": agent_id})

    @_cl_app2.post("/api/computer-use/results")
    async def _cu_post_result(request: _Request):
        """Local agent posts task results here."""
        try:
            body = await request.json()
            task_id = body.get("task_id")
            if not task_id:
                return _JSONResponse2({"error": "task_id required"}, status_code=400)
            _cu_results[task_id] = {
                "result": body.get("result", {}),
                "agent_id": body.get("agent_id"),
                "completed_at": body.get("completed_at", _datetime.utcnow().isoformat()),
            }
            if task_id in _cu_tasks:
                _cu_tasks[task_id]["status"] = "completed"
            return _JSONResponse2({"ok": True, "task_id": task_id})
        except Exception as e:
            return _JSONResponse2({"error": str(e)}, status_code=500)

    @_cl_app2.post("/api/computer-use/heartbeat")
    async def _cu_heartbeat(request: _Request):
        """Local agent sends heartbeat to show it's online."""
        try:
            body = await request.json()
            agent_id = body.get("agent_id", "unknown")
            _cu_agents[agent_id] = {
                "agent_id": agent_id,
                "platform": body.get("platform", ""),
                "connectors": body.get("connectors", []),
                "last_seen": _datetime.utcnow().isoformat(),
                "python": body.get("python", ""),
            }
            return _JSONResponse2({"ok": True, "agent_id": agent_id})
        except Exception as e:
            return _JSONResponse2({"error": str(e)}, status_code=500)

    @_cl_app2.get("/api/computer-use/status")
    async def _cu_status():
        """Returns all online agents and their capabilities."""
        from datetime import datetime, timezone, timedelta
        online = []
        for agent_id, info in _cu_agents.items():
            try:
                last = _datetime.fromisoformat(info["last_seen"])
                delta = (_datetime.utcnow() - last).total_seconds()
                if delta < 120:  # online if heartbeat within 2 min
                    online.append({**info, "online": True, "seconds_ago": round(delta)})
            except Exception:
                pass
        return _JSONResponse2({
            "agents_online": len(online),
            "agents": online,
            "total_tasks": len(_cu_tasks),
            "pending_results": sum(1 for t in _cu_tasks.values() if t.get("status") == "pending"),
        })

    print("[INFO] /api/computer-use/* endpoints mounted")
except Exception as _e2:
    print(f"[WARN] Computer Use API endpoints not mounted: {_e2}")


def _cu_get_base_url() -> str:
    """Get the base URL for inter-process HTTP calls.

    app.py and main.py run in the SAME uvicorn process (mount_chainlit is in-process).
    We can use localhost directly — much faster and more reliable than self-calls
    via the public Cloud Run URL (which adds ~200ms RTT and can timeout).

    Chainlit intercepts /api/* routes on localhost, but our /cu/* routes are
    mounted on FastAPI in main.py BEFORE mount_chainlit, so they work fine.
    """
    port = os.environ.get("PORT", "8080")
    return f"http://localhost:{port}"


def _cu_enqueue_task(connector: str, action: str, params: dict,
                      agent_id: str = "default", timeout: int = 120,
                      credentials: dict = None) -> str:
    """
    Enqueue a computer-use task via HTTP to the FastAPI server (main.py).
    Uses the public URL because Chainlit intercepts localhost requests.
    """
    import requests as _req
    task_id = str(_uuid.uuid4())
    task = {
        "task_id": task_id,
        "connector": connector,
        "action": action,
        "params": params,
        "credentials": credentials or {},
        "timeout": timeout,
        "status": "pending",
        "created_at": _datetime.utcnow().isoformat(),
    }
    base = _cu_get_base_url()
    try:
        _req.post(
            f"{base}/cu/enqueue",
            json={"task": task, "agent_id": agent_id},
            timeout=10,
        )
    except Exception:
        # Fallback: write directly to cu_state (works if same process)
        _cu_tasks[task_id] = task
        _cu_pending[agent_id].append(task_id)
    return task_id


async def _cu_wait_result(task_id: str, timeout: int = 130) -> dict:
    """Wait for a task result by polling /cu/result via the public URL."""
    import requests as _req
    base = _cu_get_base_url()
    url = f"{base}/cu/result/{task_id}"
    loop = _asyncio.get_event_loop()
    start = loop.time()

    def _poll():
        try:
            r = _req.get(url, timeout=5)
            return r.json()
        except Exception:
            return {}

    while (loop.time() - start) < timeout:
        data = await loop.run_in_executor(None, _poll)
        if data.get("ready"):
            return data.get("result", {})
        await _asyncio.sleep(2)
    return {"success": False, "error": f"Task {task_id} timed out after {timeout}s — is the local agent running?"}

# ── Anthropic client ──────────────────────────────────────────────────────────
_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
if not _anthropic_key:
    raise RuntimeError("ANTHROPIC_API_KEY not set. Add it to .env file in the project root.")

client = anthropic.Anthropic(api_key=_anthropic_key)
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Alex, a friendly and proactive AI assistant for an insurance brokerage (ASF Romania / BaFin Germany).

You talk naturally with brokers in whatever language they use (Romanian, English, German). You NEVER return raw errors — if something fails, you explain simply and offer alternatives.

## Your Personality
- Warm, concise, professional
- Always suggest the next logical step
- When unsure what the broker wants, ask one clear question
- Never say "I cannot do that" — always find a way or offer an alternative
- Respond in the same language the broker writes in

## Tools Available
- broker_search_clients — caută client după nume, telefon, email
- broker_get_client — profil complet cu polițe
- broker_create_client — adaugă client nou
- broker_update_client — corectează datele unui client existent (nume, telefon, email, etc.)
- broker_delete_client — șterge client (refuză dacă are polițe active)
- broker_search_products — caută produse (RCA, CASCO, PAD, CMR, KFZ, LIFE, HEALTH)
- broker_compare_products — comparație tabelară
- broker_create_offer — generează ofertă profesională (PDF + XLSX + DOCX)
- broker_list_offers — listează ofertele generate
- broker_send_offer_email — trimite oferta pe email clientului
- broker_get_renewals_due — polițe care expiră curând
- broker_list_policies — listează polițe
- broker_log_claim — înregistrează daună
- broker_get_claim_status — status dosar daună
- broker_asf_summary — raport lunar ASF (Romania)
- broker_bafin_summary — raport lunar BaFin (Germania)
- broker_check_rca_validity — verifică valabilitate RCA
- broker_cross_sell — analizează portofoliul clientului și sugerează produse lipsă
- broker_calculate_premium — estimează prima de asigurare (RCA/CASCO) pe baza factorilor de risc
- broker_compliance_check — verifică completitudinea dosarului client (documente, polițe, conformitate)
- broker_save_conversation — salvează și asociază conversația curentă cu un client (pentru istoric). Apelează când brokerul spune "salvează", "linkuiește la Ionescu", etc.
- broker_check_rca — verifică RCA în timp real pe portalul AIDA/BAAR via browser headless pe server (NU necesită agent local). Returnează: rca_valid, expiry_date, insurer, policy_number, coverage_type, insured_sum, days_until_expiry, captcha_blocked, from_cache (cache TTL 6h), screenshot_b64 (la eșec).
- broker_browse_web — accesează orice URL public și extrage text sau tabele (NU necesită agent local)
- broker_computer_use_status — verifică dacă agentul local e conectat (necesar doar pentru desktop apps sau intranet)
- broker_run_task — execută task pe calculatorul angajatului. Connectors disponibili: `desktop_generic` (desktop apps, rețea internă), `cedam` (verificare RCA via portal ASF/CEDAM), `web_generic` (orice site web via browser local), `anthropic_computer_use` (computer use avansat cu Claude Vision).
- broker_drive_upload — încarcă un fișier generat (ofertă PDF, raport XLSX/DOCX) în Google Drive; returnează link partajabil
- broker_drive_list — listează fișierele din folderul Google Drive al brokerului
- broker_drive_get_link — obține linkul unui fișier deja încărcat în Google Drive
- broker_sharepoint_upload — încarcă un fișier în SharePoint (Microsoft 365) via Microsoft Graph; returnează link intern
- broker_sharepoint_list — listează fișierele din folderul SharePoint configurat
- broker_sharepoint_get_link — obține linkul unui fișier deja încărcat în SharePoint
- broker_search_knowledge — căutare semantică în knowledge base (RAG): produse, ghiduri daune, conformitate, FAQ. Folosește pentru întrebări vagi/naturale despre acoperiri, excluderi, proceduri.
- broker_upload_document — încarcă PDF/imagine în Files API Anthropic pentru analiză persistentă. Returnează file_id reutilizabil.
- broker_analyze_document — analizează document cu Claude Vision: polițe scanate, poze daune, facturi, constatare amiabilă, buletin. Acceptă path local SAU file_id.
- broker_kb_status — starea knowledge base (număr chunks indexate, categorii)
- broker_kb_reindex — re-indexează knowledge base (după adăugare produse noi sau actualizare docs/)

## Când să folosești ce tool:
- **RCA verificare** → `broker_check_rca` (instant, fără agent). Dacă răspunsul conține `captcha_blocked: true` → folosește automat `broker_run_task` cu connector=`cedam` (agent local, browser vizibil, ocolește CAPTCHA).
- **Orice site web public** → `broker_browse_web` (fără agent)
- **Deschide aplicație + scrie text** (TextEdit, Notes, Word, Excel) → `broker_run_task` cu connector=`desktop_generic`, action=`open_app_and_type`, params={app: "TextEdit", text: "textul exact"} — OBLIGATORIU această acțiune, NU run_task!
- **Calculator** → `broker_run_task` cu connector=`desktop_generic`, action=`run_task`, params.instruction="deschide Calculator si calculeaza 2+2"
- **Rețea internă** (intranet, VPN) → `broker_run_task` cu connector=`desktop_generic`, action=`run_task`
- **Verificare RCA via agent local** (dacă `broker_check_rca` nu merge) → `broker_run_task` cu connector=`cedam`, action=`check_rca`, params={plate: "B123ABC"}
- **Automatizare site web via browser local** → `broker_run_task` cu connector=`web_generic`, action=`run_task`
- **Computer use avansat cu AI Vision** → `broker_run_task` cu connector=`anthropic_computer_use`, action=`run_task`
- **Salvează ofertă/raport în Google Drive** → `broker_drive_upload` cu filename=numele fișierului din output/; apoi dă linkul clientului
- **Salvează în SharePoint (Microsoft 365)** → `broker_sharepoint_upload` — pentru firme pe M365
- **Listează fișierele salvate** → `broker_drive_list` sau `broker_sharepoint_list`
- **Întrebare vagă despre acoperiri/excluderi/proceduri** (ex: "ce acoperă CASCO?", "ce documente trebuie la daune Allianz?") → `broker_search_knowledge` ÎNAINTE de `broker_search_products`
- **Broker uploadează un PDF/imagine** → `broker_upload_document` → obții file_id → `broker_analyze_document(file_id)` pentru extragere date
- **Analizează poliță scanată** → `broker_analyze_document(doc_type="policy")` → extrage automat număr poliță, date, primă, acoperire
- **Analizează poze daune** → `broker_analyze_document(doc_type="claim_photo")` → estimare daune + recomandare log_claim
- **Procesează constatare amiabilă** → `broker_analyze_document(doc_type="constatare")` → extrage ambii șoferi + descrie dauna
- INTERZIS: action `fill_form` pentru sarcini desktop simple — folosește `run_task` cu instrucțiune naturală.
- INTERZIS: action `run_task` când utilizatorul cere să deschizi o aplicație și să scrii text — folosește `open_app_and_type`.

## CRITICAL: Always use tools — NEVER answer from memory

**You have NO knowledge of real products, clients, or policies.** All data lives in the database.
- NEVER list insurance products, prices, or insurers from your training — you don't have this data
- NEVER say "Here are the top HEALTH products: NN, Allianz..." without calling broker_search_products first
- NEVER confirm or recommend a product without calling the tool first
- If asked about products → call broker_search_products IMMEDIATELY, then show the real results
- If asked about a client → call broker_search_clients or broker_get_client first

**Rule:** If you are about to mention a product name, insurer, price, or policy — STOP and call the tool instead.

## How to Handle Any Request
1. **Understand intent** — even vague requests ("fa ceva cu asta", "vreau oferta", "ce mai am de facut")
2. **Always call a tool first** — never describe data you haven't fetched yet
3. **Chain actions** — search client → create if missing → search products → create offer, all in one flow when the broker says "onboard" or "fa oferta"
4. **After offer is generated** — it's already shown in chat. Don't regenerate. Ask if they want to email it or modify something
5. **If a tool returns no results** — suggest alternatives: "Nu am găsit produse HEALTH, dar am LIFE cu acoperire similară. Generez oferta cu astea?"
6. **If something fails** — say what happened in plain language and offer 2-3 options to continue

## Document Upload Workflow
When a doc is analyzed and broker confirms data is correct:
1. Search DB using CLIENT name (never clinic/issuer phone or name) → create client if not found
2. Identify best product type from document context
3. Ask ONE question: "Am creat clientul X. Generez ofertă de HEALTH?" → on any affirmative → do it immediately

CRITICAL for document OCR:
- The CLIENT is the person the document is ABOUT (patient, vehicle owner, policy holder)
- The ISSUER is the clinic/insurer/company that issued it — NEVER use issuer phone/name as client data
- If broker says "corecție" / "greșit" / "numele e..." → update your understanding and use the corrected data
- NEVER search using a clinic phone number or company name as if it were a client

## Offer Workflow
- "da" / "yes" / "fă" / "generează" / "make it" after seeing products = call broker_create_offer IMMEDIATELY, no more questions
- After offer is generated, the UI will ask the broker to approve/edit/download — you don't need to ask again
- If broker says "aprobă" / "trimite" / "send" after seeing offer → call broker_send_offer_email right away
- If broker says "editează" / "modifică" + describes changes → call broker_create_offer again with updated parameters
- Never call broker_create_offer again just to "show" an offer — use the session cache instead
- NEVER get stuck waiting — always suggest the next logical action

## Language & Format
- Match the broker's language automatically
- Keep responses short — max 3-4 lines unless showing data tables
- Use ✅ ⚠️ 📄 💡 sparingly for clarity
- Amounts: RON for RO products, EUR for DE/KFZ

## Compliance
Never show full CNP/passport numbers — use client IDs only."""

# ── Tool definitions for Anthropic function calling ───────────────────────────
TOOLS = [
    {
        "name": "broker_search_clients",
        "description": "Search clients by name, phone, or email address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name, phone, or email to search"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "broker_get_client",
        "description": "Get full client profile including all their policies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Client ID (e.g. CLI001)"},
            },
            "required": ["client_id"],
        },
    },
    {
        "name": "broker_create_client",
        "description": "Create a new client in the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "address": {"type": "string"},
                "client_type": {"type": "string", "description": "individual or company"},
                "country": {"type": "string", "description": "RO or DE"},
                "source": {"type": "string"},
            },
            "required": ["name", "phone"],
        },
    },
    {
        "name": "broker_update_client",
        "description": "Update an existing client's details (name, phone, email, address, etc.). Only provided fields are changed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Client ID from broker_search_clients"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "address": {"type": "string"},
                "id_number": {"type": "string"},
                "country": {"type": "string", "description": "RO or DE"},
                "client_type": {"type": "string", "description": "individual or company"},
                "notes": {"type": "string"},
            },
            "required": ["client_id"],
        },
    },
    {
        "name": "broker_delete_client",
        "description": "Delete a client. Will refuse if they have active policies. Use broker_search_clients first to get client_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Client ID to delete"},
            },
            "required": ["client_id"],
        },
    },
    {
        "name": "broker_search_products",
        "description": "Search available insurance products from all partner insurers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_type": {"type": "string", "description": "Type: RCA, CASCO, PAD, HOME, LIFE, CMR, KFZ, LIABILITY, TRANSPORT, HEALTH"},
                "country": {"type": "string", "description": "RO or DE"},
            },
            "required": ["product_type"],
        },
    },
    {
        "name": "broker_compare_products",
        "description": "Compare multiple insurance products side by side.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_ids": {"type": "string", "description": "Comma-separated product IDs from broker_search_products"},
            },
            "required": ["product_ids"],
        },
    },
    {
        "name": "broker_create_offer",
        "description": "Generate a professional insurance offer document for a client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "product_ids": {"type": "string", "description": "Comma-separated product IDs"},
                "language": {"type": "string", "description": "en, ro, or de"},
                "valid_days": {"type": "integer"},
                "notes": {"type": "string"},
                "format": {"type": "string", "description": "text or pdf"},
            },
            "required": ["client_id", "product_ids"],
        },
    },
    {
        "name": "broker_list_offers",
        "description": "List generated offers, optionally filtered by client or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "status": {"type": "string", "description": "sent, accepted, or expired"},
            },
        },
    },
    {
        "name": "broker_send_offer_email",
        "description": "Send a generated offer by email to the client. Fetches client email from DB if to_email not provided.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string", "description": "Offer ID from broker_list_offers"},
                "to_email": {"type": "string", "description": "Recipient email (optional, uses client email from DB if not set)"},
                "subject": {"type": "string", "description": "Email subject (optional)"},
            },
            "required": ["offer_id"],
        },
    },
    {
        "name": "broker_get_renewals_due",
        "description": "Get policies expiring within the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Number of days to look ahead (default 30)"},
            },
        },
    },
    {
        "name": "broker_list_policies",
        "description": "List policies, optionally filtered by client ID or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "status": {"type": "string", "description": "active, expired, or cancelled"},
            },
        },
    },
    {
        "name": "broker_log_claim",
        "description": "Register a new damage/claims report for a client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "policy_id": {"type": "string"},
                "incident_date": {"type": "string", "description": "YYYY-MM-DD"},
                "description": {"type": "string"},
                "damage_estimate": {"type": "number"},
            },
            "required": ["client_id", "policy_id", "incident_date", "description"],
        },
    },
    {
        "name": "broker_get_claim_status",
        "description": "Get the status of an existing claim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string"},
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "broker_asf_summary",
        "description": "Generate monthly ASF (Romanian Financial Supervisory Authority) report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "integer", "description": "Month number 1-12"},
                "year": {"type": "integer"},
            },
            "required": ["month", "year"],
        },
    },
    {
        "name": "broker_bafin_summary",
        "description": "Generate monthly BaFin (German) regulatory report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "integer", "description": "Month number 1-12"},
                "year": {"type": "integer"},
            },
            "required": ["month", "year"],
        },
    },
    {
        "name": "broker_check_rca_validity",
        "description": "Check RCA (mandatory Romanian motor insurance) validity for a client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Client name or policy number"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "broker_cross_sell",
        "description": "Analyze a client's portfolio and suggest missing insurance products for cross-selling opportunities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Client ID (e.g. CLI001)"},
            },
            "required": ["client_id"],
        },
    },
    {
        "name": "broker_calculate_premium",
        "description": "Estimate insurance premium based on risk factors. Supports RCA and CASCO for Romania.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_type": {"type": "string", "description": "RCA or CASCO"},
                "age": {"type": "integer", "description": "Driver age (default 35)"},
                "engine_cc": {"type": "integer", "description": "Engine capacity in cc (default 1600)"},
                "bonus_malus_class": {"type": "string", "description": "B0-B14 or M1-M8 (default B0)"},
                "zone": {"type": "string", "description": "City or Urban/Rural (default Urban)"},
                "vehicle_value": {"type": "number", "description": "Vehicle value in RON (for CASCO)"},
                "country": {"type": "string", "description": "RO or DE (default RO)"},
            },
            "required": ["product_type"],
        },
    },
    {
        "name": "broker_compliance_check",
        "description": "Check compliance status for a client — missing documents, expiring policies, mandatory product gaps, regulatory issues. Returns a compliance score 0-100.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Client ID (e.g. CLI001)"},
            },
            "required": ["client_id"],
        },
    },
    {
        "name": "broker_save_conversation",
        "description": (
            "Save and link the current conversation to a specific client. "
            "Call this when the broker says something like 'save this conversation', "
            "'link to Ionescu', 'save chat about CLI001', etc. "
            "After calling this tool, the conversation will appear under that client's "
            "history in the '📁 Conversation history by client' section. "
            "Use broker_search_clients first to find the client_id if you don't have it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Client ID to link this conversation to (e.g. CLI001)",
                },
                "title": {
                    "type": "string",
                    "description": "Optional title for this conversation (max 80 chars). If omitted, keeps current title.",
                },
            },
            "required": ["client_id"],
        },
    },
    # ── Web automation tools (Playwright on Cloud Run — no local agent needed) ──
    {
        "name": "broker_check_rca",
        "description": (
            "Verifică valabilitatea poliței RCA pentru un număr de înmatriculare, "
            "accesând portalul AIDA/BAAR în timp real via browser headless pe server. "
            "Nu necesită agent local — rulează direct pe Cloud Run. Cache TTL 6h — "
            "dacă plăcuța a fost verificată recent, răspuns instant fără request nou. "
            "Returnează: rca_valid (bool), expiry_date, insurer, policy_number, "
            "coverage_type (RCA/CASCO/CMR etc.), insured_sum, days_until_expiry, "
            "captcha_blocked (bool — dacă True, folosește broker_run_task cu connector=cedam), "
            "from_cache (bool), cached_at, screenshot_b64 (base64 PNG la eșec, pentru debugging)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plate": {"type": "string", "description": "Numărul de înmatriculare (ex: B123ABC, B 123 ABC, CJ12XYZ)"},
            },
            "required": ["plate"],
        },
    },
    {
        "name": "broker_browse_web",
        "description": (
            "Accesează un URL public și extrage conținutul paginii (text sau tabele). "
            "Util pentru verificări pe site-uri externe: prețuri, știri, portaluri publice, etc. "
            "Nu necesită agent local — rulează headless pe Cloud Run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL-ul de accesat (trebuie să fie public, fără autentificare)"},
                "query": {"type": "string", "description": "Ce anume căutăm/extragem din pagină (pentru context)"},
                "extract_type": {"type": "string", "description": "'text' (default) pentru text complet, 'table' pentru tabele HTML"},
            },
            "required": ["url"],
        },
    },
    # ── Computer Use tools (local agent — for desktop apps and intranets) ──
    {
        "name": "broker_computer_use_status",
        "description": "Check if the local computer-use agent is online on the employee's machine. Returns list of connected agents and available connectors (cedam, web_generic, desktop_generic, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "broker_run_task",
        "description": (
            "Run a computer-use task on the employee's local machine. "
            "The local agent executes the task (browser automation or desktop automation) and returns the result. "
            "Use connector='cedam' for RCA checks, connector='web_generic' for any website, connector='desktop_generic' for Windows/Mac apps. "
            "Actions: extract, fill_form, navigate, click, screenshot, check_rca, read_screen, run_task, open_app_and_type. "
            "IMPORTANT: For opening a desktop app and typing text, ALWAYS use action='open_app_and_type' with params={app: 'TextEdit', text: 'exact text here'} — NOT run_task."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "connector": {"type": "string", "description": "Connector to use: cedam, web_generic, desktop_generic"},
                "action": {"type": "string", "description": "Action: extract, fill_form, navigate, click, screenshot, check_rca, read_screen, run_task, login, open_app_and_type"},
                "params": {
                    "type": "object",
                    "description": "Action parameters. For open_app_and_type: {app: 'TextEdit', text: 'exact text to type'}. For run_task: {instruction: '...'}. For check_rca: {plate: 'B123ABC'}.",
                    "properties": {
                        "query": {"type": "string"},
                        "url": {"type": "string"},
                        "plate": {"type": "string", "description": "License plate for RCA check"},
                        "instruction": {"type": "string", "description": "Natural language instruction for run_task (desktop apps)"},
                        "max_steps": {"type": "integer", "description": "Max automation steps (default 10)"},
                        "app": {"type": "string", "description": "App name for open_app_and_type, e.g. 'TextEdit', 'Notes', 'Word'"},
                        "text": {"type": "string", "description": "Exact text to type for open_app_and_type"},
                    },
                },
                "agent_id": {"type": "string", "description": "Agent ID (from broker_computer_use_status). If omitted, sends to first available agent."},
                "timeout": {"type": "integer", "description": "Max seconds to wait for result (default 120)"},
            },
            "required": ["connector", "action"],
        },
    },
    # ── Google Drive tools ──────────────────────────────────────────────────
    {
        "name": "broker_drive_upload",
        "description": "Upload a generated file (offer PDF, report XLSX/DOCX) to the broker Google Drive folder. Returns a shareable link. Use after broker_create_offer or broker_asf_summary to save the result to Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Local filename from output/ directory (e.g. Offer_CLI001_2026-03-10.pdf)"},
                "drive_filename": {"type": "string", "description": "Optional: name to use in Google Drive (default: same as local)"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "broker_drive_list",
        "description": "List files in the broker Google Drive folder. Returns names, sizes, modification dates, and shareable links.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max files to return (default 20)"},
                "name_filter": {"type": "string", "description": "Optional filter by partial filename (e.g. Offer, ASF)"}
            }
        }
    },
    {
        "name": "broker_drive_get_link",
        "description": "Get a shareable Google Drive link for an already-uploaded file by its exact filename.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Exact filename in Google Drive"}
            },
            "required": ["filename"]
        }
    },
    # ── SharePoint tools ─────────────────────────────────────────────────────
    {
        "name": "broker_sharepoint_upload",
        "description": "Upload a generated file to the broker SharePoint folder via Microsoft Graph API. Returns a SharePoint link. Use for companies on Microsoft 365.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Local filename from output/ directory"},
                "sp_filename": {"type": "string", "description": "Optional: name to use in SharePoint"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "broker_sharepoint_list",
        "description": "List files in the broker SharePoint folder. Returns names, sizes, modification dates, and SharePoint links.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max files to return (default 20)"},
                "name_filter": {"type": "string", "description": "Optional filter by partial filename"}
            }
        }
    },
    {
        "name": "broker_sharepoint_get_link",
        "description": "Get a SharePoint link for an already-uploaded file by its exact filename.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Exact filename in SharePoint"}
            },
            "required": ["filename"]
        },
    },
    # ── RAG / Knowledge Base tools ─────────────────────────────────────────────
    {
        "name": "broker_search_knowledge",
        "description": (
            "Semantic search in the broker knowledge base (ChromaDB RAG). "
            "Use when broker asks vague/natural-language questions about: "
            "- What does a product cover? What are the exclusions? "
            "- Which insurer handles CMR claims? "
            "- What documents are needed for a claim at Allianz? "
            "- What ASF/BaFin class is this product? "
            "Returns top matching chunks with relevance scores. "
            "Categories: 'product', 'claims_guidance', 'compliance', 'faq_doc'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language question or keyword"},
                "category": {
                    "type": "string",
                    "description": "Optional filter: 'product', 'claims_guidance', 'compliance', 'faq_doc'",
                },
                "top_k": {"type": "integer", "description": "Number of results (default 5, max 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "broker_upload_document",
        "description": (
            "Upload a PDF or image to Anthropic Files API for persistent document analysis. "
            "Returns a file_id that can be reused in broker_analyze_document without re-uploading. "
            "Use for: scanned policies, damage photos, invoices, constatare amiabilă. "
            "Supported formats: PDF, PNG, JPG, WEBP, GIF."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "doc_type": {
                    "type": "string",
                    "description": "Document type: 'policy', 'claim_photo', 'invoice', 'constatare', 'id_card', 'other'",
                },
                "description": {"type": "string", "description": "Short description for audit trail"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "broker_analyze_document",
        "description": (
            "Analyze a document using Claude Vision. Accepts local file path OR file_id from broker_upload_document. "
            "Auto-extracts by doc_type: "
            "'policy' → policy number, dates, premium, coverage, exclusions; "
            "'claim_photo' → damage zones, severity, repair estimate; "
            "'invoice' → vendor, items, totals; "
            "'constatare' → both drivers, damage, signatures (handles handwriting in RO/DE/EN); "
            "'id_card' → name, CNP/ID, address. "
            "Returns structured markdown extraction."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path_or_file_id": {
                    "type": "string",
                    "description": "Local path (e.g. /path/to/policy.pdf) OR file_id starting with 'file_'",
                },
                "question": {
                    "type": "string",
                    "description": "Specific question (optional — auto-prompt used if empty)",
                },
                "doc_type": {
                    "type": "string",
                    "description": "'policy', 'claim_photo', 'invoice', 'constatare', 'id_card', 'other'",
                },
            },
            "required": ["file_path_or_file_id"],
        },
    },
    {
        "name": "broker_kb_status",
        "description": "Show knowledge base status: total indexed chunks, breakdown by category. Admin/debug use.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "broker_kb_reindex",
        "description": "Force re-index all knowledge sources (products, compliance maps, docs). Use after adding new products to DB or updating docs/ files.",
        "input_schema": {"type": "object", "properties": {}},
        "cache_control": {"type": "ephemeral"},  # Cache system prompt + full tools list (last tool)
    },
]

# ── Tool executor ─────────────────────────────────────────────────────────────
TOOL_DISPATCH = {
    "broker_search_clients":     search_clients_fn,
    "broker_get_client":         get_client_fn,
    "broker_create_client":      create_client_fn,
    "broker_update_client":      update_client_fn,
    "broker_delete_client":      delete_client_fn,
    "broker_search_products":    search_products_fn,
    "broker_compare_products":   compare_products_fn,
    "broker_create_offer":       create_offer_fn,
    "broker_list_offers":        list_offers_fn,
    "broker_send_offer_email":   send_offer_email_fn,
    "broker_get_renewals_due":   get_renewals_due_fn,
    "broker_list_policies":      list_policies_fn,
    "broker_log_claim":          log_claim_fn,
    "broker_get_claim_status":   get_claim_status_fn,
    "broker_asf_summary":        asf_summary_fn,
    "broker_bafin_summary":      bafin_summary_fn,
    "broker_check_rca_validity": check_rca_validity_fn,
    "broker_cross_sell":         cross_sell_fn,
    "broker_calculate_premium":  calculate_premium_fn,
    "broker_compliance_check":   compliance_check_fn,
    "broker_save_conversation":  None,  # special — handled in agentic loop (needs session context)
    # Web automation (Playwright on Cloud Run — sync wrappers, run in thread pool)
    "broker_check_rca":          _playwright_check_rca_fn,
    "broker_browse_web":         _playwright_browse_web_fn,
    # Computer use tools — status is sync, run_task is async (handled in agentic loop)
    "broker_computer_use_status": None,  # set after function definition below
    "broker_run_task":            None,  # async — handled in agentic loop
    # Google Drive tools
    "broker_drive_upload":        upload_to_drive_fn,
    "broker_drive_list":          list_drive_files_fn,
    "broker_drive_get_link":      get_drive_link_fn,
    # SharePoint tools
    "broker_sharepoint_upload":   sp_upload_fn,
    "broker_sharepoint_list":     sp_list_fn,
    "broker_sharepoint_get_link": sp_get_link_fn,
    # RAG / Knowledge base tools
    "broker_search_knowledge":    broker_search_knowledge_fn,
    "broker_upload_document":     broker_upload_document_fn,
    "broker_analyze_document":    broker_analyze_document_fn,
    "broker_kb_status":           broker_kb_status_fn,
    "broker_kb_reindex":          broker_kb_reindex_fn,
}

def execute_tool(tool_name: str, tool_input: dict) -> str:
    fn = TOOL_DISPATCH.get(tool_name)
    if fn is None and tool_name in TOOL_DISPATCH:
        # Async tool — should be handled by execute_tool_async
        return f"[async tool '{tool_name}' — use execute_tool_async]"
    if not fn:
        return (f"Toolul '{tool_name}' nu există. "
                f"Tooluri disponibile: {', '.join(TOOL_DISPATCH.keys())}")
    try:
        result = fn(**tool_input)
        return result if result else "Operațiunea a fost efectuată cu succes."
    except TypeError as e:
        # Missing or wrong arguments — give helpful hint
        import inspect
        sig = inspect.signature(fn)
        return (f"Parametri incorecți pentru {tool_name}. "
                f"Parametri necesari: {list(sig.parameters.keys())}. "
                f"Primit: {list(tool_input.keys())}. Eroare: {e}")
    except Exception as e:
        err = str(e)
        # Return friendly message with context so Alex can recover
        return (f"A apărut o problemă la {tool_name}: {err[:200]}. "
                f"Input folosit: {tool_input}. "
                f"Sugestie: verifică dacă ID-ul clientului/produsului este corect.")


# ── Computer Use tool implementations (async) ─────────────────────────────────

def _cu_computer_use_status_fn(**kwargs) -> str:
    """Returns status of connected local agents.

    Reads directly from cu_state._cu_agents (shared module, same process).
    No HTTP call needed — app.py and main.py share the same cu_state module
    because they run in the same uvicorn process via mount_chainlit.
    """
    from datetime import datetime as _dt2
    online = []
    for agent_id, info in _cu_agents.items():
        try:
            last = _dt2.fromisoformat(info["last_seen"])
            delta = (_dt2.utcnow() - last).total_seconds()
            if delta < 120:
                online.append({**info, "online": True, "seconds_ago": round(delta)})
        except Exception:
            pass

    if not online:
        return (
            "⚠️ **Niciun agent local conectat.**\n\n"
            "Pentru a folosi computer use, porniți agentul local pe calculatorul angajatului:\n"
            "```\n"
            "cd alex-local-agent\n"
            "python main.py start\n"
            "```"
        )

    lines = ["## 🤖 Agent Local — Status\n"]
    for info in online:
        secs = info.get("seconds_ago", "?")
        lines.append(f"**Agent:** `{info.get('agent_id', '?')}`")
        lines.append(f"- Status: 🟢 Online (văzut acum {secs}s)")
        lines.append(f"- Platform: {info.get('platform', 'N/A')}")
        connectors = info.get("connectors", [])
        lines.append(f"- Connectors disponibili: {', '.join(connectors) if connectors else 'niciunul'}")
        lines.append("")

    return "\n".join(lines)


async def _cu_run_task_async(
    connector: str,
    action: str,
    params: dict = None,
    agent_id: str = None,
    timeout: int = 120,
    credentials: dict = None,
) -> str:
    """Async implementation of broker_run_task — enqueues task and waits for result."""
    params = params or {}
    credentials = credentials or {}

    # Determine target agent — read directly from cu_state (same process, no HTTP needed)
    if not agent_id:
        from datetime import datetime as _dt3
        for info in _cu_agents.values():
            try:
                last = _dt3.fromisoformat(info["last_seen"])
                delta = (_dt3.utcnow() - last).total_seconds()
                if delta < 120:
                    agent_id = info["agent_id"]
                    break
            except Exception:
                pass

    if not agent_id:
        return (
            "⚠️ **Niciun agent local online.**\n\n"
            "Porniți agentul local cu:\n```\ncd alex-local-agent\npython main.py start\n```"
        )

    # Enqueue task
    task_id = _cu_enqueue_task(
        connector=connector,
        action=action,
        params=params,
        agent_id=agent_id,
        timeout=timeout,
        credentials=credentials,
    )

    # Notify user we're waiting
    connector_emoji = {"cedam": "🚗", "web_generic": "🌐", "desktop_generic": "🖥️",
                       "anthropic_computer_use": "🤖"}.get(connector, "⚙️")
    action_desc = {
        "check_rca": f"verificare RCA pentru {params.get('plate', '')}",
        "extract": f"extragere: {params.get('query', '')[:60]}",
        "navigate": f"navigare la {params.get('url', '')}",
        "fill_form": "completare formular",
        "screenshot": "capturare ecran",
        "read_screen": "citire ecran",
        "login": "autentificare",
    }.get(action, action)

    wait_msg = f"{connector_emoji} **Execut task pe agentul local** ({connector} / {action_desc})..."

    # Wait for result with timeout
    result = await _cu_wait_result(task_id, timeout=timeout + 10)

    if not result.get("success"):
        error = result.get("error", "Eroare necunoscută")
        return f"❌ **Task eșuat** ({connector}/{action})\n\nEroare: {error}"

    # Format result nicely
    if action == "check_rca":
        return _format_rca_result(result, params.get("plate", ""))
    elif action == "screenshot":
        # Return info about screenshot (base64 would be too long for chat)
        size = result.get("size_bytes", 0)
        return f"📸 **Screenshot capturat** ({size // 1024} KB)\n\nPot analiza ecranul dacă dorești — spune-mi ce să caut."
    elif action == "extract":
        data = result.get("data") or result.get("result", {})
        if isinstance(data, str):
            return f"📄 **Date extrase:**\n\n{data[:2000]}"
        elif isinstance(data, (list, dict)):
            return f"📄 **Date extrase:**\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:2000]}\n```"
        return f"📄 **Rezultat:** {str(result)[:1000]}"
    else:
        # Generic success response
        data = result.get("data") or result.get("result") or result
        if isinstance(data, str):
            return f"✅ **Task completat** ({connector}/{action})\n\n{data[:1500]}"
        return f"✅ **Task completat** ({connector}/{action})\n\n```\n{json.dumps(data, indent=2, ensure_ascii=False, default=str)[:1500]}\n```"


def _format_rca_result(result: dict, plate: str) -> str:
    """Format RCA check result as readable markdown."""
    if not result.get("data_found"):
        return (
            f"❌ **Nu există RCA activ** pentru numărul de înmatriculare **{plate}**\n\n"
            f"Clientul trebuie să achiziționeze o poliță RCA."
        )

    valid = result.get("rca_valid")
    expiry = result.get("expiry_date", "N/A")
    days = result.get("days_until_expiry")
    insurer = result.get("insurer", "N/A")
    policy_no = result.get("policy_number", "N/A")

    status_icon = "✅" if valid else "❌"
    status_text = "**VALABIL**" if valid else "**EXPIRAT**"

    urgency = ""
    if days is not None and days <= 30:
        urgency = f"\n\n⚠️ **ATENȚIE: Polița expiră în {days} zile!** Contactați clientul pentru reînnoire."
    elif days is not None and days <= 60:
        urgency = f"\n\n📅 Polița expiră în {days} zile — pregătire reînnoire."

    return (
        f"## {status_icon} Verificare RCA — {plate}\n\n"
        f"- **Status:** {status_text}\n"
        f"- **Asigurător:** {insurer}\n"
        f"- **Număr poliță:** {policy_no}\n"
        f"- **Dată expirare:** {expiry}\n"
        f"- **Zile rămase:** {days if days is not None else 'N/A'}"
        f"{urgency}"
    )


# ── Register async computer use tools in dispatch (after functions are defined) ─
TOOL_DISPATCH["broker_computer_use_status"] = _cu_computer_use_status_fn
# broker_run_task stays None — handled specially in agentic loop (await)


# ── Export helpers ────────────────────────────────────────────────────────────

def export_to_xlsx(content: str, title: str) -> Path:
    """Convert text content to XLSX with formatting."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]

    # Header style
    header_fill = PatternFill(start_color="1a365d", end_color="1a365d", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    lines = content.split("\n")
    row = 1
    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            # Table row
            cells = [c.strip() for c in line.split("|")[1:-1]]
            for col, cell_text in enumerate(cells, 1):
                cell = ws.cell(row=row, column=col, value=cell_text)
                if row <= 2:
                    cell.fill = header_fill
                    cell.font = header_font
                cell.alignment = Alignment(wrap_text=True)
            ws.column_dimensions[chr(64 + min(col, 26))].width = 20
        elif line.startswith("#"):
            cell = ws.cell(row=row, column=1, value=line.lstrip("#").strip())
            cell.font = Font(bold=True, size=12)
        elif line.strip() and not line.startswith("---"):
            ws.cell(row=row, column=1, value=line)

        if line.strip() or line.startswith("|"):
            row += 1

    out_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_{date.today().isoformat()}.xlsx"
    wb.save(str(out_path))
    return out_path


def export_to_docx(content: str, title: str) -> Path:
    """Convert text content to DOCX."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return None

    doc = Document()

    # Title
    heading = doc.add_heading(title, level=1)
    heading.runs[0].font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)

    lines = content.split("\n")
    table_rows = []
    in_table = False

    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not line.replace("|", "").replace("-", "").replace(" ", ""):
                continue  # separator line
            table_rows.append(cells)
            in_table = True
        else:
            if in_table and table_rows:
                # Flush table
                if len(table_rows) > 1:
                    t = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
                    t.style = "Table Grid"
                    for r_idx, row_data in enumerate(table_rows):
                        for c_idx, cell_text in enumerate(row_data):
                            if c_idx < len(t.rows[r_idx].cells):
                                t.rows[r_idx].cells[c_idx].text = cell_text
                                if r_idx == 0:
                                    t.rows[r_idx].cells[c_idx].paragraphs[0].runs[0].font.bold = True if t.rows[r_idx].cells[c_idx].paragraphs[0].runs else True
                doc.add_paragraph()
                table_rows = []
                in_table = False

            if line.startswith("## "):
                doc.add_heading(line[3:], level=2)
            elif line.startswith("# "):
                doc.add_heading(line[2:], level=1)
            elif line.startswith("**") and line.endswith("**"):
                p = doc.add_paragraph()
                run = p.add_run(line.strip("**"))
                run.bold = True
            elif line.strip() and not line.startswith("---"):
                doc.add_paragraph(line)

    out_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_{date.today().isoformat()}.docx"
    doc.save(str(out_path))
    return out_path


def export_to_pdf(content: str, title: str) -> Path:
    """Convert text/markdown content to PDF via WeasyPrint."""
    try:
        from weasyprint import HTML
    except ImportError:
        return None

    # Convert markdown-like content to HTML
    lines = content.split("\n")
    html_lines = ["<html><head><style>",
                  "body { font-family: Arial, sans-serif; margin: 40px; color: #333; }",
                  "h1 { color: #1a365d; border-bottom: 2px solid #1a365d; }",
                  "h2 { color: #2d3748; }",
                  "table { border-collapse: collapse; width: 100%; margin: 15px 0; }",
                  "th { background: #1a365d; color: white; padding: 8px; text-align: left; }",
                  "td { padding: 8px; border: 1px solid #e2e8f0; }",
                  "tr:nth-child(even) { background: #f7fafc; }",
                  ".footer { color: #718096; font-size: 11px; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; }",
                  "</style></head><body>"]

    in_table = False
    table_header_done = False

    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-", "").replace(" ", "") == "" for c in cells):
                continue  # separator
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                table_header_done = False
            if not table_header_done:
                html_lines.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
                table_header_done = True
            else:
                html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
                table_header_done = False
            if line.startswith("---"):
                html_lines.append("<hr>")
            elif line.strip():
                # Bold text
                line = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1) if "**" in line else line
                html_lines.append(f"<p>{line}</p>")

    if in_table:
        html_lines.append("</table>")

    html_lines.append(f'<div class="footer">Generated by Alex — Insurance Broker AI | {date.today().strftime("%d %B %Y")}</div>')
    html_lines.append("</body></html>")

    html_content = "\n".join(html_lines)
    out_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_{date.today().isoformat()}.pdf"

    try:
        HTML(string=html_content).write_pdf(str(out_path))
        return out_path
    except Exception:
        return None


async def send_export_files(content: str, base_title: str):
    """Generate and send PDF, XLSX, DOCX as downloadable attachments."""
    elements = []
    generated = []

    xlsx_path = export_to_xlsx(content, base_title)
    if xlsx_path and xlsx_path.exists():
        elements.append(cl.File(name=xlsx_path.name, path=str(xlsx_path), display="side"))
        generated.append("XLSX")

    docx_path = export_to_docx(content, base_title)
    if docx_path and docx_path.exists():
        elements.append(cl.File(name=docx_path.name, path=str(docx_path), display="side"))
        generated.append("DOCX")

    pdf_path = export_to_pdf(content, base_title)
    if pdf_path and pdf_path.exists():
        elements.append(cl.File(name=pdf_path.name, path=str(pdf_path), display="side"))
        generated.append("PDF")

    if elements:
        await cl.Message(
            content=f"📎 **Export ready:** {' · '.join(generated)} — click to download",
            elements=elements,
            author="Alex 🤖"
        ).send()


# ── Dashboard helpers ─────────────────────────────────────────────────────────
def get_dashboard_stats() -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        today = date.today().isoformat()
        in_30 = (date.today() + timedelta(days=30)).isoformat()
        in_7  = (date.today() + timedelta(days=7)).isoformat()

        active      = conn.execute("SELECT COUNT(*) as n FROM policies WHERE status='active'").fetchone()["n"]
        expiring7   = conn.execute("SELECT COUNT(*) as n FROM policies WHERE status='active' AND end_date<=? AND end_date>=?", (in_7, today)).fetchone()["n"]
        expiring30  = conn.execute("SELECT COUNT(*) as n FROM policies WHERE status='active' AND end_date<=? AND end_date>=?", (in_30, today)).fetchone()["n"]
        clients     = conn.execute("SELECT COUNT(*) as n FROM clients").fetchone()["n"]
        open_claims = conn.execute("SELECT COUNT(*) as n FROM claims WHERE status='open'").fetchone()["n"]
        offers      = conn.execute("SELECT COUNT(*) as n FROM offers").fetchone()["n"]
        conn.close()
        return {"active_policies": active, "expiring_7": expiring7, "expiring_30": expiring30,
                "clients": clients, "open_claims": open_claims, "offers_sent": offers}
    except Exception:
        return {}


async def process_uploaded_file(file: cl.File) -> str:
    """Process an uploaded file with Claude Vision. Returns analysis text."""
    name_lower = file.name.lower()
    is_image = any(name_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"])
    is_pdf = name_lower.endswith(".pdf")
    is_text = any(name_lower.endswith(ext) for ext in [".txt", ".md", ".csv"])

    if not (is_image or is_pdf or is_text):
        return f"File {file.name} received — format not supported for auto-analysis. Please describe its content."

    # Chainlit 2.x: uploaded files may have content=None, read from path instead
    file_bytes = file.content
    if not file_bytes and file.path:
        file_bytes = Path(file.path).read_bytes()
    if not file_bytes:
        return f"Could not read file content for {file.name}."

    if is_text:
        text_content = file_bytes.decode("utf-8", errors="replace")
        return f"[Text file: {file.name}]\n\n{text_content[:3000]}"

    if is_image:
        media_type = (
            "image/jpeg" if name_lower.endswith((".jpg", ".jpeg")) else
            "image/png" if name_lower.endswith(".png") else
            "image/webp" if name_lower.endswith(".webp") else
            "image/jpeg"
        )
    else:
        media_type = "application/pdf"

    analysis_prompt = """Analyze this document carefully.

IMPORTANT DISTINCTION:
- The **CLIENT/PATIENT/SUBJECT** is the person this document is ABOUT (the insured person, patient, vehicle owner, policy holder)
- The **ISSUER/CLINIC/INSURER** is the organization that ISSUED or SIGNED the document

Extract in this exact format:

**Document Type:** (ID card / medical referral / insurance policy / accident report / invoice / lab results / other)

**CLIENT DATA** (the person this document is about — NOT the issuing organization):
- Full Name: [name of the person, NOT the clinic/company/issuer]
- Phone: [client's personal phone, NOT clinic reception number]
- Email: [client's email if present]
- Address: [client's address]
- Date of Birth / CNP: [if present]
- ID/Policy Number: [if present]

**ISSUER DATA** (clinic, insurer, company that issued the document):
- Issuer Name: [clinic name, insurer name, company]
- Issuer Phone: [clinic/company contact]
- Issuer Address: [clinic/company address]

**OTHER DETAILS:**
- Dates: [relevant dates]
- Amounts: [any monetary amounts in RON/EUR]
- Vehicle details: [if applicable]
- Diagnosis/Coverage/Damage: [key content]

**Suggested Insurance Type:** [HEALTH / LIFE / RCA / CASCO / PAD / other based on document context]

Be precise. Never confuse issuer contact data with client personal data."""

    try:
        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")
        # Claude supports images directly; PDFs via base64 document blocks
        if is_image:
            content_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded,
                },
            }
        else:
            # PDF — send as document block (supported in claude-3+ models)
            content_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": encoded,
                },
            }
        response = await _asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        content_block,
                        {"type": "text", "text": analysis_prompt},
                    ],
                }],
            )
        )
        analysis = ""
        for block in response.content:
            if hasattr(block, "text"):
                analysis += block.text
        return f"[Document analyzed: {file.name}]\n\n{analysis}" if analysis else f"Could not extract content from {file.name}."
    except Exception as e:
        err_str = str(e)
        return (f"⚠️ Nu am putut analiza {file.name}. "
                f"(Eroare: {err_str[:200]})")


# ── Auth callback (only active when CHAINLIT_AUTH_SECRET is set) ──────────────
if os.environ.get("CHAINLIT_AUTH_SECRET") and ADMIN_ENABLED:
    @cl.password_auth_callback
    def auth_callback(username: str, password: str):
        user = get_user_by_email(username)
        if not user or not user["is_active"]:
            return None
        if not verify_password(password, user["hashed_password"]):
            return None
        return cl.User(
            identifier=user["email"],
            metadata={
                "user_id": user["id"],
                "role": user["role"],
                "company_id": user["company_id"],
                "full_name": user["full_name"] or user["email"],
            }
        )


# ── Helper: load tools + show dashboard welcome ───────────────────────────────

async def _init_session_tools():
    """Load allowed_tools and user_meta into session. Returns user metadata dict."""
    if ADMIN_ENABLED:
        app_user = cl.user_session.get("user")
        if app_user:
            meta = app_user.metadata or {}
            allowed = get_user_tools(meta.get("user_id"), meta.get("role"))
            cl.user_session.set("allowed_tools", allowed)
            cl.user_session.set("user_meta", meta)
            return meta
        else:
            cl.user_session.set("allowed_tools", None)
            cl.user_session.set("user_meta", {})
    return {}


async def _refresh_sidebar(user_id: str) -> None:
    """Open/update the ElementSidebar with saved conversations grouped by client.

    Always opens the sidebar (even if empty) so the broker sees the panel.
    """
    if not ADMIN_ENABLED or not user_id:
        return
    try:
        clients = list_clients_with_conversations(user_id)

        if not clients:
            content = (
                "## 📁 Conversații salvate\n\n"
                "_Nu ai conversații salvate încă._\n\n"
                "**Cum salvezi o conversație:**\n"
                "1. Discută cu Alex despre un client\n"
                "2. Spune: **\"salvează discuția\"** sau **\"linkuiește la [Nume Client]\"**\n"
                "3. Apare aici automat, grupat pe client\n\n"
                "---\n"
                "*Sau după 3+ mesaje apare butonul 💾 automat.*"
            )
        else:
            lines = ["## 📁 Conversații salvate\n"]
            for c in clients[:30]:
                cname = c["client_name"] if c["client_name"] != "__unlinked__" else "Fără client"
                conv_count = c.get("conv_count", 0)
                lines.append(f"### 👤 {cname} ({conv_count})")
                convs = list_conversations_for_client(user_id, c["client_id"])
                for conv in convs[:10]:
                    msgs = conv.get("message_count", 0)
                    updated = conv.get("updated_at", "")[:10]
                    label = conv.get("title", "Conversație")
                    detail = f"{msgs} msg · {updated}" if msgs else updated
                    lines.append(f"- **{label}**  \n  _{detail}_")
                lines.append("")
            lines.append("---\n*Spune 'salvează discuția' pentru a adăuga una nouă.*")
            content = "\n".join(lines)

        sidebar_text = cl.Text(
            name="saved_conversations",
            content=content,
            display="side",
        )
        await cl.ElementSidebar.set_title("📁 Conversații salvate")
        await cl.ElementSidebar.set_elements([sidebar_text])
    except Exception:
        pass  # non-fatal — sidebar is cosmetic


async def _show_dashboard_welcome(user_id: str | None = None, full_name: str | None = None):
    """Send the portfolio dashboard welcome message with optional history shortcut."""
    stats = get_dashboard_stats()
    alerts = ""
    if stats.get("expiring_7", 0) > 0:
        n = stats['expiring_7']
        alerts = f"\n> ⚠️ **{n} {'policy' if n == 1 else 'policies'} expiring within 7 days!** Try: *'Show urgent renewals'*"

    greeting_line = f"👋 Hello, **{full_name}**!\n\n" if full_name else ""

    welcome = f"""{greeting_line}## 📊 Portfolio Dashboard — {date.today().strftime('%d %B %Y')}

| Metric | Value |
|---|---|
| 🟢 Active Policies | **{stats.get('active_policies', 0)}** |
| ⚠️ Expiring within 7 days | **{stats.get('expiring_7', 0)}** |
| 📅 Expiring within 30 days | **{stats.get('expiring_30', 0)}** |
| 👥 Clients | **{stats.get('clients', 0)}** |
| 📋 Open Claims | **{stats.get('open_claims', 0)}** |
| 📄 Offers Generated | **{stats.get('offers_sent', 0)}** |
{alerts}

How can I help you today? *(upload a document, ask about clients, renewals, compliance...)*"""

    # Show saved-conversations shortcut only if the user has conversations by client
    actions = []
    if ADMIN_ENABLED and user_id:
        clients_with_convs = list_clients_with_conversations(user_id)
        if clients_with_convs:
            actions.append(cl.Action(
                name="open_history",
                label="📁 Conversation history by client",
                payload={"user_id": user_id},
            ))

    await cl.Message(content=welcome, actions=actions, author="Alex 🤖").send()


# ── Conversation picker helpers (client-based) ────────────────────────────────

async def _show_client_history_picker(user_id: str):
    """Show clients that have saved conversations — user picks a client to browse."""
    clients = list_clients_with_conversations(user_id) if ADMIN_ENABLED else []

    if not clients:
        await cl.Message(
            content="No saved conversations yet. Start chatting — Alex will save conversations automatically when you link them to a client.",
            author="Alex 🤖",
        ).send()
        return

    actions = []
    for c in clients[:20]:
        conv_word = "conversation" if c["conv_count"] == 1 else "conversations"
        actions.append(cl.Action(
            name="select_client_history",
            label=f"👤 {c['client_name']} ({c['conv_count']} {conv_word})",
            payload={"client_id": c["client_id"], "client_name": c["client_name"]},
        ))

    await cl.Message(
        content="**Conversation history** — select a client to see past conversations:",
        actions=actions,
        author="Alex 🤖",
    ).send()


async def _show_conversation_picker_for_client(user_id: str, client_id: str, client_name: str):
    """Show conversations for a specific client."""
    conversations = list_conversations_for_client(user_id, client_id) if ADMIN_ENABLED else []

    actions = []
    for c in conversations[:20]:
        msgs = c.get("message_count", 0)
        msg_word = "message" if msgs == 1 else "messages"
        updated = c.get("updated_at", "")[:10]  # just the date part
        label = f"🗨️ {c['title']}"
        if msgs:
            label += f"  ({msgs} {msg_word}, {updated})"
        actions.append(cl.Action(
            name="resume_conversation",
            label=label,
            payload={"conversation_id": c["id"], "title": c["title"]},
        ))

    actions.append(cl.Action(
        name="new_conversation_for_client",
        label=f"➕ New conversation about {client_name}",
        payload={"client_id": client_id, "client_name": client_name},
    ))

    name_display = client_name if client_id != "__unlinked__" else "unlinked conversations"
    await cl.Message(
        content=f"**{name_display}** — pick a conversation or start a new one:",
        actions=actions,
        author="Alex 🤖",
    ).send()


# ── Legacy project picker (still works for backwards compat) ──────────────────

async def _show_project_picker(user_id: str, full_name: str):
    """Redirect to client-based history picker."""
    await _show_client_history_picker(user_id)


async def _show_conversation_picker(user_id: str, project_id: int, project_name: str):
    """Legacy shim — kept for backwards compat."""
    conversations = list_conversations(user_id, project_id) if ADMIN_ENABLED else []
    actions = []
    for c in conversations[:20]:
        actions.append(cl.Action(
            name="resume_conversation",
            label=f"🗨️ {c['title']}",
            payload={"conversation_id": c["id"], "title": c["title"]},
        ))
    actions.append(cl.Action(
        name="new_conversation",
        label="➕ New conversation",
        payload={"project_id": project_id, "project_name": project_name},
    ))
    await cl.Message(
        content=f"**{project_name}** — pick a conversation or start a new one:",
        actions=actions,
        author="Alex 🤖",
    ).send()


async def _render_history_to_ui(history: list[dict]):
    """Re-display stored messages in the UI. Only text blocks shown (no raw tool JSON)."""
    for msg in history:
        role    = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Multi-block assistant message — show only text parts
            text = "\n".join(
                block["text"]
                for block in content
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
            )
        else:
            text = str(content)

        if not text.strip():
            continue

        author = "You" if role == "user" else "Alex 🤖"
        await cl.Message(content=text, author=author).send()


# ── Starters (quick-action chips in the input area) ──────────────────────────
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="📁 Conversații salvate",
            message="Arată-mi conversațiile salvate",
        ),
        cl.Starter(
            label="⚠️ Reinnoiri urgente",
            message="Arată polițele care expiră în 30 de zile",
        ),
        cl.Starter(
            label="👥 Caută clienți",
            message="Caută toți clienții activi",
        ),
        cl.Starter(
            label="📊 Dashboard",
            message="Arată statistici portofoliu",
        ),
    ]


# ── Chainlit lifecycle ────────────────────────────────────────────────────────
@cl.on_chat_start
async def on_chat_start():
    # Initialise session state
    cl.user_session.set(_SK_HISTORY,    [])
    cl.user_session.set(_SK_CONV_ID,    None)
    cl.user_session.set(_SK_PROJECT_ID, None)
    cl.user_session.set(_SK_CLIENT_ID,  None)
    cl.user_session.set(_SK_TITLE_SET,  False)
    cl.user_session.set(_SK_SAVE_NUDGE, False)

    meta = await _init_session_tools()
    user_id   = meta.get("user_id")
    full_name = meta.get("full_name") or "Broker"

    # Varianta A — always go straight to chat.
    # If the user has saved projects, the welcome message shows a
    # "📁 My saved conversations" button. No blocking picker on startup.
    await _show_dashboard_welcome(user_id=user_id, full_name=full_name)
    # Open sidebar with saved conversations (non-blocking, cosmetic)
    if user_id:
        await _refresh_sidebar(user_id)


# ── Action callbacks ──────────────────────────────────────────────────────────

@cl.action_callback("select_project")
async def on_select_project(action: cl.Action):
    await action.remove()
    meta       = cl.user_session.get("user_meta", {})
    user_id    = meta.get("user_id")
    project_id   = action.payload["project_id"]
    project_name = action.payload["project_name"]

    cl.user_session.set(_SK_PROJECT_ID, project_id)
    await _show_conversation_picker(user_id, project_id, project_name)


@cl.action_callback("new_project")
async def on_new_project(action: cl.Action):
    await action.remove()
    meta       = cl.user_session.get("user_meta", {})
    user_id    = meta.get("user_id")
    company_id = meta.get("company_id")

    res = await cl.AskUserMessage(
        content="Enter a name for your new project:",
        timeout=120,
    ).send()
    if not res:
        await cl.Message(content="Project creation cancelled.", author="Alex 🤖").send()
        return

    name = res.get("output", "").strip()[:100]
    if not name:
        await cl.Message(content="Project name cannot be empty.", author="Alex 🤖").send()
        return

    try:
        project = create_project(user_id, company_id, name)
    except Exception:
        await cl.Message(
            content=f'A project named **"{name}"** already exists. Please choose a different name.',
            author="Alex 🤖",
        ).send()
        return

    cl.user_session.set(_SK_PROJECT_ID, project["id"])
    await _show_conversation_picker(user_id, project["id"], name)


@cl.action_callback("no_project")
async def on_no_project(action: cl.Action):
    """Legacy — kept for backwards compat with any in-flight sessions."""
    await action.remove()
    cl.user_session.set(_SK_PROJECT_ID, None)
    cl.user_session.set(_SK_CONV_ID, None)
    meta = cl.user_session.get("user_meta", {})
    await _show_dashboard_welcome(
        user_id=meta.get("user_id"),
        full_name=meta.get("full_name"),
    )


@cl.action_callback("open_history")
async def on_open_history(action: cl.Action):
    """Show client-based conversation history."""
    await action.remove()
    meta    = cl.user_session.get("user_meta", {})
    user_id = meta.get("user_id")
    await _show_client_history_picker(user_id)


@cl.action_callback("select_client_history")
async def on_select_client_history(action: cl.Action):
    """User picked a client — show their saved conversations."""
    await action.remove()
    meta        = cl.user_session.get("user_meta", {})
    user_id     = meta.get("user_id")
    client_id   = action.payload["client_id"]
    client_name = action.payload["client_name"]
    await _show_conversation_picker_for_client(user_id, client_id, client_name)


@cl.action_callback("new_conversation_for_client")
async def on_new_conversation_for_client(action: cl.Action):
    """Start a new saved conversation linked to a specific client."""
    await action.remove()
    meta       = cl.user_session.get("user_meta", {})
    user_id    = meta.get("user_id")
    company_id = meta.get("company_id")
    client_id  = action.payload["client_id"]
    client_name = action.payload["client_name"]

    # Create a project for the client if it doesn't exist yet (one project per client)
    project_id = None
    if ADMIN_ENABLED and user_id and company_id:
        # Try to find or create a project named after the client
        projects = list_projects(user_id)
        existing = next((p for p in projects if p["name"] == client_name), None)
        if existing:
            project_id = existing["id"]
        else:
            try:
                proj = create_project(user_id, company_id, client_name,
                                      description=f"Conversations about client {client_name}")
                project_id = proj["id"]
            except Exception:
                project_id = None

        conv = create_conversation(user_id, project_id, title=f"New conversation — {client_name}")
        cl.user_session.set(_SK_CONV_ID,    conv["id"])
        cl.user_session.set(_SK_PROJECT_ID, project_id)
        cl.user_session.set(_SK_CLIENT_ID,  client_id)
        # Link conversation to client immediately
        set_conversation_client(conv["id"], client_id)

    cl.user_session.set(_SK_HISTORY,   [])
    cl.user_session.set(_SK_TITLE_SET, False)
    await cl.Message(
        content=f"💬 New conversation about **{client_name}**. This will be saved automatically.",
        author="Alex 🤖",
    ).send()


@cl.action_callback("new_conversation")
async def on_new_conversation(action: cl.Action):
    await action.remove()
    meta       = cl.user_session.get("user_meta", {})
    user_id    = meta.get("user_id")
    project_id = cl.user_session.get(_SK_PROJECT_ID)

    if ADMIN_ENABLED and user_id and project_id:
        conv = create_conversation(user_id, project_id)
        cl.user_session.set(_SK_CONV_ID, conv["id"])

    cl.user_session.set(_SK_HISTORY,   [])
    cl.user_session.set(_SK_TITLE_SET, False)
    await _show_dashboard_welcome(user_id=user_id, full_name=meta.get("full_name"))


@cl.action_callback("resume_conversation")
async def on_resume_conversation(action: cl.Action):
    await action.remove()
    conv_id = action.payload["conversation_id"]
    title   = action.payload["title"]

    history = load_conversation_history(conv_id) if ADMIN_ENABLED else []

    cl.user_session.set(_SK_CONV_ID,    conv_id)
    cl.user_session.set(_SK_HISTORY,    history)
    cl.user_session.set(_SK_TITLE_SET,  True)
    cl.user_session.set(_SK_SAVE_NUDGE, True)   # already saved — no nudge needed

    if history:
        await _render_history_to_ui(history)

    await cl.Message(
        content=f'📂 Resumed **"{title}"** — {len(history)//2} message(s). Continue below.',
        author="Alex 🤖",
    ).send()


@cl.action_callback("save_conv_pick_client")
async def on_save_conv_pick_client(action: cl.Action):
    """Show client picker so broker can link the current conversation to a client."""
    await action.remove()
    conv_id = cl.user_session.get(_SK_CONV_ID)
    if not conv_id:
        await cl.Message(content="No active conversation to save.", author="Alex 🤖").send()
        return

    clients = get_all_clients_for_picker()
    if not clients:
        await cl.Message(content="No clients in database yet.", author="Alex 🤖").send()
        return

    actions = [
        cl.Action(
            name="save_conv_confirm",
            label=f"👤 {c['name']}",
            payload={"client_id": c["id"], "client_name": c["name"], "conv_id": conv_id},
        )
        for c in clients[:20]
    ]
    await cl.Message(
        content="**Link this conversation to a client:**",
        actions=actions,
        author="Alex 🤖",
    ).send()


@cl.action_callback("save_conv_confirm")
async def on_save_conv_confirm(action: cl.Action):
    """Link the current conversation to the selected client."""
    await action.remove()
    client_id   = action.payload["client_id"]
    client_name = action.payload["client_name"]
    conv_id     = action.payload["conv_id"]

    try:
        set_conversation_client(conv_id, client_id)
        cl.user_session.set(_SK_CLIENT_ID, client_id)

        history = cl.user_session.get("history", [])
        current_title = cl.user_session.get("title_set")
        if not current_title:
            update_conversation_title(conv_id, f"Conversation — {client_name}")

        await cl.Message(
            content=f"✅ Saved! This conversation is now linked to **{client_name}**.\n"
                    f"You'll find it in the sidebar **📁 Conversații salvate** →",
            author="Alex 🤖",
        ).send()
        # Refresh sidebar immediately so the new entry appears
        meta = cl.user_session.get("user_meta", {})
        user_id = meta.get("user_id")
        if user_id:
            await _refresh_sidebar(user_id)
    except Exception as e:
        await cl.Message(content=f"Could not link conversation: {e}", author="Alex 🤖").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming broker message — full agentic loop with Claude."""
    history = cl.user_session.get("history", [])

    # ── Project / conversation persistence ────────────────────────────────
    conv_id    = cl.user_session.get(_SK_CONV_ID)
    project_id = cl.user_session.get(_SK_PROJECT_ID)
    client_id  = cl.user_session.get(_SK_CLIENT_ID)
    title_set  = cl.user_session.get(_SK_TITLE_SET, False)

    # Auto-create a conversation on the first message (so nothing is lost)
    if ADMIN_ENABLED and not conv_id and message.content:
        meta       = cl.user_session.get("user_meta", {})
        _user_id   = meta.get("user_id")
        _company_id = meta.get("company_id")
        if _user_id and _company_id:
            try:
                conv = create_conversation(_user_id, project_id)
                conv_id = conv["id"]
                cl.user_session.set(_SK_CONV_ID, conv_id)
            except Exception:
                pass  # non-fatal — conversation won't be saved but chat works

    # Auto-title from the first user message in this conversation
    if conv_id and not title_set and message.content:
        _title = message.content[:50].strip().replace("\n", " ") or "Conversație"
        update_conversation_title(conv_id, _title)
        cl.user_session.set(_SK_TITLE_SET, True)
    # ─────────────────────────────────────────────────────────────────────

    # ── Sidebar shortcut — intercept starter message before Claude sees it ──
    _msg_lower = (message.content or "").strip().lower()
    if _msg_lower == "arată-mi conversațiile salvate" or "conversații salvate" in _msg_lower:
        _meta  = cl.user_session.get("user_meta", {})
        _uid   = _meta.get("user_id")
        if _uid and ADMIN_ENABLED:
            _clients = list_clients_with_conversations(_uid)
            if _clients:
                await _refresh_sidebar(_uid)
                await cl.Message(
                    content="📁 Am deschis panoul **Conversații salvate** în dreapta. "
                            "Poți revedea sau relua orice conversație anterioară.",
                    author="Alex 🤖",
                ).send()
            else:
                await cl.Message(
                    content="Nu ai încă conversații salvate. "
                            "Conversează cu mine și spune-mi *'salvează discuția'* la final.",
                    author="Alex 🤖",
                ).send()
            return
    # ────────────────────────────────────────────────────────────────────────

    # Build user message content (text + any uploaded files)
    user_content = []
    if message.content and message.content.strip():
        user_content.append({"type": "text", "text": message.content})

    # Process any uploaded files inline
    if message.elements:
        for element in message.elements:
            has_data = (getattr(element, "content", None) or getattr(element, "path", None))
            if has_data and hasattr(element, "name"):
                try:
                    async with cl.Step(name=f"📄 Analyzing {element.name}...", type="tool", show_input=False) as step:
                        step.output = "Processing with Claude Vision..."
                        analysis = await process_uploaded_file(element)

                    # Show extracted data with confirmation buttons
                    await cl.Message(
                        content=(
                            f"✅ **Document citit: {element.name}**\n\n"
                            f"{analysis}\n\n"
                            f"---\n"
                            f"⚠️ **Verifică datele de mai sus înainte să continui.** "
                            f"Dacă ceva e greșit (ex: s-a confundat telefonul clinicii cu al clientului), "
                            f"scrie corecția în mesajul următor."
                        ),
                        author="Alex 🤖"
                    ).send()

                    # Ask broker to confirm before proceeding
                    res = await cl.AskActionMessage(
                        content="Datele sunt corecte?",
                        actions=[
                            cl.Action(name="confirm", label="✅ Corect — continuă", payload={"value": "confirm"}),
                            cl.Action(name="edit", label="✏️ Vreau să corectez ceva", payload={"value": "edit"}),
                        ],
                        author="Alex 🤖",
                        timeout=60,
                    ).send()

                    if res and res.get("payload", {}).get("value") == "edit":
                        await cl.Message(
                            content="✏️ Scrie corecția (ex: 'Numele clientului e Ion Popescu, telefonul e 0722111222, nu cel al clinicii').",
                            author="Alex 🤖"
                        ).send()
                        # Add analysis to context but flag that broker will correct it
                        user_content.append({"type": "text", "text": (
                            f"[Document analizat: {element.name}]\n{analysis}\n\n"
                            f"[IMPORTANT: Brokerul va corecta datele în mesajul următor. Asteaptă corecția înainte să cauți sau să creezi clientul.]"
                        )})
                    else:
                        # Confirmed or timeout — proceed with analysis
                        user_content.append({"type": "text", "text": analysis})

                except Exception as e:
                    await cl.Message(
                        content=f"⚠️ Could not process **{element.name}**: {str(e)[:200]}",
                        author="Alex 🤖"
                    ).send()

    if not user_content:
        return

    # ── Shortcut: "show offer" without calling Claude ─────────────────────────
    msg_lower = (message.content or "").lower().strip()
    SHOW_OFFER_TRIGGERS = [
        "sa vad oferta", "să văd oferta", "show offer", "arata oferta", "arată oferta",
        "show me the offer", "view offer", "see offer", "oferta", "show the offer",
        "vreau sa vad", "vreau să văd",
    ]
    if any(t in msg_lower for t in SHOW_OFFER_TRIGGERS):
        last_file = cl.user_session.get("last_offer_file")
        last_content = cl.user_session.get("last_offer_content")
        if last_file and Path(last_file).exists():
            fname = Path(last_file).name
            await cl.Message(
                content=f"📄 **Here is the last generated offer:**",
                elements=[cl.File(name=fname, path=last_file, display="inline")],
                author="Alex 🤖"
            ).send()
            # Also re-send exports
            last_title = cl.user_session.get("last_offer_title", "Offer")
            await send_export_files(last_content, last_title)
            return
        # No cached offer — let Claude handle it normally
    # ─────────────────────────────────────────────────────────────────────────

    history.append({"role": "user", "content": user_content})

    async with cl.Step(name="Alex is thinking...", type="run", show_input=False) as thinking_step:
        thinking_step.output = "Processing your request..."

    final_text = ""
    iterations = 0
    import asyncio as _asyncio

    while iterations < 10:
        iterations += 1

        # Call Claude API (run in thread pool to avoid blocking the event loop)
        response = None
        last_error = None
        for _attempt in range(3):
            try:
                response = await _asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.messages.create(
                        model=MODEL,
                        max_tokens=4096,
                        system=[{
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }],
                        tools=TOOLS,
                        temperature=0.1,
                        messages=history,
                        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                    )
                )
                # Track token usage (includes cache_creation_input_tokens + cache_read_input_tokens)
                if ADMIN_ENABLED and response.usage:
                    _meta = cl.user_session.get("user_meta", {})
                    if _meta.get("user_id"):
                        total_tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
                        record_token_usage(
                            company_id=_meta.get("company_id"),
                            user_id=_meta["user_id"],
                            tokens=total_tokens,
                        )
                break  # success
            except Exception as e:
                last_error = str(e)
                err_lower = last_error.lower()
                if "overloaded" in err_lower or "529" in last_error or "503" in last_error or "429" in last_error:
                    wait_sec = [5, 15, 30][min(_attempt, 2)]
                    await _asyncio.sleep(wait_sec)
                    continue
                # Context too long — trim history and retry
                if "too long" in err_lower or "too many" in err_lower or "400" in last_error:
                    if len(history) > 6:
                        history = history[:2] + history[-4:]
                        cl.user_session.set("history", history)
                        continue
                # Hard error
                await cl.Message(
                    content="Ceva nu a mers cum trebuie. Poți reformula cererea sau încearcă din nou?",
                    author="Alex 🤖"
                ).send()
                return

        if response is None:
            await cl.Message(
                content="⚠️ Serviciul AI este supraîncărcat momentan. Te rog să retrimiti mesajul.",
                author="Alex 🤖"
            ).send()
            return

        # Parse response content blocks
        text_parts = []
        tool_use_blocks = []

        for block in response.content:
            if block.type == "text" and block.text and block.text.strip():
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append(block)

        # Append assistant turn to history
        history.append({"role": "assistant", "content": response.content})

        if not tool_use_blocks:
            final_text = "\n".join(text_parts) if text_parts else ""

            # ── Hallucination guard ────────────────────────────────────────
            # Check if recent history has any tool results (means we already called tools)
            recent_tool_results = [
                msg for msg in history[-4:]
                if msg.get("role") == "user" and
                isinstance(msg.get("content"), list) and
                any(c.get("type") == "tool_result" for c in msg["content"])
            ]
            answer_lower = final_text.lower()
            negative_phrases = [
                "nu am gasit", "nu am găsit", "nu exista", "nu există",
                "not found", "no products", "no results", "cannot find",
                "nu sunt disponibile", "nu s-au gasit", "nu s-au găsit",
                "lipsesc", "indisponibil",
            ]
            has_negative = any(neg in answer_lower for neg in negative_phrases)

            looks_like_hallucination = (
                not recent_tool_results and
                not has_negative and
                any(kw in answer_lower for kw in [
                    "allianz", "generali", "omniasig", "nn asigurari", "groupama",
                    "brd asigurari", "asirom", "uniqa", "signal iduna",
                    "premium anual", "prima anuala", "annual premium",
                    "here are the", "iată produsele", "top health", "top rca",
                    "recommend the", "recomand", "produsele disponibile",
                ]) and
                any(kw in answer_lower for kw in [
                    "health", "rca", "casco", "life", "pad", "cmr", "kfz",
                    "asigurare", "insurance", "polita", "poliță",
                ])
            )
            if looks_like_hallucination:
                # Discard the hallucinated answer and force tool call
                history.pop()  # remove assistant turn with hallucinated text
                history.append({"role": "user", "content": [{
                    "type": "text",
                    "text": (
                        "Nu răspunde din memorie. Apelează imediat broker_search_products "
                        "cu tipul de produs potrivit și arată rezultatele reale din baza de date."
                    )
                }]})
                final_text = ""
                continue  # retry — Claude will now call the tool
            # ────────────────────────────────────────────────────────────────

            # stop_reason == "end_turn" with no tool calls → done
            break

        # ── Execute tool calls ─────────────────────────────────────────────
        tool_results = []

        allowed_tools = cl.user_session.get("allowed_tools")  # None = all allowed
        user_meta = cl.user_session.get("user_meta", {})

        for tb in tool_use_blocks:
            tool_name = tb.name
            tool_input = tb.input if isinstance(tb.input, dict) else {}
            tool_use_id = tb.id

            # ── Permission gate ────────────────────────────────────────────
            if allowed_tools is not None and tool_name not in allowed_tools:
                denied_result = f"⛔ Access denied: you don't have permission to use '{tool_name}'. Contact your admin."
                if ADMIN_ENABLED and user_meta.get("user_id"):
                    log_audit(
                        user_id=user_meta["user_id"],
                        company_id=user_meta.get("company_id"),
                        tool_name=tool_name,
                        input_summary=str(tool_input)[:200],
                        success=False,
                        tokens=0,
                    )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": denied_result,
                })
                continue

            async with cl.Step(name=f"🔧 {tool_name}", type="tool", show_input=True) as step:
                step.input = json.dumps(tool_input, indent=2, ensure_ascii=False)

                # ── Save conversation → link to client ────────────────────
                if tool_name == "broker_save_conversation":
                    _client_id = tool_input.get("client_id", "").strip()
                    _new_title  = tool_input.get("title", "").strip()
                    _conv_id   = cl.user_session.get(_SK_CONV_ID)

                    if not ADMIN_ENABLED or not _client_id:
                        result = "⚠️ Cannot save: admin features disabled or no client_id provided."
                    elif not _conv_id:
                        # No conversation yet — create one now
                        _meta       = cl.user_session.get("user_meta", {})
                        _uid        = _meta.get("user_id")
                        _cid_comp   = _meta.get("company_id")
                        if _uid and _cid_comp:
                            # Find or create a project for this client
                            _projects  = list_projects(_uid)
                            # Try to get client name for project name
                            import sqlite3 as _sq
                            _db_conn = None
                            _client_name = _client_id
                            try:
                                from shared.db import get_conn as _gcn
                                _db_conn = _gcn()
                                _cr = _db_conn.execute("SELECT name FROM clients WHERE id=?", (_client_id,)).fetchone()
                                if _cr:
                                    _client_name = _cr["name"]
                            except Exception:
                                pass
                            finally:
                                if _db_conn:
                                    _db_conn.close()
                            _existing_proj = next((p for p in _projects if p["name"] == _client_name), None)
                            if _existing_proj:
                                _proj_id = _existing_proj["id"]
                            else:
                                try:
                                    _proj = create_project(_uid, _cid_comp, _client_name)
                                    _proj_id = _proj["id"]
                                except Exception:
                                    _proj_id = None
                            _conv = create_conversation(_uid, _proj_id,
                                                        title=_new_title or f"Conversation about {_client_name}")
                            _conv_id = _conv["id"]
                            cl.user_session.set(_SK_CONV_ID,    _conv_id)
                            cl.user_session.set(_SK_PROJECT_ID, _proj_id)
                            cl.user_session.set(_SK_CLIENT_ID,  _client_id)
                            # Save history so far
                            _hist = cl.user_session.get(_SK_HISTORY, [])
                            if _hist:
                                save_conversation_history(_conv_id, _hist)
                            result = f"✅ Conversation created and linked to **{_client_name}** ({_client_id}). It will appear in '📁 Conversation history by client'."
                        else:
                            result = "⚠️ Cannot save: user session not initialized."
                    else:
                        # Conversation exists — just link it
                        try:
                            set_conversation_client(_conv_id, _client_id)
                            cl.user_session.set(_SK_CLIENT_ID, _client_id)
                            if _new_title:
                                update_conversation_title(_conv_id, _new_title)
                                cl.user_session.set(_SK_TITLE_SET, True)
                            # Get client name for friendly message
                            _client_display = _client_id
                            try:
                                from shared.db import get_conn as _gcn2
                                _dc = _gcn2()
                                _cr2 = _dc.execute("SELECT name FROM clients WHERE id=?", (_client_id,)).fetchone()
                                if _cr2:
                                    _client_display = _cr2["name"]
                                _dc.close()
                            except Exception:
                                pass
                            result = f"✅ Conversation linked to **{_client_display}** ({_client_id}). It will appear in '📁 Conversation history by client'."
                        except Exception as _e:
                            result = f"❌ Could not link conversation: {_e}"

                # ── Async computer-use tools ──────────────────────────────
                elif tool_name == "broker_computer_use_status":
                    result = _cu_computer_use_status_fn(**tool_input)
                elif tool_name == "broker_run_task":
                    # Show progress message while waiting
                    connector = tool_input.get("connector", "web_generic")
                    action = tool_input.get("action", "extract")
                    progress_icons = {"cedam": "🚗", "web_generic": "🌐", "desktop_generic": "🖥️"}
                    icon = progress_icons.get(connector, "⚙️")
                    await cl.Message(
                        content=f"{icon} Execut task pe agentul local (`{connector}` / `{action}`)... ⏳",
                        author="Alex 🤖",
                    ).send()
                    result = await _cu_run_task_async(
                        connector=connector,
                        action=action,
                        params=tool_input.get("params", {}),
                        agent_id=tool_input.get("agent_id"),
                        timeout=tool_input.get("timeout", 120),
                        credentials=tool_input.get("credentials", {}),
                    )
                else:
                    result = execute_tool(tool_name, tool_input)

                step.output = result[:1000] + ("…" if len(result) > 1000 else "")

            # ── Audit log ──────────────────────────────────────────────────
            if ADMIN_ENABLED and user_meta.get("user_id"):
                log_audit(
                    user_id=user_meta["user_id"],
                    company_id=user_meta.get("company_id"),
                    tool_name=tool_name,
                    input_summary=str(tool_input)[:200],
                    success=True,
                    tokens=0,
                )

            # Truncate large tool results in history to avoid oversized context
            result_for_history = result[:600] + "\n[...truncated for context...]" if len(result) > 600 else result

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result_for_history,
            })

            # Attach offer file + export options when offer is created
            if tool_name == "broker_create_offer":
                output_files = sorted(OUTPUT_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
                if output_files:
                    latest = output_files[0]
                    offer_content = latest.read_text(encoding="utf-8")
                    base_title = latest.stem

                    cl.user_session.set("last_offer_file", str(latest))
                    cl.user_session.set("last_offer_content", offer_content)
                    cl.user_session.set("last_offer_title", base_title)
                    cl.user_session.set("offer_approved", False)

                    offer_md = offer_content  # already clean markdown

                    # Display offer as nicely formatted markdown
                    await cl.Message(
                        content=offer_md,
                        author="Alex 🤖"
                    ).send()

                    # Clean action bar — 3 options
                    res = await cl.AskActionMessage(
                        content="Ce facem cu oferta?",
                        actions=[
                            cl.Action(name="approve", label="✅ Trimite pe email", payload={"value": "approve"}),
                            cl.Action(name="download", label="📥 Descarcă (PDF / XLSX / DOCX)", payload={"value": "download"}),
                            cl.Action(name="edit", label="✏️ Modifică oferta", payload={"value": "edit"}),
                        ],
                        author="Alex 🤖",
                        timeout=180,
                    ).send()

                    if res:
                        if res.get("payload", {}).get("value") == "approve":
                            cl.user_session.set("offer_approved", True)
                            # Add approval as user message for next iteration
                            tool_results_so_far = list(tool_results)  # capture current list
                            history.append({"role": "user", "content": tool_results_so_far})
                            history.append({"role": "user", "content": [{
                                "type": "text",
                                "text": "Oferta a fost aprobată de broker. Trimite-o pe email clientului folosind broker_send_offer_email."
                            }]})
                            tool_results = []  # already appended above
                            break  # exit tool loop, continue agentic loop
                        elif res.get("payload", {}).get("value") == "download":
                            await send_export_files(offer_content, base_title)
                            cl.user_session.set("history", history)
                            return  # done
                        elif res.get("payload", {}).get("value") == "edit":
                            await cl.Message(
                                content=(
                                    "✏️ **Ce vrei să modifici?** Scrie natural, de exemplu:\n"
                                    "- *'Schimbă valabilitatea la 14 zile'*\n"
                                    "- *'Adaugă o notă despre discount de 10%'*\n"
                                    "- *'Generează în română'*\n"
                                    "- *'Elimină produsul Generali'*"
                                ),
                                author="Alex 🤖"
                            ).send()
                            cl.user_session.set("history", history)
                            return  # wait for broker to type the edit request
                    else:
                        # Timeout — generate exports automatically
                        await send_export_files(offer_content, base_title)
                        cl.user_session.set("history", history)
                        return

            # Attach export for reports
            elif tool_name in ("broker_asf_summary", "broker_bafin_summary"):
                report_type = "ASF" if tool_name == "broker_asf_summary" else "BaFin"
                base_title = f"{report_type}_Report_{date.today().isoformat()}"
                await send_export_files(result, base_title)

        # Append tool results as next user message (Anthropic format)
        if tool_results:
            history.append({"role": "user", "content": tool_results})

    # ── Send final response ────────────────────────────────────────────────
    cl.user_session.set("history", history)

    # Persist conversation history to DB (every conversation with an ID)
    if conv_id and ADMIN_ENABLED:
        try:
            save_conversation_history(conv_id, history)
        except Exception:
            pass  # non-fatal

    if final_text and final_text.strip():
        await cl.Message(content=final_text.strip(), author="Alex 🤖").send()
    # else: tool already sent output (offer file, export, etc.) — no generic message needed

    # ── "Save conversation" nudge (once per session, after 3+ exchanges, no client linked) ──
    # len(history) >= 6: 3 user + 3 assistant messages = 3 full exchanges
    nudge_shown = cl.user_session.get(_SK_SAVE_NUDGE, False)
    if (
        ADMIN_ENABLED
        and conv_id
        and not client_id               # not yet linked to a client
        and not nudge_shown             # show only once per session
        and len(history) >= 6           # at least 3 full exchanges
    ):
        cl.user_session.set(_SK_SAVE_NUDGE, True)
        await cl.Message(
            content="",
            actions=[
                cl.Action(
                    name="save_conv_pick_client",
                    label="💾 Save this conversation to a client",
                    payload={"conv_id": conv_id},
                )
            ],
            author="Alex 🤖",
        ).send()
