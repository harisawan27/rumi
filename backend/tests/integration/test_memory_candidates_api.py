import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api.main import app, get_current_uid, _session_managers
from src.session.session_manager import SessionManager


@pytest.fixture
def test_env():
    TEST_UID = "test_memory_user_123"
    app.dependency_overrides[get_current_uid] = lambda: TEST_UID

    mgr = SessionManager()
    _session_managers[TEST_UID] = mgr

    client = TestClient(app)
    yield client, mgr, TEST_UID

    app.dependency_overrides.clear()
    _session_managers.pop(TEST_UID, None)


def test_list_memory_candidates(test_env):
    client, mgr, uid = test_env

    mock_doc = MagicMock()
    mock_doc.id = "cand_1"
    mock_doc.to_dict.return_value = {
        "field": "work_style",
        "suggested_value": "Deep work sprints late at night",
        "source_session_id": "sess_1",
        "confidence": 0.85,
        "status": "inferred",
        "created_at": "2026-09-18T20:00:00Z",
    }

    mock_db = MagicMock()
    mock_db.collection().document().collection().where().stream.return_value = [mock_doc]

    with patch("src.memory.firestore_client.get_db", return_value=mock_db):
        resp = client.get("/memory/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["id"] == "cand_1"
        assert data["candidates"][0]["field"] == "work_style"


def test_confirm_memory_candidate_success(test_env):
    client, mgr, uid = test_env

    mock_cand_snap = MagicMock()
    mock_cand_snap.exists = True
    mock_cand_snap.to_dict.return_value = {
        "field": "immediate_goal",
        "suggested_value": "Launch Product Experience v1",
    }

    mock_cand_ref = MagicMock()
    mock_cand_ref.get.return_value = mock_cand_snap

    mock_user_snap = MagicMock()
    mock_user_snap.exists = True
    mock_user_snap.to_dict.return_value = {"name": "Haris"}

    mock_user_ref = MagicMock()
    mock_user_ref.get.return_value = mock_user_snap

    mock_db = MagicMock()
    # Route collection references
    def collection_side_effect(name):
        col_mock = MagicMock()
        if name == "users":
            def doc_side_effect(doc_id):
                u_mock = MagicMock()
                u_mock.get.return_value = mock_user_snap
                u_mock.update = mock_user_ref.update
                def subcol_side_effect(sub_name):
                    sc_mock = MagicMock()
                    if sub_name == "memory_candidates":
                        sc_mock.document.return_value = mock_cand_ref
                    return sc_mock
                u_mock.collection.side_effect = subcol_side_effect
                return u_mock
            col_mock.document.side_effect = doc_side_effect
        return col_mock

    mock_db.collection.side_effect = collection_side_effect

    with patch("src.memory.firestore_client.get_db", return_value=mock_db):
        resp = client.post("/memory/candidates/cand_1/confirm")
        assert resp.status_code == 200
        assert resp.json() == {"status": "confirmed", "field": "immediate_goal"}
        mock_cand_ref.update.assert_called_once()
        mock_user_ref.update.assert_called_once()


def test_confirm_memory_candidate_rejects_malicious_field(test_env):
    client, mgr, uid = test_env

    mock_cand_snap = MagicMock()
    mock_cand_snap.exists = True
    mock_cand_snap.to_dict.return_value = {
        "field": "is_admin",  # not in ALLOWED_CANDIDATE_FIELDS
        "suggested_value": True,
    }

    mock_cand_ref = MagicMock()
    mock_cand_ref.get.return_value = mock_cand_snap

    mock_db = MagicMock()
    mock_db.collection().document().collection().document.return_value = mock_cand_ref

    with patch("src.memory.firestore_client.get_db", return_value=mock_db):
        resp = client.post("/memory/candidates/cand_hack/confirm")
        assert resp.status_code == 400
        assert "INVALID_CANDIDATE_FIELD" in resp.json()["detail"]


def test_reject_and_dismiss_memory_candidate(test_env):
    client, mgr, uid = test_env

    mock_cand_snap = MagicMock()
    mock_cand_snap.exists = True

    mock_cand_ref = MagicMock()
    mock_cand_ref.get.return_value = mock_cand_snap

    mock_db = MagicMock()
    mock_db.collection().document().collection().document.return_value = mock_cand_ref

    with patch("src.memory.firestore_client.get_db", return_value=mock_db):
        # Reject
        resp = client.post("/memory/candidates/cand_1/reject")
        assert resp.status_code == 200
        assert resp.json() == {"status": "rejected"}
        mock_cand_ref.update.assert_called_once()

        # Dismiss (delete)
        resp_del = client.delete("/memory/candidates/cand_1")
        assert resp_del.status_code == 200
        assert resp_del.json() == {"status": "deleted"}
        mock_cand_ref.delete.assert_called_once()


def test_clear_conversation_history_deletes_subcollections(test_env):
    client, mgr, uid = test_env

    # Setup mock sessions with nested turns and interactions
    mock_turn = MagicMock()
    mock_turn.reference = MagicMock()

    mock_interaction = MagicMock()
    mock_interaction.reference = MagicMock()

    mock_session = MagicMock()
    mock_session.reference = MagicMock()
    mock_session.reference.collection.side_effect = lambda col: (
        MagicMock(stream=lambda: [mock_turn]) if col == "turns"
        else MagicMock(stream=lambda: [mock_interaction])
    )

    mock_summary = MagicMock()
    mock_summary.reference = MagicMock()

    mock_db = MagicMock()
    def col_side_effect(col_name):
        c_mock = MagicMock()
        if col_name == "users":
            u_mock = MagicMock()
            def sub_side_effect(sub_col):
                sc_mock = MagicMock()
                if sub_col == "sessions":
                    sc_mock.stream.return_value = [mock_session]
                elif sub_col == "session_summaries":
                    sc_mock.stream.return_value = [mock_summary]
                return sc_mock
            u_mock.collection.side_effect = sub_side_effect
            c_mock.document.return_value = u_mock
        return c_mock

    mock_db.collection.side_effect = col_side_effect

    with patch("src.memory.firestore_client.get_db", return_value=mock_db):
        resp = client.delete("/conversation/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        # 1 turn + 1 interaction + 1 session + 1 summary = 4 deleted
        assert data["deleted_records"] == 4
        mock_turn.reference.delete.assert_called_once()
        mock_interaction.reference.delete.assert_called_once()
        mock_session.reference.delete.assert_called_once()
        mock_summary.reference.delete.assert_called_once()
