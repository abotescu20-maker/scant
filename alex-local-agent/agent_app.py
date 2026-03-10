"""
Alex Local Agent — GUI Application (System Tray)

Cross-platform desktop app for Windows and Mac.
Runs in system tray — no terminal needed.

Build:
    Windows: pyinstaller alex_agent_win.spec
    Mac:     pyinstaller alex_agent_mac.spec
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

# ── Ensure correct working directory when running as frozen exe ─────────────
if getattr(sys, "frozen", False):
    # Running as compiled .exe / .app
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

sys.path.insert(0, str(APP_DIR))

# ── Imports ─────────────────────────────────────────────────────────────────
try:
    import pystray
    from pystray import MenuItem as Item
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

from config import load_config, save_config, configure_interactive
from registry import list_connectors
from main import AlexLocalAgent, AlexAPIClient

# ── Logging to file ─────────────────────────────────────────────────────────
LOG_FILE = Path.home() / ".alex-agent" / "agent.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("alex-agent-app")


# ── Tray Icon Generator ─────────────────────────────────────────────────────

def _make_icon(status: str = "idle") -> Image.Image:
    """
    Generate a simple tray icon.
    status: 'idle' (grey), 'online' (green), 'busy' (orange), 'error' (red)
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    colors = {
        "idle":   "#888888",
        "online": "#22c55e",   # green
        "busy":   "#f97316",   # orange
        "error":  "#ef4444",   # red
    }
    color = colors.get(status, "#888888")

    # Draw circle
    margin = 4
    draw.ellipse([margin, margin, size - margin, size - margin], fill=color)

    # Draw "A" letter (Alex)
    # Simple triangle / letter approximation
    cx, cy = size // 2, size // 2
    pts = [(cx, cy - 18), (cx - 14, cy + 14), (cx + 14, cy + 14)]
    draw.polygon(pts, fill="white")
    draw.polygon([(cx - 6, cy + 4), (cx + 6, cy + 4), (cx + 4, cy + 14), (cx - 4, cy + 14)], fill=color)

    return img


# ── Agent Runner (background thread) ────────────────────────────────────────

class AgentRunner:
    """Runs the polling agent in a background thread."""

    def __init__(self):
        self.agent: AlexLocalAgent | None = None
        self.thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.status = "idle"  # idle, online, busy, error
        self.status_message = "Not running"
        self.tasks_completed = 0
        self._on_status_change = None

    def set_status_callback(self, callback):
        self._on_status_change = callback

    def _notify_status(self):
        if self._on_status_change:
            try:
                self._on_status_change(self.status, self.status_message)
            except Exception:
                pass

    def start(self, config: dict):
        if self.thread and self.thread.is_alive():
            log.info("Agent already running")
            return

        self.status = "online"
        self.status_message = "Starting..."
        self._notify_status()

        def run_in_thread():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self.agent = AlexLocalAgent(config)
                self.agent._on_task_start = self._on_task_start
                self.agent._on_task_done = self._on_task_done
                self.status = "online"
                self.status_message = f"Online — polling {config['alex_url']}"
                self._notify_status()
                self._loop.run_until_complete(self.agent.run())
            except Exception as e:
                log.error(f"Agent error: {e}")
                self.status = "error"
                self.status_message = f"Error: {e}"
                self._notify_status()
            finally:
                self._loop.close()
                self._loop = None

        self.thread = threading.Thread(target=run_in_thread, daemon=True, name="alex-agent")
        self.thread.start()
        log.info("Agent thread started")

    def _on_task_start(self, task_id: str, connector: str, action: str):
        self.status = "busy"
        self.status_message = f"Running: {action} ({connector})"
        self._notify_status()

    def _on_task_done(self, task_id: str, success: bool):
        self.tasks_completed += 1
        self.status = "online"
        self.status_message = f"Online — {self.tasks_completed} tasks done"
        self._notify_status()

    def stop(self):
        if self.agent:
            self.agent.stop()
        self.status = "idle"
        self.status_message = "Stopped"
        self._notify_status()
        log.info("Agent stopped")

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())


# ── System Tray App ──────────────────────────────────────────────────────────

class AlexAgentApp:
    """System tray application."""

    def __init__(self):
        self.runner = AgentRunner()
        self.runner.set_status_callback(self._on_status_change)
        self.tray: pystray.Icon | None = None
        self._config = load_config()

    def _on_status_change(self, status: str, message: str):
        """Update tray icon when status changes."""
        if self.tray:
            self.tray.icon = _make_icon(status)
            self.tray.title = f"Alex Agent — {message}"
            self._rebuild_menu()

    def _rebuild_menu(self):
        """Rebuild tray menu based on current state."""
        if not self.tray:
            return
        self.tray.menu = self._build_menu()

    def _build_menu(self) -> pystray.Menu:
        running = self.runner.is_running()
        cfg = self._config

        items = [
            Item(
                f"Alex Agent — {self.runner.status_message}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
        ]

        if running:
            items.append(Item("⏹  Stop Agent", self._stop))
        else:
            if cfg.get("api_key"):
                items.append(Item("▶  Start Agent", self._start))
            else:
                items.append(Item("⚠️  Configure first", self._open_configure, enabled=True))

        items += [
            pystray.Menu.SEPARATOR,
            Item("⚙️  Configure...", self._open_configure),
            Item("📋  View Logs", self._open_logs),
            Item("🌐  Open Alex Chat", self._open_chat),
            pystray.Menu.SEPARATOR,
            Item("Quit", self._quit),
        ]

        return pystray.Menu(*items)

    def _start(self, icon=None, item=None):
        cfg = load_config()
        if not cfg.get("api_key"):
            self._show_notification("Configure first", "Please run Configure to set your API key.")
            return
        self._config = cfg
        self.runner.start(cfg)
        self._rebuild_menu()

    def _stop(self, icon=None, item=None):
        self.runner.stop()
        self._rebuild_menu()

    def _open_configure(self, icon=None, item=None):
        """Open configuration in a simple dialog or terminal."""
        cfg_file = Path.home() / ".alex-agent" / "config.json"
        cfg_file.parent.mkdir(parents=True, exist_ok=True)

        if platform.system() == "Darwin":
            # Mac: open config file in TextEdit
            os.system(f'open -e "{cfg_file}"')
        elif platform.system() == "Windows":
            # Windows: open config file in Notepad
            os.system(f'notepad "{cfg_file}"')
        else:
            os.system(f'xdg-open "{cfg_file}"')

        # Show a helper notification
        self._show_notification(
            "Config File Opened",
            f"Edit the config file and save it, then restart the agent.\n{cfg_file}",
        )

    def _open_logs(self, icon=None, item=None):
        """Open log file."""
        if platform.system() == "Darwin":
            os.system(f'open -e "{LOG_FILE}"')
        elif platform.system() == "Windows":
            os.system(f'notepad "{LOG_FILE}"')
        else:
            os.system(f'xdg-open "{LOG_FILE}"')

    def _open_chat(self, icon=None, item=None):
        """Open Alex chat in browser."""
        url = self._config.get("alex_url", "https://insurance-broker-alex-603810013022.europe-west3.run.app")
        webbrowser.open(url)

    def _show_notification(self, title: str, message: str):
        if self.tray:
            try:
                self.tray.notify(message, title)
            except Exception:
                pass

    def _quit(self, icon=None, item=None):
        self.runner.stop()
        if self.tray:
            self.tray.stop()

    def run(self):
        """Start the system tray app."""
        if not TRAY_AVAILABLE:
            log.error("pystray/Pillow not available — running in headless mode")
            _run_headless()
            return

        icon_img = _make_icon("idle")
        self.tray = pystray.Icon(
            "alex-agent",
            icon_img,
            "Alex Agent — Idle",
            menu=self._build_menu(),
        )

        # Auto-start if API key is configured
        cfg = load_config()
        if cfg.get("api_key"):
            # Small delay to let tray icon appear first
            threading.Timer(1.5, self._start).start()

        log.info("Starting system tray app")
        self.tray.run()


# ── Headless fallback (when no GUI available) ────────────────────────────────

def _run_headless():
    """Run without GUI — just like python main.py start."""
    cfg = load_config()
    if not cfg.get("api_key"):
        print("⚠️  API key not set.")
        print(f"   Edit: {Path.home() / '.alex-agent' / 'config.json'}")
        sys.exit(1)
    agent = AlexLocalAgent(cfg)
    asyncio.run(agent.run())


# ── First-run Setup ──────────────────────────────────────────────────────────

def _first_run_setup():
    """Create default config if it doesn't exist."""
    cfg_file = Path.home() / ".alex-agent" / "config.json"
    if not cfg_file.exists():
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        default_cfg = {
            "alex_url": "https://insurance-broker-alex-603810013022.europe-west3.run.app",
            "api_key": "",
            "poll_interval": 3,
            "task_timeout": 120,
            "headless_browser": True,
            "gemini_api_key": "",
            "anthropic_api_key": "",
            "log_level": "INFO",
            "agent_id": f"{platform.node()}-{str(uuid.uuid4())[:8]}"
        }
        with open(cfg_file, "w") as f:
            json.dump(default_cfg, f, indent=2)
        log.info(f"Created default config at {cfg_file}")

        # On first run, open config file for editing
        if platform.system() == "Darwin":
            os.system(f'open -e "{cfg_file}"')
        elif platform.system() == "Windows":
            os.system(f'notepad "{cfg_file}"')


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    _first_run_setup()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "configure":
            configure_interactive()
            return
        elif cmd == "status":
            asyncio.run(_print_status())
            return
        elif cmd == "headless":
            _run_headless()
            return

    # Default: run with system tray GUI
    app = AlexAgentApp()
    app.run()


async def _print_status():
    cfg = load_config()
    print(f"\n🤖 Alex Local Agent")
    print(f"   Server:  {cfg['alex_url']}")
    print(f"   API Key: {'✅ Set' if cfg.get('api_key') else '❌ Not set'}")
    print(f"   Connectors: {[c['name'] for c in list_connectors()]}")


if __name__ == "__main__":
    main()
