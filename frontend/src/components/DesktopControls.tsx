"use client";
import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { auth } from "../services/firebase";
import { isDesktopStop, type DesktopHandle, type DesktopNotice } from "../services/desktopCommands";

const LOCAL = "http://127.0.0.1:8765";
type Action = { operation: "list_files" } | { operation: "read_text"; name: string }
  | { operation: "create_text"; name: string; text: string }
  | { operation: "open_app"; app: "notepad" | "explorer" };

/** Pairing secrets and file contents stay in memory and clear on privacy lock. */
type Props = { sessionId: string | null; allowed: boolean;
  onCommandStart?: (id: string) => void; onCommandResult?: (notice: DesktopNotice) => void; onDisconnect?: () => void };
const DesktopControls = forwardRef<DesktopHandle, Props>(function DesktopControls({ sessionId, allowed, onCommandStart, onCommandResult, onDisconnect }, ref) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [name, setName] = useState("note.txt");
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [command, setCommand] = useState("");
  const lastFile = useRef<string | null>(null);
  const callbacks = useRef({ onCommandStart, onCommandResult, onDisconnect });
  callbacks.current = { onCommandStart, onCommandResult, onDisconnect };
  const device = useRef("");
  const pairedSession = useRef<string | null>(null);
  const resultSession = useRef<string | null>(null);
  const epoch = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const access = useRef({ allowed, sessionId });
  access.current = { allowed, sessionId };

  function disconnect() {
    const hadActivity = !!device.current || !!pending.current;
    epoch.current++;
    pending.current?.abort(); pending.current = null;
    const secret = device.current;
    device.current = "";
    pairedSession.current = null; resultSession.current = null;
    lastFile.current = null;
    if (secret) void fetch(`${LOCAL}/stop`, { method: "POST", headers: { "X-Rumi-Device": secret }, keepalive: true }).catch(() => {});
    setCode(""); setWorkspace(""); setName("note.txt"); setText(""); setCommand(""); setResult(""); setBusy(false);
    if (hadActivity) callbacks.current.onDisconnect?.();
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

  function submit(input: string) {
    setOpen(true);
    if (isDesktopStop(input)) {
      disconnect();
      resultSession.current = access.current.sessionId;
      setResult("Disconnected and requested Stop. An action already running may have completed. Restart the local app to reconnect.");
      return;
    }
    if (!access.current.allowed) return;
    resultSession.current = access.current.sessionId;
    if (pending.current) { setResult("A computer action is already running. Say Stop to disconnect; nothing else has been queued."); return; }
    if (!device.current || pairedSession.current !== access.current.sessionId) { setResult("Connect your computer first, then repeat the request."); return; }
    void call(false, undefined, input);
  }
  useImperativeHandle(ref, () => ({ submit, stop: disconnect }));

  async function call(pair: boolean, action?: Action, commandText?: string) {
    if (pending.current || !access.current.allowed || !access.current.sessionId) return;
    if (!pair && (!device.current || pairedSession.current !== access.current.sessionId)) return;
    const generation = epoch.current;
    const requestId = crypto.randomUUID();
    const requestSession = access.current.sessionId;
    const expiresAt = Math.floor(Date.now() / 1000) + 90;
    resultSession.current = access.current.sessionId;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setResult("");
    if (commandText !== undefined) callbacks.current.onCommandStart?.(requestId);
    const deadline = setTimeout(() => controller.abort(), 20000);
    try {
      const user = auth.currentUser;
      if (!user) { disconnect(); return; }
      const token = await user.getIdToken();
      if (generation !== epoch.current || !access.current.allowed) return;
      const response = await fetch(`${LOCAL}/${pair ? "pair" : commandText !== undefined ? "command" : "execute"}`, {
        method: "POST", signal: controller.signal, cache: "no-store",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "X-Rumi-Device": device.current },
        body: JSON.stringify(pair ? { code, session_id: requestSession }
          : { request_id: requestId, session_id: requestSession, expires_at: expiresAt,
              ...(commandText !== undefined ? { text: commandText, last_file: lastFile.current } : { action }) }),
      });
      if (generation !== epoch.current || !access.current.allowed) return;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          disconnect();
          resultSession.current = access.current.sessionId;
          setResult("Pairing or owner verification failed. Restart the local app and reconnect after verifying your presence. Check the folder before retrying a save.");
          return;
        }
        throw new Error();
      }
      const data = await response.json();
      if (generation !== epoch.current || !access.current.allowed) return;
      if (pair) {
        if (typeof data.device_secret !== "string" || data.device_secret.length < 32 || typeof data.workspace !== "string") throw new Error();
        device.current = data.device_secret; pairedSession.current = access.current.sessionId;
        setWorkspace(data.workspace); setCode("");
        setResult("Computer connected. Actions are limited to this folder and the apps below.");
      } else {
        if (data.request_id !== requestId) throw new Error();
        const operation = commandText !== undefined ? data.operation : action?.operation;
        if (data.state === "succeeded" && !data.replayed && (operation === "create_text" || operation === "read_text")) {
          const filename = commandText !== undefined ? data.file : action && "name" in action ? action.name : null;
          if (typeof filename === "string") lastFile.current = filename;
        }
        if (data.state === "clarification") setResult(typeof data.message === "string" ? data.message : "Please give a filename and the exact text to save.");
        else if (data.state === "uncertain") setResult("The action may have completed. Check the folder before trying again.");
        else if (data.state === "dispatched") setResult("The app launch was requested. Check that its window opened.");
        else if (data.state !== "succeeded") setResult("The action could not be completed. Existing files are never overwritten.");
        else if (operation === "read_text") setResult(typeof data.result?.text === "string" ? data.result.text : "This request already completed. Read the file again to retrieve its contents.");
        else if (operation === "list_files") setResult(Array.isArray(data.result?.names)
          ? (data.result.names.filter((n: unknown) => typeof n === "string").join("\n") || "No supported text files in this folder.") + (data.result.truncated ? "\nOnly the first 500 folder entries were checked." : "")
          : "This request already completed. List the files again to refresh the results.");
        else if (operation === "create_text") setResult("File created and its contents verified.");
        else setResult("The request returned without window verification. Check the app before continuing.");
        if (commandText !== undefined && ["succeeded", "dispatched", "uncertain", "failed", "clarification"].includes(data.state)) {
          callbacks.current.onCommandResult?.({ request_id: requestId, session_id: requestSession, expires_at: expiresAt,
            state: data.replayed && (operation === "read_text" || operation === "list_files") ? "clarification" : data.state,
            ...(["list_files", "read_text", "create_text", "open_app"].includes(operation) ? { operation } : {}) });
        }
      }
    } catch {
      if (generation === epoch.current) {
        setResult("Could not complete the request. Check the local app and owner verification. If you were saving a file, check the folder before retrying.");
        if (commandText !== undefined) callbacks.current.onCommandResult?.({ request_id: requestId, session_id: requestSession, expires_at: expiresAt, state: "uncertain" });
      }
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
        <form onSubmit={e => { e.preventDefault(); const input = command.trim(); if (input) { setCommand(""); submit(input); } }}>
          <label>Computer request<input aria-label="Computer request" value={command} onChange={e => setCommand(e.target.value)} maxLength={18000} placeholder="Open Notepad, or read notes.txt" /></label>
          <button className="btn-ghost min-h-11" disabled={!command.trim() || (busy && !isDesktopStop(command))}>Send request</button>
        </form>
        <p>You can also type in Rumi or use the microphone. For a file: create notes.txt with content: your exact text</p>
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
});
export default DesktopControls;
