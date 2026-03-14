"""
CEDAMConnector — Verificare RCA în timp real via portalul CEDAM.

CEDAM (Centrul pentru Evidența și Datele Asigurărilor din Motorsport)
oferă verificarea valabilității polițelor RCA pentru orice vehicul înmatriculat în România.

Portal: https://www.cedam.info  (sau portalul ASF al asigurărilor auto)
Alternativă ASF: https://asfromania.ro/apps/polite-rca

Această implementare folosește Playwright pentru a controla browser-ul
și a extrage datele direct din interfața web, fără API oficial.
"""
from __future__ import annotations

import asyncio
import base64
import re
from datetime import date, datetime
from typing import Optional

from .connector_web_generic import GenericWebConnector


# URL-uri cunoscute pentru verificare RCA în România (ordine prioritate)
CEDAM_URLS = [
    "https://www.aida.info.ro/polite-rca",        # BAAR/AIDA — portalul oficial curent (browser vizibil poate ocoli CAPTCHA)
    "https://www.cedam.info/verificare-rca",       # fallback 1
    "https://www.baar.auto.ro/verificare-rca",     # fallback 2
    "https://asfromania.ro/apps/polite-rca",       # fallback 3
]

# Selectori comuni pe portalurile de verificare RCA
PLATE_SELECTORS = [
    'input[name*="plate"]',
    'input[name*="nrInmatriculare"]',
    'input[name*="numar"]',
    'input[placeholder*="nmatriculare"]',
    'input[placeholder*="număr"]',
    'input[id*="plate"]',
    'input[id*="nrInmatriculare"]',
    '#nr_inmatriculare',
    '#plate_number',
]

SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Verifică")',
    'button:has-text("Caută")',
    'button:has-text("Cauta")',
    'button:has-text("Search")',
    '.btn-search',
    '#btn_search',
    '.btn-primary',
    'input[value="Cauta"]',
]

# AIDA-specific selectors (aida.info.ro/polite-rca)
AIDA_PLATE_SELECTORS = [
    '#SerieNumar',
    'input[name="registrationNumber"]',
    'input[id="registrationNumber"]',
    'input[placeholder*="nmatriculare"]',
    'input[placeholder*="egistration"]',
]

AIDA_PRIVACY_SELECTORS = [
    '#EsteDeAcordCuConditiile',
    'input[type="checkbox"]',
    'input[name*="privacy"]',
    'input[name*="gdpr"]',
    'input[name*="agree"]',
]

KNOWN_INSURERS = [
    "Allianz", "Generali", "Omniasig", "Euroins", "Grawe",
    "City Insurance", "Asirom", "Uniqa", "Groupama", "NN",
    "Gothaer", "Signal Iduna", "Astra", "BCR Asigurări",
]

COVERAGE_KEYWORDS = ["RCA", "CASCO", "CMR", "PAD", "Carte Verde", "Green Card"]


class CEDAMConnector(GenericWebConnector):
    """
    Verificare RCA în timp real prin portalul CEDAM / ASF.

    Capabilități:
    - Verifică dacă un vehicul are RCA valid
    - Extrage data de expirare a polițeiRCA
    - Extrage asigurătorul și numărul poliței
    - Verifică dacă polița este activă sau expirată

    Exemplu de utilizare:
        connector = CEDAMConnector()
        await connector.setup()
        result = await connector.check_rca("B123ABC")
        # → {"valid": True, "expiry": "2025-06-15", "insurer": "Allianz", "policy_number": "..."}
    """

    name = "cedam"
    description = "Verificare RCA în timp real via portal CEDAM / ASF România"
    requires_display = False  # headless Playwright

    CEDAM_URL = "https://www.cedam.info"
    ASF_RCA_URL = "https://asfromania.ro/apps/polite-rca"

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, browser_type="chromium")
        self._logged_in = False
        self._working_url = None

    # ── Core interface override ────────────────────────────────────────────

    async def login(self, credentials: dict) -> dict:
        """
        CEDAM/ASF nu necesită autentificare pentru verificări publice.
        Dacă portalul privat al unui asigurător necesită login,
        credentials poate conține: {url, username, password}
        """
        if credentials:
            return await super().login(credentials)
        # Public portal — no login needed
        return {"success": True, "message": "CEDAM public portal — no login required"}

    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Extrage date RCA. Acceptă:
        - query: "RCA pentru B123ABC" sau "verificare nr înmatriculare B 123 ABC"
        - params: {"plate": "B123ABC"} sau {"plate": "B 123 ABC"}
        """
        params = params or {}
        plate = params.get("plate") or _extract_plate_from_query(query)
        if not plate:
            return {
                "success": False,
                "error": "Numărul de înmatriculare nu a fost identificat. Specificați 'plate' în params.",
            }
        return await self.check_rca(plate)

    # ── CEDAM-specific methods ─────────────────────────────────────────────

    async def check_rca(self, plate_number: str) -> dict:
        """
        Verifică valabilitatea RCA pentru un număr de înmatriculare.

        Încearcă AIDA, apoi CEDAM, BAAR, ASF.
        Dacă CAPTCHA e detectat în modul headless, returnează captcha_detected=True
        — TaskExecutor poate retry automat cu headless=False (browser vizibil).

        Returns dict cu: plate, rca_valid, policy_number, insurer, coverage_type,
                          insured_sum, expiry_date, days_until_expiry, screenshot_b64
        """
        plate = _normalize_plate(plate_number)
        self._ensure_ready()

        # Try AIDA first with special form handling
        result = await self._try_check_rca_aida(plate)
        if result.get("success") and result.get("data_found"):
            result["plate"] = plate
            return result

        # If CAPTCHA detected on AIDA, return immediately so executor can retry visible
        if result.get("captcha_detected"):
            result["plate"] = plate
            return result

        # Fallback: try remaining URLs generically
        for url in CEDAM_URLS[1:]:
            result = await self._try_check_rca_at(url, plate)
            if result.get("success") and result.get("data_found"):
                result["plate"] = plate
                return result
            # Stop on CAPTCHA here too
            if result.get("captcha_detected"):
                result["plate"] = plate
                return result

        # All failed — capture screenshot for debugging
        screenshot_b64 = await self._take_screenshot_b64()
        return {
            "success": False,
            "plate": plate,
            "error": "Nu s-a putut accesa niciun portal de verificare RCA",
            "screenshot_b64": screenshot_b64,
        }

    async def _take_screenshot_b64(self) -> str | None:
        """Capturează screenshot și returnează ca base64."""
        try:
            if self._page:
                png_bytes = await self._page.screenshot(full_page=False)
                return base64.b64encode(png_bytes).decode("utf-8")
        except Exception:
            pass
        return None

    # _detect_captcha removed — use _has_recaptcha() for iframe-based detection

    async def _has_recaptcha(self) -> bool:
        """Detectează reCAPTCHA v2 prin prezența iframe-ului Google."""
        try:
            frames = self._page.frames
            for frame in frames:
                if "google.com/recaptcha" in frame.url or "recaptcha" in frame.url:
                    return True
            # Also check DOM for recaptcha div
            el = await self._page.query_selector('[data-site-key], .g-recaptcha, iframe[src*="recaptcha"]')
            return el is not None
        except Exception:
            return False

    async def _recaptcha_solved(self) -> bool:
        """Returnează True dacă utilizatorul a rezolvat reCAPTCHA (textarea completată)."""
        try:
            val = await self._page.evaluate(
                "() => { const t = document.getElementById('g-recaptcha-response'); "
                "return t ? t.value : ''; }"
            )
            return bool(val and len(val) > 10)
        except Exception:
            return False

    async def _wait_for_captcha_solution(self, timeout_s: int = 90) -> bool:
        """
        Așteaptă ca utilizatorul să rezolve reCAPTCHA (browser vizibil).
        Returnează True dacă rezolvat, False la timeout.
        """
        import time
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if await self._recaptcha_solved():
                return True
            await asyncio.sleep(1)
        return False

    async def _try_check_rca_aida(self, plate: str) -> dict:
        """Verificare specifică pentru portalul AIDA (aida.info.ro)."""
        try:
            nav = await self.navigate("https://www.aida.info.ro/polite-rca")
            if not nav["success"]:
                return {"success": False, "error": "Nu s-a putut accesa AIDA"}
            await asyncio.sleep(2)
            await self._dismiss_cookies()

            # Detectează reCAPTCHA prin iframe (nu din text)
            has_captcha = await self._has_recaptcha()
            if has_captcha:
                if self.headless:
                    # Modul headless: nu putem rezolva CAPTCHA → semnalăm pentru retry vizibil
                    return {
                        "success": False,
                        "captcha_detected": True,
                        "error": "AIDA cere reCAPTCHA — necesită browser vizibil",
                    }
                else:
                    # Modul vizibil: completăm formularul, AȘTEPTĂM ca brokerul să rezolve CAPTCHA
                    # Selectează radio 'numar'
                    try:
                        await self._page.check('input[name="CriteriuCautare"][value="numar"]', timeout=3000)
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass

                    # Completează numărul de înmatriculare
                    plate_filled = False
                    for sel in ['#SerieNumar', 'input[name="SerieNumar"]'] + PLATE_SELECTORS:
                        try:
                            el = self._page.locator(sel).first
                            if await el.is_visible(timeout=1000):
                                await el.fill(plate)
                                plate_filled = True
                                break
                        except Exception:
                            pass

                    if not plate_filled:
                        return {"success": False, "error": "Câmpul de înmatriculare nu a fost găsit"}

                    # Bifează GDPR
                    try:
                        cb = self._page.locator('#EsteDeAcordCuConditiile').first
                        if not await cb.is_checked(timeout=2000):
                            await cb.click()
                    except Exception:
                        pass

                    # Browserul e vizibil — așteptăm ca brokerul să rezolve CAPTCHA (max 90s)
                    solved = await self._wait_for_captcha_solution(timeout_s=90)
                    if not solved:
                        screenshot_b64 = await self._take_screenshot_b64()
                        return {
                            "success": False,
                            "captcha_detected": True,
                            "error": "Timeout așteptând rezolvarea CAPTCHA (90s). Completează CAPTCHA și trimite din nou.",
                            "screenshot_b64": screenshot_b64,
                        }

                    # Apasă butonul Cauta (span, nu button)
                    try:
                        await self._page.click('span.btn-cauta-polita', timeout=5000)
                    except Exception:
                        try:
                            await self._page.evaluate("document.querySelector('span.btn-cauta-polita').click()")
                        except Exception:
                            pass

                    await asyncio.sleep(4)
                    await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
                    return await self._parse_rca_results(plate)

            # Nu e CAPTCHA — completează formularul normal
            # Selectează radio 'numar'
            try:
                await self._page.check('input[name="CriteriuCautare"][value="numar"]', timeout=3000)
                await asyncio.sleep(0.3)
            except Exception:
                pass

            # Completează numărul de înmatriculare
            plate_filled = False
            for sel in ['#SerieNumar', 'input[name="SerieNumar"]'] + PLATE_SELECTORS:
                try:
                    el = self._page.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        await el.fill(plate)
                        plate_filled = True
                        break
                except Exception:
                    pass

            if not plate_filled:
                return {"success": False, "error": "Câmpul de înmatriculare nu a fost găsit pe AIDA"}

            # Bifează GDPR
            try:
                cb = self._page.locator('#EsteDeAcordCuConditiile').first
                if not await cb.is_checked(timeout=2000):
                    await cb.click()
            except Exception:
                pass

            # Apasă Cauta
            try:
                await self._page.click('span.btn-cauta-polita', timeout=5000)
            except Exception:
                try:
                    await self._page.evaluate("document.querySelector('span.btn-cauta-polita').click()")
                except Exception:
                    pass

            await asyncio.sleep(4)
            await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
            return await self._parse_rca_results(plate)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _try_check_rca_at(self, base_url: str, plate: str) -> dict:
        """Încearcă verificarea pe un URL specific."""
        try:
            nav_result = await self.navigate(base_url)
            if not nav_result["success"]:
                return {"success": False, "error": f"Nu s-a putut accesa {base_url}"}

            # Wait for page to be interactive
            await asyncio.sleep(2)

            # Accept cookie banner if present
            await self._dismiss_cookies()

            # Find the plate input field
            plate_input = await self._find_plate_input()
            if not plate_input:
                return {"success": False, "error": f"Câmpul pentru numărul de înmatriculare nu a fost găsit pe {base_url}"}

            # Type the plate number
            await self._page.fill(plate_input, plate)
            await asyncio.sleep(0.5)

            # Submit
            submitted = await self._submit_search()
            if not submitted:
                # Try pressing Enter instead
                await self._page.press(plate_input, "Enter")

            # Wait for results
            await asyncio.sleep(3)
            await self._page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Detectează reCAPTCHA prin iframe (nu din text)
            if await self._has_recaptcha():
                screenshot_b64 = await self._take_screenshot_b64()
                return {
                    "success": False,
                    "captcha_detected": True,
                    "error": f"Portalul {base_url} cere reCAPTCHA",
                    "screenshot_b64": screenshot_b64,
                }

            # Extract results
            return await self._parse_rca_results(plate)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _dismiss_cookies(self):
        """Închide banner-ul de cookies dacă apare."""
        cookie_selectors = [
            'button:has-text("Accept")',
            'button:has-text("Acceptă")',
            'button:has-text("OK")',
            '#acceptCookies',
            '.cookie-accept',
            '[data-testid="cookie-accept"]',
        ]
        for sel in cookie_selectors:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                continue

    async def _find_plate_input(self) -> Optional[str]:
        """Găsește selectorul CSS al câmpului pentru numărul de înmatriculare."""
        for sel in PLATE_SELECTORS:
            try:
                el = self._page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    return sel
            except Exception:
                continue
        # Fallback: find any visible text input
        try:
            inputs = await self._page.locator('input[type="text"]:visible').all()
            if inputs:
                # Get first visible input's selector
                return 'input[type="text"]:visible'
        except Exception:
            pass
        return None

    async def _submit_search(self) -> bool:
        """Apasă butonul de căutare/submit."""
        for sel in SUBMIT_SELECTORS:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    return True
            except Exception:
                continue
        return False

    async def _parse_rca_results(self, plate: str) -> dict:
        """
        Parsează rezultatele din pagina de după căutare.
        Extrage: valabilitate, dată expirare, asigurător, număr poliță.
        """
        # Get full page text AND HTML (AIDA ascunde unele date în atribute HTML)
        try:
            page_text = await self._page.inner_text("body", timeout=10000)
        except Exception as e:
            return {"success": False, "error": f"Nu s-a putut citi pagina: {e}"}

        # Try to extract additional data from HTML attributes (AIDA stochează date în data-* attrs)
        try:
            page_html = await self._page.content()
            # AIDA result rows: look for data-* attributes with policy info
            aida_rows = re.findall(
                r'data-(?:numar-polita|polita|nr-polita|policy)[^=]*=["\']([^"\']+)["\']',
                page_html, re.IGNORECASE
            )
            # Look for table cells with dates and insurer names
            td_texts = re.findall(r'<td[^>]*>\s*([^<]{3,80})\s*</td>', page_html)
            if td_texts:
                page_text = page_text + "\n" + "\n".join(td_texts)
            # Look for specific AIDA result structure
            result_divs = re.findall(
                r'coordonate[^<]*</[^>]+>\s*(?:<[^>]+>)*([^<]{5,200})', page_html, re.IGNORECASE
            )
        except Exception:
            pass

        # Check for "not found" patterns
        no_result_patterns = [
            "nu există",
            "nu a fost găsit",
            "no results",
            "not found",
            "nu s-a găsit",
            "inexistentă",
        ]
        page_lower = page_text.lower()
        for pattern in no_result_patterns:
            if pattern in page_lower:
                return {
                    "success": True,
                    "data_found": False,
                    "rca_valid": False,
                    "message": f"Nu există poliță RCA activă pentru {plate}",
                    "raw_text": page_text[:2000],
                }

        # Extract policy data using regex patterns
        extracted = {}

        # Date patterns (Romanian format: dd.mm.yyyy or yyyy-mm-dd)
        date_patterns = [
            r"\b(\d{2}[.\-/]\d{2}[.\-/]\d{4})\b",
            r"\b(\d{4}[.\-/]\d{2}[.\-/]\d{2})\b",
        ]
        dates_found = []
        for pattern in date_patterns:
            dates_found.extend(re.findall(pattern, page_text))

        # Policy number patterns
        policy_patterns = [
            r"[A-Z]{2,4}[\s\-]?\d{6,12}",
            r"RCA[\s\-]?\d{8,12}",
            r"[A-Z]{1,4}[0-9]{8,12}",
        ]
        policy_numbers = []
        for pattern in policy_patterns:
            policy_numbers.extend(re.findall(pattern, page_text))

        # Known Romanian insurers
        found_insurer = next(
            (ins for ins in KNOWN_INSURERS if ins.lower() in page_lower), None
        )

        # Coverage type
        found_coverage = next(
            (cov for cov in COVERAGE_KEYWORDS if cov.lower() in page_lower), "RCA"
        )

        # Insured sum (e.g. "1.000.000 EUR")
        insured_sum = None
        sum_match = re.search(
            r"(\d[\d.,]+)\s*(EUR|RON|lei|ron|eur)", page_text, re.IGNORECASE
        )
        if sum_match:
            insured_sum = f"{sum_match.group(1)} {sum_match.group(2).upper()}"

        # Check validity indicators
        # AIDA specific: "are o polita RCA valida" = valid, "nu are o polita RCA" = invalid
        aida_valid = "are o polita rca valida" in page_lower or "are o polita rca activa" in page_lower
        aida_invalid = (
            "nu are o polita rca" in page_lower
            or "nu exista polita" in page_lower
            or "nu s-a gasit" in page_lower
            or "nu există" in page_lower
        )

        valid_patterns = ["valabilă", "activă", "valid", "active", "în vigoare", "valida"]
        expired_patterns = ["expirată", "expired", "expirat", "invalida", "inactivă"]

        rca_valid = None
        if aida_valid:
            rca_valid = True
        elif aida_invalid:
            rca_valid = False
        else:
            for pattern in valid_patterns:
                if pattern in page_lower:
                    rca_valid = True
                    break
            if rca_valid is None:
                for pattern in expired_patterns:
                    if pattern in page_lower:
                        rca_valid = False
                        break

        # AIDA stochează data expirării ca imagine — nu poate fi extras din text
        # Datele găsite în text sunt de obicei data referinței (azi), nu data expirării
        # Marcăm expiry_date ca None și notăm că detaliile sunt în imagini
        expiry_date_str = None
        days_until_expiry = None
        today = date.today()

        # Dacă nu e AIDA sau dacă găsim date care nu sunt azi, le luăm
        for date_str in dates_found:
            for fmt in ["%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y.%m.%d"]:
                try:
                    d = datetime.strptime(date_str, fmt).date()
                    if d > today:  # Strict viitor = dată expirare reală
                        days_until_expiry = (d - today).days
                        expiry_date_str = d.isoformat()
                        break
                except ValueError:
                    continue
            if expiry_date_str:
                break

        # Note about AIDA image-based details
        details_note = None
        if aida_valid and not expiry_date_str:
            details_note = (
                "Detaliile poliței (asigurător, număr poliță, dată expirare) sunt "
                "afișate de AIDA ca imagini și nu pot fi extrase automat. "
                "Vizualizați browserul pentru detalii complete."
            )

        result = {
            "success": True,
            "data_found": True,
            "rca_valid": rca_valid if rca_valid is not None else (True if aida_valid else None),
            "policy_number": policy_numbers[0] if policy_numbers else None,
            "insurer": found_insurer,
            "coverage_type": found_coverage,
            "insured_sum": insured_sum,
            "expiry_date": expiry_date_str,
            "days_until_expiry": days_until_expiry,
            "all_dates_found": dates_found[:5],
            "raw_text": page_text[:3000],
        }
        if details_note:
            result["note"] = details_note
        return result

    async def check_multiple_plates(self, plates: list[str]) -> list[dict]:
        """
        Verifică mai multe numere de înmatriculare consecutiv.
        Returns: lista de rezultate, câte unul per placă.
        """
        results = []
        for plate in plates:
            result = await self.check_rca(plate)
            results.append(result)
            await asyncio.sleep(1)  # politicos față de server
        return results

    async def fill_form(self, fields: dict) -> dict:
        """
        Completează formularul de verificare RCA.
        fields: {"plate": "B123ABC"} sau {"nrInmatriculare": "B123ABC"}
        """
        plate = fields.get("plate") or fields.get("nrInmatriculare")
        if plate:
            return await self.extract(f"verificare {plate}", {"plate": plate})
        return await super().fill_form(fields)


# ── Utility functions ──────────────────────────────────────────────────────

def _normalize_plate(plate: str) -> str:
    """
    Normalizează numărul de înmatriculare: elimină spații, litere mici → mari.
    "b 123 abc" → "B123ABC"
    """
    return re.sub(r"\s+", "", plate.upper().strip())


def _extract_plate_from_query(query: str) -> Optional[str]:
    """
    Extrage numărul de înmatriculare din un query natural.
    "verificare RCA pentru B 123 ABC" → "B123ABC"
    """
    # Romanian plate patterns
    patterns = [
        r"\b([A-Z]{1,2}\s?\d{2,3}\s?[A-Z]{3})\b",  # B 123 ABC, B12ABC
        r"\b([A-Z]{2,3}\s?\d{2}\s?[A-Z]{3})\b",      # CJ 12 ABC
        r"\b([A-Z]{1,2}\d{3}[A-Z]{3})\b",             # B123ABC
    ]
    q = query.upper()
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return _normalize_plate(match.group(1))
    return None
