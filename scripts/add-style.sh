#!/bin/bash
# ScanArt Add Style — Level 6
# Usage: ./scripts/add-style.sh "pixel_art" "Pixel Art" "👾" "#00ff88" "#0088ff"
# Calls Claude Code in headless mode to add a new style using the scanart-style skill.

set -euo pipefail

if [ $# -lt 5 ]; then
  echo "Usage: $0 <style_id> <label> <emoji> <grad_color_1> <grad_color_2>"
  echo "Example: $0 pixel_art 'Pixel Art' '👾' '#00ff88' '#0088ff'"
  exit 1
fi

STYLE_ID="$1"
LABEL="$2"
EMOJI="$3"
GRAD1="$4"
GRAD2="$5"

cd "$(dirname "$0")/.."

echo "🎨 Adding style: ${EMOJI} ${LABEL} (${STYLE_ID})..."

claude --print \
  "Add a new artistic style to ScanArt using the scanart-style skill:
  - style_id: ${STYLE_ID}
  - label: ${LABEL}
  - emoji: ${EMOJI}
  - gradient: ['${GRAD1}', '${GRAD2}']
  Follow the scanart-style skill instructions exactly. Do NOT deploy — just modify the files and report which files were changed."

echo "✅ Style added. Run ./scripts/release.sh to deploy."
