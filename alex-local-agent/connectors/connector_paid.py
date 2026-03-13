"""
PAIDConnector — Verificare și interogare polițe PAD (Pool-ul de Asigurare Împotriva Dezastrelor).

PAD = Polița de Asigurare Împotriva Dezastrelor Naturale (obligatorie pentru locuințe în RO).
Portal: https://www.paid.ro

Capabilități:
- Verifică dacă o proprietate are PAD valid (după adresă sau serie buletin)
- Extrage data expirării, suma asigurată, asigurătorul
- Interogare situație portofoliu broker (necesită credențiale)

Documentație: https://www.paid.ro/agenti-brokeri
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from typing import Optional

from .connector_web_generic import GenericWebConnector


PAID_URLS = [
    "https://www.paid.ro/verificare-polita",
    "https://www.paid.ro/verificare",
    "https://www.paid.ro",
]

PAID_BROKER_URL = "https://www.paid.ro/login"

# Selectori câmp de căutare pe paid.ro
ADDRESS_SELECTORS = [
    'input[name*="adresa"]',
    'input[name*="address"]',
    'input[placeholder*="adresă"]',
    'input[placeholder*="adresa"]',
    '#adresa',
    '#address',
    'input[type="text"]:visible',
]

CNPJ_SELECTORS = [
    'input[name*="cnp"]',
    'input[name*="serie"]',
    'input[placeholder*="CNP"]',
    'input[placeholder*="buletin"]',
    '#cnp',
]

SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'button:has-text("Verifică")',
    'button:has-text("Caută")',
    'button:has-text("Verifica")',
    '.btn-primary',
    'input[type="submit"]',
]

KNOWN_PAID_INSURERS = [
    "Allianz-Tiriac", "Generali", "Omniasig", "Asirom", "Groupama",
    "Uniqa", "Grawe", "Signal Iduna", "Gothaer", "BCR Asigurări",
    "Euroins", "Certasig",
]


class PAIDConnector(GenericWebConnector):
    """
    Conector pentru portalul PAID România (www.paid.ro).

    Verificare polițe PAD (obligatorii pentru locuințe).
    Suportă:
    - Verificare polița după adresă proprietate
    - Verificare după seria/numărul poliței
    - Login broker pentru acces portofoliu (cu credențiale)

    Exemplu utilizare:
        connector = PAIDConnector()
        await connector.setup()
        result = await connector.check_pad(address="Str. Victoriei 10, București")
        # → {"valid": True, "expiry": "2025-12-01", "insurer": "Allianz-Tiriac", ...}
    """

    name = "paid"
    description = "Verificare polițe PAD (asigurare dezastre naturale) via paid.ro"
    requires_display = False

    PAID_URL = "https://www.paid.ro"
    BROKER_LOGIN_URL = "https://www.paid.ro/login"
    VERIFY_URL = "https://www.paid.ro/verificare-polita"

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, browser_type="chromium")
        self._logged_in = False

    # ── Core interface ──────────────────────────────────────────────────────

    async def login(self, credentials: dict) -> dict:
        """
        Login broker pe portalul PAID.
        credentials: {"username": "...", "password": "..."}
        Nu e necesar pentru verificări publice.
        """
        if not credentials.get("username"):
            return {"success": True, "message": "PAID public verification — no login needed"}

        try:
            nav = await self.navigate(self.BROKER_LOGIN_URL)
            if not nav["success"]:
                return {"success": False, "error": "Nu s-a putut accesa pagina de login PAID"}

            await asyncio.sleep(2)

            # Fill username
            for sel in ['input[name="username"]', 'input[type="email"]', '#username', '#email']:
                try:
                    el = self._page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.fill(credentials["username"])
                        break
                except Exception:
                    pass

            # Fill password
            for sel in ['input[name="password"]', 'input[type="password"]', '#password']:
                try:
                    el = self._page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.fill(credentials["password"])
                        break
                except Exception:
                    pass

            # Submit
            submitted = await self._submit_form()
            if not submitted:
                await self._page.evaluate("document.querySelector('form').submit()")

            await asyncio.sleep(3)
            page_text = await self._page.inner_text("body", timeout=5000)

            if any(x in page_text.lower() for x in ["panou", "dashboard", "portofoliu", "deconectare"]):
                self._logged_in = True
                return {"success": True, "message": "Login PAID reușit"}
            else:
                return {"success": False, "error": "Login PAID eșuat — verificați credențialele"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Extrage date PAD.
        params: {"address": "...", "policy_number": "...", "cnp": "..."}
        """
        params = params or {}
        policy_number = params.get("policy_number") or _extract_policy_number(query)
        address = params.get("address") or params.get("adresa")
        cnp = params.get("cnp")

        if policy_number:
            return await self.check_pad_by_policy(policy_number)
        elif address:
            return await self.check_pad(address=address)
        elif cnp:
            return await self.check_pad(cnp=cnp)
        else:
            return {
                "success": False,
                "error": "Specificați 'address', 'policy_number' sau 'cnp' în params.",
            }

    # ── PAID-specific methods ───────────────────────────────────────────────

    async def check_pad(self, address: Optional[str] = None, cnp: Optional[str] = None) -> dict:
        """
        Verifică dacă o proprietate/persoană are PAD valid.
        Prioritate: policy_number > address > cnp
        """
        self._ensure_ready()

        for url in PAID_URLS:
            result = await self._try_check_pad_at(url, address=address, cnp=cnp)
            if result.get("success"):
                return result

        screenshot_b64 = await self._take_screenshot_b64()
        return {
            "success": False,
            "error": "Nu s-a putut accesa portalul PAID pentru verificare",
            "screenshot_b64": screenshot_b64,
        }

    async def check_pad_by_policy(self, policy_number: str) -> dict:
        """Verifică o poliță PAD după numărul de poliță."""
        self._ensure_ready()

        for url in PAID_URLS:
            result = await self._try_check_pad_at(url, policy_number=policy_number)
            if result.get("success"):
                result["policy_number_searched"] = policy_number
                return result

        return {
            "success": False,
            "error": f"Nu s-a putut verifica polița PAD {policy_number}",
        }

    async def _try_check_pad_at(
        self,
        base_url: str,
        address: Optional[str] = None,
        cnp: Optional[str] = None,
        policy_number: Optional[str] = None,
    ) -> dict:
        """Încearcă verificarea pe un URL specific."""
        try:
            nav = await self.navigate(base_url)
            if not nav["success"]:
                return {"success": False, "error": f"Nu s-a putut accesa {base_url}"}

            await asyncio.sleep(2)
            await self._dismiss_cookies()

            # Fill policy number if provided
            if policy_number:
                for sel in ['input[name*="polita"]', 'input[name*="policy"]',
                            'input[placeholder*="poliță"]', 'input[placeholder*="polita"]',
                            'input[type="text"]:visible']:
                    try:
                        el = self._page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.fill(policy_number)
                            break
                    except Exception:
                        pass

            # Fill address
            elif address:
                for sel in ADDRESS_SELECTORS:
                    try:
                        el = self._page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.fill(address)
                            break
                    except Exception:
                        pass

            # Fill CNP
            elif cnp:
                for sel in CNPJ_SELECTORS:
                    try:
                        el = self._page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.fill(cnp)
                            break
                    except Exception:
                        pass
            else:
                return {"success": False, "error": "Niciun criteriu de căutare furnizat"}

            submitted = await self._submit_form()
            if not submitted:
                await self._page.keyboard.press("Enter")

            await asyncio.sleep(3)
            await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
            return await self._parse_paid_results(address or policy_number or cnp or "")

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _dismiss_cookies(self):
        """Închide banner-ul de cookies."""
        for sel in [
            'button:has-text("Accept")', 'button:has-text("Acceptă")',
            '#acceptCookies', '.cookie-accept', 'button:has-text("OK")',
        ]:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                continue

    async def _submit_form(self) -> bool:
        for sel in SUBMIT_SELECTORS:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    return True
            except Exception:
                continue
        return False

    async def _parse_paid_results(self, search_term: str) -> dict:
        """Parsează rezultatele căutării PAD."""
        try:
            page_text = await self._page.inner_text("body", timeout=10000)
        except Exception as e:
            return {"success": False, "error": f"Nu s-a putut citi pagina: {e}"}

        page_lower = page_text.lower()

        # Check for no results
        if any(p in page_lower for p in ["nu există", "nu a fost găsit", "not found", "inexistentă", "nu s-a găsit"]):
            return {
                "success": True,
                "data_found": False,
                "pad_valid": False,
                "message": f"Nu există poliță PAD activă pentru '{search_term}'",
            }

        # Extract dates
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
                        days_until_expiry = (d - today).days
                        expiry_date_str = d.isoformat()
                        break
                except ValueError:
                    continue
            if expiry_date_str:
                break

        # Extract insurer
        found_insurer = next(
            (ins for ins in KNOWN_PAID_INSURERS if ins.lower() in page_lower), None
        )

        # Extract policy number (PAD format: PAD-XXXXXX or similar)
        policy_numbers = re.findall(r"PAD[\s\-]?[A-Z0-9]{6,12}", page_text, re.IGNORECASE)

        # Extract insured sum (PAD standard: 20,000 EUR zone A/B, 10,000 EUR zone C)
        insured_sum = None
        sum_match = re.search(r"(\d[\d.,]+)\s*EUR", page_text, re.IGNORECASE)
        if sum_match:
            insured_sum = f"{sum_match.group(1)} EUR"

        # Zone (A/B/C — risk zones for PAD)
        zone = None
        zone_match = re.search(r"\bZona\s+([ABC])\b", page_text, re.IGNORECASE)
        if zone_match:
            zone = f"Zona {zone_match.group(1).upper()}"

        # Valid indicators
        pad_valid = None
        if any(p in page_lower for p in ["valabilă", "activă", "valid", "în vigoare"]):
            pad_valid = True
        elif any(p in page_lower for p in ["expirată", "expirat", "invalida", "inactivă"]):
            pad_valid = False

        return {
            "success": True,
            "data_found": True,
            "pad_valid": pad_valid if pad_valid is not None else True,
            "policy_number": policy_numbers[0] if policy_numbers else None,
            "insurer": found_insurer,
            "insured_sum": insured_sum,
            "zone": zone,
            "expiry_date": expiry_date_str,
            "days_until_expiry": days_until_expiry,
            "raw_text": page_text[:2000],
        }

    async def _take_screenshot_b64(self) -> Optional[str]:
        import base64
        try:
            if self._page:
                png_bytes = await self._page.screenshot(full_page=False)
                return base64.b64encode(png_bytes).decode("utf-8")
        except Exception:
            pass
        return None

    async def get_portfolio_summary(self) -> dict:
        """
        Extrage sumar portofoliu broker (necesită login anterior).
        Returnează: număr polițe active, total prime, distribuție zone.
        """
        if not self._logged_in:
            return {"success": False, "error": "Nu ești autentificat. Apelează login() mai întâi."}

        try:
            nav = await self.navigate(f"{self.PAID_URL}/portofoliu")
            if not nav["success"]:
                return {"success": False, "error": "Nu s-a putut accesa portofoliul"}

            await asyncio.sleep(2)
            page_text = await self._page.inner_text("body", timeout=10000)

            # Extract counts and sums
            counts = re.findall(r"(\d+)\s+(?:polițe?|asigurări?)", page_text, re.IGNORECASE)
            total = int(counts[0]) if counts else None

            return {
                "success": True,
                "total_policies": total,
                "raw_text": page_text[:3000],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Utilities ───────────────────────────────────────────────────────────────

def _extract_policy_number(query: str) -> Optional[str]:
    """Extrage numărul de poliță PAD dintr-un query natural."""
    match = re.search(r"PAD[\s\-]?([A-Z0-9]{6,12})", query, re.IGNORECASE)
    if match:
        return f"PAD-{match.group(1).upper()}"
    return None
