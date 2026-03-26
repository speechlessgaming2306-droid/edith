import asyncio
import os
import uuid
from dataclasses import dataclass, field
from typing import Any


def _truthy_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class ConnectedCompanion:
    sid: str
    companion_id: str
    name: str
    platform: str
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CompanionBridge:
    def __init__(self, sio, auth_token: str | None = None, command_timeout: float = 30.0):
        self.sio = sio
        self.auth_token = (auth_token or "").strip()
        self.command_timeout = command_timeout
        self._companions_by_sid: dict[str, ConnectedCompanion] = {}
        self._pending_results: dict[str, asyncio.Future] = {}

    def requires_companion(self) -> bool:
        return _truthy_env("EDITH_REQUIRE_COMPANION", "0")

    def has_available_companion(self) -> bool:
        return bool(self._companions_by_sid)

    def list_companions(self) -> list[dict[str, Any]]:
        return [
            {
                "companion_id": companion.companion_id,
                "name": companion.name,
                "platform": companion.platform,
                "capabilities": list(companion.capabilities),
                "metadata": dict(companion.metadata),
            }
            for companion in self._companions_by_sid.values()
        ]

    def register(self, sid: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        payload = payload or {}
        provided_token = str(payload.get("token") or "").strip()
        if self.auth_token and provided_token != self.auth_token:
            raise PermissionError("Invalid Edith companion token.")

        companion_id = str(payload.get("companion_id") or sid).strip() or sid
        companion = ConnectedCompanion(
            sid=sid,
            companion_id=companion_id,
            name=str(payload.get("name") or companion_id).strip() or companion_id,
            platform=str(payload.get("platform") or "unknown").strip() or "unknown",
            capabilities=list(payload.get("capabilities") or []),
            metadata=dict(payload.get("metadata") or {}),
        )
        self._companions_by_sid[sid] = companion
        return {
            "ok": True,
            "companion_id": companion.companion_id,
            "requires_companion": self.requires_companion(),
        }

    def unregister(self, sid: str) -> None:
        self._companions_by_sid.pop(sid, None)

    def resolve_target(self, preferred_companion_id: str | None = None) -> ConnectedCompanion | None:
        preferred = (preferred_companion_id or "").strip()
        if preferred:
            for companion in self._companions_by_sid.values():
                if companion.companion_id == preferred:
                    return companion
        return next(iter(self._companions_by_sid.values()), None)

    async def execute(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        preferred_companion_id: str | None = None,
        timeout: float | None = None,
    ) -> str:
        companion = self.resolve_target(preferred_companion_id)
        if not companion:
            raise RuntimeError("No Edith companion is connected.")

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_results[request_id] = future

        try:
            await self.sio.emit(
                "companion_action",
                {"id": request_id, "action": action, "payload": payload or {}},
                room=companion.sid,
            )
            response = await asyncio.wait_for(future, timeout=timeout or self.command_timeout)
        finally:
            self._pending_results.pop(request_id, None)

        if not response.get("success", False):
            raise RuntimeError(response.get("error") or f"Companion action '{action}' failed.")
        return str(response.get("result") or "Done.")

    def resolve_result(self, payload: dict[str, Any] | None) -> bool:
        payload = payload or {}
        request_id = str(payload.get("id") or "").strip()
        if not request_id:
            return False

        future = self._pending_results.get(request_id)
        if not future or future.done():
            return False

        future.set_result(payload)
        return True
