"""Explicit loopback-only synthetic CREATE acceptance server; never production auth.

Run with --emulator-browser and the dedicated localhost emulator environment.
Only synthetic study artifacts are exposed; no identity, voice, or Firebase login.
"""
import argparse
from contextlib import asynccontextmanager


def create_app():
    from src.artifacts.emulator import require_emulator, create_emulator_client
    require_emulator()
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, ConfigDict, Field
    from src.artifacts.contracts import ArtifactResult, GeneratedUIEditDecision
    from src.artifacts.state import StateUpdate
    from src.artifacts.firestore_repository import FirestoreArtifactRepository
    from src.artifacts.service import plan_and_execute
    from src.artifacts.planner import provider_for, close_planner_clients
    from src.api.main import _make_genai_client, FLASH_MODELS

    db = create_emulator_client()
    repo = FirestoreArtifactRepository(lambda: db)
    uid, sid = "browser_acceptance_synthetic", "browser_acceptance_session"
    provider = provider_for(_make_genai_client, FLASH_MODELS[0])

    @asynccontextmanager
    async def lifespan(app):
        yield
        await close_planner_clients()
        db.close()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        from starlette.responses import JSONResponse
        if request.client.host not in ("127.0.0.1", "::1") or request.headers.get("host") not in ("localhost:8005", "127.0.0.1:8005"):
            return JSONResponse({"detail": "Local acceptance only"}, status_code=403)
        if request.headers.get("origin") not in (None, "http://localhost:3000"):
            return JSONResponse({"detail": "Local origin required"}, status_code=403)
        return await call_next(request)

    async def check():
        require_emulator()

    def envelope(artifact, rid, event="artifact_result"):
        return {"result": ArtifactResult(type=event, request_id=rid,
            artifact_id=artifact.artifact_id, revision=artifact.revision,
            state_revision=artifact.state_revision, renderer=artifact.renderer,
            artifact=artifact).model_dump(mode="json"), "lease_seconds": 5}

    class Prompt(BaseModel):
        model_config = ConfigDict(extra="forbid")
        text: str = Field(min_length=1, max_length=4000)
        request_id: str
        selected_id: str | None = None

    @app.post("/plan")
    async def plan(body: Prompt):
        stages = []
        async def progress(stage):
            stages.append(stage)
        result, artifact, ack = await plan_and_execute(text=body.text, uid=uid,
            session_id=sid, request_id=body.request_id, selected_id=body.selected_id,
            has_canvas=bool(body.selected_id), timezone_name="Asia/Karachi", repository=repo,
            check=check, provider=provider, progress=progress)
        return {"result": artifact.model_dump(mode="json") if artifact else None,
                "mode": result.decision.mode, "ack": ack, "stages": stages}

    @app.get("/history")
    async def history():
        return await repo.list_artifacts(uid)

    @app.get("/artifacts/access")
    async def access(request_id: str):
        await check()
        return {"request_id": request_id, "lease_seconds": 5}

    @app.post("/artifacts/spec")
    async def spec(body: GeneratedUIEditDecision, request_id: str):
        return envelope(await repo.update_spec(uid, body, check), request_id, "artifact_update")

    @app.post("/artifacts/state")
    async def state(body: StateUpdate):
        return envelope(await repo.update_state(uid, body, check), body.request_id, "artifact_update")

    @app.get("/artifacts/{artifact_id}")
    async def read(artifact_id: str, request_id: str):
        return envelope(await repo.get_artifact(uid, artifact_id), request_id)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator-browser", action="store_true", required=True)
    parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8005)
