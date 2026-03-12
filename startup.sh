#!/bin/bash
# Startup script for Cloud Run container.
# Runs demo reseed if DB is empty, then starts the app.
set -e

DB="/app/mcp-server/insurance_broker.db"
PYTHONPATH="/app:/app/mcp-server"

# Re-seed demo data if DB has fewer than 5 clients (fresh deploy or empty DB)
CLIENT_COUNT=$(python3 -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('$DB')
    n = conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0]
    conn.close()
    print(n)
except:
    print(0)
" 2>/dev/null || echo 0)

echo "[startup] DB client count: $CLIENT_COUNT"

if [ "$CLIENT_COUNT" -lt 5 ]; then
    echo "[startup] DB is empty or fresh — running demo reseed..."
    PYTHONPATH="$PYTHONPATH" python3 /app/scripts/reseed_demo.py
    echo "[startup] Demo reseed complete."
else
    echo "[startup] DB has data — skipping reseed."
    # Always ensure demo users exist (idempotent, shows all output for debugging)
    PYTHONPATH="$PYTHONPATH" python3 /app/scripts/seed_users.py 2>&1 || true
fi

# Restore conversations + users from Firestore (if available)
# This ensures chat history is NOT lost between Cloud Run deploys
echo "[startup] Restoring persistent data from Firestore..."
PYTHONPATH="$PYTHONPATH" python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from shared.firestore_db import restore_from_firestore_to_sqlite, is_available
    if is_available():
        stats = restore_from_firestore_to_sqlite()
        print('[startup] Firestore restore:', stats)
    else:
        print('[startup] Firestore not available — using local SQLite only')
except Exception as e:
    print('[startup] Firestore restore skipped:', e)
" 2>&1 || echo "[startup] Firestore restore step failed (non-fatal)"

echo "[startup] Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
