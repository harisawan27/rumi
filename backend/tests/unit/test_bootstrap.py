import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api.main import app, get_current_uid, _session_managers
from src.session.session_manager import SessionManager
from src.identity.identity_loader import IdentityNotFoundError
from src.auth.firebase_auth import AuthError


@pytest.fixture
def test_setup():
    test_uid = "test_user_owner_bootstrap"
    app.dependency_overrides[get_current_uid] = lambda: test_uid
    mgr = SessionManager()
    _session_managers[test_uid] = mgr
    client = TestClient(app)

    yield client, mgr, test_uid

    app.dependency_overrides.clear()
    _session_managers.pop(test_uid, None)


def test_bootstrap_with_existing_identity(test_setup):
    client, mgr, uid = test_setup

    with patch("src.identity.identity_loader.load_core_identity", return_value={"name": "Alice"}):
        resp = client.get("/bootstrap")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"has_identity": True, "name": "Alice"}


def test_bootstrap_without_identity(test_setup):
    client, mgr, uid = test_setup

    with patch("src.identity.identity_loader.load_core_identity", side_effect=IdentityNotFoundError("no identity")):
        resp = client.get("/bootstrap")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"has_identity": False, "name": ""}


def test_bootstrap_firestore_unavailable(test_setup):
    client, mgr, uid = test_setup

    with patch("src.identity.identity_loader.load_core_identity", side_effect=RuntimeError("Firestore down")):
        resp = client.get("/bootstrap")
        assert resp.status_code == 503
        assert resp.json().get("detail") == "FIRESTORE_UNAVAILABLE"


def test_bootstrap_does_not_require_presence(test_setup):
    """Verify that /bootstrap succeeds even when session is in guest mode or presence is unverified,
    whereas /identity is blocked with 403 GUEST_PROTECTED under the exact same state."""
    client, mgr, uid = test_setup

    # Lock session into guest mode / away
    mgr._is_guest_mode = True

    # 1. /identity must be blocked by guest mode restriction
    resp_identity = client.get("/identity")
    assert resp_identity.status_code == 403
    assert "GUEST_PROTECTED" in resp_identity.json().get("detail", "")

    # 2. /bootstrap must NOT be blocked by guest mode restriction
    with patch("src.identity.identity_loader.load_core_identity", return_value={"name": "Alice"}):
        resp_bootstrap = client.get("/bootstrap")
        assert resp_bootstrap.status_code == 200
        assert resp_bootstrap.json() == {"has_identity": True, "name": "Alice"}


def test_bootstrap_auth_failure():
    """Verify standard auth error behaviors without dependency overrides."""
    client = TestClient(app)

    # Missing Authorization header
    resp = client.get("/bootstrap")
    assert resp.status_code == 422

    # Invalid Bearer token
    with patch("src.api.main.verify_id_token", side_effect=AuthError("INVALID_TOKEN")):
        resp = client.get("/bootstrap", headers={"Authorization": "Bearer invalid-token"})
        assert resp.status_code == 401
        assert resp.json().get("detail") == "INVALID_TOKEN"

    # Unauthorized user
    with patch("src.api.main.verify_id_token", side_effect=AuthError("UNAUTHORISED_USER")):
        resp = client.get("/bootstrap", headers={"Authorization": "Bearer rogue-token"})
        assert resp.status_code == 403
        assert resp.json().get("detail") == "UNAUTHORISED_USER"
