#!/usr/bin/env python3
"""
Agent Broker Test — simulează un angajat real care folosește Alex.
Trimite mesaje în limbaj natural către Gemini, execută tool calls,
și verifică că răspunsurile sunt corecte.

Rulează fără Chainlit — direct Gemini API + tool dispatch.

Usage:
    cd ~/Desktop/insurance-broker-agent
    python scripts/test_agent_broker.py [--cleanup]
"""
import sys
import os
import re
import json
import sqlite3
import traceback
from pathlib import Path
from datetime import date
from copy import deepcopy

# ── Path setup ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
MCP_DIR = BASE_DIR / "mcp-server"
sys.path.insert(0, str(MCP_DIR))
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# ── Import Gemini SDK ──────────────────────────────────────────────────────
from google import genai
from google.genai import types

api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY nu este setat. Adauga in .env")
    sys.exit(1)

os.environ["GOOGLE_API_KEY"] = api_key
os.environ["GEMINI_API_KEY"] = api_key
client = genai.Client(api_key=api_key)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")

# ── Import all tool functions ──────────────────────────────────────────────
from insurance_broker_mcp.tools.client_tools import search_clients_fn, get_client_fn, create_client_fn
from insurance_broker_mcp.tools.policy_tools import get_renewals_due_fn, list_policies_fn
from insurance_broker_mcp.tools.product_tools import search_products_fn, compare_products_fn
from insurance_broker_mcp.tools.offer_tools import create_offer_fn, list_offers_fn
from insurance_broker_mcp.tools.email_tools import send_offer_email_fn
from insurance_broker_mcp.tools.claims_tools import log_claim_fn, get_claim_status_fn
from insurance_broker_mcp.tools.compliance_tools import asf_summary_fn, bafin_summary_fn, check_rca_validity_fn
from insurance_broker_mcp.tools.analytics_tools import cross_sell_fn
from insurance_broker_mcp.tools.calculator_tools import calculate_premium_fn
from insurance_broker_mcp.tools.compliance_check_tools import compliance_check_fn

# ── Tool dispatch (exact same as app.py) ───────────────────────────────────
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
    "broker_cross_sell":         cross_sell_fn,
    "broker_calculate_premium":  calculate_premium_fn,
    "broker_compliance_check":   compliance_check_fn,
}

def execute_tool(tool_name, tool_input):
    fn = TOOL_DISPATCH.get(tool_name)
    if not fn:
        return f"Toolul '{tool_name}' nu există."
    try:
        result = fn(**tool_input)
        return result if result else "OK"
    except Exception as e:
        return f"Eroare la {tool_name}: {e}"

# ── TOOLS array (same as app.py) ──────────────────────────────────────────
# Import the same tool declarations
sys.path.insert(0, str(BASE_DIR))

# Read TOOLS from app.py by re-using the same declarations
# (We copy the structure to avoid importing chainlit)
TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="broker_search_clients",
            description="Search clients by name, phone, or email address.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "query": types.Schema(type=types.Type.STRING, description="Name, phone, or email to search"),
                "limit": types.Schema(type=types.Type.INTEGER, description="Max results (default 10)"),
            }, required=["query"]),
        ),
        types.FunctionDeclaration(
            name="broker_get_client",
            description="Get full client profile including all their policies.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING, description="Client ID (e.g. CLI001)"),
            }, required=["client_id"]),
        ),
        types.FunctionDeclaration(
            name="broker_create_client",
            description="Create a new client in the database.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "name": types.Schema(type=types.Type.STRING),
                "phone": types.Schema(type=types.Type.STRING),
                "email": types.Schema(type=types.Type.STRING),
                "address": types.Schema(type=types.Type.STRING),
                "client_type": types.Schema(type=types.Type.STRING, description="individual or company"),
                "country": types.Schema(type=types.Type.STRING, description="RO or DE"),
            }, required=["name", "phone"]),
        ),
        types.FunctionDeclaration(
            name="broker_search_products",
            description="Search available insurance products from all partner insurers.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "product_type": types.Schema(type=types.Type.STRING, description="Type: RCA, CASCO, PAD, HOME, LIFE, CMR, KFZ, HEALTH"),
                "country": types.Schema(type=types.Type.STRING, description="RO or DE"),
            }, required=["product_type"]),
        ),
        types.FunctionDeclaration(
            name="broker_compare_products",
            description="Compare multiple insurance products side by side.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "product_ids": types.Schema(type=types.Type.STRING, description="Comma-separated product IDs"),
            }, required=["product_ids"]),
        ),
        types.FunctionDeclaration(
            name="broker_create_offer",
            description="Generate a professional insurance offer document for a client.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING),
                "product_ids": types.Schema(type=types.Type.STRING, description="Comma-separated product IDs"),
                "language": types.Schema(type=types.Type.STRING, description="en, ro, or de"),
                "valid_days": types.Schema(type=types.Type.INTEGER),
                "notes": types.Schema(type=types.Type.STRING),
            }, required=["client_id", "product_ids"]),
        ),
        types.FunctionDeclaration(
            name="broker_list_offers",
            description="List generated offers, optionally filtered by client or status.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING),
                "status": types.Schema(type=types.Type.STRING),
            }),
        ),
        types.FunctionDeclaration(
            name="broker_send_offer_email",
            description="Send a generated offer by email to the client.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "offer_id": types.Schema(type=types.Type.STRING),
                "to_email": types.Schema(type=types.Type.STRING),
            }, required=["offer_id"]),
        ),
        types.FunctionDeclaration(
            name="broker_get_renewals_due",
            description="Get policies expiring within the next N days.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "days_ahead": types.Schema(type=types.Type.INTEGER, description="Days to look ahead (default 30)"),
            }),
        ),
        types.FunctionDeclaration(
            name="broker_list_policies",
            description="List policies, optionally filtered by client ID or status.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING),
                "status": types.Schema(type=types.Type.STRING, description="active, expired, or cancelled"),
            }),
        ),
        types.FunctionDeclaration(
            name="broker_log_claim",
            description="Register a new damage/claims report for a client.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING),
                "policy_id": types.Schema(type=types.Type.STRING),
                "incident_date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                "description": types.Schema(type=types.Type.STRING),
                "damage_estimate": types.Schema(type=types.Type.NUMBER),
            }, required=["client_id", "policy_id", "incident_date", "description"]),
        ),
        types.FunctionDeclaration(
            name="broker_get_claim_status",
            description="Get the status of an existing claim.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "claim_id": types.Schema(type=types.Type.STRING),
            }, required=["claim_id"]),
        ),
        types.FunctionDeclaration(
            name="broker_asf_summary",
            description="Generate monthly ASF regulatory report.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "month": types.Schema(type=types.Type.INTEGER),
                "year": types.Schema(type=types.Type.INTEGER),
            }, required=["month", "year"]),
        ),
        types.FunctionDeclaration(
            name="broker_bafin_summary",
            description="Generate monthly BaFin regulatory report.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "month": types.Schema(type=types.Type.INTEGER),
                "year": types.Schema(type=types.Type.INTEGER),
            }, required=["month", "year"]),
        ),
        types.FunctionDeclaration(
            name="broker_check_rca_validity",
            description="Check RCA validity for a client.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "query": types.Schema(type=types.Type.STRING, description="Client name or policy number"),
            }, required=["query"]),
        ),
        types.FunctionDeclaration(
            name="broker_cross_sell",
            description="Analyze client portfolio and suggest missing products.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING),
            }, required=["client_id"]),
        ),
        types.FunctionDeclaration(
            name="broker_calculate_premium",
            description="Estimate insurance premium based on risk factors.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "product_type": types.Schema(type=types.Type.STRING, description="RCA or CASCO"),
                "age": types.Schema(type=types.Type.INTEGER),
                "engine_cc": types.Schema(type=types.Type.INTEGER),
                "bonus_malus_class": types.Schema(type=types.Type.STRING),
                "vehicle_value": types.Schema(type=types.Type.NUMBER),
            }, required=["product_type"]),
        ),
        types.FunctionDeclaration(
            name="broker_compliance_check",
            description="Check compliance status for a client.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "client_id": types.Schema(type=types.Type.STRING),
            }, required=["client_id"]),
        ),
    ])
]

SYSTEM_PROMPT = """You are Alex, a friendly AI assistant for an insurance brokerage (ASF Romania / BaFin Germany).
You talk in whatever language the broker uses. You ALWAYS call tools first — NEVER answer from memory.
Available tools: broker_search_clients, broker_get_client, broker_create_client, broker_search_products,
broker_compare_products, broker_create_offer, broker_list_offers, broker_send_offer_email,
broker_get_renewals_due, broker_list_policies, broker_log_claim, broker_get_claim_status,
broker_asf_summary, broker_bafin_summary, broker_check_rca_validity, broker_cross_sell,
broker_calculate_premium, broker_compliance_check.
CRITICAL: NEVER mention product names, prices, or client data without calling a tool first."""

# ── ANSI colors ────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# ── Agent conversation engine ──────────────────────────────────────────────

def chat_with_alex(message: str, history: list, max_turns: int = 8) -> tuple:
    """
    Send a message to Alex via Gemini and execute any tool calls.
    Returns (final_answer: str, tools_called: list[str], history: list)
    """
    history.append(types.Content(role="user", parts=[types.Part(text=message)]))
    tools_called = []

    for turn in range(max_turns):
        # Retry on 503 with backoff
        import time
        response = None
        for attempt in range(5):
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=TOOLS,
                        temperature=0.3,
                    ),
                )
                break
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    wait = 3 * (attempt + 1)
                    print(f"    {YELLOW}⏳ Gemini 503 — retry {attempt+1}/5 in {wait}s...{RESET}")
                    time.sleep(wait)
                else:
                    raise
        if response is None:
            raise RuntimeError("Gemini unavailable after 5 retries")

        # Parse response
        parts = response.candidates[0].content.parts if response.candidates else []
        text_parts = []
        function_calls = []

        for part in parts:
            if hasattr(part, "text") and part.text and part.text.strip():
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                function_calls.append(part.function_call)

        # If no function calls, we have the final answer
        if not function_calls:
            final_text = "\n".join(text_parts)
            history.append(types.Content(role="model", parts=[types.Part(text=final_text)]))
            return final_text, tools_called, history

        # Execute function calls
        fn_response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}
            tools_called.append(tool_name)

            print(f"    {DIM}🔧 {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:80]}){RESET}")

            result = execute_tool(tool_name, tool_args)
            # Truncate long results for context window
            if len(result) > 800:
                result = result[:800] + "\n...(truncated)"

            fn_response_parts.append(
                types.Part(function_response=types.FunctionResponse(
                    name=tool_name,
                    response={"result": result}
                ))
            )

        # Add model turn (with function call) and user turn (with function responses)
        model_parts = []
        for fc in function_calls:
            model_parts.append(types.Part(function_call=fc))
        if text_parts:
            model_parts.insert(0, types.Part(text="\n".join(text_parts)))

        history.append(types.Content(role="model", parts=model_parts))
        history.append(types.Content(role="user", parts=fn_response_parts))

    return "(max turns reached)", tools_called, history


# ── Test scenarios ─────────────────────────────────────────────────────────

pass_count = 0
fail_count = 0
results = []


def scenario(name, message, expect_tools=None, expect_in_answer=None, expect_not_in=None, history=None):
    """Run a broker scenario and validate the response."""
    global pass_count, fail_count
    print(f"\n{CYAN}{BOLD}━━━ {name} ━━━{RESET}")
    print(f"  {BLUE}Broker:{RESET} {message}")

    if history is None:
        history = []

    try:
        answer, tools_called, history = chat_with_alex(message, history)
        passed = True
        fail_reason = ""

        # Check expected tools were called
        if expect_tools:
            for tool in expect_tools:
                if not any(tool in tc for tc in tools_called):
                    passed = False
                    fail_reason = f"Tool '{tool}' not called. Called: {tools_called}"
                    break

        # Normalize diacritics for matching
        def normalize(text):
            """Remove Romanian diacritics for fuzzy matching."""
            return (text.lower()
                    .replace("ă", "a").replace("â", "a").replace("î", "i")
                    .replace("ș", "s").replace("ț", "t")
                    .replace("ş", "s").replace("ţ", "t"))

        # Check answer contains expected substrings
        if passed and expect_in_answer:
            answer_norm = normalize(answer)
            for substr in expect_in_answer:
                if normalize(substr) not in answer_norm:
                    passed = False
                    fail_reason = f"Expected '{substr}' not in answer"
                    break

        # Check answer does NOT contain unwanted substrings
        if passed and expect_not_in:
            answer_norm = normalize(answer)
            for substr in expect_not_in:
                if normalize(substr) in answer_norm:
                    passed = False
                    fail_reason = f"Unwanted '{substr}' found in answer"
                    break

        # Print answer preview
        preview = answer[:300].replace('\n', ' ') if answer else "(empty)"
        print(f"  {DIM}Alex: {preview}{RESET}")
        print(f"  {DIM}Tools: {tools_called}{RESET}")

        if passed:
            pass_count += 1
            results.append((name, "PASS", ""))
            print(f"  {GREEN}✓ PASS{RESET}")
        else:
            fail_count += 1
            results.append((name, "FAIL", fail_reason))
            print(f"  {RED}✗ FAIL — {fail_reason}{RESET}")

        return answer, tools_called, history

    except Exception as e:
        fail_count += 1
        err = f"{type(e).__name__}: {e}"
        results.append((name, "FAIL", err))
        print(f"  {RED}✗ FAIL — {err}{RESET}")
        traceback.print_exc()
        return "", [], history or []


# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 1: Dimineata brokerului — reinnoiri
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 1: Dimineata brokerului")
print(f"{'═' * 60}{RESET}")

scenario("S1.1: Salut + reinnoiri",
         "Buna dimineata Alex! Ce polite expira saptamana asta?",
         expect_tools=["broker_get_renewals_due"])

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 2: Flux complet client existent
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 2: Flux complet — client existent")
print(f"{'═' * 60}{RESET}")

_, _, hist2 = scenario("S2.1: Cauta client",
         "Cauta-l pe Andrei Ionescu",
         expect_tools=["broker_search_clients"],
         expect_in_answer=["Andrei Ionescu"])

scenario("S2.2: Profil complet",
         "Arat-mi profilul lui complet cu toate politele",
         expect_tools=["broker_get_client"],
         history=hist2)

scenario("S2.3: Cauta produse RCA",
         "Ce optiuni RCA avem pentru el?",
         expect_tools=["broker_search_products"],
         history=hist2)

scenario("S2.4: Compara produse",
         "Compara-le pe toate 3",
         expect_tools=["broker_compare_products"],
         history=hist2)

scenario("S2.5: Genereaza oferta",
         "Genereaza oferta in romana cu toate cele 3 optiuni pentru Andrei",
         expect_tools=["broker_create_offer"],
         history=hist2)

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 3: Client german
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 3: Client german — KFZ")
print(f"{'═' * 60}{RESET}")

_, _, hist3 = scenario("S3.1: Search German client",
         "Suche nach Johann Schmidt",
         expect_tools=["broker_search_clients"],
         expect_in_answer=["Schmidt"])

scenario("S3.2: KFZ products",
         "Welche KFZ-Versicherungen haben wir?",
         expect_tools=["broker_search_products"],
         history=hist3)

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 4: Daune
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 4: Inregistrare dauna")
print(f"{'═' * 60}{RESET}")

_, _, hist4 = scenario("S4.1: Log claim",
         "Maria Popescu a avut un accident azi dimineata, i-a lovit cineva masina in parcare. Are CASCO la Allianz. Inregistreaza dauna.",
         expect_tools=["broker_search_clients"])  # should search first, then log

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 5: Rapoarte conformitate
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 5: Rapoarte ASF/BaFin")
print(f"{'═' * 60}{RESET}")

scenario("S5.1: Raport ASF",
         "Genereaza raportul ASF pentru martie 2026",
         expect_tools=["broker_asf_summary"],
         expect_in_answer=["ASF"])

scenario("S5.2: Raport BaFin",
         "Acum fa si raportul BaFin pentru luna trecuta",
         expect_tools=["broker_bafin_summary"],
         expect_in_answer=["BaFin"])

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 6: Analytics
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 6: Analitice — cross-sell, premium, compliance")
print(f"{'═' * 60}{RESET}")

scenario("S6.1: Cross-sell",
         "Ce produse ii lipsesc lui Andrei Ionescu? Analizeaza portofoliul",
         expect_tools=["broker_cross_sell"])

scenario("S6.2: Estimare prima RCA",
         "Cat ar costa un RCA pentru un sofer de 22 ani cu BMW 2500cc, clasa malus M2?",
         expect_tools=["broker_calculate_premium"])

scenario("S6.3: Compliance check",
         "Verifica conformitatea dosarului pentru clientul CLI003",
         expect_tools=["broker_compliance_check"])

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 7: Intrebari atipice / edge cases
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 7: Intrebari atipice")
print(f"{'═' * 60}{RESET}")

scenario("S7.1: Intrebare vaga",
         "ce mai am de facut azi?",
         expect_tools=["broker_get_renewals_due"])

scenario("S7.2: Client inexistent",
         "Gaseste-l pe Vasile Habarnam din Slobozia",
         expect_tools=["broker_search_clients"],
         expect_in_answer=["nu", "gasit"])

scenario("S7.3: Produs inexistent",
         "Ce asigurari de PET avem?",
         expect_in_answer=["nu"])

scenario("S7.4: RCA validity check",
         "Verifica RCA-ul lui Andrei Ionescu, mai e valid?",
         expect_tools=["broker_check_rca_validity"],
         expect_in_answer=["RCA"])

# ════════════════════════════════════════════════════════════════════════════
#  SCENARIUL 8: Flux in engleza
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  SCENARIUL 8: English workflow")
print(f"{'═' * 60}{RESET}")

scenario("S8.1: Search in English",
         "Find all policies that are about to expire in the next 60 days",
         expect_tools=["broker_get_renewals_due"])


# ════════════════════════════════════════════════════════════════════════════
#  CLEANUP
# ════════════════════════════════════════════════════════════════════════════
if "--cleanup" in sys.argv:
    DB_PATH = MCP_DIR / "insurance_broker.db"
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM clients WHERE name LIKE 'Test%'")
    conn.execute("DELETE FROM claims WHERE description LIKE 'TEST:%'")
    conn.commit()
    conn.close()
    print(f"\n{GREEN}✓ Cleanup done{RESET}")

# ════════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  AGENT BROKER TEST — RESULTS")
print(f"{'═' * 60}{RESET}")
print(f"  Total scenarios: {pass_count + fail_count}")
print(f"  {GREEN}PASSED: {pass_count}{RESET}")
if fail_count > 0:
    print(f"  {RED}FAILED: {fail_count}{RESET}")
    print(f"\n  {RED}{BOLD}Failed:{RESET}")
    for name, status, reason in results:
        if status == "FAIL":
            print(f"    - {name}: {reason}")
else:
    print(f"  FAILED: 0")
print(f"{'═' * 60}")

sys.exit(1 if fail_count > 0 else 0)
