import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from src.api import main
from src.artifacts import access, routes, planner
from src.artifacts.repository import MemoryArtifactRepository
from datetime import datetime, timedelta, timezone

CREATE = {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "create", "title": "Study",
          "week": "current", "subjects": [], "show_daily_graph": False}


@pytest.fixture
def socket_setup(monkeypatch):
    uid, sid = "planner_owner", "planner_session"
    monkeypatch.setenv("RUMI_CREATE_PLANNER_ENABLED", "1")
    monkeypatch.setenv("RUMI_ARTIFACTS_ENABLED", "1")
    mgr = SimpleNamespace(_uid=uid, session_id=sid, status="active", is_guest_mode=False, _greeting_task=None,
        _system_prompt="", _timezone="UTC", connect_gemini=AsyncMock(), interrupt_audio=lambda reason: 1)
    async def voice(text):
        await mgr._websocket.send_json({"type": "test_voice", "text": text})
    mgr.voice_query = voice
    monkeypatch.setitem(main._session_managers, uid, mgr)
    repo = MemoryArtifactRepository()
    monkeypatch.setattr(routes, "repository", repo)
    provider = AsyncMock(return_value=json.dumps(CREATE))
    monkeypatch.setattr(planner, "provider_for", lambda *args: provider)
    monkeypatch.setattr(main, "verify_id_token", lambda token: {"uid": uid})
    monkeypatch.setattr(main, "_load_canvas_history", lambda uid: [])
    monkeypatch.setattr(main, "_save_conversation_turn", lambda *args: None)
    monkeypatch.setattr(access.presence_manager, "get_presence", lambda *args, **kwargs: {
        "mode": "owner", "session_id": sid, "owner_verified_until": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()})
    return TestClient(main.app), mgr, repo, provider, uid, sid


def connect(setup):
    return setup[0].websocket_connect(f"/ws/observe?session_id={setup[5]}&token=test")


def until_voice(ws):
    messages = []
    while True:
        msg = ws.receive_json()
        messages.append(msg)
        if msg["type"] == "test_voice":
            return messages


def test_socket_create_progress_correlated_result_and_single_ack(socket_setup):
    rid = str(uuid4())
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": "I need to track how much I study this week", "request_id": rid})
        messages = until_voice(ws)
    result = next(m["result"] for m in messages if m["type"] == "generated_artifact")
    assert result["request_id"] == rid and result["artifact"]["state"] == {"entries": []}
    assert result["artifact"]["spec"]["subjects"] == []
    assert [m["stage"] for m in messages if m["type"] == "create_status"] == ["understanding", "creating", "saving", "ready"]
    assert messages[-1]["text"].startswith("Done")
    assert len(socket_setup[2].list(socket_setup[4])) == 1


@pytest.mark.parametrize("text", ["hello", "explain economics", "Why does spaced repetition work?", "What is a graph?"])
def test_ordinary_voice_bypasses_planner(socket_setup, text):
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": text})
        messages = until_voice(ws)
    socket_setup[3].assert_not_awaited()
    assert messages[-1]["text"] == text


@pytest.mark.parametrize("flag", ["RUMI_CREATE_PLANNER_ENABLED", "RUMI_ARTIFACTS_ENABLED"])
def test_flags_preserve_original_behavior(socket_setup, monkeypatch, flag):
    monkeypatch.delenv(flag)
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": "I need to track my study time"})
        until_voice(ws)
    socket_setup[3].assert_not_awaited()
    assert socket_setup[2].list(socket_setup[4]) == []


def test_explicit_canvas_preserves_markdown(socket_setup, monkeypatch):
    monkeypatch.setattr(main, "_flash_smart", AsyncMock(return_value={"title": "Plan", "content": "A detailed study plan for this week."}))
    monkeypatch.setattr(main, "_save_canvas_entry", AsyncMock())
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": "Put a detailed study plan on Canvas"})
        messages = until_voice(ws)
    socket_setup[3].assert_not_awaited()
    assert any(m["type"] == "text_response" and m["content_type"] == "markdown" for m in messages)


def test_profile_route_precedes_planner(socket_setup, monkeypatch):
    monkeypatch.setattr(main, "_flash_detect_tool", AsyncMock(return_value={}))
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": "Update my name and create a study tracker"})
        until_voice(ws)
    socket_setup[3].assert_not_awaited()


def test_face_and_image_paths_precede_planner(socket_setup, monkeypatch):
    monkeypatch.setattr(main, "_identify_face", AsyncMock(return_value="Recognized owner"))
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": "who am i", "image": "fake"})
        until_voice(ws)
    socket_setup[3].assert_not_awaited()


def test_new_request_cancels_late_create_before_persistence(socket_setup):
    async def slow(*args):
        await asyncio.sleep(0.1)
        return json.dumps(CREATE)
    socket_setup[3].side_effect = slow
    with connect(socket_setup) as ws:
        ws.send_json({"type": "user_text", "text": "Create a study tracker"})
        while ws.receive_json().get("stage") != "understanding":
            pass
        ws.send_json({"type": "user_text", "text": "Actually never mind"})
        until_voice(ws)
        # Socket remains alive beyond the delayed provider result.
        import time
        time.sleep(0.15)
    assert socket_setup[2].list(socket_setup[4]) == []
