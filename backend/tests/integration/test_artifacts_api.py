import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from src.api import main
from src.artifacts import access, routes
from src.artifacts.contracts import GeneratedArtifact
from src.artifacts.repository import MemoryArtifactRepository
from src.artifacts.state import StateUpdate

UID = "owner_test"
SID = "session_test"
RID = "750e8400-e29b-41d4-a716-446655440000"
AID = "550e8400-e29b-41d4-a716-446655440000"
DATA = json.loads((Path(__file__).resolve().parents[3] / "tests/fixtures/artifacts/valid_study_tracker.json").read_text())


def owner():
    return {"mode": "owner", "session_id": SID,
            "owner_verified_until": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("RUMI_ARTIFACT_PROOF_MODE", "1")
    repository = MemoryArtifactRepository()
    repository._items[(UID, AID)] = GeneratedArtifact.model_validate(DATA)
    monkeypatch.setattr(routes, "repository", repository)
    manager = SimpleNamespace(_uid=UID, session_id=SID, status="active", is_guest_mode=False)
    monkeypatch.setitem(main._session_managers, UID, manager)
    main.app.dependency_overrides[main.get_current_uid] = lambda: UID
    with patch.object(access.presence_manager, "get_presence", return_value=owner()) as presence:
        yield TestClient(main.app), manager, presence, repository
    main.app.dependency_overrides.clear()


def url(path=AID, sid=SID):
    return f"/generated-artifacts/{path}?session_id={sid}&request_id={RID}"


def update():
    return {"artifact_id": AID, "request_id": RID, "expected_state_revision": 0,
            "edit": {"operation": "add_entry", "entry": {
                "id": "entry_1", "subject_id": "economics", "date": "2026-09-14", "minutes": 60}}}


def test_owner_read_and_history(setup):
    client, _, presence, _ = setup
    response = client.get(url())
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["result"]["artifact"]["state"] == {"entries": []}
    assert client.get(f"/generated-artifacts?session_id={SID}").json() == {"artifact_ids": [AID]}
    assert all(c.kwargs == {"bypass_cache": True} for c in presence.call_args_list)


@pytest.mark.parametrize("sid", ["foreign_session", "missing", "..", "bad/path"])
def test_session_substitution_denied(setup, sid):
    assert setup[0].get(url(sid=sid)).status_code == 403


@pytest.mark.parametrize("change", [{"_uid": "foreign"}, {"status": "ended"}, {"status": "idle"}, {"session_id": "old"}, {"is_guest_mode": True}])
def test_invalid_session_manager_denied(setup, change):
    client, manager, _, _ = setup
    for key, value in change.items():
        setattr(manager, key, value)
    assert client.get(url()).status_code == 403


def test_missing_manager_denied(setup, monkeypatch):
    monkeypatch.delitem(main._session_managers, UID)
    assert setup[0].get(url()).status_code == 403


@pytest.mark.parametrize("presence", [None, {}, {"mode": "guest"}, {"mode": "away"}, {"mode": "unknown"},
    {"mode": "owner", "session_id": SID, "owner_verified_until": "2000-01-01T00:00:00Z"},
    {"mode": "owner", "session_id": SID, "owner_verified_until": "2099-01-01T00:00:00"},
    {"mode": "owner", "session_id": "foreign", "owner_verified_until": "2099-01-01T00:00:00Z"}])
def test_presence_fails_closed(setup, presence):
    client, _, mocked, _ = setup
    mocked.return_value = presence
    assert client.get(url()).status_code == 403


def test_presence_exception_fails_closed(setup):
    setup[2].side_effect = RuntimeError("unavailable")
    assert setup[0].get(url()).status_code == 403


@pytest.mark.asyncio
async def test_presence_timeout_fails_closed(setup):
    # Close the unawaited work coroutine in a timeout mock, unlike a real wait_for.
    async def timeout(coro, **kwargs):
        coro.close()
        raise TimeoutError
    with patch.object(access.asyncio, "wait_for", side_effect=timeout):
        with pytest.raises(HTTPException):
            await access.authorize(UID, SID, main._session_managers)


def test_read_revocation_blocks_delivery(setup):
    client, _, presence, _ = setup
    presence.side_effect = [owner(), {"mode": "guest"}]
    response = client.get(url())
    assert response.status_code == 403
    assert "Economics" not in response.text


def test_write_revocation_blocks_commit(setup):
    client, _, presence, repository = setup
    presence.side_effect = [owner(), {"mode": "guest"}]
    assert client.post(url("state"), json=update()).status_code == 403
    assert repository.get(UID, AID).state.entries == ()
    assert repository.get(UID, AID).state_revision == 0


def test_post_commit_revocation_blocks_delivery(setup):
    client, _, presence, _ = setup
    presence.side_effect = [owner(), owner(), {"mode": "guest"}]
    response = client.post(url("state"), json=update())
    assert response.status_code == 403
    assert "Economics" not in response.text


@pytest.mark.parametrize("aid", ["650e8400-e29b-41d4-a716-446655440000", "not-an-id"])
def test_foreign_or_malformed_artifact_indistinguishable(setup, aid):
    client, _, _, repository = setup
    repository._items[("foreign", AID)] = repository.get(UID, AID)
    repository._items.pop((UID, AID))
    assert client.get(url(aid)).json() == {"detail": "ARTIFACT_NOT_FOUND"}
    assert client.get(url(AID)).status_code == 404


def test_add_remove_and_conflict(setup):
    client = setup[0]
    first = client.post(url("state"), json=update())
    assert first.status_code == 200
    assert first.json()["result"]["state_revision"] == 1
    assert first.json()["result"]["revision"] == 0
    assert client.post(url("state"), json=update()).status_code == 409
    body = {**update(), "expected_state_revision": 1, "edit": {"operation": "remove_entry", "entry_id": "entry_1"}}
    assert client.post(url("state"), json=body).json()["result"]["artifact"]["state"]["entries"] == []


@pytest.mark.asyncio
async def test_concurrent_cas_accepts_only_one(setup):
    repository = setup[3]
    async def check():
        await asyncio.sleep(0)
    outcomes = await asyncio.gather(*(repository.update(UID, StateUpdate.model_validate(update()), check) for _ in range(2)), return_exceptions=True)
    assert sum(isinstance(r, GeneratedArtifact) for r in outcomes) == 1
    assert [r.status_code for r in outcomes if isinstance(r, HTTPException)] == [409]


@pytest.mark.parametrize("field,value", [("minutes", 0), ("minutes", True), ("minutes", 1441), ("date", "2026-10-01"), ("subject_id", "missing")])
def test_invalid_entry_cannot_commit(setup, field, value):
    body = update()
    body["edit"]["entry"][field] = value
    assert setup[0].post(url("state"), json=body).status_code == 422
    assert setup[3].get(UID, AID).state_revision == 0


@pytest.mark.parametrize("edit", [{"operation": "set_property", "path": "state", "value": []}, {"operation": "add_entry", "state": {"entries": []}}])
def test_no_generic_state_replacement(setup, edit):
    assert setup[0].post(url("state"), json={**update(), "edit": edit}).status_code == 422


def test_spec_edit_preserves_entries_and_checks_revision(setup):
    client = setup[0]
    client.post(url("state"), json=update())
    decision = {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "edit", "artifact_id": AID,
                "expected_revision": 0, "edit": {"operation": "set_daily_graph_visibility", "enabled": True}}
    result = client.post(url("spec"), json=decision).json()["result"]
    assert result["revision"] == result["state_revision"] == 1
    assert result["artifact"]["state"]["entries"][0]["minutes"] == 60
    assert client.post(url("spec"), json=decision).status_code == 409


def test_proof_is_opt_in_and_server_owned(setup, monkeypatch):
    client = setup[0]
    result = client.post(url("proof"), json={}).json()["result"]
    assert result["artifact_id"] != AID
    assert result["artifact"]["state"]["entries"] == []
    assert result["artifact"]["source_session_id"] == SID
    monkeypatch.delenv("RUMI_ARTIFACT_PROOF_MODE")
    assert client.post(url("proof"), json={}).status_code == 404


@pytest.mark.parametrize("sid", ["foreign", "missing", ".."])
def test_socket_session_validation_precedes_attachment(setup, sid):
    client, manager, _, _ = setup
    with patch.object(main, "verify_id_token", return_value={"uid": UID}):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/ws/observe?session_id={sid}&token=test"):
                pass
    assert exc.value.code == 4003
    assert not hasattr(manager, "_websocket")


def test_socket_history_checks_before_read_and_delivery(setup):
    client, manager, presence, _ = setup
    manager.connect_gemini = AsyncMock()
    presence.side_effect = [owner(), {"mode": "guest"}]
    with patch.object(main, "verify_id_token", return_value={"uid": UID}), patch.object(main, "_load_canvas_history", return_value=[{"content": "PRIVATE"}]) as load:
        with client.websocket_connect(f"/ws/observe?session_id={SID}&token=test") as ws:
            # A follow-up forces a safe denial response after history was withheld.
            ws.send_json({"type": "user_text", "text": "continue", "is_followup": True})
            message = ws.receive_json()
            assert message["type"] == "error"
            assert "PRIVATE" not in str(message)
        load.assert_called_once()


def test_offline_suite_blocks_firebase_even_with_credentials(monkeypatch):
    import firebase_admin
    from firebase_admin import firestore
    from src.session import presence_manager
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", "production-key.json")
    for call in (firebase_admin.initialize_app, firestore.client, presence_manager.get_db):
        with pytest.raises(RuntimeError, match="forbidden"):
            call()


@pytest.mark.parametrize("change", [{"renderer": "remote_code"}, {"artifact_id": "650e8400-e29b-41d4-a716-446655440000"}])
def test_invalid_artifact_in_store_cannot_reach_transport(setup, change):
    client, _, _, repository = setup
    repository._items[(UID, AID)] = repository.get(UID, AID).model_copy(update=change)
    response = client.get(url())
    assert response.status_code == 422
    assert response.json() == {"detail": "INVALID_ARTIFACT"}


def test_canvas_generation_revocation_never_writes_or_delivers(setup):
    client, manager, presence, _ = setup
    manager.connect_gemini = AsyncMock()
    manager.interrupt_audio = lambda reason: 1
    manager._greeting_task = None
    manager._system_prompt = ""
    manager.voice_query = AsyncMock()
    async def generate(*args, **kwargs):
        presence.return_value = {"mode": "guest"}
        return {"content": "PRIVATE generated content", "title": "Private"}
    with patch.object(main, "verify_id_token", return_value={"uid": UID}), \
         patch.object(main, "_load_canvas_history", return_value=[]), \
         patch.object(main, "_flash_smart", side_effect=generate), \
         patch.object(main, "_do_save_canvas_entry") as save, \
         patch.object(main, "_save_conversation_turn") as save_turn:
        with client.websocket_connect(f"/ws/observe?session_id={SID}&token=test") as ws:
            ws.send_json({"type": "user_text", "text": "write code for a calculator"})
            assert ws.receive_json()["type"] == "audio_interrupt"
            assert ws.receive_json() == {"type": "error", "code": "ARTIFACT_ACCESS_DENIED"}
        save.assert_not_called()
        save_turn.assert_not_called()
        manager.voice_query.assert_not_called()


def test_canvas_history_second_check_blocks_private_return(setup):
    client, _, presence, _ = setup
    # Legacy guard, strict start check, strict delivery check.
    presence.side_effect = [owner(), owner(), {"mode": "guest"}]
    with patch.object(main, "_load_canvas_history", return_value=[{"content": "PRIVATE"}]):
        response = client.get("/canvas/history")
    assert response.status_code == 403
    assert "PRIVATE" not in response.text
