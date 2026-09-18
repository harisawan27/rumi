import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api.main import app, get_current_uid, _session_managers
from src.session.session_manager import SessionManager


@pytest.fixture
def client():
    TEST_UID = "test_user_owner_42"
    # Override auth dependency to always return our test UID
    app.dependency_overrides[get_current_uid] = lambda: TEST_UID

    # Set up a fresh SessionManager for TEST_UID
    mgr = SessionManager()
    _session_managers[TEST_UID] = mgr

    test_client = TestClient(app)
    yield test_client, mgr, TEST_UID

    # Teardown
    app.dependency_overrides.clear()
    _session_managers.pop(TEST_UID, None)


def test_guest_mode_restriction_blocks_private_endpoints(client):
    test_client, mgr, uid = client

    # Simulate guest detection locking the active session
    mgr._is_guest_mode = True
    assert mgr.is_guest_mode is True

    # 1. GET /identity should return 403
    resp = test_client.get("/identity")
    assert resp.status_code == 403
    assert "GUEST_PROTECTED" in resp.json().get("detail", "")

    # 2. PUT /identity should return 403
    resp = test_client.put("/identity", json={"name": "Attacker"})
    assert resp.status_code == 403
    assert "GUEST_PROTECTED" in resp.json().get("detail", "")

    # 3. GET /known-people should return 403
    resp = test_client.get("/known-people")
    assert resp.status_code == 403
    assert "GUEST_PROTECTED" in resp.json().get("detail", "")

    # 4. GET /session-summaries should return 403
    resp = test_client.get("/session-summaries")
    assert resp.status_code == 403
    assert "GUEST_PROTECTED" in resp.json().get("detail", "")

    # 5. GET /canvas/history should return 403
    resp = test_client.get("/canvas/history")
    assert resp.status_code == 403
    assert "GUEST_PROTECTED" in resp.json().get("detail", "")


def test_owner_mode_allows_access(client):
    test_client, mgr, uid = client

    # Owner is present, guest mode is False
    mgr._is_guest_mode = False

    with patch("src.identity.identity_loader.load_core_identity", return_value={"name": "Owner User"}):
        resp = test_client.get("/identity")
        assert resp.status_code == 200
        assert resp.json().get("name") == "Owner User"

    with patch("src.memory.known_people.get_known_people", return_value=[]):
        resp = test_client.get("/known-people")
        assert resp.status_code == 200
        assert resp.json().get("people") == []


def test_guest_mode_recovery_on_owner_return(client):
    test_client, mgr, uid = client

    # Initially in guest mode
    mgr._is_guest_mode = True
    resp = test_client.get("/identity")
    assert resp.status_code == 403

    # Owner returns (face verified)
    mgr._is_guest_mode = False
    with patch("src.identity.identity_loader.load_core_identity", return_value={"name": "Owner User"}):
        resp = test_client.get("/identity")
        assert resp.status_code == 200


def test_distributed_guest_lockout_without_local_session_manager(client):
    """Test that a second instance without an in-process SessionManager still blocks guest access."""
    test_client, mgr, uid = client

    # Simulate another worker process that has NO local SessionManager
    _session_managers.pop(uid, None)

    # Firestore presence says 'guest'
    with patch("src.session.presence_manager.presence_manager.get_presence", return_value={"mode": "guest"}):
        resp = test_client.get("/identity")
        assert resp.status_code == 403
        assert "GUEST_PROTECTED" in resp.json().get("detail", "")


def test_distributed_expired_owner_presence_blocks_access(client):
    """Test that expired owner verification blocks access even if mode is 'owner'."""
    test_client, mgr, uid = client
    _session_managers.pop(uid, None)

    from datetime import datetime, timezone, timedelta
    expired_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()

    with patch("src.session.presence_manager.presence_manager.get_presence", return_value={
        "mode": "owner",
        "owner_verified_until": expired_time,
    }):
        resp = test_client.get("/identity")
        assert resp.status_code == 403
        assert "GUEST_PROTECTED" in resp.json().get("detail", "")


def test_sensitive_endpoint_bypasses_positive_cache_on_remote_guest_write(client):
    """Test that /identity bypasses local positive cache and rejects when Firestore has guest mode."""
    test_client, mgr, uid = client

    from src.session.presence_manager import presence_manager
    from datetime import datetime, timezone, timedelta

    # Set up local cache with valid owner authorization
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(seconds=30)
    presence_manager._cache[uid] = {
        "data": {"mode": "owner", "owner_verified_until": valid_until.isoformat()},
        "cached_at": now,
        "until": valid_until,
    }

    # Verify that get_presence(uid, bypass_cache=False) would have returned owner from cache
    cached_data = presence_manager.get_presence(uid, bypass_cache=False)
    assert cached_data["mode"] == "owner"

    # But mock Firestore doc returns guest mode (written by remote instance)
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"mode": "guest", "owner_verified_until": None}

    with patch.object(presence_manager, "_get_doc_ref") as mock_ref:
        mock_ref.return_value.get.return_value = mock_snap

        # Sensitive endpoint call to /identity MUST call get_presence(uid, bypass_cache=True)
        # and therefore immediately return 403 GUEST_PROTECTED!
        resp = test_client.get("/identity")
        assert resp.status_code == 403
        assert "GUEST_PROTECTED" in resp.json().get("detail", "")
