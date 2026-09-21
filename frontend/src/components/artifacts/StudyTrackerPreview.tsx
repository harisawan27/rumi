"use client";
/** Synthetic fixture harness only, unreachable in production. No Firebase/model calls. */
import React, { useEffect, useState, useSyncExternalStore } from "react";
import ArtifactCanvas from "../ArtifactCanvas";
import { ArtifactClient } from "../../services/artifactClient";
import { addStudyEntry, removeStudyEntry } from "../../services/studyTracker";
import { parseGeneratedArtifact, StudyStateEdit, StudySpecEdit } from "../../types/artifacts";
import CreateAcceptance from "./CreateAcceptance";

export default function StudyTrackerPreview({ fixture }: { fixture: unknown }) {
  const [acceptance, setAcceptance] = useState(false);
  useEffect(() => { setAcceptance(new URLSearchParams(window.location.search).get("acceptance") === "1"); }, []);
  return acceptance ? <CreateAcceptance /> : <FixturePreview fixture={fixture} />;
}

function FixturePreview({ fixture }: { fixture: unknown }) {
  const initial = parseGeneratedArtifact(fixture);
  if (!initial) throw new Error("Invalid development fixture");
  const initialId = initial.artifact_id;
  const [owner, setOwner] = useState(true);
  const [client] = useState(() => {
    let authoritative = initial;
    return new ArtifactClient(async (path, body) => {
      if (body && path.startsWith("state?")) {
        const edit = (body as { edit: StudyStateEdit }).edit;
        authoritative = edit.operation === "add_entry" ? addStudyEntry(authoritative, edit.entry) : removeStudyEntry(authoritative, edit.entry_id);
        authoritative = { ...authoritative, state_revision: authoritative.state_revision + 1 };
      } else if (body && path.startsWith("spec?")) {
        const edit = (body as { edit: StudySpecEdit }).edit;
        const spec = edit.operation === "add_subject" ? { ...authoritative.spec, subjects: [...authoritative.spec.subjects, edit.subject] }
          : edit.operation === "set_subject_color" ? { ...authoritative.spec, subjects: authoritative.spec.subjects.map(s => s.id === edit.subject_id ? { ...s, color_token: edit.color_token } : s) }
          : { ...authoritative.spec, show_daily_graph: edit.enabled };
        const candidate = parseGeneratedArtifact({ ...authoritative, revision: authoritative.revision + 1, spec });
        if (!candidate) throw new Error("Invalid preview edit");
        authoritative = candidate;
      }
      const requestId = new URLSearchParams(path.split("?")[1]).get("request_id");
      if (path.startsWith("access?")) return { request_id: requestId, lease_seconds: 5 };
      return { result: { type: "artifact_result", request_id: requestId, artifact_id: authoritative.artifact_id,
        revision: authoritative.revision, state_revision: authoritative.state_revision, renderer: authoritative.renderer, artifact: authoritative }, lease_seconds: 5 };
    });
  });
  const view = useSyncExternalStore(client.subscribe, client.snapshot, client.snapshot);
  useEffect(() => {
    client.configure("fixture_session", true);
    void client.load(initialId);
    return () => client.revoke();
  }, [client, initialId]);
  return <main style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "#04080f", color: "#e2e8f0" }}>
    <header style={{ padding: 12, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", flexShrink: 0 }}>
      <span>Synthetic tracker preview · no persistence</span>
      <button className="btn-ghost" style={{ minHeight: 44 }} onClick={() => {
        if (owner) client.revoke(); else client.configure("fixture_session", true);
        setOwner(!owner);
      }}>{owner ? "Simulate guest" : "Return owner"}</button>
      {view.artifact && <button className="btn-ghost" style={{ minHeight: 44 }} disabled={view.busy} onClick={() => void client.setGraph(!view.artifact!.spec.show_daily_graph)}>{view.artifact.spec.show_daily_graph ? "Hide graph" : "Show graph"}</button>}
    </header>
    <div style={{ flex: 1, minHeight: 0, minWidth: 0 }}>
      {owner ? <ArtifactCanvas content={view.artifact ? { kind: "generated_ui", artifact: view.artifact } : null} onArtifactEdit={client.edit} onArtifactSpecEdit={client.editSpec} artifactBusy={view.busy} onDismiss={client.dismiss} /> : <p role="status" style={{ padding: 24 }}>Private tracker removed. Owner return requires a fresh load.</p>}
    </div>
  </main>;
}
