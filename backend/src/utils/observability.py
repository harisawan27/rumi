import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("rumi.observability")

# Disallowed keys that must NEVER appear in structured logs
REDACTED_KEYS = {
    "image",
    "image_b64",
    "frame_bytes",
    "pcm_bytes",
    "audio",
    "embedding",
    "embeddings",
    "secret",
    "token",
    "password",
    "api_key",
}


def log_structured_event(
    event_type: str,
    uid: str,
    session_id: Optional[str] = None,
    watchman_state: Optional[str] = None,
    presence_mode: Optional[str] = None,
    voice_state: Optional[str] = None,
    voice_gen_id: Optional[int] = None,
    trigger_type: Optional[str] = None,
    face_status: Optional[str] = None,
    face_similarity: Optional[float] = None,
    face_confidence: Optional[float] = None,
    ws_conn_id: Optional[str] = None,
    **extra: Any,
) -> dict:
    """Emit a structured observability log entry for Rumi decision tracing.

    Allows reconstructing:
    - Why did Rumi speak? (trigger_type, voice_state, voice_gen_id)
    - Why did Rumi think this user was owner/guest? (face_status, similarity, presence_mode)
    Zero PII, zero raw images, zero audio, zero embeddings logged.
    """
    clean_extra = {}
    for k, v in extra.items():
        if k.lower() in REDACTED_KEYS:
            continue
        if isinstance(v, (bytes, bytearray)):
            continue
        if isinstance(v, (str, int, float, bool, type(None))):
            clean_extra[k] = v

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "uid": uid,
        "session_id": session_id,
        "watchman_state": watchman_state,
        "presence_mode": presence_mode,
        "voice_state": voice_state,
        "voice_gen_id": voice_gen_id,
        "trigger_type": trigger_type,
        "face_status": face_status,
        "face_similarity": round(face_similarity, 3) if face_similarity is not None else None,
        "face_confidence": round(face_confidence, 3) if face_confidence is not None else None,
        "ws_conn_id": ws_conn_id,
        **clean_extra,
    }

    # Filter None values to keep JSON compact
    compact_entry = {k: v for k, v in entry.items() if v is not None}
    logger.info("[OBSERVE] %s", json.dumps(compact_entry))
    return compact_entry
