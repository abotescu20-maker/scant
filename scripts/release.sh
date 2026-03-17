#!/bin/bash
# ScanArt Headless Release — Level 6
# Usage: ./scripts/release.sh
# Calls Claude Code in headless mode to run the full release pipeline.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "🚀 Starting headless ScanArt release..."

claude --print \
  "Run the scanart-release skill. Auto-detect the current version from sw.js, increment it, and execute all 5 phases (bump, build, deploy, sync, test). Report a JSON summary with keys: version, revision, backend_url, frontend_url, tests_passed, tests_total."

echo "✅ Release complete."
