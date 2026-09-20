import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

from src.auth.firebase_auth import verify_id_token, AuthError  # noqa: E402

@asynccontextmanager
async def lifespan(app):
    await _startup()
    yield


app = FastAPI(title="Project Rumi — Rumi Core", version="0.1.0", lifespan=lifespan)

frontend_origins = ["http://localhost:3000", "http://localhost:3001", "http://localhost:8000", "http://localhost:7860"]
frontend_env = os.getenv("FRONTEND_URL", "")
if frontend_env:
    frontend_origins.extend([origin.strip() for origin in frontend_env.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
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

    # Verify or provision OpenCV face models on startup
    try:
        from src.vision.download_models import ensure_models
        ensure_models(fail_fast=True)
        logger.info("[RUMI CORE] Face recognition models verified successfully.")
    except Exception as exc:
        logger.critical("[RUMI CORE] Model integrity verification failed: %s", exc)
        raise


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
# Identity & Guest Access Control
# ---------------------------------------------------------------------------

def _check_guest_mode_restriction(uid: str) -> None:
    """Security & Privacy guard: Rejects access to sensitive owner profile/canvas data
    if the session is currently in Guest Mode or presence is unverified in distributed state.
    Sensitive REST routes bypass positive caching to eliminate stale-authorization windows.
    """
    # 1. Local process fast-path: if local SessionManager is locked in guest mode, reject immediately
    mgr = _session_managers.get(uid)
    if mgr and getattr(mgr, "is_guest_mode", False):
        raise HTTPException(
            status_code=403,
            detail="GUEST_PROTECTED: Active session is locked in Guest Mode.",
        )

    # 2. Distributed presence check across backend instances (bypasses positive cache for sensitive endpoints)
    try:
        from src.session.presence_manager import presence_manager
        presence = presence_manager.get_presence(uid, bypass_cache=True)
        if presence:
            mode = presence.get("mode")
            if mode == "guest":
                raise HTTPException(
                    status_code=403,
                    detail="GUEST_PROTECTED: Distributed session is locked in Guest Mode.",
                )
            if mode == "owner":
                until_str = presence.get("owner_verified_until")
                if until_str:
                    from datetime import datetime, timezone
                    until = datetime.fromisoformat(until_str)
                    if until.tzinfo is None:
                        until = until.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > until:
                        raise HTTPException(
                            status_code=403,
                            detail="GUEST_PROTECTED: Owner presence verification has expired.",
                        )
                else:
                    raise HTTPException(
                        status_code=403,
                        detail="GUEST_PROTECTED: Owner presence unverified.",
                    )
            elif mode in ("away", "unknown"):
                raise HTTPException(
                    status_code=403,
                    detail="GUEST_PROTECTED: Active session presence is unverified or user is away.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("_check_guest_mode_restriction: presence check error: %s", exc)



@app.get("/identity")
def get_identity(uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
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
    _check_guest_mode_restriction(uid)
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
    _check_guest_mode_restriction(uid)
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

from src.artifacts.access import authorize as authorize_artifact, require_session
from src.artifacts.routes import create_router as create_artifact_router

app.include_router(create_artifact_router(get_current_uid, _session_managers))


@app.middleware("http")
async def private_artifact_cache_policy(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/generated-artifacts") or request.url.path in ("/canvas/history", "/conversation/history"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def _authorize_canvas(uid: str, session_id: str | None = None):
    manager = _session_managers.get(uid)
    return await authorize_artifact(uid, session_id or (manager.session_id if manager else None), _session_managers)


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
    _check_guest_mode_restriction(uid)
    from src.memory.known_people import get_known_people
    try:
        return {"people": get_known_people(uid)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.post("/known-people", status_code=201)
def create_known_person(body: KnownPersonCreate, uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
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
    _check_guest_mode_restriction(uid)
    from src.memory.known_people import update_known_person
    try:
        update_known_person(uid, person_id, body.model_dump(exclude_none=True))
        return {"status": "updated"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.delete("/known-people/{person_id}", status_code=200)
def delete_known_person_route(person_id: str, uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
    from src.memory.known_people import delete_known_person
    try:
        delete_known_person(uid, person_id)
        return {"status": "deleted"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


# ---------------------------------------------------------------------------
# Memory Candidates (Phase 5)
# ---------------------------------------------------------------------------

@app.get("/memory/candidates")
def list_memory_candidates(uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
    from src.memory.firestore_client import get_db
    try:
        db = get_db()
        docs = (
            db.collection("users")
            .document(uid)
            .collection("memory_candidates")
            .where("status", "==", "inferred")
            .stream()
        )
        candidates = []
        for d in docs:
            data = d.to_dict()
            c_at = data.get("created_at")
            if hasattr(c_at, "isoformat"):
                c_at_str = c_at.isoformat()
            else:
                c_at_str = str(c_at) if c_at else ""
            candidates.append({
                "id": d.id,
                "field": data.get("field", ""),
                "suggested_value": data.get("suggested_value", ""),
                "source_session_id": data.get("source_session_id", ""),
                "confidence": data.get("confidence", 0.75),
                "status": data.get("status", "inferred"),
                "created_at": c_at_str,
            })
        return {"candidates": candidates}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.post("/memory/candidates/{candidate_id}/confirm")
def confirm_memory_candidate(candidate_id: str, uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
    from src.memory.firestore_client import get_db
    from src.session.memory_extractor import ALLOWED_CANDIDATE_FIELDS
    from datetime import datetime, timezone
    try:
        db = get_db()
        cand_ref = db.collection("users").document(uid).collection("memory_candidates").document(candidate_id)
        cand_snap = cand_ref.get()
        if not cand_snap.exists:
            raise HTTPException(status_code=404, detail="CANDIDATE_NOT_FOUND")
        cand_data = cand_snap.to_dict()
        field = cand_data.get("field")
        value = cand_data.get("suggested_value")

        # Strict validation against whitelist
        if not field or field not in ALLOWED_CANDIDATE_FIELDS:
            raise HTTPException(status_code=400, detail="INVALID_CANDIDATE_FIELD")

        # Security check: never allow prototype pollution or system field overwriting
        if field in ("uid", "email", "role", "is_owner", "permissions", "created_at", "embedding"):
            raise HTTPException(status_code=400, detail="DISALLOWED_FIELD")

        now = datetime.now(timezone.utc)
        user_ref = db.collection("users").document(uid)
        user_snap = user_ref.get()
        current_identity = user_snap.to_dict() if user_snap.exists else {}

        # Safely apply to user identity
        if field in ("interests", "focus_breakers"):
            existing_list = current_identity.get(field, [])
            if not isinstance(existing_list, list):
                existing_list = []
            if isinstance(value, list):
                new_items = [x for x in value if x not in existing_list]
                updated_list = existing_list + new_items
            else:
                str_val = str(value).strip()
                updated_list = existing_list if str_val in existing_list else existing_list + [str_val]
            user_ref.update({field: updated_list, "last_updated": now})
        elif field == "projects":
            existing_projects = current_identity.get("projects", [])
            if not isinstance(existing_projects, list):
                existing_projects = []
            if isinstance(value, dict):
                existing_projects.append(value)
            elif isinstance(value, list):
                existing_projects.extend(value)
            user_ref.update({"projects": existing_projects, "last_updated": now})
        else:
            user_ref.update({field: value, "last_updated": now})

        # Also store durable confirmed memory record
        db.collection("users").document(uid).collection("confirmed_memories").add({
            "field": field,
            "value": value,
            "source_candidate_id": candidate_id,
            "confirmed_at": now,
        })

        cand_ref.update({"status": "confirmed", "confirmed_at": now})
        return {"status": "confirmed", "field": field}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.post("/memory/candidates/{candidate_id}/reject")
def reject_memory_candidate(candidate_id: str, uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
    from src.memory.firestore_client import get_db
    from datetime import datetime, timezone
    try:
        db = get_db()
        cand_ref = db.collection("users").document(uid).collection("memory_candidates").document(candidate_id)
        cand_snap = cand_ref.get()
        if not cand_snap.exists:
            raise HTTPException(status_code=404, detail="CANDIDATE_NOT_FOUND")
        now = datetime.now(timezone.utc)
        cand_ref.update({"status": "rejected", "rejected_at": now})
        return {"status": "rejected"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")


@app.delete("/memory/candidates/{candidate_id}")
def dismiss_memory_candidate(candidate_id: str, uid: str = Depends(get_current_uid)):
    _check_guest_mode_restriction(uid)
    from src.memory.firestore_client import get_db
    try:
        db = get_db()
        cand_ref = db.collection("users").document(uid).collection("memory_candidates").document(candidate_id)
        cand_snap = cand_ref.get()
        if not cand_snap.exists:
            raise HTTPException(status_code=404, detail="CANDIDATE_NOT_FOUND")
        cand_ref.delete()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"FIRESTORE_UNAVAILABLE: {exc}")



# ---------------------------------------------------------------------------
# Canvas helpers (Phase 3 + 5)
# ---------------------------------------------------------------------------

FLASH_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash")

def _make_genai_client():
    """Return a genai Client using Vertex AI when GOOGLE_CLOUD_PROJECT is set,
    otherwise fall back to GEMINI_API_KEY. Mirrors live_client.py auth logic."""
    from google import genai as _genai
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project:
        return _genai.Client(
            vertexai=True,
            project=project,
            location=os.getenv("GOOGLE_CLOUD_REGION", "asia-south1"),
        )
    return _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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
    # Find outermost {...} block (handles nested tool_call objects)
    start = clean.find("{")
    if start != -1:
        depth, end = 0, -1
        for i, ch in enumerate(clean[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            try:
                return json.loads(clean[start:end + 1])
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


async def _flash_detect_tool(text: str) -> dict | None:
    """Lightweight tool-intent detector — returns tool_call dict or None.

    Separate from _flash_smart so canvas content generation is NOT mixed with
    tool detection. Short JSON-only prompt → reliable parse, no essay in JSON.
    Returns e.g. {"name": "update_profile", "field": "name", "value": "Haris",
                  "confirmation": "Done — I've updated your name to Haris."}
    or None if no tool intent detected.
    """
    from google import genai as _genai
    client = _make_genai_client()

    prompt = f"""The user said: "{text}"

Detect if they want to perform one of these two actions. Reply with ONLY valid JSON, no markdown fences.

ACTION 1 — update a profile field:
Triggers: "update my name to X", "change my bio to X", "set my language to X",
"my name is X now", "call me X", "update my timezone", "change my coding style",
"update my stack to X", "my preferred language is X"
Reply: {{"tool": "update_profile", "field": "<field>", "value": "<value>", "confirmation": "one warm sentence confirming the update"}}
field must be one of: name, bio, preferred_language, timezone, coding_style, tech_stack, preferred_tone, goals, personal_context, learning_focus, mood_preference

ACTION 2 — remember a person from camera:
Triggers: "remember this person as X", "save this person", "this is my friend X",
"add X as my colleague", "this is X they're my Y", "remember him/her as X"
Reply: {{"tool": "add_known_person", "person_name": "<name>", "relationship": "<rel>", "confirmation": "one warm sentence confirming"}}

If NEITHER action matches, reply exactly: {{"tool": null}}"""

    for model in FLASH_MODELS:
        try:
            response = await client.aio.models.generate_content(model=model, contents=prompt)
            raw = (response.text or "").strip()
            data = _extract_smart_json(raw)
            if data and data.get("tool"):
                return data
            if data and "tool" in data and data["tool"] is None:
                return None
        except Exception as exc:
            logger.debug("_flash_detect_tool: %s failed: %s", model, exc)
    return None


async def _flash_smart(
    text: str,
    image_b64: str | None,
    system_prompt: str,
    context: list | None = None,
    force_canvas: bool = False,
) -> dict:
    """Route query to canvas or voice, then generate content.

    Returns {"canvas_needed": bool, "title": str, "content": str}.
    Tool detection is handled by _flash_detect_tool before this is called.
    Poetry/face queries are handled by dedicated callers before this is reached.
    force_canvas=True when an explicit file/image attachment is present.
    """
    from google import genai as _genai
    from google.genai import types as _types
    import base64 as _b64

    client = _make_genai_client()
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
  • User explicitly says: write, show, display, summarize in writing, research, solve, essay, article
  • Any image or file is attached (auto-true)

FALSE — experienced by listening. This includes:
  • Casual conversation, gossip, emotional support, opinions
  • Greetings, encouragement, check-ins
  • Simple facts (sports results, time, weather, quick questions)
  • Anything the user asks to "tell", "say", "read", or "recite"
  • Real-time questions you can't answer (live scores, today's news) — say so verbally.

When canvas_needed=false:
  - title = empty string
  - content = your full spoken response, plain text, NO markdown
  - NO length limit. Speak as long as the topic deserves naturally.
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

    for model in FLASH_MODELS:
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


# Keywords that route to the vision analysis path (face + object recognition)
_FACE_QUERY_KEYWORDS = [
    "who is in front", "who do you see", "who am i", "can you see me",
    "do you see me", "who is this", "look at me", "see me",
    "how do i look", "am i on camera", "what do i look",
    "what is in my hand", "what's in my hand", "what am i holding",
    "what do you see", "what can you see", "what are you seeing",
    "look at this", "can you see this", "what is this",
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

    client = _make_genai_client()
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
    for model in FLASH_MODELS:
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

    client = _make_genai_client()
    prompt = (
        f"{system_prompt}\n\n---\n\n"
        f'The user asked: "{text}"\n\n'
        "Recite the requested poem, couplet, or verse in full. "
        "Deliver it as a companion speaking aloud — complete, unhurried, natural. "
        "Plain text only, no markdown, no asterisks. "
        "A brief warm line before or after is fine. "
        "Do NOT mention canvas, screen, writing, or displaying anything."
    )
    for model in FLASH_MODELS:
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
    for model in FLASH_MODELS:
        try:
            logger.info("_flash_text_only: trying %s for: %.60s", model, text)
            client = _make_genai_client()
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


async def _flash_canvas_task(text: str, image_b64: str | None, ws, uid: str, session_id: str) -> None:
    """Generate canvas content via Flash and push text_response to frontend.
    Runs as a background task — never blocks voice response.
    """
    import json as _json
    try:
        await _authorize_canvas(uid, session_id)
        content = await (_flash_with_image(text, image_b64) if image_b64 else _flash_text_only(text))
        if content and len(content) > 30:
            await _authorize_canvas(uid, session_id)
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

    client = _make_genai_client()
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
    for model in FLASH_MODELS:
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

    client = _make_genai_client()
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

    for model in FLASH_MODELS:
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


async def _save_canvas_entry(uid: str, query: str, title: str, content: str, content_type: str, session_id: str) -> None:
    """Persist a canvas answer to Firestore without blocking the event loop."""
    try:
        await _authorize_canvas(uid, session_id)
        await asyncio.get_event_loop().run_in_executor(
            None, _do_save_canvas_entry, uid, query, title, content, content_type
        )
    except HTTPException:
        raise
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
            if d.get("kind") == "generated_ui":
                from src.artifacts.contracts import ArtifactId, Title
                from pydantic import TypeAdapter, ValidationError
                try:
                    reference = {"kind": "generated_ui", "artifact_id": TypeAdapter(ArtifactId).validate_python(d.get("artifact_id")),
                                 "title": TypeAdapter(Title).validate_python(d.get("title")),
                                 "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ""}
                except ValidationError:
                    continue
                items.append(reference)
                continue
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
    _check_guest_mode_restriction(uid)
    await _authorize_canvas(uid)
    items = await asyncio.get_event_loop().run_in_executor(None, _load_canvas_history, uid)
    await _authorize_canvas(uid)
    return {"items": items}


def _save_conversation_turn(
    uid: str,
    session_id: str,
    user_text: str,
    rumi_response: str,
    source: str = "voice",
) -> None:
    """Save a conversational turn to Firestore under the session."""
    try:
        from src.memory.firestore_client import get_db
        from datetime import datetime, timezone
        db = get_db()
        now = datetime.now(timezone.utc)
        turn_doc = {
            "session_id": session_id,
            "user_text": user_text,
            "rumi_response": rumi_response,
            "source": source,
            "created_at": now,
        }
        db.collection("users").document(uid).collection("sessions").document(
            session_id
        ).collection("turns").add(turn_doc)
        logger.info(
            "conversation_turn saved for uid=%s session=%s chars=(%d/%d)",
            uid, session_id, len(user_text), len(rumi_response)
        )
    except Exception as exc:
        logger.warning("_save_conversation_turn failed: %s", exc)


@app.get("/conversation/history")
async def get_conversation_history(limit: int = 15, uid: str = Depends(get_current_uid)):
    """Fetch durable conversation history grouped by session, with turns and proactive interventions."""
    _check_guest_mode_restriction(uid)
    # Conversation turns also contain saved Canvas answers.
    await _authorize_canvas(uid)
    from src.memory.firestore_client import get_db

    def _load():
        try:
            db = get_db()
            sess_docs = (
                db.collection("users")
                .document(uid)
                .collection("sessions")
                .order_by("started_at", direction="DESCENDING")
                .limit(min(limit, 30))
                .stream()
            )
            sessions_data = []
            for s_doc in sess_docs:
                s_dict = s_doc.to_dict()
                s_id = s_doc.id
                started_at = s_dict.get("started_at")
                if hasattr(started_at, "isoformat"):
                    started_at_str = started_at.isoformat()
                else:
                    started_at_str = str(started_at) if started_at else ""

                events = []
                # Turns
                try:
                    turns_stream = (
                        db.collection("users")
                        .document(uid)
                        .collection("sessions")
                        .document(s_id)
                        .collection("turns")
                        .order_by("created_at")
                        .stream()
                    )
                    for t in turns_stream:
                        td = t.to_dict()
                        cat = td.get("created_at")
                        ts = cat.isoformat() if hasattr(cat, "isoformat") else str(cat) if cat else ""
                        events.append({
                            "type": "turn",
                            "user_text": td.get("user_text", ""),
                            "rumi_response": td.get("rumi_response", ""),
                            "source": td.get("source", "voice"),
                            "timestamp": ts,
                        })
                except Exception as exc:
                    logger.debug("get_conversation_history: could not load turns for %s: %s", s_id, exc)

                # Interactions (proactive interventions)
                try:
                    interact_stream = (
                        db.collection("users")
                        .document(uid)
                        .collection("sessions")
                        .document(s_id)
                        .collection("interactions")
                        .order_by("triggered_at")
                        .stream()
                    )
                    for i in interact_stream:
                        id_data = i.to_dict()
                        tat = id_data.get("triggered_at")
                        ts = tat.isoformat() if hasattr(tat, "isoformat") else str(tat) if tat else ""
                        events.append({
                            "type": "intervention",
                            "trigger": id_data.get("trigger_type", "B"),
                            "text": id_data.get("intervention_text", ""),
                            "user_response": id_data.get("user_response", ""),
                            "timestamp": ts,
                        })
                except Exception as exc:
                    logger.debug("get_conversation_history: could not load interactions for %s: %s", s_id, exc)

                events.sort(key=lambda x: x.get("timestamp", ""))

                sessions_data.append({
                    "session_id": s_id,
                    "started_at": started_at_str,
                    "status": s_dict.get("status", "completed"),
                    "events": events,
                })
            return sessions_data
        except Exception as exc:
            logger.warning("get_conversation_history failed: %s", exc)
            return []

    sessions = await asyncio.get_event_loop().run_in_executor(None, _load)
    await _authorize_canvas(uid)
    return {"sessions": sessions}


def _delete_all_conversation_history(uid: str) -> int:
    """Recursively and genuinely wipe all sessions, nested turns, nested interactions, and session summaries."""
    from src.memory.firestore_client import get_db
    db = get_db()
    deleted_count = 0
    try:
        sess_docs = list(db.collection("users").document(uid).collection("sessions").stream())
        for s in sess_docs:
            turns = list(s.reference.collection("turns").stream())
            for t in turns:
                t.reference.delete()
                deleted_count += 1
            interactions = list(s.reference.collection("interactions").stream())
            for i in interactions:
                i.reference.delete()
                deleted_count += 1
            s.reference.delete()
            deleted_count += 1

        summaries = list(db.collection("users").document(uid).collection("session_summaries").stream())
        for sm in summaries:
            sm.reference.delete()
            deleted_count += 1
    except Exception as exc:
        logger.warning("_delete_all_conversation_history failed: %s", exc)
    return deleted_count


@app.delete("/conversation/history")
async def clear_conversation_history(uid: str = Depends(get_current_uid)):
    """Cleanly purge all user-visible conversation history: sessions, turns, interactions, and summaries."""
    _check_guest_mode_restriction(uid)
    deleted = await asyncio.get_event_loop().run_in_executor(None, _delete_all_conversation_history, uid)
    return {"status": "deleted", "deleted_records": deleted}


def _delete_all_canvas_history(uid: str) -> int:
    from src.memory.firestore_client import get_db
    deleted_count = 0
    try:
        db = get_db()
        collection = db.collection("users").document(uid).collection("canvas_history")
        while True:
            canvas_docs = list(collection.limit(100).stream(retry=None, timeout=5))
            if not canvas_docs:
                break
            batch = db.batch()
            for c in canvas_docs:
                batch.delete(c.reference)
            batch.commit(retry=None, timeout=5)
            deleted_count += len(canvas_docs)
    except Exception as exc:
        logger.warning("_delete_all_canvas_history failed: %s", exc)
        raise HTTPException(503, "CANVAS_STORAGE_UNAVAILABLE") from exc
    return deleted_count


@app.delete("/canvas/history")
async def clear_canvas_history_route(uid: str = Depends(get_current_uid)):
    """Cleanly purge all canvas history entries for the authenticated user."""
    _check_guest_mode_restriction(uid)
    await _authorize_canvas(uid)
    from src.artifacts.routes import repository
    await repository.clear_user_artifacts(uid, lambda: _authorize_canvas(uid))
    await _authorize_canvas(uid)
    deleted = await asyncio.get_event_loop().run_in_executor(None, _delete_all_canvas_history, uid)
    await _authorize_canvas(uid)
    return {"status": "deleted", "deleted_records": deleted}



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

    uid = decoded["uid"]
    try:
        mgr = require_session(uid, session_id, _session_managers)
    except HTTPException:
        await websocket.close(code=4003)
        return
    await websocket.accept()
    mgr._websocket = websocket

    # Send canvas history FIRST — before Gemini connects so frontend shows
    # history immediately without waiting for the Gemini handshake delay
    try:
        await _authorize_canvas(uid, session_id)
        history = await asyncio.get_event_loop().run_in_executor(
            None, _load_canvas_history, uid
        )
        if history:
            await _authorize_canvas(uid, session_id)
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
                try:
                    from src.session.presence_manager import presence_manager
                    presence_manager.record_session_heartbeat(uid, session_id)
                except Exception:
                    pass
            elif msg.get("type") == "frame":
                import base64
                frame_bytes = base64.b64decode(msg["data"])
                if mgr.gemini and mgr.gemini.is_connected:
                    await mgr.gemini.send_frame(frame_bytes)
                # Update StateMonitor with latest webcam frame for face/posture analysis
                if hasattr(mgr, "_state_monitor") and mgr._state_monitor:
                    mgr._state_monitor.update_frame(frame_bytes)
            elif msg.get("type") == "screen_frame":
                import base64
                screen_bytes = base64.b64decode(msg["data"])
                # Update CodingBlockTracker with screen frame to detect visual stasis
                if hasattr(mgr, "_coding_block_tracker") and mgr._coding_block_tracker:
                    mgr._coding_block_tracker.update_frame(screen_bytes)
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
            elif msg.get("type") == "demo_trigger":
                # Manual demo trigger — bypasses all thresholds and cooldowns.
                # Fired from the frontend via the \ key shortcut during live demos.
                logger.info("ws_observe: demo_trigger received — firing intervention A")
                asyncio.create_task(mgr._fire_trigger_a())

            elif msg.get("type") == "audio_interrupt":
                # Frontend-initiated manual interruption.
                gen_id = mgr.interrupt_audio("frontend_audio_interrupt")
                logger.info("ws_observe: audio_interrupt from frontend — suppressed + cancelled (gen=%d)", gen_id)
            elif msg.get("type") == "user_text":
                # Web Speech API transcript — Flash generates text (single source of truth),
                # Live speaks it verbatim, canvas opens 1500ms later (voice-first UX).
                text = msg.get("text", "").strip()
                image_b64 = msg.get("image")  # base64 JPEG or None
                is_followup = bool(msg.get("is_followup", False))
                followup_context = msg.get("context", [])  # list of {q, a} dicts
                if is_followup or msg.get("artifact_id"):
                    try:
                        await _authorize_canvas(uid, session_id)
                        # Generated-artifact edits use the typed state endpoint;
                        # never send this payload/context to the legacy model path.
                        if msg.get("artifact_id"):
                            raise HTTPException(400, "ARTIFACT_TYPED_OPERATION_REQUIRED")
                    except HTTPException as exc:
                        await websocket.send_json({"type": "error", "code": exc.detail})
                        continue
                if text:
                    import time as _time
                    _t0 = _time.perf_counter()

                    # Preemptively interrupt previous audio and claim next generation slot
                    new_gen = mgr.interrupt_audio("new_user_text")

                    # Tell frontend to clear its audio buffer with the new generation id
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "audio_interrupt",
                            "generation_id": new_gen,
                        }))
                    except Exception:
                        pass

                    # Cancel greeting if still running
                    gt = mgr._greeting_task
                    if gt and not gt.done():
                        gt.cancel()

                    t_lower = text.lower()
                    import base64 as _b64_inline
                    screen_b64: str | None = None
                    if hasattr(mgr, "_latest_screen_frame") and mgr._latest_screen_frame:
                        screen_b64 = _b64_inline.b64encode(mgr._latest_screen_frame).decode()
                    # Grab latest camera frame from state_monitor for visual queries
                    cam_b64: str | None = None
                    state_mon_img = getattr(mgr, "_state_monitor", None)
                    if state_mon_img and getattr(state_mon_img, "_current_frame", None) is not None:
                        try:
                            cam_b64 = _b64_inline.b64encode(state_mon_img._current_frame).decode()
                        except Exception:
                            pass
                    effective_img = image_b64 or screen_b64 or cam_b64
                    force_canvas = bool(image_b64)

                    is_face = effective_img and any(kw in t_lower for kw in _FACE_QUERY_KEYWORDS)

                    logger.info("[LATENCY] user_text received: %.0fms (face=%s force_canvas=%s)",
                                (_time.perf_counter() - _t0) * 1000, is_face, force_canvas)

                    if is_face:
                        # Face ID path — Flash analyses image, Live delivers verbally
                        state_mon = getattr(mgr, "_state_monitor", None)
                        _is_guest = state_mon and getattr(state_mon, "_guest_active", False)
                        sys_prompt = _GUEST_SYSTEM_PROMPT if _is_guest else (mgr._system_prompt or "")
                        async def _face_respond(t=text, img=effective_img, sp=sys_prompt) -> None:
                            try:
                                fc = await _identify_face(t, img, sp)
                                if fc:
                                    asyncio.create_task(asyncio.to_thread(_save_conversation_turn, mgr._uid, session_id, t, fc, "face"))
                                    await mgr.voice_query(fc)
                                else:
                                    asyncio.create_task(asyncio.to_thread(_save_conversation_turn, mgr._uid, session_id, t, "", "face"))
                                    await mgr.voice_query(t)
                            except asyncio.CancelledError:
                                pass
                            except Exception as exc:
                                logger.warning("_face_respond failed: %s", exc)
                        mgr._speak_task = asyncio.create_task(_face_respond())

                    else:
                        state_mon = getattr(mgr, "_state_monitor", None)
                        _is_guest = state_mon and getattr(state_mon, "_guest_active", False)
                        sys_prompt = _GUEST_SYSTEM_PROMPT if _is_guest else (mgr._system_prompt or "")

                        # ── Keyword routing (zero latency) ────────────────────────
                        _CANVAS_TRIGGER_KEYWORDS = [
                            "write code", "code for", "show me code", "write a function",
                            "write a script", "step by step", "steps to", "step-by-step",
                            "explain with code", "essay", "article", "blog post",
                            "write about", "write me a", "write an", "write a report",
                            "write a letter", "write a summary", "summarize", "summarise",
                            "research on", "report on", "explain in detail",
                            "detailed explanation", "show on canvas", "write it down",
                            "write this down", "put it on canvas", "show me in writing",
                        ]
                        _TOOL_HINT_KEYWORDS = [
                            "update my name", "change my name", "my name is now",
                            "call me ", "update my bio", "change my bio",
                            "set my language", "update my language", "change my language",
                            "update my timezone", "change my timezone",
                            "update my coding style", "change my coding style",
                            "remember this person", "save this person",
                            "this is my friend", "this is my brother", "this is my sister",
                            "this is my colleague", "add as my", "remember him as",
                            "remember her as", "remember them as",
                        ]
                        wants_canvas = is_followup or force_canvas or any(kw in t_lower for kw in _CANVAS_TRIGGER_KEYWORDS)
                        is_tool_hint = any(kw in t_lower for kw in _TOOL_HINT_KEYWORDS)

                        if is_tool_hint:
                            # Tool path — Flash detects intent and extracts params
                            async def _tool_respond(t=text, sp=sys_prompt, _ws=websocket) -> None:
                                try:
                                    tool_data = await _flash_detect_tool(t)
                                    if not tool_data or not tool_data.get("tool"):
                                        asyncio.create_task(asyncio.to_thread(_save_conversation_turn, mgr._uid, session_id, t, "", "tool"))
                                        await mgr.voice_query(t)
                                        return
                                    tool_name    = tool_data.get("tool", "")
                                    confirmation = tool_data.get("confirmation", "")
                                    if tool_name == "update_profile":
                                        field = tool_data.get("field", "").strip()
                                        value = tool_data.get("value", "").strip()
                                        if field and value:
                                            try:
                                                from src.identity.identity_loader import save_identity
                                                import asyncio as _aio
                                                await _aio.get_event_loop().run_in_executor(
                                                    None, save_identity, mgr._uid, {field: value}
                                                )
                                                asyncio.create_task(mgr.refresh_context())
                                                logger.info("tool:update_profile %s=%s", field, value)
                                                try:
                                                    await _ws.send_text(json.dumps({"type": "profile_updated", "field": field}))
                                                except Exception:
                                                    pass
                                            except Exception as exc:
                                                logger.warning("tool:update_profile failed: %s", exc)
                                                confirmation = "I had trouble with that — try the profile page."
                                    elif tool_name == "add_known_person":
                                        name = tool_data.get("person_name", "").strip()
                                        rel  = tool_data.get("relationship", "").strip()
                                        if name and rel:
                                            try:
                                                await mgr.save_person_from_voice(name, rel)
                                                logger.info("tool:add_known_person %s (%s)", name, rel)
                                                try:
                                                    await _ws.send_text(json.dumps({"type": "known_person_added", "name": name}))
                                                except Exception:
                                                    pass
                                            except Exception as exc:
                                                logger.warning("tool:add_known_person failed: %s", exc)
                                                confirmation = "I couldn't save that person — make sure I can see their face."
                                    reply_text = confirmation or t
                                    asyncio.create_task(asyncio.to_thread(_save_conversation_turn, mgr._uid, session_id, t, reply_text, "tool"))
                                    await mgr.voice_query(reply_text)
                                except asyncio.CancelledError:
                                    pass
                                except Exception as exc:
                                    logger.warning("_tool_respond failed: %s", exc)
                                    try:
                                        await mgr.voice_query(t)
                                    except Exception:
                                        pass
                            mgr._speak_task = asyncio.create_task(_tool_respond())

                        elif wants_canvas:
                            # Canvas path — single Flash call for content generation
                            async def _canvas_respond(t=text, img=effective_img, sp=sys_prompt,
                                                      _ws=websocket, _fu=is_followup) -> None:
                                try:
                                    await _authorize_canvas(uid, session_id)
                                    result  = await _flash_smart(t, img, sp, force_canvas=True)
                                    content = result.get("content", "")
                                    if content and len(content) > 10:
                                        title = result.get("title", "") or _make_title(t)
                                        if not _fu:
                                            await _save_canvas_entry(uid, t, title, content, "markdown", session_id)
                                        await _authorize_canvas(uid, session_id)
                                        await asyncio.to_thread(_save_conversation_turn, uid, session_id, t, content, "canvas")
                                        await _authorize_canvas(uid, session_id)
                                        await _ws.send_text(json.dumps({
                                            "type": "text_response", "title": title,
                                            "content": content, "content_type": "markdown",
                                            "append": _fu,
                                        }))
                                        await mgr.voice_query("I've put that on your canvas — take a look.")
                                    else:
                                        asyncio.create_task(asyncio.to_thread(_save_conversation_turn, mgr._uid, session_id, t, "", "canvas"))
                                        await mgr.voice_query(t)
                                except asyncio.CancelledError:
                                    pass
                                except HTTPException:
                                    await _ws.send_json({"type": "error", "code": "ARTIFACT_ACCESS_DENIED"})
                                except Exception as exc:
                                    logger.warning("_canvas_respond failed: %s", exc)
                                    try:
                                        await mgr.voice_query(t)
                                    except Exception:
                                        pass
                            mgr._speak_task = asyncio.create_task(_canvas_respond())

                        else:
                            # Voice — direct Gemini Live, no Flash overhead
                            asyncio.create_task(asyncio.to_thread(_save_conversation_turn, mgr._uid, session_id, text, "", "voice"))
                            mgr._speak_task = asyncio.create_task(mgr.voice_query(text))
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        mgr._websocket = None
        if hasattr(mgr, "_state_monitor") and mgr._state_monitor:
            mgr._state_monitor.set_websocket(None)
            mgr._state_monitor.stop()
