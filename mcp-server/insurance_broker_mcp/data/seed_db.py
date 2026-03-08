"""
Seed the SQLite database with mock insurance broker data.
Run once: python -m insurance_broker_mcp.data.seed_db
"""
import sqlite3
import json
import os
from pathlib import Path
from datetime import date

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR.parent.parent / "insurance_broker.db"


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            id_number TEXT,
            phone TEXT NOT NULL,
            email TEXT,
            address TEXT,
            client_type TEXT DEFAULT 'individual',
            country TEXT DEFAULT 'RO',
            source TEXT,
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            policy_type TEXT NOT NULL,
            insurer TEXT NOT NULL,
            policy_number TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            annual_premium REAL NOT NULL,
            insured_sum REAL,
            currency TEXT DEFAULT 'RON',
            installments INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            broker_commission_pct REAL,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        );

        CREATE TABLE IF NOT EXISTS insurers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            country TEXT DEFAULT 'RO',
            products TEXT,
            rating TEXT,
            broker_contact TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            insurer_id TEXT NOT NULL,
            insurer_name TEXT NOT NULL,
            product_type TEXT NOT NULL,
            annual_premium REAL NOT NULL,
            currency TEXT DEFAULT 'RON',
            insured_sum REAL,
            deductible TEXT,
            coverage_summary TEXT,
            exclusions TEXT,
            rating TEXT,
            FOREIGN KEY(insurer_id) REFERENCES insurers(id)
        );

        CREATE TABLE IF NOT EXISTS offers (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            file_path TEXT,
            products_count INTEGER DEFAULT 0,
            notes TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        );

        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            policy_id TEXT NOT NULL,
            incident_date TEXT NOT NULL,
            reported_date TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'open',
            damage_estimate REAL,
            insurer_claim_number TEXT,
            notes TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(policy_id) REFERENCES policies(id)
        );
    """)
    conn.commit()


def seed_data(conn: sqlite3.Connection):
    # Load JSON files
    with open(DATA_DIR / "mock_clients.json") as f:
        clients = json.load(f)
    with open(DATA_DIR / "mock_policies.json") as f:
        policies = json.load(f)
    with open(DATA_DIR / "mock_insurers.json") as f:
        insurers = json.load(f)
    with open(DATA_DIR / "mock_products.json") as f:
        products = json.load(f)

    # Insert clients
    for c in clients:
        conn.execute("""
            INSERT OR REPLACE INTO clients
            (id, name, id_number, phone, email, address, client_type, country, source, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (c["id"], c["name"], c.get("id_number"), c["phone"], c.get("email"),
              c.get("address"), c.get("client_type", "individual"), c.get("country", "RO"),
              c.get("source"), c.get("notes"), c.get("created_at")))

    # Insert insurers
    for ins in insurers:
        conn.execute("""
            INSERT OR REPLACE INTO insurers (id, name, country, products, rating, broker_contact)
            VALUES (?,?,?,?,?,?)
        """, (ins["id"], ins["name"], ins.get("country", "RO"),
              json.dumps(ins.get("products", [])), ins.get("rating"), ins.get("broker_contact")))

    # Insert policies
    for p in policies:
        conn.execute("""
            INSERT OR REPLACE INTO policies
            (id, client_id, policy_type, insurer, policy_number, start_date, end_date,
             annual_premium, insured_sum, currency, installments, status, broker_commission_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (p["id"], p["client_id"], p["policy_type"], p["insurer"], p["policy_number"],
              p["start_date"], p["end_date"], p["annual_premium"], p.get("insured_sum"),
              p.get("currency", "RON"), p.get("installments", 1), p.get("status", "active"),
              p.get("broker_commission_pct")))

    # Insert products
    for prod in products:
        conn.execute("""
            INSERT OR REPLACE INTO products
            (id, insurer_id, insurer_name, product_type, annual_premium, currency,
             insured_sum, deductible, coverage_summary, exclusions, rating)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (prod["id"], prod["insurer_id"], prod["insurer_name"], prod["product_type"],
              prod["annual_premium"], prod.get("currency", "RON"), prod.get("insured_sum"),
              prod.get("deductible"), prod.get("coverage_summary"), prod.get("exclusions"),
              prod.get("rating")))

    conn.commit()
    print(f"✅ Database seeded at: {DB_PATH}")
    print(f"   Clients:  {len(clients)}")
    print(f"   Policies: {len(policies)}")
    print(f"   Insurers: {len(insurers)}")
    print(f"   Products: {len(products)}")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    seed_data(conn)
    conn.close()
