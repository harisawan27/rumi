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
    """Manages the lifecycle of a single Rumi observation session."""

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
        # Serialise watchman _speak calls — prevents concurrent trigger audio
        self._gemini_lock: asyncio.Lock = asyncio.Lock()
        # Greeting task ref — cancelled immediately when user speaks
        self._greeting_task: Optional[asyncio.Task] = None
        # When True, _forward_audio drops bytes AND _receive_loop skips task creation
        self._suppress_audio: bool = False
        # Generation counter — incremented on every voice_query call.
        # CancelledError handlers check this before touching _suppress_audio so a
        # stale cancelled task can't close the gate on a newer active response.
        self._voice_gen: int = 0
        # Prevent double-greeting (connect_gemini + resume both call _send_greeting)
        self._has_greeted: bool = False
        # True while a user query response is in progress — blocks duplicate responses
        # and prevents watchman from speaking over the user's response
        self._is_responding: bool = False
        # Tracks the current speak_verbatim task so a new query can cancel it
        self._speak_task: Optional[asyncio.Task] = None
        # Owner identity — loaded at session start, used for guest intervention
        self._owner_name: str = ""
        self._owner_photo_url: str = ""
        # Prevent firing guest intervention multiple times per guest visit
        self._guest_intervention_fired: bool = False
        # Latest screen frame from frontend (updated via screen_frame WS message)
        self._latest_screen_frame: Optional[bytes] = None

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
        self._owner_name      = identity.get("name", "the owner")
        self._owner_photo_url = identity.get("profile_photo_url", "")

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

        logger.info("[RUMI CORE] Session started — identity protocol active — %s", self._session_id)
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
            # Inline suppress check — evaluated at the moment each audio chunk
            # arrives in _receive_loop, preventing stale audio task creation.
            self._gemini.set_suppress_check(lambda: self._suppress_audio)
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
        """Disconnect Gemini Live after 10 minutes of silence."""
        await asyncio.sleep(600)
        if self._gemini and self._gemini.is_connected:
            await self._gemini.disconnect()
            logger.info("SessionManager: Gemini Live disconnected (idle timeout)")

    async def connect_gemini(self) -> None:
        """Called when frontend WebSocket is established.
        Only starts the watchman and greets if the session is active — not if paused.
        This prevents auto-greeting on backend restarts when the user had paused.
        """
        if self._status == "paused":
            logger.info("SessionManager: WebSocket reconnected but session is paused — skipping watchman + greeting")
            return
        self.start_watchman()
        self._greeting_task = asyncio.create_task(self._send_greeting())
        logger.info("SessionManager: WebSocket ready — greeting queued")

    async def _send_greeting(self) -> None:
        """Open Gemini Live, greet the user once per session.
        Uses _gemini_lock so it never conflicts with _speak_verbatim.
        _has_greeted prevents double-greeting from connect_gemini + resume_session.
        """
        if self._has_greeted:
            logger.info("SessionManager: greeting skipped — already greeted this session")
            return
        self._has_greeted = True
        try:
            await asyncio.sleep(1.5)  # let WS stabilise
            async with self._gemini_lock:
                await self.ensure_gemini_connected()
                await self._gemini.query(
                    f"You have just started a new observation session with {self._owner_name}. "
                    "Greet them by name in ONE sentence. "
                    "Check your session memory: if you have prior session summaries, naturally reference "
                    "what they were working on last time (e.g. 'Welcome back — last time you were deep in X, ready to continue?'). "
                    "If this is their first session, welcome them warmly. "
                    "No preamble. Speak directly. 1 sentence only."
                )
        except asyncio.CancelledError:
            logger.info("SessionManager: greeting cancelled — user spoke first")
        except Exception as exc:
            logger.warning("SessionManager: greeting failed: %s", exc)

    async def _forward_audio(self, pcm_bytes: bytes) -> None:
        """Forward Gemini audio response to the frontend WebSocket.
        Also resets the idle timer — Gemini is still active while sending audio.
        Drops audio silently when _suppress_audio is True (user cancelled greeting).
        """
        if self._websocket is None:
            return
        if self._suppress_audio:
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
            try:
                await self._watchman_task
            except asyncio.CancelledError:
                pass
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
        # Restart the watchman loop — it was cancelled on pause
        if hasattr(self, "_state_monitor") and self._state_monitor and not self._watchman_task:
            self._watchman_task = asyncio.create_task(
                self._state_monitor.run_loop(
                    on_frustration=self._fire_trigger_a,
                    on_coding_block=self._fire_trigger_b,
                    on_long_session=self._fire_trigger_c,
                    on_deep_focus=self._fire_trigger_e,
                    on_soft_frustration=self._soft_frustration_checkin,
                )
            )
            logger.info("SessionManager: Watchman loop restarted after resume")
        # Send greeting so Rumi acknowledges the (re)start
        self._greeting_task = asyncio.create_task(self._send_greeting())
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
        import json
        from src.session.auto_summarizer import AutoSummarizer
        from src.session.memory_extractor import MemoryExtractor

        uid = self._uid
        session_id = self._session_id
        summary_text = ""

        try:
            summarizer = AutoSummarizer()
            _, summary_text = await summarizer.summarize_and_save(
                uid=uid,
                session_id=session_id,
                ended_at=ended_at,
            )
        except Exception as exc:
            logger.error("SessionManager: auto-summarizer failed: %s", exc)

        try:
            extractor = MemoryExtractor()
            patch = await extractor.extract_and_patch(uid, session_id, summary_text)
            if patch and self._websocket:
                fields = list(patch.keys())
                await self._websocket.send_text(json.dumps({
                    "type": "memory_updated",
                    "fields": fields,
                    "message": f"Rumi updated your memory: {', '.join(fields)}",
                }))
                logger.info("SessionManager: memory update notified — %s", fields)
        except Exception as exc:
            logger.error("SessionManager: memory extractor failed: %s", exc)

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
        monitor.set_uid(self._uid)
        if self._owner_photo_url:
            monitor.set_owner_photo(self._owner_photo_url)
        monitor.set_guest_callback(self._fire_guest_detected)
        monitor.set_owner_returned_callback(self.reset_guest_intervention)
        self._state_monitor = monitor
        self._watchman_task = asyncio.create_task(
            monitor.run_loop(
                on_frustration=self._fire_trigger_a,
                on_coding_block=self._fire_trigger_b,
                on_long_session=self._fire_trigger_c,
                on_deep_focus=self._fire_trigger_e,
                on_soft_frustration=self._soft_frustration_checkin,
            )
        )
        logger.info("SessionManager: Watchman loop started (triggers A, B, C, E, Guest)")

    async def _fire_trigger_a(self) -> None:
        """Generate Trigger A intervention via ADK Agent and dispatch to frontend."""
        from src.agent.rumi_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("frustrated", self._uid, self._session_id)

        # Voice disabled — intervention shown as card only.
        # Proactive _speak() races with voice_query on the shared Gemini session.

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
        from src.agent.rumi_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("coding_block", self._uid, self._session_id)

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
        from src.agent.rumi_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("long_session", self._uid, self._session_id)

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
        from src.agent.rumi_agent import generate_intervention
        from src.memory.interaction_log import log_interaction

        intervention_text = await generate_intervention("deep_focus", self._uid, self._session_id)

        interaction_id = log_interaction(
            uid=self._uid,
            session_id=self._session_id,
            trigger_type="E",
            intervention_text=intervention_text,
        )
        await self.dispatch_intervention("E", interaction_id, intervention_text)
        logger.info("SessionManager: Trigger E fired — interaction %s", interaction_id)

    async def _soft_frustration_checkin(self) -> None:
        """Soft frustration check-in — disabled to prevent race with voice_query."""
        logger.info("SessionManager: soft frustration check-in skipped (voice disabled)")

    async def _fire_guest_detected(self) -> None:
        """Speak a warm guest greeting and send an intervention card.
        Only fires once per guest visit — resets when owner returns.
        """
        if self._guest_intervention_fired:
            return
        self._guest_intervention_fired = True

        from src.agent.rumi_agent import get_user_context, _build_language_instruction
        from src.memory.interaction_log import log_interaction

        ctx      = get_user_context()
        lang_ctx = _build_language_instruction(ctx)

        text = (
            f"I see someone new in front of the camera. "
            f"I'm Rumi, {self._owner_name}'s AI companion. "
            f"Are you a friend or family member? I'm happy to help while they're away."
        )

        # Voice disabled — intervention shown as card only.
        # Proactive _speak() races with voice_query on the shared Gemini session.

        # Send intervention card to frontend
        interaction_id = log_interaction(
            uid=self._uid,
            session_id=self._session_id,
            trigger_type="G",
            intervention_text=text,
        )
        await self.dispatch_intervention("G", interaction_id, text)
        logger.info("SessionManager: guest intervention fired")

    def reset_guest_intervention(self) -> None:
        """Called when the owner returns — allows the next guest to get a fresh greeting."""
        self._guest_intervention_fired = False

    async def refresh_context(self) -> None:
        """Reload identity from Firestore and rebuild system prompt live.

        Called when the user changes companion language, expression styles, or tone
        in the profile page mid-session. Disconnects Gemini so it reconnects with
        the new system prompt on the next query.
        """
        if not self._uid:
            return
        import os
        summary_depth = int(os.getenv("SESSION_SUMMARY_DEPTH", "3"))
        identity = load_core_identity(self._uid)
        summaries = load_session_summaries(self._uid, limit=summary_depth)
        self._system_prompt = build_system_prompt(identity, summaries)
        self._owner_name = identity.get("name", "the owner")
        new_photo = identity.get("profile_photo_url", "")
        if new_photo != self._owner_photo_url:
            self._owner_photo_url = new_photo
            if hasattr(self, "_state_monitor") and self._state_monitor and new_photo:
                self._state_monitor.set_owner_photo(new_photo)
        # Drop the Gemini Live connection so it reconnects with fresh system prompt
        if self._gemini and self._gemini.is_connected:
            await self._gemini.disconnect()
        logger.info("SessionManager: context refreshed live (new language/tone will apply immediately)")

    async def _speak_verbatim(self, text: str, canvas: bool = False) -> None:
        """Deliver a response via Gemini Live.

        canvas=True  → brief warm acknowledgment ("I've put it on the canvas, take a look")
        canvas=False → speak the full content directly as the companion's reply
        """
        # Block watchman for the lifetime of this verbatim response, just like voice_query.
        self._is_responding = True
        if canvas:
            words = text.split()
            snippet = " ".join(words[:120])
            prompt = (
                "You've just displayed detailed content on the user's canvas screen. "
                f"The content begins: \"{snippet}\"\n\n"
                "Speak a warm, natural 1–2 sentence response — briefly acknowledge what "
                "you've prepared and invite them to read it. Do NOT read the full text."
            )
        else:
            # Voice-only: speak the content itself. Send it as the reply to deliver.
            prompt = (
                "Deliver this response to the user naturally, as their companion speaking aloud. "
                "Speak it completely and warmly — do not summarise, do not cut short:\n\n"
                f"{text}"
            )
        try:
            async with self._gemini_lock:
                await self.ensure_gemini_connected()
                self._suppress_audio = False
                await self._gemini.query(prompt)
                self._reset_gemini_idle_timer()
            # NOTE: do NOT suppress immediately after query() — audio tasks created during
            # query() are still queued and need to run. Suppressing here truncates the
            # tail of every response. Instead, yield for 500ms so those tasks execute.
            await asyncio.sleep(0.5)
            # Gate stays open — next voice_query or _speak will manage it from here
        except asyncio.CancelledError:
            # Do NOT reset _suppress_audio — voice_query manages it from here.
            # Do NOT reset _is_responding — voice_query sets it True immediately.
            logger.info("SessionManager: speak_verbatim cancelled")
        except Exception as exc:
            logger.warning("SessionManager: speak_verbatim failed: %s", exc)
            self._suppress_audio = False
            self._is_responding = False
        else:
            # Normal completion — release the block so watchman can speak again
            self._is_responding = False

    async def voice_query(self, text: str) -> None:
        """Natural voice conversation via Gemini Live.

        Generation counter (_voice_gen) prevents a stale CancelledError from a
        previous task from closing the audio gate on the current active response —
        which was the cause of responses not completing.

        Timing:
          _suppress_audio is already True when this task starts (set synchronously
          by the ws_observe handler before create_task). We:
          1. Send text (Gemini interrupts old generation immediately on the server).
          2. Keep suppress=True for 300ms (drain window — old audio still in transit
             is caught by the inline _receive_loop check and never forwarded).
          3. Open gate. New audio plays cleanly.
        """
        self._voice_gen += 1
        my_gen = self._voice_gen
        # Block watchman's _speak() for the lifetime of this user query.
        # _is_responding was never set after _respond() was removed — that was
        # the root cause of watchman speaking concurrently with voice_query,
        # producing two simultaneous Gemini generations on the second query.
        self._is_responding = True

        try:
            # Hold the lock for connect + send so _speak() can never fire a concurrent
            # Gemini call between our suppress and our text arriving at Gemini.
            async with self._gemini_lock:
                if not (self._gemini and self._gemini.is_connected):
                    await self.ensure_gemini_connected()
                # _suppress_audio already True (set by ws_observe). Send while suppressed:
                # Gemini receives this and immediately stops any prior generation.
                await self._gemini.send_text(text)
            self._reset_gemini_idle_timer()

            # 200ms drain: old audio arrives at _receive_loop suppressed (inline check).
            # Gemini stops sending old audio within ~100ms of receiving new text.
            # By 200ms only new-turn audio is arriving.
            await asyncio.sleep(0.2)

            # Open gate — but only if we're still the current generation.
            if self._voice_gen == my_gen:
                self._suppress_audio = False

            # Stay alive so barge-in CancelledError can suppress our audio.
            await asyncio.sleep(30)

        except asyncio.CancelledError:
            if self._voice_gen == my_gen:
                self._suppress_audio = True
            logger.info("SessionManager: voice_query cancelled (gen=%d)", my_gen)

        except Exception as exc:
            logger.warning("SessionManager: voice_query failed: %s", exc)
            if self._voice_gen == my_gen:
                self._suppress_audio = False

        finally:
            # Release the block only if we're still the active generation.
            # A newer voice_query has already set _is_responding = True for itself.
            if self._voice_gen == my_gen:
                self._is_responding = False

    async def _speak(self, text: str) -> None:
        """Ensure Gemini Live is open, then speak the text aloud.
        Acquires the lock so it never overlaps with a concurrent query or greeting.
        Skips if a user response is currently in progress.
        """
        if self._is_responding:
            logger.info("SessionManager: _speak skipped — user response in progress")
            return
        if self._speak_task and not self._speak_task.done():
            logger.info("SessionManager: _speak skipped — speak_task still active")
            return
        async with self._gemini_lock:
            # Double-check after acquiring lock — voice_query holds this lock during send_text,
            # so if we had to wait for it, the user may have started speaking by now.
            if self._is_responding or (self._speak_task and not self._speak_task.done()):
                logger.info("SessionManager: _speak aborted inside lock — response started")
                return
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
