import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from src.api import main
from src.artifacts import access


@pytest.fixture
def socket(monkeypatch):
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "1")
    uid, sid = "desktop_owner", "desktop_session"
    spoken = []
    mgr = SimpleNamespace(_uid=uid, session_id=sid, status="active", is_guest_mode=False,
        _greeting_task=None, connect_gemini=AsyncMock(), interrupt_audio=lambda reason: 1)
    async def voice(text, **kwargs):
        spoken.append((text, kwargs))
        await mgr._websocket.send_json({"type": "test_voice", "text": text, **kwargs})
    mgr.voice_query = voice
    monkeypatch.setitem(main._session_managers, uid, mgr)
    monkeypatch.setattr(main, "verify_id_token", lambda token: {"uid": uid})
    monkeypatch.setattr(main, "_load_canvas_history", lambda uid: [])
    monkeypatch.setattr(access.presence_manager, "get_presence", lambda *args, **kwargs: {
        "mode": "owner", "session_id": sid,
        "owner_verified_until": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()})
    with TestClient(main.app).websocket_connect(f"/ws/observe?session_id={sid}&token=test") as ws:
        yield ws, mgr, spoken, sid


def notice(sid, **values):
    return {"type": "desktop_result", "request_id": str(uuid4()), "session_id": sid,
            "expires_at": int(time.time()) + 90, "state": "dispatched", "operation": "open_app", **values}


def receive(ws, kind):
    for _ in range(10):
        result = ws.receive_json()
        if result["type"] == kind:
            return result
    raise AssertionError("Expected correlated response")


def test_local_receipt_reaches_existing_voice_once(socket):
    ws, _, spoken, sid = socket
    message = notice(sid)
    ws.send_json(message)
    reply = receive(ws, "test_voice")
    assert reply["desktop_request_id"] == message["request_id"]
    assert "check that its window opened" in reply["text"]
    ws.send_json(message)
    # The rejected message is a processing barrier after the duplicate.
    ws.send_json(notice(sid, file_contents="must never reach the model"))
    assert receive(ws, "error")["code"] == "DESKTOP_ACK_UNAVAILABLE"
    assert len(spoken) == 1


def test_guest_receipt_never_triggers_voice(socket):
    ws, mgr, spoken, sid = socket
    mgr.is_guest_mode = True
    ws.send_json(notice(sid))
    assert receive(ws, "error")["code"] == "DESKTOP_ACK_UNAVAILABLE"
    assert spoken == []
