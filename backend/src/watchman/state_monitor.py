import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.watchman.local_observer import LocalObserver
from src.gemini.vision_client import VisionClient

logger = logging.getLogger(__name__)

# Cycle runs every 5s
# Gemini vision runs every VISION_CYCLE_INTERVAL cycles = every 15s (3 × 5s)
CYCLE_INTERVAL_SECONDS = 5
VISION_CYCLE_INTERVAL  = 3   # Gemini vision call frequency

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
        self._vision = VisionClient()   # Gemini 2.5 Flash vision — richer analysis
        self._vision_cycle_counter = 0  # counts cycles between Gemini vision calls
        self._frustration_tracker = frustration_tracker
        self._coding_block_tracker = coding_block_tracker
        self._long_session_tracker = long_session_tracker
        self._deep_focus_tracker = deep_focus_tracker
        self._stop_event = asyncio.Event()
        self._last_result: Optional[StateResult] = None
        self._current_frame: Optional[bytes] = None
        self._screen_frame: Optional[bytes] = None
        self._focused_streak = 0
        self._idle_streak = 0
        self._websocket = None
        # ── Face watcher (owner verification + known people) ────────────────
        self._owner_photo_url: Optional[str] = None   # set by session_manager at start
        self._uid: str = ""                            # set via set_uid()
        self._face_check_counter  = 0
        self._face_check_interval = 2    # every 2 cycles = 10 seconds
        self._non_owner_streak    = 0
        self._non_owner_threshold = 1    # 1 mismatch → guest immediately
        self._guest_active        = False
        self._on_guest_detected   = None  # set via set_guest_callback()
        self._on_owner_returned   = None  # set via set_owner_returned_callback()
        # Current face label — "owner" | "known:Name:relationship" | "guest" | "nobody"
        self._last_face_label: str = "nobody"

    def set_uid(self, uid: str) -> None:
        """Store uid so face checker can query known people from Firestore."""
        self._uid = uid

    def set_owner_photo(self, url: str) -> None:
        """Called by session_manager after loading identity — enables face verification."""
        self._owner_photo_url = url
        logger.info("StateMonitor: owner photo loaded for face verification")

    def set_guest_callback(self, cb) -> None:
        """Callback fired when a confirmed guest is detected. Set by session_manager."""
        self._on_guest_detected = cb

    def set_owner_returned_callback(self, cb) -> None:
        """Callback fired when owner returns after a guest visit."""
        self._on_owner_returned = cb

    def set_websocket(self, ws) -> None:
        self._websocket = ws

    def update_frame(self, frame_bytes: bytes) -> None:
        """Called by WS handler on every incoming camera frame from the frontend."""
        self._current_frame = frame_bytes

    def update_screen_frame(self, frame_bytes: bytes) -> None:
        """Called by WS handler when frontend sends a screen capture frame."""
        self._screen_frame = frame_bytes

    async def _request_frame(self) -> None:
        """Ask the frontend for a fresh JPEG snapshot."""
        if not self._websocket:
            return
        try:
            await self._websocket.send_text(json.dumps({"type": "request_frame"}))
        except Exception as exc:
            logger.warning("StateMonitor: request_frame failed: %s", exc)

    async def run_cycle(self) -> StateResult:
        """Hybrid observation cycle.

        Every cycle:
          - LocalObserver._score_idle (frame diff, free) → detects away/idle instantly.

        Every VISION_CYCLE_INTERVAL cycles (~15s):
          - VisionClient (Gemini 2.5 Flash) → rich emotion + state analysis.
          - Skipped if frame diff shows no movement (person idle → no point calling Gemini).
        """
        if not self._current_frame:
            logger.debug("StateMonitor: no frame — returning last result")
            return self._last_result or StateResult(state="neutral", confidence=0.0)

        # ── Layer 1: frame diff (free, instant) ───────────────────────────────
        local_obs = self._local.observe(self._current_frame)

        # If completely idle (no movement), skip Gemini — no new info to gain
        if local_obs.idle_score >= 0.85:
            result = StateResult(
                state="idle",
                confidence=round(local_obs.idle_score, 2),
                cues=["No movement detected"],
                landmarks={},
            )
            self._last_result = result
            return result

        # ── Layer 2: Gemini vision (every VISION_CYCLE_INTERVAL cycles) ───────
        self._vision_cycle_counter += 1
        if self._vision_cycle_counter >= VISION_CYCLE_INTERVAL:
            self._vision_cycle_counter = 0
            try:
                if self._screen_frame:
                    data = await self._vision.analyse_frame_with_screen(self._current_frame, self._screen_frame)
                else:
                    data = await self._vision.analyse_frame(self._current_frame)
                result = StateResult(
                    state=data.get("state", "neutral"),
                    confidence=float(data.get("confidence", 0.5)),
                    cues=data.get("cues", []),
                    landmarks=data.get("emotions", {}),
                )
                self._last_result = result
                logger.info(
                    "StateMonitor [Gemini]: state=%s confidence=%.2f",
                    result.state, result.confidence,
                )
                return result
            except Exception as exc:
                logger.warning("StateMonitor: Gemini vision failed, using local: %s", exc)

        # ── Fallback: local FER result (between Gemini calls) ─────────────────
        if local_obs.event == "frustrated":
            confidence = local_obs.frustration_score
        else:
            confidence = 1.0 - max(local_obs.frustration_score, local_obs.idle_score)

        result = StateResult(
            state=local_obs.event,
            confidence=round(confidence, 2),
            cues=local_obs.cues,
            landmarks=local_obs.landmarks,
        )
        self._last_result = result
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

                # ── Face watcher — runs every 30s, non-blocking ──────────
                if self._owner_photo_url and self._current_frame:
                    self._face_check_counter += 1
                    if self._face_check_counter >= self._face_check_interval:
                        self._face_check_counter = 0
                        asyncio.create_task(
                            self._run_face_check()
                        )

            except Exception as exc:
                logger.error("StateMonitor: cycle error: %s", exc)

    def stop(self) -> None:
        self._stop_event.set()

    async def _run_face_check(self) -> None:
        """Compare current frame against owner, then known people. Fires WS events."""
        import base64
        if not self._current_frame or not self._owner_photo_url:
            return
        try:
            # ── Pre-check: local FER face detection (free, no API) ───────────
            # Skip Gemini entirely if no face is visible — prevents blank-frame
            # false positives where the model guesses identity on an empty frame.
            if not self._local.has_face(self._current_frame):
                self._non_owner_streak = 0
                self._last_face_label = "nobody"
                logger.debug("StateMonitor: no face detected locally — skipping Gemini check")
                return

            from src.vision.face_matcher import compare_faces
            frame_b64 = base64.b64encode(self._current_frame).decode()

            # ── Step 1: check owner ──────────────────────────────────────────
            result = await compare_faces(self._owner_photo_url, frame_b64)
            if result.is_owner:
                if self._guest_active:
                    logger.info("StateMonitor: owner returned")
                    if self._websocket:
                        await self._websocket.send_text(json.dumps({"type": "owner_returned"}))
                    if self._on_owner_returned:
                        asyncio.create_task(self._on_owner_returned())
                # Send identity_verified on every successful owner confirm — frontend
                # setIdentityVerified(true) is idempotent so this is safe every 10s
                if self._websocket:
                    await self._websocket.send_text(json.dumps({"type": "identity_verified"}))
                logger.info("StateMonitor: identity verified — owner confirmed")
                self._non_owner_streak = 0
                self._guest_active = False
                self._last_face_label = "owner"
                return

            # ── Step 2: not owner — if no face visible, reset streak and mark nobody
            if not result.face_detected:
                self._non_owner_streak = 0
                self._last_face_label = "nobody"
                logger.debug("StateMonitor: no face in frame — streak reset, not triggering guest")
                return

            # Face is present but not owner — check known people
            self._non_owner_streak += 1
            if self._uid:
                try:
                    known = await asyncio.get_event_loop().run_in_executor(
                        None, _load_known_people, self._uid
                    )
                    for person in known:
                        photo_url = person.get("photo_url", "")
                        if not photo_url:
                            continue
                        match = await compare_faces(photo_url, frame_b64)
                        if match.is_owner:   # same threshold — person is recognised
                            logger.info("StateMonitor: known person — %s (%s)",
                                        person["name"], person["relationship"])
                            self._non_owner_streak = 0  # known person ≠ guest
                            self._last_face_label = f"known:{person['name']}:{person['relationship']}"
                            if self._websocket:
                                await self._websocket.send_text(json.dumps({
                                    "type": "known_person_detected",
                                    "name": person["name"],
                                    "relationship": person["relationship"],
                                }))
                            # Update last_seen + interaction_count async
                            asyncio.get_event_loop().run_in_executor(
                                None, _bump_known_person, self._uid, person["id"]
                            )
                            return
                except Exception as exc:
                    logger.debug("StateMonitor: known people check failed: %s", exc)

            # ── Step 3: unknown person — guest detection ─────────────────────
            if self._non_owner_streak >= self._non_owner_threshold and not self._guest_active:
                self._guest_active = True
                self._last_face_label = "guest"
                logger.info("StateMonitor: guest confirmed (confidence=%.2f)", result.confidence)
                if self._websocket:
                    await self._websocket.send_text(json.dumps({
                        "type": "guest_detected",
                        "confidence": result.confidence,
                    }))
                if self._on_guest_detected:
                    asyncio.create_task(self._on_guest_detected())

        except Exception as exc:
            logger.debug("StateMonitor: face check error: %s", exc)


def _load_known_people(uid: str) -> list:
    from src.memory.known_people import get_known_people
    return get_known_people(uid)


def _bump_known_person(uid: str, person_id: str) -> None:
    from src.memory.known_people import record_known_person_interaction
    record_known_person_interaction(uid, person_id)
