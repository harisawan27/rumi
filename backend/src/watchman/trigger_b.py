import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from src.watchman.state_monitor import StateResult, CYCLE_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

CODING_BLOCK_THRESHOLD_SECONDS = 600  # 10 minutes
COOLDOWN_MINUTES = 30


class CodingBlockTracker:
    """Detects visual stasis (static screen) and fires Trigger B.

    Compares frame hashes across 45-second cycles. If the screen is visually
    unchanged for >= CODING_BLOCK_THRESHOLD_SECONDS, Trigger B fires.
    Tracks independently from FrustrationTracker (Trigger A).
    """

    def __init__(self):
        self._elapsed_seconds: float = 0.0
        self._last_frame_hash: Optional[str] = None
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def update_frame(self, frame_bytes: bytes) -> None:
        """Call with the raw frame bytes each cycle to track visual stasis."""
        frame_hash = hashlib.md5(frame_bytes).hexdigest()
        if self._last_frame_hash is not None and frame_hash == self._last_frame_hash:
            self._elapsed_seconds += CYCLE_INTERVAL_SECONDS
            logger.debug(
                "CodingBlockTracker: static screen elapsed=%.0fs threshold=%ds",
                self._elapsed_seconds, CODING_BLOCK_THRESHOLD_SECONDS,
            )
            if self._elapsed_seconds >= CODING_BLOCK_THRESHOLD_SECONDS:
                self._check_cooldown_and_arm()
        else:
            # Screen changed — reset counter
            self._elapsed_seconds = 0.0
        self._last_frame_hash = frame_hash

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle with the latest StateResult.

        Trigger B is frame-hash based, not state-based. This method exists
        for interface consistency with FrustrationTracker; frame-hash tracking
        is done via update_frame().
        """
        # No-op here; frame-based tracking happens in update_frame()
        pass

    def _check_cooldown_and_arm(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_fired_at is not None:
            elapsed_since = (now - self._last_fired_at).total_seconds()
            if elapsed_since < COOLDOWN_MINUTES * 60:
                logger.debug(
                    "CodingBlockTracker: cooldown active (%.0fs remaining)",
                    COOLDOWN_MINUTES * 60 - elapsed_since,
                )
                return
        self._pending_fire = True
        logger.info("CodingBlockTracker: Trigger B armed")

    def should_fire(self) -> bool:
        return self._pending_fire

    def reset_fire(self) -> None:
        """Mark the trigger as fired; reset elapsed counter and record fire time."""
        self._pending_fire = False
        self._elapsed_seconds = 0.0
        self._last_fired_at = datetime.now(timezone.utc)
        logger.info("CodingBlockTracker: Trigger B fired — cooldown started")
