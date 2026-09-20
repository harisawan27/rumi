"""Separate opt-in localhost suite. No Admin initialization or ADC fallback."""
from unittest.mock import patch
import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import Client
from src.artifacts.emulator import PROJECT, require_emulator, create_emulator_client

_guards = []


def pytest_addoption(parser):
    parser.addoption("--run-artifact-emulator", action="store_true", default=False)


def blocked(*args, **kwargs):
    raise RuntimeError("Only the explicit anonymous localhost emulator client is allowed")


def pytest_configure(config):
    if not config.getoption("--run-artifact-emulator"):
        raise pytest.UsageError("Use run_artifact_emulator_tests.py with the localhost demo emulator")
    require_emulator()
    import socket
    host, port = require_emulator().split(":")
    try:
        with socket.create_connection((host, int(port)), timeout=2):
            pass
    except OSError as exc:
        raise pytest.UsageError("Start the localhost Firestore Emulator before running this suite") from exc
    original = Client.__init__
    def guarded(self, *args, **kwargs):
        require_emulator()
        if args or kwargs.get("project") != PROJECT or not isinstance(kwargs.get("credentials"), AnonymousCredentials) or kwargs.get("client_options"):
            blocked()
        return original(self, **kwargs)
    for target, replacement in (
        ("google.cloud.firestore_v1.client.Client.__init__", guarded),
        ("google.cloud.firestore_v1.async_client.AsyncClient.__init__", blocked),
        ("firebase_admin.initialize_app", blocked),
        ("firebase_admin.firestore.client", blocked),
        ("src.memory.firestore_client.get_db", blocked),
    ):
        guard = patch(target, new=replacement)
        guard.start()
        _guards.append(guard)


def pytest_unconfigure(config):
    for guard in reversed(_guards):
        guard.stop()


@pytest.fixture
def db():
    client = create_emulator_client()
    yield client
    client.close()


@pytest.fixture
def uid(db):
    from uuid import uuid4
    user = "test_" + uuid4().hex
    yield user
    # Only this randomly named test user; schema has no nested private state.
    root = db.collection("users").document(user)
    for collection in ("artifacts", "canvas_history", "artifact_control"):
        for doc in root.collection(collection).stream(retry=None, timeout=5):
            doc.reference.delete(retry=None, timeout=5)
