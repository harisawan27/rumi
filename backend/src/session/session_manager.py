import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from src.identity.identity_loader import load_core_identity, load_session_summaries
from src.gemini.prompt_builder import build_system_prompt
from src.gemini.live_client import GeminiLiveClient
from src.memory.firestore_client import get_db

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the lifecycle of a single Mirr'at observation session."""

    def __init__(self):
        self._uid: Optional[str] = None
        self._session_id: Optional[str] = None
        self._gemini: Optional[GeminiLiveClient] = None
        self._status: str = "idle"
        self._websocket = None  # frontend WS connection, set externally
        self._watchman_task: Optional[asyncio.Task] = None
        self._idle_timer_task: Optional[asyncio.Task] = None
        self._gemini_idle_task: Optional[asyncio.Task] = None
        self._system_prompt: Optional[str] = None
        self._gemini_connecting: bool = False  # guard against concurrent connects

    # -----------------------------------------------------------------------
    # Session lifecycle
    # -----------------------------------------------------------------------

    async def start_session(self, uid: str) -> str:
        """Load identity + summaries → build system prompt → create Firestore session
        document → return session_id. Gemini Live connection is deferred to WebSocket connect.
        """
        self._uid = uid
        summary_depth = int(os.getenv("SESSION_SUMMARY_DEPTH", "3"))

        identity = load_core_identity(uid)
        summaries = load_session_summaries(uid, limit=summary_depth)
        self._system_prompt = build_system_prompt(identity, summaries)

        session_doc = {
            "user_id": uid,
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "status": "active",
            "interaction_ids": [],
            "session_summary_id": None,
        }
        db = get_db()
        _, ref = db.collection("users").document(uid).collection("sessions").add(session_doc)
        self._session_id = ref.id
        ref.update({"session_id": self._session_id})
        self._status = "active"

        logger.info("SessionManager: session started — %s", self._session_id)
        return self._session_id

    async def ensure_gemini_connected(self) -> None:
        """Lazily open a Gemini Live session only when needed.

        Called by: push-to-talk audio, trigger fires, greeting.
        After each exchange completes, a 2-min idle timer closes the session
        automatically — so it never hits the Live API duration limit.
        """
        if self._gemini and self._gemini.is_connected:
            self._reset_gemini_idle_timer()
            return
        if self._gemini_connecting:
            # Another coroutine is already connecting — wait briefly
            for _ in range(20):
                await asyncio.sleep(0.1)
                if self._gemini and self._gemini.is_connected:
                    return
            return
        self._gemini_connecting = True
        try:
            api_key = os.environ["GEMINI_API_KEY"]
            self._gemini = GeminiLiveClient(api_key=api_key)
            self._gemini.set_audio_callback(self._forward_audio)
            await self._gemini.connect(self._system_prompt)
            logger.info("SessionManager: Gemini Live session opened (on-demand)")
        finally:
            self._gemini_connecting = False
        self._reset_gemini_idle_timer()

    def _reset_gemini_idle_timer(self) -> None:
        """Restart the 2-minute idle disconnect countdown."""
        if self._gemini_idle_task:
            self._gemini_idle_task.cancel()
        self._gemini_idle_task = asyncio.create_task(self._gemini_idle_disconnect())

    async def _gemini_idle_disconnect(self) -> None:
        """Disconnect Gemini Live after 2 minutes of silence."""
        await asyncio.sleep(120)
        if self._gemini and self._gemini.is_connected:
            await self._gemini.disconnect()
            logger.info("SessionManager: Gemini Live disconnected (idle timeout)")

    async def connect_gemini(self) -> None:
        """Called when frontend WebSocket is established.
        Starts watchman and sends the opening greeting — Gemini is opened
        on-demand for the greeting then closes after 2 min idle.
        """
        self.start_watchman()
        asyncio.create_task(self._send_greeting())
        logger.info("SessionManager: WebSocket ready — greeting queued")

    async def _send_greeting(self) -> None:
        """Open Gemini Live, greet the user, then let idle timer close the session."""
        await asyncio.sleep(1.5)  # small delay to let WS stabilise
        try:
            await self.ensure_gemini_connected()
            await self._gemini.query(
                "You have just started a new observation session with the user. "
                "Greet them warmly and briefly (1–2 sentences max). "
                "Use their name and mention one of their active projects naturally. "
                "Be the Sufi-Engineer you are — precise, warm, human."
            )
            # Idle timer already running — session closes after 2 min if no activity
        except Exception as exc:
            logger.warning("SessionManager: greeting failed: %s", exc)

    async def _forward_audio(self, pcm_bytes: bytes) -> None:
        """Forward Gemini audio response to the frontend WebSocket.
        Also resets the idle timer — Gemini is still active while sending audio.
        """
        if self._websocket is None:
            return
        import base64
        import json
        try:
            b64 = base64.b64encode(pcm_bytes).decode()
            await self._websocket.send_text(
                json.dumps({"type": "audio_response", "data": b64})
            )
            self._reset_gemini_idle_timer()  # keep alive while response is streaming
        except Exception as exc:
            logger.warning("SessionManager: audio forward failed: %s", exc)

    async def pause_session(self) -> None:
        self._status = "paused"
        if self._watchman_task:
            self._watchman_task.cancel()
            self._watchman_task = None
        await self._update_firestore_status("paused")
        self._start_idle_timer()
        logger.info("SessionManager: session paused — %s", self._session_id)

    async def resume_session(self) -> None:
        if self._idle_timer_task:
            self._idle_timer_task.cancel()
            self._idle_timer_task = None
        self._status = "active"
        await self._update_firestore_status("active")
        # Reset long-session clock so 90-min countdown restarts from resume, not session start
        if hasattr(self, "_state_monitor") and self._state_monitor:
            tracker = getattr(self._state_monitor, "_long_session_tracker", None)
            if tracker:
                tracker.reset_clock()
        logger.info("SessionManager: session resumed — %s", self._session_id)

    async def end_session(self) -> None:
        self._status = "ended"
        if self._watchman_task:
            self._watchman_task.cancel()
            self._watchman_task = None
        if self._idle_timer_task:
            self._idle_timer_task.cancel()
            self._idle_timer_task = None
        if self._gemini_idle_task:
            self._gemini_idle_task.cancel()
            self._gemini_idle_task = None
        if self._gemini:
            await self._gemini.disconnect()

        ended_at = datetime.now(timezone.utc)
        if self._uid and self._session_id:
            try:
                db = get_db()
                db.collection("users").document(self._uid).collection("sessions").document(
                    self._session_id
                ).update({"status": "ended", "ended_at": ended_at})
            except Exception as exc:
                logger.warning("SessionManager: Firestore session update failed (stale?): %s", exc)

        # Trigger auto-summarizer in background
        asyncio.create_task(self._run_auto_summarizer(ended_at))
        logger.info("SessionManager: session ended — %s", self._session_id)

    # -----------------------------------------------------------------------
    # Intervention dispatch
    # -----------------------------------------------------------------------

    async def dispatch_intervention(
        self,
        trigger_type: str,
        interaction_id: str,
        text: str,
    ) -> None:
        """Send an intervention message to the frontend WebSocket."""
        if self._websocket is None:
            return
        import json
        msg = json.dumps({
            "type": "intervention",
            "trigger": trigger_type,
            "text": text,
            "interaction_id": interaction_id,
            "options": ["accept", "dismiss"],
        })
        try:
            await self._websocket.send_text(msg)
        except Exception as exc:
            logger.warning("SessionManager: WS send failed: %s", exc)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _update_firestore_status(self, status: str) -> None:
        if not self._uid or not self._session_id:
            return
        try:
            db = get_db()
            db.collection("users").document(self._uid).collection("sessions").document(
                self._session_id
            ).update({"status": status})
        except Exception as exc:
            logger.warning("SessionManager: Firestore status update failed: %s", exc)

    def _start_idle_timer(self) -> None:
        idle_minutes = int(os.getenv("IDLE_TIMEOUT_MINUTES", "30"))

        async def _timer():
            await asyncio.sleep(idle_minutes * 60)
            if self._status == "paused":
                logger.info("SessionManager: idle timeout reached — ending session")
                await self.end_session()

        self._idle_timer_task = asyncio.create_task(_timer())

    async def _run_auto_summarizer(self, ended_at: datetime) -> None:
        from src.session.auto_summarizer import AutoSummarizer
        try:
            summarizer = AutoSummarizer()
            await summarizer.summarize_and_save(
                uid=self._uid,
                session_id=self._session_id,
                ended_at=ended_at,
            )
        except Exception as exc:
            logger.error("SessionManager: auto-summarizer failed: %s", exc)

    # -----------------------------------------------------------------------
    # Watchman loop (T029 — wires Trigger A; T034 — Trigger B added in Phase 6)
    # -----------------------------------------------------------------------

    def start_watchman(self) -> None:
        """Start the Watchman observation loop with all four trigger trackers."""
        from src.watchman.state_monitor import StateMonitor
        from src.watchman.trigger_a import FrustrationTracker
        from src.watchman.trigger_b import CodingBlockTracker
        from src.watchman.trigger_c import LongSessionTracker
        from src.watchman.trigger_e import DeepFocusTracker

        frustration = FrustrationTracker()
        coding_block = CodingBlockTracker()
        long_session = LongSessionTracker()
        deep_focus = DeepFocusTracker()

        self._coding_block_tracker = coding_block  # expose for frame hash updates
        monitor = StateMonitor(
            gemini_client=self._gemini,
            frustration_tracker=frustration,
            coding_block_tracker=coding_block,
            long_session_tracker=long_session,
            deep_focus_tracker=deep_focus,
        )
        monitor.set_websocket(self._websocket)
        self._state_monitor = monitor
        self._watchman_task = asyncio.create_task(
            monitor.run_loop(
                on_frustration=self._fire_trigger_a,
                on_coding_block=self._fire_trigger_b,
                on_long_session=self._fire_trigger_c,
                on_deep_focus=self._fire_trigger_e,
            )
        )
        logger.info("SessionManager: Watchman loop started (triggers A, B, C, E)")

    async def _fire_trigger_a(self) -> None:
        """Generate Trigger A intervention via ADK Agent and dispatch to frontend."""
        from src.agent.mirrat_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("frustrated", self._uid, self._session_id)

        # Also have Gemini Live speak it aloud
        asyncio.create_task(self._speak(intervention_text))

        interaction_id = log_interaction(
            uid=self._uid,
            session_id=self._session_id,
            trigger_type="A",
            intervention_text=intervention_text,
        )
        await self.dispatch_intervention("A", interaction_id, intervention_text)
        logger.info("SessionManager: Trigger A fired — interaction %s", interaction_id)

    async def _fire_trigger_b(self) -> None:
        """Generate Trigger B intervention via ADK Agent and dispatch to frontend."""
        from src.agent.mirrat_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("coding_block", self._uid, self._session_id)

        asyncio.create_task(self._speak(intervention_text))

        interaction_id = log_interaction(
            uid=self._uid,
            session_id=self._session_id,
            trigger_type="B",
            intervention_text=intervention_text,
        )
        await self.dispatch_intervention("B", interaction_id, intervention_text)
        logger.info("SessionManager: Trigger B fired — interaction %s", interaction_id)

    async def _fire_trigger_c(self) -> None:
        """Trigger C — long session, suggest a break."""
        from src.agent.mirrat_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("long_session", self._uid, self._session_id)
        asyncio.create_task(self._speak(intervention_text))

        interaction_id = log_interaction(
            uid=self._uid,
            session_id=self._session_id,
            trigger_type="C",
            intervention_text=intervention_text,
        )
        await self.dispatch_intervention("C", interaction_id, intervention_text)
        logger.info("SessionManager: Trigger C fired — interaction %s", interaction_id)

    async def _fire_trigger_e(self) -> None:
        """Trigger E — deep focus streak, celebrate it."""
        from src.agent.mirrat_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("deep_focus", self._uid, self._session_id)
        asyncio.create_task(self._speak(intervention_text))

        interaction_id = log_interaction(
            uid=self._uid,
            session_id=self._session_id,
            trigger_type="E",
            intervention_text=intervention_text,
        )
        await self.dispatch_intervention("E", interaction_id, intervention_text)
        logger.info("SessionManager: Trigger E fired — interaction %s", interaction_id)

    async def _speak(self, text: str) -> None:
        """Ensure Gemini Live is open, then speak the text aloud."""
        try:
            await self.ensure_gemini_connected()
            await self._gemini.query(f"Say this warmly to the user: {text}")
        except Exception as exc:
            logger.warning("SessionManager: speak failed: %s", exc)

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def gemini(self) -> Optional[GeminiLiveClient]:
        return self._gemini
