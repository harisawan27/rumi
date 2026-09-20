"""Opt-in, single-worker renderer proof. No model calls or durable storage."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError, TypeAdapter
from .access import authorize
from .contracts import ArtifactId, ArtifactResult, GeneratedArtifact, GeneratedUIEditDecision
from .repository import MemoryArtifactRepository
from .state import StateUpdate

repository = MemoryArtifactRepository()
id_adapter = TypeAdapter(ArtifactId)


def create_router(get_uid, managers):
    router = APIRouter(prefix="/generated-artifacts")

    async def context(session_id: str, uid: str = Depends(get_uid)):
        if os.getenv("RUMI_ARTIFACT_PROOF_MODE") != "1":
            raise HTTPException(404, "ARTIFACT_NOT_FOUND")
        async def check():
            return await authorize(uid, session_id, managers)
        await check()
        return uid, session_id, check

    async def response(artifact, request_id, check, event="artifact_result"):
        result = ArtifactResult(
            type=event, request_id=request_id, artifact_id=artifact.artifact_id,
            revision=artifact.revision, state_revision=artifact.state_revision,
            renderer=artifact.renderer, artifact=artifact,
        )
        until = await check()  # immediately before handing private data to transport
        return {"result": result.model_dump(mode="json"),
                "lease_seconds": max(0, min(5, (until - datetime.now(timezone.utc)).total_seconds()))}

    @router.get("")
    async def history(ctx=Depends(context)):
        uid, _, check = ctx
        items = repository.list(uid)
        await check()
        return {"artifact_ids": [item.artifact_id for item in items]}

    @router.post("/proof")
    async def proof(request_id: ArtifactId, graph: bool = False, ctx=Depends(context)):
        uid, session_id, check = ctx
        path = Path(__file__).resolve().parents[3] / "tests/fixtures/artifacts/valid_study_tracker.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc)
        data.update(artifact_id=str(uuid4()), source_session_id=session_id,
                    created_at=now, updated_at=now)
        data["spec"]["show_daily_graph"] = graph
        data["spec"]["week_start"] = now.date().isoformat()
        artifact = await repository.seed(uid, GeneratedArtifact.model_validate(data), check)
        return await response(artifact, request_id, check)

    @router.get("/{artifact_id}")
    async def read(artifact_id: str, request_id: ArtifactId, ctx=Depends(context)):
        uid, _, check = ctx
        try:
            artifact_id = id_adapter.validate_python(artifact_id)
        except ValidationError:
            raise HTTPException(404, "ARTIFACT_NOT_FOUND")
        return await response(repository.get(uid, artifact_id), request_id, check)

    @router.post("/state")
    async def update(body: StateUpdate, ctx=Depends(context)):
        uid, _, check = ctx
        try:
            artifact = await repository.update(uid, body, check)
        except ValueError as exc:
            raise HTTPException(422, "INVALID_ARTIFACT_STATE") from exc
        return await response(artifact, body.request_id, check, "artifact_update")

    @router.post("/spec")
    async def edit_spec(body: GeneratedUIEditDecision, request_id: ArtifactId, ctx=Depends(context)):
        uid, _, check = ctx
        artifact = await repository.edit_spec(uid, body, check)
        return await response(artifact, request_id, check, "artifact_update")

    return router
