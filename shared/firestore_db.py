"""
Firebase Firestore persistence layer for Insurance Broker Alex.

Strategia de migrare:
  - SQLite rămâne pentru datele broker (clients, policies, products, etc.)
    acestea se re-seed din JSON-uri la fiecare deploy → nu necesită persistare
  - Firestore stochează datele care se pierd la Cloud Run restart:
    * users + companies + tool_permissions (set-up o dată)
    * conversations + conversation_messages (istoria chat-ului)
    * projects (grupuri de conversații)
    * audit_log / token_usage (opțional, pentru statistici lunare)

Fallback graceful: dacă Firestore nu e disponibil, toate operațiile
revin la SQLite (nicio funcționalitate pierdută, dar fără persistare cross-deploy).
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("firestore_db")

# ── Lazy initialization ──────────────────────────────────────────────────────

_db = None          # Firestore client
_enabled = False    # True only after successful init


def _init():
    """Try to initialize Firestore. Called lazily on first use."""
    global _db, _enabled
    if _db is not None:
        return _enabled

    try:
        from google.cloud import firestore
        # On Cloud Run: uses Application Default Credentials automatically
        # Locally: uses GOOGLE_APPLICATION_CREDENTIALS or gcloud auth
        project_id = os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            os.environ.get("GCLOUD_PROJECT", "gen-lang-client-0167987852")
        )
        _db = firestore.Client(project=project_id)
        # Quick connectivity check
        _db.collection("_health").document("ping").set({"ts": datetime.utcnow().isoformat()})
        _enabled = True
        log.info("Firestore initialized ✓ (project=%s)", project_id)
    except Exception as e:
        log.warning("Firestore not available — falling back to SQLite only. Reason: %s", e)
        _enabled = False

    return _enabled


def is_available() -> bool:
    """Return True if Firestore is reachable."""
    return _init()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _col(name: str):
    """Return a Firestore CollectionReference."""
    _init()
    if not _enabled:
        raise RuntimeError("Firestore not available")
    return _db.collection(name)


def _now() -> str:
    return datetime.utcnow().isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# USERS & COMPANIES
# ═══════════════════════════════════════════════════════════════════════════════

def sync_company_to_firestore(company: dict) -> bool:
    """Upsert a company document. Returns True on success."""
    try:
        _col("companies").document(company["id"]).set(company, merge=True)
        return True
    except Exception as e:
        log.warning("sync_company_to_firestore failed: %s", e)
        return False


def sync_user_to_firestore(user: dict) -> bool:
    """Upsert a user document (includes hashed_password — kept server-side only)."""
    try:
        doc = dict(user)
        doc.pop("hashed_password", None)   # never store plain password
        _col("users").document(doc["id"]).set(doc, merge=True)
        return True
    except Exception as e:
        log.warning("sync_user_to_firestore failed: %s", e)
        return False


def get_user_from_firestore(user_id: str) -> Optional[dict]:
    """Fetch a user document by ID. Returns None if not found."""
    try:
        doc = _col("users").document(user_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        log.warning("get_user_from_firestore failed: %s", e)
        return None


def list_users_from_firestore(company_id: str) -> list[dict]:
    """Return all active users for a company."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = _col("users").where(
            filter=FieldFilter("company_id", "==", company_id)
        ).stream()
        return [d.to_dict() for d in docs]
    except Exception as e:
        log.warning("list_users_from_firestore failed: %s", e)
        return []


def sync_tool_permissions_to_firestore(user_id: str, tool_names: list[str]) -> bool:
    """Store the full list of allowed tools for a user."""
    try:
        _col("tool_permissions").document(user_id).set({
            "user_id": user_id,
            "tools": tool_names,
            "updated_at": _now(),
        })
        return True
    except Exception as e:
        log.warning("sync_tool_permissions_to_firestore failed: %s", e)
        return False


def get_tool_permissions_from_firestore(user_id: str) -> Optional[list[str]]:
    """Return list of allowed tools, or None if not found."""
    try:
        doc = _col("tool_permissions").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("tools", [])
        return None
    except Exception as e:
        log.warning("get_tool_permissions_from_firestore failed: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ═══════════════════════════════════════════════════════════════════════════════

def save_project_to_firestore(project: dict) -> bool:
    """Upsert a project. Uses str(id) as document key."""
    try:
        doc_id = str(project["id"])
        _col("projects").document(doc_id).set(project, merge=True)
        return True
    except Exception as e:
        log.warning("save_project_to_firestore failed: %s", e)
        return False


def list_projects_from_firestore(user_id: str) -> list[dict]:
    """Return projects for a user, ordered by updated_at DESC."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        from google.cloud.firestore_v1 import query as fsq
        docs = (
            _col("projects")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .order_by("updated_at", direction="DESCENDING")
            .limit(50)
            .stream()
        )
        return [d.to_dict() for d in docs]
    except Exception as e:
        log.warning("list_projects_from_firestore failed: %s", e)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def save_conversation_to_firestore(conv: dict) -> bool:
    """Upsert a conversation metadata document."""
    try:
        _col("conversations").document(conv["id"]).set(conv, merge=True)
        return True
    except Exception as e:
        log.warning("save_conversation_to_firestore failed: %s", e)
        return False


def list_conversations_from_firestore(user_id: str, project_id=None) -> list[dict]:
    """Return conversations for a user (optionally filtered by project)."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = _col("conversations").where(filter=FieldFilter("user_id", "==", user_id))
        if project_id is not None:
            q = q.where(filter=FieldFilter("project_id", "==", project_id))
        docs = q.order_by("updated_at", direction="DESCENDING").limit(50).stream()
        return [d.to_dict() for d in docs]
    except Exception as e:
        log.warning("list_conversations_from_firestore failed: %s", e)
        return []


def update_conversation_title_firestore(conversation_id: str, title: str) -> bool:
    """Update conversation title in Firestore."""
    try:
        _col("conversations").document(conversation_id).update({
            "title": title[:80],
            "updated_at": _now(),
        })
        return True
    except Exception as e:
        log.warning("update_conversation_title_firestore failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION MESSAGES (HISTORY)
# ═══════════════════════════════════════════════════════════════════════════════

def save_history_to_firestore(conversation_id: str, history: list[dict]) -> bool:
    """
    Persist the full Anthropic message history to Firestore.
    Stored as: conversations/{conversation_id}/messages/history
    """
    try:
        history_json = json.dumps(history, ensure_ascii=False, default=str)
        _col("conversation_messages").document(conversation_id).set({
            "conversation_id": conversation_id,
            "history_json": history_json,
            "message_count": len(history),
            "updated_at": _now(),
        })
        # Also bump parent conversation updated_at
        _col("conversations").document(conversation_id).set(
            {"updated_at": _now()}, merge=True
        )
        return True
    except Exception as e:
        log.warning("save_history_to_firestore failed: %s", e)
        return False


def load_history_from_firestore(conversation_id: str) -> list[dict]:
    """
    Load the full Anthropic message history from Firestore.
    Returns [] if not found.
    """
    try:
        doc = _col("conversation_messages").document(conversation_id).get()
        if not doc.exists:
            return []
        data = doc.to_dict()
        history_json = data.get("history_json", "[]")
        return json.loads(history_json)
    except Exception as e:
        log.warning("load_history_from_firestore failed: %s", e)
        return []


def delete_conversation_from_firestore(conversation_id: str) -> bool:
    """Delete conversation + its messages from Firestore."""
    try:
        _col("conversations").document(conversation_id).delete()
        _col("conversation_messages").document(conversation_id).delete()
        return True
    except Exception as e:
        log.warning("delete_conversation_from_firestore failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG (Firestore mirror — optional, for cross-deploy stats)
# ═══════════════════════════════════════════════════════════════════════════════

def log_audit_to_firestore(user_id: str, company_id: str, tool_name: str,
                            input_summary: str = "", success: bool = True,
                            tokens: int = 0) -> bool:
    """Append an audit entry to Firestore (fire-and-forget)."""
    try:
        _col("audit_log").add({
            "user_id": user_id,
            "company_id": company_id,
            "tool_name": tool_name,
            "input_summary": input_summary[:200],
            "success": success,
            "tokens_used": tokens,
            "created_at": _now(),
        })
        return True
    except Exception as e:
        log.warning("log_audit_to_firestore failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# SYNC UTILITIES (run once to migrate existing data)
# ═══════════════════════════════════════════════════════════════════════════════

def sync_all_users_and_companies() -> dict:
    """
    One-time sync: read all users+companies from SQLite and push to Firestore.
    Returns: {"companies": N, "users": N, "errors": N}
    """
    if not is_available():
        return {"error": "Firestore not available"}

    from shared.db import get_conn
    conn = get_conn()
    stats = {"companies": 0, "users": 0, "errors": 0}

    try:
        companies = conn.execute("SELECT * FROM companies").fetchall()
        for c in companies:
            if sync_company_to_firestore(dict(c)):
                stats["companies"] += 1
            else:
                stats["errors"] += 1

        users = conn.execute("SELECT * FROM users").fetchall()
        for u in users:
            user_dict = dict(u)
            # Sync tool permissions too
            perms = conn.execute(
                "SELECT tool_name FROM tool_permissions WHERE user_id = ?",
                (user_dict["id"],)
            ).fetchall()
            user_dict["tool_names"] = [p["tool_name"] for p in perms]
            if sync_user_to_firestore(user_dict):
                stats["users"] += 1
            else:
                stats["errors"] += 1
    finally:
        conn.close()

    return stats


def sync_all_conversations() -> dict:
    """
    One-time sync: push all SQLite conversations + histories to Firestore.
    Returns: {"conversations": N, "with_history": N, "errors": N}
    """
    if not is_available():
        return {"error": "Firestore not available"}

    from shared.db import get_conn
    conn = get_conn()
    stats = {"conversations": 0, "with_history": 0, "errors": 0}

    try:
        convs = conn.execute("SELECT * FROM conversations").fetchall()
        for c in convs:
            conv_dict = dict(c)
            if save_conversation_to_firestore(conv_dict):
                stats["conversations"] += 1
            else:
                stats["errors"] += 1

            # Load history
            msg_row = conn.execute(
                "SELECT history_json FROM conversation_messages WHERE conversation_id = ?",
                (conv_dict["id"],)
            ).fetchone()
            if msg_row:
                history = json.loads(msg_row["history_json"])
                if save_history_to_firestore(conv_dict["id"], history):
                    stats["with_history"] += 1
    finally:
        conn.close()

    return stats


def restore_from_firestore_to_sqlite() -> dict:
    """
    Restore users, companies, and conversations from Firestore back to SQLite.
    Used on fresh Cloud Run container startup.
    Returns stats dict.
    """
    if not is_available():
        return {"error": "Firestore not available"}

    from shared.db import get_conn
    import sqlite3 as _sqlite3

    conn = get_conn()
    # Temporarily disable foreign keys for restore — seed_users runs first
    # and ensures users exist, but conversation FK check during restore is safe to skip
    conn.execute("PRAGMA foreign_keys=OFF")
    stats = {
        "companies_restored": 0,
        "users_restored": 0,
        "conversations_restored": 0,
        "histories_restored": 0,
        "errors": 0,
    }

    try:
        # ── Companies ─────────────────────────────────────────────────────────
        companies = _col("companies").stream()
        for doc in companies:
            c = doc.to_dict()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO companies
                        (id, name, slug, country, is_active, monthly_token_limit, plan_tier, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.get("id"), c.get("name"), c.get("slug"),
                    c.get("country", "RO"), c.get("is_active", 1),
                    c.get("monthly_token_limit", 500000),
                    c.get("plan_tier", "starter"), c.get("created_at", _now()),
                ))
                stats["companies_restored"] += 1
            except Exception as e:
                log.warning("Restore company %s: %s", c.get("id"), e)
                stats["errors"] += 1
        conn.commit()

        # ── Users ─────────────────────────────────────────────────────────────
        # Note: hashed_password is NOT in Firestore (for security)
        # We use the SQLite version from seed_users if it exists
        # Only restore users that don't already exist in SQLite
        users_from_firestore = list(_col("users").stream())  # type: ignore
        existing_user_ids = {
            row["id"] for row in conn.execute("SELECT id FROM users").fetchall()
        }

        for doc in users_from_firestore:
            u = doc.to_dict()
            if u.get("id") in existing_user_ids:
                # User already in SQLite — just sync is_active/role
                try:
                    conn.execute(
                        "UPDATE users SET is_active=?, role=?, full_name=? WHERE id=?",
                        (u.get("is_active", 1), u.get("role", "broker"),
                         u.get("full_name"), u.get("id"))
                    )
                    stats["users_restored"] += 1
                except Exception as e:
                    log.warning("Update user %s: %s", u.get("id"), e)
                    stats["errors"] += 1
        conn.commit()

        # ── Conversations ──────────────────────────────────────────────────────
        convs = _col("conversations").stream()
        for doc in convs:
            c = doc.to_dict()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO conversations
                        (id, user_id, project_id, client_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    c.get("id"), c.get("user_id"), c.get("project_id"),
                    c.get("client_id"), c.get("title", "Conversație nouă"),
                    c.get("created_at", _now()), c.get("updated_at", _now()),
                ))
                stats["conversations_restored"] += 1
            except Exception as e:
                log.warning("Restore conversation %s: %s", c.get("id"), e)
                stats["errors"] += 1
        conn.commit()

        # ── Conversation histories ─────────────────────────────────────────────
        msgs = _col("conversation_messages").stream()
        for doc in msgs:
            m = doc.to_dict()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO conversation_messages
                        (conversation_id, history_json, message_count, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    m.get("conversation_id"), m.get("history_json", "[]"),
                    m.get("message_count", 0), m.get("updated_at", _now()),
                ))
                stats["histories_restored"] += 1
            except Exception as e:
                log.warning("Restore history %s: %s", m.get("conversation_id"), e)
                stats["errors"] += 1
        conn.commit()

    except Exception as e:
        log.error("restore_from_firestore_to_sqlite failed: %s", e)
        stats["errors"] += 1
    finally:
        conn.execute("PRAGMA foreign_keys=ON")  # re-enable FK checks
        conn.close()

    log.info("Restore from Firestore complete: %s", stats)
    return stats
