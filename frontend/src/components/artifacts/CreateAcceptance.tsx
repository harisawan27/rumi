"use client";
/** Development-only synthetic identity; separate loopback emulator server. */
import React, { useEffect, useState, useSyncExternalStore } from "react";
import ArtifactCanvas from "../ArtifactCanvas";
import { ArtifactClient } from "../../services/artifactClient";
import { CreateRequests } from "../../services/createRequests";

const BASE = "http://localhost:8005";
export default function CreateAcceptance() {
  const [gate] = useState(() => new CreateRequests());
  const [client] = useState(() => new ArtifactClient(async (path, body, signal) => {
    const response = await fetch(`${BASE}/artifacts/${path}`, { method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined, signal });
    if (!response.ok) throw new Error("The local test request failed. Reload and retry.");
    return response.json();
  }));
  const view = useSyncExternalStore(client.subscribe, client.snapshot, client.snapshot);
  const [text, setText] = useState("I need to track how much I study this week.");
  const [status, setStatus] = useState("Ready for local testing");
  const [history, setHistory] = useState<{ artifact_id: string; title: string }[]>([]);
  const refresh = async () => {
    const response = await fetch(`${BASE}/history`);
    if (!response.ok) throw new Error("Start the local acceptance server first.");
    setHistory((await response.json()).items);
  };
  useEffect(() => {
    client.configure("browser_acceptance_session", true);
    void refresh().catch(e => setStatus(e.message));
    return () => { gate.cancel(); client.revoke(); };
  }, [client, gate]);
  return <main style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "#04080f", color: "#e2e8f0" }}>
    <header style={{ padding: 12 }}>
      <p>Local CREATE acceptance · synthetic user · emulator storage · no Google sign-in</p>
      <form style={{ display: "flex", gap: 8 }} onSubmit={async e => {
        e.preventDefault();
        const request_id = gate.begin(view.artifact?.artifact_id ?? null);
        const started = performance.now();
        setStatus("Understanding request…");
        try {
          const response = await fetch(`${BASE}/plan`, { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, request_id, selected_id: view.artifact?.artifact_id ?? null }) });
          if (!response.ok) throw new Error("The test request failed. Please retry.");
          const data = await response.json();
          if (!gate.current(request_id)) return;
          const result = gate.result(data.result);
          if (result) {
            await client.loadIfCurrent(result.artifact_id, () => gate.current(request_id));
            await refresh();
          }
          if (gate.current(request_id)) setStatus(`${data.ack || `Route: ${data.mode} (voice/Markdown not simulated here)`} · ${(performance.now() - started).toFixed(0)} ms`);
        } catch (error) { if (gate.current(request_id)) setStatus(error instanceof Error ? error.message : "Test failed"); }
      }}>
        <input aria-label="Ask Rumi" value={text} onChange={e => setText(e.target.value)} style={{ flex: 1, minWidth: 0, color: "#e2e8f0", background: "#0b1824", padding: 8 }} />
        <button type="submit">Send</button>
      </form>
      <p role="status">{status}</p>
      <nav aria-label="Saved trackers">{history.map(item => <button key={item.artifact_id} onClick={() => { gate.cancel(); void client.load(item.artifact_id); }}>{item.title}</button>)}</nav>
    </header>
    <div style={{ flex: 1, minHeight: 0 }}>
      <ArtifactCanvas content={view.artifact ? { kind: "generated_ui", artifact: view.artifact } : null}
        onArtifactEdit={client.edit} onArtifactSpecEdit={client.editSpec} artifactBusy={view.busy}
        onDismiss={() => { gate.cancel(); client.dismiss(); }} />
    </div>
  </main>;
}
