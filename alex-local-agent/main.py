"""
Alex Local Agent — main polling loop.

This script runs on the employee's local machine.
It polls the Alex Cloud Run server for tasks, executes them
using the appropriate connector, and returns results.

Usage:
    python main.py start        # start the agent (polling loop)
    python main.py configure    # interactive configuration wizard
    python main.py status       # show current status and connectors
    python main.py test cedam B123ABC   # test a connector directly

Install:
    pip install -r requirements.txt
    playwright install chromium
    python main.py configure
    python main.py start
"""
from __future__ import annotations

import asyncio
import json
import logging
import platform
import sys
import time
import uuid
from datetime import datetime
from typing import Optional

import requests

from config import load_config, configure_interactive
from registry import list_connectors, create_connector

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alex-agent")


# ── API Client ─────────────────────────────────────────────────────────────

class AlexAPIClient:
    """Simple REST client for communicating with Alex Cloud Run."""

    def __init__(self, base_url: str, api_key: str, agent_id: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "X-Agent-ID": agent_id,
            "X-Agent-Platform": platform.system(),
            "Content-Type": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def poll_tasks(self) -> list[dict]:
        """GET /cu/tasks — fetch pending tasks for this agent."""
        try:
            r = self.session.get(
                self._url("/cu/tasks"),
                timeout=30,  # 30s to handle Cloud Run cold starts
            )
            r.raise_for_status()
            return r.json().get("tasks", [])
        except requests.exceptions.ConnectionError:
            log.debug("Connection error polling tasks — server may be down")
            return []
        except requests.exceptions.ReadTimeout:
            log.debug("Poll timeout — server busy, will retry")
            return []
        except Exception as e:
            log.warning(f"Error polling tasks: {e}")
            return []

    def send_result(self, task_id: str, result: dict):
        """POST /cu/results — send task result back to Alex."""
        try:
            payload = {
                "task_id": task_id,
                "agent_id": self.agent_id,
                "result": result,
                "completed_at": datetime.utcnow().isoformat(),
            }
            r = self.session.post(
                self._url("/cu/results"),
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            log.debug(f"Result sent for task {task_id}")
        except Exception as e:
            log.error(f"Failed to send result for {task_id}: {e}")

    def send_heartbeat(self, connectors: list[str]):
        """POST /cu/heartbeat — report agent is online."""
        try:
            payload = {
                "agent_id": self.agent_id,
                "platform": platform.system(),
                "python": platform.python_version(),
                "connectors": connectors,
                "timestamp": datetime.utcnow().isoformat(),
            }
            r = self.session.post(
                self._url("/cu/heartbeat"),
                json=payload,
                timeout=10,
            )
            r.raise_for_status()
        except Exception as e:
            log.debug(f"Heartbeat failed: {e}")


# ── Task Executor ──────────────────────────────────────────────────────────

class TaskExecutor:
    """
    Executes computer-use tasks using the appropriate connector.

    Task format (from Cloud Run):
    {
        "task_id": "uuid",
        "connector": "cedam",          # which connector to use
        "action": "extract",           # action: login/extract/fill_form/screenshot/click/navigate
        "params": {                    # action-specific params
            "query": "RCA pentru B123ABC",
            "plate": "B123ABC"
        },
        "credentials": {...},          # optional, for login action
        "timeout": 60,                 # max seconds
    }
    """

    def __init__(self, config: dict):
        self.config = config
        self._active_connectors: dict[str, object] = {}

    async def execute(self, task: dict) -> dict:
        """Execute a single task and return the result."""
        task_id = task.get("task_id", "unknown")
        connector_name = task.get("connector", "web_generic")
        action = task.get("action", "extract")
        params = task.get("params", {})
        credentials = task.get("credentials", {})
        timeout = task.get("timeout", self.config.get("task_timeout", 120))

        log.info(f"[Task {task_id[:8]}] connector={connector_name} action={action}")
        if action == "run_task" and params.get("instruction"):
            log.info(f"[Task {task_id[:8]}] instruction='{params['instruction']}'")

        try:
            connector = await self._get_or_create_connector(connector_name)
        except Exception as e:
            return {"success": False, "error": f"Cannot create connector '{connector_name}': {e}"}

        try:
            result = await asyncio.wait_for(
                self._run_action(connector, action, params, credentials),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            result = {"success": False, "error": f"Task timed out after {timeout}s"}
        except Exception as e:
            result = {"success": False, "error": str(e)}

        log.info(f"[Task {task_id[:8]}] done — success={result.get('success')}")
        return result

    async def _get_or_create_connector(self, name: str):
        """Get cached connector or create new one."""
        if name not in self._active_connectors:
            connector = create_connector(
                name,
                headless=self.config.get("headless_browser", True),
            )
            if connector is None:
                raise ValueError(f"Unknown connector: '{name}'. Available: {list(self._active_connectors.keys())}")

            # Inject API keys
            if hasattr(connector, "gemini_api_key") and not connector.gemini_api_key:
                connector.gemini_api_key = self.config.get("gemini_api_key", "")
            if hasattr(connector, "api_key") and not connector.api_key:
                connector.api_key = self.config.get("anthropic_api_key", "")

            await connector.setup()
            self._active_connectors[name] = connector
            log.info(f"Connector '{name}' started")

        return self._active_connectors[name]

    async def _run_action(self, connector, action: str, params: dict, credentials: dict) -> dict:
        """Dispatch to the correct connector method."""
        if action == "login":
            return await connector.login(credentials)
        elif action == "extract":
            query = params.get("query", "")
            return await connector.extract(query, params)
        elif action == "fill_form":
            fields = params.get("fields", params)
            return await connector.fill_form(fields)
        elif action == "screenshot":
            png = await connector.screenshot()
            if png:
                return {
                    "success": True,
                    "screenshot_b64": connector.screenshot_to_base64(png),
                    "size_bytes": len(png),
                }
            return {"success": False, "error": "Screenshot failed"}
        elif action == "navigate":
            target = params.get("url") or params.get("target", "")
            return await connector.navigate(target)
        elif action == "click":
            target = params.get("target", "")
            return await connector.click(target)
        elif action == "type":
            field = params.get("field", "")
            text = params.get("text", "")
            return await connector.type_text(field, text)
        elif action == "wait_for":
            condition = params.get("condition", "")
            timeout = params.get("timeout", 30)
            return await connector.wait_for(condition, timeout)
        elif action == "check_rca":
            # CEDAM-specific shorthand
            plate = params.get("plate", "")
            if hasattr(connector, "check_rca"):
                return await connector.check_rca(plate)
            return {"success": False, "error": "check_rca not supported by this connector"}
        elif action == "read_screen":
            question = params.get("question", "What do you see on the screen?")
            if hasattr(connector, "read_screen"):
                return await connector.read_screen(question)
            return {"success": False, "error": "read_screen not supported by this connector"}
        elif action == "run_task":
            instruction = params.get("instruction", "")
            max_steps = params.get("max_steps", 10)
            if hasattr(connector, "run_task"):
                return await connector.run_task(instruction, max_steps=max_steps)
            return {"success": False, "error": "run_task not supported by this connector"}
        elif action == "open_app_and_type":
            # Direct action — no regex needed. params: {app: "TextEdit", text: "hello"}
            app = params.get("app", "")
            text = params.get("text", "")
            if hasattr(connector, "open_app_and_type"):
                return await connector.open_app_and_type(app, text)
            return {"success": False, "error": "open_app_and_type not supported by this connector"}
        else:
            return {"success": False, "error": f"Unknown action: '{action}'"}

    async def teardown_all(self):
        """Close all active connectors."""
        for name, connector in self._active_connectors.items():
            try:
                await connector.teardown()
                log.info(f"Connector '{name}' closed")
            except Exception as e:
                log.warning(f"Error closing connector '{name}': {e}")
        self._active_connectors.clear()


# ── Main Polling Loop ──────────────────────────────────────────────────────

class AlexLocalAgent:
    """Main agent — polls for tasks and executes them."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False

        if not config.get("agent_id"):
            config["agent_id"] = f"{platform.node()}-{str(uuid.uuid4())[:8]}"

        self.api = AlexAPIClient(
            base_url=config["alex_url"],
            api_key=config["api_key"],
            agent_id=config["agent_id"],
        )
        self.executor = TaskExecutor(config)
        self._last_heartbeat = 0.0
        self._heartbeat_interval = 10  # seconds (was 30 — shorter interval so agent re-registers faster after Cloud Run restart)

    async def run(self):
        """Main loop."""
        self.running = True
        poll_interval = self.config.get("poll_interval", 3)
        available_connectors = [c["name"] for c in list_connectors()]

        log.info(f"🤖 Alex Local Agent starting")
        log.info(f"   Agent ID: {self.config['agent_id']}")
        log.info(f"   Server:   {self.config['alex_url']}")
        log.info(f"   Connectors: {', '.join(available_connectors)}")
        log.info(f"   Polling every {poll_interval}s")
        log.info("   Press Ctrl+C to stop")
        print()

        # Send heartbeat immediately on start (don't wait 10s for Alex to see us)
        self.api.send_heartbeat(available_connectors)
        self._last_heartbeat = time.time()
        log.info("✅ Heartbeat sent — agent registered with server")

        try:
            while self.running:
                # Send heartbeat periodically
                now = time.time()
                if now - self._last_heartbeat > self._heartbeat_interval:
                    self.api.send_heartbeat(available_connectors)
                    self._last_heartbeat = now

                # Poll for tasks
                tasks = self.api.poll_tasks()

                if tasks:
                    log.info(f"📋 Got {len(tasks)} task(s)")
                    # Execute tasks concurrently (if multiple)
                    await asyncio.gather(*[self._handle_task(t) for t in tasks])
                else:
                    await asyncio.sleep(poll_interval)

        except KeyboardInterrupt:
            log.info("Stopping agent...")
        finally:
            await self.executor.teardown_all()
            log.info("✅ Agent stopped")

    async def _handle_task(self, task: dict):
        """Execute a task and send result back."""
        task_id = task.get("task_id", "unknown")
        try:
            result = await self.executor.execute(task)
        except Exception as e:
            result = {"success": False, "error": str(e)}
        self.api.send_result(task_id, result)

    def stop(self):
        self.running = False


# ── CLI Entry Point ────────────────────────────────────────────────────────

async def cmd_status():
    """Print agent status and available connectors."""
    cfg = load_config()
    print(f"\n🤖 Alex Local Agent Status")
    print(f"   Server:    {cfg['alex_url']}")
    print(f"   Agent ID:  {cfg.get('agent_id', '(not set)')}")
    print(f"   API Key:   {'✅ Set' if cfg.get('api_key') else '❌ Not set'}")
    print(f"   Gemini:    {'✅ Set' if cfg.get('gemini_api_key') else '❌ Not set (desktop automation disabled)'}")
    print(f"   Anthropic: {'✅ Set (computer_use Mode B activ)' if cfg.get('anthropic_api_key') else '⚪ Not set (optional — adaugă pentru Mode B)'}")
    print()
    print("   Available connectors:")
    for c in list_connectors():
        req = "  [requires display]" if c.get("requires_display") else ""
        print(f"   • {c['name']:20s} — {c['description']}{req}")
    print()


async def cmd_test(connector_name: str, *args):
    """Test a connector directly from CLI."""
    cfg = load_config()
    print(f"\n🧪 Testing connector: {connector_name}")

    connector = create_connector(
        connector_name,
        headless=cfg.get("headless_browser", True),
    )
    if connector is None:
        print(f"❌ Unknown connector: '{connector_name}'")
        print(f"   Available: {[c['name'] for c in list_connectors()]}")
        return

    if cfg.get("gemini_api_key") and hasattr(connector, "gemini_api_key"):
        connector.gemini_api_key = cfg["gemini_api_key"]

    try:
        await connector.setup()
        print(f"✅ Connector '{connector_name}' started")

        if connector_name == "cedam" and args:
            plate = args[0]
            print(f"   Checking RCA for plate: {plate}")
            result = await connector.check_rca(plate)
            print(f"\n📋 Result:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        elif args:
            query = " ".join(args)
            print(f"   Extracting: {query}")
            result = await connector.extract(query)
            print(f"\n📋 Result:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    finally:
        await connector.teardown()


def main():
    import sys
    args = sys.argv[1:]
    cmd = args[0] if args else "start"

    if cmd == "configure":
        configure_interactive()
    elif cmd == "status":
        asyncio.run(cmd_status())
    elif cmd == "test" and len(args) >= 2:
        asyncio.run(cmd_test(*args[1:]))
    elif cmd == "start":
        cfg = load_config()
        if not cfg.get("api_key"):
            print("⚠️  API key not set. Run 'python main.py configure' first.")
            sys.exit(1)
        agent = AlexLocalAgent(cfg)
        asyncio.run(agent.run())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
