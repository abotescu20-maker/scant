#!/bin/bash
# =====================================================================
# Alex Agent — Mac Installer & Launcher
# =====================================================================
# Dublu-click pe acest fișier pentru a instala și porni Alex Agent.
# Prima rulare: instalare automată (~2 minute, o singură dată)
# Rulări ulterioare: pornire imediată
# =====================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Go to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       Alex Agent — Installer        ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ Python3 nu este instalat.${NC}"
    echo "   Descarcă de la: https://www.python.org/downloads/"
    echo "   Sau instalează cu Homebrew: brew install python3"
    read -p "Apasă Enter pentru a deschide python.org..." _
    open "https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
echo -e "✅ Python $PYTHON_VERSION găsit"

# ── Create/activate virtualenv ───────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo -e "${BLUE}📦 Prima rulare — instalare componente (~2 minute)...${NC}"
    echo ""

    echo "   [1/4] Creare mediu virtual Python..."
    python3 -m venv "$VENV_DIR"

    echo "   [2/4] Instalare pachete..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet \
        requests>=2.31.0 \
        playwright>=1.44.0 \
        pystray>=0.19.5 \
        pillow>=10.0.0 \
        python-dotenv>=1.0.0

    echo "   [3/4] Instalare browser Chromium (~150MB, o singură dată)..."
    "$VENV_DIR/bin/playwright" install chromium

    echo "   [4/4] Instalare completă!"
    echo ""
    echo -e "${GREEN}✅ Alex Agent instalat cu succes!${NC}"
else
    echo -e "✅ Instalare existentă găsită"
    # Quick update check
    "$VENV_DIR/bin/pip" install --quiet --upgrade requests playwright pystray pillow 2>/dev/null || true
fi

# ── Configure if not already done ────────────────────────────────────────────
CONFIG_FILE="$HOME/.alex-agent/config.json"

if [ ! -f "$CONFIG_FILE" ] || ! grep -q '"api_key": "[^"]' "$CONFIG_FILE" 2>/dev/null; then
    echo ""
    echo "═══════════════════════════════════════"
    echo "  Configurare Alex Agent"
    echo "═══════════════════════════════════════"
    echo ""
    echo "  Introdu datele primite de la administrator:"
    echo ""

    read -p "  Alex URL [https://insurance-broker-alex-603810013022.europe-west3.run.app]: " ALEX_URL
    ALEX_URL=${ALEX_URL:-"https://insurance-broker-alex-603810013022.europe-west3.run.app"}

    read -p "  API Key: " API_KEY
    if [ -z "$API_KEY" ]; then
        echo -e "${YELLOW}⚠️  API Key nu poate fi gol. Rulează din nou după ce primești cheia.${NC}"
        exit 1
    fi

    mkdir -p "$HOME/.alex-agent"
    AGENT_ID="$(hostname)-$(python3 -c 'import uuid; print(str(uuid.uuid4())[:8])')"

    cat > "$CONFIG_FILE" <<JSONEOF
{
  "alex_url": "$ALEX_URL",
  "api_key": "$API_KEY",
  "poll_interval": 3,
  "task_timeout": 120,
  "headless_browser": true,
  "gemini_api_key": "",
  "anthropic_api_key": "",
  "log_level": "INFO",
  "agent_id": "$AGENT_ID"
}
JSONEOF

    echo ""
    echo -e "${GREEN}✅ Configurare salvată!${NC}"
    echo "   Agent ID: $AGENT_ID"
fi

# ── Show config ───────────────────────────────────────────────────────────────
ALEX_URL=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('alex_url',''))" 2>/dev/null)
AGENT_ID=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print(d.get('agent_id',''))" 2>/dev/null)

echo ""
echo "═══════════════════════════════════════"
echo "  🤖 Alex Agent pornind..."
echo "═══════════════════════════════════════"
echo "  Server:    $ALEX_URL"
echo "  Agent ID:  $AGENT_ID"
echo "  Log:       ~/.alex-agent/agent.log"
echo ""
echo "  Apasă Ctrl+C pentru a opri."
echo "═══════════════════════════════════════"
echo ""

# ── Start agent ───────────────────────────────────────────────────────────────
PYTHONPATH="$SCRIPT_DIR" "$VENV_DIR/bin/python3" "$SCRIPT_DIR/agent_app.py" headless
