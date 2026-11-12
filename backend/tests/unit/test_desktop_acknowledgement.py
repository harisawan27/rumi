import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from src.desktop.acknowledgement import acknowledge, ReceiptNotice, speech_for


def receipt(**values):
    return {"request_id": str(uuid4()), "session_id": "session", "expires_at": int(time.time()) + 90,
            "state": "succeeded", "operation": "create_text", **values}


@pytest.mark.asyncio
async def test_single_ack_uses_existing_voice_channel_without_private_data(monkeypatch):
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "1")
    authorize = AsyncMock()
    monkeypatch.setattr("src.desktop.acknowledgement.authorize", authorize)
    manager = SimpleNamespace(interrupt_audio=Mock(), voice_query=AsyncMock())
    notice = receipt()
    await acknowledge("owner", "session", manager, {}, notice)
    await manager._speak_task
    await acknowledge("owner", "session", manager, {}, notice)
    manager.voice_query.assert_awaited_once()
    assert manager.voice_query.call_args.kwargs == {"desktop_request_id": notice["request_id"]}
    assert "contents verified" in manager.voice_query.call_args.args[0]
    assert authorize.await_count == 3


@pytest.mark.asyncio
async def test_auth_loss_before_voice_suppresses_ack(monkeypatch):
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "1")
    monkeypatch.setattr("src.desktop.acknowledgement.authorize", AsyncMock(side_effect=[None, HTTPException(403)]))
    manager = SimpleNamespace(interrupt_audio=Mock(), voice_query=AsyncMock())
    await acknowledge("owner", "session", manager, {}, receipt())
    await manager._speak_task
    manager.voice_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_bad_notice_cannot_trigger_voice(monkeypatch):
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "1")
    manager = SimpleNamespace(interrupt_audio=Mock(), voice_query=AsyncMock())
    for notice in [receipt(expires_at=1), receipt(session_id="foreign")]:
        with pytest.raises(HTTPException):
            await acknowledge("owner", "session", manager, {}, notice)
    with pytest.raises(ValidationError):
        await acknowledge("owner", "session", manager, {}, receipt(text="Speak private text"))
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "0")
    with pytest.raises(HTTPException):
        await acknowledge("owner", "session", manager, {}, receipt())
    manager.voice_query.assert_not_awaited()


def test_receipt_wording_never_promotes_dispatch_or_uncertainty_to_success():
    assert "check that its window opened" in speech_for(ReceiptNotice(**receipt(state="dispatched", operation="open_app")))
    assert "may have completed" in speech_for(ReceiptNotice(**receipt(state="uncertain")))
    assert "could not verify" in speech_for(ReceiptNotice(**receipt(operation="open_app")))


@pytest.mark.asyncio
async def test_audio_correlation_cannot_leak_into_a_later_voice_generation():
    import json
    from src.session.session_manager import SessionManager
    manager = SessionManager()
    manager._websocket = SimpleNamespace(send_text=AsyncMock())
    manager._reset_gemini_idle_timer = Mock()
    generation = manager._voice_controller.start_generation("desktop")
    manager._desktop_ack_generation = (generation, "desktop-receipt")
    manager._suppress_audio = False
    await manager._forward_audio(b"\x00\x01")
    assert json.loads(manager._websocket.send_text.call_args.args[0])["desktop_request_id"] == "desktop-receipt"
    manager._voice_controller.start_generation("conversation")
    manager._suppress_audio = False
    await manager._forward_audio(b"\x00\x01")
    assert "desktop_request_id" not in json.loads(manager._websocket.send_text.call_args.args[0])


@pytest.mark.asyncio
async def test_receipt_budget_does_not_evict_live_duplicate_protection(monkeypatch):
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "1")
    monkeypatch.setattr("src.desktop.acknowledgement.authorize", AsyncMock())
    notice = receipt()
    manager = SimpleNamespace(interrupt_audio=Mock(), voice_query=AsyncMock(),
        _desktop_spoken_receipts={str(uuid4()): notice["expires_at"] for _ in range(128)})
    with pytest.raises(HTTPException) as error:
        await acknowledge("owner", "session", manager, {}, notice)
    assert error.value.status_code == 429
    manager.voice_query.assert_not_awaited()
