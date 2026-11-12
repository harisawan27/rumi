"use client";
import React, { useEffect, useRef, useState } from "react";
import { auth } from "../services/firebase";

const LOCAL = "http://127.0.0.1:8765";
type Action = { operation: "list_files" } | { operation: "read_text"; name: string }
  | { operation: "create_text"; name: string; text: string }
  | { operation: "open_app"; app: "notepad" | "explorer" };

/** Pairing secrets and file contents stay in memory and clear on privacy lock. */
export default function DesktopControls({ sessionId, allowed }: { sessionId: string | null; allowed: boolean }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [name, setName] = useState("note.txt");
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const device = useRef("");
  const pairedSession = useRef<string | null>(null);
  const resultSession = useRef<string | null>(null);
  const epoch = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const access = useRef({ allowed, sessionId });
  access.current = { allowed, sessionId };

  function disconnect() {
    epoch.current++;
    pending.current?.abort(); pending.current = null;
    const secret = device.current;
    device.current = "";
    pairedSession.current = null; resultSession.current = null;
    if (secret) void fetch(`${LOCAL}/stop`, { method: "POST", headers: { "X-Rumi-Device": secret }, keepalive: true }).catch(() => {});
    setCode(""); setWorkspace(""); setName("note.txt"); setText(""); setResult(""); setBusy(false);
  }
  useEffect(() => {
    if (!allowed) disconnect();
  }, [allowed]);
  useEffect(() => { disconnect(); }, [sessionId]);
  useEffect(() => {
    const hide = () => { if (document.hidden) disconnect(); };
    document.addEventListener("visibilitychange", hide);
    return () => { document.removeEventListener("visibilitychange", hide); disconnect(); };
  }, []);

  async function call(pair: boolean, action?: Action) {
    if (pending.current || !access.current.allowed || !access.current.sessionId) return;
    if (!pair && (!device.current || pairedSession.current !== access.current.sessionId)) return;
    const generation = epoch.current;
    resultSession.current = access.current.sessionId;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setResult("");
    const deadline = setTimeout(() => controller.abort(), 20000);
    try {
      const user = auth.currentUser;
      if (!user) throw new Error();
      const token = await user.getIdToken();
      if (generation !== epoch.current || !access.current.allowed) return;
      const requestId = crypto.randomUUID();
      const response = await fetch(`${LOCAL}/${pair ? "pair" : "execute"}`, {
        method: "POST", signal: controller.signal, cache: "no-store",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "X-Rumi-Device": device.current },
        body: JSON.stringify(pair ? { code, session_id: access.current.sessionId }
          : { request_id: requestId, session_id: access.current.sessionId, expires_at: Math.floor(Date.now() / 1000) + 90, action }),
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (generation !== epoch.current || !access.current.allowed) return;
      if (pair) {
        if (typeof data.device_secret !== "string" || data.device_secret.length < 32 || typeof data.workspace !== "string") throw new Error();
        device.current = data.device_secret; pairedSession.current = access.current.sessionId;
        setWorkspace(data.workspace); setCode("");
        setResult("Computer connected. Actions are limited to this folder and the apps below.");
      } else {
        if (data.request_id !== requestId) throw new Error();
        if (data.state === "uncertain") setResult("The action may have completed. Check the folder before trying again.");
        else if (data.state === "dispatched") setResult("The app launch was requested. Check that its window opened.");
        else if (data.state !== "succeeded") setResult("The action could not be completed. Existing files are never overwritten.");
        else if (action?.operation === "read_text") setResult(typeof data.result?.text === "string" ? data.result.text : "This request already completed. Read the file again to retrieve its contents.");
        else if (action?.operation === "list_files") setResult(Array.isArray(data.result?.names)
          ? (data.result.names.filter((n: unknown) => typeof n === "string").join("\n") || "No supported text files in this folder.") + (data.result.truncated ? "\nOnly the first 500 folder entries were checked." : "")
          : "This request already completed. List the files again to refresh the results.");
        else if (action?.operation === "create_text") setResult("File created and its contents verified.");
        else setResult("The request returned without window verification. Check the app before continuing.");
      }
    } catch {
      if (generation === epoch.current) setResult("Could not complete the request. Check the local app and owner verification. If you were saving a file, check the folder before retrying.");
    } finally {
      clearTimeout(deadline);
      if (pending.current === controller) { pending.current = null; setBusy(false); }
    }
  }
  return <div>
    <button className="btn-ghost min-h-11" onClick={() => setOpen(!open)} aria-expanded={open}>Computer</button>
    {open && <section aria-label="Computer controls" className="rumi-card" style={{ position: "fixed", right: 12, top: 72, width: "min(440px, calc(100vw - 24px))", maxHeight: "80dvh", overflowY: "auto", zIndex: 60 }}>
      <h2>Connect your computer</h2>
      {!allowed ? <p>Start a session and verify your presence to use computer actions.</p> : !workspace || pairedSession.current !== sessionId ? <form onSubmit={e => { e.preventDefault(); void call(true); }}>
        <p>Start the Rumi local app with your chosen folder, then enter its pairing code.</p>
        <label>Pairing code<input aria-label="Pairing code" type="password" autoComplete="off" value={code} onChange={e => setCode(e.target.value)} /></label>
        <button className="btn-ghost min-h-11" disabled={busy || code.length < 20}>Connect</button>
      </form> : <>
        <p>Selected folder: {workspace}</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost min-h-11" disabled={busy} onClick={() => void call(false, { operation: "list_files" })}>List text files</button>
          <button className="btn-ghost min-h-11" disabled={busy} onClick={() => void call(false, { operation: "open_app", app: "notepad" })}>Open Notepad</button>
          <button className="btn-ghost min-h-11" disabled={busy} onClick={() => void call(false, { operation: "open_app", app: "explorer" })}>Open Explorer</button>
        </div>
        <label>Filename<input aria-label="Filename" value={name} onChange={e => setName(e.target.value)} maxLength={120} /></label>
        <label>Note<textarea aria-label="Note" value={text} onChange={e => setText(e.target.value)} maxLength={16000} /></label>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost min-h-11" disabled={busy} onClick={() => void call(false, { operation: "create_text", name, text })}>Create file</button>
          <button className="btn-ghost min-h-11" disabled={busy} onClick={() => void call(false, { operation: "read_text", name })}>Read file</button>
          <button className="btn-ghost min-h-11" onClick={disconnect}>Stop and disconnect</button>
        </div>
      </>}
      {busy && <p role="status">Working…</p>}
      {allowed && resultSession.current === sessionId && result && <pre role="status" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{result}</pre>}
      <button className="btn-ghost min-h-11" onClick={() => setOpen(false)}>Close</button>
    </section>}
  </div>;
}
