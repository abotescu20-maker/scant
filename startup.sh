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
    # Always ensure demo users exist (idempotent)
    PYTHONPATH="$PYTHONPATH" python3 -c "
import sys; sys.path.insert(0, '/app')
exec(open('/app/scripts/reseed_demo.py').read())
_seed_demo_users()
" 2>&1 | grep -E "(Created|already|WARN|ERROR)" || true
fi

echo "[startup] Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
