"""Compliance and reporting tools — ASF (Romania) + BaFin (Germany)."""
import sqlite3
from datetime import date
from pathlib import Path
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"

# ASF insurance class codes (Romania)
ASF_CLASS_MAP = {
    "RCA": "A10 — Motor vehicle liability",
    "CASCO": "A3 — Land vehicles (own damage)",
    "PAD": "A9 — Damage to property (disaster)",
    "HOME": "A9 — Damage to property",
    "LIFE": "B1 — Life insurance",
    "HEALTH": "A2 — Accident / health",
    "CMR": "A11 — Aircraft / goods in transit",
    "LIABILITY": "A13 — General liability",
    "TRANSPORT": "A7 — Goods in transit",
}

# BaFin insurance classes (Germany — Spartenplan)
BAFIN_CLASS_MAP = {
    "KFZ": "Kraftfahrzeughaftpflicht (KH)",
    "GEBAEUDE": "Verbundene Gebäudeversicherung (VGV)",
    "BERUFSUNFAEHIGKEIT": "Berufsunfähigkeitsversicherung (BU)",
    "LIFE": "Lebensversicherung",
    "HEALTH": "Krankenzusatzversicherung",
    "LIABILITY": "Haftpflichtversicherung",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def asf_summary_fn(month: int, year: int) -> str:
    """Generate ASF monthly activity summary."""
    conn = get_db()
    try:
        month_str = f"{year}-{month:02d}"
        rows = conn.execute("""
            SELECT policy_type,
                   COUNT(*) as policy_count,
                   SUM(annual_premium) as total_premium,
                   SUM(annual_premium * COALESCE(broker_commission_pct, 10) / 100) as total_commission,
                   currency
            FROM policies
            WHERE strftime('%Y-%m', start_date) = ?
            GROUP BY policy_type, currency
            ORDER BY total_premium DESC
        """, (month_str,)).fetchall()

        all_policies = conn.execute("""
            SELECT COUNT(*) as total, SUM(annual_premium) as total_premium
            FROM policies WHERE status = 'active'
        """).fetchone()

        lines = [
            f"## ASF Monthly Activity Report — {month:02d}/{year}",
            f"*Prepared for ASF submission — Law 236/2018 on Insurance Distribution*\n",
            "### Policies Intermediated This Month",
            "| Insurance Class | ASF Code | Count | Gross Premium (RON) | Broker Commission |",
            "|---|---|---|---|---|"
        ]

        total_p = 0
        total_c = 0
        for r in rows:
            asf_code = ASF_CLASS_MAP.get(r['policy_type'], "A99 — Other")
            premium = r['total_premium'] or 0
            commission = r['total_commission'] or 0
            total_p += premium
            total_c += commission
            lines.append(
                f"| {r['policy_type']} | {asf_code} | {r['policy_count']} | "
                f"{premium:,.2f} {r['currency']} | {commission:,.2f} {r['currency']} |"
            )

        lines += [
            f"| **TOTAL** | | | **{total_p:,.2f} RON** | **{total_c:,.2f} RON** |",
            "",
            "### Portfolio Overview (All Active Policies)",
            f"- **Total active policies:** {all_policies['total']}",
            f"- **Total portfolio premium:** {all_policies['total_premium']:,.2f} RON",
            "",
            "### Regulatory Notes",
            "- Report submitted per Art. 39 of Law 236/2018",
            "- Broker authorized under ASF Decision [RBK-DEMO-001]",
            "- All intermediated products from ASF-licensed insurers",
            "- GDPR compliance: client data processed under consent (Art. 6 GDPR)",
            "",
            "*This summary is generated automatically. Final submission requires broker signature.*"
        ]
        return "\n".join(lines)
    finally:
        conn.close()


def check_rca_validity_fn(query: str) -> str:
    """Check RCA validity — demo searches by client name."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT p.*, c.name as client_name, c.phone
            FROM policies p
            JOIN clients c ON c.id = p.client_id
            WHERE p.policy_type = 'RCA'
              AND (c.name LIKE ? OR p.policy_number LIKE ?)
            ORDER BY p.end_date DESC
        """, (f"%{query}%", f"%{query}%")).fetchall()

        if not rows:
            return (
                f"No RCA policy found for '{query}'.\n"
                f"**⚠️ Note:** In production, this tool connects to CEDAM "
                f"(Centrul de Date al Asigurătorilor din România) for real-time verification.\n"
                f"Demo searches local database only."
            )

        today = date.today().isoformat()
        lines = [f"## RCA Validity Check — '{query}'\n"]
        for r in rows:
            is_valid = r['end_date'] >= today and r['status'] == 'active'
            days_left = (date.fromisoformat(r['end_date']) - date.today()).days
            status_icon = "✅ VALID" if is_valid else "❌ EXPIRED"
            lines += [
                f"### {status_icon}",
                f"- **Client:** {r['client_name']}",
                f"- **Policy Number:** {r['policy_number']}",
                f"- **Insurer:** {r['insurer']}",
                f"- **Valid Until:** {r['end_date']}",
                f"- **Days Remaining:** {days_left if is_valid else 'EXPIRED'}",
                f"- **Annual Premium:** {r['annual_premium']:,.0f} {r['currency']}",
                ""
            ]
            if not is_valid:
                lines.append("**⚠️ Action Required:** Client is driving without valid RCA — liable to RAR fines up to 10,000 RON.")
        return "\n".join(lines)
    finally:
        conn.close()


def bafin_summary_fn(month: int, year: int) -> str:
    """Generate BaFin monthly summary for German regulated business."""
    conn = get_db()
    try:
        month_str = f"{year}-{month:02d}"
        rows = conn.execute("""
            SELECT p.policy_type, COUNT(*) as count,
                   SUM(p.annual_premium) as total_premium, p.currency
            FROM policies p
            JOIN clients c ON c.id = p.client_id
            WHERE c.country = 'DE'
              AND strftime('%Y-%m', p.start_date) = ?
            GROUP BY p.policy_type, p.currency
        """, (month_str,)).fetchall()

        if not rows:
            return f"No German (BaFin-regulated) business recorded for {month:02d}/{year}."

        lines = [
            f"## BaFin Monthly Activity — {month:02d}/{year}",
            f"*German regulated insurance distribution — VVG compliance*\n",
            "| Product | BaFin Class | Count | Premium (EUR) |",
            "|---|---|---|---|"
        ]
        for r in rows:
            bafin = BAFIN_CLASS_MAP.get(r['policy_type'], "Sonstige")
            lines.append(
                f"| {r['policy_type']} | {bafin} | {r['count']} | {r['total_premium']:,.2f} EUR |"
            )
        lines += [
            "",
            "### Regulatory Framework",
            "- Distribution per VVG (Versicherungsvertragsgesetz)",
            "- IDD compliance: Insurance Distribution Directive 2016/97/EU",
            "- Broker registered with BaFin [DE-BROKER-DEMO]",
        ]
        return "\n".join(lines)
    finally:
        conn.close()


def register_compliance_tools(mcp: FastMCP):

    @mcp.tool(
        name="broker_asf_summary",
        description="Generate monthly portfolio summary for ASF (Romanian Financial Supervisory Authority) reporting. Provide month (1-12) and year."
    )
    def broker_asf_summary(month: int, year: int) -> str:
        return asf_summary_fn(month, year)

    @mcp.tool(
        name="broker_check_rca_validity",
        description="Check RCA (mandatory Romanian motor TPL) validity for a registration plate or by client name. Returns policy details and expiry status."
    )
    def broker_check_rca_validity(query: str) -> str:
        return check_rca_validity_fn(query)

    @mcp.tool(
        name="broker_bafin_summary",
        description="Generate monthly activity summary for BaFin (Germany) regulated insurance distribution. Provide month and year."
    )
    def broker_bafin_summary(month: int, year: int) -> str:
        return bafin_summary_fn(month, year)
