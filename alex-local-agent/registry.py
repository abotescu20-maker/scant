"""
Connector Registry — maps connector names to their classes.

To add a new connector:
1. Create connectors/connector_<name>.py with a class inheriting BaseConnector
2. Import it here
3. Add it to CONNECTORS dict

Alex (Cloud Run) sends tasks with connector="cedam" →
the local agent looks up CEDAMConnector here and instantiates it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from connectors.base import BaseConnector

# ── Lazy imports (avoid crashing if optional deps missing) ─────────────────


def _get_connector_classes():
    """Returns dict of all available connector classes."""
    connectors = {}

    try:
        from connectors.connector_web_generic import GenericWebConnector
        connectors["web_generic"] = GenericWebConnector
        connectors["web"] = GenericWebConnector  # alias
    except ImportError as e:
        print(f"[Registry] GenericWebConnector not available: {e}")

    try:
        from connectors.connector_desktop_generic import GenericDesktopConnector
        connectors["desktop_generic"] = GenericDesktopConnector
        connectors["desktop"] = GenericDesktopConnector  # alias
    except ImportError as e:
        print(f"[Registry] GenericDesktopConnector not available: {e}")

    try:
        from connectors.connector_cedam import CEDAMConnector
        connectors["cedam"] = CEDAMConnector
    except ImportError as e:
        print(f"[Registry] CEDAMConnector not available: {e}")

    try:
        from anthropic_mode import AnthropicComputerUseConnector
        connectors["anthropic_computer_use"] = AnthropicComputerUseConnector
        connectors["claude_computer_use"] = AnthropicComputerUseConnector  # alias
    except ImportError as e:
        print(f"[Registry] AnthropicComputerUseConnector not available: {e}")

    try:
        from connectors.connector_paid import PAIDConnector
        connectors["paid"] = PAIDConnector
    except ImportError as e:
        print(f"[Registry] PAIDConnector not available: {e}")

    try:
        from connectors.connector_allianz import AllianzConnector
        connectors["allianz"] = AllianzConnector
        connectors["allianz_ro"] = AllianzConnector  # alias
    except ImportError as e:
        print(f"[Registry] AllianzConnector not available: {e}")

    return connectors


# Singleton registry — built on first access
_REGISTRY: dict | None = None


def get_registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _get_connector_classes()
    return _REGISTRY


def get_connector_class(name: str):
    """
    Get a connector class by name.
    Returns None if not found.
    """
    return get_registry().get(name.lower())


def list_connectors() -> list[dict]:
    """
    List all available connectors with their metadata.
    Used by broker_computer_use_status tool.
    """
    result = []
    for name, cls in get_registry().items():
        try:
            instance = cls()
            result.append({
                "name": name,
                "class": cls.__name__,
                "description": getattr(cls, "description", ""),
                "requires_display": getattr(cls, "requires_display", False),
            })
        except Exception as e:
            result.append({"name": name, "class": cls.__name__, "error": str(e)})
    return result


def create_connector(name: str, **kwargs) -> "BaseConnector | None":
    """
    Instantiate a connector by name.

    Example:
        conn = create_connector("cedam", headless=True)
        await conn.setup()
        result = await conn.check_rca("B123ABC")
        await conn.teardown()
    """
    cls = get_connector_class(name)
    if cls is None:
        return None
    return cls(**kwargs)
