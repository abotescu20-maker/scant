"""
Configuration for Alex Local Agent.

Values are read from environment variables or ~/.alex-agent/config.json
"""
import json
import os
from pathlib import Path

CONFIG_FILE = Path.home() / ".alex-agent" / "config.json"

# Defaults
DEFAULTS = {
    "alex_url": "https://insurance-broker-alex-603810013022.europe-west3.run.app",
    "api_key": "",
    "poll_interval": 3,          # seconds between task polls
    "task_timeout": 120,         # max seconds per task
    "headless_browser": True,    # run Playwright headless
    "gemini_api_key": "",        # for desktop vision + CEDAM
    "anthropic_api_key": "",     # for Anthropic computer_use Mode B (optional)
    "log_level": "INFO",
    "agent_id": "",              # set automatically on first run
}


def load_config() -> dict:
    """Load config from file + environment overrides."""
    cfg = DEFAULTS.copy()

    # Load from config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                file_cfg = json.load(f)
            cfg.update(file_cfg)
        except Exception as e:
            print(f"[Config] Warning: could not read config file: {e}")

    # Environment variable overrides (take priority)
    env_map = {
        "ALEX_URL": "alex_url",
        "ALEX_API_KEY": "api_key",
        "ALEX_POLL_INTERVAL": "poll_interval",
        "GEMINI_API_KEY": "gemini_api_key",
        "ANTHROPIC_API_KEY": "anthropic_api_key",
        "ALEX_HEADLESS": "headless_browser",
        "ALEX_AGENT_ID": "agent_id",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            # Type coercion for non-string values
            if cfg_key in ("poll_interval", "task_timeout"):
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif cfg_key == "headless_browser":
                val = val.lower() not in ("0", "false", "no")
            cfg[cfg_key] = val

    return cfg


def save_config(cfg: dict):
    """Save config to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"[Config] Saved to {CONFIG_FILE}")


def configure_interactive():
    """Interactive CLI configuration wizard."""
    print("\n🤖 Alex Local Agent — Configuration")
    print("=" * 40)

    cfg = load_config()

    alex_url = input(f"Alex URL [{cfg['alex_url']}]: ").strip()
    if alex_url:
        cfg["alex_url"] = alex_url

    api_key = input(f"API Key [{cfg['api_key'][:8]}...]: ").strip()
    if api_key:
        cfg["api_key"] = api_key

    gemini_key = input(f"Gemini API Key [{cfg['gemini_api_key'][:8] if cfg['gemini_api_key'] else ''}...]: ").strip()
    if gemini_key:
        cfg["gemini_api_key"] = gemini_key

    headless = input(f"Headless browser (y/n) [{('y' if cfg['headless_browser'] else 'n')}]: ").strip().lower()
    if headless in ("y", "n"):
        cfg["headless_browser"] = headless == "y"

    # Generate agent ID if not set
    if not cfg["agent_id"]:
        import uuid, platform
        cfg["agent_id"] = f"{platform.node()}-{str(uuid.uuid4())[:8]}"

    save_config(cfg)
    print(f"\n✅ Configuration saved. Agent ID: {cfg['agent_id']}")
    print("Run 'python main.py start' to start the agent.")
    return cfg
