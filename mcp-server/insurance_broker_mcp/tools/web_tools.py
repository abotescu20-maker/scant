"""
Web automation tools — Playwright headless running directly on Cloud Run.

No local agent needed. These tools run in the same process as Alex,
using a headless Chromium browser bundled with Playwright.

Available tools:
- check_rca_fn(plate)          — verificare RCA pe portalul ASF
- browse_web_fn(url, query)    — extrage text/date de pe orice URL public
"""
from __future__ import annotations

import asyncio
import base64
import re
from datetime import date, datetime
from typing import Optional


# ── Playwright availability check ─────────────────────────────────────────

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ── RCA result cache (in-memory, TTL 6h) ──────────────────────────────────
# Avoids re-scraping AIDA/CEDAM for the same plate within the same session.
# Key: normalized plate string. Value: {result: dict, cached_at: datetime}

_rca_cache: dict = {}
_RCA_CACHE_TTL_HOURS = 6


def _cache_get(plate: str) -> dict | None:
    entry = _rca_cache.get(plate)
    if entry is None:
        return None
    age_hours = (datetime.utcnow() - entry["cached_at"]).total_seconds() / 3600
    if age_hours > _RCA_CACHE_TTL_HOURS:
        del _rca_cache[plate]
        return None
    result = dict(entry["result"])
    result["from_cache"] = True
    result["cached_at"] = entry["cached_at"].isoformat()
    return result


def _cache_set(plate: str, result: dict) -> None:
    _rca_cache[plate] = {"result": result, "cached_at": datetime.utcnow()}


# ── Shared browser pool (one browser per process lifetime) ─────────────────
# Cloud Run has one process → we reuse one browser instance across requests.
# Guarded by an asyncio lock to prevent concurrent setup races.
#
# BUG FIX: --single-process was causing the browser to crash after the first
# context.close(). Removed it — Chromium handles multi-process fine in headless.
# Also added _is_browser_alive() check since is_connected() alone is unreliable.

_browser_instance = None
_pw_instance = None
_browser_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    global _browser_lock
    if _browser_lock is None:
        _browser_lock = asyncio.Lock()
    return _browser_lock


async def _is_browser_alive(browser) -> bool:
    """Check if the browser is truly usable, not just 'connected'."""
    if browser is None:
        return False
    try:
        if not browser.is_connected():
            return False
        # Try creating a context to verify the browser is actually alive
        ctx = await browser.new_context()
        await ctx.close()
        return True
    except Exception:
        return False


async def _get_browser():
    """Return (or create) the shared headless Chromium browser."""
    import os
    global _browser_instance, _pw_instance
    async with _get_lock():
        if not await _is_browser_alive(_browser_instance):
            # Clean up old instance if exists
            if _browser_instance is not None:
                try:
                    await _browser_instance.close()
                except Exception:
                    pass
            if _pw_instance is not None:
                try:
                    await _pw_instance.stop()
                except Exception:
                    pass

            _pw_instance = await async_playwright().start()
            launch_kwargs = dict(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ],
            )
            # On Cloud Run we use the system Chromium installed via apt
            chromium_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            if chromium_path and os.path.exists(chromium_path):
                launch_kwargs["executable_path"] = chromium_path
            _browser_instance = await _pw_instance.chromium.launch(**launch_kwargs)
    return _browser_instance


async def _new_page(browser=None):
    """Open a new browser tab with a realistic user-agent."""
    if browser is None:
        browser = await _get_browser()
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    return page, context


# ── RCA Check ──────────────────────────────────────────────────────────────

# Known Romanian plate patterns
_PLATE_RE = re.compile(
    r"\b([A-Z]{1,2}\s?\d{2,3}\s?[A-Z]{3})\b",
    re.IGNORECASE,
)

_PLATE_SELECTORS = [
    '#nr_inmatriculare',
    'input[name*="plate"]',
    'input[name*="nrInmatriculare"]',
    'input[name*="numar"]',
    'input[placeholder*="nmatriculare"]',
    'input[placeholder*="număr"]',
    'input[id*="plate"]',
    'input[id*="nrInmatriculare"]',
    '#plate_number',
    'input[type="text"]',
]

_SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Verifică")',
    'button:has-text("Caută")',
    'button:has-text("Search")',
    '.btn-search',
    '#btn_search',
]

_KNOWN_INSURERS = [
    "Allianz", "Generali", "Omniasig", "Euroins", "Grawe",
    "City Insurance", "Asirom", "Uniqa", "Groupama", "NN",
    "Gothaer", "Signal Iduna", "Astra", "BCR Asigurări",
]

_RCA_URLS = [
    "https://www.aida.info.ro/polite-rca",        # BAAR/AIDA — portalul oficial curent
    "https://www.cedam.info/verificare-rca",       # fallback 1
    "https://www.baar.auto.ro/verificare-rca",     # fallback 2 — BAAR alternativ (no CAPTCHA)
]

_COVERAGE_KEYWORDS = ["RCA", "CASCO", "CMR", "PAD", "Carte Verde", "Green Card"]

# AIDA-specific selectors (portalul BAAR — aida.info.ro)
_AIDA_PLATE_SELECTORS = [
    'input[name="registrationNumber"]',
    'input[id="registrationNumber"]',
    'input[placeholder*="nmatriculare"]',
    'input[placeholder*="egistration"]',
    '#registrationNumber',
]

_AIDA_PRIVACY_SELECTORS = [
    'input[type="checkbox"]',
    'input[name*="privacy"]',
    'input[name*="gdpr"]',
    'input[name*="terms"]',
    'input[id*="privacy"]',
    'input[id*="gdpr"]',
    'input[id*="terms"]',
    'input[id*="agree"]',
]


def _normalize_plate(plate: str) -> str:
    return re.sub(r"\s+", "", plate.upper().strip())


def _parse_rca_page(page_text: str, plate: str) -> dict:
    """Extract RCA data from raw page text."""
    page_lower = page_text.lower()

    # No-result indicators
    for pattern in ["nu există", "nu a fost găsit", "no results", "not found",
                     "nu s-a găsit", "inexistentă"]:
        if pattern in page_lower:
            return {
                "success": True,
                "data_found": False,
                "rca_valid": False,
                "plate": plate,
                "captcha_blocked": False,
                "from_cache": False,
                "message": f"Nu există poliță RCA activă pentru {plate}",
            }

    # Extract dates
    dates_found = re.findall(r"\b(\d{2}[.\-/]\d{2}[.\-/]\d{4})\b", page_text)
    dates_found += re.findall(r"\b(\d{4}[.\-/]\d{2}[.\-/]\d{2})\b", page_text)

    # Extract policy numbers
    policy_numbers = re.findall(r"[A-Z]{2,4}[\s\-]?\d{6,12}", page_text)
    policy_numbers += re.findall(r"RCA[\s\-]?\d{8,12}", page_text)

    # Detect insurer
    found_insurer = next(
        (ins for ins in _KNOWN_INSURERS if ins.lower() in page_lower), None
    )

    # Detect coverage type
    found_coverage = next(
        (cov for cov in _COVERAGE_KEYWORDS if cov.lower() in page_lower), "RCA"
    )

    # Extract insured sum (e.g. "1.000.000 EUR" or "5.000.000 RON")
    insured_sum = None
    sum_match = re.search(
        r"(\d[\d.,]+)\s*(EUR|RON|lei|ron|eur)", page_text, re.IGNORECASE
    )
    if sum_match:
        insured_sum = f"{sum_match.group(1)} {sum_match.group(2).upper()}"

    # Detect validity
    rca_valid = None
    for p in ["valabilă", "activă", "valid", "active", "în vigoare"]:
        if p in page_lower:
            rca_valid = True
            break
    if rca_valid is None:
        for p in ["expirată", "expired", "expirat", "invalida", "inactivă"]:
            if p in page_lower:
                rca_valid = False
                break

    # Parse expiry date
    expiry_date_str = None
    days_until_expiry = None
    today = date.today()
    for date_str in dates_found:
        for fmt in ["%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y.%m.%d"]:
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

    return {
        "success": True,
        "data_found": True,
        "rca_valid": rca_valid if rca_valid is not None else True,
        "plate": plate,
        "policy_number": policy_numbers[0] if policy_numbers else None,
        "insurer": found_insurer,
        "coverage_type": found_coverage,
        "insured_sum": insured_sum,
        "expiry_date": expiry_date_str,
        "days_until_expiry": days_until_expiry,
        "captcha_blocked": False,
        "from_cache": False,
        "cached_at": None,
        "all_dates_found": dates_found[:5],
        "raw_text": page_text[:2000],
    }


async def _check_rca_aida(page, plate: str) -> dict | None:
    """Try AIDA portal (aida.info.ro/polite-rca).

    The form requires:
    1. Select "Numar de inmatriculare" radio button
    2. Fill in the plate number
    3. Check the GDPR/privacy checkbox
    4. Solve reCAPTCHA v2 (Google)
    5. Submit via POST to /politerca/cautare

    Note: reCAPTCHA cannot be solved headlessly. If the portal has CAPTCHA,
    we return a structured error so Alex can inform the user.
    """
    try:
        await page.goto("https://www.aida.info.ro/polite-rca", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

        # Dismiss cookie banners
        for sel in ['button:has-text("Accept")', 'button:has-text("Acceptă")',
                    'button:has-text("De acord")', '#acceptCookies', '.cookie-accept',
                    'button:has-text("OK")', '.accept-cookies']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                pass

        # Step 1: Select "Numar de inmatriculare" radio button
        try:
            radio = page.locator('#numar')
            if await radio.is_visible(timeout=2000):
                await radio.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # Step 2: Fill plate number (field id=SerieNumar)
        plate_filled = False
        for sel in ['#SerieNumar'] + _AIDA_PLATE_SELECTORS + _PLATE_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1000):
                    await el.fill("")
                    await el.fill(plate)
                    plate_filled = True
                    await asyncio.sleep(0.3)
                    break
            except Exception:
                pass

        if not plate_filled:
            return None  # can't find form

        # Step 3: Check GDPR checkbox (id=EsteDeAcordCuConditiile)
        for sel in ['#EsteDeAcordCuConditiile'] + _AIDA_PRIVACY_SELECTORS:
            try:
                cb = page.locator(sel).first
                if await cb.is_visible(timeout=1000):
                    is_checked = await cb.is_checked()
                    if not is_checked:
                        await cb.click()
                        await asyncio.sleep(0.3)
                    break
            except Exception:
                pass

        # Step 4: Check for reCAPTCHA
        has_captcha = False
        try:
            captcha_iframe = page.locator('iframe[src*="recaptcha"]').first
            if await captcha_iframe.is_visible(timeout=2000):
                has_captcha = True
        except Exception:
            pass

        if has_captcha:
            # Cannot solve reCAPTCHA headlessly — return structured error
            # Caller (_check_rca_async) will try BAAR fallback next
            return {
                "success": True,
                "data_found": False,
                "rca_valid": None,
                "plate": plate,
                "captcha_blocked": True,
                "from_cache": False,
                "cached_at": None,
                "coverage_type": None,
                "insured_sum": None,
                "message": (
                    f"Portalul AIDA necesită reCAPTCHA. Încerc portalul alternativ BAAR..."
                ),
                "source_url": "https://www.aida.info.ro/polite-rca",
                "manual_url": "https://www.aida.info.ro/polite-rca",
            }

        # Step 5: Submit form (if no CAPTCHA — try Cauta button/link)
        submitted = False
        for sel in _SUBMIT_SELECTORS + ['a:has-text("Cauta")', 'div:has-text("Cauta") >> button',
                                         '.btn-primary', 'input[value="Cauta"]']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    submitted = True
                    break
            except Exception:
                pass

        if not submitted:
            # Try submitting the form directly via JS
            await page.evaluate("document.querySelector('form').submit()")

        await asyncio.sleep(4)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)

        page_text = await page.inner_text("body", timeout=10000)
        result = _parse_rca_page(page_text, plate)
        result["source_url"] = "https://www.aida.info.ro/polite-rca"
        return result

    except Exception as e:
        return {"success": False, "error": str(e), "source_url": "https://www.aida.info.ro/polite-rca"}


async def _check_rca_async(plate_raw: str) -> dict:
    """Internal async implementation of RCA check.

    Flow:
    1. Check in-memory cache (TTL 6h) — return immediately if hit
    2. Try AIDA portal (primary)
       a. If reCAPTCHA detected → try BAAR fallback (no CAPTCHA)
    3. Try remaining fallback URLs generically
    4. On total failure → return error with screenshot_b64 for debugging
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright not installed on this server."}

    plate = _normalize_plate(plate_raw)

    # 1. Cache hit?
    cached = _cache_get(plate)
    if cached:
        return cached

    page, context = await _new_page()

    async def _take_screenshot_b64() -> str | None:
        try:
            png_bytes = await page.screenshot(full_page=False)
            return base64.b64encode(png_bytes).decode("utf-8")
        except Exception:
            return None

    try:
        # 2. Try AIDA first (primary portal)
        aida_result = await _check_rca_aida(page, plate)

        if aida_result and aida_result.get("success"):
            # If CAPTCHA blocked, try BAAR as automatic fallback
            if aida_result.get("captcha_blocked"):
                baar_result = await _check_rca_generic(
                    page, plate, "https://www.baar.auto.ro/verificare-rca"
                )
                if baar_result and baar_result.get("data_found"):
                    _cache_set(plate, baar_result)
                    return baar_result
                # BAAR also failed — return AIDA captcha error with updated message
                aida_result["message"] = (
                    f"Portalul AIDA necesită reCAPTCHA și portalul BAAR nu a răspuns. "
                    f"Verificați manual: https://www.aida.info.ro/polite-rca "
                    f"sau folosiți agentul local cu connector=cedam."
                )
                aida_result["screenshot_b64"] = await _take_screenshot_b64()
                return aida_result
            # AIDA success — cache and return
            _cache_set(plate, aida_result)
            return aida_result

        # 3. Fallback: generic approach for remaining URLs
        for url in _RCA_URLS[1:]:
            result = await _check_rca_generic(page, plate, url)
            if result and result.get("data_found"):
                _cache_set(plate, result)
                return result

        # 4. All portals failed — capture screenshot for debugging
        screenshot_b64 = await _take_screenshot_b64()
        return {
            "success": False,
            "plate": plate,
            "captcha_blocked": False,
            "from_cache": False,
            "screenshot_b64": screenshot_b64,
            "error": (
                "Nu s-a putut accesa niciun portal de verificare RCA. "
                "Încearcați din nou sau folosiți agentul local cu connector=cedam."
            ),
        }
    finally:
        await context.close()


async def _check_rca_generic(page, plate: str, url: str) -> dict | None:
    """Generic RCA check for any URL that has a standard plate input form."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

        # Dismiss cookie banners
        for sel in ['button:has-text("Accept")', 'button:has-text("Acceptă")',
                    '#acceptCookies', '.cookie-accept']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                pass

        # Find plate input
        plate_selector = None
        for sel in _PLATE_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    plate_selector = sel
                    break
            except Exception:
                pass

        if not plate_selector:
            return None

        await page.fill(plate_selector, plate)
        await asyncio.sleep(0.3)

        # Submit
        submitted = False
        for sel in _SUBMIT_SELECTORS:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    submitted = True
                    break
            except Exception:
                pass
        if not submitted:
            await page.press(plate_selector, "Enter")

        await asyncio.sleep(3)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)

        page_text = await page.inner_text("body", timeout=10000)
        result = _parse_rca_page(page_text, plate)
        result["source_url"] = url
        if result.get("data_found") or "nu există" in page_text.lower():
            return result
        return None
    except Exception:
        return None


def check_rca_fn(plate: str) -> str:
    """
    Verifică RCA pentru un număr de înmatriculare pe portalul ASF/CEDAM.
    Returnează JSON cu: valid, dată expirare, asigurător, număr poliță.
    """
    import json
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context (Chainlit) — use asyncio.create_task pattern
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _check_rca_async(plate))
                result = future.result(timeout=60)
        else:
            result = loop.run_until_complete(_check_rca_async(plate))
    except Exception as e:
        result = {"success": False, "error": str(e)}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Generic web browse ─────────────────────────────────────────────────────

async def _browse_web_async(url: str, query: str, extract_type: str = "text") -> dict:
    """Internal async web browsing."""
    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright not installed on this server."}

    page, context = await _new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(1)

        if extract_type == "table":
            tables = await page.evaluate("""() => {
                const tables = document.querySelectorAll('table');
                return Array.from(tables).map(table => {
                    const rows = Array.from(table.querySelectorAll('tr'));
                    return rows.map(row => {
                        const cells = Array.from(row.querySelectorAll('th, td'));
                        return cells.map(cell => cell.innerText.trim());
                    });
                });
            }""")
            return {"success": True, "url": page.url, "type": "tables",
                    "data": tables, "query": query}

        # Default: full page text
        text = await page.inner_text("body", timeout=10000)
        if len(text) > 6000:
            text = text[:6000] + "\n\n[... pagina a fost trunchiată ...]"

        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "type": "page_text",
            "data": text,
            "query": query,
        }
    except Exception as e:
        return {"success": False, "url": url, "error": str(e)}
    finally:
        await context.close()


def browse_web_fn(url: str, query: str = "", extract_type: str = "text") -> str:
    """
    Accesează un URL public și extrage conținutul text sau tabelele.
    Util pentru verificări pe site-uri externe, prețuri, știri, etc.

    Args:
        url: URL-ul de accesat
        query: ce anume căutăm (pentru context, nu filtrează)
        extract_type: "text" (default) sau "table"
    """
    import json
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _browse_web_async(url, query, extract_type))
                result = future.result(timeout=45)
        else:
            result = loop.run_until_complete(_browse_web_async(url, query, extract_type))
    except Exception as e:
        result = {"success": False, "error": str(e)}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── pint.ro RCA price comparator ──────────────────────────────────────────────
#
# pint.ro (agregator) returnează prețuri reale de la asigurătorii parteneri
# pe baza numărului de înmatriculare. Nu cere CNP sau serie șasiu obligatoriu.
# Datele sunt furnizate de asigurători prin API-ul agregatorul pint.ro.
# Sursa: https://pint.ro/calculator-asigurare-rca
#
# Cache TTL: 2h (prețurile nu se schimbă frecvent în aceeași zi)

_price_cache: dict = {}
_PRICE_CACHE_TTL_HOURS = 2


def _price_cache_get(plate: str) -> dict | None:
    entry = _price_cache.get(plate.upper().replace(" ", ""))
    if entry is None:
        return None
    age_hours = (datetime.utcnow() - entry["cached_at"]).total_seconds() / 3600
    if age_hours > _PRICE_CACHE_TTL_HOURS:
        del _price_cache[plate.upper().replace(" ", "")]
        return None
    return dict(entry["result"])


def _price_cache_set(plate: str, result: dict) -> None:
    _price_cache[plate.upper().replace(" ", "")] = {
        "result": result,
        "cached_at": datetime.utcnow(),
    }


async def _scrape_pint_rca_async(plate: str) -> dict:
    """
    Scrape pint.ro pentru prețuri RCA reale pe baza numărului de înmatriculare.
    Parcurge formularul în 3 pași: vehicul → detalii client (minimal) → oferte.
    Returnează lista de oferte cu asigurător + preț anual + preț lunar.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright nu este disponibil pe acest server."}

    plate_norm = plate.upper().replace(" ", "").replace("-", "")
    page, context = await _new_page()
    try:
        # ── Pasul 1: Detalii autovehicul ──────────────────────────────────────
        await page.goto("https://pint.ro/calculator-asigurare-rca", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2500)

        # Dismiss cookie banner via JS (CybotCookiebotDialogBodyButton)
        await page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = b.textContent.trim();
                    if (t === 'Accepta' || t === 'Accept' || t === 'OK' || b.id.includes('Cookie')) {
                        b.click(); return 'clicked ' + t;
                    }
                }
            }
        """)
        await page.wait_for_timeout(1000)

        # Completează numărul de înmatriculare via JS (bypass overlay issues)
        await page.evaluate(f"""
            () => {{
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {{
                    const ph = (inp.placeholder || '').toLowerCase();
                    if (ph.includes('pozitia a') || ph.includes('nmatriculare')) {{
                        inp.value = '{plate_norm}';
                        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return 'filled';
                    }}
                }}
            }}
        """)
        await page.wait_for_timeout(500)

        # Completat automat — auto-fill date vehicul după numărul de înmatriculare
        try:
            auto_btn = page.locator("text=Completati automat").first
            if await auto_btn.is_visible(timeout=2000):
                await auto_btn.click()
                await page.wait_for_timeout(5000)  # așteptăm API call DRPCIV
        except Exception:
            pass

        # Apasă "Înainte" via JS
        await page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, a');
                for (const b of btns) {
                    if (b.textContent.includes('nainte')) { b.click(); return 'clicked Inainte'; }
                }
            }
        """)
        await page.wait_for_timeout(3000)

        # ── Pasul 2: Detalii client (minim obligatoriu) ────────────────────────
        await page.wait_for_timeout(2000)

        # Data nașterii dacă e cerută
        try:
            dob_input = page.locator('input[type="date"], input[placeholder*="data"], input[name*="dataNastere"]').first
            if await dob_input.is_visible(timeout=1500):
                await dob_input.fill("1985-06-15")
                await page.wait_for_timeout(300)
        except Exception:
            pass

        # Apasă "Înainte" din nou via JS
        await page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, a');
                for (const b of btns) {
                    if (b.textContent.includes('nainte')) { b.click(); return 'clicked Inainte 2'; }
                }
            }
        """)
        await page.wait_for_timeout(5000)  # așteptăm ofertele să se încarce

        # ── Pasul 3: Oferte ────────────────────────────────────────────────────
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        # Extrage ofertele — pint.ro afișează carduri cu asigurător + preț
        page_text = await page.inner_text("body", timeout=10000)
        page_url = page.url

        # Parse oferte din text
        offers = _parse_pint_offers(page_text)

        if not offers:
            # Fallback: returnează text brut pentru debugging
            return {
                "success": False,
                "plate": plate_norm,
                "error": "Nu s-au putut extrage ofertele. Site-ul poate fi blocat sau a schimbat structura.",
                "page_url": page_url,
                "raw_snippet": page_text[:1500],
            }

        return {
            "success": True,
            "source": "pint.ro",
            "plate": plate_norm,
            "offers": offers,
            "offer_count": len(offers),
        }

    except Exception as e:
        return {"success": False, "plate": plate_norm, "error": str(e)}
    finally:
        await context.close()


def _parse_pint_offers(text: str) -> list[dict]:
    """
    Parsează ofertele din textul paginii pint.ro.
    pint.ro afișează: Asigurător | Preț anual | Preț lunar
    """
    offers = []
    known_insurers = [
        "Allianz", "Generali", "Omniasig", "Groupama", "Uniqa",
        "Asirom", "Euroins", "Grawe", "Signal Iduna", "Gothaer",
        "Certasig", "BCR", "Axeria",
    ]

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        insurer_found = None
        for ins in known_insurers:
            if ins.lower() in line.lower():
                insurer_found = ins
                break

        if insurer_found:
            # Caută prețul în liniile următoare (max 6 linii)
            # Prima valoare RON mare = preț anual, a doua mai mică (< annual/6) = preț lunar
            price_annual = None
            price_monthly = None
            for j in range(i + 1, min(i + 7, len(lines))):
                # Stop dacă am dat de alt asigurător
                if any(ins.lower() in lines[j].lower() for ins in known_insurers if ins != insurer_found):
                    break
                price_match = re.search(r"([\d\s,.]+)\s*(RON|lei|ron)", lines[j], re.IGNORECASE)
                if price_match:
                    raw = price_match.group(1).replace(" ", "").replace(".", "").replace(",", "")
                    try:
                        val = int(raw)
                        if price_annual is None and 300 <= val <= 20000:
                            price_annual = val
                        elif price_annual is not None and price_monthly is None:
                            # Lunar trebuie să fie mult mai mic decât anual (max 1/6 din anual)
                            if 50 <= val <= price_annual // 6 * 2:
                                price_monthly = val
                    except ValueError:
                        pass

            if price_annual:
                offers.append({
                    "insurer": insurer_found,
                    "annual_ron": price_annual,
                    "monthly_ron": price_monthly or round(price_annual / 12),
                })
        i += 1

    # Deduplică și sortează
    seen = set()
    unique = []
    for o in offers:
        if o["insurer"] not in seen:
            seen.add(o["insurer"])
            unique.append(o)
    unique.sort(key=lambda x: x["annual_ron"])
    return unique


def scrape_rca_prices_fn(plate: str) -> str:
    """
    Obține prețuri RCA reale de la asigurători via pint.ro (agregator).
    Input: numărul de înmatriculare al vehiculului (ex: B123ABC).
    Returnează tabel comparativ cu prețuri reale, sortat cel mai ieftin primul.
    Cache TTL: 2 ore (prețurile sunt stabile în aceeași zi).
    """
    import json

    plate = plate.upper().strip()

    # Check cache
    cached = _price_cache_get(plate)
    if cached:
        cached["from_cache"] = True
        return _format_pint_result(cached)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _scrape_pint_rca_async(plate))
                result = future.result(timeout=60)
        else:
            result = loop.run_until_complete(_scrape_pint_rca_async(plate))
    except Exception as e:
        result = {"success": False, "error": str(e)}

    if result.get("success"):
        _price_cache_set(plate, result)

    return _format_pint_result(result)


def _format_pint_result(result: dict) -> str:
    """Formatează rezultatul scraping-ului pint.ro ca tabel markdown."""
    if not result.get("success"):
        error = result.get("error", "Eroare necunoscută")
        plate = result.get("plate", "")
        snippet = result.get("raw_snippet", "")
        msg = (
            f"❌ **Prețuri live indisponibile** pentru `{plate}`\n\n"
            f"Motiv: {error}\n\n"
            f"💡 Folosește `broker_compare_premiums_live` pentru tarife orientative 2024-2025 "
            f"(nu necesită număr de înmatriculare)."
        )
        if snippet:
            msg += f"\n\n*Debug snippet:* ```\n{snippet[:500]}\n```"
        return msg

    offers = result.get("offers", [])
    plate = result.get("plate", "")
    from_cache = result.get("from_cache", False)
    cache_note = " *(din cache)*" if from_cache else ""

    if not offers:
        return (
            f"❌ Nu s-au găsit oferte pentru `{plate}` pe pint.ro.\n\n"
            f"💡 Folosește `broker_compare_premiums_live` pentru tarife orientative."
        )

    lines = [
        f"## 🔴 Prețuri RCA LIVE — `{plate}`{cache_note}\n",
        f"> Sursa: **pint.ro** (agregator) — prețuri reale de la asigurători.\n",
        f"| # | Asigurător | Preț anual | Preț lunar |",
        f"|---|---|---|---|",
    ]
    min_price = offers[0]["annual_ron"]
    for i, o in enumerate(offers, 1):
        marker = " ✅" if i == 1 else ""
        diff = o["annual_ron"] - min_price
        diff_str = "" if diff == 0 else f" (+{diff:,} RON)"
        lines.append(
            f"| {i} | **{o['insurer']}**{marker} | **{o['annual_ron']:,} RON**{diff_str} | {o['monthly_ron']:,} RON/lună |"
        )

    best = offers[0]
    lines.append(
        f"\n### 💡 Cel mai bun preț\n"
        f"**{best['insurer']}** — **{best['annual_ron']:,} RON/an** ({best['monthly_ron']:,} RON/lună)\n"
    )
    lines.append(
        f"*Prețuri furnizate de asigurători via pint.ro. "
        f"Prețul final poate varia în funcție de istoricul șoferului și condițiile poliței.*"
    )
    return "\n".join(lines)
