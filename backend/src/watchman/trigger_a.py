import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.watchman.state_monitor import StateResult

logger = logging.getLogger(__name__)

FRUSTRATION_THRESHOLD_SECONDS = 120  # 2 minutes
COOLDOWN_MINUTES = 30


class FrustrationTracker:
    """Tracks sustained frustration posture and fires Trigger A.

    Trigger A fires when the user has been in a 'frustrated' state for
    >= FRUSTRATION_THRESHOLD_SECONDS continuously, subject to a 30-minute cooldown.
    """

    def __init__(self):
        self._elapsed_seconds: float = 0.0
        self._last_cycle_state: Optional[str] = None
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle with the latest StateResult."""
        from src.watchman.state_monitor import CYCLE_INTERVAL_SECONDS
        if state_result.state == "frustrated":
            self._elapsed_seconds += CYCLE_INTERVAL_SECONDS
            logger.debug(
                "FrustrationTracker: elapsed=%.0fs threshold=%ds",
                self._elapsed_seconds, FRUSTRATION_THRESHOLD_SECONDS,
            )
            if self._elapsed_seconds >= FRUSTRATION_THRESHOLD_SECONDS:
                self._check_cooldown_and_arm()
        else:
            self._elapsed_seconds = 0.0

    def _check_cooldown_and_arm(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_fired_at is not None:
            elapsed_since = (now - self._last_fired_at).total_seconds()
            if elapsed_since < COOLDOWN_MINUTES * 60:
                logger.debug(
                    "FrustrationTracker: cooldown active (%.0fs remaining)",
                    COOLDOWN_MINUTES * 60 - elapsed_since,
                )
                return
        self._pending_fire = True
        logger.info("FrustrationTracker: Trigger A armed")

    def should_fire(self) -> bool:
        return self._pending_fire

    def reset_fire(self) -> None:
        """Mark the trigger as fired; reset elapsed counter and record fire time."""
        self._pending_fire = False
        self._elapsed_seconds = 0.0
        self._last_fired_at = datetime.now(timezone.utc)
        logger.info("FrustrationTracker: Trigger A fired — cooldown started")
