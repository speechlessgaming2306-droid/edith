import asyncio

import pytest

from companion_bridge import CompanionBridge


class FakeSio:
    def __init__(self):
        self.emits = []

    async def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


@pytest.mark.asyncio
async def test_companion_execute_round_trip():
    sio = FakeSio()
    bridge = CompanionBridge(sio, auth_token="secret", command_timeout=0.2)
    registration = bridge.register(
        "sid-1",
        {"token": "secret", "companion_id": "mac-1", "name": "Mac mini", "platform": "darwin"},
    )

    assert registration["ok"] is True
    task = asyncio.create_task(bridge.execute("read_clipboard", {}))
    await asyncio.sleep(0)

    assert sio.emits
    _, payload, room = sio.emits[0]
    assert room == "sid-1"
    assert payload["action"] == "read_clipboard"

    assert bridge.resolve_result({"id": payload["id"], "success": True, "result": "Clipboard contents:\nhello"}) is True
    result = await task
    assert "hello" in result


def test_companion_rejects_bad_token():
    bridge = CompanionBridge(FakeSio(), auth_token="secret")
    with pytest.raises(PermissionError):
        bridge.register("sid-1", {"token": "wrong", "companion_id": "mac-1"})
