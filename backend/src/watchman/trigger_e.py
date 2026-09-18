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
    """Fires Trigger E when the user sustains focused, productive work for 30+ minutes.

    Evidence-based flow detection:
    - Explicit 'focused' state ignites and advances the streak with full weight.
    - 'neutral' states (e.g. between vision cycles or quiet contemplation) preserve
      an already-active streak with partial progression (0.5x weight).
    - A session consisting solely of passive 'neutral' states without any explicit
      'focused' signals will never trigger deep-focus celebrations.
    - Negative states ('frustrated', 'coding_block') or 'idle' instantly reset the streak.
    """

    def __init__(self):
        self._elapsed_seconds: float = 0.0
        self._focused_cycles: int = 0
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle."""
        state = state_result.state

        if state == "focused":
            self._focused_cycles += 1
            self._elapsed_seconds += CYCLE_INTERVAL_SECONDS
            logger.debug(
                "DeepFocusTracker: active focus streak=%.0fs (focused_cycles=%d) threshold=%ds",
                self._elapsed_seconds, self._focused_cycles, DEEP_FOCUS_THRESHOLD_SECONDS,
            )
            # Require at least 2 explicit focused confirmations to arm
            if self._elapsed_seconds >= DEEP_FOCUS_THRESHOLD_SECONDS and self._focused_cycles >= 2:
                self._check_cooldown_and_arm()

        elif state == "neutral":
            # Neutral only advances if a focus streak was already ignited by explicit focus
            if self._focused_cycles > 0:
                self._elapsed_seconds += CYCLE_INTERVAL_SECONDS * 0.5
                logger.debug(
                    "DeepFocusTracker: neutral sustaining focus streak=%.0fs (focused_cycles=%d)",
                    self._elapsed_seconds, self._focused_cycles,
                )
                if self._elapsed_seconds >= DEEP_FOCUS_THRESHOLD_SECONDS and self._focused_cycles >= 2:
                    self._check_cooldown_and_arm()
            else:
                # Passive neutral without prior focus does not advance
                self._elapsed_seconds = 0.0
        else:
            # Frustration, coding block, or idle resets the streak
            self._elapsed_seconds = 0.0
            self._focused_cycles = 0

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
