import asyncio
import logging
from typing import Optional, Callable

import os
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Gemini 2.5 Flash Native Audio — supports bidiGenerateContent (Live API)
LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"

# Sentinel to signal turn complete in the response queue
_TURN_COMPLETE = object()


class GeminiLiveClient:
    """Manages a single Gemini Multimodal Live API WebSocket session.

    Uses a single background receive loop so query() and audio callbacks
    never conflict over session.receive().
    """

    def __init__(self, api_key: str):
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_REGION", "asia-south1")
        if project:
            # Vertex AI — regional routing to asia-south1 (Mumbai)
            self._client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )
        else:
            # Fallback: standard Gemini API — Live API requires v1alpha
            self._client = genai.Client(
                api_key=api_key,
                http_options={"api_version": "v1alpha"},
            )
        self._session = None
        self._session_ctx = None
        self._system_prompt: Optional[str] = None
        self._connected = False
        # Single queue for all Gemini responses
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._receive_task: Optional[asyncio.Task] = None
        self._on_audio: Optional[Callable] = None

    async def connect(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=system_prompt,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                )
            ),
        )
        self._session_ctx = self._client.aio.live.connect(
            model=LIVE_MODEL, config=config
        )
        self._session = await self._session_ctx.__aenter__()
        self._connected = True
        # Start the single receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("GeminiLiveClient: session connected, receive loop started")

    async def _receive_loop(self) -> None:
        """Single loop that drains ALL responses from Gemini.

        Text responses go into the queue for query() to consume.
        Audio responses call self._on_audio directly.
        """
        try:
            async for response in self._session.receive():
                # ── Text / transcript ─────────────────────────────────────
                # Native audio models send audio only; transcript may come
                # via server_content.output_transcription or not at all.
                text = response.text or ""
                if not text and response.server_content:
                    sc = response.server_content
                    if hasattr(sc, "output_transcription") and sc.output_transcription:
                        text = sc.output_transcription.text or ""
                if text:
                    await self._response_queue.put(("text", text))

                # ── Audio ─────────────────────────────────────────────────
                # Try shorthand first, then walk parts for inline_data
                audio_bytes = response.data or None
                if not audio_bytes and response.server_content:
                    sc = response.server_content
                    if sc.model_turn and sc.model_turn.parts:
                        for part in sc.model_turn.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                mime = part.inline_data.mime_type or ""
                                if "audio" in mime:
                                    audio_bytes = part.inline_data.data
                                    break

                if audio_bytes and self._on_audio:
                    logger.info("GeminiLiveClient: forwarding %d audio bytes", len(audio_bytes))
                    asyncio.create_task(self._on_audio(audio_bytes))
                elif not audio_bytes and response.server_content:
                    logger.info("GeminiLiveClient: server_content received, no audio detected")

                # ── Turn complete ─────────────────────────────────────────
                if (
                    response.server_content
                    and response.server_content.turn_complete
                ):
                    await self._response_queue.put(("done", None))
        except Exception as exc:
            logger.warning("GeminiLiveClient: receive loop ended: %s", exc)
        finally:
            await self._response_queue.put(("done", None))

    def set_audio_callback(self, callback: Callable) -> None:
        self._on_audio = callback

    async def disconnect(self) -> None:
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as exc:
                logger.warning("GeminiLiveClient: disconnect error: %s", exc)
            finally:
                self._session = None
                self._session_ctx = None
                self._connected = False
                logger.info("GeminiLiveClient: disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send raw PCM audio (16-bit, 16kHz, mono). PRIVACY: never persisted."""
        if not self._session:
            return
        await self._session.send(
            input=types.LiveClientRealtimeInput(
                media_chunks=[types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")]
            )
        )

    async def send_frame(self, frame_bytes: bytes) -> None:
        """Send a JPEG frame. PRIVACY_CHECK: ephemeral — never written to disk or Firestore."""
        if not self._session:
            return
        logger.debug("PRIVACY_CHECK: sending frame ephemerally to Gemini WebSocket")
        await self._session.send(
            input=types.LiveClientRealtimeInput(
                media_chunks=[types.Blob(data=frame_bytes, mime_type="image/jpeg")]
            )
        )

    async def query(self, prompt: str, timeout: float = 15.0) -> str:
        """Send a text prompt and collect the full response via the shared queue."""
        if not self._session:
            raise RuntimeError("Not connected")
        # Drain any stale items from a previous turn
        while not self._response_queue.empty():
            self._response_queue.get_nowait()

        await self._session.send(input=prompt, end_of_turn=True)

        parts = []
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("GeminiLiveClient: query timed out")
                break
            try:
                kind, data = await asyncio.wait_for(
                    self._response_queue.get(), timeout=remaining
                )
            except asyncio.TimeoutError:
                break
            if kind == "text":
                parts.append(data)
            elif kind == "done":
                break
        return "".join(parts)

    async def reconnect(self) -> None:
        delays = [1, 2, 4, 8, 16, 30]
        for delay in delays:
            try:
                await self.disconnect()
                if self._system_prompt:
                    await self.connect(self._system_prompt)
                logger.info("GeminiLiveClient: reconnected after %ds", delay)
                return
            except Exception as exc:
                logger.warning("GeminiLiveClient: reconnect failed in %ds: %s", delay, exc)
                await asyncio.sleep(delay)
        raise RuntimeError("GeminiLiveClient: all reconnect attempts failed")
