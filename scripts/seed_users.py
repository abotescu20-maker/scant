#!/usr/bin/env python3
"""
Seed demo users into the admin DB. Idempotent — safe to run on every startup.
Creates: admin@demo.ro / admin123  and  broker@demo.ro / broker123
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-server"))

from shared.db import init_admin_tables, get_conn
from shared.auth import hash_password, new_id

DEMO_COMPANY_ID = "COMP-DEMO-01"

BROKER_TOOLS = [
    "broker_search_clients", "broker_get_client", "broker_create_client",
    "broker_update_client", "broker_delete_client",
    "broker_search_products", "broker_compare_products",
    "broker_create_offer", "broker_list_offers", "broker_send_offer_email",
    "broker_get_renewals_due", "broker_list_policies",
    "broker_log_claim", "broker_get_claim_status",
    "broker_generate_report", "broker_check_compliance",
    "broker_check_rca", "broker_run_task", "broker_computer_use_status",
    "broker_calculate_premium", "broker_get_cross_sell",
    "broker_export_excel", "broker_export_docx",
    "broker_upload_document", "broker_analyze_document",
    "broker_search_documents", "broker_knowledge_base_status",
    "broker_reindex_documents",
    "broker_gdrive_upload", "broker_gdrive_list", "broker_gdrive_get_link",
    "broker_sharepoint_upload", "broker_sharepoint_list", "broker_sharepoint_get_link",
    "broker_save_conversation", "broker_get_saved_conversations",
]

def main():
    init_admin_tables()
    conn = get_conn()

    # Company
    conn.execute(
        "INSERT OR IGNORE INTO companies (id, name, slug, country, plan_tier) VALUES (?, ?, ?, ?, ?)",
        (DEMO_COMPANY_ID, "Demo Broker SRL", "demo-broker", "RO", "scale"),
    )

    # Admin user
    if not conn.execute("SELECT id FROM users WHERE email='admin@demo.ro'").fetchone():
        conn.execute(
            "INSERT INTO users (id, company_id, email, hashed_password, full_name, role) VALUES (?, ?, ?, ?, ?, ?)",
            (new_id("USR"), DEMO_COMPANY_ID, "admin@demo.ro",
             hash_password("admin123"), "Admin Demo", "superadmin"),
        )
        print("[seed_users] ✅ Created admin@demo.ro / admin123")
    else:
        print("[seed_users] ✓  admin@demo.ro already exists")

    # Broker user
    existing = conn.execute("SELECT id FROM users WHERE email='broker@demo.ro'").fetchone()
    if not existing:
        broker_id = new_id("USR")
        conn.execute(
            "INSERT INTO users (id, company_id, email, hashed_password, full_name, role) VALUES (?, ?, ?, ?, ?, ?)",
            (broker_id, DEMO_COMPANY_ID, "broker@demo.ro",
             hash_password("broker123"), "Maria Broker", "broker"),
        )
        for t in BROKER_TOOLS:
            conn.execute(
                "INSERT OR IGNORE INTO tool_permissions (user_id, tool_name) VALUES (?, ?)",
                (broker_id, t),
            )
        print("[seed_users] ✅ Created broker@demo.ro / broker123")
    else:
        broker_id = existing[0]
        # Ensure tool permissions exist even if user was created without them
        for t in BROKER_TOOLS:
            conn.execute(
                "INSERT OR IGNORE INTO tool_permissions (user_id, tool_name) VALUES (?, ?)",
                (broker_id, t),
            )
        print("[seed_users] ✓  broker@demo.ro already exists")

    conn.commit()
    conn.close()
    print("[seed_users] Done.")

if __name__ == "__main__":
    main()
