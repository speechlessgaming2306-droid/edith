import json
import os
import time
from datetime import datetime
from pathlib import Path

try:
    from mem0 import MemoryClient
except Exception:  # pragma: no cover - optional dependency
    MemoryClient = None


class Mem0MemoryStore:
    EXPLICIT_NOTE_PREFIX = "[Explicit note] "

    def __init__(
        self,
        api_key: str = "",
        user_id: str = "sir",
        app_id: str = "edith",
        org_id: str = "",
        project_id: str = "",
        enabled: bool = True,
    ):
        self.api_key = (api_key or "").strip()
        self.user_id = (user_id or "sir").strip() or "sir"
        self.app_id = (app_id or "edith").strip() or "edith"
        self.org_id = (org_id or "").strip()
        self.project_id = (project_id or "").strip()
        self.enabled = bool(enabled)
        self.client = None
        self.last_error = None

        if not self.enabled or not self.api_key or MemoryClient is None:
            return

        try:
            kwargs = {"api_key": self.api_key}
            if self.org_id and self.project_id:
                kwargs["org_id"] = self.org_id
                kwargs["project_id"] = self.project_id
            self.client = MemoryClient(**kwargs)
        except Exception as exc:  # pragma: no cover - network/client init variability
            self.last_error = str(exc)
            self.client = None

    @classmethod
    def from_workspace(cls, workspace_root: str | Path):
        workspace_root = Path(workspace_root)
        settings_tokens = {}
        settings_path = workspace_root / "backend" / "settings.json"
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                settings_tokens = settings.get("service_tokens") or {}
            except Exception:
                settings_tokens = {}

        api_key = (
            os.getenv("MEM0_API_KEY")
            or os.getenv("EDITH_MEM0_API_KEY")
            or settings_tokens.get("mem0_api_key")
            or ""
        )
        user_id = (
            os.getenv("MEM0_USER_ID")
            or os.getenv("EDITH_MEM0_USER_ID")
            or settings_tokens.get("mem0_user_id")
            or "sir"
        )
        app_id = (
            os.getenv("MEM0_APP_ID")
            or os.getenv("EDITH_MEM0_APP_ID")
            or settings_tokens.get("mem0_app_id")
            or "edith"
        )
        org_id = (
            os.getenv("MEM0_ORG_ID")
            or os.getenv("EDITH_MEM0_ORG_ID")
            or settings_tokens.get("mem0_org_id")
            or ""
        )
        project_id = (
            os.getenv("MEM0_PROJECT_ID")
            or os.getenv("EDITH_MEM0_PROJECT_ID")
            or settings_tokens.get("mem0_project_id")
            or ""
        )
        return cls(api_key=api_key, user_id=user_id, app_id=app_id, org_id=org_id, project_id=project_id)

    @property
    def is_enabled(self) -> bool:
        return self.client is not None

    def add_chat_message(self, sender: str, text: str):
        cleaned = str(text or "").strip()
        if not cleaned or not self.client:
            return False

        role = "assistant" if str(sender or "").strip().lower().startswith("edith") else "user"
        try:
            self.client.add(
                [{"role": role, "content": cleaned}],
                user_id=self.user_id,
                app_id=self.app_id,
                metadata={"source": "edith", "sender": str(sender or ""), "kind": "chat"},
            )
            return True
        except Exception as exc:  # pragma: no cover - network/client variability
            self.last_error = str(exc)
            return False

    def add_memory_note(self, text: str):
        cleaned = str(text or "").strip()
        if not cleaned or not self.client:
            return False

        try:
            self.client.add(
                [{"role": "user", "content": f"{self.EXPLICIT_NOTE_PREFIX}{cleaned}"}],
                user_id=self.user_id,
                app_id=self.app_id,
                metadata={"source": "edith", "kind": "explicit_note"},
            )
            return True
        except Exception as exc:  # pragma: no cover - network/client variability
            self.last_error = str(exc)
            return False

    def search(self, query: str, limit: int = 8):
        cleaned = str(query or "").strip()
        if not cleaned or not self.client:
            return []

        try:
            response = self.client.search(
                cleaned,
                filters={
                    "AND": [
                        {"user_id": self.user_id},
                        {"app_id": self.app_id},
                    ]
                },
            )
        except Exception as exc:  # pragma: no cover - network/client variability
            self.last_error = str(exc)
            return []
        return self._normalize_response_items(response, limit=limit)

    def get_recent_memories(self, limit: int = 40):
        if not self.client:
            return []

        try:
            response = self.client.get_all(
                filters={
                    "AND": [
                        {"user_id": self.user_id},
                        {"app_id": self.app_id},
                    ]
                },
                page=1,
                page_size=max(limit, 1),
            )
        except Exception as exc:  # pragma: no cover - network/client variability
            self.last_error = str(exc)
            return []

        items = self._normalize_response_items(response, limit=None)
        items.sort(key=lambda item: float(item.get("timestamp", 0) or 0), reverse=True)
        return items[:limit]

    def _normalize_response_items(self, response, limit: int | None):
        if isinstance(response, dict):
            items = response.get("results") or response.get("memories") or response.get("data") or []
        elif isinstance(response, list):
            items = response
        else:
            items = []

        normalized = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue

            text = str(
                item.get("memory")
                or item.get("text")
                or item.get("content")
                or ""
            ).strip()
            if not text:
                continue

            kind = "mem0"
            sender = "Memory"
            if text.startswith(self.EXPLICIT_NOTE_PREFIX):
                text = text[len(self.EXPLICIT_NOTE_PREFIX):].strip()
                kind = "explicit_note"
            elif isinstance(item.get("metadata"), dict) and item["metadata"].get("kind") == "explicit_note":
                kind = "explicit_note"

            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)

            normalized.append(
                {
                    "sender": sender,
                    "text": text,
                    "kind": kind,
                    "timestamp": self._coerce_timestamp(
                        item.get("updated_at") or item.get("created_at") or item.get("timestamp")
                    ),
                }
            )

            if limit and len(normalized) >= limit:
                break

        return normalized

    def _coerce_timestamp(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
        return time.time()
