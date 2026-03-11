#!/usr/bin/env python3
"""Quick diagnostic: print users table content and verify passwords."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-server"))

from shared.db import get_conn, init_admin_tables
from shared.auth import verify_password

init_admin_tables()
conn = get_conn()

rows = conn.execute("SELECT email, hashed_password, is_active, role FROM users").fetchall()
if not rows:
    print("[check] NO USERS FOUND in DB!")
else:
    for r in rows:
        email, hashed, is_active, role = r[0], r[1], r[2], r[3]
        print(f"[check] email={email} is_active={is_active} role={role} hash_prefix={hashed[:20]}")

# Verify demo passwords
for email, pwd in [("admin@demo.ro", "admin123"), ("broker@demo.ro", "broker123")]:
    row = conn.execute("SELECT hashed_password FROM users WHERE email=?", (email,)).fetchone()
    if row:
        ok = verify_password(pwd, row[0])
        print(f"[check] verify_password({email}, {pwd!r}) => {ok}")
    else:
        print(f"[check] {email} NOT FOUND")

conn.close()
