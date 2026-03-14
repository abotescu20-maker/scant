"""
Re-seed demo database with realistic data:
- Clean up test/duplicate clients
- Add realistic policies (spread across future dates)
- Add realistic claims mix
- Keep original 6 core clients + add 4 more realistic ones
- Seed demo users (admin@demo.ro / admin123, broker@demo.ro / broker123)
"""
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "mcp-server" / "insurance_broker.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def d(days_from_now: int) -> str:
    return (date.today() + timedelta(days=days_from_now)).isoformat()

def d_past(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()

def main():
    conn = get_conn()

    print("1. Cleaning up test/duplicate clients...")
    # First remove any policies/offers/claims referencing test clients to avoid FK errors
    conn.execute("""
        DELETE FROM offers WHERE client_id IN (
            SELECT id FROM clients WHERE name LIKE 'Test Client%' OR name LIKE 'Rasdu%' OR name LIKE 'Radu Const%'
        )
    """)
    conn.execute("""
        DELETE FROM claims WHERE client_id IN (
            SELECT id FROM clients WHERE name LIKE 'Test Client%' OR name LIKE 'Rasdu%' OR name LIKE 'Radu Const%'
        )
    """)
    conn.execute("""
        DELETE FROM policies WHERE client_id IN (
            SELECT id FROM clients WHERE name LIKE 'Test Client%' OR name LIKE 'Rasdu%' OR name LIKE 'Radu Const%'
        )
    """)
    conn.execute("""
        DELETE FROM clients WHERE name LIKE 'Test Client%'
        OR name LIKE 'Rasdu%'
        OR name LIKE 'Radu Const%'
    """)
    conn.commit()

    # Keep only the 6 core clients + Anton Botescu
    core_clients = {'CLI001', 'CLI002', 'CLI003', 'CLI004', 'CLI005', 'CLI006', 'CLI4F1AD0'}
    all_clients = [r[0] for r in conn.execute("SELECT id FROM clients").fetchall()]
    extra = [c for c in all_clients if c not in core_clients]
    if extra:
        placeholders = ','.join('?' * len(extra))
        # Clean dependent records first
        conn.execute(f"DELETE FROM offers WHERE client_id IN ({placeholders})", extra)
        conn.execute(f"DELETE FROM claims WHERE client_id IN ({placeholders})", extra)
        conn.execute(f"DELETE FROM policies WHERE client_id IN ({placeholders})", extra)
        conn.execute(f"DELETE FROM clients WHERE id IN ({placeholders})", extra)
        conn.commit()
        print(f"   Removed {len(extra)} extra clients")

    print("2. Adding new demo clients...")
    new_clients = [
        ("CLI007", "Elena Dragomir", "2850412251234", "+40755678901", "elena.dragomir@yahoo.com",
         "Str. Victoriei 22, Cluj-Napoca, 400001", "individual", "RO", "referral",
         "Teacher, interested in life + health insurance. Has PAD at Allianz.", d_past(400)),

        ("CLI008", "SC TechRom SRL", "RO34567890", "+40213456789", "contact@techrom.ro",
         "Bd. Pipera 42, Voluntari, 077190", "company", "RO", "website",
         "IT company, 45 employees. Needs group health + liability + D&O.", d_past(300)),

        ("CLI009", "Gheorghe Popa", "1780901251234", "+40733445566", "gheorghe.popa@gmail.com",
         "Str. Eminescu 7, Timișoara, 300011", "individual", "RO", "phone",
         "Farmer with 3 vehicles + agricultural land. CMR + RCA + PAD needed.", d_past(200)),

        ("CLI010", "Kristina Weber", "DE 987654321", "+4989123456789", "k.weber@weber-bau.de",
         "Leopoldstraße 18, 80802 München", "individual", "DE", "referral",
         "German client, building contractor. Berufshaftpflicht + KFZ (2 cars).", d_past(150)),
    ]

    for c in new_clients:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO clients
                (id, name, id_number, phone, email, address, client_type, country, source, notes, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, c)
        except Exception as e:
            print(f"   Skip {c[0]}: {e}")
    conn.commit()
    print(f"   Added {len(new_clients)} new clients")

    print("3. Resetting policies with realistic future dates...")
    conn.execute("DELETE FROM claims")   # claims reference policies
    conn.execute("DELETE FROM policies")
    conn.commit()

    policies = [
        # CLI001 — Andrei Ionescu: RCA + CASCO (expire in ~11 months — fresh)
        ("POL001", "CLI001", "RCA",   "Generali Romania",           "GEN-RCA-2025-001",
         d_past(20), d(345), 1792.0, 500000.0,  "RON", 1, "active", 12.0),
        ("POL002", "CLI001", "CASCO", "Allianz-Tiriac Asigurari",   "ALZ-CASCO-2025-001",
         d_past(15), d(350), 8430.0, 45000.0,   "RON", 2, "active", 15.0),

        # CLI002 — SC Logistic Trans: RCA fleet + CMR + PAD sediu
        ("POL003", "CLI002", "RCA",   "Omniasig VIG",               "OMA-RCA-FLEET-001",
         d_past(60), d(25),  18400.0, 500000.0, "RON", 4, "active", 10.0),  # expires in 25 days — URGENT
        ("POL004", "CLI002", "CMR",   "Generali Romania",           "GEN-CMR-2025-001",
         d_past(30), d(335), 12600.0, 500000.0, "RON", 2, "active", 12.0),
        ("POL005", "CLI002", "PAD",   "Pool PAD Romania",           "PAD-SED-002-2025",
         d_past(10), d(355), 500.0,   20000.0,  "RON", 1, "active",  5.0),

        # CLI003 — Maria Popescu: CASCO expires in 35 days + PAD fresh
        ("POL006", "CLI003", "CASCO", "Allianz-Tiriac Asigurari",   "ALZ-CASCO-2025-002",
         d_past(330), d(35), 5200.0, 28000.0,   "RON", 1, "active", 15.0),  # expires in 35 days
        ("POL007", "CLI003", "PAD",   "Asirom VIG",                 "ASI-PAD-2025-001",
         d_past(5),  d(360), 120.0,  20000.0,   "RON", 1, "active",  5.0),

        # CLI004 — Johann Schmidt: KFZ (DE) + PAD for Bucharest apt
        ("POL008", "CLI004", "KFZ",   "Allianz Deutschland AG",     "ALZ-DE-KFZ-001",
         d_past(90), d(275), 1250.0, 100000000.0, "EUR", 1, "active", 10.0),
        ("POL009", "CLI004", "PAD",   "Allianz-Tiriac Asigurari",   "ALZ-PAD-SCH-001",
         d_past(20), d(345), 150.0,  20000.0,   "RON", 1, "active",  5.0),

        # CLI005 — Ion Gheorghe: CASCO expires in 13 days — RED URGENT
        ("POL010", "CLI005", "CASCO", "Omniasig VIG",               "OMA-CASCO-2025-001",
         d_past(352), d(13), 7890.0, 35000.0,   "RON", 1, "active", 15.0),  # 13 days!
        ("POL011", "CLI005", "RCA",   "Asirom VIG",                 "ASI-RCA-2025-001",
         d_past(40), d(325), 2100.0, 500000.0,  "RON", 1, "active", 12.0),

        # CLI006 — Immobilien GmbH Müller (DE): Gebäudeversicherung + Haftpflicht
        ("POL012", "CLI006", "GEBÄUDE", "Munich Re",                "MR-DE-GEB-001",
         d_past(180), d(185), 3200.0, 2000000.0, "EUR", 1, "active", 8.0),
        ("POL013", "CLI006", "LIABILITY", "Allianz Deutschland AG", "ALZ-DE-LIAB-001",
         d_past(45), d(320), 1800.0, 5000000.0, "EUR", 1, "active", 10.0),

        # CLI007 — Elena Dragomir: PAD + LIFE
        ("POL014", "CLI007", "PAD",   "Pool PAD Romania",           "PAD-DRG-2025-001",
         d_past(200), d(165), 100.0, 20000.0,   "RON", 1, "active",  5.0),  # expires in 165 days
        ("POL015", "CLI007", "LIFE",  "Grawe Romania",              "GRW-LIFE-2025-001",
         d_past(365), d(730), 4200.0, 200000.0, "RON", 12,"active", 18.0),

        # CLI008 — SC TechRom SRL: LIABILITY + GROUP HEALTH
        ("POL016", "CLI008", "LIABILITY", "Allianz-Tiriac Asigurari", "ALZ-LIAB-TRM-001",
         d_past(100), d(265), 8500.0, 1000000.0, "RON", 2, "active", 12.0),
        ("POL017", "CLI008", "HEALTH", "Generali Romania",          "GEN-GRP-HTH-001",
         d_past(15), d(350), 45000.0, 50000.0,  "RON", 12,"active", 15.0),

        # CLI009 — Gheorghe Popa: RCA x3 vehicles + PAD teren
        ("POL018", "CLI009", "RCA",   "Omniasig VIG",               "OMA-RCA-POP-001",
         d_past(200), d(5),  1500.0, 500000.0,  "RON", 1, "active", 12.0),  # 5 days!
        ("POL019", "CLI009", "RCA",   "Omniasig VIG",               "OMA-RCA-POP-002",
         d_past(100), d(265), 1200.0, 500000.0, "RON", 1, "active", 12.0),
        ("POL020", "CLI009", "PAD",   "Pool PAD Romania",           "PAD-POP-2025-001",
         d_past(50), d(315), 100.0,  20000.0,   "RON", 1, "active",  5.0),

        # CLI010 — Kristina Weber (DE): KFZ x2 + Berufshaftpflicht
        ("POL021", "CLI010", "KFZ",   "HUK-Coburg",                 "HUK-DE-KFZ-WEB1",
         d_past(30), d(335), 890.0, 100000000.0,"EUR", 1, "active", 10.0),
        ("POL022", "CLI010", "KFZ",   "HUK-Coburg",                 "HUK-DE-KFZ-WEB2",
         d_past(30), d(335), 750.0, 100000000.0,"EUR", 1, "active", 10.0),
        ("POL023", "CLI010", "LIABILITY", "Allianz Deutschland AG",  "ALZ-DE-BH-WEB-001",
         d_past(180), d(20), 2100.0, 2000000.0, "EUR", 1, "active", 10.0),  # 20 days — soon

        # CLI4F1AD0 — Anton Botescu: simple RCA
        ("POL024", "CLI4F1AD0", "RCA", "Generali Romania",          "GEN-RCA-BOT-001",
         d_past(300), d(65), 1650.0, 500000.0,  "RON", 1, "active", 12.0),  # 65 days
    ]

    for p in policies:
        try:
            conn.execute("""
                INSERT INTO policies
                (id, client_id, policy_type, insurer, policy_number,
                 start_date, end_date, annual_premium, insured_sum,
                 currency, installments, status, broker_commission_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, p)
        except Exception as e:
            print(f"   Skip {p[0]}: {e}")
    conn.commit()
    print(f"   Added {len(policies)} policies")

    # Urgency summary
    today = date.today()
    urgent_7  = [(p[0], p[2], p[3], p[6]) for p in policies if (date.fromisoformat(p[6]) - today).days <= 7]
    urgent_30 = [(p[0], p[2], p[3], p[6]) for p in policies if (date.fromisoformat(p[6]) - today).days <= 30]
    print(f"\n   🔴 Expiring ≤7 days:  {len(urgent_7)}")
    for p in urgent_7:
        print(f"      {p[0]} {p[1]} @ {p[2]} — {p[3]}")
    print(f"   🟡 Expiring ≤30 days: {len(urgent_30)}")
    for p in urgent_30:
        print(f"      {p[0]} {p[1]} @ {p[2]} — {p[3]}")

    print("\n4. Resetting claims with realistic data...")
    conn.execute("DELETE FROM claims")
    conn.commit()

    # Schema: id, client_id, policy_id, incident_date, reported_date,
    #         description, status, damage_estimate, insurer_claim_number, notes
    claims = [
        # Open claims
        ("CLM001", "CLI001", "POL002", d_past(15), d_past(14),
         "Minor accident on DN1, front bumper damaged. Other party: Popescu Ion, B-12-XYZ.",
         "open", 3200.0, "ALZ-CASCO-DMG-2025-001",
         "CASCO claim. Waiting for repair estimate from authorized service."),

        ("CLM002", "CLI002", "POL003", d_past(8), d_past(7),
         "Truck driver hit a parked vehicle in Ploiești. Third party claims vehicle + medical damages.",
         "investigating", 9700.0, "OMA-RCA-INV-2025-007",
         "RCA TPL. Insurer investigating liability. Legal department notified."),

        ("CLM003", "CLI009", "POL018", d_past(3), d_past(3),
         "Rear-end collision on E70 near Timișoara. Third party vehicle: Dacia Logan. Estimate pending.",
         "open", None, None,
         "RCA claim. Police report filed PV-2025-1847. Waiting for damage estimate."),

        # Closed/paid claims
        ("CLM004", "CLI003", "POL006", d_past(90), d_past(88),
         "Catalytic converter stolen from parking lot at night.",
         "paid", 2100.0, "ALZ-CASCO-THF-2025-003",
         "CASCO theft. Police report PV 1234/2025. Paid after deductible."),

        ("CLM005", "CLI005", "POL010", d_past(45), d_past(44),
         "Hail damage — multiple dents on roof, hood, boot lid.",
         "paid", 5800.0, "OMA-CASCO-HAIL-2025-011",
         "CASCO weather damage. Paid in full, no deductible applied."),

        ("CLM006", "CLI007", "POL014", d_past(120), d_past(118),
         "Basement flooding during heavy rain, furniture and floor damaged.",
         "paid", 8000.0, "PAD-2025-FLD-007",
         "PAD flood claim Zone B. Full payout 8,000 RON."),

        # Recent new claim
        ("CLM007", "CLI008", "POL016", d_past(2), d_past(1),
         "Client (Nexus SRL) alleges software project delivered 3 weeks late, claims €15,000 penalty.",
         "open", 15000.0, None,
         "Liability / professional indemnity. TechRom disputes delay cause. Legal review in progress."),
    ]

    for c in claims:
        try:
            conn.execute("""
                INSERT INTO claims
                (id, client_id, policy_id, incident_date, reported_date,
                 description, status, damage_estimate, insurer_claim_number, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, c)
        except Exception as e:
            print(f"   Skip claim {c[0]}: {e}")
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    print(f"   Added {count} claims")

    print("\n5. Final stats:")
    for tbl in ["clients", "policies", "claims", "products", "offers"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"   {tbl}: {n}")

    conn.close()

    print("\n6. Seeding demo users (admin@demo.ro, broker@demo.ro)...")
    _seed_demo_users()

    print("\n✅ Demo DB reseeded successfully!")


def _seed_demo_users():
    """Create demo company and users for the Chainlit login. Idempotent."""
    try:
        from shared.db import init_admin_tables, get_conn as _get_conn
        from shared.auth import hash_password, new_id
    except ImportError as e:
        print(f"   WARN: Could not import shared modules ({e}) — skipping user seed.")
        return

    init_admin_tables()
    c = _get_conn()

    # Demo company
    demo_company_id = "COMP-DEMO-01"
    c.execute(
        "INSERT OR IGNORE INTO companies (id, name, slug, country, plan_tier) VALUES (?, ?, ?, ?, ?)",
        (demo_company_id, "Demo Broker SRL", "demo-broker", "RO", "scale"),
    )

    # admin@demo.ro — superadmin (all tools, admin panel access)
    if not c.execute("SELECT id FROM users WHERE email='admin@demo.ro'").fetchone():
        c.execute(
            "INSERT INTO users (id, company_id, email, hashed_password, full_name, role) VALUES (?, ?, ?, ?, ?, ?)",
            (new_id("USR"), demo_company_id, "admin@demo.ro",
             hash_password("admin123"), "Admin Demo", "superadmin"),
        )
        print("   ✅ Created admin@demo.ro / admin123")
    else:
        print("   ✓  admin@demo.ro already exists")

    # broker@demo.ro — broker role
    if not c.execute("SELECT id FROM users WHERE email='broker@demo.ro'").fetchone():
        broker_id = new_id("USR")
        c.execute(
            "INSERT INTO users (id, company_id, email, hashed_password, full_name, role) VALUES (?, ?, ?, ?, ?, ?)",
            (broker_id, demo_company_id, "broker@demo.ro",
             hash_password("broker123"), "Maria Broker", "broker"),
        )
        # Give broker access to all standard tools
        broker_tools = [
            "broker_search_clients", "broker_get_client", "broker_create_client",
            "broker_update_client", "broker_search_products", "broker_compare_products",
            "broker_create_offer", "broker_list_offers", "broker_send_offer_email",
            "broker_get_renewals_due", "broker_list_policies",
            "broker_log_claim", "broker_get_claim_status",
            "broker_generate_report", "broker_check_compliance",
            "broker_check_rca", "broker_run_task", "broker_computer_use_status",
            "broker_calculate_premium", "broker_compare_premiums_live", "broker_scrape_rca_prices",
            "broker_get_cross_sell",
            "broker_export_excel", "broker_export_docx",
            "broker_save_conversation", "broker_get_saved_conversations",
        ]
        for t in broker_tools:
            c.execute("INSERT OR IGNORE INTO tool_permissions (user_id, tool_name) VALUES (?, ?)",
                      (broker_id, t))
        print("   ✅ Created broker@demo.ro / broker123")
    else:
        print("   ✓  broker@demo.ro already exists")

    c.commit()
    c.close()

if __name__ == "__main__":
    main()
