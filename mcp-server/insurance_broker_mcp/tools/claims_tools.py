"""Claims management tools."""
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

# Claims guidance per insurer
CLAIMS_GUIDANCE = {
    "Allianz-Tiriac Asigurari": {
        "phone": "021 302 71 71 (24/7)",
        "portal": "https://www.allianz-tiriac.ro/daune",
        "avg_days": 14,
        "tip": "Allianz has cashless repair at 300+ workshops. Report online for fastest processing."
    },
    "Generali Romania": {
        "phone": "021 302 75 00",
        "portal": "https://www.generali.ro/daune",
        "avg_days": 14,
        "tip": "Generali requires police report for claims over 5,000 RON."
    },
    "Omniasig Vienna Insurance Group": {
        "phone": "021 405 73 00",
        "portal": "https://www.omniasig.ro/daune",
        "avg_days": 18,
        "tip": "VIG group: strong claims support for commercial lines."
    },
    "Allianz Deutschland": {
        "phone": "+49 89 3800 0",
        "portal": "https://www.allianz.de/schaden",
        "avg_days": 10,
        "tip": "Report within 7 days as per VVG requirement. Online portal fastest."
    },
    "AXA Versicherung": {
        "phone": "+49 221 148 0",
        "portal": "https://www.axa.de/schaden",
        "avg_days": 12,
        "tip": "AXA digital claims: photo upload via app reduces processing time."
    },
    "DEFAULT": {
        "phone": "Check policy document for 24/7 claims hotline",
        "portal": "Check insurer website",
        "avg_days": 21,
        "tip": "Always report within 24-48 hours of incident."
    }
}


def log_claim_fn(
    client_id: str,
    policy_id: str,
    incident_date: str,
    description: str,
    damage_estimate: Optional[float] = None,
    notes: Optional[str] = None
) -> str:
    """Register a new claim in the system."""
    conn = get_db()
    try:
        client = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        policy = conn.execute("SELECT * FROM policies WHERE id=?", (policy_id,)).fetchone()

        if not client or not policy:
            return "Client or policy not found. Please verify IDs."

        claim_id = f"CLM{str(uuid.uuid4())[:6].upper()}"
        conn.execute("""
            INSERT INTO claims (id, client_id, policy_id, incident_date, reported_date,
                                description, status, damage_estimate, notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (claim_id, client_id, policy_id, incident_date, date.today().isoformat(),
              description, "open", damage_estimate, notes))
        conn.commit()

        # Sync to Firestore
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from shared.firestore_db import save_claim_to_firestore, is_available
            if is_available():
                row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
                if row:
                    save_claim_to_firestore(dict(row))
        except Exception:
            pass

        guidance = CLAIMS_GUIDANCE.get(policy['insurer'], CLAIMS_GUIDANCE["DEFAULT"])

        return (
            f"✅ **Claim Logged Successfully**\n"
            f"- **Claim ID:** {claim_id}\n"
            f"- **Client:** {client['name']}\n"
            f"- **Policy:** {policy['policy_type']} — {policy['policy_number']}\n"
            f"- **Insurer:** {policy['insurer']}\n"
            f"- **Incident Date:** {incident_date}\n"
            "- **Damage Estimate:** " + (f"{damage_estimate:,.0f} {policy['currency']}" if damage_estimate else "TBD") + "\n\n"
            f"### Next Steps — {policy['insurer']}\n"
            f"1. **Call:** {guidance['phone']}\n"
            f"2. **Online portal:** {guidance['portal']}\n"
            f"3. **Avg processing time:** {guidance['avg_days']} business days\n"
            f"4. **Tip:** {guidance['tip']}\n\n"
            f"### Documents Required\n"
            f"- Identity document (ID/Passport)\n"
            f"- Policy document ({policy['policy_number']})\n"
            f"- Incident photos (min. 5 photos from different angles)\n"
            f"- Police report (if applicable)\n"
            f"- Amicable accident report (if motor accident with other party)"
        )
    finally:
        conn.close()


def get_claim_status_fn(claim_id: str) -> str:
    """Get claim status."""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT cl.*, c.name as client_name, p.policy_type, p.insurer, p.policy_number
            FROM claims cl
            JOIN clients c ON c.id = cl.client_id
            JOIN policies p ON p.id = cl.policy_id
            WHERE cl.id = ?
        """, (claim_id,)).fetchone()

        if not row:
            return f"Claim '{claim_id}' not found."

        STATUS_EMOJI = {"open": "🟡", "in_progress": "🔵", "settled": "✅", "rejected": "🔴", "closed": "⚫"}
        emoji = STATUS_EMOJI.get(row['status'], "❓")

        return (
            f"## Claim {claim_id} — {emoji} {row['status'].upper()}\n"
            f"- **Client:** {row['client_name']}\n"
            f"- **Policy:** {row['policy_type']} — {row['policy_number']}\n"
            f"- **Insurer:** {row['insurer']}\n"
            f"- **Incident Date:** {row['incident_date']}\n"
            f"- **Reported Date:** {row['reported_date']}\n"
            f"- **Description:** {row['description']}\n"
            "- **Damage Estimate:** " + (f"{row['damage_estimate']:,.0f}" if row['damage_estimate'] else "TBD") + "\n"
            f"- **Insurer Claim No.:** {row['insurer_claim_number'] or 'Pending'}\n"
            f"- **Broker Notes:** {row['notes'] or 'None'}"
        )
    finally:
        conn.close()


def register_claims_tools(mcp: FastMCP):

    @mcp.tool(
        name="broker_log_claim",
        description="Log a new insurance claim for a client. Provide client_id, policy_id, incident date, description, and optional damage estimate."
    )
    def broker_log_claim(
        client_id: str,
        policy_id: str,
        incident_date: str,
        description: str,
        damage_estimate: Optional[float] = None,
        notes: Optional[str] = None
    ) -> str:
        return log_claim_fn(client_id, policy_id, incident_date, description, damage_estimate, notes)

    @mcp.tool(
        name="broker_get_claim_status",
        description="Check the status and details of an existing claim by claim ID."
    )
    def broker_get_claim_status(claim_id: str) -> str:
        return get_claim_status_fn(claim_id)
