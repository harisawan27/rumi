"""All ordinary tests are offline, even when developer credentials exist.

Install guards before test modules import production modules (including aliases).
Tests inject fake get_db/documents explicitly. No emulator tests live in this
suite; any future emulator suite must have its own isolated test entrypoint.
"""
from unittest.mock import patch


def _blocked(*args, **kwargs):
    raise RuntimeError("Live Firebase/Firestore is forbidden in offline tests; inject a fake")


_guards = []


def pytest_configure(config):
    for target in (
        "firebase_admin.initialize_app", "firebase_admin.firestore.client",
        "google.cloud.firestore_v1.client.Client.__init__",
        "google.cloud.firestore_v1.async_client.AsyncClient.__init__",
        "src.memory.firestore_client.get_db",
    ):
        guard = patch(target, side_effect=_blocked)
        guard.start()
        _guards.append(guard)


def pytest_unconfigure(config):
    for guard in reversed(_guards):
        guard.stop()
