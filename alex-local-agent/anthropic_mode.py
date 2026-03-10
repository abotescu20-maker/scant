"""
Anthropic Computer Use Mode B (Optional).

Uses the Anthropic API's native computer_use tool to control the screen.
Instead of Gemini Vision + rule-based logic, this sends screenshots to
Claude claude-opus-4 / claude-sonnet-4-5 which decides exactly what to click/type.

Advantages vs Gemini Vision mode:
- More intelligent multi-step reasoning
- Better at novel/unexpected UI layouts
- Natural language instructions without JSON format
- Claude maintains context across multiple actions

Disadvantages:
- More expensive (~$0.01-0.05 per action)
- Slower (additional API round-trip per action)
- Requires Anthropic API key (separate from Alex's Gemini key)

Usage in tasks (Cloud Run sends):
{
    "task_id": "...",
    "connector": "anthropic_computer_use",
    "action": "run_task",
    "params": {
        "instruction": "Open the Allianz portal, find policy POL-2024-111, extract expiry date",
        "max_steps": 20
    }
}
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from typing import Optional

from connectors.base import BaseConnector

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import pyautogui
    import PIL.ImageGrab
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


class AnthropicComputerUseConnector(BaseConnector):
    """
    Uses Claude's native computer_use tool for maximum intelligence.

    Claude sees screenshots and decides:
    - Where to click
    - What to type
    - How to navigate
    - When the task is done

    This is the most powerful mode — Claude adapts to any UI without
    needing specific selectors or pre-coded logic.
    """

    name = "anthropic_computer_use"
    description = "Claude AI controls the computer directly via Anthropic computer_use API"
    requires_display = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-5",
        max_tokens: int = 4096,
        **kwargs,  # absorb extra kwargs like headless=True passed by registry
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self._client: Optional[anthropic.Anthropic] = None

        # Screen dimensions (detected at setup)
        self._screen_width = 1280
        self._screen_height = 800

    async def setup(self) -> None:
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "Anthropic SDK not installed. Run: pip install anthropic"
            )
        if not PYAUTOGUI_AVAILABLE:
            raise RuntimeError(
                "PyAutoGUI not installed. Run: pip install pyautogui pillow"
            )
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to config or environment."
            )

        self._client = anthropic.Anthropic(api_key=self.api_key)

        # Detect screen size
        try:
            size = pyautogui.size()
            self._screen_width = size.width
            self._screen_height = size.height
        except Exception:
            pass

        pyautogui.PAUSE = 0.3
        pyautogui.FAILSAFE = True

    async def teardown(self) -> None:
        self._client = None

    # ── Core interface ─────────────────────────────────────────────────────

    async def login(self, credentials: dict) -> dict:
        """Login using Claude's computer_use intelligence."""
        app = credentials.get("app_name", "the application")
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        url = credentials.get("url", "")

        instruction = f"Log into {app}"
        if url:
            instruction += f" at {url}"
        instruction += f" with username '{username}'"
        if password:
            instruction += f" and the provided password"

        result = await self.run_task(
            instruction=instruction,
            sensitive_data={"password": password} if password else {},
            max_steps=10,
        )
        return result

    async def extract(self, query: str, params: Optional[dict] = None) -> dict:
        """Extract data from screen using Claude's vision."""
        params = params or {}
        instruction = f"Look at the screen and extract: {query}. Return the extracted data clearly."
        if "url" in params:
            instruction = f"Navigate to {params['url']}, then " + instruction

        result = await self.run_task(instruction=instruction, max_steps=5)
        return result

    async def fill_form(self, fields: dict) -> dict:
        """Fill form fields using Claude's understanding."""
        field_desc = "\n".join(f"- {k}: {v}" for k, v in fields.items() if not k.startswith("_"))
        instruction = f"Fill in the following form fields:\n{field_desc}"
        if "_submit" in fields:
            instruction += f"\nThen click the '{fields['_submit']}' button."
        return await self.run_task(instruction=instruction, max_steps=15)

    async def read_screen(self, question: str = "What do you see on the screen?") -> dict:
        """Read/describe the current screen content. Alias for extract via run_task."""
        instruction = (
            f"{question}\n\n"
            "Look at the screen carefully and describe what you see. "
            "Be specific about any text, numbers, forms, or UI elements visible. "
            "Report the result clearly."
        )
        return await self.run_task(instruction=instruction, max_steps=3)

    async def screenshot(self) -> Optional[bytes]:
        """Capture current screen. Uses screencapture on macOS (most reliable)."""
        loop = asyncio.get_event_loop()

        def _capture():
            import platform as _platform
            import tempfile, os, subprocess

            if _platform.system() == "Darwin":
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                try:
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
                if not PYAUTOGUI_AVAILABLE:
                    return None
                try:
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

    # ── Main computer_use loop ─────────────────────────────────────────────

    async def run_task(
        self,
        instruction: str,
        sensitive_data: Optional[dict] = None,
        max_steps: int = 20,
    ) -> dict:
        """
        Run a computer_use task with Claude controlling the computer.

        Args:
            instruction: natural language instruction for Claude
            sensitive_data: dict of sensitive values (passwords, etc.) that
                           Claude should type but we don't log
            max_steps: maximum number of actions before giving up

        Returns:
            {"success": True/False, "result": "...", "steps": N, "actions_taken": [...]}
        """
        if not self._client:
            return {"success": False, "error": "Connector not set up"}

        # Messages history — starts with instruction + screenshot on step 1
        # On subsequent steps, screenshot is added as tool_result after tool_use
        messages = []
        actions_taken = []
        step = 0

        while step < max_steps:
            step += 1

            # Capture current screen
            png = await self.screenshot()
            if not png:
                return {"success": False, "error": "Cannot capture screenshot"}

            screenshot_b64 = base64.standard_b64encode(png).decode("utf-8")

            if step == 1:
                # First turn: instruction text + screenshot image together
                api_messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": screenshot_b64,
                                },
                            },
                        ],
                    }
                ]
            else:
                # Subsequent turns: include full conversation + new screenshot as tool_result
                # (screenshot tool_use_id from Claude's last tool_use block)
                last_tool_use_id = actions_taken[-1].get("tool_use_id", "toolu_screenshot") if actions_taken else "toolu_screenshot"
                screenshot_result = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": last_tool_use_id,
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": screenshot_b64,
                                    },
                                }
                            ],
                        }
                    ],
                }
                api_messages = messages + [screenshot_result]

            # Call Claude with computer_use tools
            try:
                loop = asyncio.get_event_loop()
                _api_messages_snapshot = api_messages  # capture for lambda closure
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.beta.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        tools=[
                            {
                                "type": "computer_20250124",
                                "name": "computer",
                                "display_width_px": self._screen_width,
                                "display_height_px": self._screen_height,
                            }
                        ],
                        messages=_api_messages_snapshot,
                        betas=["computer-use-2025-01-24"],
                    )
                )
            except Exception as e:
                return {"success": False, "error": f"Anthropic API error: {e}", "steps": step}

            # Update messages with what we sent this turn (for step 1, messages was empty)
            if step == 1:
                messages = list(api_messages)  # save the first user turn

            # Process Claude's response
            final_text = None
            for block in response.content:
                if block.type == "text":
                    final_text = block.text
                    messages.append({"role": "assistant", "content": block.text})
                    # Check if Claude says the task is done
                    if any(phrase in block.text.lower() for phrase in [
                        "task complete", "done", "finished", "extracted", "successfully",
                        "am terminat", "gata", "am extras", "result", "the screen shows",
                    ]):
                        return {
                            "success": True,
                            "result": block.text,
                            "steps": step,
                            "actions_taken": actions_taken,
                        }

                elif block.type == "tool_use" and block.name == "computer":
                    action_input = block.input
                    action_type = action_input.get("action", "")

                    # If Claude wants a screenshot, we'll provide it at the top of the next loop
                    # For all other actions, execute them now
                    if action_type != "screenshot":
                        action_result = await self._execute_computer_action(
                            action_input, sensitive_data or {}
                        )
                    else:
                        action_result = {"success": True}

                    actions_taken.append({
                        "step": step,
                        "action": action_type,
                        "tool_use_id": block.id,
                        "success": action_result.get("success", True),
                    })

                    # Add assistant tool_use + user tool_result to history
                    messages.append({
                        "role": "assistant",
                        "content": [{"type": "tool_use", "id": block.id, "name": "computer", "input": action_input}],
                    })

                    if action_type == "screenshot":
                        # Don't add text result — next loop iteration will add screenshot image
                        pass
                    else:
                        result_text = "Action executed successfully" if action_result.get("success") else f"Action failed: {action_result.get('error', 'unknown error')}"
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": [{"type": "text", "text": result_text}],
                            }],
                        })

            if response.stop_reason == "end_turn":
                # Claude finished — if we have any text, return it as success
                if final_text:
                    return {
                        "success": True,
                        "result": final_text,
                        "steps": step,
                        "actions_taken": actions_taken,
                    }
                break

        return {
            "success": False,
            "error": f"Task not completed after {max_steps} steps",
            "steps": step,
            "actions_taken": actions_taken,
        }

    async def _execute_computer_action(self, action: dict, sensitive_data: dict) -> dict:
        """Execute a computer_use action from Claude."""
        action_type = action.get("action")
        loop = asyncio.get_event_loop()

        def _run_sync():
            if action_type == "screenshot":
                return {"success": True}  # we take screenshot at top of loop

            elif action_type == "left_click":
                x, y = action.get("coordinate", [0, 0])
                pyautogui.click(x, y)
                return {"success": True}

            elif action_type == "double_click":
                x, y = action.get("coordinate", [0, 0])
                pyautogui.doubleClick(x, y)
                return {"success": True}

            elif action_type == "right_click":
                x, y = action.get("coordinate", [0, 0])
                pyautogui.rightClick(x, y)
                return {"success": True}

            elif action_type == "mouse_move":
                x, y = action.get("coordinate", [0, 0])
                pyautogui.moveTo(x, y)
                return {"success": True}

            elif action_type == "type":
                text = action.get("text", "")
                # Replace sensitive placeholders
                for placeholder, actual in sensitive_data.items():
                    text = text.replace(f"<{placeholder}>", actual)
                pyautogui.typewrite(text, interval=0.04)
                return {"success": True}

            elif action_type == "key":
                key = action.get("key", "")
                # Map Anthropic key names to PyAutoGUI names
                key_map = {
                    "Return": "enter", "BackSpace": "backspace",
                    "Tab": "tab", "Escape": "escape",
                    "ctrl+a": ("ctrl", "a"), "ctrl+c": ("ctrl", "c"),
                    "ctrl+v": ("ctrl", "v"), "ctrl+z": ("ctrl", "z"),
                }
                if key in key_map:
                    mapped = key_map[key]
                    if isinstance(mapped, tuple):
                        pyautogui.hotkey(*mapped)
                    else:
                        pyautogui.press(mapped)
                else:
                    pyautogui.press(key.lower())
                return {"success": True}

            elif action_type == "scroll":
                x, y = action.get("coordinate", [0, 0])
                direction = action.get("direction", "down")
                amount = action.get("amount", 3)
                pyautogui.moveTo(x, y)
                if direction == "down":
                    pyautogui.scroll(-amount)
                else:
                    pyautogui.scroll(amount)
                return {"success": True}

            return {"success": False, "error": f"Unknown action: {action_type}"}

        try:
            result = await loop.run_in_executor(None, _run_sync)
            await asyncio.sleep(0.3)  # wait for UI to react
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
