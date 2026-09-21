import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.artifacts.contracts import GeneratedArtifact, GeneratedUIEditDecision
from src.artifacts.firestore_repository import FirestoreArtifactRepository
from src.artifacts.emulator import create_emulator_client
from src.artifacts.state import StateUpdate

DATA = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/artifacts/valid_study_tracker.json").read_text())


async def check():
    await asyncio.sleep(0)


def artifact():
    return GeneratedArtifact.model_validate({**DATA, "artifact_id": str(uuid4())})


def state(a, minutes=60):
    return StateUpdate.model_validate({"request_id": str(uuid4()), "artifact_id": a.artifact_id,
        "expected_state_revision": a.state_revision,
        "edit": {"operation": "add_entry", "entry": {"id": str(uuid4()), "subject_id": "economics", "date": "2026-09-14", "minutes": minutes}}})


def spec(a, edit=None):
    return GeneratedUIEditDecision.model_validate({"mode": "generated_ui", "operation": "edit", "renderer": "study_tracker_v1",
        "artifact_id": a.artifact_id, "expected_revision": a.revision,
        "edit": edit or {"operation": "set_daily_graph_visibility", "enabled": True}})


@pytest.fixture
def repo(db):
    return FirestoreArtifactRepository(lambda: db)


@pytest.mark.asyncio
async def test_create_owner_scope_duplicate_and_server_time(repo, uid):
    a = artifact()
    saved = await repo.create_artifact(uid, a, check)
    assert saved.created_at > datetime.now(timezone.utc) - timedelta(minutes=1)
    assert saved.created_at == saved.updated_at
    assert await repo.get_artifact(uid, saved.artifact_id) == saved
    with pytest.raises(HTTPException) as duplicate:
        await repo.create_artifact(uid, a, check)
    assert duplicate.value.status_code == 409
    for owner, target in ((uid + "_foreign", a.artifact_id), (uid, str(uuid4())), (uid, "../other")):
        with pytest.raises(HTTPException) as error:
            await repo.get_artifact(owner, target)
        assert (error.value.status_code, error.value.detail) == (404, "ARTIFACT_NOT_FOUND")


@pytest.mark.asyncio
async def test_state_survives_color_and_graph_and_noop(repo, uid):
    a = await repo.create_artifact(uid, artifact(), check)
    a = await repo.update_state(uid, state(a), check)
    colored = await repo.update_spec(uid, spec(a, {"operation": "set_subject_color", "subject_id": "economics", "color_token": "red"}), check)
    graphed = await repo.update_spec(uid, spec(colored), check)
    assert graphed.state == a.state
    assert graphed.state.entries[0].minutes == 60
    assert graphed.state_revision == 1 and graphed.revision == 2
    assert graphed.artifact_id == a.artifact_id
    assert await repo.update_spec(uid, spec(graphed), check) == graphed
    new_client = create_emulator_client()
    try:
        reloaded = await FirestoreArtifactRepository(lambda: new_client).get_artifact(uid, a.artifact_id)
        assert reloaded == graphed
    finally:
        new_client.close()


def test_api_proof_update_and_clear_canvas_data(repo, db, uid, monkeypatch):
    from src.api import main
    from src.artifacts import routes, access
    from src.session.session_manager import SessionManager
    monkeypatch.setenv("RUMI_ARTIFACTS_ENABLED", "1")
    monkeypatch.setenv("RUMI_ARTIFACT_PROOF_MODE", "1")
    monkeypatch.setattr(routes, "repository", repo)
    manager = SessionManager()
    manager._uid, manager._session_id, manager._status = uid, "emulator_api_session", "active"
    monkeypatch.setitem(main._session_managers, uid, manager)
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_uid, lambda: uid)
    presence = {"mode": "owner", "session_id": manager.session_id,
        "owner_verified_until": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()}
    monkeypatch.setattr(access.presence_manager, "get_presence", lambda *args, **kwargs: presence)
    monkeypatch.setattr("src.memory.firestore_client.get_db", lambda: db)
    client = TestClient(main.app)
    def url(path):
        return f"/generated-artifacts/{path}?session_id={manager.session_id}&request_id={uuid4()}"
    created = client.post(url("proof"))
    assert created.status_code == 200
    a = GeneratedArtifact.model_validate(created.json()["result"]["artifact"])
    change = state(a).model_dump(mode="json")
    change["edit"]["entry"]["date"] = a.spec.week_start.isoformat()
    updated = client.post(url("state"), json=change)
    assert updated.status_code == 200
    graph = client.post(url("spec"), json=spec(a).model_dump(mode="json"))
    assert graph.status_code == 200
    assert graph.json()["result"]["artifact"]["state"]["entries"][0]["minutes"] == 60
    # A complete backend process reload with a new session uses the same storage.
    probe = subprocess.run([sys.executable, str(Path(__file__).with_name("restart_probe.py")), uid, a.artifact_id],
        capture_output=True, text=True, timeout=90)
    assert probe.returncode == 0, probe.stderr
    assert json.loads(probe.stdout) == graph.json()["result"]["artifact"]
    db.collection("users").document(uid).collection("canvas_history").document("legacy").set({"content": "legacy"})
    cleared = client.delete("/canvas/history")
    assert cleared.status_code == 200
    assert list(db.collection("users").document(uid).collection("artifacts").stream()) == []
    assert list(db.collection("users").document(uid).collection("canvas_history").stream()) == []
    assert client.get(url(a.artifact_id)).status_code == 404


@pytest.mark.parametrize("domain", ["state", "spec"])
@pytest.mark.asyncio
async def test_two_clients_only_one_revision_wins(repo, uid, domain):
    a = await repo.create_artifact(uid, artifact(), check)
    other_client = create_emulator_client()
    other = FirestoreArtifactRepository(lambda: other_client)
    try:
        requests = [r.update_state(uid, state(a), check) if domain == "state" else r.update_spec(uid, spec(a), check) for r in (repo, other)]
        results = await asyncio.wait_for(asyncio.gather(*requests, return_exceptions=True), 90)
        assert sum(isinstance(r, GeneratedArtifact) for r in results) == 1
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 1
        assert isinstance(failures[0], HTTPException) and failures[0].status_code == 409
        current = await repo.get_artifact(uid, a.artifact_id)
        assert (current.state_revision, current.revision) == ((1, 0) if domain == "state" else (0, 1))
    finally:
        other_client.close()


@pytest.mark.asyncio
async def test_revoked_before_commit_does_not_write(repo, uid):
    a = await repo.create_artifact(uid, artifact(), check)
    async def deny():
        raise HTTPException(403, "ARTIFACT_ACCESS_DENIED")
    with pytest.raises(HTTPException) as denied:
        await repo.update_state(uid, state(a), deny)
    assert denied.value.status_code == 403
    assert await repo.get_artifact(uid, a.artifact_id) == a


@pytest.mark.asyncio
async def test_listing_pages_and_history_trim_keep_artifacts(repo, db, uid):
    saved = [await repo.create_artifact(uid, artifact(), check) for _ in range(23)]
    first = await repo.list_artifacts(uid)
    second = await repo.list_artifacts(uid, first["next_cursor"])
    assert len(first["items"]) == 20 and len(second["items"]) == 3
    assert len({i["artifact_id"] for i in first["items"] + second["items"]}) == 23
    assert "state" not in first["items"][0] and "spec" not in first["items"][0]
    assert (await repo.list_artifacts(uid + "_foreign"))["items"] == []
    from src.api.main import _do_save_canvas_entry, _load_canvas_history
    with patch("src.memory.firestore_client.get_db", return_value=db):
        _do_save_canvas_entry(uid, "question", "legacy", "markdown", "markdown")
        history = _load_canvas_history(uid)
    assert len(history) == 20
    assert any(i.get("kind") == "generated_ui" and "content" not in i for i in history)
    for a in saved:
        assert await repo.get_artifact(uid, a.artifact_id) == a


@pytest.mark.asyncio
async def test_delete_and_paginated_clear_remove_data_and_references(repo, db, uid, monkeypatch):
    # Small page size exercises the exact multi-page production deletion loop.
    monkeypatch.setattr("src.artifacts.firestore_repository.DELETE_PAGE_SIZE", 2)
    saved = [await repo.create_artifact(uid, artifact(), check) for _ in range(5)]
    await repo.delete_artifact(uid, saved[0].artifact_id, check)
    root = db.collection("users").document(uid)
    assert not root.collection("canvas_history").document("artifact_" + saved[0].artifact_id).get().exists
    assert await repo.clear_user_artifacts(uid, check) == 4
    assert list(root.collection("artifacts").stream()) == []
    assert list(root.collection("canvas_history").stream()) == []
    assert not root.collection("artifact_control").document("state").get().to_dict()["clearing_token"]
    assert (await repo.create_artifact(uid, artifact(), check)).state.entries == ()


@pytest.mark.asyncio
async def test_partial_clear_blocks_writes_until_retried(repo, db, uid, monkeypatch):
    monkeypatch.setattr("src.artifacts.firestore_repository.DELETE_PAGE_SIZE", 1)
    a = await repo.create_artifact(uid, artifact(), check)
    calls = 0
    async def revoke():
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise HTTPException(403, "ARTIFACT_ACCESS_DENIED")
    with pytest.raises(HTTPException):
        await repo.clear_user_artifacts(uid, revoke)
    with pytest.raises(HTTPException) as blocked:
        await repo.update_state(uid, state(a), check)
    assert blocked.value.detail == "ARTIFACT_CLEAR_IN_PROGRESS"
    assert await repo.clear_user_artifacts(uid, check) == 1


@pytest.mark.parametrize("change", [{"renderer": "react"}, {"schema_version": 99}, {"uid": "foreign"}, {"artifact_id": str(uuid4())}])
@pytest.mark.asyncio
async def test_malformed_storage_never_leaves_repository(repo, db, uid, change):
    a = await repo.create_artifact(uid, artifact(), check)
    db.collection("users").document(uid).collection("artifacts").document(a.artifact_id).update(change)
    with pytest.raises(HTTPException) as error:
        await repo.get_artifact(uid, a.artifact_id)
    assert error.value.status_code == 422
    await repo.delete_artifact(uid, a.artifact_id, check)


@pytest.mark.asyncio
async def test_restarted_backend_process_new_session_reloads_same_artifact(repo, uid):
    a = await repo.create_artifact(uid, artifact(), check)
    a = await repo.update_state(uid, state(a), check)
    a = await repo.update_spec(uid, spec(a), check)
    process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).with_name("restart_probe.py")), uid, a.artifact_id,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(process.communicate(), 90)
    assert process.returncode == 0, stderr.decode()
    assert json.loads(stdout) == a.model_dump(mode="json")


@pytest.mark.asyncio
async def test_storage_failure_is_safe_without_memory_fallback(repo, uid):
    a = await repo.create_artifact(uid, artifact(), check)
    def unavailable():
        raise RuntimeError("private/path/credentials must not leak")
    failed = FirestoreArtifactRepository(unavailable)
    with pytest.raises(HTTPException) as error:
        await failed.update_state(uid, state(a), check)
    assert (error.value.status_code, error.value.detail) == (503, "ARTIFACT_STORAGE_UNAVAILABLE")
    assert (await repo.get_artifact(uid, a.artifact_id)).state_revision == 0


def test_client_rules_deny_even_matching_owner(db, uid):
    # REST bearer token with emulator's unsigned test JWT exercises client rules.
    import base64
    import urllib.request
    import urllib.error
    from src.artifacts.emulator import require_emulator, PROJECT
    def b64(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    token = b64({"alg": "none", "typ": "JWT"}) + "." + b64({"sub": uid, "user_id": uid, "aud": PROJECT, "iss": "https://securetoken.google.com/" + PROJECT,
        "iat": 1, "exp": 4102444800, "firebase": {"sign_in_provider": "custom", "identities": {}}}) + "."
    base = f"http://{require_emulator()}/v1/projects/{PROJECT}/databases/(default)/documents/users/{uid}"
    # Positive control proves this token is authenticated as the matching owner.
    allowed = urllib.request.Request(base + "/canvas_history", headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(allowed, timeout=5) as response:
        assert response.status == 200
    for collection in ("artifacts", "artifact_control"):
        for method in ("GET", "POST"):
            request = urllib.request.Request(base + "/" + collection, method=method,
                data=b'{"fields":{}}' if method == "POST" else None,
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            with pytest.raises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(request, timeout=5)
            assert denied.value.code == 403


@pytest.mark.asyncio
async def test_planner_create_subject_entries_edits_restart_and_history(repo, db, uid):
    from src.artifacts.service import plan_and_execute
    from unittest.mock import AsyncMock
    async def execute(text, plan, selected=None):
        _, result, _ = await plan_and_execute(text=text, uid=uid, session_id="planner_emulator_session",
            request_id=str(uuid4()), selected_id=selected, has_canvas=bool(selected), timezone_name="Asia/Karachi",
            repository=repo, check=check, provider=AsyncMock(return_value=json.dumps(plan)), progress=AsyncMock())
        return result.artifact
    created = await execute("I need to track how much I study this week", {
        "mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "create", "title": "Study",
        "week": "current", "subjects": [], "show_daily_graph": False})
    assert created.state.entries == () and created.spec.subjects == ()
    reference = db.collection("users").document(uid).collection("canvas_history").document("artifact_" + created.artifact_id).get().to_dict()
    assert reference["artifact_id"] == created.artifact_id and "state" not in reference
    added = await repo.update_spec(uid, spec(created, {"operation": "add_subject", "subject": {
        "id": "economics", "label": "Economics", "color_token": "gold"}}), check)
    update = state(added).model_dump(mode="json")
    update["edit"]["entry"]["date"] = added.spec.week_start.isoformat()
    entered = await repo.update_state(uid, StateUpdate.model_validate(update), check)
    colored = await execute("Make Economics red", {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "edit",
        "edit": {"operation": "set_subject_color", "subject_label": "Economics", "color_token": "red"}}, created.artifact_id)
    graphed = await execute("Add a graph showing daily study time", {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "edit",
        "edit": {"operation": "set_daily_graph_visibility", "enabled": True}}, created.artifact_id)
    assert graphed.artifact_id == entered.artifact_id and graphed.state == entered.state
    assert graphed.state_revision == 1 and graphed.revision == 3
    process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).with_name("restart_probe.py")), uid, created.artifact_id,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(process.communicate(), 90)
    assert process.returncode == 0, stderr.decode()
    assert json.loads(stdout) == graphed.model_dump(mode="json")


@pytest.mark.asyncio
async def test_planner_racing_edit_conflicts_without_rebuilding(repo, uid):
    from src.artifacts.service import plan_and_execute
    from unittest.mock import AsyncMock
    a = await repo.create_artifact(uid, artifact(), check)
    async def provider(*args):
        await repo.update_spec(uid, spec(a), check)
        return json.dumps({"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "edit",
            "edit": {"operation": "set_subject_color", "subject_label": "Economics", "color_token": "red"}})
    with pytest.raises(HTTPException) as conflict:
        await plan_and_execute(text="Make Economics red", uid=uid, session_id="planner_session", request_id=str(uuid4()),
            selected_id=a.artifact_id, has_canvas=True, timezone_name="UTC", repository=repo, check=check,
            provider=provider, progress=AsyncMock())
    assert conflict.value.status_code == 409
    assert len((await repo.list_artifacts(uid))["items"]) == 1
    assert (await repo.get_artifact(uid, a.artifact_id)).spec.subjects[0].color_token == "gold"


@pytest.mark.asyncio
async def test_persistence_latency_samples(repo, uid):
    """Storage-only benchmark; never mislabeled as browser or model latency."""
    import time
    import statistics
    writes, loads = [], []
    for _ in range(20):
        started = time.perf_counter()
        a = await repo.create_artifact(uid, artifact(), check)
        writes.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        assert await repo.get_artifact(uid, a.artifact_id) == a
        loads.append((time.perf_counter() - started) * 1000)
    def summary(values):
        return {"samples": len(values), "p50_ms": round(statistics.median(values), 3),
                "p95_ms": round(sorted(values)[18], 3)}
    print("\nPERSISTENCE_LATENCY " + json.dumps({"create": summary(writes), "load": summary(loads)}))
