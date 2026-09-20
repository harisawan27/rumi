"""Process-local proof repository. NOT durable or suitable for multiple workers.

UID is an authenticated server argument, never part of an incoming document.
The lock covers authoritative load, CAS and the final authorization check.
Replace this with a UID-scoped transactional store before production rollout.
"""
import asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from .contracts import GeneratedArtifact
from .contracts import SetSubjectColor, validate_artifact_transition
from datetime import datetime, timezone
from .state import apply_state_update


class MemoryArtifactRepository:
    def __init__(self):
        self._items = {}
        self._lock = asyncio.Lock()

    def get(self, uid, artifact_id):
        item = self._items.get((uid, artifact_id))
        if item is None:
            raise HTTPException(404, "ARTIFACT_NOT_FOUND")
        try:
            artifact = GeneratedArtifact.model_validate(item)
        except ValidationError as exc:
            raise HTTPException(422, "INVALID_ARTIFACT") from exc
        if artifact.artifact_id != artifact_id:
            raise HTTPException(422, "INVALID_ARTIFACT")
        return artifact

    def list(self, uid):
        return [self.get(uid, artifact_id) for owner, artifact_id in self._items if owner == uid]

    async def seed(self, uid, artifact, check):
        artifact = GeneratedArtifact.model_validate(artifact)
        async with self._lock:
            await check()
            if len(self.list(uid)) >= 20:
                raise HTTPException(409, "ARTIFACT_LIMIT")
            self._items[(uid, artifact.artifact_id)] = artifact
        return artifact

    async def update(self, uid, update, check):
        async with self._lock:
            previous = self.get(uid, update.artifact_id)
            if previous.state_revision != update.expected_state_revision:
                raise HTTPException(409, "ARTIFACT_REVISION_CONFLICT")
            candidate = apply_state_update(previous, update)
            await check()
            # No yielding between final authorization and the local commit.
            self._items[(uid, update.artifact_id)] = candidate
            return candidate

    async def clear(self, uid, check):
        async with self._lock:
            await check()
            self._items = {key: value for key, value in self._items.items() if key[0] != uid}

    async def edit_spec(self, uid, decision, check):
        async with self._lock:
            previous = self.get(uid, decision.artifact_id)
            if previous.revision != decision.expected_revision:
                raise HTTPException(409, "ARTIFACT_REVISION_CONFLICT")
            data = previous.model_dump(mode="json")
            if isinstance(decision.edit, SetSubjectColor):
                subject = next((s for s in data["spec"]["subjects"] if s["id"] == decision.edit.subject_id), None)
                if subject is None:
                    raise HTTPException(422, "INVALID_ARTIFACT_SPEC")
                subject["color_token"] = decision.edit.color_token
            else:
                data["spec"]["show_daily_graph"] = decision.edit.enabled
            if data["spec"] != previous.model_dump(mode="json")["spec"]:
                data["revision"] += 1
            data["updated_at"] = datetime.now(timezone.utc)
            candidate = validate_artifact_transition(previous, GeneratedArtifact.model_validate(data))
            await check()
            self._items[(uid, decision.artifact_id)] = candidate
            return candidate
