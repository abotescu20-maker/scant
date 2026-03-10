"""
Shared database layer — SQLite for dev, upgrade to PostgreSQL for prod.
Handles both admin tables and broker tables in the same DB.
"""
import json
import sqlite3
import os
import uuid
from datetime import datetime
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

        -- ── Projects & persistent conversations ──────────────────────────────
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company_id  TEXT    NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, name)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          TEXT    PRIMARY KEY,
            user_id     TEXT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL,
            client_id   TEXT    REFERENCES clients(id) ON DELETE SET NULL,
            title       TEXT    NOT NULL DEFAULT 'Conversație nouă',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversation_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT    NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            history_json    TEXT    NOT NULL,
            message_count   INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(conversation_id)
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_user_project
            ON conversations(user_id, project_id);
        CREATE INDEX IF NOT EXISTS idx_projects_user
            ON projects(user_id);
    """)
    conn.commit()

    # ── Migration: add client_id column if missing (safe to run on existing DB) ──
    try:
        conn.execute("ALTER TABLE conversations ADD COLUMN client_id TEXT REFERENCES clients(id) ON DELETE SET NULL")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists — that's fine

    # ── Index on client_id (after migration so column is guaranteed to exist) ──
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_client ON conversations(user_id, client_id)")
        conn.commit()
    except sqlite3.OperationalError:
        pass

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


# ── Projects & persistent conversations ──────────────────────────────────────

class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles non-serialisable types gracefully."""
    def default(self, obj):
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        return str(obj)


def create_project(user_id: str, company_id: str, name: str,
                   description: str | None = None) -> dict:
    """Create a new project. Raises sqlite3.IntegrityError on duplicate name."""
    conn = get_conn()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO projects (user_id, company_id, name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, company_id, name.strip()[:100], description, now, now),
    )
    conn.commit()
    project_id = cur.lastrowid
    conn.close()
    return {"id": project_id, "user_id": user_id, "company_id": company_id,
            "name": name, "description": description, "created_at": now}


def list_projects(user_id: str) -> list[dict]:
    """Return all projects for a user, newest first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, description, created_at, updated_at "
        "FROM projects WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_conversation(user_id: str, project_id: int | None,
                        conversation_id: str | None = None,
                        title: str = "Conversație nouă") -> dict:
    """Create a conversation row. Returns dict with the conversation id."""
    conn = get_conn()
    cid = conversation_id or str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO conversations (id, user_id, project_id, title, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (cid, user_id, project_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": cid, "user_id": user_id, "project_id": project_id, "title": title}


def list_conversations(user_id: str, project_id: int | None) -> list[dict]:
    """Return conversations for a user in a given project, newest first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at "
        "FROM conversations WHERE user_id = ? AND project_id IS ? "
        "ORDER BY updated_at DESC LIMIT 50",
        (user_id, project_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_conversation_title(conversation_id: str, title: str) -> None:
    """Update conversation title (called after first user message)."""
    conn = get_conn()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
        (title[:80], conversation_id),
    )
    conn.commit()
    conn.close()


def save_conversation_history(conversation_id: str, history: list[dict]) -> None:
    """Upsert the full Anthropic message history for a conversation.

    history is the list stored in cl.user_session["history"]:
        [{"role": "user"|"assistant", "content": str | list[dict]}, ...]
    """
    conn = get_conn()
    history_json = json.dumps(history, cls=_SafeEncoder, ensure_ascii=False)
    conn.execute(
        """INSERT INTO conversation_messages (conversation_id, history_json, message_count, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(conversation_id) DO UPDATE SET
               history_json  = excluded.history_json,
               message_count = excluded.message_count,
               updated_at    = excluded.updated_at""",
        (conversation_id, history_json, len(history)),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
        (conversation_id,),
    )
    conn.commit()
    conn.close()


def load_conversation_history(conversation_id: str) -> list[dict]:
    """Load and deserialize the full Anthropic message history.
    Returns an empty list if no history has been saved yet."""
    conn = get_conn()
    row = conn.execute(
        "SELECT history_json FROM conversation_messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return []
    return json.loads(row["history_json"])


def set_conversation_client(conversation_id: str, client_id: str) -> None:
    """Associate a conversation with a client (can be called any time during chat)."""
    conn = get_conn()
    conn.execute(
        "UPDATE conversations SET client_id = ?, updated_at = datetime('now') WHERE id = ?",
        (client_id, conversation_id),
    )
    conn.commit()
    conn.close()


def list_clients_with_conversations(user_id: str) -> list[dict]:
    """Return clients that have at least one saved conversation for this user.
    Each entry: {client_id, client_name, conv_count, last_conv_at}
    Ordered by most recent conversation first.
    Also includes an '__unlinked__' entry if there are conversations without a client.
    """
    conn = get_conn()
    # Clients with linked conversations
    # Note: clients table uses 'name' column (not 'full_name')
    rows = conn.execute(
        """
        SELECT
            cl.id        AS client_id,
            cl.name      AS client_name,
            COUNT(c.id)  AS conv_count,
            MAX(c.updated_at) AS last_conv_at
        FROM conversations c
        JOIN clients cl ON cl.id = c.client_id
        WHERE c.user_id = ?
        GROUP BY cl.id
        ORDER BY last_conv_at DESC
        LIMIT 40
        """,
        (user_id,),
    ).fetchall()

    result = [dict(r) for r in rows]

    # Conversations without a client
    unlinked = conn.execute(
        """
        SELECT COUNT(*) AS cnt, MAX(updated_at) AS last_at
        FROM conversations
        WHERE user_id = ? AND client_id IS NULL
        """,
        (user_id,),
    ).fetchone()
    conn.close()

    if unlinked and unlinked["cnt"] > 0:
        result.append({
            "client_id": "__unlinked__",
            "client_name": "💬 Temporary / not linked",
            "conv_count": unlinked["cnt"],
            "last_conv_at": unlinked["last_at"],
        })

    return result


def list_conversations_for_client(user_id: str, client_id: str | None) -> list[dict]:
    """Return conversations for a user linked to a specific client (or unlinked).
    Pass client_id='__unlinked__' to get conversations with no client set.
    """
    conn = get_conn()
    if client_id == "__unlinked__" or client_id is None:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COALESCE(cm.message_count, 0) AS message_count
            FROM conversations c
            LEFT JOIN conversation_messages cm ON cm.conversation_id = c.id
            WHERE c.user_id = ? AND c.client_id IS NULL
            ORDER BY c.updated_at DESC LIMIT 30
            """,
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COALESCE(cm.message_count, 0) AS message_count
            FROM conversations c
            LEFT JOIN conversation_messages cm ON cm.conversation_id = c.id
            WHERE c.user_id = ? AND c.client_id = ?
            ORDER BY c.updated_at DESC LIMIT 30
            """,
            (user_id, client_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_clients_for_picker() -> list[dict]:
    """Return all clients — used when creating a new conversation
    to let the broker pick which client it's about."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, client_type FROM clients ORDER BY name LIMIT 50",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize tables on import
init_admin_tables()
