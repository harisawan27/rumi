"""Execute the closed planner capability set through the durable repository."""
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import uuid4
from fastapi import HTTPException
from .contracts import (ArtifactResult, GeneratedArtifact, GeneratedUICreateDecision,
                        GeneratedUIEditDecision, SetSubjectColor, SetDailyGraphVisibility)
from .planner import plan_output, create_intent

log = logging.getLogger(__name__)


def current_week(tz_name="UTC", now=None):
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = timezone.utc
    today = (now or datetime.now(timezone.utc)).astimezone(zone).date()
    return today - timedelta(days=today.weekday())


async def plan_and_execute(*, text, uid, session_id, request_id, selected_id,
                           has_canvas, timezone_name, repository, check, provider, progress):
    started = time.perf_counter()
    await check()
    active = await repository.get_artifact(uid, selected_id) if selected_id else None
    await check()
    await progress("understanding")
    result = await plan_output(text, active, has_canvas, current_week(timezone_name), provider)
    await check()  # planning is an untrusted, interruptible delay
    decision = result.decision
    if not isinstance(decision, (GeneratedUICreateDecision, GeneratedUIEditDecision)):
        return result, None, None
    # Capability policy is intentionally independent of the prompt/schema.
    if decision.renderer != "study_tracker_v1":
        raise HTTPException(422, "UNSUPPORTED_ARTIFACT")
    before_store = time.perf_counter()
    if isinstance(decision, GeneratedUICreateDecision):
        if not create_intent(text) or decision.spec.week_start != current_week(timezone_name):
            raise HTTPException(422, "UNSUPPORTED_ARTIFACT_CREATE")
        await progress("creating")
        now = datetime.now(timezone.utc)
        artifact = GeneratedArtifact.model_validate({"artifact_id": str(uuid4()), "kind": "generated_ui",
            "renderer": decision.renderer, "schema_version": 1, "revision": 0, "state_revision": 0,
            "title": decision.title, "spec": decision.spec, "state": {"entries": []},
            "created_at": now, "updated_at": now, "source_session_id": session_id,
            "validation_version": "1", "generation_version": "planner-1"})
        await check()
        await progress("saving")
        artifact = await repository.create_artifact(uid, artifact, check)
        acknowledgment = "Done — I made you a tracker for this week. Add your subjects to get started."
        event = "artifact_result"
    else:
        if (active is None or decision.artifact_id != selected_id or decision.expected_revision != active.revision
                or not isinstance(decision.edit, (SetSubjectColor, SetDailyGraphVisibility))):
            raise HTTPException(422, "UNSUPPORTED_ARTIFACT_EDIT")
        await progress("updating")
        await check()
        artifact = await repository.update_spec(uid, decision, check)
        if isinstance(decision.edit, SetSubjectColor):
            label = next(s.label for s in artifact.spec.subjects if s.id == decision.edit.subject_id)
            acknowledgment = f"Done — {label} is {decision.edit.color_token} now."
        else:
            acknowledgment = "Added the daily graph." if decision.edit.enabled else "Hidden the daily graph."
        event = "artifact_update"
    await check()
    envelope = ArtifactResult(type=event, request_id=request_id, artifact_id=artifact.artifact_id,
        revision=artifact.revision, state_revision=artifact.state_revision, renderer=artifact.renderer, artifact=artifact)
    log.info("create_execution event=%s persistence_ms=%.2f ready_ms=%.2f", event,
             (time.perf_counter() - before_store) * 1000, (time.perf_counter() - started) * 1000)
    return result, envelope, acknowledgment
