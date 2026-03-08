#!/usr/bin/env python3
"""
Bootstrap script — creates the superadmin account and default company.
Run once after first deploy:
    python scripts/create_superadmin.py
"""
import sys
import os
from pathlib import Path

# Make sure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from shared.db import get_conn, init_admin_tables
from shared.auth import hash_password, new_id

def main():
    init_admin_tables()
    conn = get_conn()

    # Check if superadmin already exists
    existing = conn.execute("SELECT id FROM users WHERE role='superadmin'").fetchone()
    if existing:
        print("✅ Superadmin already exists. Nothing to do.")
        conn.close()
        return

    print("=== Create Superadmin Account ===")
    email = input("Email: ").strip()
    password = input("Password (min 8 chars): ").strip()
    name = input("Full name: ").strip() or "Super Admin"

    if len(password) < 8:
        print("❌ Password too short.")
        return

    # Create default company
    company_id = new_id("COMP")
    conn.execute(
        "INSERT OR IGNORE INTO companies (id, name, slug, country, plan_tier) VALUES (?, ?, ?, ?, ?)",
        (company_id, "MSP Admin", "msp-admin", "RO", "scale")
    )

    # Create superadmin user
    user_id = new_id("USR")
    conn.execute(
        "INSERT INTO users (id, company_id, email, hashed_password, full_name, role) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, company_id, email, hash_password(password), name, "superadmin")
    )
    conn.commit()
    conn.close()

    print(f"\n✅ Superadmin created!")
    print(f"   Email: {email}")
    print(f"   Company ID: {company_id}")
    print(f"   User ID: {user_id}")
    print(f"\n   Login at: /admin")

if __name__ == "__main__":
    main()
