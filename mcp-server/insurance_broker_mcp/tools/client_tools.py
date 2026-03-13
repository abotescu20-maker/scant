"""Client management tools for the Insurance Broker MCP server."""
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Plain callable functions (used by Chainlit UI directly) ────────────────

def search_clients_fn(query: str, limit: int = 10) -> str:
    conn = get_db()
    try:
        q = f"%{query}%"
        rows = conn.execute("""
            SELECT c.*,
                   COUNT(p.id) as active_policies,
                   SUM(CASE WHEN p.currency='EUR' THEN p.annual_premium
                            ELSE p.annual_premium/5.0 END) as total_premium_eur
            FROM clients c
            LEFT JOIN policies p ON p.client_id = c.id AND p.status = 'active'
            WHERE c.name LIKE ? OR c.phone LIKE ? OR c.email LIKE ? OR c.id_number LIKE ?
            GROUP BY c.id
            LIMIT ?
        """, (q, q, q, q, limit)).fetchall()

        if not rows:
            return f"No clients found matching '{query}'. Use broker_create_client to add a new client."

        lines = [f"## Clients matching '{query}'\n",
                 "| ID | Name | Phone | Email | Country | Active Policies | Est. Annual Premium |",
                 "|---|---|---|---|---|---|---|"]
        for r in rows:
            premium = f"€{r['total_premium_eur']:.0f}" if r['total_premium_eur'] else "€0"
            lines.append(
                f"| {r['id']} | {r['name']} | {r['phone']} | {r['email'] or '-'} | "
                f"{r['country']} | {r['active_policies']} | {premium} |"
            )
        return "\n".join(lines)
    finally:
        conn.close()


def get_client_fn(client_id: str) -> str:
    conn = get_db()
    try:
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return f"Client '{client_id}' not found."

        policies = conn.execute(
            "SELECT * FROM policies WHERE client_id = ? ORDER BY end_date ASC", (client_id,)
        ).fetchall()
        claims = conn.execute(
            "SELECT * FROM claims WHERE client_id = ? ORDER BY incident_date DESC LIMIT 5", (client_id,)
        ).fetchall()

        lines = [
            f"## Client Profile: {client['name']}",
            f"- **ID:** {client['id']}",
            f"- **Type:** {client['client_type'].title()}",
            f"- **Country:** {client['country']}",
            f"- **Phone:** {client['phone']}",
            f"- **Email:** {client['email'] or 'N/A'}",
            f"- **Address:** {client['address'] or 'N/A'}",
            f"- **Source:** {client['source'] or 'N/A'}",
            f"- **Notes:** {client['notes'] or 'None'}",
            f"- **Client since:** {client['created_at']}",
            "",
            f"### Active Policies ({len([p for p in policies if p['status'] == 'active'])})",
        ]

        if policies:
            lines.append("| Type | Insurer | Policy No. | Expires | Premium | Status |")
            lines.append("|---|---|---|---|---|---|")
            today = date.today().isoformat()
            for p in policies:
                days_note = ""
                if p['end_date'] >= today and p['status'] == 'active':
                    d = (date.fromisoformat(p['end_date']) - date.today()).days
                    days_note = f" (**{d}d ⚠️**)" if d <= 30 else f" ({d}d)"
                lines.append(
                    f"| {p['policy_type']} | {p['insurer']} | {p['policy_number']} | "
                    f"{p['end_date']}{days_note} | {p['annual_premium']:,.0f} {p['currency']} | {p['status']} |"
                )
        else:
            lines.append("_No policies found._")

        if claims:
            lines += ["", "### Recent Claims"]
            for c in claims:
                lines.append(f"- **{c['incident_date']}** — {c['description'] or 'N/A'} | Status: {c['status']}")

        return "\n".join(lines)
    finally:
        conn.close()


def _fs_sync_client(client_id: str, conn) -> None:
    """Fire-and-forget Firestore sync for a client row."""
    try:
        import sys, os
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from shared.firestore_db import save_client_to_firestore, is_available
        if is_available():
            row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            if row:
                save_client_to_firestore(dict(row))
    except Exception:
        pass  # Firestore sync is best-effort


def update_client_fn(
    client_id: str,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    id_number: Optional[str] = None,
    country: Optional[str] = None,
    client_type: Optional[str] = None,
    source: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    conn = get_db()
    try:
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return f"❌ Client '{client_id}' not found."

        fields = []
        values = []
        for col, val in [
            ("name", name), ("phone", phone), ("email", email),
            ("address", address), ("id_number", id_number),
            ("country", country), ("client_type", client_type),
            ("source", source), ("notes", notes),
        ]:
            if val is not None:
                fields.append(f"{col} = ?")
                values.append(val)

        if not fields:
            return "⚠️ No fields to update provided."

        values.append(client_id)
        conn.execute(f"UPDATE clients SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        _fs_sync_client(client_id, conn)
        return (
            f"✅ **Client updated successfully**\n"
            f"- **ID:** {client_id}\n"
            + (f"- **Name:** {name}\n" if name else "")
            + (f"- **Phone:** {phone}\n" if phone else "")
            + (f"- **Email:** {email}\n" if email else "")
        )
    finally:
        conn.close()


def delete_client_fn(client_id: str) -> str:
    conn = get_db()
    try:
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return f"❌ Client '{client_id}' not found."

        # Check for active policies — don't delete if they exist
        active = conn.execute(
            "SELECT COUNT(*) as cnt FROM policies WHERE client_id = ? AND status = 'active'",
            (client_id,)
        ).fetchone()["cnt"]
        if active > 0:
            return (
                f"⚠️ Cannot delete client **{client['name']}** — they have **{active} active "
                f"{'policy' if active == 1 else 'policies'}**. "
                f"Cancel or expire the policies first, then delete the client."
            )

        client_name = client["name"]
        # Delete related records first (cascade)
        conn.execute("DELETE FROM claims WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM policies WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        # Remove from Firestore
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from shared.firestore_db import delete_client_from_firestore, is_available
            if is_available():
                delete_client_from_firestore(client_id)
        except Exception:
            pass
        return f"🗑️ Client **{client_name}** (ID: {client_id}) deleted successfully."
    finally:
        conn.close()


def create_client_fn(
    name: str,
    phone: str,
    email: Optional[str] = None,
    address: Optional[str] = None,
    id_number: Optional[str] = None,
    country: str = "RO",
    client_type: str = "individual",
    source: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    conn = get_db()
    try:
        client_id = f"CLI{str(uuid.uuid4())[:6].upper()}"
        created_at = date.today().isoformat()
        conn.execute("""
            INSERT INTO clients (id, name, id_number, phone, email, address,
                                 client_type, country, source, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (client_id, name, id_number, phone, email, address,
              client_type, country, source, notes, created_at))
        conn.commit()
        _fs_sync_client(client_id, conn)
        return (
            f"✅ **Client created successfully**\n"
            f"- **ID:** {client_id}\n"
            f"- **Name:** {name}\n"
            f"- **Phone:** {phone}\n"
            f"- **Country:** {country}\n"
            f"- **Created:** {created_at}\n\n"
            f"Use `broker_search_products` to find suitable insurance for this client."
        )
    finally:
        conn.close()


# ── MCP registration (for Claude Code terminal use) ────────────────────────

def register_client_tools(mcp: FastMCP):

    @mcp.tool(name="broker_search_clients",
              description="Search clients by name, phone, email, or ID number.")
    def broker_search_clients(query: str, limit: int = 10) -> str:
        return search_clients_fn(query, limit)

    @mcp.tool(name="broker_get_client",
              description="Get full client profile including all policies and claims.")
    def broker_get_client(client_id: str) -> str:
        return get_client_fn(client_id)

    @mcp.tool(name="broker_create_client",
              description="Create a new client. Required: name, phone. Optional: email, address, country (RO/DE), client_type (individual/company).")
    def broker_create_client(
        name: str, phone: str, email: Optional[str] = None,
        address: Optional[str] = None, id_number: Optional[str] = None,
        country: str = "RO", client_type: str = "individual",
        source: Optional[str] = None, notes: Optional[str] = None
    ) -> str:
        return create_client_fn(name, phone, email, address, id_number,
                                country, client_type, source, notes)

    @mcp.tool(name="broker_update_client",
              description="Update an existing client's details. Only the fields provided will be changed. Use client_id from broker_search_clients.")
    def broker_update_client(
        client_id: str, name: Optional[str] = None, phone: Optional[str] = None,
        email: Optional[str] = None, address: Optional[str] = None,
        id_number: Optional[str] = None, country: Optional[str] = None,
        client_type: Optional[str] = None, source: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        return update_client_fn(client_id, name, phone, email, address,
                                id_number, country, client_type, source, notes)

    @mcp.tool(name="broker_delete_client",
              description="Delete a client and their history. Will refuse if the client has active policies. Use broker_search_clients to get client_id first.")
    def broker_delete_client(client_id: str) -> str:
        return delete_client_fn(client_id)
