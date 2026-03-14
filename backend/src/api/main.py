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


def _extract_smart_json(raw: str) -> dict | None:
    """Robustly extract the smart-routing JSON from Gemini output."""
    import re
    # Strip markdown fences
    clean = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    # Try full parse
    try:
        return json.loads(clean)
    except Exception:
        pass
    # Find first {...} block containing canvas_needed
    match = re.search(r"\{[^{}]*\"canvas_needed\"[^{}]*\}", clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


_CANVAS_REF_PATTERNS = [
    r"[Ii](?:'ve| have) (?:written|put|placed|shared|displayed|noted) (?:it|this|the \w+(?:\s+\w+)?) (?:on|in|onto) the canvas[^.]*\.",
    r"[Pp]lease (?:check|see|look at) the canvas[^.]*\.",
    r"[Cc]heck (?:the )?canvas[^.]*\.",
    r"[Ii](?:'ll| will) (?:write|put|display|show) (?:it|this|that) (?:on|in) the canvas[^.]*\.",
    r"(?:on|in) the canvas for you[^.]*\.",
    r"[Ii] have (?:a )?technical (?:issue|difficulty|limitation)[^.]*canvas[^.]*\.",
]

def _sanitize_voice(content: str) -> str:
    """Strip canvas-referencing phrases from content that will be spoken aloud."""
    import re
    for pattern in _CANVAS_REF_PATTERNS:
        content = re.sub(pattern, "", content)
    return content.strip()


async def _flash_smart(
    text: str,
    image_b64: str | None,
    system_prompt: str,
    context: list | None = None,
    force_canvas: bool = False,
) -> dict:
    """Route query to canvas or voice, then generate content.

    Returns {"canvas_needed": bool, "title": str, "content": str}.
    Poetry/face queries are handled by dedicated callers before this is reached.
    force_canvas=True when an explicit file/image attachment is present.
    """
    from google import genai as _genai
    from google.genai import types as _types
    import base64 as _b64

    client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    identity_block = f"{system_prompt}\n\n---\n\n" if system_prompt else ""

    context_block = ""
    if context:
        lines = [f'Q: {ex.get("q","")}\nA: {ex.get("a","")}' for ex in context]
        context_block = "Conversation context:\n" + "\n\n".join(lines) + "\n\n---\n\n"

    force_note = (
        "\nNOTE: An image or file is attached — canvas_needed MUST be true.\n"
        if force_canvas else ""
    )

    routing_instruction = f"""{force_note}
You must respond with ONLY valid JSON — no text before or after, no markdown fences:
{{
  "canvas_needed": false,
  "title": "",
  "content": "your full response here"
}}

DECISION RULES for canvas_needed:
TRUE — response must be read, not just heard:
  • Code, technical solutions, debugging steps
  • Step-by-step instructions (3+ steps)
  • Structured comparisons, tables, lists
  • Math/logic problems solved in writing
  • User explicitly says: write, show, display, summarize in writing, research, solve
  • Any image or file is attached (auto-true)

FALSE — experienced by listening. This includes:
  • Casual conversation, gossip, emotional support, opinions
  • Greetings, encouragement, check-ins
  • Simple facts (sports results, time, weather, quick questions)
  • Anything the user asks to "tell", "say", "read", or "recite"
  • Real-time questions you can't answer (live scores, today's news) — just say
    you don't have live data verbally. Never route uncertainty to canvas.

When canvas_needed=false:
  - title = empty string
  - content = your full spoken response, plain text, NO markdown
  - NO length limit. Speak as long as the topic deserves naturally.
  - If you don't know something, say so out loud simply — do NOT mention canvas.
  - NEVER say "I'll write it", "check the canvas", "I've displayed", or similar.
  - The user ONLY hears your voice. Everything must be delivered verbally.

When canvas_needed=true:
  - title = 3-5 word summary
  - content = well-structured Markdown
"""

    image_note = (
        "\nA camera frame from the user's own webcam is attached. "
        "This camera belongs to the person whose identity is described above. "
        "If asked who is in front of the camera or who you see, identify them as the owner by name. "
        "Only express uncertainty if the face is clearly a different person.\n"
        if image_b64 else ""
    )
    full_prompt = (
        f"{identity_block}"
        f"{context_block}"
        f'User query: "{text}"\n'
        f"{image_note}"
        f"{routing_instruction}"
    )

    parts: list = []
    if image_b64:
        parts.append(_types.Part(inline_data=_types.Blob(data=_b64.b64decode(image_b64), mime_type="image/jpeg")))
    parts.append(_types.Part(text=full_prompt))

    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            response = await client.aio.models.generate_content(model=model, contents=parts)
            raw = (response.text or "").strip()
            data = _extract_smart_json(raw)
            if data and "content" in data:
                canvas = bool(data.get("canvas_needed", False))
                if force_canvas:
                    canvas = True
                logger.info("_flash_smart: canvas=%s model=%s chars=%d", canvas, model, len(data["content"]))
                return {
                    "canvas_needed": canvas,
                    "title": data.get("title", "") or (_make_title(text) if canvas else ""),
                    "content": data["content"],
                }
        except Exception as exc:
            logger.warning("_flash_smart: %s failed: %s", model, exc)

    return {"canvas_needed": False, "title": "", "content": ""}


# Keywords that route to the dedicated face identification path
_FACE_QUERY_KEYWORDS = [
    "who is in front", "who do you see", "who am i", "can you see me",
    "do you see me", "who is this", "look at me", "see me",
    "how do i look", "am i on camera", "what do i look",
]

# Keywords that bypass _flash_smart and go straight to voice recitation
_POETRY_KEYWORDS = [
    "couplet", "sher", "ghazal", "nazm", "poem", "poetry", "verse",
    "ghalib", "iqbal", "faiz", "mir taqi", "recite", "sunao",
    "suna", "padhao", "likho sher", "ek sher", "ruba", "rubaiyat",
]


# Stripped system prompt for guests — no owner identity, memory, or projects
_GUEST_SYSTEM_PROMPT = """\
You are Rumi, a warm and wise AI companion. You are currently speaking with a guest \
— someone other than the device owner. You have no information about who the owner is; \
their identity, projects, and personal memory are private and must never be disclosed.

Behaviour:
- Be genuinely helpful, warm, and conversational with the person in front of you.
- Answer general questions freely: knowledge, advice, poetry, coding, anything public.
- If asked about the owner's projects, schedule, personal goals, or private details, \
politely say you can only share that with the owner directly.
- Never mention the owner's name, location, work, or personal context.
- Keep responses natural — you are a companion, not a gatekeeper.
"""


async def _identify_face(text: str, image_b64: str, system_prompt: str) -> str:
    """Dedicated face identification — focused single-purpose call.
    Bypasses _flash_smart so routing and face analysis don't compete.
    Returns plain spoken text, no markdown, no JSON.
    """
    from google import genai as _genai
    from google.genai import types as _types
    import base64 as _b64

    client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = (
        f"{system_prompt}\n\n---\n\n"
        f'The user asked: "{text}"\n\n'
        "A live camera frame from the user's own webcam is attached. "
        "This is their personal device — the person in the frame is almost certainly "
        "the owner whose name and identity are described above. "
        "Look at the face in the image. Respond warmly as their AI companion: "
        "confirm it's them by name, maybe comment naturally on their expression, "
        "how they look today, or what you notice — like a friend would. "
        "2-4 sentences, plain spoken text, no markdown, no robotic description."
    )
    frame_bytes = _b64.b64decode(image_b64)
    contents = [
        _types.Part(inline_data=_types.Blob(data=frame_bytes, mime_type="image/jpeg")),
        _types.Part(text=prompt),
    ]
    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            response = await client.aio.models.generate_content(model=model, contents=contents)
            result = (response.text or "").strip()
            if result:
                logger.info("_identify_face: %s returned %d chars", model, len(result))
                return result
        except Exception as exc:
            logger.warning("_identify_face: %s failed: %s", model, exc)
    return ""


async def _recite_poem(text: str, system_prompt: str) -> str:
    """Dedicated poetry/couplet recitation — always voice, never canvas.
    Called directly so _flash_smart's routing logic never touches poetry.
    """
    from google import genai as _genai
    from google.genai import types as _types

    client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = (
        f"{system_prompt}\n\n---\n\n"
        f'The user asked: "{text}"\n\n'
        "Recite the requested poem, couplet, or verse in full. "
        "Deliver it as a companion speaking aloud — complete, unhurried, natural. "
        "Plain text only, no markdown, no asterisks. "
        "A brief warm line before or after is fine. "
        "Do NOT mention canvas, screen, writing, or displaying anything."
    )
    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            response = await client.aio.models.generate_content(
                model=model, contents=[_types.Part(text=prompt)],
            )
            result = (response.text or "").strip()
            if result:
                logger.info("_recite_poem: %s returned %d chars", model, len(result))
                return result
        except Exception as exc:
            logger.warning("_recite_poem: %s failed: %s", model, exc)
    return ""


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
            elif msg.get("type") == "audio_interrupt":
                # Frontend-initiated barge-in — cancel speak task immediately
                if mgr._speak_task and not mgr._speak_task.done():
                    mgr._speak_task.cancel()
                mgr._is_responding = False
                logger.info("ws_observe: audio_interrupt from frontend — speak task cancelled")
            elif msg.get("type") == "user_text":
                # Web Speech API transcript — Flash generates text (single source of truth),
                # Live speaks it verbatim, canvas opens 1500ms later (voice-first UX).
                text = msg.get("text", "").strip()
                image_b64 = msg.get("image")  # base64 JPEG or None
                is_followup = bool(msg.get("is_followup", False))
                followup_context = msg.get("context", [])  # list of {q, a} dicts
                if text:
                    import time as _time
                    _t0 = _time.perf_counter()
                    # Barge-in: if user speaks while we're processing, cancel current response
                    if mgr._is_responding:
                        logger.info("ws_observe: barge-in — cancelling active response for new query")
                        if mgr._speak_task and not mgr._speak_task.done():
                            mgr._speak_task.cancel()
                        mgr._is_responding = False
                        try:
                            await websocket.send_text(json.dumps({"type": "audio_interrupt"}))
                        except Exception:
                            pass
                    if True:
                        async def _respond(t: str = text, img=image_b64, _ws=websocket, _is_fu=is_followup, _ctx=followup_context, _req_t0=_t0) -> None:
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
                                # suppress_audio stays True — voice_query will set it False
                                # after draining stale audio from any previous response

                                t_lower = t.lower()
                                screen_b64: str | None = None
                                if hasattr(mgr, "_latest_screen_frame") and mgr._latest_screen_frame:
                                    import base64 as _b64_inner
                                    screen_b64 = _b64_inner.b64encode(mgr._latest_screen_frame).decode()
                                effective_img = img or screen_b64
                                force_canvas = bool(img)

                                # Canvas is only triggered when user explicitly wants structured content
                                # OR an image/file is attached. Everything else → Gemini Live direct.
                                _CANVAS_TRIGGER_KEYWORDS = [
                                    "write code", "code for", "show me code", "write a function",
                                    "write a script", "step by step", "steps to", "step-by-step",
                                    "explain with code", "show on canvas", "write it down",
                                    "write this down", "put it on canvas", "show me in writing",
                                ]
                                wants_canvas = force_canvas or any(kw in t_lower for kw in _CANVAS_TRIGGER_KEYWORDS)

                                # Face identification — always needs image analysis
                                is_face = effective_img and any(kw in t_lower for kw in _FACE_QUERY_KEYWORDS)

                                _latency_ms = (_time.perf_counter() - _req_t0) * 1000
                                logger.info("[LATENCY] user_text→route: %.0fms (canvas=%s face=%s)", _latency_ms, wants_canvas, is_face)

                                if is_face:
                                    # Face ID: uses _identify_face (Flash with image), then Live to speak
                                    state_mon = getattr(mgr, "_state_monitor", None)
                                    _is_guest = state_mon and getattr(state_mon, "_guest_active", False)
                                    sys_prompt = _GUEST_SYSTEM_PROMPT if _is_guest else (mgr._system_prompt or "")
                                    try:
                                        face_content = await _identify_face(t, effective_img, sys_prompt)
                                    except Exception as exc:
                                        logger.warning("ws_observe: _identify_face threw: %s", exc)
                                        face_content = ""
                                    if face_content:
                                        mgr._speak_task = asyncio.create_task(
                                            mgr._speak_verbatim(face_content, canvas=False)
                                        )
                                    else:
                                        mgr._speak_task = asyncio.create_task(mgr.voice_query(t))

                                elif wants_canvas:
                                    # Canvas path: Flash generates structured content, Live speaks brief ack
                                    state_mon = getattr(mgr, "_state_monitor", None)
                                    _is_guest = state_mon and getattr(state_mon, "_guest_active", False)
                                    sys_prompt = _GUEST_SYSTEM_PROMPT if _is_guest else (mgr._system_prompt or "")
                                    try:
                                        result = await _flash_smart(
                                            t, effective_img, sys_prompt,
                                            context=_ctx if _is_fu else None,
                                            force_canvas=True,
                                        )
                                    except Exception as exc:
                                        logger.warning("ws_observe: _flash_smart threw: %s", exc)
                                        result = {"canvas_needed": False, "title": "", "content": ""}
                                    content = result.get("content", "")
                                    if content and len(content) > 10:
                                        title = result.get("title", "") or _make_title(t)
                                        await _ws.send_text(json.dumps({
                                            "type": "text_response",
                                            "title": title,
                                            "content": content,
                                            "content_type": "markdown",
                                            "append": _is_fu,
                                        }))
                                        if not _is_fu:
                                            asyncio.create_task(_save_canvas_entry(mgr._uid, t, title, content, "markdown"))
                                        mgr._speak_task = asyncio.create_task(
                                            mgr._speak_verbatim(content, canvas=True)
                                        )
                                    else:
                                        # Flash failed — fall back to Live voice
                                        mgr._speak_task = asyncio.create_task(mgr.voice_query(t))

                                else:
                                    # All other queries — Gemini Live handles directly, naturally
                                    # This is the main path: poems, sports, casual, opinions, facts
                                    mgr._speak_task = asyncio.create_task(mgr.voice_query(t))
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
