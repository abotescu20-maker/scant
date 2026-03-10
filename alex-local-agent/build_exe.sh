#!/bin/bash
# ============================================================
# Alex Local Agent — Build Script
# ============================================================
# Builds executables for Windows (.exe) and Mac (.app)
#
# Prerequisites (run once):
#   pip install pyinstaller pystray pillow
#   pip install -r requirements.txt
#   playwright install chromium
#
# Usage:
#   ./build_exe.sh          → auto-detect platform
#   ./build_exe.sh windows  → build .exe (run from Windows/WSL)
#   ./build_exe.sh mac      → build .app (run from Mac)
# ============================================================

set -e

PLATFORM=${1:-$(uname -s | tr '[:upper:]' '[:lower:]')}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "🤖 Alex Local Agent — Build"
echo "   Platform: $PLATFORM"
echo "   Directory: $SCRIPT_DIR"
echo ""

# ── Install build dependencies ───────────────────────────────────────────────
echo "📦 Installing build dependencies..."
pip install --quiet pyinstaller pystray pillow

# ── Clean previous build ─────────────────────────────────────────────────────
echo "🧹 Cleaning previous builds..."
rm -rf dist build __pycache__

# ── Generate icon if not present ─────────────────────────────────────────────
if [ ! -f "alex_icon.png" ]; then
    echo "🎨 Generating icon..."
    python3 - <<'PYTHON'
from PIL import Image, ImageDraw
import os

def make_icon():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle — Alex brand green
    draw.ellipse([4, 4, size-4, size-4], fill="#22c55e")

    # "A" letter in white
    cx, cy = size // 2, size // 2
    pts = [(cx, cy - 72), (cx - 56, cy + 56), (cx + 56, cy + 56)]
    draw.polygon(pts, fill="white")
    # Bar of A
    draw.polygon([
        (cx - 24, cy + 16), (cx + 24, cy + 16),
        (cx + 18, cy + 56), (cx - 18, cy + 56)
    ], fill="#22c55e")

    img.save("alex_icon.png")
    print("   Created alex_icon.png")

make_icon()
PYTHON
fi

# ── Platform-specific build ──────────────────────────────────────────────────

if [[ "$PLATFORM" == *"darwin"* ]] || [[ "$PLATFORM" == "mac" ]]; then
    echo "🍎 Building for macOS..."

    # Convert PNG to .icns for Mac
    if [ -f "alex_icon.png" ] && [ ! -f "alex_icon.icns" ]; then
        echo "   Converting icon to .icns..."
        mkdir -p alex_icon.iconset
        sips -z 16 16     alex_icon.png --out alex_icon.iconset/icon_16x16.png 2>/dev/null
        sips -z 32 32     alex_icon.png --out alex_icon.iconset/icon_16x16@2x.png 2>/dev/null
        sips -z 32 32     alex_icon.png --out alex_icon.iconset/icon_32x32.png 2>/dev/null
        sips -z 64 64     alex_icon.png --out alex_icon.iconset/icon_32x32@2x.png 2>/dev/null
        sips -z 128 128   alex_icon.png --out alex_icon.iconset/icon_128x128.png 2>/dev/null
        sips -z 256 256   alex_icon.png --out alex_icon.iconset/icon_128x128@2x.png 2>/dev/null
        sips -z 256 256   alex_icon.png --out alex_icon.iconset/icon_256x256.png 2>/dev/null
        sips -z 512 512   alex_icon.png --out alex_icon.iconset/icon_256x256@2x.png 2>/dev/null
        iconutil -c icns alex_icon.iconset -o alex_icon.icns 2>/dev/null || true
        rm -rf alex_icon.iconset
        echo "   Created alex_icon.icns"
    fi

    pyinstaller alex_agent_mac.spec --clean --noconfirm

    if [ -d "dist/AlexAgent.app" ]; then
        echo ""
        echo "✅ Mac build successful!"
        echo "   Output: dist/AlexAgent.app"
        echo ""
        echo "   Install: drag AlexAgent.app to /Applications"
        echo "   First run: right-click → Open (to bypass Gatekeeper)"

        # Create DMG for distribution
        if command -v create-dmg &>/dev/null; then
            echo ""
            echo "📀 Creating DMG..."
            create-dmg \
                --volname "Alex Agent" \
                --window-pos 200 120 \
                --window-size 600 400 \
                --icon-size 100 \
                --icon "AlexAgent.app" 175 190 \
                --hide-extension "AlexAgent.app" \
                --app-drop-link 425 190 \
                "dist/AlexAgent-1.0.0-mac.dmg" \
                "dist/AlexAgent.app"
            echo "✅ DMG created: dist/AlexAgent-1.0.0-mac.dmg"
        else
            # Simple zip for distribution
            cd dist && zip -r "AlexAgent-1.0.0-mac.zip" "AlexAgent.app" && cd ..
            echo "✅ Zip created: dist/AlexAgent-1.0.0-mac.zip"
        fi
    else
        echo "❌ Build failed — dist/AlexAgent.app not found"
        exit 1
    fi

elif [[ "$PLATFORM" == *"mingw"* ]] || [[ "$PLATFORM" == *"cygwin"* ]] || [[ "$PLATFORM" == "windows" ]]; then
    echo "🪟 Building for Windows..."

    # Convert PNG to .ico for Windows
    if [ -f "alex_icon.png" ] && [ ! -f "alex_icon.ico" ]; then
        echo "   Converting icon to .ico..."
        python3 - <<'PYTHON'
from PIL import Image
img = Image.open("alex_icon.png")
img.save("alex_icon.ico", format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print("   Created alex_icon.ico")
PYTHON
    fi

    pyinstaller alex_agent_win.spec --clean --noconfirm

    if [ -f "dist/AlexAgent.exe" ]; then
        echo ""
        echo "✅ Windows build successful!"
        echo "   Output: dist/AlexAgent.exe"
        echo ""
        echo "   Distribution: copy AlexAgent.exe to employee's computer"
        echo "   First run: AlexAgent.exe (will open config file)"

        # Create zip for distribution
        cd dist && zip "AlexAgent-1.0.0-win.zip" "AlexAgent.exe" && cd ..
        echo "✅ Zip created: dist/AlexAgent-1.0.0-win.zip"
    else
        echo "❌ Build failed — dist/AlexAgent.exe not found"
        exit 1
    fi

else
    echo "ℹ️  Unknown platform: $PLATFORM"
    echo "   Run with 'mac' or 'windows' argument"
    echo "   Example: ./build_exe.sh mac"
    exit 1
fi

echo ""
echo "🎉 Done! Check dist/ folder for the output."
