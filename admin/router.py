"""
Admin panel routes — FastAPI router mounted at /admin
"""
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from shared.db import get_conn, init_admin_tables, get_user_by_email, get_user_tools
from shared.auth import verify_password, create_access_token, decode_token, hash_password, new_id

router = APIRouter()
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ALL_TOOLS = [
    "broker_search_clients", "broker_get_client", "broker_create_client",
    "broker_search_products", "broker_compare_products",
    "broker_create_offer", "broker_list_offers", "broker_send_offer_email",
    "broker_get_renewals_due", "broker_list_policies",
    "broker_log_claim", "broker_get_claim_status",
    "broker_asf_summary", "broker_bafin_summary", "broker_check_rca_validity",
]


def get_current_admin(request: Request) -> Optional[dict]:
    token = request.cookies.get("admin_token")
    if not token:
        return None
    return decode_token(token)


def require_admin(request: Request) -> dict:
    user = get_current_admin(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return user


def require_superadmin(request: Request) -> dict:
    user = require_admin(request)
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")
    return user


# ── Login ──────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@router.post("/login")
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    user = get_user_by_email(email)
    if not user or not verify_password(password, user["hashed_password"]):
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "Invalid email or password"
        })
    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "company_id": user["company_id"],
        "full_name": user["full_name"] or user["email"],
    })
    response = RedirectResponse("/admin/dashboard", status_code=302)
    response.set_cookie("admin_token", token, httponly=True, max_age=28800)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie("admin_token")
    return response


# ── Dashboard ──────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, admin=Depends(require_admin)):
    conn = get_conn()
    month = date.today().strftime("%Y-%m")
    try:
        companies = conn.execute("SELECT COUNT(*) as n FROM companies WHERE is_active=1").fetchone()["n"]
        users = conn.execute("SELECT COUNT(*) as n FROM users WHERE is_active=1").fetchone()["n"]
        tokens = conn.execute(
            "SELECT COALESCE(SUM(tokens_used),0) as n FROM token_usage WHERE month=?", (month,)
        ).fetchone()["n"]
        audit_today = conn.execute(
            "SELECT COUNT(*) as n FROM audit_log WHERE DATE(created_at)=DATE('now')"
        ).fetchone()["n"]
        recent_audit = conn.execute(
            "SELECT a.*, u.email as user_email FROM audit_log a "
            "LEFT JOIN users u ON a.user_id = u.id "
            "ORDER BY a.id DESC LIMIT 10"
        ).fetchall()
        top_tools = conn.execute(
            "SELECT tool_name, COUNT(*) as cnt FROM audit_log "
            "GROUP BY tool_name ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "current_user": admin,
        "active_page": "dashboard",
        "stats": {
            "companies": companies,
            "active_users": users,
            "total_users": users,
            "tokens_this_month": tokens,
            "calls_today": audit_today,
        },
        "recent_audit": [dict(r) | {"email": r["user_email"]} for r in recent_audit],
        "company_usage": [],
    })


# ── Companies ──────────────────────────────────────────────────────────────

@router.get("/companies", response_class=HTMLResponse)
async def companies_list(request: Request, admin=Depends(require_superadmin)):
    conn = get_conn()
    companies = conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM users u WHERE u.company_id=c.id) as user_count "
        "FROM companies c ORDER BY c.created_at DESC"
    ).fetchall()
    conn.close()
    return templates.TemplateResponse("companies.html", {
        "request": request, "current_user": admin,
        "active_page": "companies",
        "companies": [dict(c) for c in companies],
    })


@router.post("/companies/create")
async def company_create(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    country: str = Form("RO"),
    plan_tier: str = Form("starter"),
    admin=Depends(require_superadmin)
):
    company_id = new_id("COMP")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO companies (id, name, slug, country, plan_tier) VALUES (?, ?, ?, ?, ?)",
            (company_id, name, slug.lower().replace(" ", "-"), country, plan_tier)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return RedirectResponse("/admin/companies?error=slug_taken", status_code=302)
    conn.close()
    return RedirectResponse("/admin/companies", status_code=302)


@router.post("/companies/{company_id}/toggle")
async def company_toggle(company_id: str, admin=Depends(require_superadmin)):
    conn = get_conn()
    conn.execute(
        "UPDATE companies SET is_active = 1 - is_active WHERE id = ?", (company_id,)
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/companies", status_code=302)


# ── Users ──────────────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, admin=Depends(require_admin)):
    conn = get_conn()
    if admin["role"] == "superadmin":
        users = conn.execute(
            "SELECT u.*, c.name as company_name FROM users u "
            "JOIN companies c ON u.company_id = c.id ORDER BY u.created_at DESC"
        ).fetchall()
        companies = conn.execute("SELECT * FROM companies WHERE is_active=1").fetchall()
    else:
        users = conn.execute(
            "SELECT u.*, c.name as company_name FROM users u "
            "JOIN companies c ON u.company_id = c.id WHERE u.company_id=? ORDER BY u.created_at DESC",
            (admin["company_id"],)
        ).fetchall()
        companies = conn.execute(
            "SELECT * FROM companies WHERE id=?", (admin["company_id"],)
        ).fetchall()
    conn.close()
    return templates.TemplateResponse("users.html", {
        "request": request, "current_user": admin,
        "active_page": "users",
        "users": [dict(u) for u in users],
        "companies": [dict(c) for c in companies],
        "all_tools": ALL_TOOLS,
    })


@router.post("/users/create")
async def user_create(
    request: Request,
    company_id: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    role: str = Form("broker"),
    admin=Depends(require_admin)
):
    # company_admin can only create users for their own company
    if admin["role"] == "company_admin":
        company_id = admin["company_id"]

    user_id = new_id("USR")
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (id, company_id, email, hashed_password, full_name, role) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, company_id, email, hash_password(password), full_name, role)
        )
        # Give broker default read-only tools
        if role == "broker":
            default_tools = ["broker_search_clients", "broker_get_client", "broker_list_policies",
                             "broker_get_renewals_due", "broker_check_rca_validity"]
            for tool in default_tools:
                conn.execute(
                    "INSERT OR IGNORE INTO tool_permissions (user_id, tool_name) VALUES (?, ?)",
                    (user_id, tool)
                )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return RedirectResponse("/admin/users?error=email_taken", status_code=302)
    conn.close()
    return RedirectResponse("/admin/users", status_code=302)


@router.post("/users/{user_id}/toggle")
async def user_toggle(user_id: str, admin=Depends(require_admin)):
    conn = get_conn()
    conn.execute("UPDATE users SET is_active = 1 - is_active WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/users", status_code=302)


# ── Permissions ────────────────────────────────────────────────────────────

@router.get("/permissions/{user_id}", response_class=HTMLResponse)
async def permissions_page(user_id: str, request: Request, admin=Depends(require_admin)):
    conn = get_conn()
    user = conn.execute(
        "SELECT u.*, c.name as company_name FROM users u "
        "JOIN companies c ON u.company_id=c.id WHERE u.id=?", (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        raise HTTPException(404, "User not found")
    current_tools = [r["tool_name"] for r in conn.execute(
        "SELECT tool_name FROM tool_permissions WHERE user_id=?", (user_id,)
    ).fetchall()]
    conn.close()
    return templates.TemplateResponse("permissions.html", {
        "request": request, "current_user": admin,
        "active_page": "permissions",
        "target_user": dict(user),
        "all_tools": ALL_TOOLS,
        "user_tools": current_tools,
    })


@router.post("/permissions/{user_id}/save")
async def permissions_save(user_id: str, request: Request, admin=Depends(require_admin)):
    form = await request.form()
    selected_tools = [k for k in form.keys() if k in ALL_TOOLS]
    conn = get_conn()
    conn.execute("DELETE FROM tool_permissions WHERE user_id=?", (user_id,))
    for tool in selected_tools:
        conn.execute(
            "INSERT INTO tool_permissions (user_id, tool_name) VALUES (?, ?)", (user_id, tool)
        )
    conn.commit()
    conn.close()
    return RedirectResponse(f"/admin/permissions/{user_id}?saved=1", status_code=302)


# ── Audit Log ──────────────────────────────────────────────────────────────

@router.get("/audit", response_class=HTMLResponse)
async def audit_log(
    request: Request,
    admin=Depends(require_admin),
    page: int = 1,
    user_filter: str = "",
    tool_filter: str = "",
    status_filter: str = "",
):
    per_page = 50
    offset = (page - 1) * per_page
    conn = get_conn()

    where_clauses = []
    params = []

    if admin["role"] != "superadmin":
        where_clauses.append("a.company_id=?")
        params.append(admin["company_id"])
    if user_filter:
        where_clauses.append("u.email LIKE ?")
        params.append(f"%{user_filter}%")
    if tool_filter:
        where_clauses.append("a.tool_name LIKE ?")
        params.append(f"%{tool_filter}%")
    if status_filter in ("0", "1"):
        where_clauses.append("a.success=?")
        params.append(int(status_filter))

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    rows = conn.execute(
        f"SELECT a.*, u.email as user_email FROM audit_log a "
        f"LEFT JOIN users u ON a.user_id=u.id "
        f"{where_sql} ORDER BY a.id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) as n FROM audit_log a LEFT JOIN users u ON a.user_id=u.id {where_sql}",
        params
    ).fetchone()["n"]
    conn.close()
    return templates.TemplateResponse("audit.html", {
        "request": request, "current_user": admin,
        "active_page": "audit",
        "rows": [dict(r) | {"email": r["user_email"]} for r in rows],
        "current_page": page,
        "offset": offset,
        "total": total,
        "page_size": per_page,
        "user_filter": request.query_params.get("user_filter", ""),
        "tool_filter": request.query_params.get("tool_filter", ""),
        "status_filter": request.query_params.get("status_filter", ""),
    })


# ── Root redirect ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def admin_root(request: Request):
    user = get_current_admin(request)
    if user:
        return RedirectResponse("/admin/dashboard", status_code=302)
    return RedirectResponse("/admin/login", status_code=302)
