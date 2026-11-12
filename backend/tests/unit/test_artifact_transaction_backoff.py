from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from src.artifacts.firestore_repository import FirestoreArtifactRepository


def fixtures(monkeypatch):
    db = Mock()
    db.transaction.return_value.write_results = []
    db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {}
    events = []
    monkeypatch.setattr("src.artifacts.firestore_repository.random.uniform", lambda *args: 0.1)
    monkeypatch.setattr("src.artifacts.firestore_repository.time.sleep", lambda delay: events.append(("delay", delay)))
    def retry_after_aborted_commit(callback):
        # Emulate the SDK entering the callback again after a confirmed abort.
        def run(tx):
            callback(tx)
            return callback(tx)
        return run
    monkeypatch.setattr("src.artifacts.firestore_repository.firestore.transactional", retry_after_aborted_commit)
    return db, events


def test_retry_delays_before_read_locks_and_rechecks_authorization(monkeypatch):
    db, events = fixtures(monkeypatch)
    control = db.collection.return_value.document.return_value.collection.return_value.document.return_value
    control.get.side_effect = lambda **kwargs: events.append("read") or Mock(to_dict=lambda: {})
    check = lambda: events.append("authorize")
    result = FirestoreArtifactRepository()._transaction(db, "owner", check, lambda *args: "saved")
    assert result == "saved"
    assert events == ["read", "authorize", "authorize", ("delay", 0.1), "read", "authorize"]
    db.transaction.assert_called_once_with(max_attempts=5)


def test_revoked_retry_stops_before_delay_and_new_reads(monkeypatch):
    db, events = fixtures(monkeypatch)
    check = Mock(side_effect=[None, HTTPException(403, "ARTIFACT_ACCESS_DENIED")])
    operation = Mock(return_value="saved")
    with pytest.raises(HTTPException) as error:
        FirestoreArtifactRepository()._transaction(db, "owner", check, operation)
    assert error.value.status_code == 403
    operation.assert_called_once()
    assert events == []
