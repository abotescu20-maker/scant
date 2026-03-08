"""Policy management tools."""
import sqlite3
from datetime import date
from pathlib import Path
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Plain callable functions ────────────────────────────────────────────────

def get_renewals_due_fn(days_ahead: int = 30) -> str:
    conn = get_db()
    try:
        today = date.today().isoformat()
        rows = conn.execute("""
            SELECT p.*, c.name as client_name, c.phone as client_phone, c.email as client_email
            FROM policies p
            JOIN clients c ON c.id = p.client_id
            WHERE p.status = 'active'
              AND p.end_date BETWEEN ? AND date(?, '+' || ? || ' days')
            ORDER BY p.end_date ASC
        """, (today, today, days_ahead)).fetchall()
        if not rows:
            return f"✅ No policies expiring in the next {days_ahead} days. Portfolio is in good shape!"
        urgent   = [r for r in rows if (date.fromisoformat(r['end_date']) - date.today()).days <= 7]
        attention = [r for r in rows if 7 < (date.fromisoformat(r['end_date']) - date.today()).days <= days_ahead]
        lines = [f"## Policies Expiring in Next {days_ahead} Days\n"]
        if urgent:
            lines.append(f"### 🔴 URGENT — Expiring within 7 days ({len(urgent)} policies)")
            lines.append("| Client | Type | Insurer | Expires | Days Left | Premium |")
            lines.append("|---|---|---|---|---|---|")
            for r in urgent:
                d = (date.fromisoformat(r['end_date']) - date.today()).days
                lines.append(f"| {r['client_name']} | **{r['policy_type']}** | {r['insurer']} | "
                             f"{r['end_date']} | **{d} days** | {r['annual_premium']:,.0f} {r['currency']} |")
        if attention:
            lines.append(f"\n### 🟡 ATTENTION — Expiring 8-{days_ahead} days ({len(attention)} policies)")
            lines.append("| Client | Type | Insurer | Expires | Days Left | Premium |")
            lines.append("|---|---|---|---|---|---|")
            for r in attention:
                d = (date.fromisoformat(r['end_date']) - date.today()).days
                lines.append(f"| {r['client_name']} | {r['policy_type']} | {r['insurer']} | "
                             f"{r['end_date']} | {d} days | {r['annual_premium']:,.0f} {r['currency']} |")
        lines.append(f"\n**Total: {len(rows)} policies to renew.**")
        return "\n".join(lines)
    finally:
        conn.close()


def list_policies_fn(client_id: str = None, status: str = "active") -> str:
    conn = get_db()
    try:
        if client_id:
            rows = conn.execute("""
                SELECT p.*, c.name as client_name FROM policies p
                JOIN clients c ON c.id = p.client_id
                WHERE p.client_id = ? AND p.status = ? ORDER BY p.end_date ASC
            """, (client_id, status)).fetchall()
        else:
            rows = conn.execute("""
                SELECT p.*, c.name as client_name FROM policies p
                JOIN clients c ON c.id = p.client_id
                WHERE p.status = ? ORDER BY p.end_date ASC LIMIT 50
            """, (status,)).fetchall()
        if not rows:
            return "No policies found matching the criteria."
        lines = [f"## Policies (status: {status})\n",
                 "| Client | Type | Insurer | Policy No. | End Date | Premium |",
                 "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['client_name']} | {r['policy_type']} | {r['insurer']} | "
                         f"{r['policy_number']} | {r['end_date']} | {r['annual_premium']:,.0f} {r['currency']} |")
        return "\n".join(lines)
    finally:
        conn.close()


def register_policy_tools(mcp: FastMCP):

    @mcp.tool(name="broker_get_renewals_due",
              description="List policies expiring within the next N days (default 30).")
    def broker_get_renewals_due(days_ahead: int = 30) -> str:
        return get_renewals_due_fn(days_ahead)

    @mcp.tool(name="broker_list_policies",
              description="List all policies for a client or the whole portfolio.")
    def broker_list_policies(client_id: str = None, status: str = "active") -> str:
        return list_policies_fn(client_id, status)
