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

    Tracks accumulated active working time across non-idle cycles using real
    monotonic elapsed time deltas, not theoretical cycle constants.
    Idle time (e.g. user away from desk) does not count towards working duration.
    """

    def __init__(self):
        self._active_seconds: float = 0.0
        self._last_active_timestamp: Optional[float] = None
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def reset_clock(self) -> None:
        """Call on session resume or after a break is taken."""
        self._active_seconds = 0.0
        self._last_active_timestamp = None
        logger.info("LongSessionTracker: active working clock reset")

    def get_active_seconds(self) -> float:
        """Return total accumulated active working seconds."""
        return self._active_seconds

    def update(self, state_result: StateResult, now: Optional[float] = None) -> None:
        """Called every Watchman cycle."""
        import time
        current_time = now if now is not None else time.monotonic()

        if state_result.state == "idle":
            # User is away — close the active time interval and do not accumulate
            self._last_active_timestamp = None
            return

        if self._last_active_timestamp is not None:
            delta = current_time - self._last_active_timestamp
            # Cap delta: if gap is larger than 3 nominal cycles (e.g. pause/lag/sleep),
            # count only 1 nominal cycle rather than entire offline duration
            max_active_gap = CYCLE_INTERVAL_SECONDS * 3.0
            if 0 < delta <= max_active_gap:
                self._active_seconds += delta
            elif delta > max_active_gap:
                self._active_seconds += CYCLE_INTERVAL_SECONDS
        else:
            # First active cycle after init or return from idle
            self._active_seconds += CYCLE_INTERVAL_SECONDS

        self._last_active_timestamp = current_time
        logger.debug("LongSessionTracker: active_work=%.1fs threshold=%ds", self._active_seconds, SESSION_BREAK_THRESHOLD_SECONDS)

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
