"""Cross-sell analytics tools — analyze client portfolio and suggest missing products."""
import sqlite3
from pathlib import Path
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"

# Standard product bundles per client type and country
RECOMMENDED_BUNDLES = {
    "individual_RO": ["RCA", "CASCO", "PAD", "HOME", "HEALTH", "LIFE"],
    "individual_DE": ["KFZ", "PHV", "HAUSRAT", "BU", "RECHTSSCHUTZ"],
    "company_RO": ["RCA", "CASCO", "LIABILITY", "CMR", "PROPERTY"],
    "company_DE": ["KFZ", "BERUFSHAFTPFLICHT", "GEBAUDE", "RECHTSSCHUTZ"],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def cross_sell_fn(client_id: str) -> str:
    """Analyze a client's portfolio and suggest missing products."""
    conn = get_db()
    try:
        # Get client info
        client = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not client:
            return f"Client {client_id} not found."

        # Get active policies
        policies = conn.execute(
            "SELECT policy_type FROM policies WHERE client_id = ? AND status = 'active'",
            (client_id,),
        ).fetchall()
        owned_types = {r["policy_type"].upper() for r in policies}

        # Determine recommended bundle
        client_type = (client["client_type"] or "individual").lower() if client["client_type"] else "individual"
        country = (client["country"] or "RO").upper() if client["country"] else "RO"
        bundle_key = f"{client_type}_{country}"
        recommended = RECOMMENDED_BUNDLES.get(bundle_key, RECOMMENDED_BUNDLES.get(f"individual_{country}", []))

        missing = [p for p in recommended if p not in owned_types]

        lines = [f"## Cross-Sell Analysis: {client['name']} ({client_id})\n"]
        lines.append(f"**Country**: {country} | **Type**: {client_type}")
        lines.append(f"**Active policies**: {', '.join(owned_types) if owned_types else 'None'}\n")

        if not missing:
            lines.append("Portfolio is **complete** — client has all recommended products.")
        else:
            lines.append(f"### Recommended Products ({len(missing)} missing)\n")
            lines.append("| Product | Why | Priority |")
            lines.append("|---------|-----|----------|")
            for p in missing:
                priority, reason = _get_recommendation(p, country)
                lines.append(f"| **{p}** | {reason} | {priority} |")
            lines.append(f"\n**Action**: Search these products with `broker_search_products` and create a bundled offer.")

        return "\n".join(lines)
    finally:
        conn.close()


def _get_recommendation(product: str, country: str) -> tuple:
    """Return (priority, reason) for a missing product."""
    recommendations = {
        "RCA": ("URGENT", "Mandatory motor insurance — fines if missing"),
        "PAD": ("URGENT", "Mandatory home disaster insurance — cannot get other home insurance without it"),
        "KFZ": ("URGENT", "Mandatory motor TPL — vehicle cannot be registered without it"),
        "CASCO": ("HIGH", "Comprehensive motor — protects vehicle value, high claim frequency"),
        "HOME": ("HIGH", "Home insurance — protects largest asset"),
        "HEALTH": ("HIGH", "Health insurance — covers medical costs not in CNAS"),
        "LIFE": ("MEDIUM", "Life insurance — income protection for family"),
        "BU": ("HIGH", "Disability insurance — protects 60-80% of income if unable to work"),
        "PHV": ("HIGH", "Personal liability — essential coverage, low premium"),
        "HAUSRAT": ("MEDIUM", "Contents insurance — covers personal belongings"),
        "LIABILITY": ("HIGH", "Business liability — essential for companies"),
        "CMR": ("HIGH", "Transport liability — mandatory for international freight"),
        "BERUFSHAFTPFLICHT": ("HIGH", "Professional liability — protects against professional errors"),
        "GEBAUDE": ("MEDIUM", "Building insurance — protects commercial property"),
        "RECHTSSCHUTZ": ("LOW", "Legal protection — covers legal costs"),
        "PROPERTY": ("MEDIUM", "Commercial property insurance"),
    }
    return recommendations.get(product, ("MEDIUM", "Recommended for complete portfolio coverage"))


def register_analytics_tools(mcp: FastMCP):

    @mcp.tool(name="broker_cross_sell",
              description="Analyze a client's portfolio and suggest missing insurance products for cross-selling.")
    def broker_cross_sell(client_id: str) -> str:
        return cross_sell_fn(client_id)
