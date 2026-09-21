"""Offline structural and cross-field validation for generated artifact v1."""

import copy
import datetime as dt
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.artifacts.contracts import (
    MAX_ENTRIES, MAX_ID_LENGTH, MAX_MINUTES_PER_ENTRY, MAX_REVISION,
    MAX_SUBJECT_LABEL_LENGTH, MAX_SUBJECTS, MAX_TITLE_LENGTH, MAX_VERSION_LENGTH,
    OUTPUT_DECISION_ADAPTER, STUDY_TRACKER_EDIT_ADAPTER,
    ArtifactResult, GeneratedArtifact, GeneratedUICreateDecision,
    SetDailyGraphVisibility, SetSubjectColor, StudyEntry, StudySubject,
    StudyTrackerSpec, StudyTrackerState, validate_artifact_transition,
)


FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "artifacts"


def load_fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def artifact_data():
    return load_fixture("valid_study_tracker")


@pytest.fixture
def create_data(artifact_data):
    return {
        "mode": "generated_ui", "renderer": "study_tracker_v1",
        "operation": "create", "title": artifact_data["title"],
        "spec": artifact_data["spec"],
    }


@pytest.fixture
def entry_data():
    return {"id": "entry_1", "subject_id": "economics", "date": "2026-09-14", "minutes": 60}


@pytest.mark.parametrize("payload", [
    {"mode": "conversation"}, {"mode": "artifact", "title": "Study plan"},
])
def test_non_ui_modes_are_semantic_decisions(payload):
    assert OUTPUT_DECISION_ADAPTER.validate_python(payload).model_dump() == payload


def test_create_accepts_spec_without_identity_or_state(create_data):
    decision = OUTPUT_DECISION_ADAPTER.validate_python(create_data)
    assert isinstance(decision, GeneratedUICreateDecision)
    assert decision.spec.subjects[0].label == "Economics"
    assert not {"artifact_id", "state", "expected_revision"} & decision.model_dump().keys()


@pytest.mark.parametrize("mode", ["search", "action", "browser", "android", "tool", "unknown", "GENERATED_UI", None, 1])
def test_unimplemented_modes_rejected(mode):
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_python({"mode": mode})


@pytest.mark.parametrize("field,value", [
    ("renderer", "react"), ("renderer", "study_tracker_v2"),
    ("operation", "delete"), ("operation", "eval"),
])
def test_only_known_renderer_and_operation(create_data, field, value):
    create_data[field] = value
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_python(create_data)


@pytest.mark.parametrize("missing", ["artifact_id", "expected_revision", "edit"])
def test_edit_requires_target_revision_and_operation(missing):
    payload = load_fixture("valid_color_edit")
    del payload[missing]
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_python(payload)


@pytest.mark.parametrize("field,value", [
    ("artifact_id", "550e8400-e29b-41d4-a716-446655440000"),
    ("expected_revision", 0), ("state", {"entries": []}),
    ("revision", 0), ("state_revision", 0), ("created_at", "2026-09-14T09:00:00Z"),
    ("generation_version", "1"), ("edit", {"operation": "set_daily_graph_visibility", "enabled": True}),
])
def test_create_cannot_nominate_server_fields_or_user_history(create_data, field, value):
    create_data[field] = value
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_python(create_data)


@pytest.mark.parametrize("name", ["valid_color_edit", "valid_graph_edit", "valid_add_subject"])
def test_shared_valid_edits_round_trip(name):
    payload = load_fixture(name)
    decision = OUTPUT_DECISION_ADAPTER.validate_python(payload)
    assert decision == OUTPUT_DECISION_ADAPTER.validate_json(json.dumps(payload))
    assert decision.model_dump(mode="json") == payload


def test_shared_empty_tracker_fixture():
    artifact = GeneratedArtifact.model_validate(load_fixture("valid_empty_study_tracker"))
    assert artifact.spec.subjects == () and artifact.state.entries == ()


@pytest.mark.parametrize("name", ["invalid_renderer", "invalid_color"])
def test_shared_invalid_fixtures_fail(name):
    payload = load_fixture(name)
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_python(payload)
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_json(json.dumps(payload))


@pytest.mark.parametrize("color", ["red", "blue", "green", "gold", "purple", "teal", "orange"])
def test_color_allowlist(color):
    assert StudySubject(id="economics", label="Economics", color_token=color).color_token == color


@pytest.mark.parametrize("color", ["#ff0000", "rgb(255,0,0)", "url(x)", "background:red", "red-500", "RED", ""])
def test_css_and_unknown_colors_rejected(color):
    with pytest.raises(ValidationError):
        StudySubject(id="economics", label="Economics", color_token=color)
    with pytest.raises(ValidationError):
        SetSubjectColor(operation="set_subject_color", subject_id="economics", color_token=color)


@pytest.mark.parametrize("label", ["", "  ", "x" * (MAX_SUBJECT_LABEL_LENGTH + 1), 123])
def test_invalid_labels(label):
    with pytest.raises(ValidationError):
        StudySubject(id="economics", label=label, color_token="red")


def test_subject_limits_and_uniqueness(artifact_data):
    spec = artifact_data["spec"]
    spec["subjects"] = [
        {"id": f"s{i}", "label": "x" * MAX_SUBJECT_LABEL_LENGTH, "color_token": "red"}
        for i in range(MAX_SUBJECTS)
    ]
    assert len(StudyTrackerSpec.model_validate(spec).subjects) == MAX_SUBJECTS
    spec["subjects"].append({"id": "overflow", "label": "Extra", "color_token": "red"})
    with pytest.raises(ValidationError):
        StudyTrackerSpec.model_validate(spec)
    spec["subjects"] = [spec["subjects"][0]] * 2
    with pytest.raises(ValidationError):
        StudyTrackerSpec.model_validate(spec)
    spec["subjects"] = []
    assert StudyTrackerSpec.model_validate(spec).subjects == ()


@pytest.mark.parametrize("identifier", ["", "../owner", "users/abc", "https://evil.example", "x" * (MAX_ID_LENGTH + 1)])
def test_stable_identifiers_are_not_paths_or_urls(identifier, entry_data):
    for field in ("id", "subject_id"):
        with pytest.raises(ValidationError):
            StudyEntry.model_validate({**entry_data, field: identifier})


@pytest.mark.parametrize("minutes", [0, -1, MAX_MINUTES_PER_ENTRY + 1, True, 1.5, "60", None])
def test_invalid_minutes(entry_data, minutes):
    with pytest.raises(ValidationError):
        StudyEntry.model_validate({**entry_data, "minutes": minutes})


def test_minutes_bounds_and_valid_date(entry_data):
    for minutes in (1, MAX_MINUTES_PER_ENTRY):
        entry = StudyEntry.model_validate({**entry_data, "minutes": minutes})
        assert entry.minutes == minutes
        assert entry.date == dt.date(2026, 9, 14)


@pytest.mark.parametrize("date", ["2026-02-30", "2026-9-14", "14/09/2026", "20260914", "2026-09-14T00:00:00Z", 0, True, dt.datetime(2026, 9, 14)])
def test_dates_reject_coercion_or_ambiguity(entry_data, artifact_data, date):
    with pytest.raises(ValidationError):
        StudyEntry.model_validate({**entry_data, "date": date})
    with pytest.raises(ValidationError):
        StudyTrackerSpec.model_validate({**artifact_data["spec"], "week_start": date})


def test_entry_limit_and_duplicate_ids(entry_data):
    entries = [{**entry_data, "id": f"entry_{i}"} for i in range(MAX_ENTRIES)]
    assert len(StudyTrackerState(entries=entries).entries) == MAX_ENTRIES
    with pytest.raises(ValidationError):
        StudyTrackerState(entries=entries + [{**entry_data, "id": "overflow"}])
    with pytest.raises(ValidationError):
        StudyTrackerState(entries=[entry_data, entry_data])


def test_default_state_is_empty_and_artifact_json_round_trips(artifact_data):
    artifact = GeneratedArtifact.model_validate(artifact_data)
    assert artifact.state.entries == ()
    assert artifact == GeneratedArtifact.model_validate_json(artifact.model_dump_json())
    del artifact_data["state"]
    assert GeneratedArtifact.model_validate(artifact_data).state.entries == ()


@pytest.mark.parametrize("field,value", [
    ("subject_id", "missing"), ("date", "2026-09-13"), ("date", "2026-09-21"),
])
def test_entry_must_reference_spec_and_week(artifact_data, entry_data, field, value):
    artifact_data["state"]["entries"] = [{**entry_data, field: value}]
    with pytest.raises(ValidationError):
        GeneratedArtifact.model_validate(artifact_data)


def test_week_and_daily_total_boundaries(artifact_data, entry_data):
    artifact_data["state"]["entries"] = [{**entry_data, "date": "2026-09-20", "minutes": 1440}]
    assert GeneratedArtifact.model_validate(artifact_data).state.entries[0].minutes == 1440
    artifact_data["state"]["entries"].append({**entry_data, "id": "entry_2", "date": "2026-09-20", "minutes": 1})
    with pytest.raises(ValidationError):
        GeneratedArtifact.model_validate(artifact_data)


@pytest.mark.parametrize("revision", [-1, True, 0.0, "0", MAX_REVISION + 1])
def test_revisions_are_strict_bounded_integers(artifact_data, revision):
    for field in ("revision", "state_revision"):
        with pytest.raises(ValidationError):
            GeneratedArtifact.model_validate({**artifact_data, field: revision})
    edit = load_fixture("valid_color_edit")
    edit["expected_revision"] = revision
    with pytest.raises(ValidationError):
        OUTPUT_DECISION_ADAPTER.validate_python(edit)


@pytest.mark.parametrize("field,value", [
    ("schema_version", 2), ("schema_version", True), ("schema_version", 1.0),
    ("schema_version", "1"), ("renderer", "react"), ("kind", "artifact"),
    ("artifact_id", "chosen_by_model"), ("artifact_id", "550e8400-e29b-11d4-a716-446655440000"),
    ("title", "x" * (MAX_TITLE_LENGTH + 1)), ("title", "  "),
    ("generation_version", "x" * (MAX_VERSION_LENGTH + 1)),
    ("validation_version", "https://evil.example"),
    ("created_at", "2026-09-14T09:00:00"), ("updated_at", 0),
    ("updated_at", "2026-09-13T09:00:00Z"),
])
def test_envelope_constraints(artifact_data, field, value):
    with pytest.raises(ValidationError):
        GeneratedArtifact.model_validate({**artifact_data, field: value})


@pytest.mark.parametrize("enabled", [True, False])
def test_graph_operation_is_only_a_boolean(enabled):
    edit = STUDY_TRACKER_EDIT_ADAPTER.validate_python({"operation": "set_daily_graph_visibility", "enabled": enabled})
    assert isinstance(edit, SetDailyGraphVisibility)
    assert edit.enabled is enabled
    assert "state" not in edit.model_dump()


@pytest.mark.parametrize("enabled", [0, 1, "true", "false", None])
def test_graph_flag_does_not_coerce(enabled):
    with pytest.raises(ValidationError):
        SetDailyGraphVisibility(operation="set_daily_graph_visibility", enabled=enabled)


@pytest.mark.parametrize("operation", ["set_property", "eval", "custom_css", "custom_javascript", "custom_component", "custom_event", "network_request"])
def test_no_generic_mutation_language(operation):
    with pytest.raises(ValidationError):
        STUDY_TRACKER_EDIT_ADAPTER.validate_python({"operation": operation, "path": "state.entries", "value": []})


@pytest.mark.parametrize("field", ["state", "entries", "spec", "path", "value"])
def test_edits_cannot_replace_state_or_spec(field):
    payload = load_fixture("valid_color_edit")
    for location in (payload, payload["edit"]):
        invalid = copy.deepcopy(payload)
        target = invalid if location is payload else invalid["edit"]
        target[field] = []
        with pytest.raises(ValidationError):
            OUTPUT_DECISION_ADAPTER.validate_python(invalid)


HOSTILE_TEXT = [
    "<script>alert(1)</script>", "javascript:alert(1)", "https://evil.example",
    "background:url(x)", "onClick", "eval(x)", "fetch(x)",
    "document.cookie", "window.parent", "The window of opportunity",
]


@pytest.mark.parametrize("text", HOSTILE_TEXT)
def test_labels_are_literal_text_not_a_keyword_filter(text):
    subject = StudySubject(id="literal_text", label=text, color_token="red")
    assert subject.model_dump(mode="json") == {"id": "literal_text", "label": text, "color_token": "red"}
    # This is not HTML sanitization; the future trusted renderer must escape it.
    assert StudySubject.model_validate_json(subject.model_dump_json()) == subject


@pytest.mark.parametrize("field", [
    "html", "javascript", "css", "url", "className", "onClick", "eval",
    "fetch", "network", "dom", "uid", "owner", "token", "firebase_token", "firestore_path",
])
def test_capabilities_and_credentials_are_forbidden_at_every_level(artifact_data, entry_data, create_data, field):
    inputs = [
        (GeneratedArtifact, artifact_data), (StudyTrackerSpec, artifact_data["spec"]),
        (StudySubject, artifact_data["spec"]["subjects"][0]),
        (StudyTrackerState, artifact_data["state"]), (StudyEntry, entry_data),
    ]
    for model, payload in inputs:
        with pytest.raises(ValidationError):
            model.model_validate({**payload, field: "https://evil.example"})
    for payload in (create_data, load_fixture("valid_color_edit"), {"mode": "conversation"}, {"mode": "artifact", "title": "Plan"}):
        with pytest.raises(ValidationError):
            OUTPUT_DECISION_ADAPTER.validate_python({**payload, field: "document.cookie"})
    with pytest.raises(ValidationError):
        STUDY_TRACKER_EDIT_ADAPTER.validate_python({**load_fixture("valid_color_edit")["edit"], field: "fetch(x)"})


def test_validated_snapshots_are_deeply_immutable(artifact_data):
    artifact = GeneratedArtifact.model_validate(artifact_data)
    with pytest.raises(ValidationError):
        artifact.revision = -1
    with pytest.raises(ValidationError):
        artifact.spec.subjects[0].color_token = "blue"
    with pytest.raises(AttributeError):
        artifact.state.entries.append("bad")
    artifact_data["spec"]["subjects"][0]["label"] = "Changed source dictionary"
    assert artifact.spec.subjects[0].label == "Economics"


def test_spec_transition_preserves_existing_user_state(artifact_data, entry_data):
    artifact_data["state"] = {"entries": [entry_data]}
    previous = GeneratedArtifact.model_validate(artifact_data)
    candidate_data = previous.model_dump(mode="json")
    candidate_data["spec"]["subjects"][0]["color_token"] = "red"
    candidate_data["spec"]["show_daily_graph"] = True
    candidate_data["revision"] = 1
    candidate = GeneratedArtifact.model_validate(candidate_data)
    assert validate_artifact_transition(previous, candidate).state == previous.state
    assert candidate.state_revision == previous.state_revision == 0
    assert previous.spec.subjects[0].color_token == "gold"


def test_state_transition_does_not_advance_spec(artifact_data, entry_data):
    previous = GeneratedArtifact.model_validate(artifact_data)
    artifact_data["state"] = {"entries": [entry_data]}
    artifact_data["state_revision"] = 1
    candidate = GeneratedArtifact.model_validate(artifact_data)
    assert validate_artifact_transition(previous, candidate).revision == previous.revision


@pytest.mark.parametrize("field", ["revision", "state_revision"])
def test_transition_rejects_rollback_or_unearned_increment(artifact_data, field):
    artifact_data[field] = 2
    previous = GeneratedArtifact.model_validate(artifact_data)
    for value in (1, 3):
        candidate = GeneratedArtifact.model_validate({**artifact_data, field: value})
        with pytest.raises(ValueError):
            validate_artifact_transition(previous, candidate)
    assert validate_artifact_transition(previous, previous) == previous


def test_changed_state_cannot_hide_behind_same_revision(artifact_data, entry_data):
    previous = GeneratedArtifact.model_validate(artifact_data)
    artifact_data["state"] = {"entries": [entry_data]}
    with pytest.raises(ValueError):
        validate_artifact_transition(previous, GeneratedArtifact.model_validate(artifact_data))


def test_transition_rejects_target_switch_and_revalidates_instances(artifact_data):
    previous = GeneratedArtifact.model_validate(artifact_data)
    other = GeneratedArtifact.model_validate({**artifact_data, "artifact_id": "650e8400-e29b-41d4-a716-446655440000"})
    with pytest.raises(ValueError):
        validate_artifact_transition(previous, other)
    forged = previous.model_copy(update={"renderer": "custom_component"})
    with pytest.raises(ValidationError):
        validate_artifact_transition(previous, forged)


def result_payload(artifact_data):
    return {
        "type": "artifact_result", "request_id": "750e8400-e29b-41d4-a716-446655440000",
        "artifact_id": artifact_data["artifact_id"], "revision": artifact_data["revision"],
        "state_revision": artifact_data["state_revision"], "renderer": artifact_data["renderer"],
        "artifact": artifact_data,
    }


@pytest.mark.parametrize("event_type", ["artifact_result", "artifact_update"])
def test_result_preserves_correlation(artifact_data, event_type):
    payload = {**result_payload(artifact_data), "type": event_type}
    result = ArtifactResult.model_validate(payload)
    assert result == ArtifactResult.model_validate_json(result.model_dump_json())
    assert result.artifact_id == result.artifact.artifact_id


@pytest.mark.parametrize("field,value", [
    ("artifact_id", "650e8400-e29b-41d4-a716-446655440000"),
    ("revision", 1), ("state_revision", 1), ("renderer", "custom_component"),
    ("request_id", "https://evil.example"), ("type", "execute"), ("url", "https://evil.example"),
])
def test_result_rejects_inconsistent_or_unsafe_metadata(artifact_data, field, value):
    with pytest.raises(ValidationError):
        ArtifactResult.model_validate({**result_payload(artifact_data), field: value})


def test_json_schema_retains_discriminators_and_closed_objects():
    schema = OUTPUT_DECISION_ADAPTER.json_schema()
    assert set(schema["discriminator"]["mapping"]) == {"conversation", "artifact", "generated_ui"}
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False
