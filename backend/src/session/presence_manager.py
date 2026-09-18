import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.memory.firestore_client import get_db

logger = logging.getLogger(__name__)

# Default verification TTL: owner must be re-verified by face at least once every 45s
DEFAULT_OWNER_VERIFICATION_TTL_SECONDS = int(os.getenv("OWNER_VERIFICATION_TTL_SECONDS", "45"))

# Cache settings:
# - Negative states (guest, unknown) can be cached for up to 5s.
# - Positive OWNER authorization is only cached for 2s max to discover remote guest lockouts rapidly.
POSITIVE_CACHE_TTL_SECONDS = 2.0
NEGATIVE_CACHE_TTL_SECONDS = 5.0

INSTANCE_ID = os.getenv("INSTANCE_ID", str(uuid.uuid4())[:8])


class PresenceManager:
    """Manages ephemeral presence state across multiple backend instances using Firestore.

    Authoritative path: users/{uid}/presence/current

    Invariants:
    1. Only successful fresh face verification extends `owner_verified_until`.
    2. Session heartbeats update `last_session_heartbeat` ONLY and never extend owner authorization.
    3. Missing, unverified, or expired presence fails safe to UNAUTHORIZED (returns False).
    4. Local guest detection writes guest mode immediately and clears local owner cache.
    5. Positive owner state is cached for at most 2 seconds; stale local owner state never overrides
       shared guest mode in Firestore.
    """

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def _get_doc_ref(self, uid: str):
        db = get_db()
        return db.collection("users").document(uid).collection("presence").document("current")

    def set_owner_verified(
        self,
        uid: str,
        session_id: Optional[str] = None,
        confidence: float = 1.0,
        ttl_seconds: int = DEFAULT_OWNER_VERIFICATION_TTL_SECONDS,
        verification_method: str = "face",
    ) -> dict:
        """Mark owner presence verified for ttl_seconds from now."""
        now = datetime.now(timezone.utc)
        until = now + timedelta(seconds=ttl_seconds)

        payload = {
            "mode": "owner",
            "session_id": session_id,
            "owner_verified_at": now.isoformat(),
            "owner_verified_until": until.isoformat(),
            "last_session_heartbeat": now.isoformat(),
            "instance_id": INSTANCE_ID,
            "verification_method": verification_method,
            "confidence": round(float(confidence), 3),
            "updated_at": now.isoformat(),
        }

        try:
            self._get_doc_ref(uid).set(payload)
            self._cache[uid] = {
                "data": payload,
                "cached_at": now,
                "until": until,
            }
            logger.info("PresenceManager: owner verified for %s until %s (instance=%s)",
                        uid, until.isoformat(), INSTANCE_ID)
        except Exception as exc:
            logger.warning("PresenceManager: set_owner_verified failed for %s: %s", uid, exc)

        return payload

    def set_guest_mode(
        self,
        uid: str,
        session_id: Optional[str] = None,
        confidence: float = 1.0,
    ) -> dict:
        """Lock presence into guest mode immediately across instances."""
        now = datetime.now(timezone.utc)
        payload = {
            "mode": "guest",
            "session_id": session_id,
            "owner_verified_at": None,
            "owner_verified_until": None,
            "last_session_heartbeat": now.isoformat(),
            "instance_id": INSTANCE_ID,
            "verification_method": "face",
            "confidence": round(float(confidence), 3),
            "updated_at": now.isoformat(),
        }

        try:
            self._get_doc_ref(uid).set(payload)
            self._cache[uid] = {
                "data": payload,
                "cached_at": now,
                "until": None,
            }
            logger.info("PresenceManager: guest mode set for %s (instance=%s)", uid, INSTANCE_ID)
        except Exception as exc:
            logger.warning("PresenceManager: set_guest_mode failed for %s: %s", uid, exc)

        return payload

    def set_away_mode(self, uid: str, session_id: Optional[str] = None) -> dict:
        """Mark user as away — invalidates owner verification."""
        now = datetime.now(timezone.utc)
        payload = {
            "mode": "away",
            "session_id": session_id,
            "owner_verified_at": None,
            "owner_verified_until": None,
            "last_session_heartbeat": now.isoformat(),
            "instance_id": INSTANCE_ID,
            "verification_method": "none",
            "confidence": 0.0,
            "updated_at": now.isoformat(),
        }

        try:
            self._get_doc_ref(uid).set(payload)
            self._cache[uid] = {
                "data": payload,
                "cached_at": now,
                "until": None,
            }
            logger.info("PresenceManager: away mode set for %s", uid)
        except Exception as exc:
            logger.warning("PresenceManager: set_away_mode failed for %s: %s", uid, exc)

        return payload

    def record_session_heartbeat(self, uid: str, session_id: Optional[str] = None) -> None:
        """Record a session keepalive ping.
        CRITICAL: Never updates or extends owner_verified_until.
        """
        now = datetime.now(timezone.utc)
        try:
            ref = self._get_doc_ref(uid)
            ref.update({
                "last_session_heartbeat": now.isoformat(),
                "session_id": session_id,
            })
        except Exception:
            pass

    def end_session(self, uid: str, session_id: Optional[str] = None) -> None:
        """Clean up presence on session end."""
        self.set_away_mode(uid, session_id)
        self._cache.pop(uid, None)

    def get_presence(self, uid: str, bypass_cache: bool = False) -> Optional[dict]:
        """Fetch raw presence document for uid, with short local cache.

        If bypass_cache is True, ignores the positive owner cache to guarantee reading
        the most up-to-date distributed state from Firestore (e.g. for sensitive routes).
        """
        now = datetime.now(timezone.utc)
        if not bypass_cache:
            cached = self._cache.get(uid)
            if cached:
                cached_at = cached.get("cached_at")
                mode = cached.get("data", {}).get("mode")
                max_age = POSITIVE_CACHE_TTL_SECONDS if mode == "owner" else NEGATIVE_CACHE_TTL_SECONDS
                if cached_at and (now - cached_at).total_seconds() < max_age:
                    return cached.get("data")

        try:
            doc = self._get_doc_ref(uid).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            until = None
            until_str = data.get("owner_verified_until")
            if until_str:
                try:
                    until = datetime.fromisoformat(until_str)
                except Exception:
                    until = None

            self._cache[uid] = {
                "data": data,
                "cached_at": now,
                "until": until,
            }
            return data
        except Exception as exc:
            logger.warning("PresenceManager: get_presence failed for %s: %s", uid, exc)
            return None

    def is_owner_authorized(
        self,
        uid: str,
        local_guest_mode: bool = False,
        bypass_cache: bool = False,
    ) -> bool:
        """Determine if caller has verified owner authorization.

        Security checks:
        1. If local session is marked as guest -> immediately False (0ms).
        2. If bypass_cache is True, bypasses positive owner cache and reads directly from Firestore.
        3. If mode != 'owner' -> False.
        4. If now > owner_verified_until -> False (expired verification).
        5. Any error / missing record -> False (fail-safe).
        """
        if local_guest_mode:
            return False

        now = datetime.now(timezone.utc)

        if not bypass_cache:
            # Fast cache check
            cached = self._cache.get(uid)
            if cached:
                mode = cached.get("data", {}).get("mode")
                cached_at = cached.get("cached_at")
                # If cached as negative (guest/away/unknown) within 5 seconds, reject fast
                if mode != "owner" and cached_at and (now - cached_at).total_seconds() < NEGATIVE_CACHE_TTL_SECONDS:
                    return False
                # If cached as owner within 2 seconds, check expiry
                if mode == "owner" and cached_at and (now - cached_at).total_seconds() < POSITIVE_CACHE_TTL_SECONDS:
                    until = cached.get("until")
                    if until and now <= until:
                        return True

        # Consult distributed Firestore document
        data = self.get_presence(uid, bypass_cache=bypass_cache)
        if not data:
            return False

        mode = data.get("mode")
        if mode != "owner":
            return False

        until_str = data.get("owner_verified_until")
        if not until_str:
            return False

        try:
            until = datetime.fromisoformat(until_str)
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            return now <= until
        except Exception:
            return False

    def clear_cache(self, uid: Optional[str] = None) -> None:
        """Clear local in-process cache."""
        if uid:
            self._cache.pop(uid, None)
        else:
            self._cache.clear()


# Global singleton instance
presence_manager = PresenceManager()
