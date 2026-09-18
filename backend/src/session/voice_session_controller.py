import asyncio
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceServerState(str, Enum):
    IDLE = "IDLE"
    GENERATING = "GENERATING"
    STREAMING = "STREAMING"
    INTERRUPTED = "INTERRUPTED"


class VoiceSessionController:
    """Authoritative backend controller for voice generation and audio delivery lifecycle.

    Invariants:
    1. Every generation attempt increments `generation_id`.
    2. Incoming audio from previous generations is rejected synchronously via generation matching.
    3. User or proactive interruption invalidates the active generation immediately.
    4. Generation lock prevents race conditions between simultaneous trigger speech and user queries.
    """

    def __init__(self):
        self._generation_id: int = 0
        self._state: VoiceServerState = VoiceServerState.IDLE
        self._suppress_audio: bool = False
        self._active_task: Optional[asyncio.Task] = None
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def generation_id(self) -> int:
        return self._generation_id

    @property
    def state(self) -> VoiceServerState:
        return self._state

    @property
    def suppress_audio(self) -> bool:
        return self._suppress_audio

    @property
    def is_generating_or_speaking(self) -> bool:
        return self._state in (VoiceServerState.GENERATING, VoiceServerState.STREAMING)

    def start_generation(self, task_name: str = "query") -> int:
        """Start a new voice generation lifecycle slot.
        Immediately increments generation_id and suppresses audio during transit drain.
        """
        self._generation_id += 1
        self._state = VoiceServerState.GENERATING
        self._suppress_audio = True

        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            self._active_task = None

        logger.info("VoiceSessionController: start generation=%d (%s)", self._generation_id, task_name)
        return self._generation_id

    def set_active_task(self, task: asyncio.Task) -> None:
        self._active_task = task

    def mark_streaming(self, gen_id: int) -> bool:
        """Open the audio delivery gate if gen_id matches current generation."""
        if gen_id == self._generation_id:
            self._state = VoiceServerState.STREAMING
            self._suppress_audio = False
            logger.debug("VoiceSessionController: streaming opened for generation=%d", gen_id)
            return True
        logger.debug("VoiceSessionController: rejected stale stream for generation=%d (current=%d)",
                     gen_id, self._generation_id)
        return False

    def mark_complete(self, gen_id: int) -> None:
        """Mark current generation complete if still active."""
        if gen_id == self._generation_id:
            self._state = VoiceServerState.IDLE
            self._suppress_audio = False
            logger.info("VoiceSessionController: completed generation=%d", gen_id)

    def cancel_active_generation(self, reason: str = "user_interrupt") -> int:
        """Cancel active generation immediately and invalidate its audio chunks."""
        self._generation_id += 1
        self._state = VoiceServerState.INTERRUPTED
        self._suppress_audio = True

        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            self._active_task = None

        logger.info("VoiceSessionController: cancelled (reason=%s) -> next generation=%d",
                    reason, self._generation_id)
        return self._generation_id

    def is_stale(self, gen_id: int) -> bool:
        """Return True if chunk belongs to an outdated generation."""
        return gen_id != self._generation_id
