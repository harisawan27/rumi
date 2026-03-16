import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from src.watchman.state_monitor import StateResult

logger = logging.getLogger(__name__)

_DEMO = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
SESSION_BREAK_THRESHOLD_SECONDS = 60 if _DEMO else 90 * 60
COOLDOWN_SECONDS                = 60 if _DEMO else 60 * 60


class LongSessionTracker:
    """Fires Trigger C when Haris has worked continuously for 90+ minutes.

    Pure clock-based — no MediaPipe, no API cost.
    Resets on pause/resume via reset_clock().
    """

    def __init__(self):
        self._session_start: float = time.monotonic()
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def reset_clock(self) -> None:
        """Call on session resume or after a break is taken."""
        self._session_start = time.monotonic()
        logger.info("LongSessionTracker: clock reset")

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle."""
        if state_result.state == "idle":
            # User is away — don't count idle time as working
            return

        elapsed = time.monotonic() - self._session_start
        logger.debug("LongSessionTracker: elapsed=%.0fs threshold=%ds", elapsed, SESSION_BREAK_THRESHOLD_SECONDS)

        if elapsed >= SESSION_BREAK_THRESHOLD_SECONDS:
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
        self._session_start = time.monotonic()   # reset so next reminder is 1h later
        self._last_fired_at = datetime.now(timezone.utc)
        logger.info("LongSessionTracker: Trigger C fired — clock reset")
