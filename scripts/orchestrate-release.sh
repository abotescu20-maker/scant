#!/bin/bash
# ScanArt Parallel Release Orchestrator — Level 8
# Runs 3 specialist Claude sessions in parallel, then summarizes.

set -euo pipefail

cd "$(dirname "$0")/.."

VERSION=$(grep -oP "scanart-v\K\d+" frontend/sw.js)
NEXT=$((VERSION + 1))

echo "🎯 Orchestrating parallel release v${NEXT}..."

TMPDIR=$(mktemp -d)

# Phase 1: Bump version
echo "Phase 1: Bumping version v${VERSION} → v${NEXT}..."
sed -i '' "s/scanart-v${VERSION}/scanart-v${NEXT}/g" frontend/sw.js

# Phase 2: Run 3 specialists in parallel
echo "Phase 2: Launching 3 specialist agents..."

claude --print \
  "Build and deploy ScanArt backend v${NEXT}. Run: gcloud builds submit + gcloud run deploy. Report: revision name, deploy status." \
  > "${TMPDIR}/backend.log" 2>&1 &
PID1=$!

claude --print \
  "Sync ScanArt frontend to GCS: gsutil -m rsync -r -d frontend/ gs://scanart-frontend-1772986018. Verify sw.js contains scanart-v${NEXT}." \
  > "${TMPDIR}/frontend.log" 2>&1 &
PID2=$!

claude --print \
  "Visual QA ScanArt: use preview tools to screenshot landing and camera screens. Report any layout issues." \
  > "${TMPDIR}/qa.log" 2>&1 &
PID3=$!

echo "  Backend agent PID: ${PID1}"
echo "  Frontend agent PID: ${PID2}"
echo "  QA agent PID: ${PID3}"

wait ${PID1} ${PID2} ${PID3}

echo ""
echo "Phase 3: Collecting results..."

# Phase 3: Summarize
claude --print \
  "Summarize these 3 parallel release reports into one status:

  BACKEND:
  $(cat ${TMPDIR}/backend.log)

  FRONTEND:
  $(cat ${TMPDIR}/frontend.log)

  VISUAL QA:
  $(cat ${TMPDIR}/qa.log)

  Output a clean release report for v${NEXT}."

rm -rf "${TMPDIR}"
echo "✅ Orchestrated release v${NEXT} complete."
