"""Explicit paired loopback service. No cloud credentials or auth bypasses."""
import hmac
import secrets
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from .contracts import Closed, ActionRequest
from .executor import Executor
from .workspace import Workspace, WorkspaceError


class PairRequest(Closed):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{20,200}$")
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


def create_local_app(*, root, journal, origin, authorize, pairing_code, port=8765, desktop_check=None):
    """authorize(token, session_id) calls the configured real backend, never a URL
    supplied by the caller. It returns its Firebase-authenticated UID.
    """
    paired = {"uid": None, "secret": None}
    pairing_lock = threading.Lock()
    code_expires = time.monotonic() + 300
    attempts = 0

    def owner_check(token, session_id):
        uid = authorize(token, session_id)
        if not paired["uid"] or uid != paired["uid"]:
            raise WorkspaceError("owner_required")

    from .windows import require_unlocked_desktop
    executor = Executor(Workspace(root), journal, owner_check, desktop_check=desktop_check or require_unlocked_desktop)

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.executor = executor
    app.add_middleware(CORSMiddleware, allow_origins=[origin], allow_methods=["POST"],
                       allow_headers=["Authorization", "Content-Type", "X-Rumi-Device"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        from starlette.responses import JSONResponse
        # Exact Host stops DNS rebinding; exact Origin stops other local websites.
        if (request.headers.get("host") != f"127.0.0.1:{port}"
                or request.headers.get("origin") != origin
                or request.client.host not in ("127.0.0.1", "::1", "testclient")):
            return JSONResponse({"detail": "LOCAL_CLIENT_REQUIRED"}, status_code=403)
        # Bound actual streamed bytes, not an untrusted Content-Length header.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 100000:
                return JSONResponse({"detail": "REQUEST_TOO_LARGE"}, status_code=413)
        request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def credential(authorization):
        if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 10000:
            raise HTTPException(401, "SIGN_IN_REQUIRED")
        return authorization[7:]

    def device(secret):
        if not secret or not paired["secret"] or not hmac.compare_digest(secret.encode(), paired["secret"].encode()):
            raise HTTPException(403, "PAIR_DEVICE_FIRST")

    @app.post("/pair")
    def pair(body: PairRequest, authorization: str = Header(default="")):
        nonlocal attempts
        with pairing_lock:
            attempts += 1
            if attempts > 5 or paired["uid"] or time.monotonic() >= code_expires or not hmac.compare_digest(body.code, pairing_code):
                raise HTTPException(403, "PAIRING_UNAVAILABLE")
            try:
                uid = authorize(credential(authorization), body.session_id)
                if not isinstance(uid, str) or not uid:
                    raise ValueError()
            except Exception:
                raise HTTPException(403, "OWNER_VERIFICATION_REQUIRED")
            paired.update(uid=uid, secret=secrets.token_urlsafe(32))
            return {"device_secret": paired["secret"], "workspace": str(executor.workspace.root),
                    "capabilities": ["list_files", "read_text", "create_text", "open_app"]}

    @app.post("/execute")
    def execute(body: ActionRequest, authorization: str = Header(default=""), x_rumi_device: str = Header(default="")):
        device(x_rumi_device)
        try:
            return executor.execute(body, credential(authorization))
        except WorkspaceError as exc:
            raise HTTPException(409 if exc.code == "busy" else 403, exc.code)
        except Exception:
            raise HTTPException(403, "OWNER_VERIFICATION_REQUIRED")

    @app.post("/stop")
    def stop(x_rumi_device: str = Header(default="")):
        device(x_rumi_device)
        executor.stop()
        return {"state": "stopped"}

    # No remote resume: restart/re-pair after an emergency stop.
    return app
