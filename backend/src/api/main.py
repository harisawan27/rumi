import asyncio
import logging
import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

from src.auth.firebase_auth import verify_id_token, AuthError  # noqa: E402

app = FastAPI(title="Project Rumi — Rumi Core", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", os.getenv("FRONTEND_URL", "")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def get_current_uid(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = verify_id_token(token)
        return decoded["uid"]
    except AuthError as exc:
        msg = str(exc)
        if "UNAUTHORISED_USER" in msg:
            raise HTTPException(status_code=403, detail="UNAUTHORISED_USER")
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup():
    logger.info("[RUMI CORE] Initializing Identity Protocol...")
    uid = os.getenv("AUTHORISED_USER_UID", "")
    if uid:
        logger.warning(
            "AUTHORISED_USER_UID is set (%s) — only that user can sign in. "
            "Remove it from .env to enable multi-user mode.", uid
        )
    else:
        logger.info("[RUMI CORE] Multi-user mode active — identity layer ready.")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Auth verify
# ---------------------------------------------------------------------------

from pydantic import BaseModel  # noqa: E402


class VerifyRequest(BaseModel):
    id_token: str


@app.post("/auth/verify")
def auth_verify(body: VerifyRequest):
    try:
        decoded = verify_id_token(body.id_token)
    except AuthError as exc:
        msg = str(exc)
        if "UNAUTHORISED_USER" in msg:
            raise HTTPException(status_code=403, detail="UNAUTHORISED_USER")
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    from src.identity.identity_loader import load_core_identity, IdentityNotFoundError
    try:
        identity = load_core_identity(decoded["uid"])
    except IdentityNotFoundError:
        name = decoded.get("name", "")
    else:
        name = identity.get("name", "")

    return {"uid": decoded["uid"], "name": name, "authenticated": True}


# ---------------------------------------------------------------------------
# Identity (T016)
# ---------------------------------------------------------------------------

@app.get("/identity")
def get_identity(uid: str = Depends(get_current_uid)):
    from src.identity.identity_loader import load_core_identity, IdentityNotFoundError
    try:
        return load_core_identity(uid)
    except IdentityNotFoundError:
        raise HTTPException(status_code=404, detail="IDENTITY_NOT_FOUND")
    except Exception:
        raise HTTPException(status_code=503, detail="FIRESTORE_UNAVAILABLE")


class IdentityUpdate(BaseModel):
    model_config = {"extra": "allow"}   # forward-compatible — any new profile field saves cleanly

    name: str = ""
    full_name: str = ""
    age: int | None = None
    location: str = ""
    roles: list[str] = []
    projects: list[dict] = []
    interests: list[str] = []
    work_style: str = ""
    focus_breakers: list[str] = []
    communication_preference: str = ""
    faith: str = ""
    salah_awareness: str = ""
    turkish_goal: str = ""
    leisure: str = ""
    immediate_goal: str = ""
    long_term_goal: str = ""
    driving_fear: str = ""
    wellness_trigger: str = ""
    student_context: str = ""
    environment: str = ""
    # Language & speech preferences
    companion_language: str = ""
    expression_styles: list[str] = []
    companion_tone: str = "casual"
    companion_style: str = ""
    # Timezone (auto-detected by browser — never ask the user)
    timezone: str = "UTC"
    # Profile photo (Firebase Storage URL)
    profile_photo_url: str = ""


@app.put("/identity", status_code=200)
def put_identity(body: IdentityUpdate, uid: str = Depends(get_current_uid)):
    from src.identity.identity_loader import save_identity
    try:
        save_identity(uid, body.model_dump(exclude_none=True))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")
    return {"status": "saved"}


# ---------------------------------------------------------------------------
# Session Summaries (T022)
# ---------------------------------------------------------------------------

@app.get("/session-summaries")
def get_session_summaries(
    limit: int = 3,
    uid: str = Depends(get_current_uid),
):
    from src.identity.identity_loader import load_session_summaries
    import os
    max_depth = int(os.getenv("SESSION_SUMMARY_DEPTH", "3"))
    effective_limit = min(limit, 10, max_depth)
    try:
        summaries = load_session_summaries(uid, limit=effective_limit)
    except Exception:
        raise HTTPException(status_code=503, detail="FIRESTORE_UNAVAILABLE")
    return {"summaries": summaries, "count": len(summaries)}


# ---------------------------------------------------------------------------
# Session lifecycle (T030 + T040 + T042)
# ---------------------------------------------------------------------------

# Per-user session managers — one SessionManager per authenticated user
from src.session.session_manager import SessionManager  # noqa: E402

_session_managers: dict[str, SessionManager] = {}


def _get_session_manager(uid: str) -> SessionManager:
    if uid not in _session_managers:
        _session_managers[uid] = SessionManager()
    return _session_managers[uid]


@app.post("/session/start", status_code=201)
async def start_session(uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager(uid)
    # End any stale active session (e.g. page refresh without clean close)
    if mgr.status == "active":
        try:
            await mgr.end_session()
        except Exception:
            pass
        _session_managers[uid] = SessionManager()
        mgr = _session_managers[uid]
    try:
        session_id = await mgr.start_session(uid)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=f"SESSION_START_FAILED: {exc}")
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }


@app.put("/session/{session_id}/pause")
async def pause_session(session_id: str, uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager(uid)
    await mgr.pause_session()
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "status": "paused",
        "paused_at": datetime.now(timezone.utc).isoformat(),
    }


@app.put("/session/{session_id}/resume")
async def resume_session(session_id: str, uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager(uid)
    await mgr.resume_session()
    mgr.start_watchman()
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "status": "active",
        "resumed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/session/refresh-context")
async def refresh_session_context(uid: str = Depends(get_current_uid)):
    """Hot-reload identity for the active session — call after profile changes."""
    if uid not in _session_managers:
        return {"status": "no_active_session"}
    mgr = _session_managers[uid]
    if mgr.status not in ("active", "paused"):
        return {"status": "session_not_active"}
    await mgr.refresh_context()
    return {"status": "refreshed"}


@app.post("/session/{session_id}/end", status_code=202)
async def end_session(session_id: str, uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager(uid)
    await mgr.end_session()
    # Remove from active managers so next start gets a clean instance
    _session_managers.pop(uid, None)
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "status": "ended",
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "summary_status": "generating",
    }


# ---------------------------------------------------------------------------
# Interactions (T030)
# ---------------------------------------------------------------------------

class InteractionRequest(BaseModel):
    session_id: str
    trigger_type: str
    triggered_at: str
    intervention_text: str
    user_response: str
    response_at: str | None = None


@app.post("/interactions", status_code=201)
def record_interaction(body: InteractionRequest, uid: str = Depends(get_current_uid)):
    if body.trigger_type not in ("A", "B", "C", "E"):
        raise HTTPException(status_code=422, detail="trigger_type must be A, B, C or E")
    if body.user_response not in ("accepted", "dismissed", "no_response"):
        raise HTTPException(status_code=422, detail="invalid user_response value")

    from src.memory.interaction_log import log_interaction
    from datetime import datetime, timezone
    interaction_id = log_interaction(
        uid=uid,
        session_id=body.session_id,
        trigger_type=body.trigger_type,
        intervention_text=body.intervention_text,
        user_response=body.user_response,
    )
    return {
        "interaction_id": interaction_id,
        "session_id": body.session_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Debug — manual trigger (remove before submission)
# ---------------------------------------------------------------------------

@app.post("/debug/trigger/{trigger_type}", status_code=200)
async def debug_trigger(trigger_type: str, uid: str = Depends(get_current_uid)):
    """Fire any trigger manually to test the intervention pipeline."""
    if trigger_type not in ("A", "B", "C", "E"):
        raise HTTPException(status_code=422, detail="trigger_type must be A B C or E")
    mgr = _get_session_manager(uid)
    if mgr.status != "active":
        raise HTTPException(status_code=409, detail="No active session")
    dispatch = {
        "A": mgr._fire_trigger_a,
        "B": mgr._fire_trigger_b,
        "C": mgr._fire_trigger_c,
        "E": mgr._fire_trigger_e,
    }
    asyncio.create_task(dispatch[trigger_type]())
    return {"fired": trigger_type}


# ---------------------------------------------------------------------------
# Known People (face recognition social graph)
# ---------------------------------------------------------------------------

class KnownPersonCreate(BaseModel):
    name:         str
    relationship: str
    photo_url:    str = ""
    notes:        str = ""
    added_by:     str = "manual"   # "manual" | "rumi_introduction"


class KnownPersonUpdate(BaseModel):
    name:         str | None = None
    relationship: str | None = None
    photo_url:    str | None = None
    notes:        str | None = None
    status:       str | None = None


@app.get("/known-people")
def list_known_people(uid: str = Depends(get_current_uid)):
    from src.memory.known_people import get_known_people
    try:
        return {"people": get_known_people(uid)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.post("/known-people", status_code=201)
def create_known_person(body: KnownPersonCreate, uid: str = Depends(get_current_uid)):
    from src.memory.known_people import add_known_person
    try:
        person_id = add_known_person(uid, body.model_dump())
        return {"id": person_id, "status": "created"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.put("/known-people/{person_id}")
def update_known_person_route(
    person_id: str,
    body: KnownPersonUpdate,
    uid: str = Depends(get_current_uid),
):
    from src.memory.known_people import update_known_person
    try:
        update_known_person(uid, person_id, body.model_dump(exclude_none=True))
        return {"status": "updated"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.delete("/known-people/{person_id}", status_code=200)
def delete_known_person_route(person_id: str, uid: str = Depends(get_current_uid)):
    from src.memory.known_people import delete_known_person
    try:
        delete_known_person(uid, person_id)
        return {"status": "deleted"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


# ---------------------------------------------------------------------------
# Canvas helpers (Phase 3 + 5)
# ---------------------------------------------------------------------------

def _make_title(query: str, max_words: int = 5) -> str:
    """Derive a short canvas title from the user query."""
    q = query.strip().rstrip("?!.")
    words = q.split()
    if len(words) <= max_words:
        return q.title()
    return " ".join(words[:max_words]).title() + "\u2026"


async def _flash_text_only(text: str, system_prompt: str = "") -> str:
    """Call Gemini Flash for a text-only response. Returns markdown string.
    Tries gemini-2.5-flash first, falls back to gemini-2.0-flash on failure.
    system_prompt carries the user's identity/memory so Flash knows who it's talking to.
    """
    from google import genai as _genai

    identity_block = f"{system_prompt}\n\n---\n\n" if system_prompt else ""
    prompt = (
        f"{identity_block}"
        f'The user asked: "{text}"\n\n'
        "Respond as Rumi in well-structured Markdown. Use the identity and memory above "
        "to give a personalised answer — mention the user by name and reference their "
        "projects or context where relevant. If it is a creative request (poem, story), "
        "write it beautifully formatted. If it is a question or task, give a thorough "
        "step-by-step answer with headings. Be the Sufi-Engineer — precise and soulful."
    )
    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            logger.info("_flash_text_only: trying %s for: %.60s", model, text)
            client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
            )
            result = (response.text or "").strip()
            logger.info("_flash_text_only: %s returned %d chars", model, len(result))
            if result:
                return result
        except Exception as exc:
            logger.warning("_flash_text_only: %s failed: %s", model, exc)
    return ""


async def _flash_canvas_task(text: str, image_b64: str | None, ws) -> None:
    """Generate canvas content via Flash and push text_response to frontend.
    Runs as a background task — never blocks voice response.
    """
    import json as _json
    try:
        content = await (_flash_with_image(text, image_b64) if image_b64 else _flash_text_only(text))
        if content and len(content) > 30:
            await ws.send_text(_json.dumps({
                "type": "text_response",
                "title": _make_title(text),
                "content": content,
                "content_type": "markdown",
            }))
            logger.info("_flash_canvas_task: sent %d chars", len(content))
    except Exception as exc:
        logger.warning("_flash_canvas_task: failed: %s", exc)


async def _flash_with_image(text: str, image_b64: str, system_prompt: str = "") -> str:
    """Call Gemini Flash multimodal (notebook mode). Returns markdown string.
    PRIVACY_CHECK: image processed ephemerally — never persisted.
    """
    import base64 as _b64
    from google import genai as _genai
    from google.genai import types as _types

    client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    image_bytes = _b64.b64decode(image_b64)
    identity_block = f"{system_prompt}\n\n---\n\n" if system_prompt else ""
    text_prompt = (
        f"{identity_block}"
        f'The user asked: "{text}"\n\n'
        "A live camera frame is attached as ambient context. "
        "IMPORTANT: Do NOT describe the camera image unless it is directly relevant "
        "to answering the question (e.g. the user is holding up a document, math problem, "
        "diagram, or code). If the image just shows the user's face or general environment, "
        "ignore it completely and answer the text question directly.\n\n"
        "Respond as Rumi in well-structured Markdown. Use the identity context above "
        "to personalise your answer. Be the Sufi-Engineer — precise and soulful."
    )
    contents = [
        _types.Part(inline_data=_types.Blob(data=image_bytes, mime_type="image/jpeg")),
        _types.Part(text=text_prompt),
    ]
    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            response = await client.aio.models.generate_content(
                model=model, contents=contents
            )
            result = (response.text or "").strip()
            if result:
                return result
        except Exception as exc:
            logger.warning("_flash_with_image: %s failed: %s", model, exc)
    return ""


async def _flash_followup(text: str, context: list, image_b64: str | None, system_prompt: str = "") -> str:
    """Generate a follow-up response with conversation context."""
    from google import genai as _genai
    from google.genai import types as _types
    import base64 as _b64

    client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    identity_block = f"{system_prompt}\n\n---\n\n" if system_prompt else ""

    context_block = ""
    if context:
        lines = []
        for ex in context:
            lines.append(f'Q: {ex.get("q", "")}\nA: {ex.get("a", "")}')
        context_block = "Previous conversation context:\n" + "\n\n".join(lines) + "\n\n---\n\n"

    text_prompt = (
        f"{identity_block}"
        f"{context_block}"
        f'Follow-up question: "{text}"\n\n'
        "Continue the conversation as Rumi. Reference previous context where relevant. "
        "Respond in well-structured Markdown. Be precise and soulful."
    )
    parts: list = []
    if image_b64:
        parts.append(_types.Part(inline_data=_types.Blob(data=_b64.b64decode(image_b64), mime_type="image/jpeg")))
    parts.append(_types.Part(text=text_prompt))

    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            response = await client.aio.models.generate_content(model=model, contents=parts)
            result = (response.text or "").strip()
            if result:
                return result
        except Exception as exc:
            logger.warning("_flash_followup: %s failed: %s", model, exc)
    return ""


# ---------------------------------------------------------------------------
# Canvas history — Firestore persistence (cap 20 per user)
# ---------------------------------------------------------------------------

def _do_save_canvas_entry(uid: str, query: str, title: str, content: str, content_type: str) -> None:
    """Synchronous Firestore write — run via executor to avoid blocking the event loop."""
    from src.memory.firestore_client import get_db
    from datetime import datetime, timezone
    db = get_db()
    col = db.collection("users").document(uid).collection("canvas_history")
    col.add({
        "query": query,
        "title": title,
        "content": content,
        "content_type": content_type,
        "timestamp": datetime.now(timezone.utc),
    })
    # Trim oldest beyond 20
    docs = list(col.order_by("timestamp", direction="DESCENDING").stream())
    for doc in docs[20:]:
        doc.reference.delete()


async def _save_canvas_entry(uid: str, query: str, title: str, content: str, content_type: str) -> None:
    """Persist a canvas answer to Firestore without blocking the event loop."""
    try:
        await asyncio.get_event_loop().run_in_executor(
            None, _do_save_canvas_entry, uid, query, title, content, content_type
        )
    except Exception as exc:
        logger.warning("_save_canvas_entry: failed: %s", exc)


def _load_canvas_history(uid: str, limit: int = 20) -> list:
    """Load canvas history from Firestore, oldest-first for nav order."""
    try:
        from src.memory.firestore_client import get_db
        db = get_db()
        docs = list(
            db.collection("users").document(uid).collection("canvas_history")
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        items = []
        for doc in reversed(docs):  # chronological order
            d = doc.to_dict()
            ts = d.get("timestamp")
            items.append({
                "query": d.get("query", ""),
                "title": d.get("title", ""),
                "content": d.get("content", ""),
                "content_type": d.get("content_type", "markdown"),
                "timestamp": ts.strftime("%b %d") if ts else "",
            })
        return items
    except Exception as exc:
        logger.warning("_load_canvas_history: failed: %s", exc)
        return []


@app.get("/canvas/history")
async def get_canvas_history(uid: str = Depends(get_current_uid)):
    """REST endpoint — lets frontend fetch history at page load without WS timing dependency."""
    items = await asyncio.get_event_loop().run_in_executor(None, _load_canvas_history, uid)
    return {"items": items}


# ---------------------------------------------------------------------------
# WebSocket observe (T030 contract)
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect  # noqa: E402
import json  # noqa: E402


@app.websocket("/ws/observe")
async def ws_observe(websocket: WebSocket, session_id: str, token: str):
    try:
        decoded = verify_id_token(token)
    except AuthError:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    uid = decoded["uid"]
    mgr = _get_session_manager(uid)
    mgr._websocket = websocket

    # Send canvas history FIRST — before Gemini connects so frontend shows
    # history immediately without waiting for the Gemini handshake delay
    try:
        history = await asyncio.get_event_loop().run_in_executor(
            None, _load_canvas_history, uid
        )
        if history:
            await websocket.send_text(json.dumps({"type": "canvas_history", "items": history}))
            logger.info("ws_observe: sent %d canvas history items", len(history))
    except Exception as exc:
        logger.warning("ws_observe: canvas_history send failed: %s", exc)

    # Connect Gemini Live API (can take a few seconds — history already sent above)
    try:
        await mgr.connect_gemini()
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "code": "GEMINI_DISCONNECTED", "message": str(exc)}))
        logger.warning("ws_observe: Gemini connect failed: %s", exc)

    # Keepalive ping every 30s
    async def _ping():
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break

    ping_task = asyncio.create_task(_ping())
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "pong":
                pass
            elif msg.get("type") == "frame":
                import base64
                frame_bytes = base64.b64decode(msg["data"])
                if mgr.gemini and mgr.gemini.is_connected:
                    await mgr.gemini.send_frame(frame_bytes)
                # Update CodingBlockTracker with frame hash (T034/T035)
                if hasattr(mgr, "_coding_block_tracker") and mgr._coding_block_tracker:
                    mgr._coding_block_tracker.update_frame(frame_bytes)
                # Update StateMonitor with latest frame for VisionClient analysis
                if hasattr(mgr, "_state_monitor") and mgr._state_monitor:
                    mgr._state_monitor.update_frame(frame_bytes)
            elif msg.get("type") == "screen_frame":
                import base64
                screen_bytes = base64.b64decode(msg["data"])
                if hasattr(mgr, "_state_monitor") and mgr._state_monitor:
                    mgr._state_monitor.update_screen_frame(screen_bytes)
                mgr._latest_screen_frame = screen_bytes
            elif msg.get("type") == "intervention_response":
                # Update interaction response in Firestore
                from src.memory.firestore_client import get_db
                db = get_db()
                interaction_id = msg.get("interaction_id")
                response = msg.get("response")
                if interaction_id and response:
                    from datetime import datetime, timezone
                    db.collection("users").document(decoded["uid"]).collection(
                        "sessions"
                    ).document(session_id).collection("interactions").document(
                        interaction_id
                    ).update({"user_response": response, "response_at": datetime.now(timezone.utc)})
            elif msg.get("type") == "talk_start":
                # Pre-connect Gemini then signal speech start
                await mgr.ensure_gemini_connected()
                if mgr.gemini and mgr.gemini.is_connected:
                    await mgr.gemini.activity_start()
            elif msg.get("type") == "audio":
                import base64
                pcm_bytes = base64.b64decode(msg["data"])
                if mgr.gemini and mgr.gemini.is_connected:
                    await mgr.gemini.send_audio(pcm_bytes)
                    mgr._reset_gemini_idle_timer()
            elif msg.get("type") == "audio_end":
                # User released mic — signal speech end, Gemini generates reply
                if mgr.gemini and mgr.gemini.is_connected:
                    await mgr.gemini.activity_end()
                else:
                    logger.warning("audio_end received but Gemini not connected — reply lost")
            elif msg.get("type") == "user_text":
                # Web Speech API transcript — Flash generates text (single source of truth),
                # Live speaks it verbatim, canvas opens 1500ms later (voice-first UX).
                text = msg.get("text", "").strip()
                image_b64 = msg.get("image")  # base64 JPEG or None
                is_followup = bool(msg.get("is_followup", False))
                followup_context = msg.get("context", [])  # list of {q, a} dicts
                if text:
                    # Safety: reset stuck flag if no active speak task
                    if mgr._is_responding and (mgr._speak_task is None or mgr._speak_task.done()):
                        logger.warning("ws_observe: _is_responding stuck — resetting")
                        mgr._is_responding = False
                    if mgr._is_responding:
                        logger.info("ws_observe: duplicate user_text dropped — already responding")
                    else:
                        async def _respond(t: str = text, img=image_b64, _ws=websocket, _is_fu=is_followup, _ctx=followup_context) -> None:
                            mgr._is_responding = True
                            mgr._suppress_audio = True
                            try:
                                gt = mgr._greeting_task
                                if gt and not gt.done():
                                    gt.cancel()

                                try:
                                    await asyncio.sleep(0.3)
                                    await _ws.send_text(json.dumps({"type": "audio_interrupt"}))
                                except Exception:
                                    pass
                                mgr._suppress_audio = False

                                sys_prompt = mgr._system_prompt or ""
                                screen_b64: str | None = None
                                if hasattr(mgr, "_latest_screen_frame") and mgr._latest_screen_frame:
                                    import base64 as _b64_inner
                                    screen_b64 = _b64_inner.b64encode(mgr._latest_screen_frame).decode()
                                effective_img = img or screen_b64

                                content = ""
                                try:
                                    if _is_fu and _ctx:
                                        content = await _flash_followup(t, _ctx, effective_img, sys_prompt)
                                    elif effective_img:
                                        content = await _flash_with_image(t, effective_img, sys_prompt)
                                    else:
                                        content = await _flash_text_only(t, sys_prompt)
                                except Exception as exc:
                                    logger.warning("ws_observe: Flash threw: %s", exc)

                                if not content or len(content) <= 30:
                                    content = "I'm having trouble reaching my thoughts right now. Please try again in a moment."

                                title = _make_title(t)
                                await _ws.send_text(json.dumps({
                                    "type": "text_response",
                                    "title": title,
                                    "content": content,
                                    "content_type": "markdown",
                                    "append": _is_fu,
                                }))
                                logger.info("ws_observe: text_response sent (%d chars, follow_up=%s)", len(content), _is_fu)
                                if not _is_fu:
                                    asyncio.create_task(_save_canvas_entry(mgr._uid, t, title, content, "markdown"))
                                mgr._speak_task = asyncio.create_task(mgr._speak_verbatim(content))
                            except BaseException as exc:
                                logger.warning("ws_observe: _respond failed: %s", exc)
                            finally:
                                mgr._is_responding = False
                                mgr._suppress_audio = False

                        asyncio.create_task(_respond())
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        mgr._websocket = None
        if hasattr(mgr, "_state_monitor") and mgr._state_monitor:
            mgr._state_monitor.set_websocket(None)
            mgr._state_monitor.stop()
