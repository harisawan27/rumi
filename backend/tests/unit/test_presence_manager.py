import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from src.session.presence_manager import PresenceManager, DEFAULT_OWNER_VERIFICATION_TTL_SECONDS


@pytest.fixture
def mock_db():
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_client.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc
    with patch("src.session.presence_manager.get_db", return_value=mock_client):
        yield mock_client, mock_doc


def test_set_owner_verified_creates_correct_presence(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"
    session_id = "session_xyz"

    res = pm.set_owner_verified(uid, session_id=session_id, confidence=0.98, ttl_seconds=45)

    assert res["mode"] == "owner"
    assert res["session_id"] == session_id
    assert res["confidence"] == 0.98
    assert res["owner_verified_at"] is not None
    assert res["owner_verified_until"] is not None
    assert res["verification_method"] == "face"

    mock_doc.set.assert_called_once()
    saved = mock_doc.set.call_args[0][0]
    assert saved["mode"] == "owner"
    assert saved["confidence"] == 0.98


def test_set_guest_mode_locks_presence_and_nulls_verification(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"

    res = pm.set_guest_mode(uid, session_id="session_xyz", confidence=0.95)

    assert res["mode"] == "guest"
    assert res["owner_verified_at"] is None
    assert res["owner_verified_until"] is None

    mock_doc.set.assert_called_once()
    saved = mock_doc.set.call_args[0][0]
    assert saved["mode"] == "guest"
    assert saved["owner_verified_until"] is None


def test_session_heartbeat_does_not_extend_owner_verification(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"

    pm.record_session_heartbeat(uid, session_id="session_xyz")

    mock_doc.update.assert_called_once()
    updated_fields = mock_doc.update.call_args[0][0]
    assert "last_session_heartbeat" in updated_fields
    # Must NEVER contain owner_verified_until
    assert "owner_verified_until" not in updated_fields
    assert "owner_verified_at" not in updated_fields


def test_is_owner_authorized_rejects_when_expired(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"

    # Set up presence that expired 10 seconds ago
    now = datetime.now(timezone.utc)
    expired_until = (now - timedelta(seconds=10)).isoformat()
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {
        "mode": "owner",
        "owner_verified_until": expired_until,
    }
    mock_doc.get.return_value = mock_snap

    is_auth = pm.is_owner_authorized(uid)
    assert is_auth is False


def test_is_owner_authorized_accepts_valid_owner(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"

    now = datetime.now(timezone.utc)
    valid_until = (now + timedelta(seconds=30)).isoformat()
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {
        "mode": "owner",
        "owner_verified_until": valid_until,
    }
    mock_doc.get.return_value = mock_snap

    is_auth = pm.is_owner_authorized(uid)
    assert is_auth is True


def test_is_owner_authorized_rejects_guest_mode(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"

    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {
        "mode": "guest",
        "owner_verified_until": None,
    }
    mock_doc.get.return_value = mock_snap

    is_auth = pm.is_owner_authorized(uid)
    assert is_auth is False


def test_is_owner_authorized_fails_safe_on_missing_or_error(mock_db):
    _, mock_doc = mock_db
    pm = PresenceManager()
    uid = "user_abc_123"

    # Missing document
    mock_snap = MagicMock()
    mock_snap.exists = False
    mock_doc.get.return_value = mock_snap
    assert pm.is_owner_authorized(uid) is False

    # Firestore error
    mock_doc.get.side_effect = RuntimeError("Firestore unavailable")
    pm.clear_cache()
    assert pm.is_owner_authorized(uid) is False


def test_stale_local_owner_state_cannot_override_shared_guest():
    pm = PresenceManager()
    uid = "user_remote_lockout"

    # Local cache has old owner record
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(seconds=30)
    # Stale cache older than 2s positive TTL
    pm._cache[uid] = {
        "data": {"mode": "owner", "owner_verified_until": valid_until.isoformat()},
        "cached_at": now - timedelta(seconds=3),
        "until": valid_until,
    }

    # Meanwhile, Firestore now has guest mode written by another instance
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"mode": "guest", "owner_verified_until": None}
    mock_doc.get.return_value = mock_snap
    mock_client.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc

    with patch("src.session.presence_manager.get_db", return_value=mock_client):
        # Must re-read Firestore because positive cache TTL (2s) expired -> sees guest -> rejects!
        is_auth = pm.is_owner_authorized(uid)
        assert is_auth is False


def test_positive_cache_window_and_bypass_cache_forces_refresh():
    """Verify that bypass_cache=True forces an immediate read from Firestore even within the 2s cache window."""
    pm = PresenceManager()
    uid = "user_cache_test"

    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(seconds=30)
    # Cache positive owner record updated 0.5s ago (within 2s window)
    pm._cache[uid] = {
        "data": {"mode": "owner", "owner_verified_until": valid_until.isoformat()},
        "cached_at": now - timedelta(seconds=0.5),
        "until": valid_until,
    }

    # Firestore has changed to guest mode on another instance
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"mode": "guest", "owner_verified_until": None}
    mock_doc.get.return_value = mock_snap
    mock_client.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc

    with patch("src.session.presence_manager.get_db", return_value=mock_client):
        # Ordinary call within 2s positive cache window reads from cache (stale window)
        assert pm.is_owner_authorized(uid, bypass_cache=False) is True

        # Sensitive call with bypass_cache=True bypasses cache, sees guest mode, and rejects immediately (0s window)
        assert pm.is_owner_authorized(uid, bypass_cache=True) is False
