import os
import time
import asyncio
import base64
import re
import subprocess
import sys
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
from dotenv import load_dotenv
from google import genai
from google.genai import types

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional in cloud/server deployments
    async_playwright = None

# 1. Load API Key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("Please set GEMINI_API_KEY in your .env file")

# 2. Configuration
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900
# UPDATED: Use the specific Computer Use preview model
MODEL_ID = "gemini-2.5-computer-use-preview-10-2025"

KNOWN_DOMAINS = {
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "openai": "https://openai.com",
    "gmail": "https://mail.google.com",
    "google docs": "https://docs.google.com",
    "google drive": "https://drive.google.com",
    "google calendar": "https://calendar.google.com",
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "whatsapp web": "https://web.whatsapp.com",
    "notion": "https://www.notion.so",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
    "spotify": "https://open.spotify.com",
    "linkedin": "https://www.linkedin.com",
    "x": "https://x.com",
    "twitter": "https://x.com",
    "instagram": "https://www.instagram.com",
    "claude": "https://claude.ai",
    "perplexity": "https://www.perplexity.ai",
}

class WebAgent:
    def __init__(self):
        self.client = genai.Client(api_key=API_KEY)
        self.browser = None
        self.context = None
        self.page = None

    async def ensure_browser(self):
        if async_playwright is None:
            raise RuntimeError("Playwright is not installed, so the browser agent is unavailable on this deployment.")
        if self.browser and self.context and self.page:
            return

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        await self.page.goto("https://www.google.com")

    async def _emit_snapshot(self, update_callback, log_text):
        if not update_callback:
            return
        screenshot_bytes = await self.page.screenshot(type="png")
        encoded_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        await update_callback(encoded_image, log_text)

    def _extract_url(self, prompt: str) -> str | None:
        match = re.search(r'https?://\S+', prompt)
        if match:
            return match.group(0)
        domain_match = re.search(r'\b([a-zA-Z0-9-]+\.(?:com|in|org|net|ai|io|co))\b', prompt)
        if domain_match:
            return f"https://{domain_match.group(1)}"
        return None

    def _normalized_site_query(self, prompt: str) -> str:
        text = (prompt or "").strip().lower()
        text = re.sub(
            r"^(open|go to|visit|launch|take me to|browse to|navigate to)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\b(website|site|homepage|official site|official website)\b", "", text)
        text = re.sub(r"\s+", " ", text).strip(" .?!")
        return text

    def _first_search_result_url(self, query: str) -> str | None:
        search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            req = Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                },
            )
            with urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

        for href in re.findall(r'href="([^"]+)"', html):
            if "duckduckgo.com/l/?" not in href:
                continue
            parsed = urlparse(href)
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            if not target:
                continue
            target = unquote(target)
            if target.startswith("http://") or target.startswith("https://"):
                return target
        return None

    def _resolve_website_url(self, prompt: str) -> tuple[str, str] | None:
        query = self._normalized_site_query(prompt)
        if not query:
            return None

        if query in KNOWN_DOMAINS:
            url = KNOWN_DOMAINS[query]
            return url, f"Opened {query} in Chrome."

        direct_match = self._extract_url(query)
        if direct_match:
            return direct_match, f"Opened {direct_match} in Chrome."

        return None

    def _has_explicit_website_intent(self, prompt: str) -> bool:
        text = (prompt or "").strip().lower()
        return any(token in text for token in (
            "website",
            "site",
            "homepage",
            "official page",
            "official website",
            "official site",
            "link",
            "url",
        ))

    def _is_whatsapp_message_intent(self, prompt: str) -> bool:
        text = (prompt or "").strip().lower()
        if "whatsapp" not in text:
            return False
        return any(token in text for token in (
            "message",
            "text ",
            "send ",
            "chat",
            "contact",
            "reply",
            "tell ",
            "say ",
            "mom",
        ))

    def _should_use_direct_browser_mode(self, prompt: str) -> bool:
        text = (prompt or "").strip().lower()
        if not text:
            return False

        if self._extract_url(text):
            return True

        if text.startswith(("search ", "search google for ", "search youtube for ", "look up ", "find ")):
            return True

        if text.startswith(("play ", "watch ", "open youtube video ")):
            return True

        if text in {"youtube", "gmail", "google"}:
            return True

        if text.startswith(("open ", "go to ", "visit ", "launch ", "take me to ", "browse to ", "navigate to ")):
            query = self._normalized_site_query(text)
            if query in KNOWN_DOMAINS:
                return True
            if self._extract_url(query):
                return True
            if self._has_explicit_website_intent(text):
                return True
            return True

        return False

    def _first_youtube_video_url(self, query: str) -> str | None:
        search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        try:
            req = Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                },
            )
            with urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

        for video_id in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html):
            return f"https://www.youtube.com/watch?v={video_id}"

        for video_id in re.findall(r'watch\?v=([A-Za-z0-9_-]{11})', html):
            return f"https://www.youtube.com/watch?v={video_id}"

        return None

    def _browser_url_for_prompt(self, prompt: str) -> tuple[str, str]:
        text = (prompt or "").strip()
        lowered = text.lower()
        url = self._extract_url(text)

        if self._is_whatsapp_message_intent(text):
            return (
                "https://web.whatsapp.com",
                "Opened WhatsApp Web in Chrome.",
            )

        youtube_direct_query = None
        if lowered.startswith("play "):
            youtube_direct_query = text[5:].strip(" .?!")
        elif lowered.startswith("watch "):
            youtube_direct_query = text[6:].strip(" .?!")
        elif lowered.startswith("open youtube video "):
            youtube_direct_query = text[len("open youtube video "):].strip(" .?!")
        elif " trailer" in lowered or "official trailer" in lowered or "music video" in lowered:
            youtube_direct_query = text.strip(" .?!")

        if youtube_direct_query:
            direct_url = self._first_youtube_video_url(youtube_direct_query)
            if direct_url:
                return (
                    direct_url,
                    f"Opened the top YouTube result for '{youtube_direct_query}' in Chrome.",
                )
            return (
                f"https://www.youtube.com/results?search_query={quote_plus(youtube_direct_query)}",
                f"Opened YouTube search results for '{youtube_direct_query}' in Chrome.",
            )

        if lowered.startswith("search youtube for "):
            query = text[len("search youtube for "):].strip(" .?!")
            return (
                f"https://www.youtube.com/results?search_query={quote_plus(query)}",
                f"Opened YouTube search results for '{query}' in Chrome.",
            )

        match = re.search(r"(?:search(?: youtube)? for|look up|find)\s+(.+)", text, re.IGNORECASE)
        if match and "youtube" in lowered:
            query = match.group(1).strip(" .?!")
            return (
                f"https://www.youtube.com/results?search_query={quote_plus(query)}",
                f"Opened YouTube search results for '{query}' in Chrome.",
            )

        if "open youtube" in lowered or lowered == "youtube":
            return ("https://www.youtube.com", "Opened YouTube in Chrome.")

        if "open gmail" in lowered or lowered == "gmail":
            return ("https://mail.google.com", "Opened Gmail in Chrome.")

        if lowered.startswith("search google for "):
            query = text[len("search google for "):].strip(" .?!")
            return (
                f"https://www.google.com/search?q={quote_plus(query)}",
                f"Opened Google results for '{query}' in Chrome.",
            )

        if lowered.startswith(("open ", "go to ", "visit ", "launch ", "take me to ", "browse to ", "navigate to ")):
            resolved_site = self._resolve_website_url(text)
            if resolved_site:
                return resolved_site
            query = self._normalized_site_query(text)
            return (
                f"https://www.google.com/search?q={quote_plus(query)}",
                f"Opened Google results for '{query}' in Chrome.",
            )

        if url:
            return (url, f"Opened {url} in Chrome.")

        search_prompt = text.replace("open ", "", 1) if lowered.startswith("open ") else text
        search_prompt = search_prompt.strip(" .?!")
        return (
            f"https://www.google.com/search?q={quote_plus(search_prompt)}",
            f"Opened Google results for '{search_prompt}' in Chrome.",
        )

    async def open_in_system_browser(self, prompt: str, update_callback=None, reason=None):
        prompt_lower = (prompt or "").strip().lower()

        if any(phrase in prompt_lower for phrase in ("close tab", "close the tab", "close browser tab", "close this tab", "close chrome tab", "close youtube tab")):
            try:
                if sys.platform == "darwin":
                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            'tell application "Google Chrome" to if (count of windows) > 0 then close active tab of front window',
                        ],
                        check=True,
                    )
                else:
                    raise RuntimeError("System tab closing is only implemented for macOS right now.")
            except Exception as e:
                message = f"Failed to close the active browser tab: {e}"
                if update_callback:
                    await update_callback(None, message)
                return message

            message = "Closed the active Chrome tab."
            if update_callback:
                await update_callback(None, message)
            return message

        target, result = self._browser_url_for_prompt(prompt)
        prefix = "Direct browser mode"
        if reason:
            prefix += f" after {reason}"

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-a", "Google Chrome", target], check=True)
            else:
                subprocess.run(["open", target], check=True)
        except Exception:
            if sys.platform == "darwin":
                subprocess.run(["open", target], check=True)
            else:
                raise

        if update_callback:
            await update_callback(None, f"{prefix}. {result}")
        return result

    async def fallback_run_task(self, prompt, update_callback=None, reason=None):
        await self.ensure_browser()
        prompt_lower = (prompt or "").strip().lower()
        url = self._extract_url(prompt_lower)
        prefix = "Fallback browser mode"
        if reason:
            prefix += f" after model failure: {reason}"

        if self._is_whatsapp_message_intent(prompt):
            await self.page.goto("https://web.whatsapp.com")
            await self._emit_snapshot(update_callback, f"{prefix}. Opened WhatsApp Web directly for the messaging task.")
            return "Opened WhatsApp Web in fallback browser mode."

        if "youtube" in prompt_lower and not url:
            await self.page.goto("https://www.youtube.com")
            await self._emit_snapshot(update_callback, f"{prefix}. Opened YouTube directly.")
            return "Opened YouTube in fallback browser mode."

        youtube_search_match = re.search(r"(?:search(?: youtube)? for|look up)\s+(.+)", prompt_lower)
        if youtube_search_match and "youtube.com" in (self.page.url or ""):
            query = youtube_search_match.group(1).strip(" .?!")
            await self.page.goto("https://www.youtube.com/results?search_query=" + query.replace(" ", "+"))
            await self._emit_snapshot(update_callback, f"{prefix}. Searched YouTube for: {query}")
            return f"Searched YouTube for '{query}' in fallback browser mode."

        if prompt_lower.startswith("search youtube for "):
            query = prompt_lower.replace("search youtube for ", "", 1).strip(" .?!")
            await self.page.goto("https://www.youtube.com/results?search_query=" + query.replace(" ", "+"))
            await self._emit_snapshot(update_callback, f"{prefix}. Searched YouTube for: {query}")
            return f"Searched YouTube for '{query}' in fallback browser mode."

        if url:
            await self.page.goto(url)
            await self._emit_snapshot(update_callback, f"{prefix}. Opened {url}.")
            return f"Opened {url} in fallback browser mode."

        search_prompt = prompt.strip()
        await self.page.goto("https://www.google.com/search?q=" + search_prompt.replace(" ", "+"))
        await self._emit_snapshot(update_callback, f"{prefix}. Ran a Google search for: {search_prompt}")
        return f"Ran a browser search for '{search_prompt}' in fallback mode."

    def denormalize_x(self, x: int, width: int) -> int:
        return int((x / 1000) * width)

    def denormalize_y(self, y: int, height: int) -> int:
        return int((y / 1000) * height)

    async def execute_function_calls(self, function_calls):
        results = []
        
        for call in function_calls:
            # Extract ID if available, otherwise it might be None or empty depending on the SDK version
            # But the Computer Use model typically expects IDs to be threaded back.
            call_id = getattr(call, 'id', None)
            fn_name = call.name
            args = call.args
            print(f"[ACTION] Action: {fn_name} {args}")

            # --- SAFETY CHECK ---
            requires_acknowledgement = False
            if "safety_decision" in args:
                 decision = args["safety_decision"]
                 if decision.get("decision") == "require_confirmation":
                     print(f"   [SAFETY] Safety Alert: {decision.get('explanation')}")
                     print("   -> Auto-acknowledging to proceed.")
                     requires_acknowledgement = True

            result_data = {}
            
            try:
                # --- NAVIGATION ---
                if fn_name == "open_web_browser":
                    pass 
                elif fn_name == "navigate":
                    await self.page.goto(args["url"])
                elif fn_name == "go_back":
                    await self.page.go_back()
                elif fn_name == "go_forward":
                    await self.page.go_forward()
                elif fn_name == "search":
                    await self.page.goto("https://www.google.com")
                elif fn_name == "wait_5_seconds":
                    await asyncio.sleep(5)

                # --- MOUSE CLICKS & TYPING ---
                elif fn_name == "click_at":
                    x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    await self.page.mouse.click(x, y)
                    
                elif fn_name == "type_text_at":
                    x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    text = args["text"]
                    press_enter = args.get("press_enter", False)
                    clear_before = args.get("clear_before_typing", True)
                    
                    await self.page.mouse.click(x, y)
                    if clear_before:
                        # 'Meta+A' for Mac, 'Control+A' for Windows/Linux
                        # Simply using Control+A is usually fine for headless linux/windows envs
                        await self.page.keyboard.press("Control+A") 
                        await self.page.keyboard.press("Backspace")
                    
                    await self.page.keyboard.type(text)
                    if press_enter:
                        await self.page.keyboard.press("Enter")

                # --- MOUSE MOVEMENT / HOVER ---
                elif fn_name == "hover_at":
                    x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    await self.page.mouse.move(x, y)

                elif fn_name == "drag_and_drop":
                    start_x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                    start_y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                    end_x = self.denormalize_x(args["destination_x"], SCREEN_WIDTH)
                    end_y = self.denormalize_y(args["destination_y"], SCREEN_HEIGHT)
                    
                    await self.page.mouse.move(start_x, start_y)
                    await self.page.mouse.down()
                    await self.page.mouse.move(end_x, end_y)
                    await self.page.mouse.up()

                # --- KEYBOARD ---
                elif fn_name == "key_combination":
                    key_comb = args.get("keys")
                    await self.page.keyboard.press(key_comb)

                # --- SCROLLING ---
                elif fn_name == "scroll_document" or fn_name == "scroll_at":
                    magnitude = args.get("magnitude", 800)
                    direction = args.get("direction", "down")
                    
                    # If scroll_at, move mouse there first
                    if fn_name == "scroll_at":
                        x = self.denormalize_x(args["x"], SCREEN_WIDTH)
                        y = self.denormalize_y(args["y"], SCREEN_HEIGHT)
                        await self.page.mouse.move(x, y)

                    dx, dy = 0, 0
                    if direction == "down": dy = magnitude
                    elif direction == "up": dy = -magnitude
                    elif direction == "right": dx = magnitude
                    elif direction == "left": dx = -magnitude
                    
                    await self.page.mouse.wheel(dx, dy)

                else:
                    print(f"[WARN] Warning: Model requested unimplemented function {fn_name}")

                # Wait a moment for UI to settle
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[ERR] Error executing {fn_name}: {e}")
                result_data = {"error": str(e)}

            # Add the acknowledgement flag if needed
            if requires_acknowledgement:
                result_data["safety_acknowledgement"] = True

            results.append((call_id, fn_name, result_data))
        
        return results

    async def get_function_responses(self, results):
        # UPDATED: Changed "jpeg" to "png" to satisfy Computer Use model requirements
        screenshot_bytes = await self.page.screenshot(type="png") 
        current_url = self.page.url
        
        function_responses = []
        for call_id, name, result in results:
            response_data = {"url": current_url}
            response_data.update(result)
            
            # Construct the response object
            # Note: The SDK might change how 'id' is passed. 
            # If 'types.FunctionResponse' supports 'id', we pass it.
            # Based on standard Google GenAI SDK usage for function calling:
            function_responses.append(
                types.FunctionResponse(
                    name=name,
                    id=call_id, # critical for matching request-response
                    response=response_data,
                    parts=[types.FunctionResponsePart(
                        inline_data=types.FunctionResponseBlob(
                            # UPDATED: Changed "image/jpeg" to "image/png"
                            mime_type="image/png",
                            data=screenshot_bytes
                        )
                    )]
                )
            )
        return function_responses, screenshot_bytes

    async def run_task(self, prompt, update_callback=None):
        """
        Runs the agent with the given prompt.
        update_callback: async function(screenshot_b64: str, logs: str)
        Returns the final response from the agent.
        """
        print(f"[START] WebAgent started. Goal: {prompt}")
        final_response = "Agent finished without a final summary."

        if self._should_use_direct_browser_mode(prompt):
            return await self.open_in_system_browser(prompt, update_callback=update_callback, reason="direct browser mode")

        await self.ensure_browser()

        config = types.GenerateContentConfig(
            tools=[types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_BROWSER
                )
            )],
            thinking_config=types.ThinkingConfig(include_thoughts=True) 
        )

        # UPDATED: Capture initial screenshot as PNG
        initial_screenshot = await self.page.screenshot(type="png")
        
        # Send initial state
        if update_callback:
            encoded_image = base64.b64encode(initial_screenshot).decode('utf-8')
            await update_callback(encoded_image, "Web Agent Initialized")

        chat_history = [
            types.Content(
                role="user",
                parts=[
                    types.Part(text=prompt),
                    types.Part.from_bytes(data=initial_screenshot, mime_type="image/png")
                ]
            )
        ]

        MAX_TURNS = 20
        
        for turn in range(MAX_TURNS):
            print(f"\n--- Turn {turn + 1} ---")
            
            try:
                response = await self.client.aio.models.generate_content(
                    model=MODEL_ID,
                    contents=chat_history,
                    config=config
                )
            except Exception as e:
                print(f"[CRITICAL] Critical API Error: {e}")
                error_text = str(e)
                if "quota" in error_text.lower() or "429" in error_text or "GenerateRequestsPerMinutePerProjectPerModel-FreeTier" in error_text:
                    final_response = await self.fallback_run_task(
                        prompt,
                        update_callback=update_callback,
                        reason="Gemini computer-use quota is currently rate-limited",
                    )
                    break
                if update_callback:
                    await update_callback(None, f"Error: {error_text}")
                final_response = await self.fallback_run_task(prompt, update_callback=update_callback, reason=error_text)
                break
            
            if not response.candidates:
                print("[WARN] Model returned no content.")
                break
            
            candidate = response.candidates[0]
            model_content = candidate.content
            chat_history.append(model_content)

            # Process thoughts and tool calls
            has_tool_use = False
            thought_text = ""
            agent_text = ""
            
            for part in model_content.parts:
                if part.thought:
                    print(f"[THOUGHT] Thought: {part.text}")
                    thought_text += f"[Thoughts] {part.text}\n"
                elif part.text:
                    print(f"[AGENT] Agent: {part.text}")
                    thought_text += f"[Agent] {part.text}\n"
                    agent_text = part.text
                if part.function_call:
                    has_tool_use = True
            
            if agent_text:
                final_response = agent_text

            if update_callback and thought_text:
                pass

            function_calls = [part.function_call for part in model_content.parts if part.function_call]
            
            if not function_calls:
                if not has_tool_use:
                    print("[DONE] Task finished details.")
                    if update_callback:
                        await update_callback(None, "Task Finished")
                    break
                else:
                    print("...Thinking...")
                    continue

            results = await self.execute_function_calls(function_calls)
            
            print("[SNAP] Capturing new state...")
            function_responses, screenshot_bytes = await self.get_function_responses(results)
            
            if update_callback:
                encoded_image = base64.b64encode(screenshot_bytes).decode('utf-8')
                actions_log = ", ".join([r[1] for r in results])
                await update_callback(encoded_image, f"Executed: {actions_log}")

            response_parts = [types.Part(function_response=fr) for fr in function_responses]
            chat_history.append(types.Content(role="user", parts=response_parts))

        return final_response

if __name__ == "__main__":
    agent = WebAgent()
    asyncio.run(agent.run_task("Go to google.com and search for 'Gemini API' pricing."))
