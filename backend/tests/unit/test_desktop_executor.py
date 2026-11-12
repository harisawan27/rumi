import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from src.desktop.contracts import ActionRequest, NamedFile
from src.desktop.executor import Executor
from src.desktop.workspace import Workspace, WorkspaceError
from src.desktop.local_server import create_local_app


def request(action=None, **values):
    return {"request_id": str(uuid4()), "session_id": "owner_session", "expires_at": int(time.time()) + 90,
            "action": action or {"operation": "create_text", "name": "note.txt", "text": "hello"}, **values}


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    auth = Mock()
    executor = Executor(Workspace(root), tmp_path / "journal.sqlite", auth)
    yield executor, root, auth
    executor.close()


@pytest.mark.parametrize("name", ["../secret.txt", "..\\secret.txt", "C:\\secret.txt", "//server/share/a.txt",
    "a.txt:secret", "CON.txt", "nul.md", "COM1.txt", "LPT9.csv", "a.txt.", "a.txt ", ".hidden.txt",
    "a.exe", "a.ps1", "a.html", "sub/a.txt", "a\x00.txt", "a..txt", "a?.txt"])
def test_unsafe_filename_rejected(name):
    with pytest.raises(ValidationError):
        NamedFile(name=name)


@pytest.mark.parametrize("extra", [{"uid": "owner"}, {"shell": "whoami"}, {"command": "calc"}, {"path": "C:/"}])
def test_no_extra_capabilities(extra):
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(request(action={"operation": "list_files", **extra}))


def test_create_read_list_and_no_overwrite(setup):
    executor, root, auth = setup
    assert executor.execute(request(), "token")["state"] == "succeeded"
    assert (root / "note.txt").read_text() == "hello"
    assert executor.execute(request(), "token")["result"]["reason"] == "already_exists"
    assert executor.execute(request({"operation": "read_text", "name": "note.txt"}), "token")["result"]["text"] == "hello"
    assert executor.execute(request({"operation": "list_files"}), "token")["result"]["names"] == ["note.txt"]
    assert auth.call_count >= 8


def test_duplicate_id_never_reexecutes_and_changed_arguments_fail(setup):
    executor, root, _ = setup
    original = request()
    executor.execute(original, "token")
    assert executor.execute(original, "token")["replayed"]
    with pytest.raises(WorkspaceError, match="request_id_reused"):
        executor.execute({**original, "action": {**original["action"], "text": "changed"}}, "token")
    assert (root / "note.txt").read_text() == "hello"


def test_restart_preserves_receipt_and_omits_file_contents(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    journal = tmp_path / "journal.sqlite"
    original = request()
    executor = Executor(Workspace(root), journal, lambda *args: None)
    executor.execute(original, "token")
    read = request({"operation": "read_text", "name": "note.txt"})
    executor.execute(read, "token")
    executor.close()
    executor = Executor(Workspace(root), journal, lambda *args: None)
    try:
        assert executor.execute(original, "token")["replayed"]
        assert "text" not in executor.execute(read, "token")["result"]
        rows = executor.db.execute("SELECT * FROM receipts").fetchall()
        assert "hello" not in json.dumps(rows)
        assert "token" not in json.dumps(rows)
    finally:
        executor.close()


def test_crashed_request_is_uncertain_never_retried(setup):
    executor, root, _ = setup
    original = request()
    fingerprint = executor.fingerprint(ActionRequest.model_validate(original))
    executor.db.execute("INSERT INTO receipts VALUES (?,?,?,?)", (original["request_id"], fingerprint, "running", "{}"))
    executor.db.commit()
    assert executor.execute(original, "token")["state"] == "uncertain"
    assert not (root / "note.txt").exists()


@pytest.mark.parametrize("offset", [-1, 200])
def test_expired_and_excessive_deadline_fail(setup, offset):
    executor, root, _ = setup
    with pytest.raises(WorkspaceError, match="expired"):
        executor.execute(request(expires_at=int(time.time()) + offset), "token")
    assert list(root.iterdir()) == []


def test_stop_and_auth_loss_prevent_write(setup):
    executor, root, auth = setup
    executor.stop()
    with pytest.raises(WorkspaceError, match="stopped"):
        executor.execute(request(), "token")
    executor.resume()
    auth.side_effect = PermissionError()
    with pytest.raises(PermissionError):
        executor.execute(request(), "token")
    assert list(root.iterdir()) == []


def test_revocation_after_commit_withholds_delivery_keeps_receipt(setup):
    executor, root, auth = setup
    auth.side_effect = [None, None, PermissionError()]
    with pytest.raises(PermissionError):
        executor.execute(request(), "token")
    assert (root / "note.txt").read_text() == "hello"
    assert executor.db.execute("SELECT state FROM receipts").fetchone()[0] == "succeeded"


def test_hardlink_is_not_read(setup, tmp_path):
    import os
    executor, root, _ = setup
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    os.link(outside, root / "link.txt")
    result = executor.execute(request({"operation": "read_text", "name": "link.txt"}), "token")
    assert result["state"] == "failed"
    assert "secret" not in json.dumps(result)


def test_busy_no_parallel_execution(setup):
    executor, _, _ = setup
    executor.lock.acquire()
    try:
        with pytest.raises(WorkspaceError, match="busy"):
            executor.execute(request(), "token")
    finally:
        executor.lock.release()


def test_app_dispatch_is_not_window_success(setup):
    executor, _, _ = setup
    executor.launcher = Mock(return_value={"dispatched": True, "verified_window": False})
    result = executor.execute(request({"operation": "open_app", "app": "notepad"}), "token")
    assert result["state"] == "dispatched"
    assert not result["result"]["verified_window"]


@pytest.fixture
def local(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    auth = Mock(return_value="owner")
    app = create_local_app(root=root, journal=tmp_path / "journal.sqlite", origin="http://localhost:3000",
                           authorize=auth, pairing_code="a" * 32, desktop_check=lambda: None)
    with TestClient(app, base_url="http://127.0.0.1:8765", headers={"Origin": "http://localhost:3000"}) as client:
        yield client, auth, root


def pair(client):
    response = client.post("/pair", json={"code": "a" * 32, "session_id": "owner_session"}, headers={"Authorization": "Bearer owner-token"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer owner-token", "X-Rumi-Device": response.json()["device_secret"]}


def test_pair_and_execute_real_temp_files(local):
    client, _, root = local
    headers = pair(client)
    assert client.post("/execute", json=request(), headers=headers).json()["state"] == "succeeded"
    assert (root / "note.txt").read_text() == "hello"
    assert client.post("/pair", json={"code": "a" * 32, "session_id": "owner_session"}, headers=headers).status_code == 403


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Host": "evil.example"}])
def test_untrusted_origin_and_rebinding_denied(local, headers):
    client, _, _ = local
    assert client.post("/pair", json={"code": "a" * 32, "session_id": "owner_session"}, headers=headers).status_code == 403


def test_credentials_pairing_and_stop(local):
    client, auth, root = local
    assert client.post("/execute", json=request()).status_code == 403
    headers = pair(client)
    auth.return_value = "different_owner"
    assert client.post("/execute", json=request(), headers=headers).status_code == 403
    auth.return_value = "owner"
    assert client.post("/stop", headers=headers).status_code == 200
    assert client.post("/execute", json=request(), headers=headers).status_code == 403
    assert list(root.iterdir()) == []


def test_body_limit(local):
    client, _, _ = local
    assert client.post("/pair", content=b"x" * 100001).status_code == 413


def test_receipt_cannot_transfer_to_another_workspace(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    journal, original = tmp_path / "journal.sqlite", request()
    executor = Executor(Workspace(first), journal, lambda *args: None)
    try:
        assert executor.execute(original, "token")["state"] == "succeeded"
    finally:
        executor.close()
    executor = Executor(Workspace(second), journal, lambda *args: None)
    try:
        with pytest.raises(WorkspaceError, match="request_id_reused"):
            executor.execute(original, "token")
        assert list(second.iterdir()) == []
    finally:
        executor.close()


def test_stop_during_authorization_prevents_write(setup):
    executor, root, auth = setup
    auth.side_effect = lambda *args: executor.stop()
    with pytest.raises(WorkspaceError, match="stopped"):
        executor.execute(request(), "token")
    assert list(root.iterdir()) == []


def test_locked_desktop_cannot_dispatch_or_write(setup):
    executor, root, _ = setup
    executor.desktop_check = Mock(side_effect=WorkspaceError("desktop_locked"))
    executor.launcher = Mock()
    for action in [None, {"operation": "open_app", "app": "notepad"}]:
        with pytest.raises(WorkspaceError, match="desktop_locked"):
            executor.execute(request(action), "token")
    executor.launcher.assert_not_called()
    assert list(root.iterdir()) == []


def test_interrupted_write_is_uncertain_and_never_repeated(setup, monkeypatch):
    executor, root, _ = setup
    def interrupted(name, text, check):
        check()
        (root / name).write_text("partial")
        raise OSError("interrupted fixture")
    writer = Mock(side_effect=interrupted)
    monkeypatch.setattr(executor.workspace, "create_text", writer)
    original = request()
    assert executor.execute(original, "token")["state"] == "uncertain"
    assert executor.execute(original, "token")["state"] == "uncertain"
    writer.assert_called_once()
    assert (root / "note.txt").read_text() == "partial"


@pytest.mark.parametrize("contents,reason", [(b"\xff", "not_utf8"), (b"a" * 64001, "file_too_large")], ids=["invalid-utf8", "oversized"])
def test_bounded_utf8_read(setup, contents, reason):
    executor, root, _ = setup
    (root / "note.txt").write_bytes(contents)
    result = executor.execute(request({"operation": "read_text", "name": "note.txt"}), "token")
    assert result["state"] == "failed"
    assert result["result"] == {"reason": reason}


def test_native_windows_junction_escape_rejected(tmp_path):
    import os
    if os.name != "nt":
        pytest.skip("Windows junction regression")
    import _winapi
    outside, link = tmp_path / "outside", tmp_path / "junction"
    outside.mkdir()
    (outside / "secret.txt").write_text("private")
    _winapi.CreateJunction(str(outside), str(link))
    try:
        with pytest.raises(WorkspaceError, match="unsafe_workspace"):
            Workspace(link)
        with pytest.raises(WorkspaceError, match="unsafe_workspace"):
            Workspace(link / ".")
        assert (outside / "secret.txt").read_text() == "private"
    finally:
        link.rmdir()


def test_pairing_attempt_budget(local):
    client, auth, _ = local
    for _ in range(5):
        assert client.post("/pair", json={"code": "b" * 32, "session_id": "owner_session"}).status_code == 403
    assert client.post("/pair", json={"code": "a" * 32, "session_id": "owner_session"}, headers={"Authorization": "Bearer token"}).status_code == 403
    auth.assert_not_called()


def test_pairing_expires(local, monkeypatch):
    client, auth, _ = local
    now = time.monotonic()
    monkeypatch.setattr("src.desktop.local_server.time.monotonic", lambda: now + 301)
    assert client.post("/pair", json={"code": "a" * 32, "session_id": "owner_session"}, headers={"Authorization": "Bearer token"}).status_code == 403
    auth.assert_not_called()


def test_invalid_pairing_characters_rejected_without_server_error(local):
    client, auth, _ = local
    assert client.post("/pair", json={"code": "\u00e9" * 32, "session_id": "owner_session"}).status_code == 422
    auth.assert_not_called()
