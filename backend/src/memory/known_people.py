"""Firestore CRUD for the known_people subcollection.

Schema — users/{uid}/known_people/{person_id}:
    name:              str
    relationship:      str          # e.g. "brother", "colleague", "friend"
    photo_url:         str          # Firebase Storage download URL
    added_by:          "manual" | "rumi_introduction"
    status:            "verified" | "draft"
    notes:             str
    added_at:          timestamp
    last_seen:         timestamp | None
    interaction_count: int
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _col(uid: str):
    from src.memory.firestore_client import get_db
    return get_db().collection("users").document(uid).collection("known_people")


def get_known_people(uid: str) -> list[dict]:
    try:
        docs = list(_col(uid).order_by("added_at", direction="DESCENDING").stream())
        result = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            # Convert timestamps to ISO strings for JSON serialisation
            for key in ("added_at", "last_seen"):
                if d.get(key) and hasattr(d[key], "isoformat"):
                    d[key] = d[key].isoformat()
            result.append(d)
        return result
    except Exception as exc:
        logger.warning("get_known_people: %s", exc)
        return []


def add_known_person(uid: str, data: dict) -> str:
    now = datetime.now(timezone.utc)
    record = {
        "name":              data.get("name", ""),
        "relationship":      data.get("relationship", ""),
        "photo_url":         data.get("photo_url", ""),
        "added_by":          data.get("added_by", "manual"),
        "status":            "verified" if data.get("added_by", "manual") == "manual" else "draft",
        "notes":             data.get("notes", ""),
        "added_at":          now,
        "last_seen":         None,
        "interaction_count": 0,
    }
    ref = _col(uid).add(record)
    return ref[1].id


def update_known_person(uid: str, person_id: str, data: dict) -> None:
    allowed = {"name", "relationship", "photo_url", "notes", "status",
               "last_seen", "interaction_count"}
    update = {k: v for k, v in data.items() if k in allowed}
    if update:
        _col(uid).document(person_id).update(update)


def delete_known_person(uid: str, person_id: str) -> None:
    _col(uid).document(person_id).delete()


def record_known_person_interaction(uid: str, person_id: str) -> None:
    """Increment interaction_count and update last_seen. Safe to call from async context."""
    try:
        from google.cloud.firestore import Increment
        _col(uid).document(person_id).update({
            "interaction_count": Increment(1),
            "last_seen": datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning("record_known_person_interaction: %s", exc)
