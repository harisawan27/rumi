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
        self._is_away: bool = False
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

                # Lightweight presence check if in away mode
                if self._is_away:
                    local_obs = self._local.observe(self._current_frame) if self._current_frame else None
                    if local_obs and (local_obs.idle_score < 0.85 or self._local.has_face(self._current_frame)):
                        self._is_away = False
                        self._idle_streak = 0
                        logger.info("StateMonitor: presence returned — transitioning away -> active")
                        if self._websocket:
                            try:
                                await self._websocket.send_text(json.dumps({"type": "presence_returned"}))
                            except Exception:
                                pass
                    else:
                        # Throttled idle loop while user is away
                        continue

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

                # Away mode threshold detection
                if result.state == "idle":
                    self._idle_streak += 1
                    self._focused_streak = 0
                    if self._idle_streak >= AWAY_THRESHOLD_CYCLES:
                        if not self._is_away:
                            logger.info("StateMonitor: away mode entered — idle for ~5 min")
                            self._is_away = True
                            if self._websocket:
                                try:
                                    await self._websocket.send_text(json.dumps({"type": "away_mode"}))
                                except Exception:
                                    pass
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

                # ── Face watcher — runs every 10s, non-blocking ──────────
                # Only runs after owner has uploaded a profile photo.
                # Before that, guest mode is never triggered (new accounts are safe).
                if self._current_frame and self._owner_photo_url:
                    self._face_check_counter += 1
                    if self._face_check_counter >= self._face_check_interval:
                        self._face_check_counter = 0
                        asyncio.create_task(self._run_face_check())

            except Exception as exc:
                logger.error("StateMonitor: cycle error: %s", exc)

    def stop(self) -> None:
        self._stop_event.set()

    async def _run_face_check(self) -> None:
        """Identity check every 10s using local face embeddings (zero Gemini API cost).

        Owner face in frame  → identity_verified, streak reset, distributed presence extended.
        Known person face    → known_person_detected, streak reset.
        No face              → desk empty (nobody).
        Multiple faces / Unknown face → guest mode activated immediately.
        """
        if not self._current_frame:
            return
        try:
            from src.vision.face_identity_service import face_identity_service
            from src.vision.face_matcher import FaceVerificationStatus

            result = await face_identity_service.identify(
                frame_bytes=self._current_frame,
                uid=self._uid,
                owner_photo_url=self._owner_photo_url,
            )

            from src.utils.observability import log_structured_event
            log_structured_event(
                event_type="FACE_IDENTIFICATION",
                uid=self._uid,
                face_status=result.status.value,
                face_similarity=result.similarity,
                face_confidence=result.confidence,
                presence_mode="guest" if self._guest_active else "owner",
                faces_detected=result.faces_detected,
            )

            if result.status == FaceVerificationStatus.VERIFICATION_UNAVAILABLE:
                logger.warning("StateMonitor: face identity unavailable — maintaining state")
                return

            # ── 1. Owner confirmed ───────────────────────────────────────────
            if result.status == FaceVerificationStatus.OWNER:
                if self._guest_active:
                    logger.info("StateMonitor: owner returned")
                    if self._websocket:
                        await self._websocket.send_text(json.dumps({"type": "owner_returned"}))
                    if self._on_owner_returned:
                        asyncio.create_task(self._on_owner_returned())
                if self._websocket:
                    await self._websocket.send_text(json.dumps({"type": "identity_verified"}))
                logger.info("StateMonitor: identity verified — owner confirmed (sim=%.3f)", result.similarity or 0.0)
                self._non_owner_streak = 0
                self._guest_active = False
                self._last_face_label = "owner"

                # Extend distributed presence authorization
                if self._uid:
                    try:
                        from src.session.presence_manager import presence_manager
                        presence_manager.set_owner_verified(self._uid, confidence=result.confidence or 1.0)
                    except Exception:
                        pass
                return

            # ── 2. Known Person confirmed ────────────────────────────────────
            if result.status == FaceVerificationStatus.KNOWN_PERSON:
                logger.info("StateMonitor: known person detected — %s (%s, sim=%.3f)",
                            result.name, result.relationship, result.similarity or 0.0)
                self._non_owner_streak = 0
                self._last_face_label = f"known:{result.name}:{result.relationship}"
                if self._websocket:
                    await self._websocket.send_text(json.dumps({
                        "type": "known_person_detected",
                        "name": result.name or "",
                        "relationship": result.relationship or "",
                    }))
                if result.person_id and self._uid:
                    asyncio.get_event_loop().run_in_executor(
                        None, _bump_known_person, self._uid, result.person_id
                    )
                return

            # ── 3. No face in frame ──────────────────────────────────────────
            if result.status == FaceVerificationStatus.NO_FACE:
                self._last_face_label = "nobody"
                logger.debug("StateMonitor: no face in frame — desk empty")
                return

            # ── 4. Unknown face or Multiple faces ────────────────────────────
            # Multiple simultaneous faces conservatively remove owner-private authorization /
            # enter protected guest state without individual face tracking.
            self._last_face_label = "guest"
            self._non_owner_streak += 1
            logger.debug("StateMonitor: non_owner_streak=%d (status=%s, faces=%d)",
                         self._non_owner_streak, result.status.value, result.faces_detected)

            if self._non_owner_streak >= self._non_owner_threshold and not self._guest_active:
                self._guest_active = True
                logger.info("StateMonitor: guest mode activated — streak=%d status=%s",
                            self._non_owner_streak, result.status.value)
                if self._websocket:
                    await self._websocket.send_text(json.dumps({
                        "type": "guest_detected",
                        "confidence": result.confidence or 0.0,
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
