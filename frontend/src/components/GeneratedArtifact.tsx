"use client";
import React from "react";
import { parseGeneratedArtifact, StudyStateEdit } from "../types/artifacts";
import StudyTracker from "./artifacts/StudyTracker";

export default function GeneratedArtifact({ artifact: input, onEdit, busy }: {
  artifact: unknown; onEdit: (edit: StudyStateEdit) => Promise<void>; busy?: boolean;
}) {
  const artifact = parseGeneratedArtifact(input);
  if (!artifact) return <p role="status">This artifact is unsupported or invalid.</p>;
  switch (artifact.renderer) {
    case "study_tracker_v1": return <StudyTracker key={artifact.artifact_id} artifact={artifact} onEdit={onEdit} busy={busy} />;
    default: return <p role="status">This artifact is unsupported.</p>;
  }
}
