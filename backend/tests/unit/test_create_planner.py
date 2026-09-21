import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from src.artifacts.contracts import GeneratedArtifact, GeneratedUIEditDecision
from src.artifacts.planner import plan_output, needs_planner, context_projection, resolve_plan, PLAN_ADAPTER
from src.artifacts.service import current_week, plan_and_execute
from src.artifacts.repository import MemoryArtifactRepository
from src.artifacts.state import StateUpdate, apply_spec_update

DATA = json.loads((Path(__file__).resolve().parents[3] / "tests/fixtures/artifacts/valid_study_tracker.json").read_text())
WEEK = date(2026, 9, 14)
CREATE = {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "create",
          "title": "Study this week", "week": "current", "subjects": [], "show_daily_graph": False}
COLOR = {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "edit",
         "edit": {"operation": "set_subject_color", "subject_label": "Economics", "color_token": "red"}}
GRAPH = {"mode": "generated_ui", "renderer": "study_tracker_v1", "operation": "edit",
         "edit": {"operation": "set_daily_graph_visibility", "enabled": True}}


@pytest.fixture
def artifact():
    return GeneratedArtifact.model_validate(DATA)


@pytest.mark.parametrize("text,active,expected", [
    ("hello", False, False), ("explain economics", False, False),
    ("make me a study tracker for this week", False, True),
    ("I need to track my study time", False, True),
    ("I need to track how much I study this week.", False, True),
    ("make Economics red", True, True), ("show daily graph", True, True),
    ("hide the graph", True, True), ("What is a graph?", True, False),
    ("What's the best way to track study time?", False, False),
    ("Why do people procrastinate?", False, False),
])
def test_fast_path_matrix(text, active, expected):
    assert needs_planner(text, active) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("text,output,active,mode", [
    ("Give me a long structured comparison", {"mode": "artifact", "title": "Comparison"}, False, "artifact"),
    ("I need to track how much I study this week", CREATE, False, "generated_ui"),
    ("Make Economics red", COLOR, True, "generated_ui"),
    ("show daily graph", GRAPH, True, "generated_ui"),
    ("hide the graph", {**GRAPH, "edit": {"operation": "set_daily_graph_visibility", "enabled": False}}, True, "generated_ui"),
    ("Make Economics red", COLOR, False, "conversation"),
])
async def test_planner_matrix(artifact, text, output, active, mode):
    result = await plan_output(text, artifact if active else None, False, WEEK, AsyncMock(return_value=json.dumps(output)))
    assert result.decision.mode == mode


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["not json", "```json\n{}\n```", '{"mode":"generated_ui","renderer":"arbitrary_react","operation":"run_javascript"}',
    *[json.dumps({**CREATE, key: "forbidden"}) for key in ("uid", "path", "url", "html", "js", "css", "network", "state", "artifact_id")]])
async def test_invalid_plans_never_escape_and_repair_is_bounded(bad):
    provider = AsyncMock(return_value=bad)
    result = await plan_output("Create a study tracker", None, False, WEEK, provider)
    assert result.failed and result.decision.mode == "conversation"
    assert provider.await_count == 2


@pytest.mark.asyncio
async def test_repair_and_timeout():
    provider = AsyncMock(side_effect=["bad", json.dumps(CREATE)])
    result = await plan_output("Create a study tracker", None, False, WEEK, provider)
    assert result.repaired and not result.failed
    provider = AsyncMock(side_effect=TimeoutError)
    result = await plan_output("Create a study tracker", None, False, WEEK, provider)
    assert result.failed and provider.await_count == 1


def test_projection_omits_private_state_identity_and_ids(artifact):
    projection = context_projection("Show graph", artifact, True, WEEK)
    assert set(projection["active_generated_artifact"]) == {"renderer", "title", "revision", "subjects", "graph_enabled"}
    assert all(key not in json.dumps(projection) for key in ("entries", "uid", "artifact_id", "source_session_id"))


def test_authoritative_week_timezone():
    now = datetime(2026, 9, 20, 23, 30, tzinfo=timezone.utc)
    assert current_week("Asia/Karachi", now) == date(2026, 9, 21)
    assert current_week("America/New_York", now) == WEEK
    assert current_week("invalid/zone", now) == WEEK


@pytest.mark.parametrize("text", ["Make Economics red", "What is a study tracker?", "Create a study tracker for next week"])
def test_no_new_build_for_edit_or_unsupported_week(text, artifact):
    with pytest.raises(ValueError):
        resolve_plan(PLAN_ADAPTER.validate_python(CREATE), text, artifact, WEEK)


def test_no_invented_subjects():
    plan = PLAN_ADAPTER.validate_python({**CREATE, "subjects": [{"label": "Physics", "color_token": "blue"}]})
    with pytest.raises(ValueError):
        resolve_plan(plan, "Create a study tracker", None, WEEK)


def test_subject_exact_normalization_and_ambiguity(artifact):
    data = artifact.model_dump(mode="json")
    data["spec"]["subjects"].append({"id": "micro", "label": "Microeconomics", "color_token": "blue"})
    with_micro = GeneratedArtifact.model_validate(data)
    edit = resolve_plan(PLAN_ADAPTER.validate_python(COLOR), "Make economics red", with_micro, WEEK)
    assert edit.edit.subject_id == "economics"
    data["spec"]["subjects"].append({"id": "duplicate", "label": " ECONOMICS ", "color_token": "blue"})
    with pytest.raises(ValueError):
        resolve_plan(PLAN_ADAPTER.validate_python(COLOR), "Make economics red", GeneratedArtifact.model_validate(data), WEEK)


def test_add_subject_bounded_and_preserves_state(artifact):
    edit = GeneratedUIEditDecision.model_validate({"mode": "generated_ui", "renderer": "study_tracker_v1",
        "operation": "edit", "artifact_id": artifact.artifact_id, "expected_revision": 0,
        "edit": {"operation": "add_subject", "subject": {"id": "physics", "label": "Physics", "color_token": "blue"}}})
    added = apply_spec_update(artifact, edit)
    assert added.state == artifact.state and added.state_revision == artifact.state_revision
    assert added.revision == 1
    with pytest.raises(ValueError):
        apply_spec_update(added, edit)


@pytest.mark.asyncio
async def test_create_empty_and_correlated():
    repo = MemoryArtifactRepository()
    rid = str(uuid4())
    _, result, ack = await plan_and_execute(text="I need to track my study time", uid="owner", session_id="session",
        request_id=rid, selected_id=None, has_canvas=False, timezone_name="UTC", repository=repo,
        check=AsyncMock(), progress=AsyncMock(), provider=AsyncMock(return_value=json.dumps(CREATE)))
    assert result.request_id == rid and result.artifact.state.entries == () and result.artifact.spec.subjects == ()
    assert result.artifact_id in [a.artifact_id for a in repo.list("owner")]
    assert ack


@pytest.mark.asyncio
async def test_targeted_edits_preserve_data_and_other_tracker(artifact):
    repo = MemoryArtifactRepository()
    check = AsyncMock()
    a = await repo.create_artifact("owner", artifact, check)
    b = await repo.create_artifact("owner", GeneratedArtifact.model_validate({**DATA, "artifact_id": str(uuid4())}), check)
    a = await repo.update_state("owner", StateUpdate.model_validate({"request_id": str(uuid4()), "artifact_id": a.artifact_id,
        "expected_state_revision": 0, "edit": {"operation": "add_entry", "entry": {"id": "entry", "subject_id": "economics", "date": "2026-09-14", "minutes": 60}}}), check)
    for text, plan in (("Make Economics red", COLOR), ("Add a graph showing daily study time", GRAPH)):
        _, result, _ = await plan_and_execute(text=text, uid="owner", session_id="session", request_id=str(uuid4()),
            selected_id=a.artifact_id, has_canvas=True, timezone_name="UTC", repository=repo,
            check=check, progress=AsyncMock(), provider=AsyncMock(return_value=json.dumps(plan)))
        assert result.artifact.state == a.state and result.state_revision == 1
    assert result.revision == 2
    assert repo.get("owner", b.artifact_id) == b


@pytest.mark.asyncio
async def test_guest_transition_and_cancellation_before_persistence():
    for cancel in (False, True):
        repo = MemoryArtifactRepository()
        revoked = False
        async def check():
            if revoked:
                if cancel:
                    raise asyncio.CancelledError()
                raise HTTPException(403, "denied")
        async def provider(*args):
            nonlocal revoked
            revoked = True
            return json.dumps(CREATE)
        with pytest.raises(asyncio.CancelledError if cancel else HTTPException):
            await plan_and_execute(text="Create a study tracker", uid="owner", session_id="session", request_id=str(uuid4()),
                selected_id=None, has_canvas=False, timezone_name="UTC", repository=repo,
                check=check, progress=AsyncMock(), provider=provider)
        assert repo.list("owner") == []
