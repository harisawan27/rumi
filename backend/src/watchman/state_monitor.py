import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.watchman.local_observer import LocalObserver

logger = logging.getLogger(__name__)

# Cycle runs every 5s — free (LocalObserver, no API calls)
# Triggers import this constant to accumulate elapsed time correctly
CYCLE_INTERVAL_SECONDS = 5

AWAY_THRESHOLD_CYCLES = 60      # 60 × 5s = 5 minutes of idle → away mode
FOCUSED_STREAK_THRESHOLD = 12   # 12 × 5s = 1 minute of focus → slow check-in cycle


@dataclass
class StateResult:
    state: str
    confidence: float
    cues: list = field(default_factory=list)
    landmarks: dict = field(default_factory=dict)


class StateMonitor:
    """Robot-style local perception loop. Zero API cost.

    Architecture:
    - LocalObserver (MediaPipe) runs on every frame — free, on-device.
    - No LLM is called here at all.
    - Trigger thresholds are tracked by FrustrationTracker / CodingBlockTracker.
    - When a trigger fires, the ADK Agent is invoked (ONE API call, rare event).

    Pull model: requests a single JPEG frame from frontend before each cycle.
    Frame diff gate: skips scoring if frame unchanged.
    Away mode: stops loop after 5 min of idle.
    """

    def __init__(self, gemini_client, frustration_tracker=None, coding_block_tracker=None,
                 long_session_tracker=None, deep_focus_tracker=None):
        self._gemini = gemini_client  # kept for voice dispatch in session_manager
        self._local = LocalObserver()
        self._frustration_tracker = frustration_tracker
        self._coding_block_tracker = coding_block_tracker
        self._long_session_tracker = long_session_tracker
        self._deep_focus_tracker = deep_focus_tracker
        self._stop_event = asyncio.Event()
        self._last_result: Optional[StateResult] = None
        self._current_frame: Optional[bytes] = None
        self._focused_streak = 0
        self._idle_streak = 0
        self._websocket = None

    def set_websocket(self, ws) -> None:
        self._websocket = ws

    def update_frame(self, frame_bytes: bytes) -> None:
        """Called by WS handler on every incoming frame from the frontend."""
        self._current_frame = frame_bytes

    async def _request_frame(self) -> None:
        """Ask the frontend for a fresh JPEG snapshot."""
        if not self._websocket:
            return
        try:
            await self._websocket.send_text(json.dumps({"type": "request_frame"}))
        except Exception as exc:
            logger.warning("StateMonitor: request_frame failed: %s", exc)

    async def run_cycle(self) -> StateResult:
        """Run one local observation cycle. No API call."""
        if not self._current_frame:
            logger.debug("StateMonitor: no frame — returning last result")
            return self._last_result or StateResult(state="neutral", confidence=0.0)

        observation = self._local.observe(self._current_frame)

        # Map LocalObservation → StateResult
        # Confidence is the dominant score
        if observation.event == "frustrated":
            confidence = observation.frustration_score
        elif observation.event == "idle":
            confidence = observation.idle_score
        else:
            confidence = 1.0 - max(observation.frustration_score, observation.idle_score)

        result = StateResult(
            state=observation.event,
            confidence=round(confidence, 2),
            cues=observation.cues,
            landmarks=observation.landmarks,
        )
        self._last_result = result
        logger.debug(
            "StateMonitor: state=%s confidence=%.2f cues=%s",
            result.state, result.confidence, result.cues,
        )
        return result

    async def run_loop(self, on_frustration=None, on_coding_block=None,
                       on_long_session=None, on_deep_focus=None,
                       on_soft_frustration=None) -> None:
        """Main watchman loop — free, always-on, event-driven."""
        self._stop_event.clear()

        while not self._stop_event.is_set():
            await asyncio.sleep(CYCLE_INTERVAL_SECONDS)
            if self._stop_event.is_set():
                break

            try:
                await self._request_frame()
                await asyncio.sleep(0.3)  # brief wait for frame to arrive

                result = await self.run_cycle()

                # Broadcast detection overlay to frontend
                if self._websocket:
                    try:
                        await self._websocket.send_text(json.dumps({
                            "type": "detection_update",
                            "state": result.state,
                            "confidence": result.confidence,
                            "cues": result.cues,
                            "landmarks": result.landmarks,
                        }))
                    except Exception:
                        pass

                # Away mode
                if result.state == "idle":
                    self._idle_streak += 1
                    self._focused_streak = 0
                    if self._idle_streak >= AWAY_THRESHOLD_CYCLES:
                        logger.info("StateMonitor: away mode — idle for ~5 min, stopping loop")
                        self._idle_streak = 0
                        self.stop()
                        break
                else:
                    self._idle_streak = 0

                if result.state == "focused":
                    self._focused_streak += 1
                else:
                    self._focused_streak = 0

                # Update all trackers
                if self._frustration_tracker:
                    self._frustration_tracker.update(result)
                if self._coding_block_tracker:
                    self._coding_block_tracker.update(result)
                if self._long_session_tracker:
                    self._long_session_tracker.update(result)
                if self._deep_focus_tracker:
                    self._deep_focus_tracker.update(result)

                # Trigger priority: A > B > C > E
                # (negative states take precedence; celebrate only when all is calm)
                trigger_a = self._frustration_tracker and self._frustration_tracker.should_fire()
                trigger_b = self._coding_block_tracker and self._coding_block_tracker.should_fire()
                trigger_c = self._long_session_tracker and self._long_session_tracker.should_fire()
                trigger_e = self._deep_focus_tracker and self._deep_focus_tracker.should_fire()

                # Soft check-in before full trigger A
                if self._frustration_tracker and self._frustration_tracker.should_soft_check():
                    self._frustration_tracker.reset_soft_check()
                    if on_soft_frustration:
                        await on_soft_frustration()

                if trigger_a:
                    self._frustration_tracker.reset_fire()
                    if on_frustration:
                        await on_frustration()
                elif trigger_b:
                    self._coding_block_tracker.reset_fire()
                    if on_coding_block:
                        await on_coding_block()
                elif trigger_c:
                    self._long_session_tracker.reset_fire()
                    if on_long_session:
                        await on_long_session()
                elif trigger_e:
                    self._deep_focus_tracker.reset_fire()
                    if on_deep_focus:
                        await on_deep_focus()

            except Exception as exc:
                logger.error("StateMonitor: cycle error: %s", exc)

    def stop(self) -> None:
        self._stop_event.set()
