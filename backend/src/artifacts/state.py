"""User state operations, separate from model spec edits."""
from typing import Annotated, Literal, Union
from datetime import datetime, timezone
from pydantic import Field
from .contracts import (
    Contract, ArtifactId, StableId, Revision, StudyEntry, GeneratedArtifact,
    validate_artifact_transition,
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
    data["updated_at"] = datetime.now(timezone.utc)
    return validate_artifact_transition(artifact, GeneratedArtifact.model_validate(data))
