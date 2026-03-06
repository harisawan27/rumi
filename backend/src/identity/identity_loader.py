from datetime import datetime, timezone
from src.memory.firestore_client import get_db


class IdentityNotFoundError(Exception):
    pass


def save_identity(uid: str, data: dict) -> None:
    """Create or overwrite a user's Core Identity Profile in Firestore."""
    db = get_db()
    data["user_id"] = uid
    data["last_updated"] = datetime.now(timezone.utc)
    db.collection("users").document(uid).set(data, merge=True)


def load_core_identity(uid: str) -> dict:
    """Load Core Identity Profile from Firestore for the given UID.

    Raises IdentityNotFoundError if the document does not exist.
    """
    db = get_db()
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        raise IdentityNotFoundError(f"No identity document for UID: {uid}")
    return doc.to_dict()


def load_session_summaries(uid: str, limit: int = 3) -> list:
    """Load the most recent Session Summaries for the given UID.

    Returns a list of summary dicts ordered by created_at descending.
    """
    db = get_db()
    query = (
        db.collection("users")
        .document(uid)
        .collection("session_summaries")
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )
    return [doc.to_dict() for doc in query.stream()]
