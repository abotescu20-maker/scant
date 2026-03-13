#!/bin/bash
# Startup script for Cloud Run container.
# Strategy:
#   1. Always seed demo users (idempotent).
#   2. Restore users/conversations from Firestore.
#   3. Check if broker data (clients, policies, etc.) exists in Firestore:
#      - YES → restore from Firestore (no reseed, data is persistent)
#      - NO  → seed from JSON mock data, then push to Firestore for next time
set -e

DB="/app/mcp-server/insurance_broker.db"
PYTHONPATH="/app:/app/mcp-server"

# Always ensure demo users exist (idempotent)
echo "[startup] Seeding demo users..."
PYTHONPATH="$PYTHONPATH" python3 /app/scripts/seed_users.py 2>&1 || true

# Restore users + conversations from Firestore
echo "[startup] Restoring users/conversations from Firestore..."
PYTHONPATH="$PYTHONPATH" python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from shared.firestore_db import restore_from_firestore_to_sqlite, is_available
    if is_available():
        stats = restore_from_firestore_to_sqlite()
        print('[startup] Firestore user/conv restore:', stats)
    else:
        print('[startup] Firestore not available — using local SQLite only')
except Exception as e:
    print('[startup] Firestore user/conv restore skipped:', e)
" 2>&1 || echo "[startup] Firestore user/conv restore failed (non-fatal)"

# Check if broker data exists in Firestore
echo "[startup] Checking broker data in Firestore..."
BROKER_IN_FIRESTORE=$(PYTHONPATH="$PYTHONPATH" python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from shared.firestore_db import broker_data_exists_in_firestore, is_available
    if is_available() and broker_data_exists_in_firestore():
        print('yes')
    else:
        print('no')
except Exception as e:
    print('no')
" 2>/dev/null || echo "no")

echo "[startup] Broker data in Firestore: $BROKER_IN_FIRESTORE"

if [ "$BROKER_IN_FIRESTORE" = "yes" ]; then
    echo "[startup] Restoring broker data from Firestore (no reseed)..."
    PYTHONPATH="$PYTHONPATH" python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from shared.firestore_db import restore_broker_data_from_firestore
    stats = restore_broker_data_from_firestore()
    print('[startup] Broker data restored from Firestore:', stats)
except Exception as e:
    print('[startup] Broker Firestore restore failed:', e)
" 2>&1 || echo "[startup] Broker Firestore restore failed (non-fatal)"
else
    echo "[startup] No broker data in Firestore — running demo reseed and syncing..."
    PYTHONPATH="$PYTHONPATH" python3 /app/scripts/reseed_demo.py
    echo "[startup] Demo reseed complete. Syncing broker data to Firestore..."
    PYTHONPATH="$PYTHONPATH" python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    from shared.firestore_db import sync_broker_data_to_firestore, is_available
    if is_available():
        stats = sync_broker_data_to_firestore()
        print('[startup] Broker data synced to Firestore:', stats)
    else:
        print('[startup] Firestore not available — broker data not synced')
except Exception as e:
    print('[startup] Broker Firestore sync failed (non-fatal):', e)
" 2>&1 || echo "[startup] Broker Firestore sync failed (non-fatal)"
fi

echo "[startup] Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
