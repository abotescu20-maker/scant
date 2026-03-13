"""
AllianzConnector — Automatizare portal Allianz-Tiriac România.

Portal broker: https://broker.allianz-tiriac.ro
Portal public:  https://www.allianz-tiriac.ro

Capabilități:
- Login broker pe portalul Allianz-Tiriac
- Interogare portofoliu polițe (RCA, CASCO, PAD, LIFE)
- Extrage date poliță după număr poliță sau client
- Generare ofertă preliminară (dacă portalul suportă)
- Rapoarte comisioane broker

Documentație partener: https://broker.allianz-tiriac.ro/docs
"""
from __future__ import annotations

import asyncio
import base64
import re
from datetime import date, datetime
from typing import Optional

from .connector_web_generic import GenericWebConnector


# URL-uri portal Allianz România
ALLIANZ_RO_BROKER_URL = "https://broker.allianz-tiriac.ro"
ALLIANZ_RO_PUBLIC_URL = "https://www.allianz-tiriac.ro"
ALLIANZ_RO_LOGIN_URL  = "https://broker.allianz-tiriac.ro/login"

# Portal Allianz DE (pentru clienți germani)
ALLIANZ_DE_BROKER_URL = "https://makler.allianz.de"
ALLIANZ_DE_LOGIN_URL  = "https://makler.allianz.de/login"

# Selectori login
LOGIN_SELECTORS = {
    "username": [
        'input[name="username"]', 'input[type="email"]',
        '#username', '#email', 'input[name="email"]',
        'input[placeholder*="utilizator"]', 'input[placeholder*="user"]',
    ],
    "password": [
        'input[name="password"]', 'input[type="password"]',
        '#password', 'input[placeholder*="parolă"]',
    ],
    "submit": [
        'button[type="submit"]', 'button:has-text("Autentificare")',
        'button:has-text("Login")', 'button:has-text("Intră")',
        'input[type="submit"]', '.btn-login', '.btn-primary',
    ],
}

# Selectori căutare poliță
POLICY_SEARCH_SELECTORS = [
    'input[name*="policy"]', 'input[name*="polita"]', 'input[name*="numar"]',
    'input[placeholder*="poliță"]', 'input[placeholder*="polita"]',
    'input[placeholder*="număr"]', '#policyNumber', '#nrPolita',
    'input[type="text"]:visible',
]

KNOWN_POLICY_TYPES = ["RCA", "CASCO", "PAD", "LIFE", "CMR", "TRAVEL", "PROPERTY"]


class AllianzConnector(GenericWebConnector):
    """
    Conector pentru portalul broker Allianz-Tiriac România.

    Suportă atât portalul RO (broker.allianz-tiriac.ro) cât și DE (makler.allianz.de).

    Exemplu utilizare:
        connector = AllianzConnector(country="RO")
        await connector.setup()
        result = await connector.login({"username": "broker@firma.ro", "password": "..."})
        portfolio = await connector.get_portfolio()
        policy = await connector.get_policy_details("ALZ-CASCO-2025-001")
    """

    name = "allianz"
    description = "Portal broker Allianz-Tiriac RO și Allianz DE — polițe, portofoliu, oferte"
    requires_display = False

    def __init__(self, headless: bool = True, country: str = "RO"):
        super().__init__(headless=headless, browser_type="chromium")
        self._logged_in = False
        self.country = country.upper()
        if self.country == "DE":
            self._broker_url = ALLIANZ_DE_BROKER_URL
            self._login_url = ALLIANZ_DE_LOGIN_URL
        else:
            self._broker_url = ALLIANZ_RO_BROKER_URL
            self._login_url = ALLIANZ_RO_LOGIN_URL

    # ── Core interface ──────────────────────────────────────────────────────

    async def login(self, credentials: dict) -> dict:
        """
        Autentificare pe portalul broker Allianz.
        credentials: {"username": "...", "password": "..."}
        """
        if not credentials.get("username") or not credentials.get("password"):
            return {"success": False, "error": "Credențiale lipsă (username + password necesare)"}

        self._ensure_ready()

        try:
            nav = await self.navigate(self._login_url)
            if not nav["success"]:
                return {"success": False, "error": f"Nu s-a putut accesa {self._login_url}"}

            await asyncio.sleep(2)
            await self._dismiss_cookies()

            # Fill username
            username_filled = False
            for sel in LOGIN_SELECTORS["username"]:
                try:
                    el = self._page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.fill(credentials["username"])
                        username_filled = True
                        break
                except Exception:
                    pass

            if not username_filled:
                return {"success": False, "error": "Câmpul username nu a fost găsit pe pagina de login"}

            # Fill password
            for sel in LOGIN_SELECTORS["password"]:
                try:
                    el = self._page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.fill(credentials["password"])
                        break
                except Exception:
                    pass

            # Submit
            submitted = False
            for sel in LOGIN_SELECTORS["submit"]:
                try:
                    btn = self._page.locator(sel).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        submitted = True
                        break
                except Exception:
                    pass

            if not submitted:
                await self._page.evaluate("document.querySelector('form').submit()")

            await asyncio.sleep(4)
            page_text = await self._page.inner_text("body", timeout=10000)
            page_lower = page_text.lower()

            # Check login success indicators
            success_indicators = ["dashboard", "panou", "portofoliu", "deconectare", "logout", "welcome"]
            error_indicators = ["invalid", "incorect", "eroare", "error", "incorrect"]

            if any(x in page_lower for x in success_indicators):
                self._logged_in = True
                current_url = self._page.url
                return {
                    "success": True,
                    "message": f"Login Allianz reușit ({self.country})",
                    "current_url": current_url,
                }
            elif any(x in page_lower for x in error_indicators):
                return {"success": False, "error": "Login eșuat — credențiale incorecte"}
            else:
                # Ambiguous — take screenshot
                screenshot_b64 = await self._take_screenshot_b64()
                return {
                    "success": False,
                    "error": "Login rezultat neclar — verificați credențialele",
                    "screenshot_b64": screenshot_b64,
                    "page_text_preview": page_text[:500],
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Extrage date din portalul Allianz.
        params: {"policy_number": "...", "client_name": "...", "action": "portfolio|policy|offer"}
        """
        params = params or {}
        action = params.get("action", "policy")

        if action == "portfolio":
            return await self.get_portfolio()
        elif action == "commissions":
            return await self.get_commissions()

        policy_number = params.get("policy_number") or _extract_allianz_policy(query)
        if policy_number:
            return await self.get_policy_details(policy_number)

        client_name = params.get("client_name") or params.get("client")
        if client_name:
            return await self.search_client_policies(client_name)

        return {
            "success": False,
            "error": "Specificați 'policy_number', 'client_name' sau 'action' în params.",
        }

    # ── Allianz-specific methods ────────────────────────────────────────────

    async def get_portfolio(self) -> dict:
        """
        Extrage lista polițelor din portofoliu broker.
        Necesită login anterior.
        """
        if not self._logged_in:
            return {"success": False, "error": "Nu ești autentificat. Apelează login() mai întâi."}

        try:
            portfolio_urls = [
                f"{self._broker_url}/portofoliu",
                f"{self._broker_url}/portfolio",
                f"{self._broker_url}/polite",
                f"{self._broker_url}/policies",
                f"{self._broker_url}/dashboard",
            ]

            for url in portfolio_urls:
                nav = await self.navigate(url)
                if nav["success"]:
                    await asyncio.sleep(2)
                    page_text = await self._page.inner_text("body", timeout=10000)
                    if len(page_text) > 200:  # has actual content
                        return await self._parse_portfolio(page_text)

            return {"success": False, "error": "Nu s-a putut accesa portofoliul"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_policy_details(self, policy_number: str) -> dict:
        """
        Extrage detaliile unei polițe după numărul de poliță.
        Încearcă mai întâi cu login, apoi verificare publică.
        """
        self._ensure_ready()

        try:
            # Try broker portal first
            search_urls = [
                f"{self._broker_url}/polite/{policy_number}",
                f"{self._broker_url}/search?q={policy_number}",
                ALLIANZ_RO_PUBLIC_URL + "/verificare-polita",
            ]

            for url in search_urls:
                nav = await self.navigate(url)
                if not nav["success"]:
                    continue

                await asyncio.sleep(2)
                page_text = await self._page.inner_text("body", timeout=10000)

                if policy_number.lower() in page_text.lower():
                    return await self._parse_policy_details(page_text, policy_number)

            # Try search form if direct URL failed
            return await self._search_policy_via_form(policy_number)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _search_policy_via_form(self, policy_number: str) -> dict:
        """Caută polița prin formularul de pe portal."""
        try:
            await self.navigate(self._broker_url)
            await asyncio.sleep(2)

            for sel in POLICY_SEARCH_SELECTORS:
                try:
                    el = self._page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.fill(policy_number)
                        await el.press("Enter")
                        await asyncio.sleep(3)
                        page_text = await self._page.inner_text("body", timeout=10000)
                        if policy_number.lower() in page_text.lower():
                            return await self._parse_policy_details(page_text, policy_number)
                        break
                except Exception:
                    pass

            screenshot_b64 = await self._take_screenshot_b64()
            return {
                "success": False,
                "error": f"Polița {policy_number} nu a fost găsită pe portalul Allianz",
                "screenshot_b64": screenshot_b64,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_client_policies(self, client_name: str) -> dict:
        """Caută polițele unui client după nume."""
        if not self._logged_in:
            return {"success": False, "error": "Nu ești autentificat. Apelează login() mai întâi."}

        try:
            search_url = f"{self._broker_url}/search?client={client_name.replace(' ', '+')}"
            nav = await self.navigate(search_url)
            if not nav["success"]:
                return {"success": False, "error": "Nu s-a putut efectua căutarea"}

            await asyncio.sleep(2)
            page_text = await self._page.inner_text("body", timeout=10000)
            return await self._parse_portfolio(page_text, client_filter=client_name)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_commissions(self) -> dict:
        """Extrage raportul de comisioane broker (lunar)."""
        if not self._logged_in:
            return {"success": False, "error": "Nu ești autentificat. Apelează login() mai întâi."}

        try:
            commission_urls = [
                f"{self._broker_url}/comisioane",
                f"{self._broker_url}/commissions",
                f"{self._broker_url}/rapoarte",
                f"{self._broker_url}/reports",
            ]

            for url in commission_urls:
                nav = await self.navigate(url)
                if nav["success"]:
                    await asyncio.sleep(2)
                    page_text = await self._page.inner_text("body", timeout=10000)
                    if any(x in page_text.lower() for x in ["comision", "commission", "%"]):
                        # Extract commission data
                        amounts = re.findall(r"(\d[\d.,]+)\s*(RON|EUR|lei)", page_text, re.IGNORECASE)
                        percentages = re.findall(r"(\d+(?:\.\d+)?)\s*%", page_text)
                        return {
                            "success": True,
                            "data_found": True,
                            "amounts_found": amounts[:10],
                            "percentages_found": percentages[:10],
                            "raw_text": page_text[:3000],
                        }

            return {"success": False, "error": "Pagina de comisioane nu a fost găsită"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Parsing helpers ─────────────────────────────────────────────────────

    async def _parse_policy_details(self, page_text: str, policy_number: str) -> dict:
        """Extrage detalii poliță din textul paginii."""
        page_lower = page_text.lower()

        # Dates
        dates_found = re.findall(r"\b(\d{2}[.\-/]\d{2}[.\-/]\d{4})\b", page_text)
        dates_found += re.findall(r"\b(\d{4}[.\-/]\d{2}[.\-/]\d{2})\b", page_text)

        today = date.today()
        expiry_date_str = None
        days_until_expiry = None
        for date_str in dates_found:
            for fmt in ["%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    d = datetime.strptime(date_str, fmt).date()
                    if d >= today:
                        expiry_date_str = d.isoformat()
                        days_until_expiry = (d - today).days
                        break
                except ValueError:
                    continue
            if expiry_date_str:
                break

        # Policy type
        policy_type = next((pt for pt in KNOWN_POLICY_TYPES if pt.lower() in page_lower), None)

        # Premium amount
        premium = None
        premium_match = re.search(r"(\d[\d.,]+)\s*(RON|EUR|ron|eur)", page_text)
        if premium_match:
            premium = f"{premium_match.group(1)} {premium_match.group(2).upper()}"

        # Status
        status = None
        if any(x in page_lower for x in ["activă", "active", "valabilă", "în vigoare"]):
            status = "active"
        elif any(x in page_lower for x in ["expirată", "expired", "anulată", "cancelled"]):
            status = "expired"

        return {
            "success": True,
            "data_found": True,
            "policy_number": policy_number,
            "policy_type": policy_type,
            "status": status,
            "premium": premium,
            "expiry_date": expiry_date_str,
            "days_until_expiry": days_until_expiry,
            "raw_text": page_text[:3000],
        }

    async def _parse_portfolio(self, page_text: str, client_filter: Optional[str] = None) -> dict:
        """Extrage lista polițelor din pagina de portofoliu."""
        page_lower = page_text.lower()

        # Count policies mentioned
        policy_refs = re.findall(r"[A-Z]{2,4}[\s\-]\d{6,12}", page_text)
        allianz_refs = re.findall(r"ALZ[\s\-][A-Z0-9\-]+", page_text, re.IGNORECASE)

        # Extract total premium
        amounts = re.findall(r"(\d[\d.,]+)\s*(RON|EUR)", page_text)

        return {
            "success": True,
            "data_found": len(policy_refs) > 0,
            "policy_count": len(set(policy_refs)),
            "policy_references": list(set(policy_refs))[:20],
            "allianz_references": list(set(allianz_refs))[:20],
            "amounts_found": amounts[:10],
            "raw_text": page_text[:4000],
        }

    async def _dismiss_cookies(self):
        for sel in [
            'button:has-text("Accept all")', 'button:has-text("Acceptă")',
            'button:has-text("Accept")', '#onetrust-accept-btn-handler',
            '.cookie-consent-accept', 'button:has-text("OK")',
        ]:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                continue

    async def _take_screenshot_b64(self) -> Optional[str]:
        try:
            if self._page:
                png_bytes = await self._page.screenshot(full_page=False)
                return base64.b64encode(png_bytes).decode("utf-8")
        except Exception:
            pass
        return None


# ── Utilities ────────────────────────────────────────────────────────────────

def _extract_allianz_policy(query: str) -> Optional[str]:
    """Extrage numărul de poliță Allianz dintr-un query."""
    match = re.search(r"ALZ[\s\-][A-Z0-9\-]+", query, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    # Generic policy number pattern
    match = re.search(r"\b[A-Z]{2,4}[\s\-]\d{6,12}\b", query)
    if match:
        return match.group(0)
    return None
