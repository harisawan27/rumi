import io
import time
from datetime import datetime, timezone
import pytest
from PIL import Image

from src.watchman.state_monitor import StateResult
from src.watchman.trigger_b import CodingBlockTracker
from src.watchman.trigger_c import LongSessionTracker
from src.watchman.trigger_e import DeepFocusTracker


def _create_test_image_bytes(color=(100, 100, 100), size=(64, 64), noise=0) -> bytes:
    """Helper to generate JPEG bytes with optional tiny noise."""
    img = Image.new("RGB", size, color)
    if noise > 0:
        pixels = img.load()
        for i in range(min(noise, size[0])):
            r, g, b = pixels[i, 0]
            pixels[i, 0] = (r + 1, g, b)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Trigger B: CodingBlockTracker Tests
# ---------------------------------------------------------------------------

def test_coding_block_identical_frames():
    tracker = CodingBlockTracker()
    img1 = _create_test_image_bytes((120, 120, 120))
    # First update establishes baseline
    tracker.update_frame(img1)
    assert tracker._elapsed_seconds == 0.0

    # Second update with identical bytes
    tracker.update_frame(img1)
    assert tracker._elapsed_seconds > 0.0


def test_coding_block_resilient_to_tiny_noise():
    """Tiny compression noise between frames should still be recognized as the same screen."""
    tracker = CodingBlockTracker()
    img1 = _create_test_image_bytes((120, 120, 120), noise=0)
    img2 = _create_test_image_bytes((120, 120, 120), noise=2)

    tracker.update_frame(img1)
    tracker.update_frame(img2)
    assert tracker._elapsed_seconds > 0.0, "Screen with tiny noise should be considered visually static"


def test_coding_block_resets_on_meaningful_change():
    tracker = CodingBlockTracker()
    img1 = _create_test_image_bytes((50, 50, 50))
    img2 = _create_test_image_bytes((220, 220, 220))

    tracker.update_frame(img1)
    tracker.update_frame(img1)
    assert tracker._elapsed_seconds > 0.0

    # Meaningful change: screen content changed
    tracker.update_frame(img2)
    assert tracker._elapsed_seconds == 0.0, "Meaningful change must reset elapsed seconds"


def test_coding_block_no_frame_noop():
    tracker = CodingBlockTracker()
    tracker.update_frame(b"")
    assert tracker._elapsed_seconds == 0.0


# ---------------------------------------------------------------------------
# Trigger E: DeepFocusTracker Tests
# ---------------------------------------------------------------------------

def test_deep_focus_accumulates_on_focused():
    tracker = DeepFocusTracker()
    res_focused = StateResult(state="focused", confidence=0.8)

    tracker.update(res_focused)
    assert tracker._elapsed_seconds > 0.0, "Focused state MUST ignite and accumulate deep focus streak"
    assert tracker._focused_cycles == 1


def test_deep_focus_passive_neutral_alone_does_not_accumulate():
    tracker = DeepFocusTracker()
    res_neutral = StateResult(state="neutral", confidence=0.7)

    # Passive neutral without any prior focus state
    for _ in range(5):
        tracker.update(res_neutral)

    assert tracker._elapsed_seconds == 0.0, "Passive neutral alone must NEVER start a deep focus streak"
    assert tracker._focused_cycles == 0


def test_deep_focus_neutral_progresses_active_streak():
    tracker = DeepFocusTracker()
    # 1. Ignited by focused state
    tracker.update(StateResult(state="focused", confidence=0.9))
    time_after_focus = tracker._elapsed_seconds
    assert time_after_focus > 0.0

    # 2. Subsequent neutral state sustains and progresses with partial weight
    tracker.update(StateResult(state="neutral", confidence=0.8))
    assert tracker._elapsed_seconds > time_after_focus
    # Partial weight (0.5x of 5s = 2.5s)
    assert tracker._elapsed_seconds == time_after_focus + 2.5


def test_deep_focus_resets_on_frustration_or_idle():
    tracker = DeepFocusTracker()
    tracker.update(StateResult(state="focused", confidence=0.9))
    assert tracker._elapsed_seconds > 0.0

    # Frustration breaks focus streak
    tracker.update(StateResult(state="frustrated", confidence=0.85))
    assert tracker._elapsed_seconds == 0.0
    assert tracker._focused_cycles == 0

    tracker.update(StateResult(state="focused", confidence=0.9))
    assert tracker._elapsed_seconds > 0.0

    # Idle breaks focus streak
    tracker.update(StateResult(state="idle", confidence=0.9))
    assert tracker._elapsed_seconds == 0.0
    assert tracker._focused_cycles == 0


# ---------------------------------------------------------------------------
# Trigger C: LongSessionTracker Tests
# ---------------------------------------------------------------------------

def test_long_session_monotonic_delta_tracking():
    tracker = LongSessionTracker()

    # 1. First cycle at t=100.0 (baseline)
    tracker.update(StateResult(state="focused", confidence=0.9), now=100.0)
    assert tracker.get_active_seconds() == 5.0

    # 2. Next active cycle at t=112.5 (12.5s real elapsed time between cycles)
    tracker.update(StateResult(state="focused", confidence=0.9), now=112.5)
    assert tracker.get_active_seconds() == 17.5

    # 3. User becomes idle at t=125.0
    tracker.update(StateResult(state="idle", confidence=0.9), now=125.0)
    assert tracker.get_active_seconds() == 17.5  # does not increase

    # 4. User still idle at t=200.0
    tracker.update(StateResult(state="idle", confidence=0.9), now=200.0)
    assert tracker.get_active_seconds() == 17.5  # still frozen

    # 5. User resumes work at t=210.0
    tracker.update(StateResult(state="focused", confidence=0.9), now=210.0)
    assert tracker.get_active_seconds() == 22.5  # counts 1 nominal cycle upon return

    # 6. Next active cycle at t=220.0 (10.0s elapsed)
    tracker.update(StateResult(state="focused", confidence=0.9), now=220.0)
    assert tracker.get_active_seconds() == 32.5

    # 7. Laptop suspension / sleep: 3600s gap to t=3820.0
    # Capped at 1 nominal cycle (5.0s) instead of accumulating offline duration
    tracker.update(StateResult(state="focused", confidence=0.9), now=3820.0)
    assert tracker.get_active_seconds() == 37.5
