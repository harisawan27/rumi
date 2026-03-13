import logging
from datetime import datetime, timezone

from src.memory.firestore_client import get_db

logger = logging.getLogger(__name__)


def log_interaction(
    uid: str,
    session_id: str,
    trigger_type: str,
    intervention_text: str,
    user_response: str = "no_response",
    response_at: datetime | None = None,
) -> str:
    """Write an Interaction Summary to Firestore.

    Returns the interaction_id of the created document.
    Also appends the interaction_id to the parent session document's
    interaction_ids array.

    Privacy: this function MUST NOT be called with raw video or audio data.
    Only the inferred trigger_type label and text are stored.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "session_id": session_id,
        "trigger_type": trigger_type,
        "triggered_at": now,
        "intervention_text": intervention_text,
        "user_response": user_response,
        "response_at": response_at,
    }
    # Write interaction document
    _, ref = (
        db.collection("users")
        .document(uid)
        .collection("sessions")
        .document(session_id)
        .collection("interactions")
        .add(doc)
    )
    interaction_id = ref.id
    ref.update({"interaction_id": interaction_id})

    # Append to parent session's interaction_ids array
    from google.cloud.firestore import ArrayUnion
    db.collection("users").document(uid).collection("sessions").document(
        session_id
    ).update({"interaction_ids": ArrayUnion([interaction_id])})

    logger.info(
        "interaction_log: logged interaction %s (trigger=%s, session=%s)",
        interaction_id, trigger_type, session_id,
    )
    return interaction_id
