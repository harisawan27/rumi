import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import pytest

from src.watchman.local_observer import LocalObserver, LocalObservation
from src.watchman.state_monitor import StateMonitor, StateResult


def test_local_observation_dataclass_fields():
    obs = LocalObservation(
        event="neutral",
        frustration_score=0.1,
        idle_score=0.2,
        cues=["neutral"],
        landmarks={"happy": 0.85, "neutral": 0.15},
        face_detected=True,
        detector_status="ready",
    )
    assert obs.event == "neutral"
    assert obs.landmarks["happy"] == 0.85
    assert obs.face_detected is True
    assert obs.detector_status == "ready"


def test_local_observer_blank_frame_no_face():
    observer = LocalObserver()
    observer._fer_loaded = True
    observer._fer = MagicMock()
    observer._fer.detect_emotions.return_value = []

    # Blank black image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    import cv2
    frame_bytes = cv2.imencode(".jpg", img)[1].tobytes()

    with patch.object(observer, "_find_face_rectangles", return_value=[]):
        obs = observer.observe(frame_bytes)

    assert obs.face_detected is False
    assert obs.landmarks == {}
    assert obs.event == "neutral" or obs.event == "idle"


def test_local_observer_yunet_fallback_when_haar_misses():
    observer = LocalObserver()
    observer._fer_loaded = True
    observer._fer = MagicMock()
    # First call (Haar) returns empty, second call (with face_rectangles from YuNet) returns face
    observer._fer.detect_emotions.side_effect = [
        [],
        [{"box": (10, 10, 50, 50), "emotions": {"happy": 0.88, "neutral": 0.10, "angry": 0.02}}],
    ]

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    import cv2
    frame_bytes = cv2.imencode(".jpg", img)[1].tobytes()

    with patch.object(observer, "_find_face_rectangles", return_value=[(10, 10, 50, 50)]):
        obs = observer.observe(frame_bytes)

    assert obs.face_detected is True
    assert obs.landmarks["happy"] == 0.88
    assert "happy" in obs.cues


def test_state_monitor_preserves_landmarks_on_idle():
    """Regression test for Bug 1: StateMonitor must NOT wipe landmarks to {} when idle_score >= 0.85."""
    monitor = StateMonitor(gemini_client=MagicMock())
    monitor._current_frame = b"fake_jpeg_bytes"

    fake_emotions = {"happy": 0.90, "neutral": 0.10}
    fake_obs = LocalObservation(
        event="idle",
        frustration_score=0.0,
        idle_score=0.92,  # User sitting completely still looking at camera
        cues=["No movement detected"],
        landmarks=fake_emotions,
        face_detected=True,
        detector_status="ready",
    )

    with patch.object(monitor._local, "observe", return_value=fake_obs):
        result = asyncio.run(monitor.run_cycle())

    assert result.state == "idle"
    # MUST NOT be empty dict!
    assert result.landmarks == fake_emotions, "Emotion landmarks must be preserved even when user is still"
    assert result.face_detected is True
    assert result.detector_status == "ready"


@pytest.mark.asyncio
async def test_state_monitor_throttled_perception_broadcast():
    monitor = StateMonitor(gemini_client=MagicMock())
    mock_ws = AsyncMock()
    monitor.set_websocket(mock_ws)

    fake_obs = LocalObservation(
        event="neutral",
        frustration_score=0.05,
        idle_score=0.1,
        cues=["neutral"],
        landmarks={"neutral": 0.80, "happy": 0.20},
        face_detected=True,
        detector_status="ready",
    )

    with patch.object(monitor._local, "observe", return_value=fake_obs):
        res = await monitor.process_incoming_frame(b"dummy_frame")

    assert res is not None
    assert mock_ws.send_text.called
    sent_payload = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent_payload["type"] == "detection_update"
    assert sent_payload["landmarks"] == {"neutral": 0.80, "happy": 0.20}
    assert sent_payload["face_detected"] is True
    assert sent_payload["detector_status"] == "ready"


@pytest.mark.asyncio
async def test_state_monitor_expression_independent_of_watchman_triggers():
    """Perception updates must flow even if no proactive Watchman trigger fires."""
    monitor = StateMonitor(gemini_client=MagicMock())
    mock_ws = AsyncMock()
    monitor.set_websocket(mock_ws)

    fake_obs = LocalObservation(
        event="neutral",
        frustration_score=0.0,
        idle_score=0.0,
        cues=[],
        landmarks={"neutral": 0.95},
        face_detected=True,
        detector_status="ready",
    )

    with patch.object(monitor._local, "observe", return_value=fake_obs):
        res = await monitor.process_incoming_frame(b"frame_1")

    assert res is not None
    assert mock_ws.send_text.called
    payload = json.loads(mock_ws.send_text.call_args[0][0])
    assert payload["type"] == "detection_update"
    assert payload["state"] == "neutral"
