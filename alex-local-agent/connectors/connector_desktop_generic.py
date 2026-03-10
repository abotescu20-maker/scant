"""
GenericDesktopConnector — PyAutoGUI + Gemini Vision for ANY desktop application.

For Windows/Mac apps that have no web interface and no API.
Uses:
  - PIL (Pillow) to capture screenshots
  - Gemini Vision to "read" the screen and decide what to click/type
  - PyAutoGUI to control mouse and keyboard
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from typing import Optional

from .base import BaseConnector

try:
    import pyautogui
    import PIL.Image
    import PIL.ImageGrab
    import io
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GenericDesktopConnector(BaseConnector):
    name = "desktop_generic"
    description = "Controls any desktop application using PyAutoGUI + Gemini Vision"
    requires_display = True  # needs a display (not headless)

    def __init__(self, gemini_api_key: Optional[str] = None, confidence: float = 0.8, **kwargs):
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.confidence = confidence  # image matching confidence
        self._gemini_model = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def setup(self) -> None:
        # PyAutoGUI optional — run_task works without it via AppleScript/subprocess
        if PYAUTOGUI_AVAILABLE:
            pyautogui.PAUSE = 0.3
            pyautogui.FAILSAFE = True

        # Gemini optional — only needed for vision-based actions (login, click, extract)
        if GEMINI_AVAILABLE and self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self._gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self._gemini_model = None
            # run_task works via AppleScript/subprocess without Gemini

    async def teardown(self) -> None:
        self._gemini_model = None

    # ── Core interface ─────────────────────────────────────────────────────

    async def login(self, credentials: dict) -> dict:
        """
        Login to a desktop application using Gemini Vision to identify fields.

        credentials: {
            "app_name": "Soft X",           # name of the app to look for on screen
            "username": "...",
            "password": "...",
            "instructions": "..."            # optional extra context for Gemini
        }
        """
        if not self._gemini_model:
            return {"success": False, "error": "Connector not set up"}

        png = await self.screenshot()
        if not png:
            return {"success": False, "error": "Cannot capture screenshot"}

        app_name = credentials.get("app_name", "the application")
        extra = credentials.get("instructions", "")

        prompt = f"""
You are controlling a computer screen. I need to log into {app_name}.
{extra}

Look at this screenshot and find the username/email field and the password field.
Return a JSON object with this exact structure:
{{
    "username_field": {{"x": <pixel_x>, "y": <pixel_y>, "found": true/false}},
    "password_field": {{"x": <pixel_x>, "y": <pixel_y>, "found": true/false}},
    "submit_button": {{"x": <pixel_x>, "y": <pixel_y>, "found": true/false}}
}}
Only return the JSON, no other text.
"""
        try:
            result = await self._gemini_analyze(png, prompt)
            coords = json.loads(result)

            if coords["username_field"]["found"]:
                pyautogui.click(coords["username_field"]["x"], coords["username_field"]["y"])
                await asyncio.sleep(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(credentials.get("username", ""), interval=0.05)

            if coords["password_field"]["found"]:
                pyautogui.click(coords["password_field"]["x"], coords["password_field"]["y"])
                await asyncio.sleep(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(credentials.get("password", ""), interval=0.05)

            if coords["submit_button"]["found"]:
                pyautogui.click(coords["submit_button"]["x"], coords["submit_button"]["y"])
                await asyncio.sleep(2)

            return {"success": True, "coords_used": coords}

        except json.JSONDecodeError:
            return {"success": False, "error": f"Gemini returned non-JSON: {result[:200]}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Extract data from the current screen using Gemini Vision.

        query: what to extract, e.g. "the policy number shown in the top section"
        params:
            region: [x, y, width, height] to capture only a portion of screen
            wait_seconds: wait before capture (default 0)
        """
        if not self._gemini_model:
            return {"success": False, "error": "Connector not set up"}

        params = params or {}
        wait_sec = params.get("wait_seconds", 0)
        if wait_sec > 0:
            await asyncio.sleep(wait_sec)

        region = params.get("region")  # [x, y, w, h]
        png = await self.screenshot(region=region)
        if not png:
            return {"success": False, "error": "Cannot capture screenshot"}

        prompt = f"""
You are looking at a screenshot of a computer application.
Extract the following information: {query}

Return the extracted data as a JSON object. Be precise and literal.
If the information is not visible, return {{"found": false, "reason": "..."}}.
If found, return {{"found": true, "data": {{... extracted fields ...}}}}.
Only return JSON, no other text.
"""
        try:
            result = await self._gemini_analyze(png, prompt)
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # Return as raw text if not JSON
                data = {"found": True, "raw_text": result}
            return {
                "success": True,
                "query": query,
                "result": data,
                "screenshot_b64": self.screenshot_to_base64(png),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fill_form(self, fields: dict) -> dict:
        """
        Fill fields in a desktop form using Gemini Vision to locate them.

        fields: {
            "Field Label": "value to type",
            "Another Field": "another value",
            "_submit": "Submit Button Text"   # optional
        }
        """
        # If no Gemini model, build instruction from any field and delegate to run_task
        if not self._gemini_model:
            # Try common field names for instruction
            instruction = (
                fields.get("question")
                or fields.get("instruction")
                or fields.get("task")
                or fields.get("text_to_type")
                or fields.get("app_name")
                or None
            )
            # Build combined instruction from all fields
            if not instruction:
                parts = []
                app = fields.get("app_name") or fields.get("app") or ""
                text = fields.get("text_to_type") or fields.get("text") or fields.get("content") or ""
                if app:
                    parts.append(f"deschide {app}")
                if text:
                    parts.append(f"scrie {text}")
                instruction = " si ".join(parts) if parts else str(fields)
            elif fields.get("app_name") and fields.get("text_to_type"):
                instruction = f"deschide {fields['app_name']} si scrie {fields['text_to_type']}"
            return await self.run_task(instruction)

        filled = []
        errors = []

        for field_name, value in fields.items():
            if field_name.startswith("_"):
                continue

            png = await self.screenshot()
            if not png:
                errors.append(f"{field_name}: cannot take screenshot")
                continue

            prompt = f"""
You are controlling a computer screen.
Find the input field labeled "{field_name}" and return its center coordinates.
Return JSON: {{"found": true/false, "x": <pixel_x>, "y": <pixel_y>}}
Only return JSON, no other text.
"""
            try:
                result = await self._gemini_analyze(png, prompt)
                coords = json.loads(result)

                if coords.get("found"):
                    pyautogui.click(coords["x"], coords["y"])
                    await asyncio.sleep(0.3)
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.typewrite(str(value), interval=0.05)
                    filled.append(field_name)
                else:
                    errors.append(f"{field_name}: field not found on screen")
            except Exception as e:
                errors.append(f"{field_name}: {e}")

        # Handle submit
        if "_submit" in fields:
            submit_label = fields["_submit"]
            png = await self.screenshot()
            if png:
                prompt = f"""
Find the button labeled "{submit_label}" and return its center coordinates.
Return JSON: {{"found": true/false, "x": <pixel_x>, "y": <pixel_y>}}
Only return JSON.
"""
                try:
                    result = await self._gemini_analyze(png, prompt)
                    coords = json.loads(result)
                    if coords.get("found"):
                        pyautogui.click(coords["x"], coords["y"])
                        await asyncio.sleep(1)
                except Exception as e:
                    errors.append(f"submit: {e}")

        return {"success": len(errors) == 0, "filled": filled, "errors": errors}

    async def screenshot(self, region=None) -> Optional[bytes]:
        """Capture the screen (or a region) and return PNG bytes.
        Uses screencapture on macOS (more reliable than PIL.ImageGrab),
        falls back to PIL.ImageGrab on Linux/Windows."""
        loop = asyncio.get_event_loop()

        def _capture():
            import platform as _platform
            import tempfile, os, subprocess

            if _platform.system() == "Darwin":
                # macOS: use native screencapture (works without extra permissions in most cases)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                try:
                    if region:
                        x, y, w, h = region
                        subprocess.run(
                            ["screencapture", "-x", "-R", f"{x},{y},{w},{h}", tmp],
                            check=True, capture_output=True, timeout=5,
                        )
                    else:
                        subprocess.run(
                            ["screencapture", "-x", tmp],
                            check=True, capture_output=True, timeout=5,
                        )
                    with open(tmp, "rb") as f:
                        return f.read()
                except Exception:
                    return None
                finally:
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass
            else:
                # Linux / Windows: use PIL.ImageGrab
                if not PYAUTOGUI_AVAILABLE:
                    return None
                try:
                    if region:
                        img = PIL.ImageGrab.grab(bbox=(
                            region[0], region[1],
                            region[0] + region[2],
                            region[1] + region[3]
                        ))
                    else:
                        img = PIL.ImageGrab.grab()
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue()
                except Exception:
                    return None

        try:
            return await loop.run_in_executor(None, _capture)
        except Exception:
            return None

    # ── Desktop helpers ────────────────────────────────────────────────────

    async def click(self, target: str) -> dict:
        """
        Click a UI element identified by its label/text using Gemini Vision.
        target: text label or description of the button/element to click
        """
        if not self._gemini_model:
            return {"success": False, "error": "Connector not set up"}

        png = await self.screenshot()
        if not png:
            return {"success": False, "error": "Cannot capture screenshot"}

        prompt = f"""
Find the UI element "{target}" on screen and return its center coordinates.
Return JSON: {{"found": true/false, "x": <pixel_x>, "y": <pixel_y>}}
Only return JSON.
"""
        try:
            result = await self._gemini_analyze(png, prompt)
            coords = json.loads(result)
            if coords.get("found"):
                pyautogui.click(coords["x"], coords["y"])
                await asyncio.sleep(0.5)
                return {"success": True, "clicked_at": [coords["x"], coords["y"]]}
            else:
                return {"success": False, "error": f"Element '{target}' not found on screen"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, field: str, text: str) -> dict:
        """Click on field by label, then type text."""
        click_result = await self.click(field)
        if not click_result["success"]:
            return click_result
        try:
            pyautogui.hotkey("ctrl", "a")
            pyautogui.typewrite(text, interval=0.04)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for(self, condition: str, timeout: int = 30) -> dict:
        """
        Wait until Gemini Vision confirms the condition is visible on screen.
        condition: natural language description e.g. "the word 'Success' appears"
        """
        if not self._gemini_model:
            return {"success": False, "error": "Connector not set up"}

        start = time.time()
        while (time.time() - start) < timeout:
            png = await self.screenshot()
            if not png:
                await asyncio.sleep(1)
                continue
            prompt = f"""
Is the following condition true on this screen?
Condition: {condition}
Answer with JSON: {{"condition_met": true/false, "explanation": "..."}}
Only return JSON.
"""
            try:
                result = await self._gemini_analyze(png, prompt)
                data = json.loads(result)
                if data.get("condition_met"):
                    return {"success": True, "elapsed": round(time.time() - start, 1)}
            except Exception:
                pass
            await asyncio.sleep(1)

        return {"success": False, "error": f"Timeout after {timeout}s: '{condition}' not met"}

    async def read_screen(self, question: str) -> dict:
        """
        Ask Gemini Vision a free-form question about the current screen.
        Returns the answer as text.
        """
        if not self._gemini_model:
            return {"success": False, "error": "Connector not set up"}
        png = await self.screenshot()
        if not png:
            return {"success": False, "error": "Cannot capture screenshot"}
        try:
            answer = await self._gemini_analyze(png, question)
            return {"success": True, "answer": answer}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Internal ───────────────────────────────────────────────────────────

    async def _gemini_analyze(self, png_bytes: bytes, prompt: str) -> str:
        """Send screenshot + prompt to Gemini Vision, return text response."""
        loop = asyncio.get_event_loop()

        def _call():
            import PIL.Image
            import io as _io
            img = PIL.Image.open(_io.BytesIO(png_bytes))
            response = self._gemini_model.generate_content([prompt, img])
            return response.text.strip()

        return await loop.run_in_executor(None, _call)

    async def run_task(self, instruction: str, max_steps: int = 10, **kwargs) -> dict:
        """
        Execute a free-form desktop automation task described in natural language.
        Uses AppleScript on macOS (reliable, no pyautogui needed) + pyautogui fallback.

        Understands instructions like:
        - "deschide TextEdit si scrie cici cici"
        - "deschide Calculator si calculeaza 1+1"
        - "deschide Word si scrie Hello World"
        - "scrie ceva in fereastra activa"
        """
        import subprocess
        import platform
        import re

        steps_done = []
        instruction_lower = instruction.lower()
        is_mac = platform.system() == "Darwin"

        # ── Detect target app from instruction ────────────────────────────────
        # Maps keyword → macOS app name (for AppleScript) and Windows exe
        APP_MAP = {
            "textedit":   {"mac_name": "TextEdit",        "mac_new_doc": True,  "win": "notepad.exe"},
            "notepad":    {"mac_name": "TextEdit",        "mac_new_doc": True,  "win": "notepad.exe"},
            "word":       {"mac_name": "Microsoft Word",  "mac_new_doc": False, "win": "winword.exe"},
            "excel":      {"mac_name": "Microsoft Excel", "mac_new_doc": False, "win": "excel.exe"},
            "calculator": {"mac_name": "Calculator",      "mac_new_doc": False, "win": "calc.exe"},
            "safari":     {"mac_name": "Safari",          "mac_new_doc": False, "win": ""},
            "chrome":     {"mac_name": "Google Chrome",   "mac_new_doc": False, "win": "chrome.exe"},
            "finder":     {"mac_name": "Finder",          "mac_new_doc": False, "win": "explorer.exe"},
        }

        opened_app_key = None
        opened_app_info = None
        for key, info in APP_MAP.items():
            if key in instruction_lower:
                opened_app_key = key
                opened_app_info = info
                break

        # ── Step 1: Open the app via AppleScript / subprocess ─────────────────
        if opened_app_key and opened_app_info:
            if is_mac:
                mac_name = opened_app_info["mac_name"]
                make_doc = opened_app_info["mac_new_doc"]

                if make_doc:
                    # Open app via `open -a` (works whether app is running or not),
                    # then create new document via AppleScript
                    try:
                        subprocess.run(["open", "-a", mac_name], check=True, timeout=5)
                    except Exception:
                        pass
                    await asyncio.sleep(2)
                    new_doc_script = f'''
tell application "{mac_name}"
    activate
    make new document
end tell
'''
                    subprocess.run(["osascript", "-e", new_doc_script],
                                   capture_output=True, timeout=10)
                    await asyncio.sleep(1)
                    steps_done.append(f"Deschis {mac_name}")
                else:
                    try:
                        subprocess.run(["open", "-a", mac_name], check=True, timeout=5)
                        await asyncio.sleep(2)
                        steps_done.append(f"Deschis {mac_name}")
                    except Exception as e:
                        steps_done.append(f"Eroare deschidere {mac_name}: {e}")
            else:
                # Windows
                win_exe = opened_app_info.get("win", "")
                if win_exe:
                    try:
                        subprocess.Popen([win_exe])
                        await asyncio.sleep(2)
                        steps_done.append(f"Deschis {opened_app_key}")
                    except Exception as e:
                        steps_done.append(f"Eroare deschidere {opened_app_key}: {e}")

        # ── Step 2a: Calculator — type expression ─────────────────────────────
        if opened_app_key == "calculator":
            calc_match = re.search(
                r'(?:calculeaz[aă]|calculez[aă]|calc(?:ul)?|compute|=)\s*([\d\s\+\-\*\/\(\)\.]+)',
                instruction_lower
            )
            if calc_match:
                expr = calc_match.group(1).strip()
                try:
                    result_val = eval(expr.replace(" ", ""))
                except Exception:
                    result_val = "?"

                if is_mac:
                    # AppleScript keystroke for Calculator
                    safe_expr = expr.replace(" ", "")
                    calc_script = f'''
tell application "Calculator"
    activate
end tell
delay 1
tell application "System Events"
    keystroke "{safe_expr}"
    key code 36
end tell
delay 0.5
'''
                    try:
                        subprocess.run(["osascript", "-e", calc_script], capture_output=True, timeout=10)
                        steps_done.append(f"Calculat: {expr} = {result_val}")
                    except Exception as e:
                        steps_done.append(f"Eroare calculator: {e}")
                else:
                    try:
                        import pyautogui
                        await asyncio.sleep(1)
                        for ch in expr.replace(" ", ""):
                            if ch in "0123456789":
                                pyautogui.press(ch)
                            elif ch == "+":
                                pyautogui.hotkey('shift', 'equal')
                            elif ch == "-":
                                pyautogui.press('-')
                            elif ch == "*":
                                pyautogui.hotkey('shift', '8')
                            elif ch == "/":
                                pyautogui.press('/')
                            await asyncio.sleep(0.08)
                        pyautogui.press('return')
                        steps_done.append(f"Calculat: {expr} = {result_val}")
                    except ImportError:
                        steps_done.append(f"Calculat local: {expr} = {result_val}")

                await asyncio.sleep(0.5)
                screenshot_bytes = await self.screenshot()
                return {
                    "success": True,
                    "steps": steps_done,
                    "result": f"{expr} = {result_val}",
                    "message": f"Am calculat {expr} = **{result_val}**",
                    "has_screenshot": screenshot_bytes is not None,
                }

        # ── Step 2b: Type text in text editor / any app ───────────────────────
        # Patterns: "scrie X", "scrie textul X", "type X", "write X", "tastează X"
        # Strategy A: quoted text — most reliable, grab content between quotes
        quoted_match = re.search(
            r'''(?:scrie(?:\s+(?:textul|mesajul|urm[aă]torul\s+text))?|typeaz[aă]|type(?:\s+the\s+text)?|write(?:\s+the\s+text)?|introdu|tasteaz[aă]|tastează)\s+['"\u201c\u201e](.+?)['"\u201d\u201f]''',
            instruction, re.IGNORECASE
        )
        # Strategy B: unquoted — stop at prepositions / end of sentence
        # "textul:" with colon — skip it, grab what follows
        unquoted_match = re.search(
            r'''(?:scrie(?:\s+(?:textul|mesajul|urm[aă]torul\s+text))?|typeaz[aă]|type(?:\s+the\s+text)?|write(?:\s+the\s+text)?|introdu|tasteaz[aă]|tastează)\s+(?:(?:textul|mesajul|doar|only|just)\s*:?\s*)?([A-Za-z0-9\xC0-\xFF\u0100-\u024F][^\n,;.]*?)(?:\s+(?:în|in|pe|la|din|into|inside)\s+\w|$)''',
            instruction, re.IGNORECASE
        )
        write_match = quoted_match or unquoted_match
        if write_match:
            text_to_write = write_match.group(1).strip().strip("\"'\u201c\u201d\u201e\u201f")

            # Give app time to focus before typing
            await asyncio.sleep(1.0)
            typed_ok = False

            # Strategy 1: pyautogui.write() — works reliably on Mac with Accessibility
            if PYAUTOGUI_AVAILABLE:
                try:
                    if opened_app_info and is_mac:
                        subprocess.run(
                            ["osascript", "-e",
                             f'tell application "{opened_app_info["mac_name"]}" to activate'],
                            capture_output=True, timeout=5
                        )
                        await asyncio.sleep(0.4)
                    import pyautogui as _pag
                    _pag.write(text_to_write, interval=0.04)
                    steps_done.append(f"Scris text: '{text_to_write}'")
                    typed_ok = True
                except Exception as e:
                    steps_done.append(f"pyautogui eroare: {e}")

            # Strategy 2: clipboard paste (pbpaste on macOS) — no Accessibility needed
            if not typed_ok and is_mac:
                try:
                    subprocess.run(["pbcopy"], input=text_to_write.encode("utf-8"),
                                   check=True, timeout=5)
                    await asyncio.sleep(0.2)
                    # Cmd+V to paste
                    paste_script = 'tell application "System Events" to keystroke "v" using command down'
                    result = subprocess.run(["osascript", "-e", paste_script],
                                            capture_output=True, timeout=8)
                    if result.returncode == 0:
                        steps_done.append(f"Lipit din clipboard: '{text_to_write}'")
                        typed_ok = True
                    else:
                        err = result.stderr.decode(errors="replace").strip()
                        steps_done.append(f"Clipboard paste eroare: {err[:100]}")
                except Exception as e:
                    steps_done.append(f"Clipboard eroare: {e}")

            # Strategy 3: AppleScript keystroke (needs Accessibility for System Events)
            if not typed_ok and is_mac:
                target_app = opened_app_info["mac_name"] if opened_app_info else None
                if target_app:
                    type_script = f'tell application "{target_app}" to activate\ndelay 0.3\ntell application "System Events" to keystroke "{text_to_write}"'
                else:
                    type_script = f'tell application "System Events" to keystroke "{text_to_write}"'
                try:
                    result = subprocess.run(["osascript", "-e", type_script],
                                            capture_output=True, timeout=15)
                    if result.returncode == 0:
                        steps_done.append(f"Scris via AppleScript: '{text_to_write}'")
                        typed_ok = True
                    else:
                        err = result.stderr.decode(errors="replace").strip()
                        steps_done.append(f"AppleScript eroare: {err[:100]}")
                except Exception as e:
                    steps_done.append(f"AppleScript excepție: {e}")

            if not typed_ok and not is_mac:
                # Windows fallback
                try:
                    import pyautogui as _pag
                    _pag.write(text_to_write, interval=0.05)
                    steps_done.append(f"Scris text: '{text_to_write}'")
                except Exception as e:
                    steps_done.append(f"Windows tastare eroare: {e}")

            await asyncio.sleep(0.5)
            screenshot_bytes = await self.screenshot()
            return {
                "success": True,
                "steps": steps_done,
                "message": f"Am scris '{text_to_write}' în {opened_app_key or 'aplicația activă'}.",
                "has_screenshot": screenshot_bytes is not None,
            }

        # ── Step 3: Generic — just open app, take screenshot ──────────────────
        await asyncio.sleep(1)
        screenshot_bytes = await self.screenshot()

        if steps_done:
            return {
                "success": True,
                "steps": steps_done,
                "message": "Task executat: " + "; ".join(steps_done),
                "has_screenshot": screenshot_bytes is not None,
            }

        return {
            "success": False,
            "steps": steps_done,
            "message": (
                f"Nu am putut interpreta instrucțiunea: '{instruction}'.\n"
                "Exemple valide:\n"
                "- 'deschide TextEdit si scrie Hello World'\n"
                "- 'deschide Calculator si calculeaza 2+2'\n"
                "- 'scrie ceva in fereastra activa'"
            ),
        }

    async def open_app_and_type(self, app: str, text: str) -> dict:
        """
        Open a macOS app and type text into it — NO regex, direct params.
        app: e.g. "TextEdit", "Notes", "Word"
        text: exact text to type
        """
        import subprocess
        import platform
        steps = []
        is_mac = platform.system() == "Darwin"

        # Normalize app name
        APP_ALIASES = {
            "textedit": "TextEdit",
            "notes": "Notes",
            "word": "Microsoft Word",
            "excel": "Microsoft Excel",
            "notepad": "TextEdit",
        }
        mac_name = APP_ALIASES.get(app.lower(), app)

        if is_mac:
            # 1. Open app
            try:
                subprocess.run(["open", "-a", mac_name], check=True, timeout=5)
                await asyncio.sleep(2)
                steps.append(f"Deschis {mac_name}")
            except Exception as e:
                return {"success": False, "steps": steps, "error": f"Nu am putut deschide {mac_name}: {e}"}

            # 2. New document (for TextEdit/Notes)
            if mac_name in ("TextEdit", "Notes"):
                new_doc = f'tell application "{mac_name}"\n    activate\n    make new document\nend tell'
                subprocess.run(["osascript", "-e", new_doc], capture_output=True, timeout=10)
                await asyncio.sleep(1)

            # 3. Activate window
            activate = f'tell application "{mac_name}" to activate'
            subprocess.run(["osascript", "-e", activate], capture_output=True, timeout=5)
            await asyncio.sleep(0.5)

            # 4. Type text — Strategy 1: pyautogui
            typed = False
            if PYAUTOGUI_AVAILABLE:
                try:
                    import pyautogui as _pag
                    _pag.write(text, interval=0.04)
                    steps.append(f"Scris (pyautogui): '{text}'")
                    typed = True
                except Exception as e:
                    steps.append(f"pyautogui eroare: {e}")

            # Strategy 2: clipboard paste
            if not typed:
                try:
                    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, timeout=5)
                    await asyncio.sleep(0.2)
                    paste = 'tell application "System Events" to keystroke "v" using command down'
                    r = subprocess.run(["osascript", "-e", paste], capture_output=True, timeout=8)
                    if r.returncode == 0:
                        steps.append(f"Lipit din clipboard: '{text}'")
                        typed = True
                    else:
                        steps.append(f"Clipboard eroare: {r.stderr.decode(errors='replace')[:80]}")
                except Exception as e:
                    steps.append(f"Clipboard excepție: {e}")

            # Strategy 3: AppleScript keystroke
            if not typed:
                try:
                    ks = f'tell application "System Events" to keystroke "{text}"'
                    r = subprocess.run(["osascript", "-e", ks], capture_output=True, timeout=15)
                    if r.returncode == 0:
                        steps.append(f"Scris (AppleScript): '{text}'")
                        typed = True
                    else:
                        steps.append(f"AppleScript eroare: {r.stderr.decode(errors='replace')[:80]}")
                except Exception as e:
                    steps.append(f"AppleScript excepție: {e}")

            return {
                "success": typed,
                "steps": steps,
                "message": f"Am scris '{text}' în {mac_name}." if typed else f"Nu am putut scrie în {mac_name}.",
            }
        else:
            return {"success": False, "error": "open_app_and_type suportat doar pe macOS momentan"}

    async def navigate(self, target: str) -> dict:
        """Open a program or bring a window to focus by pressing Win+R or similar."""
        try:
            import subprocess
            import platform
            if platform.system() == "Windows":
                subprocess.Popen(["cmd", "/c", "start", target])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
            await asyncio.sleep(2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
