"""Offer generation tools — professional PDF offers using Jinja2."""
import sqlite3
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_text_offer(client: dict, products: list, offer_id: str, valid_until: str, notes: str, language: str) -> str:
    """Generate a clean markdown offer for display in chat."""
    lang = language.lower()

    if lang == "de":
        header = "Versicherungsangebot"
        dear = f"Sehr geehrte/r {client['name']},"
        intro = "Wir unterbreiten Ihnen folgende Versicherungsoptionen:"
        footer = "Dieses Angebot ist unverbindlich und vorbehaltlich der Risikoprüfung."
        valid_label = "Gültig bis"
        offer_label = "Angebots-Nr."
        premium_label = "Jahresprämie"
        deduct_label = "Selbstbehalt"
        cover_label = "Deckung"
        rec_label = "Empfehlung"
    elif lang == "ro":
        header = "Ofertă de Asigurare"
        dear = f"Stimate/ă {client['name']},"
        intro = "Vă prezentăm următoarele opțiuni de asigurare:"
        footer = "Oferta este orientativă și supusă analizei de risc finale."
        valid_label = "Valabilă până la"
        offer_label = "Nr. Ofertă"
        premium_label = "Primă anuală"
        deduct_label = "Franciză"
        cover_label = "Acoperire"
        rec_label = "Recomandare"
    else:
        header = "Insurance Offer"
        dear = f"Dear {client['name']},"
        intro = "We are pleased to present the following insurance options:"
        footer = "This offer is indicative and subject to final risk assessment."
        valid_label = "Valid until"
        offer_label = "Offer No."
        premium_label = "Annual Premium"
        deduct_label = "Deductible"
        cover_label = "Coverage"
        rec_label = "Best Value"

    lines = [
        f"# {header}",
        "",
        f"**{offer_label}:** {offer_id} &nbsp;&nbsp; **{valid_label}:** {valid_until} &nbsp;&nbsp; **Data:** {date.today().strftime('%d %b %Y')}",
        "",
        f"---",
        "",
        f"{dear}",
        f"{intro}",
        "",
    ]

    # Product comparison table
    lines += [
        f"| # | Asigurător | Tip | {premium_label} | {deduct_label} | Rating |",
        "|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(products, 1):
        premium_str = f"**{p['annual_premium']:,.0f} {p['currency']}**"
        deduct_str = str(p['deductible']) if p['deductible'] else "—"
        lines.append(f"| {i} | {p['insurer_name']} | {p['product_type']} | {premium_str} | {deduct_str} | {p['rating']} ⭐ |")

    lines.append("")

    # Individual product details
    for i, p in enumerate(products, 1):
        lines += [
            f"### Opțiunea {i}: {p['insurer_name']} — {p['product_type']}",
            f"- **{premium_label}:** {p['annual_premium']:,.2f} {p['currency']}",
            f"- **{cover_label}:** {p['coverage_summary']}",
        ]
        if p.get('insured_sum'):
            lines.append(f"- **Sumă asigurată:** {p['insured_sum']:,.0f} {p['currency']}")
        if p.get('deductible'):
            lines.append(f"- **{deduct_label}:** {p['deductible']}")
        lines.append("")

    # Best value highlight
    if len(products) > 1:
        best = min(products, key=lambda x: x['annual_premium'])
        lines += [
            f"> 💡 **{rec_label}:** {best['insurer_name']} — {best['annual_premium']:,.2f} {best['currency']}/an",
            "",
        ]

    if notes:
        lines += [f"> 📝 **Notă:** {notes}", ""]

    lines += [
        "---",
        f"*{footer}*",
        "",
        "*Demo Broker SRL · Licență ASF: RBK-DEMO-001 · demo@broker.com · +40 21 000 0000*",
    ]

    return "\n".join(lines)


# ── Plain callable function aliases ────────────────────────────────────────

def _create_offer_impl(
    client_id: str,
    product_ids: str,
    language: str = "en",
    valid_days: int = 30,
    notes: Optional[str] = None,
    format: str = "text"
) -> str:
    conn = get_db()
    try:
        client = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        if not client:
            return f"Client '{client_id}' not found."
        ids = [pid.strip() for pid in product_ids.split(",") if pid.strip()]
        if not ids:
            return "No product IDs provided."
        placeholders = ",".join("?" * len(ids))
        products = conn.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders})", ids
        ).fetchall()
        if not products:
            return f"No products found for IDs: {product_ids}"
        offer_id = f"OFF-{str(uuid.uuid4())[:8].upper()}"
        valid_until = (date.today() + timedelta(days=valid_days)).isoformat()
        conn.execute("""
            INSERT INTO offers (id, client_id, created_at, valid_until, status, products_count, notes)
            VALUES (?,?,?,?,?,?,?)
        """, (offer_id, client_id, date.today().isoformat(), valid_until,
              "draft", len(products), notes))
        conn.commit()

        # Sync to Firestore
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from shared.firestore_db import save_offer_to_firestore, is_available
            if is_available():
                row = conn.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
                if row:
                    save_offer_to_firestore(dict(row))
        except Exception:
            pass

        client_dict = dict(client)
        products_list = [dict(p) for p in products]
        offer_text = generate_text_offer(client_dict, products_list, offer_id, valid_until, notes, language)
        OUTPUT_DIR.mkdir(exist_ok=True)
        safe_name = client_dict['name'].replace(' ', '_').replace('/', '-')
        out_file = OUTPUT_DIR / f"{safe_name}_{date.today().isoformat()}_{offer_id}.txt"
        out_file.write_text(offer_text)
        pdf_status = ""
        try:
            from jinja2 import Environment, FileSystemLoader
            import weasyprint
            template_file = TEMPLATE_DIR / "offer_en.html"
            if template_file.exists():
                env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
                tmpl = env.get_template("offer_en.html")
                html = tmpl.render(client=client_dict, products=products_list,
                                   offer_id=offer_id, valid_until=valid_until,
                                   today=date.today().isoformat(), notes=notes, language=language)
                pdf_file = OUTPUT_DIR / f"{safe_name}_{date.today().isoformat()}_{offer_id}.pdf"
                weasyprint.HTML(string=html).write_pdf(str(pdf_file))
                pdf_status = f"\n📄 **PDF saved:** `{pdf_file}`"
        except Exception as e:
            pdf_status = f"\n_(PDF generation skipped: {type(e).__name__})_"
        return (
            f"✅ **Offer Generated: {offer_id}**\n"
            f"- **Client:** {client_dict['name']}\n"
            f"- **Products:** {len(products)} options included\n"
            f"- **Valid Until:** {valid_until}\n"
            f"- **Language:** {language.upper()}\n"
            f"- **Text saved:** `{out_file}`"
            f"{pdf_status}\n\n---\n\n{offer_text}"
        )
    finally:
        conn.close()


def _list_offers_impl(client_id: Optional[str] = None, status: Optional[str] = None) -> str:
    conn = get_db()
    try:
        if client_id and status:
            rows = conn.execute("""SELECT o.*, c.name as client_name FROM offers o
                JOIN clients c ON c.id=o.client_id WHERE o.client_id=? AND o.status=?
                ORDER BY o.created_at DESC""", (client_id, status)).fetchall()
        elif client_id:
            rows = conn.execute("""SELECT o.*, c.name as client_name FROM offers o
                JOIN clients c ON c.id=o.client_id WHERE o.client_id=?
                ORDER BY o.created_at DESC""", (client_id,)).fetchall()
        else:
            rows = conn.execute("""SELECT o.*, c.name as client_name FROM offers o
                JOIN clients c ON c.id=o.client_id
                ORDER BY o.created_at DESC LIMIT 20""").fetchall()
        if not rows:
            return "No offers found."
        lines = ["## Generated Offers\n",
                 "| Offer ID | Client | Created | Valid Until | Status | Products |",
                 "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['client_name']} | {r['created_at']} | "
                         f"{r['valid_until']} | {r['status']} | {r['products_count']} |")
        return "\n".join(lines)
    finally:
        conn.close()


# Aliases used by Chainlit app.py
create_offer_fn = _create_offer_impl
list_offers_fn  = _list_offers_impl


def register_offer_tools(mcp: FastMCP):

    @mcp.tool(name="broker_create_offer",
              description="Generate a professional insurance offer. Provide client_id, product_ids (comma-separated), optional language (en/ro/de), valid_days, notes.")
    def broker_create_offer(client_id: str, product_ids: str, language: str = "en",
                            valid_days: int = 30, notes: Optional[str] = None,
                            format: str = "text") -> str:
        return _create_offer_impl(client_id, product_ids, language, valid_days, notes, format)

    @mcp.tool(name="broker_list_offers",
              description="List generated offers, optionally filtered by client ID or status.")
    def broker_list_offers(client_id: Optional[str] = None, status: Optional[str] = None) -> str:
        return _list_offers_impl(client_id, status)

# Public aliases used by app.py
create_offer_fn = _create_offer_impl
list_offers_fn = _list_offers_impl
