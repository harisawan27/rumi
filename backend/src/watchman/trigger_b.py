import io
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from PIL import Image

from src.watchman.state_monitor import StateResult, CYCLE_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

_DEMO = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
CODING_BLOCK_THRESHOLD_SECONDS = 20 if _DEMO else 600
COOLDOWN_MINUTES               = 1  if _DEMO else 30

# Maximum mean absolute pixel difference (0-255 scale) to consider screen unchanged.
# 3.5 allows normal JPEG re-encoding noise and tiny cursor blinks without resetting.
SIMILARITY_DIFF_THRESHOLD = 3.5
THUMBNAIL_SIZE = (64, 64)


def _extract_screen_signature(frame_bytes: bytes) -> Optional[np.ndarray]:
    if not frame_bytes:
        return None
    try:
        with Image.open(io.BytesIO(frame_bytes)) as img:
            gray = img.convert("L").resize(THUMBNAIL_SIZE, Image.Resampling.BILINEAR)
            return np.asarray(gray, dtype=np.float32)
    except Exception as exc:
        logger.debug("CodingBlockTracker: failed to decode frame: %s", exc)
        return None


class CodingBlockTracker:
    """Detects visual stasis (static screen) and fires Trigger B.

    Compares screen frame signatures across observation cycles using a normalized
    grayscale difference metric. If the screen is visually unchanged for >= CODING_BLOCK_THRESHOLD_SECONDS,
    Trigger B fires.
    """

    def __init__(self):
        self._elapsed_seconds: float = 0.0
        self._last_frame_sig: Optional[np.ndarray] = None
        self._last_fired_at: Optional[datetime] = None
        self._pending_fire: bool = False

    def update_frame(self, frame_bytes: bytes) -> None:
        """Call with the raw screen frame bytes each cycle to track visual stasis."""
        if not frame_bytes:
            return

        sig = _extract_screen_signature(frame_bytes)
        if sig is None:
            return

        if self._last_frame_sig is not None:
            diff = float(np.mean(np.abs(sig - self._last_frame_sig)))
            if diff <= SIMILARITY_DIFF_THRESHOLD:
                self._elapsed_seconds += CYCLE_INTERVAL_SECONDS
                logger.debug(
                    "CodingBlockTracker: static screen elapsed=%.0fs diff=%.2f threshold=%ds",
                    self._elapsed_seconds, diff, CODING_BLOCK_THRESHOLD_SECONDS,
                )
                if self._elapsed_seconds >= CODING_BLOCK_THRESHOLD_SECONDS:
                    self._check_cooldown_and_arm()
            else:
                # Meaningful screen change detected — reset counter
                self._elapsed_seconds = 0.0
        self._last_frame_sig = sig

    def update(self, state_result: StateResult) -> None:
        """Called every Watchman cycle with the latest StateResult.

        Trigger B is visual stasis-based; tracking happens in update_frame().
        """
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
