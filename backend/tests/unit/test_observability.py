import json
from src.utils.observability import log_structured_event


def test_log_structured_event_redacts_sensitive_keys():
    entry = log_structured_event(
        event_type="TEST_EVENT",
        uid="user_123",
        session_id="session_abc",
        embedding=[0.1, 0.2, 0.3],     # Must be redacted!
        image=b"\xff\xd8\xff\xe0...",  # Must be redacted!
        token="super_secret_jwt",      # Must be redacted!
        raw_pcm_bytes=b"pcm16...",     # Binary must be excluded
        allowed_param="clean_value",
    )

    assert "embedding" not in entry
    assert "image" not in entry
    assert "token" not in entry
    assert "raw_pcm_bytes" not in entry
    assert entry["allowed_param"] == "clean_value"
    assert entry["uid"] == "user_123"
    assert entry["session_id"] == "session_abc"


def test_log_structured_event_decision_tracing():
    # Why did Rumi speak?
    speech_entry = log_structured_event(
        event_type="INTERVENTION_TRIGGER",
        uid="user_123",
        session_id="session_abc",
        trigger_type="A",
        voice_state="GENERATING",
        voice_gen_id=4,
        presence_mode="owner",
    )
    assert speech_entry["trigger_type"] == "A"
    assert speech_entry["voice_state"] == "GENERATING"
    assert speech_entry["voice_gen_id"] == 4

    # Why did Rumi think user was owner or guest?
    identity_entry = log_structured_event(
        event_type="FACE_IDENTIFICATION",
        uid="user_123",
        face_status="OWNER",
        face_similarity=0.912345,
        face_confidence=0.912345,
        presence_mode="owner",
    )
    assert identity_entry["face_status"] == "OWNER"
    assert identity_entry["face_similarity"] == 0.912
    assert identity_entry["face_confidence"] == 0.912
