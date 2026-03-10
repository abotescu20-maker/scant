#!/usr/bin/env python3
"""
Comprehensive test script for all 18 Insurance Broker AI tools.
Tests every tool function with valid data, edge cases, and DB verification.

Usage:
    cd ~/Desktop/insurance-broker-agent
    python scripts/test_all_tools.py [--cleanup] [--api]

Options:
    --cleanup   Delete test data created during the run
    --api       Also test n8n REST API endpoints (requires server running on :8080)
"""
import sys
import os
import re
import sqlite3
import traceback
from pathlib import Path
from datetime import date

# ── Path setup (same pattern as app.py) ────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
MCP_DIR = BASE_DIR / "mcp-server"
sys.path.insert(0, str(MCP_DIR))
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# ── Import all tool functions (exact same imports as app.py lines 48-57) ───
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

DB_PATH = MCP_DIR / "insurance_broker.db"
OUTPUT_DIR = MCP_DIR / "output"

# ── ANSI colors ────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── Test infrastructure ────────────────────────────────────────────────────
pass_count = 0
fail_count = 0
results = []


def T(test_name, fn_call, expect_contains=None):
    """Run a test. fn_call is a zero-arg lambda wrapping the actual tool call."""
    global pass_count, fail_count
    try:
        result = fn_call()
        if result is None:
            raise ValueError("Function returned None instead of string")

        result_str = str(result)
        passed = True
        fail_reason = ""

        if expect_contains:
            for substring in expect_contains:
                if substring.lower() not in result_str.lower():
                    passed = False
                    fail_reason = f"Expected '{substring}' not found in result"
                    break

        if passed and "Traceback" in result_str:
            passed = False
            fail_reason = "Python traceback in result"

        if passed:
            pass_count += 1
            results.append((test_name, "PASS", ""))
            print(f"  {GREEN}✓ PASS{RESET}  {test_name}")
        else:
            fail_count += 1
            results.append((test_name, "FAIL", fail_reason))
            print(f"  {RED}✗ FAIL{RESET}  {test_name} — {fail_reason}")
            print(f"         Result preview: {result_str[:200]}")

        return result_str

    except Exception as e:
        fail_count += 1
        err = f"{type(e).__name__}: {e}"
        results.append((test_name, "FAIL", err))
        print(f"  {RED}✗ FAIL{RESET}  {test_name} — {err}")
        traceback.print_exc()
        return ""


def section(title):
    print(f"\n{CYAN}{BOLD}{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}{RESET}\n")


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY A: CLIENT TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("A. CLIENT TOOLS")

T("A1: search by full name",
  lambda: search_clients_fn(query="Andrei Ionescu"),
  ["CLI001", "Andrei Ionescu"])

T("A2: search partial name",
  lambda: search_clients_fn(query="Popescu"),
  ["CLI003", "Maria Popescu"])

T("A3: search by phone",
  lambda: search_clients_fn(query="+40745123456"),
  ["CLI001"])

T("A4: search by email",
  lambda: search_clients_fn(query="office@logistictrans.ro"),
  ["CLI002"])

T("A5: search German client",
  lambda: search_clients_fn(query="Schmidt"),
  ["CLI004", "Johann Schmidt"])

T("A6: search with limit",
  lambda: search_clients_fn(query="CLI", limit=2))

T("A7: search no results",
  lambda: search_clients_fn(query="NONEXISTENT_XYZ_999"),
  ["no client"])

T("A8: get client CLI001",
  lambda: get_client_fn(client_id="CLI001"),
  ["Andrei Ionescu"])

T("A9: get company client CLI002",
  lambda: get_client_fn(client_id="CLI002"),
  ["Logistic Trans"])

T("A10: get German client CLI004",
  lambda: get_client_fn(client_id="CLI004"),
  ["Johann Schmidt"])

T("A11: get invalid client",
  lambda: get_client_fn(client_id="CLI_INVALID_999"),
  ["not found"])

result_a12 = T("A12: create client (minimal)",
               lambda: create_client_fn(name="Test Client Alpha", phone="+40700000001"),
               ["CLI"])

result_a13 = T("A13: create client (full)",
               lambda: create_client_fn(
                   name="Test Client Beta", phone="+40700000002",
                   email="beta@test.com", address="Test Address 123",
                   client_type="company", country="DE", source="test"),
               ["CLI"])

T("A14: search newly created client",
  lambda: search_clients_fn(query="Test Client Alpha"),
  ["Test Client Alpha"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY B: PRODUCT TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("B. PRODUCT TOOLS")

T("B1: search RCA Romania",
  lambda: search_products_fn(product_type="RCA", country="RO"),
  ["Allianz", "Generali", "Omniasig"])

T("B2: search CASCO Romania",
  lambda: search_products_fn(product_type="CASCO", country="RO"),
  ["CASCO"])

T("B3: search KFZ Germany",
  lambda: search_products_fn(product_type="KFZ", country="DE"),
  ["EUR"])

T("B4: search PAD Romania",
  lambda: search_products_fn(product_type="PAD", country="RO"),
  ["PAD"])

T("B5: search CMR Romania",
  lambda: search_products_fn(product_type="CMR", country="RO"),
  ["CMR"])

T("B6: search nonexistent type",
  lambda: search_products_fn(product_type="NONEXISTENT_XYZ", country="RO"),
  ["no product"])

T("B7: search RCA in DE (no results)",
  lambda: search_products_fn(product_type="RCA", country="DE"),
  ["no product"])

T("B8: compare 3 RCA products",
  lambda: compare_products_fn(product_ids="PROD_RCA_ALZ,PROD_RCA_GEN,PROD_RCA_OMA"),
  ["Allianz", "Generali", "Omniasig"])

T("B9: compare 2 KFZ DE products",
  lambda: compare_products_fn(product_ids="PROD_KFZ_ALZ_DE,PROD_KFZ_AXA_DE"),
  ["EUR"])

T("B10: compare single product",
  lambda: compare_products_fn(product_ids="PROD_RCA_ALZ"),
  ["Allianz"])

T("B11: compare invalid product IDs",
  lambda: compare_products_fn(product_ids="INVALID_ID_1,INVALID_ID_2"),
  ["no product"])

T("B12: compare empty string",
  lambda: compare_products_fn(product_ids=""))


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY C: POLICY TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("C. POLICY TOOLS")

T("C1: renewals 30 days",
  lambda: get_renewals_due_fn(days_ahead=30))

T("C2: renewals 365 days",
  lambda: get_renewals_due_fn(days_ahead=365))

T("C3: renewals 1 day",
  lambda: get_renewals_due_fn(days_ahead=1))

T("C4: list all active policies",
  lambda: list_policies_fn(status="active"))

T("C5: list policies for CLI001",
  lambda: list_policies_fn(client_id="CLI001", status="active"),
  ["Andrei Ionescu"])

T("C6: list expired policies",
  lambda: list_policies_fn(status="expired"))

T("C7: list policies invalid client",
  lambda: list_policies_fn(client_id="CLI_INVALID", status="active"),
  ["no polic"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY D: OFFER TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("D. OFFER TOOLS")

result_d1 = T("D1: create offer EN (CLI001 + RCA)",
              lambda: create_offer_fn(
                  client_id="CLI001",
                  product_ids="PROD_RCA_ALZ,PROD_RCA_GEN",
                  language="en", valid_days=30),
              ["OFF-"])

result_d2 = T("D2: create offer RO (CLI003 + CASCO)",
              lambda: create_offer_fn(
                  client_id="CLI003",
                  product_ids="PROD_CASCO_ALZ",
                  language="ro", valid_days=14,
                  notes="Discount 5% oferta speciala"),
              ["OFF-"])

result_d3 = T("D3: create offer DE (CLI004 + KFZ)",
              lambda: create_offer_fn(
                  client_id="CLI004",
                  product_ids="PROD_KFZ_ALZ_DE,PROD_KFZ_AXA_DE",
                  language="de", valid_days=21),
              ["OFF-"])

T("D4: create offer invalid client",
  lambda: create_offer_fn(client_id="CLI_INVALID", product_ids="PROD_RCA_ALZ"),
  ["not found"])

T("D5: create offer invalid product",
  lambda: create_offer_fn(client_id="CLI001", product_ids="INVALID_PROD_1"),
  ["no product"])

T("D6: list all offers",
  lambda: list_offers_fn())

T("D7: list offers for CLI001",
  lambda: list_offers_fn(client_id="CLI001"))

T("D8: list offers invalid client",
  lambda: list_offers_fn(client_id="CLI_INVALID"),
  ["no offer"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY E: CLAIMS TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("E. CLAIMS TOOLS")

result_e1 = T("E1: log claim (valid)",
              lambda: log_claim_fn(
                  client_id="CLI001", policy_id="POL001",
                  incident_date="2026-03-09",
                  description="TEST: Rear-end collision in parking lot",
                  damage_estimate=1500.0),
              ["CLM"])

result_e2 = T("E2: log claim (no estimate)",
              lambda: log_claim_fn(
                  client_id="CLI003", policy_id="POL005",
                  incident_date="2026-03-08",
                  description="TEST: Windshield crack from road debris"))

T("E3: log claim invalid client",
  lambda: log_claim_fn(
      client_id="CLI_INVALID", policy_id="POL001",
      incident_date="2026-03-09", description="Test"),
  ["not found"])

T("E4: log claim invalid policy",
  lambda: log_claim_fn(
      client_id="CLI001", policy_id="POL_INVALID",
      incident_date="2026-03-09", description="Test"),
  ["not found"])

# E5: Get claim status - extract ID from E1
claim_id = ""
if result_e1:
    match = re.search(r'(CLM[A-Z0-9]+)', result_e1)
    if match:
        claim_id = match.group(1)

if claim_id:
    _cid = claim_id  # capture for lambda
    T("E5: get claim status (valid)",
      lambda: get_claim_status_fn(claim_id=_cid),
      ["Andrei Ionescu", "OPEN"])
else:
    print(f"  {YELLOW}⚠ SKIP{RESET}  E5: could not extract claim ID from E1 result")
    results.append(("E5: get claim status (valid)", "SKIP", "claim ID extraction failed"))

T("E6: get claim status invalid",
  lambda: get_claim_status_fn(claim_id="CLM_INVALID_999"),
  ["not found"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY F: COMPLIANCE TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("F. COMPLIANCE TOOLS")

T("F1: ASF report (data month)",
  lambda: asf_summary_fn(month=3, year=2026),
  ["ASF"])

T("F2: ASF report (empty month)",
  lambda: asf_summary_fn(month=1, year=2020))

T("F3: BaFin report (DE data)",
  lambda: bafin_summary_fn(month=10, year=2025),
  ["BaFin"])

T("F4: BaFin report (empty month)",
  lambda: bafin_summary_fn(month=1, year=2020))

T("F5: check RCA by name",
  lambda: check_rca_validity_fn(query="Andrei Ionescu"),
  ["RCA"])

T("F6: check RCA by policy number",
  lambda: check_rca_validity_fn(query="RCA-GEN-2025-001234"),
  ["RCA"])

T("F7: check RCA - no RCA found",
  lambda: check_rca_validity_fn(query="Johann Schmidt"),
  ["no"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY G: ANALYTICS TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("G. ANALYTICS TOOLS — Cross-Sell")

T("G1: cross-sell RO individual (CLI001)",
  lambda: cross_sell_fn(client_id="CLI001"),
  ["CLI001"])

T("G2: cross-sell RO company (CLI002)",
  lambda: cross_sell_fn(client_id="CLI002"),
  ["CLI002"])

T("G3: cross-sell DE individual (CLI004)",
  lambda: cross_sell_fn(client_id="CLI004"),
  ["CLI004"])

T("G4: cross-sell DE company (CLI006)",
  lambda: cross_sell_fn(client_id="CLI006"),
  ["CLI006"])

T("G5: cross-sell invalid client",
  lambda: cross_sell_fn(client_id="CLI_INVALID"),
  ["not found"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY H: CALCULATOR TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("H. CALCULATOR TOOLS — Premium Estimation")

T("H1: RCA default params",
  lambda: calculate_premium_fn(product_type="RCA"),
  ["RCA"])

T("H2: RCA custom (risky profile)",
  lambda: calculate_premium_fn(
      product_type="RCA", age=22, engine_cc=2500,
      bonus_malus_class="M2", zone="Bucuresti"))

T("H3: RCA young driver (19 years)",
  lambda: calculate_premium_fn(product_type="RCA", age=19))

T("H4: RCA experienced (B14 bonus)",
  lambda: calculate_premium_fn(product_type="RCA", bonus_malus_class="B14"))

T("H5: CASCO with vehicle value",
  lambda: calculate_premium_fn(product_type="CASCO", vehicle_value=100000, age=40))

T("H6: CASCO no vehicle value",
  lambda: calculate_premium_fn(product_type="CASCO", vehicle_value=0))

T("H7: unsupported type (HEALTH)",
  lambda: calculate_premium_fn(product_type="HEALTH"))


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY I: COMPLIANCE CHECK TOOLS
# ════════════════════════════════════════════════════════════════════════════
section("I. COMPLIANCE CHECK TOOLS")

T("I1: compliance check CLI001",
  lambda: compliance_check_fn(client_id="CLI001"),
  ["compliance"])

T("I2: compliance check CLI003",
  lambda: compliance_check_fn(client_id="CLI003"),
  ["compliance"])

T("I3: compliance check CLI004 (DE)",
  lambda: compliance_check_fn(client_id="CLI004"),
  ["compliance"])

T("I4: compliance check CLI006 (no policies)",
  lambda: compliance_check_fn(client_id="CLI006"),
  ["compliance"])

T("I5: compliance check invalid client",
  lambda: compliance_check_fn(client_id="CLI_INVALID"),
  ["not found"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY J: EMAIL TOOLS (SMTP not configured)
# ════════════════════════════════════════════════════════════════════════════
section("J. EMAIL TOOLS (SMTP not configured — expected behavior)")

T("J1: email without SMTP config",
  lambda: send_offer_email_fn(offer_id="OFF-TEST123"),
  ["not configured"])

T("J2: email invalid offer ID",
  lambda: send_offer_email_fn(offer_id="OFF_INVALID_99999"),
  ["not configured"])


# ════════════════════════════════════════════════════════════════════════════
#  CATEGORY K: n8n API ENDPOINTS (conditional)
# ════════════════════════════════════════════════════════════════════════════
if "--api" in sys.argv:
    section("K. n8n REST API ENDPOINTS (http://localhost:8080)")

    try:
        import httpx
        _use_httpx = True
    except ImportError:
        _use_httpx = False
        try:
            import requests
        except ImportError:
            print(f"  {YELLOW}⚠ SKIP{RESET}  httpx/requests not installed.")
            requests = None

    BASE_URL = "http://localhost:8080"

    def api_test(test_name, path, expect_key=None):
        global pass_count, fail_count
        try:
            if _use_httpx:
                with httpx.Client(timeout=10) as client:
                    resp = client.get(f"{BASE_URL}{path}")
            else:
                resp = requests.get(f"{BASE_URL}{path}", timeout=10)

            passed = resp.status_code == 200
            fail_reason = ""

            if passed and expect_key:
                body = resp.json()
                if expect_key not in body:
                    passed = False
                    fail_reason = f"Key '{expect_key}' not in response"

            if passed:
                pass_count += 1
                results.append((test_name, "PASS", ""))
                print(f"  {GREEN}✓ PASS{RESET}  {test_name} (HTTP {resp.status_code})")
            else:
                if not fail_reason:
                    fail_reason = f"Expected HTTP 200, got {resp.status_code}"
                fail_count += 1
                results.append((test_name, "FAIL", fail_reason))
                print(f"  {RED}✗ FAIL{RESET}  {test_name} — {fail_reason}")

        except Exception as e:
            fail_count += 1
            err = f"Connection error: {e}"
            results.append((test_name, "FAIL", err))
            print(f"  {RED}✗ FAIL{RESET}  {test_name} — {err}")

    if _use_httpx or requests:
        api_test("K1: GET /health", "/health", "status")
        api_test("K2: GET /api/renewals?days=30", "/api/renewals?days=30", "renewals")
        api_test("K3: GET /api/renewals?days=365", "/api/renewals?days=365", "renewals")
        api_test("K4: GET /api/reports/asf", "/api/reports/asf?month=2&year=2026", "report")
        api_test("K5: GET /api/reports/bafin", "/api/reports/bafin?month=10&year=2025", "report")
        api_test("K6: GET /api/claims/overdue", "/api/claims/overdue?days=14", "overdue_threshold_days")
        api_test("K7: GET /api/clients/search", "/api/clients/search?q=Andrei", "clients")
        api_test("K8: GET /api/clients/search (no results)", "/api/clients/search?q=NONEXISTENT_XYZ")
else:
    print(f"\n{YELLOW}  ⚠ Skipping API tests. Run with --api to test n8n endpoints.{RESET}")


# ════════════════════════════════════════════════════════════════════════════
#  DB VERIFICATION
# ════════════════════════════════════════════════════════════════════════════
section("DB VERIFICATION")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

db_checks_passed = 0
db_checks_total = 0


def db_check(description, query, params=(), min_rows=1):
    global db_checks_passed, db_checks_total
    db_checks_total += 1
    rows = conn.execute(query, params).fetchall()
    if len(rows) >= min_rows:
        db_checks_passed += 1
        print(f"  {GREEN}✓ DB{RESET}   {description} — {len(rows)} row(s)")
    else:
        print(f"  {RED}✗ DB{RESET}   {description} — expected >={min_rows}, got {len(rows)}")


db_check("Test clients created",
         "SELECT * FROM clients WHERE name LIKE 'Test Client%'",
         min_rows=2)

db_check("Test claims created",
         "SELECT * FROM claims WHERE description LIKE 'TEST:%'",
         min_rows=1)

db_check("Offers exist in DB",
         "SELECT * FROM offers",
         min_rows=1)

# Check output files
txt_files = list(OUTPUT_DIR.glob("*.txt"))
md_files = list(OUTPUT_DIR.glob("*.md"))
db_checks_total += 1
if len(txt_files) >= 1:
    db_checks_passed += 1
    print(f"  {GREEN}✓ FS{RESET}   Output files exist — {len(txt_files)} .txt, {len(md_files)} .md")
else:
    print(f"  {RED}✗ FS{RESET}   No output files found in {OUTPUT_DIR}")

db_check("Demo clients intact (6 original)",
         "SELECT * FROM clients WHERE id LIKE 'CLI00%'",
         min_rows=6)

db_check("Demo products intact (10 products)",
         "SELECT * FROM products",
         min_rows=10)

db_check("Demo policies intact",
         "SELECT * FROM policies WHERE status='active'",
         min_rows=1)

db_check("Demo insurers intact",
         "SELECT * FROM insurers",
         min_rows=5)


# ════════════════════════════════════════════════════════════════════════════
#  CLEANUP (optional)
# ════════════════════════════════════════════════════════════════════════════
if "--cleanup" in sys.argv:
    section("CLEANUP — Removing test data")
    conn.execute("DELETE FROM clients WHERE name LIKE 'Test Client%'")
    conn.execute("DELETE FROM claims WHERE description LIKE 'TEST:%'")
    conn.commit()
    print(f"  {GREEN}✓{RESET}  Deleted test clients and claims")

conn.close()


# ════════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═' * 60}")
print(f"  INSURANCE BROKER AI — TEST RESULTS")
print(f"{'═' * 60}{RESET}")
print(f"  Total tests:  {pass_count + fail_count}")
print(f"  {GREEN}PASSED:     {pass_count}{RESET}")
if fail_count > 0:
    print(f"  {RED}FAILED:     {fail_count}{RESET}")
else:
    print(f"  FAILED:     0")
print(f"  DB Checks:    {db_checks_passed}/{db_checks_total}")
print()

if fail_count > 0:
    print(f"  {RED}{BOLD}Failed tests:{RESET}")
    for name, status, reason in results:
        if status == "FAIL":
            print(f"    - {name}: {reason}")
    print()

skipped = [r for r in results if r[1] == "SKIP"]
if skipped:
    print(f"  {YELLOW}Skipped tests:{RESET}")
    for name, _, reason in skipped:
        print(f"    - {name}: {reason}")
    print()

print(f"{'═' * 60}")
sys.exit(1 if fail_count > 0 else 0)
