"""Insurance product search and comparison tools."""
import sqlite3
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Plain callable functions ────────────────────────────────────────────────

def search_products_fn(product_type: str, country: str = "RO",
                       max_premium: Optional[float] = None, currency: str = "RON") -> str:
    conn = get_db()
    try:
        product_type = product_type.upper()
        rows = conn.execute("""
            SELECT p.*, i.country as insurer_country
            FROM products p
            JOIN insurers i ON i.id = p.insurer_id
            WHERE p.product_type = ? AND i.country = ?
            ORDER BY p.annual_premium ASC
        """, (product_type, country.upper())).fetchall()

        if not rows:
            return (
                f"No products found for type '{product_type}' in country '{country}'. "
                f"Available types: RCA, CASCO, PAD, CMR, KFZ, LIFE, HEALTH"
            )
        if max_premium:
            rows = [r for r in rows if r['annual_premium'] <= max_premium]

        lines = [
            f"## {product_type} Products — {country}\n",
            f"Found **{len(rows)} options**:\n",
            "| # | Insurer | Premium | Currency | Deductible | Rating | Product ID |",
            "|---|---|---|---|---|---|---|"
        ]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | **{r['insurer_name']}** | {r['annual_premium']:,.0f} | "
                f"{r['currency']} | {r['deductible'] or 'N/A'} | {r['rating']} | `{r['id']}` |"
            )
        lines.append("\n### Coverage Details\n")
        for r in rows:
            lines.append(f"**{r['insurer_name']}** (`{r['id']}`)")
            lines.append(f"> {r['coverage_summary']}")
            if r['exclusions']:
                lines.append(f"> *Exclusions: {r['exclusions']}*")
            lines.append("")
        lines.append("Use `broker_compare_products` with product IDs, or `broker_create_offer` to generate an offer.")
        return "\n".join(lines)
    finally:
        conn.close()


def compare_products_fn(product_ids: str) -> str:
    conn = get_db()
    try:
        ids = [pid.strip() for pid in product_ids.split(",") if pid.strip()]
        if not ids:
            return "Please provide comma-separated product IDs."
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders}) ORDER BY annual_premium ASC", ids
        ).fetchall()
        if not rows:
            return f"No products found for IDs: {', '.join(ids)}"

        product_type = rows[0]['product_type']
        lines = [
            f"## {product_type} Comparison — {len(rows)} Insurers\n",
            "| Criterion | " + " | ".join(r['insurer_name'] for r in rows) + " |",
            "|---|" + "---|" * len(rows)
        ]
        premiums = [r['annual_premium'] for r in rows]
        min_p = min(premiums)
        premium_cells = []
        for r in rows:
            p = r['annual_premium']
            cell = f"**{p:,.0f} {r['currency']} ✅**" if p == min_p else f"{p:,.0f} {r['currency']}"
            premium_cells.append(cell)
        lines.append("| **Annual Premium** | " + " | ".join(premium_cells) + " |")
        lines.append("| Deductible | " + " | ".join(r['deductible'] or "N/A" for r in rows) + " |")
        lines.append("| Insurer Rating | " + " | ".join(r['rating'] for r in rows) + " |")
        sums = [f"{r['insured_sum']:,.0f} {r['currency']}" if r['insured_sum'] else "N/A" for r in rows]
        lines.append("| Insured Sum | " + " | ".join(sums) + " |")
        lines.append("\n### Coverage Summary\n")
        for r in rows:
            lines.append(f"**{r['insurer_name']}:** {r['coverage_summary']}")
        best = rows[0]
        lines.append(
            f"\n### 💡 Recommendation\n"
            f"**{best['insurer_name']}** — lowest premium: **{best['annual_premium']:,.0f} {best['currency']}**, "
            f"rating **{best['rating']}**."
        )
        return "\n".join(lines)
    finally:
        conn.close()


def register_product_tools(mcp: FastMCP):

    @mcp.tool(name="broker_search_products",
              description="Search insurance products by type (RCA,CASCO,PAD,CMR,KFZ,LIFE,HEALTH) and country (RO/DE).")
    def broker_search_products(product_type: str, country: str = "RO",
                               max_premium: Optional[float] = None, currency: str = "RON") -> str:
        return search_products_fn(product_type, country, max_premium, currency)

    @mcp.tool(name="broker_compare_products",
              description="Compare insurance products side-by-side. Pass comma-separated product IDs.")
    def broker_compare_products(product_ids: str) -> str:
        return compare_products_fn(product_ids)

    # keep old implementations below for reference (unused now)
    def _old_search(product_ids: str) -> str:
        conn = get_db()
        try:
            ids = [pid.strip() for pid in product_ids.split(",") if pid.strip()]
            if not ids:
                return "Please provide comma-separated product IDs, e.g. 'PROD_RCA_ALZ,PROD_RCA_GEN'"

            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT * FROM products WHERE id IN ({placeholders}) ORDER BY annual_premium ASC",
                ids
            ).fetchall()

            if not rows:
                return f"No products found for IDs: {', '.join(ids)}"

            product_type = rows[0]['product_type']
            currency = rows[0]['currency']

            lines = [
                f"## {product_type} Comparison — {len(rows)} Insurers\n",
                "| Criterion | " + " | ".join(r['insurer_name'] for r in rows) + " |",
                "|---|" + "---|" * len(rows)
            ]

            # Premium row (highlight lowest)
            premiums = [r['annual_premium'] for r in rows]
            min_p = min(premiums)
            premium_cells = []
            for r in rows:
                p = r['annual_premium']
                cell = f"**{p:,.0f} {r['currency']}** ✅" if p == min_p else f"{p:,.0f} {r['currency']}"
                premium_cells.append(cell)
            lines.append("| **Annual Premium** | " + " | ".join(premium_cells) + " |")

            # Deductible
            lines.append("| Deductible | " + " | ".join(r['deductible'] or "N/A" for r in rows) + " |")

            # Rating
            lines.append("| Insurer Rating | " + " | ".join(r['rating'] for r in rows) + " |")

            # Insured sum
            sums = []
            for r in rows:
                sums.append(f"{r['insured_sum']:,.0f} {r['currency']}" if r['insured_sum'] else "N/A")
            lines.append("| Insured Sum | " + " | ".join(sums) + " |")

            lines.append("\n### Coverage Summary\n")
            for r in rows:
                lines.append(f"**{r['insurer_name']}:** {r['coverage_summary']}")

            # Recommendation
            best = rows[0]
            lines.append(
                f"\n### 💡 Recommendation\n"
                f"**{best['insurer_name']}** offers the lowest premium at "
                f"**{best['annual_premium']:,.0f} {best['currency']}** with rating **{best['rating']}**.\n\n"
                f"Use `broker_create_offer` with `product_ids='{','.join(r['id'] for r in rows)}'` "
                f"to generate a professional PDF offer for the client."
            )
            return "\n".join(lines)
        finally:
            conn.close()
