"""User state operations, separate from model spec edits."""
from typing import Annotated, Literal, Union
from datetime import datetime, timezone
from pydantic import Field
from .contracts import (
    Contract, ArtifactId, StableId, Revision, StudyEntry, GeneratedArtifact,
    GeneratedUIEditDecision, SetSubjectColor, validate_artifact_transition,
)


class AddStudyEntry(Contract):
    operation: Literal["add_entry"]
    entry: StudyEntry


class RemoveStudyEntry(Contract):
    operation: Literal["remove_entry"]
    entry_id: StableId


class StateUpdate(Contract):
    request_id: ArtifactId
    artifact_id: ArtifactId
    expected_state_revision: Revision
    edit: Annotated[Union[AddStudyEntry, RemoveStudyEntry], Field(discriminator="operation")]


def apply_state_update(artifact: GeneratedArtifact, update: StateUpdate) -> GeneratedArtifact:
    artifact = GeneratedArtifact.model_validate(artifact)
    update = StateUpdate.model_validate(update)
    if update.artifact_id != artifact.artifact_id:
        raise ValueError("artifact mismatch")
    data = artifact.model_dump(mode="json")
    entries = data["state"]["entries"]
    if isinstance(update.edit, AddStudyEntry):
        entries.append(update.edit.entry.model_dump(mode="json"))
    else:
        if not any(e["id"] == update.edit.entry_id for e in entries):
            raise ValueError("entry not found")
        data["state"]["entries"] = [e for e in entries if e["id"] != update.edit.entry_id]
    data["state_revision"] += 1
    data["updated_at"] = max(datetime.now(timezone.utc), artifact.updated_at)
    return validate_artifact_transition(artifact, GeneratedArtifact.model_validate(data))


def apply_spec_update(artifact: GeneratedArtifact, decision: GeneratedUIEditDecision) -> GeneratedArtifact:
    artifact = GeneratedArtifact.model_validate(artifact)
    decision = GeneratedUIEditDecision.model_validate(decision)
    if artifact.artifact_id != decision.artifact_id:
        raise ValueError("artifact mismatch")
    data = artifact.model_dump(mode="json")
    if isinstance(decision.edit, SetSubjectColor):
        subject = next((s for s in data["spec"]["subjects"] if s["id"] == decision.edit.subject_id), None)
        if subject is None:
            raise ValueError("unknown subject")
        subject["color_token"] = decision.edit.color_token
    else:
        data["spec"]["show_daily_graph"] = decision.edit.enabled
    if data["spec"] == artifact.model_dump(mode="json")["spec"]:
        return artifact
    data["revision"] += 1
    data["updated_at"] = max(datetime.now(timezone.utc), artifact.updated_at)
    return validate_artifact_transition(artifact, GeneratedArtifact.model_validate(data))
