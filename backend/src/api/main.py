import logging
import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

from src.auth.firebase_auth import verify_id_token, AuthError  # noqa: E402

app = FastAPI(title="Mirr'at Backend", version="0.1.0")

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


@app.put("/identity", status_code=200)
def put_identity(body: dict, uid: str = Depends(get_current_uid)):
    from src.identity.identity_loader import save_identity
    try:
        save_identity(uid, body)
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

# Global session manager — single-user MVP; one concurrent session
from src.session.session_manager import SessionManager  # noqa: E402

_session_manager: SessionManager | None = None


def _get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


@app.post("/session/start", status_code=201)
async def start_session(uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager()
    if mgr.status == "active":
        raise HTTPException(status_code=409, detail="SESSION_ALREADY_ACTIVE")
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
    mgr = _get_session_manager()
    await mgr.pause_session()
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "status": "paused",
        "paused_at": datetime.now(timezone.utc).isoformat(),
    }


@app.put("/session/{session_id}/resume")
async def resume_session(session_id: str, uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager()
    await mgr.resume_session()
    mgr.start_watchman()
    from datetime import datetime, timezone
    return {
        "session_id": session_id,
        "status": "active",
        "resumed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/session/{session_id}/end", status_code=202)
async def end_session(session_id: str, uid: str = Depends(get_current_uid)):
    mgr = _get_session_manager()
    await mgr.end_session()
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
    if body.trigger_type not in ("A", "B"):
        raise HTTPException(status_code=422, detail="trigger_type must be 'A' or 'B'")
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
    mgr = _get_session_manager()
    mgr._websocket = websocket

    # Connect Gemini Live API now that WebSocket is established
    try:
        await mgr.connect_gemini()
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "code": "GEMINI_DISCONNECTED", "message": str(exc)}))
        logger.warning("ws_observe: Gemini connect failed: %s", exc)

    # Keepalive ping every 30s
    import asyncio

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
            elif msg.get("type") == "audio":
                import base64
                pcm_bytes = base64.b64decode(msg["data"])
                await mgr.ensure_gemini_connected()
                if mgr.gemini and mgr.gemini.is_connected:
                    await mgr.gemini.send_audio(pcm_bytes)
                    mgr._reset_gemini_idle_timer()
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        mgr._websocket = None
        if hasattr(mgr, "_state_monitor") and mgr._state_monitor:
            mgr._state_monitor.set_websocket(None)
            mgr._state_monitor.stop()
