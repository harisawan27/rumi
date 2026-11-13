"use client";
import React, { useEffect, useRef, useState } from "react";
import { Icon, Presence } from "./DesktopPreview";
import { receiptText, type LocalGrant, type NativeDesktopApi } from "@/services/nativeDesktop";
import s from "./desktop.module.css";
import n from "./native.module.css";

const disconnected: LocalGrant = { active: false };
export default function NativeDesktop() {
  const [available, setAvailable] = useState(false);
  const [grant, setGrant] = useState<LocalGrant>(disconnected);
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [state, setState] = useState("ready");
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState("dark");
  const api = useRef<NativeDesktopApi | null>(null);
  const epoch = useRef(0);
  const pending = useRef(false);
  const choosing = useRef(false);
  const hadGrant = useRef(false);
  const input = useRef<HTMLInputElement>(null);

  function clear() {
    epoch.current++;
    pending.current = false;
    hadGrant.current = false;
    setGrant(disconnected); setResult(""); setText(""); setBusy(false);
  }
  function stop() {
    clear(); setState("stopped");
    const generation = epoch.current;
    void api.current?.stop().catch(() => { if (generation === epoch.current) setState("stop-unconfirmed"); });
  }
  useEffect(() => {
    let gone = false, checking = false;
    async function check() {
      if (gone || checking || choosing.current || !api.current) return;
      checking = true;
      const generation = epoch.current;
      try {
        const next = await api.current.status();
        if (gone || generation !== epoch.current) return;
        if (!next.active) { const ended = hadGrant.current; clear(); if (ended) setState("permission-ended"); }
        else if (hadGrant.current) { setGrant(next); }
        else { void api.current.stop().catch(() => {}); } // Only native consent can enable this UI; polling cannot undo Stop.
      } catch {
        if (!gone && generation === epoch.current) { clear(); setState("disconnected"); }
      } finally { checking = false; }
    }
    function ready() { if (gone) return; api.current = window.pywebview?.api || null; setAvailable(!!api.current); void check(); }
    function key(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); input.current?.focus(); }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === "Period" || e.key === ">")) { e.preventDefault(); stop(); }
    }
    function hide() { if (document.hidden) stop(); }
    ready();
    window.addEventListener("pywebviewready", ready);
    window.addEventListener("keydown", key);
    document.addEventListener("visibilitychange", hide);
    const timer = setInterval(check, 2000);
    return () => { gone = true; epoch.current++; clearInterval(timer); window.removeEventListener("pywebviewready", ready); window.removeEventListener("keydown", key); document.removeEventListener("visibilitychange", hide); void api.current?.stop().catch(() => {}); };
  }, []);

  async function choose() {
    if (!api.current || choosing.current || pending.current) return;
    clear(); choosing.current = true; setBusy(true); setState("choosing");
    const generation = epoch.current;
    try {
      const next = await api.current.choose_workspace();
      if (generation !== epoch.current) return;
      hadGrant.current = next.active; setGrant(next); setState(next.active ? "ready" : "not-enabled");
      if (next.message) setResult(next.message);
    } catch { if (generation === epoch.current) setState("disconnected"); }
    finally { choosing.current = false; if (generation === epoch.current) setBusy(false); }
  }
  async function submit(value: string) {
    if (/^(stop|cancel)[.!]?$/i.test(value.trim())) { stop(); return; }
    if (!api.current || !grant.active || !grant.session_id || pending.current || choosing.current || !value.trim()) return;
    const generation = epoch.current, requestId = crypto.randomUUID();
    pending.current = true; setBusy(true); setState("working"); setResult(""); setText("");
    const timer = setTimeout(() => {
      if (generation !== epoch.current) return;
      clear(); setState("uncertain"); void api.current?.stop().catch(() => {});
    }, 20000);
    try {
      const receipt = await api.current.command({ request_id: requestId, session_id: grant.session_id, expires_at: Math.floor(Date.now() / 1000) + 90, text: value.trim() });
      if (generation !== epoch.current) return;
      if (receipt.request_id !== requestId) throw new Error("Mismatched receipt");
      if (receipt.state === "blocked" || receipt.state === "uncertain") {
        clear(); setState(receipt.state); void api.current.stop().catch(() => {}); return;
      }
      setResult(receiptText(receipt)); setState(receipt.state);
    } catch { if (generation === epoch.current) { clear(); setState("uncertain"); void api.current?.stop().catch(() => {}); } }
    finally { clearTimeout(timer); if (generation === epoch.current) { pending.current = false; setBusy(false); } }
  }
  const message: Record<string, string> = {
    ready: grant.active ? "Local permission is active. Your next command runs on this device." : "Choose a folder and enable local actions to get started.",
    choosing: "Choose a folder in the Windows dialog, then review the local permission request.",
    "not-enabled": "No local permission was granted. You can choose a folder when ready.",
    working: "Working locally. Stop is available at any time.",
    stopped: "Local permission cleared. An action already committed may have completed; inspect it before retrying.",
    "stop-unconfirmed": "The app did not confirm Stop. Close Rumi to end local access; check the last action before retrying.",
    "permission-ended": "Local permission ended. Private results were cleared. Choose a folder again to continue.",
    disconnected: "The native connection is unavailable. Close and reopen Rumi Desktop.",
    uncertain: "The action may have completed. Check the folder or app before trying again. Local permission was cleared.",
    blocked: "The action was blocked. Re-enable local permission and check the folder before retrying.",
    dispatched: "Launch requested", succeeded: "Verified local result", failed: "Action could not complete", clarification: "A little more detail needed",
  };
  return <div className={s.root} data-theme={theme}>
    <div className={n.shell}>
      <header className={n.header}><div className={s.brand}><span className={s.brandSymbol}>r.</span><span>rumi<span className={s.brandCaption}>YOUR LOCAL COMPANION</span></span></div><div className={n.headerActions}><span className={s.previewBadge}>LOCAL WINDOWS APP</span><button className={s.iconButton} aria-label="Toggle Rumi appearance" onClick={() => setTheme(t => t === "dark" ? "light" : "dark")}><Icon name="sun" /></button><button className={s.stopButton} onClick={stop} disabled={!available}><Icon name="stop" size={16} />Stop & disconnect</button></div></header>
      <main className={n.main}>
        <div className={s.connectionLine}><span><i className={s.statusDot} /> {available ? "Native connection ready" : "Native app required"}<b>·</b>Cloud AI off</span><span>Microphone off</span></div>
        <div className={s.hero}><div><span className={s.eyebrow}>SMALL COMMANDS. REAL RESULTS.</span><h1>Your computer.<br /><em>A little more possible.</em></h1><p>Open an app. Write a note. Find your next step.<br />Every supported command runs right here.</p></div><div className={s.heroPresence}><Presence active={state === "working"} /><span><i className={s.statusDot} />{state === "working" ? "Working on your device" : "Here when you need me"}</span></div></div>
        {!available && <section className={n.info}><h2>Open this workspace in Rumi Desktop.</h2><p>This browser page has no computer access. Launch the packaged Rumi Desktop app to choose a folder and run local commands.</p></section>}
        <section className={n.permission} aria-label="Local permission"><div><span className={s.eyebrow}>YOUR CHOSEN SPACE</span><h2>{grant.active ? "Connected to your folder" : "Start with a folder you choose."}</h2><p>{grant.active ? grant.workspace : "Read, list and create text files in one local folder. Existing files stay intact."}</p>{grant.active && <small>Permission remaining: {Math.ceil((grant.seconds_remaining || 0) / 60)} minutes · this Windows session</small>}</div><button className={s.primary} disabled={!available || busy} onClick={choose}>{grant.active ? "Change folder" : "Choose folder & enable"}<Icon name="folder" size={17} /></button></section>
        <form className={s.command} onSubmit={e => { e.preventDefault(); void submit(text); }}><span className={s.commandMark}><Icon name="spark" /></span><input ref={input} aria-label="Local command" value={text} onChange={e => setText(e.target.value)} maxLength={18000} disabled={!grant.active} placeholder={grant.active ? "Try: open Notepad, or read notes.txt" : "Enable local actions to enter a command"} /><button className={s.send} disabled={!grant.active || busy || !text.trim()} aria-label="Run local command"><Icon name="arrow" /></button></form>
        <div className={s.commandHint}><span><kbd>Ctrl K</kbd> command focus · <kbd>Ctrl Shift .</kbd> stop while this app is focused</span><span>No model tokens</span></div>
        <div className={n.shortcuts}>{[{label:"Open Notepad",icon:"expand",command:"Open Notepad"},{label:"List text files",icon:"folder",command:"List files"},{label:"Read that file",icon:"activity",command:"Read that file"}].map(item => <button key={item.label} className={s.secondary} disabled={!grant.active || busy} onClick={() => void submit(item.command)}><Icon name={item.icon as "expand" | "folder" | "activity"} size={17} />{item.label}</button>)}<button className={s.textButton} disabled={!grant.active || busy} onClick={() => { setText("Create first-note.txt with content: Hello from Rumi."); input.current?.focus(); }}>Prepare a first note <Icon name="arrow" size={16} /></button></div>
        <div className={n.columns}><section className={s.taskPanel} aria-labelledby="local-result-title"><div className={s.panelHeading}><span className={s.eyebrow}>IN FOCUS</span><span className={s.taskBadge}>{state === "working" ? "RUNNING" : "LOCAL"}</span></div><h2 id="local-result-title">{message[state] || "Ready for your next step."}</h2>{result && <pre className={n.result} aria-label="Local result">{result}</pre>}<p className={n.status} role="status">{state === "working" ? "Waiting for the local executor…" : result ? "Result returned by your local executor." : ""}</p></section><aside className={s.sidePanel}><span className={s.eyebrow}>CLEAR BOUNDARIES</span><h2>On your device.<br /><em>On your terms.</em></h2><p>Local permission belongs to this unlocked Windows session. It is separate from the website’s Google sign-in and face verification.</p><p>Supported now: Notepad, Explorer, and .txt, .md, .csv or .json files in the selected folder. Files are never overwritten.</p><p>Stop, detected screen lock, minimize or app exit ends permission. No action resumes automatically.</p><div className={s.assurance}><Icon name="check" size={16} /><span>No cloud AI or background audio</span></div></aside></div>
      </main><footer className={s.footer}><span><i className={s.statusDot} />Rumi Desktop · local control foundation</span><span>WINDOWS · OFFLINE COMMANDS</span></footer>
    </div>
  </div>;
}
