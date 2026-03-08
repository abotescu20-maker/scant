"""
Insurance Broker AI Assistant — Chainlit UI
============================================
Chat interface for non-technical insurance broker employees.
Uses Google Gemini API (google-genai SDK).
Features: PDF/image upload (Gemini Vision), email offers, export PDF/XLSX/DOCX
"""
import sys
import os
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv

import chainlit as cl
from google import genai
from google.genai import types

# ── Admin DB helpers (imported only if tables exist) ──────────────────────────
try:
    from shared.db import (
        get_user_by_email, get_user_tools, log_audit, record_token_usage,
        init_admin_tables
    )
    from shared.auth import verify_password
    init_admin_tables()
    ADMIN_ENABLED = True
except Exception:
    ADMIN_ENABLED = False

# ── Load .env ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────
MCP_SERVER_DIR = BASE_DIR / "mcp-server"
DB_PATH = MCP_SERVER_DIR / "insurance_broker.db"
OUTPUT_DIR = MCP_SERVER_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(MCP_SERVER_DIR))

# ── Import broker tools directly ────────────────────────────────────────────
from insurance_broker_mcp.tools.client_tools import search_clients_fn, get_client_fn, create_client_fn
from insurance_broker_mcp.tools.policy_tools import get_renewals_due_fn, list_policies_fn
from insurance_broker_mcp.tools.product_tools import search_products_fn, compare_products_fn
from insurance_broker_mcp.tools.offer_tools import create_offer_fn, list_offers_fn
from insurance_broker_mcp.tools.claims_tools import log_claim_fn, get_claim_status_fn
from insurance_broker_mcp.tools.compliance_tools import asf_summary_fn, bafin_summary_fn, check_rca_validity_fn
from insurance_broker_mcp.tools.email_tools import send_offer_email_fn

# ── Gemini client (new SDK) ──────────────────────────────────────────────────
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set. Add it to .env file in the project root.")

client = genai.Client(api_key=api_key)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Alex, an AI assistant for an insurance brokerage licensed under ASF (Romania) and BaFin (Germany).

You help insurance brokers with their daily work: finding clients, searching products, generating offers, tracking renewals, and processing claims.

## Available Tools
- broker_search_clients — search clients by name, phone, email
- broker_get_client — full client profile with policies
- broker_create_client — add new client to database
- broker_search_products — search insurance products (RCA, CASCO, PAD, CMR, KFZ, LIFE, etc.)
- broker_compare_products — side-by-side comparison table
- broker_create_offer — generate professional insurance offer (saves file + shows in chat)
- broker_list_offers — list generated offers
- broker_send_offer_email — send offer by email to the client (use offer_id from broker_list_offers)
- broker_get_renewals_due — policies expiring soon (use days_ahead parameter)
- broker_list_policies — list policies by client or status
- broker_log_claim — register new damage claim
- broker_get_claim_status — check claim status
- broker_asf_summary — monthly ASF regulatory report (Romania)
- broker_bafin_summary — monthly BaFin regulatory report (Germany)
- broker_check_rca_validity — check RCA validity for a client

## Document Upload
When a user uploads a file (PDF, image, etc.), it will be analyzed automatically using Gemini Vision.
You will receive the analysis result and can then:
- Create a new client from extracted ID card data
- Log a claim from extracted accident report data
- Add a new policy from extracted policy scan data
- Use damage description from accident photo analysis

## Behavior
- Always be proactive: if a client has urgent renewals, mention it immediately
- When searching products, compare all available options (even if only 1-2 found)
- After finding products, ALWAYS proceed to broker_create_offer immediately when broker says "make a proposal" or "yes" — do not ask for confirmation again
- If a product search returns results, use those product IDs to call broker_create_offer right away
- If a product search returns 0 results, try an alternative type (e.g. LIFE if HEALTH is empty) and still create an offer
- Generate offers in English by default; switch to German (de) or Romanian (ro) on request
- Keep responses concise and professional
- All amounts: RON for Romanian products, EUR for German (KFZ) products
- Regulatory framework: ASF Law 236/2018 (RO), VVG + IDD (DE), GDPR (both)

## Document Upload Workflow
When a document is analyzed and the broker says "extract data" or confirms an action:
1. Search for the client by phone/name extracted from the document
2. If not found, create the client automatically with extracted data
3. Based on document context, proactively suggest the most relevant product type
4. When broker says "make a proposal" or "yes" — search products AND create offer in the same turn, without asking again

## Compliance
Never share full ID numbers (CNP/passport) in responses — use client IDs only."""

# ── Tool definitions for Gemini function calling ─────────────────────────────
TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="broker_search_clients",
            description="Search clients by name, phone, or email address.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="Name, phone, or email to search"),
                    "limit": types.Schema(type=types.Type.INTEGER, description="Max results (default 10)"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_get_client",
            description="Get full client profile including all their policies.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "client_id": types.Schema(type=types.Type.STRING, description="Client ID (e.g. CLI001)"),
                },
                required=["client_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_create_client",
            description="Create a new client in the database.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "name": types.Schema(type=types.Type.STRING),
                    "phone": types.Schema(type=types.Type.STRING),
                    "email": types.Schema(type=types.Type.STRING),
                    "address": types.Schema(type=types.Type.STRING),
                    "client_type": types.Schema(type=types.Type.STRING, description="individual or company"),
                    "country": types.Schema(type=types.Type.STRING, description="RO or DE"),
                    "source": types.Schema(type=types.Type.STRING),
                },
                required=["name", "phone"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_search_products",
            description="Search available insurance products from all partner insurers.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "product_type": types.Schema(type=types.Type.STRING, description="Type: RCA, CASCO, PAD, HOME, LIFE, CMR, KFZ, LIABILITY, TRANSPORT, HEALTH"),
                    "country": types.Schema(type=types.Type.STRING, description="RO or DE"),
                },
                required=["product_type"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_compare_products",
            description="Compare multiple insurance products side by side.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "product_ids": types.Schema(type=types.Type.STRING, description="Comma-separated product IDs from broker_search_products"),
                },
                required=["product_ids"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_create_offer",
            description="Generate a professional insurance offer document for a client.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "client_id": types.Schema(type=types.Type.STRING),
                    "product_ids": types.Schema(type=types.Type.STRING, description="Comma-separated product IDs"),
                    "language": types.Schema(type=types.Type.STRING, description="en, ro, or de"),
                    "valid_days": types.Schema(type=types.Type.INTEGER),
                    "notes": types.Schema(type=types.Type.STRING),
                    "format": types.Schema(type=types.Type.STRING, description="text or pdf"),
                },
                required=["client_id", "product_ids"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_list_offers",
            description="List generated offers, optionally filtered by client or status.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "client_id": types.Schema(type=types.Type.STRING),
                    "status": types.Schema(type=types.Type.STRING, description="sent, accepted, or expired"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="broker_send_offer_email",
            description="Send a generated offer by email to the client. Fetches client email from DB if to_email not provided.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "offer_id": types.Schema(type=types.Type.STRING, description="Offer ID from broker_list_offers"),
                    "to_email": types.Schema(type=types.Type.STRING, description="Recipient email (optional, uses client email from DB if not set)"),
                    "subject": types.Schema(type=types.Type.STRING, description="Email subject (optional)"),
                },
                required=["offer_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_get_renewals_due",
            description="Get policies expiring within the next N days.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "days_ahead": types.Schema(type=types.Type.INTEGER, description="Number of days to look ahead (default 30)"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="broker_list_policies",
            description="List policies, optionally filtered by client ID or status.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "client_id": types.Schema(type=types.Type.STRING),
                    "status": types.Schema(type=types.Type.STRING, description="active, expired, or cancelled"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="broker_log_claim",
            description="Register a new damage/claims report for a client.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "client_id": types.Schema(type=types.Type.STRING),
                    "policy_id": types.Schema(type=types.Type.STRING),
                    "incident_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                    "description": types.Schema(type=types.Type.STRING),
                    "damage_estimate": types.Schema(type=types.Type.NUMBER),
                },
                required=["client_id", "policy_id", "incident_date", "description"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_get_claim_status",
            description="Get the status of an existing claim.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "claim_id": types.Schema(type=types.Type.STRING),
                },
                required=["claim_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_asf_summary",
            description="Generate monthly ASF (Romanian Financial Supervisory Authority) report.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "month": types.Schema(type=types.Type.INTEGER, description="Month number 1-12"),
                    "year": types.Schema(type=types.Type.INTEGER),
                },
                required=["month", "year"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_bafin_summary",
            description="Generate monthly BaFin (German) regulatory report.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "month": types.Schema(type=types.Type.INTEGER, description="Month number 1-12"),
                    "year": types.Schema(type=types.Type.INTEGER),
                },
                required=["month", "year"],
            ),
        ),
        types.FunctionDeclaration(
            name="broker_check_rca_validity",
            description="Check RCA (mandatory Romanian motor insurance) validity for a client.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="Client name or policy number"),
                },
                required=["query"],
            ),
        ),
    ])
]

# ── Tool executor ─────────────────────────────────────────────────────────────
TOOL_DISPATCH = {
    "broker_search_clients":     search_clients_fn,
    "broker_get_client":         get_client_fn,
    "broker_create_client":      create_client_fn,
    "broker_search_products":    search_products_fn,
    "broker_compare_products":   compare_products_fn,
    "broker_create_offer":       create_offer_fn,
    "broker_list_offers":        list_offers_fn,
    "broker_send_offer_email":   send_offer_email_fn,
    "broker_get_renewals_due":   get_renewals_due_fn,
    "broker_list_policies":      list_policies_fn,
    "broker_log_claim":          log_claim_fn,
    "broker_get_claim_status":   get_claim_status_fn,
    "broker_asf_summary":        asf_summary_fn,
    "broker_bafin_summary":      bafin_summary_fn,
    "broker_check_rca_validity": check_rca_validity_fn,
}

def execute_tool(tool_name: str, tool_input: dict) -> str:
    fn = TOOL_DISPATCH.get(tool_name)
    if not fn:
        return f"Unknown tool: {tool_name}"
    try:
        return fn(**tool_input)
    except Exception as e:
        return f"Tool error: {type(e).__name__}: {e}"


# ── Export helpers ────────────────────────────────────────────────────────────

def export_to_xlsx(content: str, title: str) -> Path:
    """Convert text content to XLSX with formatting."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]

    # Header style
    header_fill = PatternFill(start_color="1a365d", end_color="1a365d", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    lines = content.split("\n")
    row = 1
    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            # Table row
            cells = [c.strip() for c in line.split("|")[1:-1]]
            for col, cell_text in enumerate(cells, 1):
                cell = ws.cell(row=row, column=col, value=cell_text)
                if row <= 2:
                    cell.fill = header_fill
                    cell.font = header_font
                cell.alignment = Alignment(wrap_text=True)
            ws.column_dimensions[chr(64 + min(col, 26))].width = 20
        elif line.startswith("#"):
            cell = ws.cell(row=row, column=1, value=line.lstrip("#").strip())
            cell.font = Font(bold=True, size=12)
        elif line.strip() and not line.startswith("---"):
            ws.cell(row=row, column=1, value=line)

        if line.strip() or line.startswith("|"):
            row += 1

    out_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_{date.today().isoformat()}.xlsx"
    wb.save(str(out_path))
    return out_path


def export_to_docx(content: str, title: str) -> Path:
    """Convert text content to DOCX."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return None

    doc = Document()

    # Title
    heading = doc.add_heading(title, level=1)
    heading.runs[0].font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)

    lines = content.split("\n")
    table_rows = []
    in_table = False

    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not line.replace("|", "").replace("-", "").replace(" ", ""):
                continue  # separator line
            table_rows.append(cells)
            in_table = True
        else:
            if in_table and table_rows:
                # Flush table
                if len(table_rows) > 1:
                    t = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
                    t.style = "Table Grid"
                    for r_idx, row_data in enumerate(table_rows):
                        for c_idx, cell_text in enumerate(row_data):
                            if c_idx < len(t.rows[r_idx].cells):
                                t.rows[r_idx].cells[c_idx].text = cell_text
                                if r_idx == 0:
                                    t.rows[r_idx].cells[c_idx].paragraphs[0].runs[0].font.bold = True if t.rows[r_idx].cells[c_idx].paragraphs[0].runs else True
                doc.add_paragraph()
                table_rows = []
                in_table = False

            if line.startswith("## "):
                doc.add_heading(line[3:], level=2)
            elif line.startswith("# "):
                doc.add_heading(line[2:], level=1)
            elif line.startswith("**") and line.endswith("**"):
                p = doc.add_paragraph()
                run = p.add_run(line.strip("**"))
                run.bold = True
            elif line.strip() and not line.startswith("---"):
                doc.add_paragraph(line)

    out_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_{date.today().isoformat()}.docx"
    doc.save(str(out_path))
    return out_path


def export_to_pdf(content: str, title: str) -> Path:
    """Convert text/markdown content to PDF via WeasyPrint."""
    try:
        from weasyprint import HTML
    except ImportError:
        return None

    # Convert markdown-like content to HTML
    lines = content.split("\n")
    html_lines = ["<html><head><style>",
                  "body { font-family: Arial, sans-serif; margin: 40px; color: #333; }",
                  "h1 { color: #1a365d; border-bottom: 2px solid #1a365d; }",
                  "h2 { color: #2d3748; }",
                  "table { border-collapse: collapse; width: 100%; margin: 15px 0; }",
                  "th { background: #1a365d; color: white; padding: 8px; text-align: left; }",
                  "td { padding: 8px; border: 1px solid #e2e8f0; }",
                  "tr:nth-child(even) { background: #f7fafc; }",
                  ".footer { color: #718096; font-size: 11px; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 10px; }",
                  "</style></head><body>"]

    in_table = False
    table_header_done = False

    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-", "").replace(" ", "") == "" for c in cells):
                continue  # separator
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                table_header_done = False
            if not table_header_done:
                html_lines.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
                table_header_done = True
            else:
                html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
                table_header_done = False
            if line.startswith("---"):
                html_lines.append("<hr>")
            elif line.strip():
                # Bold text
                line = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1) if "**" in line else line
                html_lines.append(f"<p>{line}</p>")

    if in_table:
        html_lines.append("</table>")

    html_lines.append(f'<div class="footer">Generated by Alex — Insurance Broker AI | {date.today().strftime("%d %B %Y")}</div>')
    html_lines.append("</body></html>")

    html_content = "\n".join(html_lines)
    out_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_{date.today().isoformat()}.pdf"

    try:
        HTML(string=html_content).write_pdf(str(out_path))
        return out_path
    except Exception:
        return None


async def send_export_files(content: str, base_title: str):
    """Generate and send PDF, XLSX, DOCX as downloadable attachments."""
    elements = []
    generated = []

    xlsx_path = export_to_xlsx(content, base_title)
    if xlsx_path and xlsx_path.exists():
        elements.append(cl.File(name=xlsx_path.name, path=str(xlsx_path), display="inline"))
        generated.append("XLSX")

    docx_path = export_to_docx(content, base_title)
    if docx_path and docx_path.exists():
        elements.append(cl.File(name=docx_path.name, path=str(docx_path), display="inline"))
        generated.append("DOCX")

    pdf_path = export_to_pdf(content, base_title)
    if pdf_path and pdf_path.exists():
        elements.append(cl.File(name=pdf_path.name, path=str(pdf_path), display="inline"))
        generated.append("PDF")

    if elements:
        await cl.Message(
            content=f"📎 **Export ready:** {' · '.join(generated)} — click to download",
            elements=elements,
            author="Alex 🤖"
        ).send()


# ── Dashboard helpers ─────────────────────────────────────────────────────────
def get_dashboard_stats() -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        today = date.today().isoformat()
        in_30 = (date.today() + timedelta(days=30)).isoformat()
        in_7  = (date.today() + timedelta(days=7)).isoformat()

        active      = conn.execute("SELECT COUNT(*) as n FROM policies WHERE status='active'").fetchone()["n"]
        expiring7   = conn.execute("SELECT COUNT(*) as n FROM policies WHERE status='active' AND end_date<=? AND end_date>=?", (in_7, today)).fetchone()["n"]
        expiring30  = conn.execute("SELECT COUNT(*) as n FROM policies WHERE status='active' AND end_date<=? AND end_date>=?", (in_30, today)).fetchone()["n"]
        clients     = conn.execute("SELECT COUNT(*) as n FROM clients").fetchone()["n"]
        open_claims = conn.execute("SELECT COUNT(*) as n FROM claims WHERE status='open'").fetchone()["n"]
        offers      = conn.execute("SELECT COUNT(*) as n FROM offers").fetchone()["n"]
        conn.close()
        return {"active_policies": active, "expiring_7": expiring7, "expiring_30": expiring30,
                "clients": clients, "open_claims": open_claims, "offers_sent": offers}
    except Exception:
        return {}


async def process_uploaded_file(file: cl.File) -> str:
    """Process an uploaded file with Gemini Vision. Returns analysis text."""
    name_lower = file.name.lower()
    is_image = any(name_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"])
    is_pdf = name_lower.endswith(".pdf")
    is_text = any(name_lower.endswith(ext) for ext in [".txt", ".md", ".csv"])

    if not (is_image or is_pdf or is_text):
        return f"File {file.name} received — format not supported for auto-analysis. Please describe its content."

    # Chainlit 2.x: uploaded files may have content=None, read from path instead
    file_bytes = file.content
    if not file_bytes and file.path:
        file_bytes = Path(file.path).read_bytes()
    if not file_bytes:
        return f"Could not read file content for {file.name}."

    if is_text:
        text_content = file_bytes.decode("utf-8", errors="replace")
        return f"[Text file: {file.name}]\n\n{text_content[:3000]}"

    # Gemini Vision analysis — use flash model for speed (OCR doesn't need 2.5-pro)
    OCR_MODEL = "gemini-2.0-flash"

    if is_image:
        mime_type = (
            "image/jpeg" if name_lower.endswith((".jpg", ".jpeg")) else
            "image/png" if name_lower.endswith(".png") else
            "image/webp" if name_lower.endswith(".webp") else
            "image/jpeg"
        )
    else:
        mime_type = "application/pdf"

    analysis_prompt = """Analyze this insurance-related document.

Extract ALL visible information:

1. **Document Type:** (ID card / insurance policy / accident photo / constatare amiabila / invoice / other)
2. **Extracted Data:**
   - Person/Company name(s)
   - ID/policy numbers
   - Dates (start, end, incident)
   - Amounts/premiums (RON or EUR)
   - Addresses, phone, email
   - Vehicle details if applicable
   - Damage description if accident photo
   - Coverage details if policy
3. **Suggested Next Action:** which broker tool to use

Be concise but complete."""

    try:
        response = client.models.generate_content(
            model=OCR_MODEL,
            contents=[
                types.Part(inline_data=types.Blob(mime_type=mime_type, data=file_bytes)),
                types.Part(text=analysis_prompt)
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1024,
            ),
        )
        analysis = ""
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    analysis += part.text
        return f"[Document analyzed: {file.name}]\n\n{analysis}" if analysis else f"Could not extract content from {file.name}."
    except Exception as e:
        return f"[OCR error for {file.name}]: {str(e)[:200]}"


# ── Auth callback (only active when CHAINLIT_AUTH_SECRET is set) ──────────────
if os.environ.get("CHAINLIT_AUTH_SECRET") and ADMIN_ENABLED:
    @cl.password_auth_callback
    def auth_callback(username: str, password: str):
        user = get_user_by_email(username)
        if not user or not user["is_active"]:
            return None
        if not verify_password(password, user["hashed_password"]):
            return None
        return cl.User(
            identifier=user["email"],
            metadata={
                "user_id": user["id"],
                "role": user["role"],
                "company_id": user["company_id"],
                "full_name": user["full_name"] or user["email"],
            }
        )


# ── Chainlit lifecycle ────────────────────────────────────────────────────────
@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])

    # Load tool permissions for this user
    if ADMIN_ENABLED:
        app_user = cl.user_session.get("user")
        if app_user:
            meta = app_user.metadata or {}
            allowed = get_user_tools(meta.get("user_id"), meta.get("role"))
            cl.user_session.set("allowed_tools", allowed)
            cl.user_session.set("user_meta", meta)
        else:
            # No auth configured — all tools allowed
            cl.user_session.set("allowed_tools", None)
            cl.user_session.set("user_meta", {})
    stats = get_dashboard_stats()

    alerts = ""
    if stats.get("expiring_7", 0) > 0:
        n = stats['expiring_7']
        alerts = f"\n> ⚠️ **{n} {'policy' if n == 1 else 'policies'} expiring within 7 days!** Try: *'Show urgent renewals'*"

    welcome = f"""# 👋 Hello! I'm **Alex**, your Insurance Broker AI.

## 📊 Portfolio Dashboard — {date.today().strftime('%d %B %Y')}

| Metric | Value |
|---|---|
| 🟢 Active Policies | **{stats.get('active_policies', 0)}** |
| ⚠️ Expiring within 7 days | **{stats.get('expiring_7', 0)}** |
| 📅 Expiring within 30 days | **{stats.get('expiring_30', 0)}** |
| 👥 Clients | **{stats.get('clients', 0)}** |
| 📋 Open Claims | **{stats.get('open_claims', 0)}** |
| 📄 Offers Generated | **{stats.get('offers_sent', 0)}** |
{alerts}

---

## 💬 What can I help you with?

**📎 Upload Documents** *(NEW!)*
- Drop a PDF policy scan, accident photo, or ID card — I'll extract the data automatically

**Clients & Policies**
- *"Find client Andrei Ionescu"* · *"Show all active policies"*

**Offers & Comparison**
- *"Search RCA products and generate an offer for CLI001"*
- After offer: *"Send it to the client by email"*

**Renewals**
- *"Show policies expiring in the next 30 days"*

**Claims**
- *"Log a claim for Maria Popescu — parking accident today"*

**Compliance Reports** *(export as PDF/XLSX/DOCX)*
- *"Generate ASF report for February 2026"*
- *"Generate BaFin report for February 2026"*
"""
    await cl.Message(content=welcome, author="Alex 🤖").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming broker message — full agentic loop with Gemini."""
    history = cl.user_session.get("history", [])

    # Build user message parts (text + any uploaded files)
    user_parts = []
    if message.content and message.content.strip():
        user_parts.append(types.Part(text=message.content))

    # Process any uploaded files inline
    if message.elements:
        for element in message.elements:
            has_data = (getattr(element, "content", None) or getattr(element, "path", None))
            if has_data and hasattr(element, "name"):
                try:
                    async with cl.Step(name=f"📄 Analyzing {element.name}...", type="tool", show_input=False) as step:
                        step.output = "Processing with Gemini Vision..."
                        analysis = await process_uploaded_file(element)

                    await cl.Message(
                        content=f"✅ **Document read: {element.name}**\n\n{analysis}\n\n---\n*What would you like me to do with this?*",
                        author="Alex 🤖"
                    ).send()

                    # Add analysis to conversation context
                    user_parts.append(types.Part(text=analysis))
                except Exception as e:
                    await cl.Message(
                        content=f"⚠️ Could not process **{element.name}**: {str(e)[:200]}",
                        author="Alex 🤖"
                    ).send()

    if not user_parts:
        return

    history.append(types.Content(role="user", parts=user_parts))

    async with cl.Step(name="Alex is thinking...", type="run", show_input=False) as thinking_step:
        thinking_step.output = "Processing your request..."

    final_text = ""
    iterations = 0

    while iterations < 10:
        iterations += 1

        # Try primary model, fallback to flash on 503/429
        models_to_try = [MODEL, "gemini-2.0-flash"] if MODEL != "gemini-2.0-flash" else [MODEL]
        response = None
        last_error = None
        for model_attempt in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_attempt,
                    contents=history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=TOOLS,
                        temperature=0.1,
                        max_output_tokens=4096,
                    ),
                )
                # Track token usage
                if ADMIN_ENABLED and response.usage_metadata:
                    _meta = cl.user_session.get("user_meta", {})
                    if _meta.get("user_id"):
                        total_tokens = (
                            getattr(response.usage_metadata, "total_token_count", 0) or
                            (getattr(response.usage_metadata, "prompt_token_count", 0) +
                             getattr(response.usage_metadata, "candidates_token_count", 0))
                        )
                        record_token_usage(
                            company_id=_meta.get("company_id"),
                            user_id=_meta["user_id"],
                            tokens=total_tokens,
                        )
                break  # success
            except Exception as e:
                last_error = str(e)
                if "503" in last_error or "UNAVAILABLE" in last_error or "429" in last_error:
                    continue  # try next model
                # Other errors — don't retry
                await cl.Message(
                    content=f"⚠️ Error: {last_error[:300]}",
                    author="Alex 🤖"
                ).send()
                return

        if response is None:
            await cl.Message(
                content="⚠️ AI models are currently overloaded. Please try again in 30 seconds.",
                author="Alex 🤖"
            ).send()
            return

        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content or not candidate.content.parts:
            final_text = "I couldn't generate a response. Please try again."
            break

        parts = candidate.content.parts
        text_parts = []
        function_calls = []

        for part in parts:
            if hasattr(part, "text") and part.text and part.text.strip():
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                function_calls.append(part.function_call)

        history.append(types.Content(role="model", parts=parts))

        if not function_calls:
            final_text = "\n".join(text_parts) if text_parts else ""
            break

        # ── Execute tool calls ─────────────────────────────────────────────
        function_response_parts = []

        allowed_tools = cl.user_session.get("allowed_tools")  # None = all allowed
        user_meta = cl.user_session.get("user_meta", {})

        for fc in function_calls:
            tool_name = fc.name
            tool_input = dict(fc.args) if fc.args else {}

            # ── Permission gate ────────────────────────────────────────────
            if allowed_tools is not None and tool_name not in allowed_tools:
                denied_result = f"⛔ Access denied: you don't have permission to use '{tool_name}'. Contact your admin."
                if ADMIN_ENABLED and user_meta.get("user_id"):
                    log_audit(
                        user_id=user_meta["user_id"],
                        company_id=user_meta.get("company_id"),
                        tool_name=tool_name,
                        input_summary=str(tool_input)[:200],
                        success=False,
                        tokens=0,
                    )
                function_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": denied_result},
                        )
                    )
                )
                continue

            async with cl.Step(name=f"🔧 {tool_name}", type="tool", show_input=True) as step:
                step.input = json.dumps(tool_input, indent=2, ensure_ascii=False)
                result = execute_tool(tool_name, tool_input)
                step.output = result[:1000] + ("…" if len(result) > 1000 else "")

            # ── Audit log ──────────────────────────────────────────────────
            if ADMIN_ENABLED and user_meta.get("user_id"):
                log_audit(
                    user_id=user_meta["user_id"],
                    company_id=user_meta.get("company_id"),
                    tool_name=tool_name,
                    input_summary=str(tool_input)[:200],
                    success=True,
                    tokens=0,
                )

            function_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    )
                )
            )

            # Attach offer file + export options when offer is created
            if tool_name == "broker_create_offer":
                output_files = sorted(OUTPUT_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
                if output_files:
                    latest = output_files[0]
                    offer_content = latest.read_text(encoding="utf-8")
                    base_title = latest.stem

                    await cl.Message(
                        content=f"📄 **Offer generated:** `{latest.name}`",
                        elements=[cl.File(name=latest.name, path=str(latest), display="inline")],
                        author="Alex 🤖"
                    ).send()

                    # Generate export formats
                    await send_export_files(offer_content, base_title)

            # Attach export for reports
            elif tool_name in ("broker_asf_summary", "broker_bafin_summary"):
                report_type = "ASF" if tool_name == "broker_asf_summary" else "BaFin"
                base_title = f"{report_type}_Report_{date.today().isoformat()}"
                await send_export_files(result, base_title)

        history.append(types.Content(role="user", parts=function_response_parts))

    # ── Send final response ────────────────────────────────────────────────
    cl.user_session.set("history", history)

    if final_text and final_text.strip():
        await cl.Message(content=final_text.strip(), author="Alex 🤖").send()
    else:
        await cl.Message(content="Done. Let me know if you need anything else.", author="Alex 🤖").send()
