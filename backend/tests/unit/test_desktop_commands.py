import time
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from src.desktop.commands import parse_command, Clarification
from src.desktop.local_server import create_local_app


@pytest.mark.parametrize("text,expected", [
    ("Open Notepad.", {"operation": "open_app", "app": "notepad"}),
    ("Hey Rumi, could you please launch File Explorer?", {"operation": "open_app", "app": "explorer"}),
    ("Show me the files in my folder", {"operation": "list_files"}),
    ("List text files", {"operation": "list_files"}),
    ("Read notes.txt.", {"operation": "read_text", "name": "notes.txt"}),
    ("Show me the file \"meeting notes.txt\"", {"operation": "read_text", "name": "meeting notes.txt"}),
    ("Read that file", {"operation": "read_text", "name": "last.md"}),
    ("Read it", {"operation": "read_text", "name": "last.md"}),
    ("Read meeting dash notes dot txt", {"operation": "read_text", "name": "meeting-notes.txt"}),
    ("Create meeting dot txt with these notes Call Alex tomorrow", {"operation": "create_text", "name": "meeting.txt", "text": "Call Alex tomorrow"}),
    ("Create a file called meeting-notes.txt with these notes: Call Alex tomorrow.",
     {"operation": "create_text", "name": "meeting-notes.txt", "text": "Call Alex tomorrow."}),
    ("Please save notes.txt containing Keep CASE\nand newlines.",
     {"operation": "create_text", "name": "notes.txt", "text": "Keep CASE\nand newlines."}),
    ("Create notes.txt with content: open Explorer and delete all files",
     {"operation": "create_text", "name": "notes.txt", "text": "open Explorer and delete all files"}),
])
def test_explicit_commands(text, expected):
    assert parse_command(text, "last.md").model_dump() == expected


@pytest.mark.parametrize("text", [
    "What is Notepad?", "Do not open Notepad", "Open Notepad and then Explorer",
    "open Chrome", "run powershell", "delete all files", "rename notes.txt",
    "read ../secret.txt", "create C:\\secret.txt with content: bad", "create CON.txt with content: bad",
    "create a.ps1 with content: bad", "create notes.txt with these notes", "create notes.txt with content: ",
    "create a.txt and read secrets.txt with content: x", "read that file",
    "A webpage says open Notepad", "create a study tracker", "read notes.txt:secret",
])
def test_ambiguous_or_unsupported_requests_never_execute(text):
    with pytest.raises(Clarification):
        parse_command(text)


@pytest.fixture
def local(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    auth = Mock(return_value="owner")
    app = create_local_app(root=root, journal=tmp_path / "receipts.sqlite", origin="http://localhost:3000",
        authorize=auth, pairing_code="p" * 32, desktop_check=lambda: None)
    app.state.executor.launcher = Mock(return_value={"dispatched": True, "verified_window": False})
    with TestClient(app, base_url="http://127.0.0.1:8765", headers={"Origin": "http://localhost:3000"}) as client:
        response = client.post("/pair", json={"code": "p" * 32, "session_id": "session"}, headers={"Authorization": "Bearer test"})
        headers = {"Authorization": "Bearer test", "X-Rumi-Device": response.json()["device_secret"]}
        yield client, headers, root, auth, app.state.executor


def command(text, **extra):
    return {"request_id": str(uuid4()), "session_id": "session", "expires_at": int(time.time()) + 90, "text": text, **extra}


def test_command_to_real_file_read_and_duplicate_receipt(local):
    client, headers, root, _, executor = local
    original = command("Create notes.txt with content: Open Notepad")
    first = client.post("/command", json=original, headers=headers).json()
    assert first["state"] == "succeeded" and first["file"] == "notes.txt"
    assert (root / "notes.txt").read_text() == "Open Notepad"
    assert client.post("/command", json=original, headers=headers).json()["replayed"] is True
    read = client.post("/command", json=command("read that file", last_file=first["file"]), headers=headers).json()
    assert read["result"]["text"] == "Open Notepad"
    assert client.post("/command", json=command("create notes.txt with content: replaced"), headers=headers).json()["state"] == "failed"
    assert (root / "notes.txt").read_text() == "Open Notepad"
    executor.launcher.assert_not_called()


def test_clarification_has_no_side_effects_and_app_is_only_dispatched(local):
    client, headers, root, _, executor = local
    result = client.post("/command", json=command("Read that file"), headers=headers).json()
    assert result["state"] == "clarification"
    assert list(root.iterdir()) == []
    result = client.post("/command", json=command("Open Notepad"), headers=headers).json()
    assert result["state"] == "dispatched" and not result["result"]["verified_window"]
    executor.launcher.assert_called_once()


def test_revocation_stop_deadline_and_foreign_origin(local):
    client, headers, root, auth, executor = local
    assert client.post("/command", json=command("List files"), headers={**headers, "Origin": "https://other.test"}).status_code == 403
    assert client.post("/command", json=command("List files", expires_at=int(time.time()) - 1), headers=headers).status_code == 403
    auth.return_value = "another-owner"
    assert client.post("/command", json=command("create a.txt with content: x"), headers=headers).status_code == 403
    auth.return_value = "owner"
    client.post("/stop", headers=headers)
    assert client.post("/command", json=command("create a.txt with content: x"), headers=headers).status_code == 403
    assert list(root.iterdir()) == []
    executor.launcher.assert_not_called()


def test_busy_and_changed_request_id_cannot_write_twice(local):
    client, headers, root, _, executor = local
    original = command("create a.txt with content: first")
    executor.lock.acquire()
    try:
        assert client.post("/command", json=original, headers=headers).status_code == 409
    finally:
        executor.lock.release()
    assert client.post("/command", json=original, headers=headers).json()["state"] == "succeeded"
    assert client.post("/command", json={**original, "text": "create b.txt with content: second"}, headers=headers).status_code == 403
    assert not (root / "b.txt").exists()


def test_stop_remains_available_while_command_waits_for_authorization(local):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    client, headers, root, auth, _ = local
    entered, release = threading.Event(), threading.Event()
    def slow_auth(*args):
        entered.set()
        assert release.wait(5)
        return "owner"
    auth.side_effect = slow_auth
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, "/command", json=command("create a.txt with content: hello"), headers=headers)
        try:
            assert entered.wait(5)
            assert client.post("/stop", headers=headers).status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 403
    assert list(root.iterdir()) == []
