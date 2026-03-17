#!/bin/bash
# ScanArt Analytics — Level 6
# Usage: ./scripts/stats.sh [days]
# Fetches analytics snapshot via the admin API.

set -euo pipefail

DAYS=${1:-7}
BACKEND="https://scanart-backend-603810013022.us-central1.run.app"

if [ -z "${ADMIN_API_KEY:-}" ]; then
  echo "❌ Set ADMIN_API_KEY env var first"
  exit 1
fi

echo "📊 Fetching ScanArt analytics (last ${DAYS} days)..."

curl -s "${BACKEND}/api/admin/stats?key=${ADMIN_API_KEY}&days=${DAYS}" | python3 -m json.tool

echo ""
echo "✅ Done."
