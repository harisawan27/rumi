import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from src.artifacts import telemetry
from src.artifacts.readiness import CreateReadiness
from src.artifacts.planner import create_intent, plan_output
from src.session.session_manager import SessionManager
from datetime import date


def test_telemetry_closed_metadata(caplog):
    with caplog.at_level(logging.INFO):
        token = telemetry.begin(str(uuid4()))
        try:
            telemetry.emit("create_failed", reason="conflict")
            telemetry.emit("private prompt", reason="none")
            telemetry.emit("create_failed", reason="private subject")
        finally:
            telemetry.end(token)
    rows = [r.message for r in caplog.records if r.message.startswith("rumi_create")]
    assert len(rows) == 1
    assert set(json.loads(rows[0].split(" ", 1)[1])) == {"event", "request_id", "elapsed_ms", "reason"}
    with pytest.raises(ValueError):
        telemetry.begin("private token")


@pytest.mark.asyncio
async def test_readiness_disabled_does_no_setup(monkeypatch):
    monkeypatch.setenv("RUMI_CREATE_PLANNER_ENABLED", "1")
    monkeypatch.delenv("RUMI_ARTIFACTS_ENABLED", raising=False)
    health = CreateReadiness()
    factory = AsyncMock()
    health.start(factory)
    assert health.snapshot()["status"] == "disabled"
    assert health.task is None
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_readiness_failure_does_not_raise_or_run_inference(monkeypatch):
    monkeypatch.setenv("RUMI_CREATE_PLANNER_ENABLED", "1")
    monkeypatch.setenv("RUMI_ARTIFACTS_ENABLED", "1")
    health = CreateReadiness()
    with patch("src.artifacts.planner.prepare_planner_client", new=AsyncMock(side_effect=RuntimeError("secret"))):
        health.start(object())
        await health.task
    assert health.snapshot() == {"enabled": True, "status": "degraded", "provider": "unavailable", "storage": "not_checked"}
    await health.stop()


@pytest.mark.asyncio
async def test_invalid_model_configuration_does_not_initialize(monkeypatch):
    monkeypatch.setenv("RUMI_CREATE_PLANNER_MODEL", " ")
    with patch("src.artifacts.planner.prepare_planner_client", new=AsyncMock()) as setup:
        health = CreateReadiness()
        await health.prepare(object())
        setup.assert_not_called()
        assert health.provider == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["a", "b", "c", "e"])
async def test_watchman_cannot_replace_pending_create_audio(trigger):
    mgr = SessionManager()
    mgr._create_task = asyncio.create_task(asyncio.sleep(30))
    mgr._speak_task = mgr._create_task
    mgr.voice_query = AsyncMock()
    mgr.dispatch_intervention = AsyncMock()
    with patch("src.agent.rumi_agent.generate_intervention", new=AsyncMock(return_value="synthetic")), patch("src.memory.interaction_log.log_interaction", return_value="test"):
        await getattr(mgr, "_fire_trigger_" + trigger)()
    assert mgr._speak_task is mgr._create_task
    mgr.voice_query.assert_not_called()
    mgr._create_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await mgr._create_task


@pytest.mark.parametrize("text", ["I need something where I can record how long I study every day.", "I want a place to log my studying", "Build a way to measure study time"])
def test_general_study_recording_intent(text):
    assert create_intent(text)


@pytest.mark.asyncio
async def test_ack_audio_correlation_excludes_stale_generation():
    mgr = SessionManager()
    mgr._websocket = AsyncMock()
    mgr._reset_gemini_idle_timer = lambda: None
    mgr._suppress_audio = False
    rid = str(uuid4())
    generation = mgr._voice_controller.generation_id
    mgr._create_ack_generation = (generation, rid)
    await mgr._forward_audio(b"\x00\x00")
    assert json.loads(mgr._websocket.send_text.call_args.args[0])["create_request_id"] == rid
    mgr._create_ack_generation = (generation - 1, rid)
    await mgr._forward_audio(b"\x00\x00")
    assert "create_request_id" not in json.loads(mgr._websocket.send_text.call_args.args[0])


def test_health_endpoint_reports_create_snapshot():
    from fastapi.testclient import TestClient
    from src.api.main import app
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "create" in data
    assert set(data["create"].keys()) == {"enabled", "provider", "storage", "status"}

