"""Offline test double. Never selected by production/development environment flags.

UID is an authenticated server argument, never part of an incoming document.
The lock covers authoritative load, CAS and the final authorization check.
Production uses FirestoreArtifactRepository instead.
"""
import asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from .contracts import GeneratedArtifact
from .contracts import SetSubjectColor, validate_artifact_transition
from datetime import datetime, timezone
from .state import apply_state_update, apply_spec_update


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
            if (uid, artifact.artifact_id) in self._items:
                raise HTTPException(409, "ARTIFACT_ALREADY_EXISTS")
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
            try:
                candidate = apply_spec_update(previous, decision)
            except ValueError as exc:
                raise HTTPException(422, "INVALID_ARTIFACT_SPEC") from exc
            await check()
            self._items[(uid, decision.artifact_id)] = candidate
            return candidate

    create_artifact = seed
    update_state = update
    update_spec = edit_spec
    clear_user_artifacts = clear

    async def get_artifact(self, uid, artifact_id):
        return self.get(uid, artifact_id)

    async def list_artifacts(self, uid, cursor=None):
        from .firestore_repository import artifact_metadata, PAGE_SIZE
        artifacts = sorted(self.list(uid), key=lambda a: a.artifact_id)
        artifacts = [a for a in artifacts if not cursor or a.artifact_id > cursor]
        return {"items": [artifact_metadata(a) for a in artifacts[:PAGE_SIZE]],
                "next_cursor": artifacts[PAGE_SIZE - 1].artifact_id if len(artifacts) > PAGE_SIZE else None}

    async def delete_artifact(self, uid, artifact_id, check):
        async with self._lock:
            self.get(uid, artifact_id)
            await check()
            del self._items[(uid, artifact_id)]
