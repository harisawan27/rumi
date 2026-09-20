"""Narrow, fail-closed authorization for private Canvas/artifact operations."""
import asyncio
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from src.session.presence_manager import presence_manager

PRESENCE_TIMEOUT_SECONDS = 3


def require_session(uid, session_id, managers):
    manager = managers.get(uid)
    if (not isinstance(session_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id)
            or manager is None or manager._uid != uid
            or manager.session_id != session_id
            or manager.status not in ("active", "paused")):
        raise HTTPException(403, "ARTIFACT_ACCESS_DENIED")
    return manager


async def authorize(uid, session_id, managers):
    manager = require_session(uid, session_id, managers)
    try:
        if manager.is_guest_mode:
            raise ValueError("guest")
        presence = await asyncio.wait_for(
            asyncio.to_thread(presence_manager.get_presence, uid, bypass_cache=True),
            timeout=PRESENCE_TIMEOUT_SECONDS,
        )
        # Session may have ended/replaced while the lookup was in flight.
        current = require_session(uid, session_id, managers)
        if current is not manager or current.is_guest_mode:
            raise ValueError("session changed")
        if not presence or presence.get("mode") != "owner" or presence.get("session_id") != session_id:
            raise ValueError("unverified presence")
        until = datetime.fromisoformat(presence["owner_verified_until"])
        if until.tzinfo is None or until <= datetime.now(timezone.utc):
            raise ValueError("expired presence")
        return until
    except Exception as exc:
        raise HTTPException(403, "ARTIFACT_ACCESS_DENIED") from exc
