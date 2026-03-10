"""Base connector interface — every connector must implement this."""
from abc import ABC, abstractmethod
from typing import Any, Optional
import base64
import io


class BaseConnector(ABC):
    """
    Abstract base class for all Alex computer-use connectors.

    A connector wraps a specific software (web portal, desktop app, etc.)
    and exposes a uniform interface so the local agent can use them
    interchangeably.

    To add support for a new software, create a new file:
        connectors/connector_<name>.py
    and subclass BaseConnector.
    """

    # ── Identity ───────────────────────────────────────────────────────────
    name: str = ""          # e.g. "cedam", "allianz_portal"
    description: str = ""   # human-readable, shown in status
    requires_display: bool = False  # True for desktop apps (need DISPLAY env)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def setup(self) -> None:
        """Called once when the connector is first instantiated.
        Override to launch browser, open app, etc."""
        pass

    async def teardown(self) -> None:
        """Called on shutdown / task completion. Override to close browser, etc."""
        pass

    # ── Core interface ─────────────────────────────────────────────────────

    @abstractmethod
    async def login(self, credentials: dict) -> dict:
        """
        Authenticate with the target software.

        Args:
            credentials: dict with keys relevant to the connector
                         e.g. {"username": "...", "password": "..."}

        Returns:
            {"success": True} or {"success": False, "error": "..."}
        """

    @abstractmethod
    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Extract data from the target software.

        Args:
            query: natural-language description of what to extract
                   e.g. "RCA validity for plate B123ABC"
                   e.g. "all policies expiring in March"
            params: optional structured params (plate number, date range, etc.)

        Returns:
            {"success": True, "data": {...}} or {"success": False, "error": "..."}
        """

    @abstractmethod
    async def fill_form(self, fields: dict) -> dict:
        """
        Fill a form in the target software.

        Args:
            fields: dict mapping field names/labels to values
                    e.g. {"plate_number": "B123ABC", "id_number": "1234567890"}

        Returns:
            {"success": True} or {"success": False, "error": "..."}
        """

    @abstractmethod
    async def screenshot(self) -> Optional[bytes]:
        """
        Capture current state of the software.

        Returns:
            PNG bytes or None if screenshot not available
        """

    # ── Optional helpers ───────────────────────────────────────────────────

    async def navigate(self, target: str) -> dict:
        """Navigate to a URL or screen/section within the software."""
        return {"success": False, "error": f"{self.name} does not implement navigate()"}

    async def click(self, target: str) -> dict:
        """Click an element identified by label/description."""
        return {"success": False, "error": f"{self.name} does not implement click()"}

    async def type_text(self, field: str, text: str) -> dict:
        """Type text into a field identified by label/description."""
        return {"success": False, "error": f"{self.name} does not implement type_text()"}

    async def wait_for(self, condition: str, timeout: int = 30) -> dict:
        """Wait for a condition to be true on screen."""
        return {"success": False, "error": f"{self.name} does not implement wait_for()"}

    # ── Utility ────────────────────────────────────────────────────────────

    def screenshot_to_base64(self, png_bytes: bytes) -> str:
        """Convert PNG bytes to base64 string for JSON transport."""
        return base64.b64encode(png_bytes).decode("utf-8")

    def base64_to_screenshot(self, b64: str) -> bytes:
        """Convert base64 string back to PNG bytes."""
        return base64.b64decode(b64)

    async def get_status(self) -> dict:
        """Return connector health/status information."""
        return {
            "connector": self.name,
            "description": self.description,
            "requires_display": self.requires_display,
        }
