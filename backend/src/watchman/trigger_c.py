import logging
import os
from datetime import datetime, timezone
from typing import Optional

from src.watchman.state_monitor import StateResult, CYCLE_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

_DEMO = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
SESSION_BREAK_THRESHOLD_SECONDS = 60 if _DEMO else 90 * 60
COOLDOWN_SECONDS                = 60 if _DEMO else 60 * 60


class LongSessionTracker:
    """Fires Trigger C when the user has worked actively for 90+ minutes.

    Tracks accumulated active working time across non-idle cycles.
    Idle time (e.g. user away from desk) does not count towards working duration.
    """

    def __init__(self):
        self._active_seconds: float = 0.0
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def reset_clock(self) -> None:
        """Call on session resume or after a break is taken."""
        self._active_seconds = 0.0
        logger.info("LongSessionTracker: active working clock reset")

    def get_active_seconds(self) -> float:
        """Return total accumulated active working seconds."""
        return self._active_seconds

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle."""
        if state_result.state == "idle":
            # User is away — don't count idle time as working
            return

        self._active_seconds += CYCLE_INTERVAL_SECONDS
        logger.debug("LongSessionTracker: active_work=%.0fs threshold=%ds", self._active_seconds, SESSION_BREAK_THRESHOLD_SECONDS)

        if self._active_seconds >= SESSION_BREAK_THRESHOLD_SECONDS:
            self._check_cooldown_and_arm()

    def _check_cooldown_and_arm(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_fired_at is not None:
            elapsed_since = (now - self._last_fired_at).total_seconds()
            if elapsed_since < COOLDOWN_SECONDS:
                return
        self._pending_fire = True
        logger.info("LongSessionTracker: Trigger C armed")

    def should_fire(self) -> bool:
        return self._pending_fire

    def reset_fire(self) -> None:
        self._pending_fire = False
        self._active_seconds = 0.0
        self._last_fired_at = datetime.now(timezone.utc)
        logger.info("LongSessionTracker: Trigger C fired — active clock reset")
