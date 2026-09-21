"""Data-only contracts; no routing, generation, rendering, or persistence.

Parse untrusted input with model_validate/model_validate_json or the adapters.
Do not use model_construct or model_copy(update=...) as validation boundaries.
Labels/titles are literal text, NOT sanitized markup: future renderers must use
escaped text nodes and must never interpret them as HTML, CSS, code, or URLs.

Create decisions cannot nominate artifact IDs, ownership, provenance, or state.
Persisted envelopes are server-assembled. UUID syntax cannot prove that an ID
was issued by the server: authenticated target lookup/authorization is still
required when wiring edits. Revision comparisons belong in an atomic repository
operation later; validate_artifact_transition supplies its pure invariant check.
"""

import datetime as dt
import re
from typing import Annotated, Literal, Union

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    model_validator,
)


# Personal weekly tracker bounds, shared with future client parity tests.
MAX_TITLE_LENGTH = 120
MAX_SUBJECT_LABEL_LENGTH = 80
MAX_SUBJECTS = 20
MAX_ENTRIES = 200
MAX_MINUTES_PER_ENTRY = 1440  # A full day is the absolute physical maximum.
MAX_MINUTES_PER_DAY = 1440
MAX_ID_LENGTH = 64
MAX_VERSION_LENGTH = 32
MAX_REVISION = 2**53 - 1  # JSON integers must round-trip exactly in JavaScript.
WEEK_DAYS = 7

ColorToken = Literal["red", "blue", "green", "gold", "purple", "teal", "orange"]
Renderer = Literal["study_tracker_v1"]
Title = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH)
]
SubjectLabel = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=MAX_SUBJECT_LABEL_LENGTH)
]
StableId = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=MAX_ID_LENGTH, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
]
ArtifactId = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=36,
        max_length=36,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    ),
]
Version = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=MAX_VERSION_LENGTH, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
]
Revision = Annotated[int, Field(strict=True, ge=0, le=MAX_REVISION)]
Minutes = Annotated[int, Field(strict=True, ge=1, le=MAX_MINUTES_PER_ENTRY)]


def _iso_date(value: object) -> dt.date:
    """Accept date objects or canonical YYYY-MM-DD, never epochs/datetimes."""
    if type(value) is dt.date:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return dt.date.fromisoformat(value)
    raise ValueError("date must be YYYY-MM-DD or a date object")


def _timestamp(value: object) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value
    ):
        return dt.datetime.fromisoformat(value)
    raise ValueError("timestamp must be a timezone-aware ISO datetime")


def _schema_version(value: object) -> int:
    # Literal[1] alone also accepts True/1.0 through equality.
    if type(value) is not int or value != 1:
        raise ValueError("schema_version must be integer 1")
    return value


def _immutable_array(value: object) -> object:
    # JSON arrays become tuples so a validated frozen model cannot be changed
    # through append/pop; other input types still fail strict tuple validation.
    return tuple(value) if isinstance(value, list) else value


ISODate = Annotated[dt.date, BeforeValidator(_iso_date)]
Timestamp = Annotated[AwareDatetime, BeforeValidator(_timestamp)]
SchemaVersion = Annotated[Literal[1], BeforeValidator(_schema_version)]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True,
        validate_default=True, revalidate_instances="always",
    )


class StudySubject(Contract):
    id: StableId
    label: SubjectLabel
    color_token: ColorToken


class StudyEntry(Contract):
    id: StableId
    subject_id: StableId
    date: ISODate
    minutes: Minutes


class StudyTrackerSpec(Contract):
    """An explicit seven-day window; no assumed locale or automatic rollover."""

    week_start: ISODate
    subjects: Annotated[
        tuple[StudySubject, ...], BeforeValidator(_immutable_array),
        Field(max_length=MAX_SUBJECTS),
    ]
    show_daily_graph: bool = False

    @model_validator(mode="after")
    def valid_subjects_and_week(self) -> "StudyTrackerSpec":
        ids = [subject.id for subject in self.subjects]
        if len(set(ids)) != len(ids):
            raise ValueError("subject IDs must be unique")
        if self.week_start > dt.date.max - dt.timedelta(days=WEEK_DAYS - 1):
            raise ValueError("week_start must allow a complete seven-day window")
        return self


class StudyTrackerState(Contract):
    entries: Annotated[
        tuple[StudyEntry, ...], BeforeValidator(_immutable_array),
        Field(max_length=MAX_ENTRIES),
    ] = ()

    @model_validator(mode="after")
    def unique_entries(self) -> "StudyTrackerState":
        ids = [entry.id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("entry IDs must be unique")
        return self


class SetSubjectColor(Contract):
    operation: Literal["set_subject_color"]
    subject_id: StableId
    color_token: ColorToken


class SetDailyGraphVisibility(Contract):
    operation: Literal["set_daily_graph_visibility"]
    enabled: bool


class AddSubject(Contract):
    operation: Literal["add_subject"]
    subject: StudySubject


StudyTrackerEdit = Annotated[
    Union[SetSubjectColor, SetDailyGraphVisibility, AddSubject], Field(discriminator="operation")
]
STUDY_TRACKER_EDIT_ADAPTER = TypeAdapter(StudyTrackerEdit)


class ConversationDecision(Contract):
    mode: Literal["conversation"]


class ArtifactDecision(Contract):
    mode: Literal["artifact"]
    title: Title


class GeneratedUICreateDecision(Contract):
    """Model-created configuration only. Initial user state is always empty."""

    mode: Literal["generated_ui"]
    renderer: Renderer
    operation: Literal["create"]
    title: Title
    spec: StudyTrackerSpec


class GeneratedUIEditDecision(Contract):
    """Target is supplied/resolved by the host, then authorized server-side."""

    mode: Literal["generated_ui"]
    renderer: Renderer
    operation: Literal["edit"]
    artifact_id: ArtifactId
    expected_revision: Revision
    edit: StudyTrackerEdit


GeneratedUIDecision = Annotated[
    Union[GeneratedUICreateDecision, GeneratedUIEditDecision], Field(discriminator="operation")
]
OutputDecision = Annotated[
    Union[ConversationDecision, ArtifactDecision, GeneratedUIDecision], Field(discriminator="mode")
]
OUTPUT_DECISION_ADAPTER = TypeAdapter(OutputDecision)


class GeneratedArtifact(Contract):
    """Server-owned envelope, never a model-output schema or an auth claim."""

    artifact_id: ArtifactId
    kind: Literal["generated_ui"]
    renderer: Renderer
    schema_version: SchemaVersion
    revision: Revision
    state_revision: Revision
    title: Title
    spec: StudyTrackerSpec
    state: StudyTrackerState = Field(default_factory=StudyTrackerState)
    created_at: Timestamp
    updated_at: Timestamp
    source_session_id: StableId
    validation_version: Version
    generation_version: Version

    @model_validator(mode="after")
    def consistent_artifact(self) -> "GeneratedArtifact":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        subject_ids = {subject.id for subject in self.spec.subjects}
        daily_minutes: dict[dt.date, int] = {}
        for entry in self.state.entries:
            if entry.subject_id not in subject_ids:
                raise ValueError("entry references an unknown subject")
            if not 0 <= (entry.date - self.spec.week_start).days < WEEK_DAYS:
                raise ValueError("entry date must be inside the artifact's week")
            daily_minutes[entry.date] = daily_minutes.get(entry.date, 0) + entry.minutes
            if daily_minutes[entry.date] > MAX_MINUTES_PER_DAY:
                raise ValueError("total study minutes cannot exceed one day")
        return self


def validate_artifact_transition(
    previous: GeneratedArtifact, candidate: GeneratedArtifact,
) -> GeneratedArtifact:
    """Validate a candidate snapshot without applying any edit or writing data.

    Each changed domain advances its counter by exactly one; an unchanged domain
    retains its counter. The future repository must compare previous against the
    authoritative stored version atomically. This helper alone is not CAS.
    """
    previous = GeneratedArtifact.model_validate(previous)
    candidate = GeneratedArtifact.model_validate(candidate)
    for field in ("artifact_id", "kind", "renderer", "schema_version", "created_at", "source_session_id"):
        if getattr(previous, field) != getattr(candidate, field):
            raise ValueError(f"{field} cannot change within an artifact")
    if candidate.updated_at < previous.updated_at:
        raise ValueError("updated_at cannot move backwards")
    spec_changed = any(
        getattr(previous, field) != getattr(candidate, field)
        for field in ("title", "spec", "validation_version", "generation_version")
    )
    state_changed = previous.state != candidate.state
    if candidate.revision != previous.revision + int(spec_changed):
        raise ValueError("revision must advance exactly once for a spec/provenance change")
    if candidate.state_revision != previous.state_revision + int(state_changed):
        raise ValueError("state_revision must advance exactly once for a state change")
    return candidate


class ArtifactResult(Contract):
    """Future socket snapshot. Consumer must also check pending request/target IDs.

    Matching metadata prevents internally inconsistent events; cancellation and
    comparison with the currently selected/stored revision require host state.
    """

    type: Literal["artifact_result", "artifact_update"]
    request_id: ArtifactId
    artifact_id: ArtifactId
    revision: Revision
    state_revision: Revision
    renderer: Renderer
    artifact: GeneratedArtifact

    @model_validator(mode="after")
    def matching_payload(self) -> "ArtifactResult":
        for field in ("artifact_id", "revision", "state_revision", "renderer"):
            if getattr(self, field) != getattr(self.artifact, field):
                raise ValueError(f"result {field} must match artifact payload")
        return self
