import asyncio
import json
from itertools import count

from websockets.asyncio.client import connect as ws_connect


class KaptureClient:
    HTTP_BASES = ("http://localhost:61822", "http://127.0.0.1:61822")
    WS_URLS = ("ws://localhost:61822/mcp", "ws://127.0.0.1:61822/mcp")

    def __init__(self):
        self.websocket = None
        self._initialized = False
        self._request_ids = count(1)
        self._lock = asyncio.Lock()
        self.http_base = self.HTTP_BASES[0]
        self._last_tab_id = None

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        self._initialized = False

    def _http_json(self, path: str):
        from urllib.request import urlopen

        last_error = None
        for base in self.HTTP_BASES:
            try:
                with urlopen(f"{base}{path}", timeout=5) as response:
                    self.http_base = base
                    return json.loads(response.read().decode("utf-8"))
            except Exception as e:
                last_error = e
        raise last_error

    async def is_available(self) -> bool:
        try:
            await asyncio.to_thread(self._http_json, "/tabs")
            return True
        except Exception:
            return False

    async def list_tabs(self):
        try:
            result = await self.call_tool("list_tabs", {})
            tabs = self._extract_tabs(result)
            if tabs:
                return tabs
        except Exception:
            pass

        try:
            result = await asyncio.to_thread(self._http_json, "/tabs")
            tabs = self._extract_tabs(result)
            if tabs:
                return tabs
        except Exception:
            pass
        return []

    def _extract_tabs(self, result):
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("tabs", "connectedTabs", "data", "currentTabs"):
                value = result.get(key)
                if isinstance(value, list):
                    return value
        return []

    async def _ensure_connection(self):
        if self.websocket and not getattr(self.websocket, "closed", False):
            return

        last_error = None
        for url in self.WS_URLS:
            try:
                self.websocket = await ws_connect(url, max_size=8 * 1024 * 1024)
                self._initialized = False
                return
            except Exception as e:
                last_error = e
        raise last_error

    async def _initialize_locked(self):
        if self._initialized:
            return

        result = await self._send_request_locked(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "edith-kapture-client",
                    "version": "1.0.0",
                },
            },
        )

        await self.websocket.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }
            )
        )
        self._initialized = True
        return result

    async def _send_request_locked(self, method: str, params: dict | None = None):
        request_id = next(self._request_ids)
        await self.websocket.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params or {},
                }
            )
        )

        while True:
            raw = await asyncio.wait_for(self.websocket.recv(), timeout=20)
            message = json.loads(raw)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(message["error"].get("message", "Unknown Kapture error"))
            return message.get("result", {})

    async def _request(self, method: str, params: dict | None = None):
        async with self._lock:
            for attempt in range(2):
                try:
                    await self._ensure_connection()
                    if not self._initialized:
                        await self._initialize_locked()
                    return await self._send_request_locked(method, params)
                except Exception:
                    await self.close()
                    if attempt == 1:
                        raise

    async def call_tool(self, name: str, arguments: dict | None = None):
        result = await self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
        return self._normalize_result(result)

    def _normalize_result(self, result):
        if not isinstance(result, dict):
            return {"raw": result}

        if isinstance(result.get("structuredContent"), dict):
            structured = dict(result["structuredContent"])
            if result.get("content"):
                structured["_content"] = result["content"]
            return structured

        content = result.get("content")
        if isinstance(content, list):
            texts = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and part.get("text"):
                    texts.append(part["text"])
                elif part.get("type") == "image" and part.get("data"):
                    return {
                        "image_base64": part["data"],
                        "mimeType": part.get("mimeType", "image/png"),
                    }
            if texts:
                text = "\n".join(texts)
                try:
                    return json.loads(text)
                except Exception:
                    return {"text": text}

        return result

    async def _resolve_tab_id(self, tab_id: str | None = None):
        if tab_id:
            self._last_tab_id = tab_id
            return tab_id

        tabs = []
        for _ in range(3):
            tabs = await self.list_tabs()
            if tabs:
                break
            await asyncio.sleep(0.2)

        if not tabs and self._last_tab_id:
            return self._last_tab_id
        if not tabs:
            raise RuntimeError("No Kapture-connected tabs are available.")

        for tab in tabs:
            if isinstance(tab, dict) and (tab.get("active") or tab.get("current") or tab.get("focused")):
                resolved = tab.get("tabId") or tab.get("id")
                if resolved:
                    self._last_tab_id = resolved
                    return resolved

        first = tabs[0]
        if isinstance(first, dict):
            resolved = first.get("tabId") or first.get("id")
            if resolved:
                self._last_tab_id = resolved
                return resolved
        return None

    async def navigate(self, url: str, tab_id: str | None = None):
        resolved_tab = await self._resolve_tab_id(tab_id)
        result = await self.call_tool("navigate", {"tabId": resolved_tab, "url": url})
        self._last_tab_id = resolved_tab
        return result

    async def click(self, selector: str | None = None, xpath: str | None = None, tab_id: str | None = None):
        resolved_tab = await self._resolve_tab_id(tab_id)
        payload = {"tabId": resolved_tab}
        if selector:
            payload["selector"] = selector
        if xpath:
            payload["xpath"] = xpath
        result = await self.call_tool("click", payload)
        self._last_tab_id = resolved_tab
        return result

    async def fill(self, selector: str, value: str, tab_id: str | None = None):
        resolved_tab = await self._resolve_tab_id(tab_id)
        result = await self.call_tool("fill", {"tabId": resolved_tab, "selector": selector, "value": value})
        self._last_tab_id = resolved_tab
        return result

    async def keypress(self, key: str | None = None, text: str | None = None, tab_id: str | None = None):
        resolved_tab = await self._resolve_tab_id(tab_id)
        payload = {"tabId": resolved_tab}
        if key:
            payload["key"] = key
        if text:
            payload["text"] = text
        result = await self.call_tool("keypress", payload)
        self._last_tab_id = resolved_tab
        return result

    async def dom(self, selector: str | None = None, tab_id: str | None = None):
        resolved_tab = await self._resolve_tab_id(tab_id)
        payload = {"tabId": resolved_tab}
        if selector:
            payload["selector"] = selector
        result = await self.call_tool("dom", payload)
        self._last_tab_id = resolved_tab
        return result

    async def screenshot(self, tab_id: str | None = None, selector: str | None = None, scale: float = 0.5):
        resolved_tab = await self._resolve_tab_id(tab_id)
        payload = {"tabId": resolved_tab, "scale": scale}
        if selector:
            payload["selector"] = selector
        result = await self.call_tool("screenshot", payload)
        self._last_tab_id = resolved_tab
        if isinstance(result, dict):
            result["tabId"] = result.get("tabId", resolved_tab)
            return result
        return {"tabId": resolved_tab, "raw": result}
