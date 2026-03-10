"""
Testează dacă screenshot-ul funcționează din acest terminal.
Rulează: python test_screenshot.py

Dacă eșuează → du-te la:
  System Settings → Privacy & Security → Screen Recording
  Activează terminalul tău (Terminal sau iTerm2)
  Repornește terminalul și încearcă din nou.
"""
import subprocess
import tempfile
import os
import sys

print("Testez screenshot...")

with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
    tmp = f.name

result = subprocess.run(
    ["screencapture", "-x", tmp],
    capture_output=True,
    timeout=5,
)

if result.returncode == 0 and os.path.getsize(tmp) > 0:
    size_kb = os.path.getsize(tmp) // 1024
    print(f"✅ Screenshot OK — {size_kb} KB salvat la {tmp}")
    print("   Agentul poate controla desktop-ul.")

    # Try to open it
    subprocess.run(["open", tmp])
else:
    print("❌ Screenshot eșuat!")
    print(f"   Eroare: {result.stderr.decode()}")
    print()
    print("   SOLUȚIE:")
    print("   1. System Settings → Privacy & Security → Screen Recording")
    print("   2. Activează ✅ Terminal (sau iTerm2)")
    print("   3. Repornește terminalul")
    print("   4. Rulează din nou: python test_screenshot.py")
    os.unlink(tmp)
    sys.exit(1)

os.unlink(tmp)

# Also test if we can click
print()
print("Testez PyAutoGUI...")
try:
    import pyautogui
    pos = pyautogui.position()
    print(f"✅ PyAutoGUI OK — cursor la ({pos.x}, {pos.y})")
except Exception as e:
    print(f"❌ PyAutoGUI eroare: {e}")

print()
print("Testez Anthropic SDK...")
try:
    import anthropic
    print(f"✅ Anthropic SDK instalat — versiunea {anthropic.__version__}")
except ImportError:
    print("❌ anthropic nu e instalat — rulează: pip install anthropic")

print()
print("Totul gata! Pornește agentul cu: python main.py start")
