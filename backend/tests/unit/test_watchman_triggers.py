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
    assert tracker._elapsed_seconds > 0.0, "Focused state MUST accumulate towards deep focus"


def test_deep_focus_accumulates_on_neutral():
    tracker = DeepFocusTracker()
    res_neutral = StateResult(state="neutral", confidence=0.7)

    tracker.update(res_neutral)
    assert tracker._elapsed_seconds > 0.0, "Calm neutral state should accumulate towards deep focus"


def test_deep_focus_resets_on_frustration_or_idle():
    tracker = DeepFocusTracker()
    tracker.update(StateResult(state="focused", confidence=0.9))
    assert tracker._elapsed_seconds > 0.0

    # Frustration breaks focus streak
    tracker.update(StateResult(state="frustrated", confidence=0.85))
    assert tracker._elapsed_seconds == 0.0

    tracker.update(StateResult(state="focused", confidence=0.9))
    assert tracker._elapsed_seconds > 0.0

    # Idle breaks focus streak
    tracker.update(StateResult(state="idle", confidence=0.9))
    assert tracker._elapsed_seconds == 0.0


# ---------------------------------------------------------------------------
# Trigger C: LongSessionTracker Tests
# ---------------------------------------------------------------------------

def test_long_session_does_not_accumulate_idle_time():
    tracker = LongSessionTracker()

    # User works 1 cycle
    tracker.update(StateResult(state="focused", confidence=0.9))
    working_time_1 = tracker.get_active_seconds() if hasattr(tracker, "get_active_seconds") else tracker._elapsed_seconds
    assert working_time_1 > 0

    # User is idle for simulated long period (10 idle cycles)
    for _ in range(10):
        tracker.update(StateResult(state="idle", confidence=0.95))

    working_time_after_idle = tracker.get_active_seconds() if hasattr(tracker, "get_active_seconds") else tracker._elapsed_seconds
    assert working_time_after_idle == working_time_1, "Idle cycles must NOT increase active working time"


def test_long_session_resumes_after_idle():
    tracker = LongSessionTracker()
    tracker.update(StateResult(state="focused", confidence=0.9))
    time_1 = tracker.get_active_seconds() if hasattr(tracker, "get_active_seconds") else tracker._elapsed_seconds

    # Idle cycle
    tracker.update(StateResult(state="idle", confidence=0.9))

    # Resumes work
    tracker.update(StateResult(state="focused", confidence=0.9))
    time_2 = tracker.get_active_seconds() if hasattr(tracker, "get_active_seconds") else tracker._elapsed_seconds
    assert time_2 > time_1, "Resumed active work must continue accumulating"
