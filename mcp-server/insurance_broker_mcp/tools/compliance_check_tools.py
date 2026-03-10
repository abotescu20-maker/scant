"""Compliance check tools — verify client file completeness and regulatory requirements."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"

# Required documents per product type
REQUIRED_DOCS = {
    "RCA": ["IPID", "CI/Passport", "Vehicle registration", "Bonus-malus certificate", "GDPR consent"],
    "CASCO": ["IPID", "CI/Passport", "Vehicle registration", "Vehicle photos", "GDPR consent"],
    "PAD": ["IPID", "CI/Passport", "Property deed", "GDPR consent"],
    "CMR": ["IPID", "CUI/J-number", "Transport license", "Vehicle fleet list", "GDPR consent"],
    "HEALTH": ["IPID", "CI/Passport", "Health questionnaire", "GDPR consent", "Health data consent (Art.9)"],
    "LIFE": ["IPID", "CI/Passport", "Health questionnaire", "Income proof", "GDPR consent", "Health data consent (Art.9)"],
    "KFZ": ["IPID", "Personalausweis/Reisepass", "Zulassungsbescheinigung Teil I", "SF-Nachweis", "DSGVO consent", "Beratungsprotokoll"],
    "BU": ["IPID", "Personalausweis", "Gesundheitsfragen", "Income proof", "DSGVO consent", "Health data consent (Art.9)", "Beratungsprotokoll"],
    "LIABILITY": ["IPID", "CI/CUI", "Business description", "Revenue declaration", "GDPR consent"],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_get(row, key, default=None):
    """Safe .get() equivalent for sqlite3.Row objects."""
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default


def compliance_check_fn(client_id: str) -> str:
    """Check compliance status for a client — missing documents, expiring policies, regulatory issues."""
    conn = get_db()
    try:
        # Get client
        client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return f"Client {client_id} not found."

        # Get active policies
        policies = conn.execute(
            "SELECT * FROM policies WHERE client_id = ? AND status = 'active' ORDER BY end_date ASC",
            (client_id,),
        ).fetchall()

        # Get open claims
        claims = conn.execute(
            "SELECT * FROM claims WHERE client_id = ? AND status IN ('open', 'in_progress')",
            (client_id,),
        ).fetchall()

        issues = []
        warnings = []
        ok_items = []

        # --- Client data checks ---
        if not _row_get(client, "email"):
            issues.append("Missing client email — required for offer delivery and GDPR communication")
        else:
            ok_items.append("Client email present")

        if not _row_get(client, "phone"):
            issues.append("Missing client phone — required for urgent communications")
        else:
            ok_items.append("Client phone present")

        if not _row_get(client, "address"):
            warnings.append("Missing client address — needed for formal correspondence")

        # --- Policy checks ---
        today = date.today()
        country = (_row_get(client, "country", "RO")).upper()

        for p in policies:
            ptype = p["policy_type"].upper()
            end = date.fromisoformat(p["end_date"]) if _row_get(p, "end_date") else None

            # Expiry check
            if end:
                days_left = (end - today).days
                if days_left < 0:
                    issues.append(f"**{ptype}** ({p['insurer']}) — EXPIRED {abs(days_left)} days ago!")
                elif days_left <= 7:
                    issues.append(f"**{ptype}** ({p['insurer']}) — expires in {days_left} days! Renew urgently.")
                elif days_left <= 30:
                    warnings.append(f"{ptype} ({p['insurer']}) — expires in {days_left} days. Plan renewal.")
                else:
                    ok_items.append(f"{ptype} ({p['insurer']}) — valid until {p['end_date']}")

            # Document checklist
            required = REQUIRED_DOCS.get(ptype, ["IPID", "CI/Passport", "GDPR consent"])
            # Note: in production, check against actual document storage
            warnings.append(f"{ptype}: Verify presence of {len(required)} required documents: {', '.join(required)}")

        # --- Mandatory product check (RO) ---
        owned_types = {p["policy_type"].upper() for p in policies}
        if country == "RO":
            if "RCA" not in owned_types:
                # Check if client has vehicle-related policies suggesting they own a car
                if any(t in owned_types for t in ["CASCO"]):
                    issues.append("Has CASCO but **no active RCA** — RCA is mandatory! Client risks fines.")
            if "PAD" not in owned_types:
                if any(t in owned_types for t in ["HOME"]):
                    issues.append("Has HOME insurance but **no active PAD** — PAD is mandatory for homeowners!")

        # --- Claims checks ---
        for c in claims:
            claim_date = date.fromisoformat(c["incident_date"]) if _row_get(c, "incident_date") else today
            days_open = (today - claim_date).days
            if days_open > 30:
                issues.append(f"Claim {c['id']}: Open for {days_open} days — insurer must respond within 30 days (RCA)")
            elif days_open > 14:
                warnings.append(f"Claim {c['id']}: Open for {days_open} days — follow up with insurer")

        # --- Build report ---
        lines = [f"## Compliance Check: {client['name']} ({client_id})\n"]

        if issues:
            lines.append(f"### Issues ({len(issues)})\n")
            for i, issue in enumerate(issues, 1):
                lines.append(f"{i}. {issue}")

        if warnings:
            lines.append(f"\n### Warnings ({len(warnings)})\n")
            for i, w in enumerate(warnings, 1):
                lines.append(f"{i}. {w}")

        if ok_items:
            lines.append(f"\n### OK ({len(ok_items)})\n")
            for item in ok_items:
                lines.append(f"- {item}")

        score = max(0, 100 - len(issues) * 20 - len(warnings) * 5)
        lines.append(f"\n**Compliance Score: {score}/100**")
        if score < 50:
            lines.append("**Action required immediately.**")
        elif score < 80:
            lines.append("Some items need attention.")
        else:
            lines.append("Client file is in good order.")

        return "\n".join(lines)
    finally:
        conn.close()


def register_compliance_check_tools(mcp: FastMCP):

    @mcp.tool(name="broker_compliance_check",
              description="Check client file completeness: missing documents, expiring policies, mandatory products, open claims status.")
    def broker_compliance_check(client_id: str) -> str:
        return compliance_check_fn(client_id)
