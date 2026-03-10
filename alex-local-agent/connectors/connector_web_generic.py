"""
GenericWebConnector — Playwright-based connector for ANY website.

Works without a specific connector when the broker needs to:
- Open a URL in the browser
- Extract text/tables from any page
- Fill forms on any website
- Take screenshots

For specific portals (CEDAM, Allianz, etc.) use dedicated connectors
that inherit from this class or BaseConnector directly.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from .base import BaseConnector

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class GenericWebConnector(BaseConnector):
    name = "web_generic"
    description = "Controls any website via Playwright browser automation"
    requires_display = False  # runs headless by default

    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        self.headless = headless
        self.browser_type = browser_type
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def setup(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        self._playwright = await async_playwright().start()
        browser_launcher = getattr(self._playwright, self.browser_type)
        self._browser = await browser_launcher.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()

    async def teardown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def _ensure_ready(self):
        if not self._page:
            raise RuntimeError("Connector not set up. Call setup() first.")

    # ── Core interface ─────────────────────────────────────────────────────

    async def login(self, credentials: dict) -> dict:
        """
        Generic login — looks for common username/password patterns.
        For site-specific login flows, override in a subclass.

        credentials: {
            "url": "https://...",          # page with login form (optional if already there)
            "username": "...",
            "password": "...",
            "username_selector": "input[name='username']",  # optional CSS selector
            "password_selector": "input[name='password']",  # optional CSS selector
            "submit_selector": "button[type='submit']",     # optional
        }
        """
        self._ensure_ready()
        try:
            if "url" in credentials:
                await self._page.goto(credentials["url"], wait_until="domcontentloaded", timeout=30000)

            # Try common selectors
            user_sel = credentials.get("username_selector") or 'input[type="text"], input[name*="user"], input[name*="email"], input[id*="user"], input[id*="email"]'
            pass_sel = credentials.get("password_selector") or 'input[type="password"]'
            submit_sel = credentials.get("submit_selector") or 'button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign in")'

            await self._page.fill(user_sel, credentials.get("username", ""), timeout=10000)
            await self._page.fill(pass_sel, credentials.get("password", ""), timeout=10000)
            await self._page.click(submit_sel, timeout=10000)
            await self._page.wait_for_load_state("domcontentloaded", timeout=15000)

            return {"success": True, "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Extract data from the current page using Gemini Vision + DOM parsing.

        query: natural language description of what to extract
               e.g. "all rows in the policies table"
               e.g. "the policy number and expiry date"

        params:
            url: navigate here first (optional)
            selector: CSS selector to focus on (optional)
            extract_type: "text" | "table" | "screenshot_only" (default: "text")
        """
        self._ensure_ready()
        params = params or {}
        try:
            if "url" in params:
                await self._page.goto(params["url"], wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1)

            extract_type = params.get("extract_type", "text")

            if extract_type == "screenshot_only":
                png = await self._page.screenshot(full_page=False)
                return {
                    "success": True,
                    "type": "screenshot",
                    "screenshot_b64": self.screenshot_to_base64(png),
                    "url": self._page.url,
                }

            # Try DOM-based extraction first
            if "selector" in params:
                try:
                    text = await self._page.inner_text(params["selector"], timeout=5000)
                    return {"success": True, "type": "dom_text", "data": text, "query": query}
                except Exception:
                    pass

            if extract_type == "table":
                tables = await self._page.evaluate("""() => {
                    const tables = document.querySelectorAll('table');
                    return Array.from(tables).map(table => {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        return rows.map(row => {
                            const cells = Array.from(row.querySelectorAll('th, td'));
                            return cells.map(cell => cell.innerText.trim());
                        });
                    });
                }""")
                return {
                    "success": True,
                    "type": "tables",
                    "data": tables,
                    "count": len(tables),
                    "query": query,
                }

            # Full page text extraction
            text = await self._page.inner_text("body", timeout=10000)
            # Truncate very long pages
            if len(text) > 8000:
                text = text[:8000] + "\n\n[... page truncated for length ...]"
            return {
                "success": True,
                "type": "page_text",
                "data": text,
                "url": self._page.url,
                "query": query,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fill_form(self, fields: dict) -> dict:
        """
        Fill a form on the current page.

        fields: {
            "field_label_or_selector": "value",
            ...
            "_submit": True   # optional — click submit after filling
        }
        """
        self._ensure_ready()
        filled = []
        errors = []

        for field_key, value in fields.items():
            if field_key.startswith("_"):
                continue  # skip meta keys like _submit
            try:
                # Try as CSS selector first, then by label/placeholder text
                try:
                    await self._page.fill(field_key, str(value), timeout=5000)
                    filled.append(field_key)
                except Exception:
                    # Try finding by label text
                    el = self._page.get_by_label(field_key)
                    await el.fill(str(value), timeout=5000)
                    filled.append(field_key)
            except Exception as e:
                errors.append(f"{field_key}: {e}")

        if fields.get("_submit"):
            try:
                submit_sel = fields.get("_submit_selector", 'button[type="submit"], input[type="submit"]')
                await self._page.click(submit_sel, timeout=10000)
                await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception as e:
                errors.append(f"submit: {e}")

        return {
            "success": len(errors) == 0,
            "filled": filled,
            "errors": errors,
        }

    async def screenshot(self) -> Optional[bytes]:
        if not self._page:
            return None
        try:
            return await self._page.screenshot(full_page=False)
        except Exception:
            return None

    # ── Extra browser helpers ──────────────────────────────────────────────

    async def navigate(self, target: str) -> dict:
        self._ensure_ready()
        try:
            await self._page.goto(target, wait_until="domcontentloaded", timeout=30000)
            return {"success": True, "url": self._page.url, "title": await self._page.title()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, target: str) -> dict:
        """Click by CSS selector, text, or ARIA label."""
        self._ensure_ready()
        try:
            # Try as CSS selector
            try:
                await self._page.click(target, timeout=5000)
                return {"success": True}
            except Exception:
                pass
            # Try by text
            await self._page.get_by_text(target, exact=False).first.click(timeout=5000)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, field: str, text: str) -> dict:
        """Type into field by CSS selector or label."""
        self._ensure_ready()
        try:
            try:
                await self._page.fill(field, text, timeout=5000)
            except Exception:
                await self._page.get_by_label(field).fill(text, timeout=5000)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for(self, condition: str, timeout: int = 30) -> dict:
        """Wait for a CSS selector or text to appear."""
        self._ensure_ready()
        try:
            try:
                await self._page.wait_for_selector(condition, timeout=timeout * 1000)
                return {"success": True}
            except Exception:
                await self._page.wait_for_function(
                    f"document.body.innerText.includes('{condition}')",
                    timeout=timeout * 1000,
                )
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""

    async def get_page_title(self) -> str:
        if self._page:
            return await self._page.title()
        return ""
