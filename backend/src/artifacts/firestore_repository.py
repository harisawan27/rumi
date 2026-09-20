"""UID-scoped storage. Authorization is supplied by the service, never a document.

Firestore transactions provide CAS across workers. A fresh authorization callback
runs on every transaction attempt immediately before returning to SDK commit.
Presence and artifact commits are NOT one atomic authorization transaction.
"""
import asyncio
import os
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

from fastapi import HTTPException
from google.cloud import firestore
from pydantic import TypeAdapter, ValidationError
from src.memory.firestore_client import get_db
from .contracts import ArtifactId, GeneratedArtifact, GeneratedUIEditDecision
from .state import StateUpdate, apply_state_update, apply_spec_update

_id = TypeAdapter(ArtifactId)
PAGE_SIZE = 20
DELETE_PAGE_SIZE = 100  # two writes per artifact; below Firestore's 500-write cap


def artifact_metadata(artifact):
    data = artifact.model_dump(mode="json")
    return {key: data[key] for key in (
        "artifact_id", "title", "renderer", "updated_at", "revision", "state_revision",
    )}


class FirestoreArtifactRepository:
    def __init__(self, client_factory=None):
        self._client_factory = client_factory or self._configured_client

    @staticmethod
    def _configured_client():
        if os.getenv("FIRESTORE_EMULATOR_HOST") is not None:
            from .emulator import create_emulator_client
            return create_emulator_client()
        return get_db()

    @staticmethod
    def _uid(uid):
        if not isinstance(uid, str) or not uid or len(uid) > 128 or "/" in uid or uid in (".", ".."):
            raise HTTPException(403, "ARTIFACT_ACCESS_DENIED")
        return uid

    @staticmethod
    def _artifact_id(value):
        try:
            return _id.validate_python(value)
        except ValidationError as exc:
            raise HTTPException(404, "ARTIFACT_NOT_FOUND") from exc

    def _user(self, db, uid):
        return db.collection("users").document(self._uid(uid))

    @staticmethod
    def _decode(snapshot):
        if not snapshot.exists:
            raise HTTPException(404, "ARTIFACT_NOT_FOUND")
        try:
            artifact = GeneratedArtifact.model_validate(snapshot.to_dict())
        except ValidationError as exc:
            raise HTTPException(422, "INVALID_ARTIFACT") from exc
        if artifact.artifact_id != snapshot.id:
            raise HTTPException(422, "INVALID_ARTIFACT")
        return artifact

    @staticmethod
    def _stored(artifact):
        data = artifact.model_dump(mode="json")
        # Firestore native timestamps; dates in spec/state remain ISO calendar dates.
        data.update(created_at=artifact.created_at, updated_at=artifact.updated_at)
        return data

    async def _run(self, work, check=None):
        loop = asyncio.get_running_loop()
        canceled = Event()
        def checked():
            if canceled.is_set():
                raise HTTPException(403, "ARTIFACT_ACCESS_DENIED")
            future = asyncio.run_coroutine_threadsafe(check(), loop)
            try:
                future.result(timeout=5)
            except Exception:
                future.cancel()
                raise
            if canceled.is_set():
                raise HTTPException(403, "ARTIFACT_ACCESS_DENIED")
        def run():
            try:
                return work(self._client_factory(), checked)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(503, "ARTIFACT_STORAGE_UNAVAILABLE") from exc
        try:
            return await asyncio.to_thread(run)
        finally:
            canceled.set()

    def _transaction(self, db, uid, check, operation, *, clearing_token=None):
        user = self._user(db, uid)
        control = user.collection("artifact_control").document("state")
        tx = db.transaction(max_attempts=5)
        @firestore.transactional
        def commit(transaction):
            status = control.get(transaction=transaction, retry=None, timeout=5).to_dict() or {}
            if clearing_token is not None:
                if status.get("clearing_token") != clearing_token:
                    raise HTTPException(409, "ARTIFACT_CLEAR_IN_PROGRESS")
            elif status.get("clearing_token"):
                raise HTTPException(409, "ARTIFACT_CLEAR_IN_PROGRESS")
            result = operation(transaction, user)
            check()  # re-run on EVERY SDK retry, after all reads/transforms
            return result
        result = commit(tx)
        if isinstance(result, GeneratedArtifact) and tx.write_results:
            data = result.model_dump(mode="json")
            # SERVER_TIMESTAMP resolves to request time, which can differ from
            # document update_time (notably in the emulator). Both create
            # transforms share that time; updates have only updated_at.
            stamp = tx.write_results[0].transform_results[0].timestamp_value
            data["updated_at"] = stamp
            # Create is tagged by operation; updates preserve original created_at.
            if getattr(operation, "creating", False):
                data["created_at"] = stamp
            return GeneratedArtifact.model_validate(data)
        return result

    async def create_artifact(self, uid, artifact, check):
        artifact = GeneratedArtifact.model_validate(artifact)
        self._uid(uid)
        def create(tx, user):
            ref = user.collection("artifacts").document(artifact.artifact_id)
            if ref.get(transaction=tx, retry=None, timeout=5).exists:
                raise HTTPException(409, "ARTIFACT_ALREADY_EXISTS")
            now = datetime.now(timezone.utc)
            candidate = GeneratedArtifact.model_validate({**artifact.model_dump(mode="json"), "created_at": now, "updated_at": now})
            data = self._stored(candidate)
            data.update(created_at=firestore.SERVER_TIMESTAMP, updated_at=firestore.SERVER_TIMESTAMP)
            tx.create(ref, data)
            tx.set(user.collection("canvas_history").document("artifact_" + artifact.artifact_id), {
                "kind": "generated_ui", "artifact_id": artifact.artifact_id,
                "title": artifact.title, "timestamp": firestore.SERVER_TIMESTAMP,
            })
            return candidate
        create.creating = True
        return await self._run(lambda db, checked: self._transaction(db, uid, checked, create), check)

    async def get_artifact(self, uid, artifact_id):
        self._uid(uid)
        artifact_id = self._artifact_id(artifact_id)
        return await self._run(lambda db, _: self._decode(
            self._user(db, uid).collection("artifacts").document(artifact_id).get(retry=None, timeout=5)))

    async def list_artifacts(self, uid, cursor=None):
        self._uid(uid)
        if cursor is not None:
            cursor = self._artifact_id(cursor)
        def load(db, _):
            collection = self._user(db, uid).collection("artifacts")
            query = collection.order_by("__name__").limit(PAGE_SIZE + 1)
            if cursor:
                query = query.start_after({"__name__": collection.document(cursor)})
            docs = list(query.stream(retry=None, timeout=5))
            items = [artifact_metadata(self._decode(doc)) for doc in docs[:PAGE_SIZE]]
            return {"items": items, "next_cursor": docs[PAGE_SIZE - 1].id if len(docs) > PAGE_SIZE else None}
        return await self._run(load)

    async def _update(self, uid, request, check, state):
        self._uid(uid)
        def change(tx, user):
            ref = user.collection("artifacts").document(request.artifact_id)
            previous = self._decode(ref.get(transaction=tx, retry=None, timeout=5))
            expected = request.expected_state_revision if state else request.expected_revision
            if expected != (previous.state_revision if state else previous.revision):
                raise HTTPException(409, "ARTIFACT_REVISION_CONFLICT")
            try:
                candidate = apply_state_update(previous, request) if state else apply_spec_update(previous, request)
            except ValueError as exc:
                raise HTTPException(422, "INVALID_ARTIFACT_STATE" if state else "INVALID_ARTIFACT_SPEC") from exc
            if candidate != previous:
                data = self._stored(candidate)
                data["updated_at"] = firestore.SERVER_TIMESTAMP
                tx.set(ref, data)
            return candidate
        return await self._run(lambda db, checked: self._transaction(db, uid, checked, change), check)

    async def update_state(self, uid, update, check):
        return await self._update(uid, StateUpdate.model_validate(update), check, True)

    async def update_spec(self, uid, decision, check):
        return await self._update(uid, GeneratedUIEditDecision.model_validate(decision), check, False)

    async def delete_artifact(self, uid, artifact_id, check):
        self._uid(uid)
        artifact_id = self._artifact_id(artifact_id)
        def delete(tx, user):
            ref = user.collection("artifacts").document(artifact_id)
            if not ref.get(transaction=tx, retry=None, timeout=5).exists:
                raise HTTPException(404, "ARTIFACT_NOT_FOUND")
            # No subcollections: state is inline. Malformed artifacts can also be deleted.
            tx.delete(ref)
            tx.delete(user.collection("canvas_history").document("artifact_" + artifact_id))
        await self._run(lambda db, checked: self._transaction(db, uid, checked, delete), check)

    async def clear_user_artifacts(self, uid, check):
        self._uid(uid)
        token = str(uuid4())
        def start(db, checked):
            control = self._user(db, uid).collection("artifact_control").document("state")
            @firestore.transactional
            def mark(tx):
                control.get(transaction=tx, retry=None, timeout=5)
                tx.set(control, {"clearing_token": token})
                checked()
            mark(db.transaction())
        await self._run(start, check)
        deleted = 0
        while True:
            def page(tx, user):
                docs = list(user.collection("artifacts").limit(DELETE_PAGE_SIZE).stream(transaction=tx, retry=None, timeout=5))
                for doc in docs:
                    tx.delete(doc.reference)
                    tx.delete(user.collection("canvas_history").document("artifact_" + doc.id))
                return len(docs)
            count = await self._run(lambda db, checked: self._transaction(db, uid, checked, page, clearing_token=token), check)
            deleted += count
            if not count:
                break
        def finish(tx, user):
            tx.set(user.collection("artifact_control").document("state"), {"clearing_token": None})
        await self._run(lambda db, checked: self._transaction(db, uid, checked, finish, clearing_token=token), check)
        return deleted
