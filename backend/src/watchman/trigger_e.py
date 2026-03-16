import logging
import os
from datetime import datetime, timezone
from typing import Optional

from src.watchman.state_monitor import StateResult, CYCLE_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

_DEMO = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
DEEP_FOCUS_THRESHOLD_SECONDS = 30          if _DEMO else 30 * 60
COOLDOWN_SECONDS             = 60          if _DEMO else 2 * 60 * 60


class DeepFocusTracker:
    """Fires Trigger E when Haris sustains focused, calm work for 30+ minutes.

    Counts consecutive cycles where state == 'neutral' (not frustrated, not idle).
    This is the *positive* trigger — Rumi celebrates productive flow states.
    """

    def __init__(self):
        self._elapsed_seconds: float = 0.0
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle."""
        if state_result.state == "neutral":
            self._elapsed_seconds += CYCLE_INTERVAL_SECONDS
            logger.debug(
                "DeepFocusTracker: focus streak=%.0fs threshold=%ds",
                self._elapsed_seconds, DEEP_FOCUS_THRESHOLD_SECONDS,
            )
            if self._elapsed_seconds >= DEEP_FOCUS_THRESHOLD_SECONDS:
                self._check_cooldown_and_arm()
        else:
            # Any frustration or idle breaks the streak
            self._elapsed_seconds = 0.0

    def _check_cooldown_and_arm(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_fired_at is not None:
            elapsed_since = (now - self._last_fired_at).total_seconds()
            if elapsed_since < COOLDOWN_SECONDS:
                return
        self._pending_fire = True
        logger.info("DeepFocusTracker: Trigger E armed")

    def should_fire(self) -> bool:
        return self._pending_fire

    def reset_fire(self) -> None:
        self._pending_fire = False
        self._elapsed_seconds = 0.0
        self._last_fired_at = datetime.now(timezone.utc)
        logger.info("DeepFocusTracker: Trigger E fired — streak reset")
