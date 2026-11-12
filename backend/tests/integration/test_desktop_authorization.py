from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from src.desktop.routes import create_router
from src.artifacts.access import presence_manager


@pytest.mark.parametrize("enabled,guest,presence,session,expected", [
    (False, False, "owner", "session", 404),
    (True, False, "owner", "session", 200),
    (True, True, "owner", "session", 403),
    (True, False, "guest", "session", 403),
    (True, False, "owner", "wrong", 403),
    (True, False, "expired", "session", 403),
])
def test_desktop_requires_real_session_and_fresh_presence(monkeypatch, enabled, guest, presence, session, expected):
    monkeypatch.setenv("RUMI_DESKTOP_ENABLED", "1" if enabled else "0")
    manager = SimpleNamespace(_uid="owner", session_id="session", status="active", is_guest_mode=guest)
    monkeypatch.setattr(presence_manager, "get_presence", lambda *a, **kw: {
        "mode": "owner" if presence == "expired" else presence, "session_id": "session",
        "owner_verified_until": (datetime.now(timezone.utc) + timedelta(seconds=-1 if presence == "expired" else 60)).isoformat()})
    app = FastAPI()
    app.include_router(create_router(lambda: "owner", {"owner": manager}))
    response = TestClient(app).post("/desktop/authorize", json={"session_id": session})
    assert response.status_code == expected
    if expected == 200:
        assert response.json() == {"uid": "owner", "session_id": "session"}
