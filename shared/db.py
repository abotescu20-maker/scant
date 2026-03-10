"""
Shared database layer — SQLite for dev, upgrade to PostgreSQL for prod.
Handles both admin tables and broker tables in the same DB.
"""
import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
MCP_SERVER_DIR = BASE_DIR / "mcp-server"
DB_PATH = os.environ.get("DB_PATH", str(MCP_SERVER_DIR / "insurance_broker.db"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_admin_tables():
    """Create admin tables if they don't exist. Safe to call on every startup."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            slug        TEXT UNIQUE NOT NULL,
            country     TEXT DEFAULT 'RO',
            is_active   INTEGER DEFAULT 1,
            monthly_token_limit INTEGER DEFAULT 500000,
            plan_tier   TEXT DEFAULT 'starter',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            company_id      TEXT NOT NULL REFERENCES companies(id),
            email           TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name       TEXT,
            role            TEXT DEFAULT 'broker',
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tool_permissions (
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tool_name   TEXT NOT NULL,
            PRIMARY KEY (user_id, tool_name)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT,
            company_id      TEXT,
            tool_name       TEXT NOT NULL,
            input_summary   TEXT,
            success         INTEGER DEFAULT 1,
            tokens_used     INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS token_usage (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  TEXT NOT NULL,
            user_id     TEXT,
            month       TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            UNIQUE(company_id, user_id, month)
        );
    """)
    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> sqlite3.Row | None:
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    conn = get_conn()
    user = conn.execute(
        "SELECT u.*, c.name as company_name, c.monthly_token_limit "
        "FROM users u JOIN companies c ON u.company_id = c.id "
        "WHERE u.id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def get_user_tools(user_id: str, role: str) -> list[str]:
    """Return list of allowed tool names for a user. Superadmin gets all."""
    all_tools = [
        "broker_search_clients", "broker_get_client", "broker_create_client",
        "broker_search_products", "broker_compare_products",
        "broker_create_offer", "broker_list_offers", "broker_send_offer_email",
        "broker_get_renewals_due", "broker_list_policies",
        "broker_log_claim", "broker_get_claim_status",
        "broker_asf_summary", "broker_bafin_summary", "broker_check_rca_validity",
        "broker_cross_sell", "broker_calculate_premium", "broker_compliance_check",
    ]
    if role in ("superadmin", "company_admin"):
        return all_tools
    conn = get_conn()
    rows = conn.execute(
        "SELECT tool_name FROM tool_permissions WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [r["tool_name"] for r in rows]


def log_audit(user_id: str, company_id: str, tool_name: str,
              input_summary: str = "", success: bool = True, tokens: int = 0):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO audit_log (user_id, company_id, tool_name, input_summary, success, tokens_used) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, company_id, tool_name, input_summary[:200], int(success), tokens)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def record_token_usage(company_id: str, user_id: str, tokens: int):
    try:
        from datetime import date
        month = date.today().strftime("%Y-%m")
        conn = get_conn()
        conn.execute("""
            INSERT INTO token_usage (company_id, user_id, month, tokens_used)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(company_id, user_id, month)
            DO UPDATE SET tokens_used = tokens_used + excluded.tokens_used
        """, (company_id, user_id, month, tokens))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_dashboard_data() -> dict:
    conn = get_conn()
    from datetime import date
    month = date.today().strftime("%Y-%m")
    try:
        companies = conn.execute("SELECT COUNT(*) as n FROM companies WHERE is_active=1").fetchone()["n"]
        users = conn.execute("SELECT COUNT(*) as n FROM users WHERE is_active=1").fetchone()["n"]
        tokens_month = conn.execute(
            "SELECT COALESCE(SUM(tokens_used),0) as n FROM token_usage WHERE month=?", (month,)
        ).fetchone()["n"]
        audit_today = conn.execute(
            "SELECT COUNT(*) as n FROM audit_log WHERE DATE(created_at)=DATE('now')"
        ).fetchone()["n"]
        top_tools = conn.execute(
            "SELECT tool_name, COUNT(*) as cnt FROM audit_log "
            "WHERE month(created_at) = ? GROUP BY tool_name ORDER BY cnt DESC LIMIT 5",
            (month,)
        ).fetchall()
    except Exception:
        top_tools = []
        companies = users = tokens_month = audit_today = 0
    finally:
        conn.close()
    return {
        "companies": companies,
        "users": users,
        "tokens_month": tokens_month,
        "audit_today": audit_today,
        "top_tools": [dict(r) for r in top_tools] if top_tools else [],
    }


# Initialize tables on import
init_admin_tables()
