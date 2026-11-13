"use client";
import React, { useEffect, useRef, useState } from "react";
import { Icon } from "./DesktopPreview";
import RumiCompanion from "./RumiCompanion";
import { localReply, receiptText, textPages, type LocalGrant, type LocalVoiceState, type NativeDesktopApi, type VoiceEvent } from "@/services/nativeDesktop";
import s from "./native.module.css";

const disconnected: LocalGrant = { active: false };
const quiet: LocalVoiceState = { active: false, message: "Microphone off" };
type Draft = { text: string; until: number };

export default function NativeDesktop() {
  const [available, setAvailable] = useState(false);
  const [grant, setGrant] = useState<LocalGrant>(disconnected);
  const [voice, setVoice] = useState<LocalVoiceState>(quiet);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [text, setText] = useState("");
  const [heard, setHeard] = useState("");
  const [result, setResult] = useState("");
  const [state, setState] = useState("ready");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("companion");
  const [typing, setTyping] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [spoken, setSpoken] = useState(true);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [page, setPage] = useState(0);
  const [dimensions, setDimensions] = useState({ columns: 42, rows: 7 });
  const api = useRef<NativeDesktopApi | null>(null);
  const epoch = useRef(0), voiceEpoch = useRef(0), lastEvent = useRef(0);
  const pending = useRef(false), choosing = useRef(false), hadGrant = useRef(false);
  const input = useRef<HTMLInputElement>(null), output = useRef<HTMLDivElement>(null);
  const live = useRef({ grant, voice, spoken, draft });
  live.current = { grant, voice, spoken, draft };
  const onVoice = useRef<(event: VoiceEvent) => void>(() => {});

  function clear() {
    epoch.current++; voiceEpoch.current++;
    pending.current = hadGrant.current = false;
    live.current = { ...live.current, grant: disconnected, voice: quiet, draft: null };
    setGrant(disconnected); setVoice(quiet); setVoiceBusy(false); setDraft(null);
    setResult(""); setText(""); setHeard(""); setBusy(false); setPage(0); setView("companion");
  }
  function stop() {
    clear(); setState("stopped");
    const generation = epoch.current;
    void api.current?.stop().catch(() => { if (generation === epoch.current) setState("stop-unconfirmed"); });
  }
  function pauseVoice() {
    const generation = ++voiceEpoch.current;
    live.current.voice = quiet; live.current.draft = null;
    setVoice(quiet); setVoiceBusy(false); setDraft(null); setHeard("");
    void api.current?.voice_stop?.().catch(() => { if (generation === voiceEpoch.current) setVoice({ active: false, message: "Microphone stop was not confirmed. Close Rumi to end capture." }); });
  }
  function announce(words: string) {
    const current = live.current;
    if (!current.spoken || !current.voice.active || current.voice.voice_id === undefined || !current.grant.session_id) return;
    void api.current?.voice_speak?.({ session_id: current.grant.session_id, voice_id: current.voice.voice_id, text: words.slice(0, 780) }).catch(() => {});
  }
  function showResult(value: string, nextState: string) { setResult(value); setState(nextState); setPage(0); setView("workspace"); }

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
        else { void api.current.stop().catch(() => {}); }
      } catch {
        if (!gone && generation === epoch.current) { clear(); setState("disconnected"); void api.current?.stop().catch(() => {}); }
      } finally { checking = false; }
    }
    function ready() { if (gone) return; api.current = window.pywebview?.api || null; setAvailable(!!api.current); void check(); }
    function key(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setTyping(true); requestAnimationFrame(() => input.current?.focus({ preventScroll: true })); }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === "Period" || e.key === ">")) { e.preventDefault(); stop(); }
      if (e.key === "Escape") { stop(); }
    }
    function hide() { if (document.hidden) stop(); }
    ready();
    window.addEventListener("pywebviewready", ready); window.addEventListener("keydown", key); document.addEventListener("visibilitychange", hide);
    const timer = setInterval(check, 2000);
    return () => { gone = true; epoch.current++; voiceEpoch.current++; clearInterval(timer); window.removeEventListener("pywebviewready", ready); window.removeEventListener("keydown", key); document.removeEventListener("visibilitychange", hide); void api.current?.stop().catch(() => {}); };
  }, []);

  useEffect(() => {
    if (!voice.active || !api.current?.voice_poll) return;
    let gone = false, checking = false;
    const generation = voiceEpoch.current;
    const timer = setInterval(async () => {
      if (checking || gone) return;
      checking = true;
      try {
        const next = await api.current!.voice_poll!();
        if (gone || generation !== voiceEpoch.current) return;
        live.current.voice = next; setVoice(next);
        if (!next.active) { setDraft(null); live.current.draft = null; setHeard(""); }
        for (const event of next.active ? next.events || [] : []) {
          if (event.id > lastEvent.current) { lastEvent.current = event.id; onVoice.current(event); }
        }
      } catch { if (!gone && generation === voiceEpoch.current) pauseVoice(); }
      finally { checking = false; }
    }, 250);
    return () => { gone = true; clearInterval(timer); };
  }, [voice.active]);

  useEffect(() => {
    if (!draft) return;
    const timer = setTimeout(() => { live.current.draft = null; setDraft(null); setHeard(""); showResult("The confirmation expired. Nothing was created. Please ask again.", "clarification"); }, Math.max(0, draft.until - Date.now()));
    return () => clearTimeout(timer);
  }, [draft]);

  useEffect(() => {
    if (!output.current || typeof ResizeObserver === "undefined") return;
    const element = output.current;
    const observer = new ResizeObserver(() => {
      const style = getComputedStyle(element);
      const size = parseFloat(style.fontSize) || 14, line = parseFloat(style.lineHeight) || 24;
      setDimensions({ columns: Math.max(12, Math.floor((element.clientWidth - 4) / (size * .64))), rows: Math.max(1, Math.floor((element.clientHeight - 4) / line)) });
    });
    observer.observe(element); return () => observer.disconnect();
  }, [view]);

  async function choose() {
    if (!api.current || choosing.current || pending.current) return;
    clear(); choosing.current = true; setBusy(true); setState("choosing");
    const generation = epoch.current;
    try {
      const next = await api.current.choose_workspace();
      if (generation !== epoch.current) return;
      hadGrant.current = next.active; live.current.grant = next;
      setGrant(next); setState(next.active ? "ready" : "not-enabled");
      if (next.message) showResult(next.message, "not-enabled");
    } catch { if (generation === epoch.current) setState("disconnected"); }
    finally { choosing.current = false; if (generation === epoch.current) setBusy(false); }
  }
  async function enableVoice() {
    if (!api.current?.voice_start || !live.current.grant.active || voiceBusy) return;
    if (live.current.voice.active) { pauseVoice(); return; }
    const generation = ++voiceEpoch.current;
    setVoiceBusy(true);
    try {
      const next = await api.current.voice_start();
      if (generation !== voiceEpoch.current) return;
      lastEvent.current = 0; live.current.voice = next; setVoice(next);
      for (const event of next.active ? next.events || [] : []) { lastEvent.current = event.id; onVoice.current(event); }
    } catch { if (generation === voiceEpoch.current) setVoice({ active: false, message: "Local voice is unavailable. You can still type a command." }); }
    finally { if (generation === voiceEpoch.current) setVoiceBusy(false); }
  }

  async function submit(value: string, fromVoice = false, confirmed = false) {
    if (/^(?:(?:hey\s+)?rumi[,!]?\s+)?(?:stop|cancel)[.!]?$/i.test(value.trim())) { stop(); return; }
    const current = live.current.grant;
    if (!api.current || !current.active || !current.session_id || pending.current || choosing.current || !value.trim()) return;
    const reply = localReply(value);
    if (reply) { showResult(reply, "reply"); announce(reply); return; }
    if (fromVoice && !confirmed && /^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:create|make|save|write)\b/i.test(value)) {
      const next = { text: value, until: Date.now() + 30000 };
      live.current.draft = next; setDraft(next); setResult(""); setPage(0); setView("workspace"); setState("confirming");
      announce("I've prepared your words. Review the request on screen. Say Rumi confirm to create the file, or Rumi cancel to stop.");
      return;
    }
    live.current.draft = null; setDraft(null);
    const generation = epoch.current, requestId = crypto.randomUUID();
    pending.current = true; setBusy(true); setState("working"); setResult(""); setText(""); setView("workspace"); setPage(0);
    const timer = setTimeout(() => {
      if (generation !== epoch.current) return;
      clear(); setState("uncertain"); void api.current?.stop().catch(() => {});
    }, 20000);
    try {
      const receipt = await api.current.command({ request_id: requestId, session_id: current.session_id, expires_at: Math.floor(Date.now() / 1000) + 90, text: value.trim() });
      if (generation !== epoch.current) return;
      if (receipt.request_id !== requestId) throw new Error("Mismatched receipt");
      if (receipt.state === "blocked" || receipt.state === "uncertain") {
        clear(); setState(receipt.state); void api.current.stop().catch(() => {}); return;
      }
      const content = receiptText(receipt) || "This file is empty.";
      showResult(content, receipt.state);
      announce(receipt.operation === "read_text" ? `Here's your note. ${content.slice(0, 600)}${content.length > 600 ? " The rest is in your workspace." : ""}` : content.slice(0, 700));
    } catch { if (generation === epoch.current) { clear(); setState("uncertain"); void api.current?.stop().catch(() => {}); } }
    finally { clearTimeout(timer); if (generation === epoch.current) { pending.current = false; setBusy(false); } }
  }
  onVoice.current = event => {
    if (event.kind === "interrupted") { setHeard("I'm listening. Give me a moment, then speak."); return; }
    if (event.kind === "unclear") { setHeard(event.text); return; }
    setHeard(event.text);
    if (pending.current) { setHeard("I'm finishing the current action. Please ask again when it's done."); return; }
    const navigation = event.text.trim().replace(/[.!?]+$/, "").toLowerCase();
    if (navigation === "next page" || navigation === "previous page") {
      setView("workspace"); setPage(value => Math.max(0, Math.min(pages.length - 1, value + (navigation === "next page" ? 1 : -1)))); return;
    }
    if (navigation === "show workspace" || navigation === "show companion") {
      setView(navigation === "show workspace" ? "workspace" : "companion"); return;
    }
    if (/^confirm[.!]?$/i.test(event.text.trim())) {
      const saved = live.current.draft;
      if (saved && Date.now() < saved.until) void submit(saved.text, true, true);
      else setHeard("There is no pending file to confirm.");
      return;
    }
    if (live.current.draft && !/^(cancel|stop)[.!]?$/i.test(event.text.trim())) {
      setHeard("Confirm this file first, or say Rumi cancel. Nothing else was queued."); return;
    }
    void submit(event.text, true);
  };

  const messages: Record<string, string> = {
    ready: grant.active ? "I'm here. What shall we do?" : "A little presence. A world of possibility.",
    choosing: "Choose our workspace.", "not-enabled": "Your space, when you're ready.", working: "On it. Stay with me.",
    stopped: "Local permission cleared. An action already committed may have completed; inspect it before retrying.",
    "stop-unconfirmed": "Stop was not confirmed. Close Rumi to end local access, and check the last action.",
    "permission-ended": "Local permission ended. Your private results were cleared.", disconnected: "The native connection is unavailable. Close and reopen Rumi.",
    uncertain: "The action may have completed. Check the folder or app before trying again. Local permission was cleared.",
    blocked: "The action was blocked. Re-enable local permission and check the folder before retrying.",
    dispatched: "Launch requested", succeeded: "Verified local result", failed: "Let's try another way.", clarification: "A little more detail.", confirming: "Your words. Your say.", reply: "One thing at a time. Together.",
  };
  const mood = voice.speaking ? "speaking" : busy ? "working" : draft ? "curious" : voice.active ? "listening" : state === "succeeded" ? "pleased" : "resting";
  const pages = textPages(draft?.text || result || "Your next result will appear here. Ask Rumi to list your files, read a note or open an app.", dimensions.columns, dimensions.rows);
  const currentPage = Math.min(page, pages.length - 1);
  const workspace = view === "workspace";
  return <div className={s.shell} data-reduced={reduced} data-view={view}>
    <div className={s.stars} aria-hidden="true"/><div className={s.horizon} aria-hidden="true"/>
    <header className={s.header}>
      <div className={s.brand}><span className={s.mark}>r.</span><span>rumi<small>YOUR PERSONAL ORBIT</small></span></div>
      <div className={s.connection}><i className={available ? s.online : s.offline}/><span>{available ? "On your device" : "Preview · native app required"}</span><b> / </b><span>Cloud AI off</span></div>
      <div className={s.headerActions}>
        <button className={s.iconButton} aria-label="Reduce motion" aria-pressed={reduced} onClick={() => setReduced(v => !v)} title="Reduce motion"><Icon name="activity"/></button>
        <button className={s.iconButton} aria-label="Spoken replies" aria-pressed={spoken} onClick={() => { setSpoken(v => !v); if (voice.speaking) pauseVoice(); }} title="Spoken replies"><Icon name="mic"/></button>
        <button className={s.stopButton} onClick={stop} disabled={!available}><Icon name="stop" size={15}/>Stop & disconnect</button>
      </div>
    </header>
    <main className={s.stage}>
      <nav className={s.rail} aria-label="Companion views">
        <button aria-label="Companion" aria-pressed={!workspace} onClick={() => setView("companion")}><Icon name="spark"/><span>Presence</span></button>
        <button aria-label="Workspace" aria-pressed={workspace} onClick={() => setView("workspace")}><Icon name="expand"/><span>Workspace</span>{!!result && <i/>}</button>
      </nav>
      <section className={s.scene} aria-label="Rumi companion space">
        <div className={s.sceneTop}><span className={s.eyebrow}>A SPACE FOR YOU & ME</span><span className={s.sceneMode}>{mood}</span></div>
        <div className={s.characterStage}>
          <div className={s.coordinate} aria-hidden="true">R / 01<br/>PERSONAL COMPANION</div>
          <RumiCompanion mood={mood} level={voice.level}/>
          <div className={s.orbitNote}><i/><span>{voice.active ? voice.speaking ? "Speaking locally" : "Listening locally" : "Here when you need me"}</span></div>
        </div>
        <div className={s.greeting}><p className={s.eyebrow}>{voice.active ? "SAY MY NAME. I'M LISTENING." : "HELLO, HUMAN."}</p><h1>{workspace ? "Right here with you." : "Let's make space\nfor possibility."}</h1><p>{grant.active ? "Talk to me. Watch things happen." : "Choose a folder. Bring me into your day."}</p></div>
        <div className={s.permission} aria-label="Local permission"><Icon name="folder" size={17}/><div><strong>{grant.active ? "Connected to your folder" : "A workspace you choose"}</strong><span title={grant.workspace || ""}>{grant.active ? grant.workspace : "Local files. Your permission."}</span></div><button disabled={!available || busy} onClick={choose}>{grant.active ? "Change folder" : "Choose folder & enable"}</button></div>
        {grant.active && <span className={s.grantTime}>{Math.ceil((grant.seconds_remaining || 0) / 60)} min remaining · this Windows session</span>}
      </section>
      {workspace && <section className={s.workspace} aria-label="Local workspace">
        <div className={s.workspaceHeading}><div><span className={s.eyebrow}>{draft ? "REVIEW BEFORE CREATING" : "YOUR WORKSPACE"}</span><h2>{messages[state] || "Ready for your next step."}</h2></div><button className={s.iconButton} aria-label="Return to companion" onClick={() => setView("companion")}><Icon name="close"/></button></div>
        <div className={s.resultFrame}><div className={s.pageTop}><span>{draft ? "Pending request" : state === "working" ? "Local action in progress" : "Local result"}</span><span>{String(currentPage + 1).padStart(2,"0")} / {String(pages.length).padStart(2,"0")}</span></div><div className={s.textSurface} ref={output}><pre aria-label="Local result">{state === "working" ? "Working on your device…" : pages[currentPage]}</pre></div><div className={s.pagination}><button aria-label="Previous result page" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>← Previous</button><span>No scrolling. One page at a time.</span><button aria-label="Next result page" disabled={currentPage === pages.length - 1} onClick={() => setPage(currentPage + 1)}>Next →</button></div></div>
        {draft ? <div className={s.confirmation}><p>Say <strong>“Rumi confirm”</strong> within 30 seconds. Check the filename and every word first.</p><button onClick={() => { const saved = live.current.draft; if (saved && Date.now() < saved.until) void submit(saved.text, true, true); }}>Confirm creation</button><button onClick={() => { live.current.draft = null; setDraft(null); showResult("Nothing was created.", "clarification"); }}>Discard</button></div> : <div className={s.shortcuts}><button disabled={!grant.active || busy} onClick={() => void submit("Open Notepad")}><Icon name="expand" size={15}/>Open Notepad</button><button disabled={!grant.active || busy} onClick={() => void submit("List files")}><Icon name="folder" size={15}/>List text files</button><button disabled={!grant.active || busy} onClick={() => void submit("Read that file")}><Icon name="activity" size={15}/>Read that file</button></div>}
      </section>}
      {!workspace && <aside className={s.whisper}><span className={s.eyebrow}>SMALL BEGINNINGS</span><p>“Rumi, open Notepad.”</p><p>“Rumi, list my files.”</p><p>“Rumi, read that file.”</p><div className={s.homeShortcuts}><button disabled={!grant.active || busy} onClick={() => void submit("Open Notepad")} aria-label="Open Notepad">Open Notepad ↗</button><button disabled={!grant.active || busy} onClick={() => void submit("List files")} aria-label="List text files">List text files ↗</button><button disabled={!grant.active || busy} onClick={() => void submit("Read that file")} aria-label="Read that file">Read that file ↗</button></div><small>English voice · local Windows speech<br/>Your exact words. No model tokens.</small></aside>}
    </main>
    <section className={s.conversation} aria-label="Conversation controls">
      <div className={s.liveLine} role="status">{!available ? "Open this workspace in Rumi Desktop." : heard || (state === "ready" ? voice.message || messages.ready : messages[state])}</div>
      <div className={s.dock}>
        <button className={s.typeToggle} aria-label="Type a command" aria-pressed={typing} onClick={() => { setTyping(v => !v); requestAnimationFrame(() => input.current?.focus({ preventScroll: true })); }}><span>⌨</span><small>Type</small></button>
        <button className={s.talkButton} disabled={!grant.active || !api.current?.voice_start || voiceBusy} onClick={() => void enableVoice()} aria-label={voice.active ? "Pause microphone" : "Enable local voice"} aria-pressed={voice.active}><Icon name={voice.active ? "stop" : "mic"} size={23}/><span>{voiceBusy ? "Waking up…" : voice.active ? "We're listening" : "Let's talk"}<small>{voice.active ? '“Rumi stop” ends access · “Rumi listen” interrupts speech' : "Enable your microphone · audio stays on this PC"}</small></span><span className={s.signal} aria-hidden="true">{[.4,.8,1,.6,.9].map((x,i) => <i key={i} style={{height: `${4 + (voice.active ? (voice.level || 0) * .24 * x : 3*x)}px`}}/>)}</span></button>
        <span className={s.localSeal}><i/>{voice.active ? "MIC ON" : "MIC OFF"}<small>{voice.language || "LOCAL ONLY"}</small></span>
      </div>
      <form className={`${s.command} ${typing ? s.commandOpen : ""}`} aria-label="Typed command" onSubmit={e => { e.preventDefault(); void submit(text); }}><input ref={input} aria-label="Local command" value={text} onChange={e => setText(e.target.value)} maxLength={18000} disabled={!grant.active} tabIndex={typing ? 0 : -1} placeholder="Type a request. Same Rumi, same local actions."/><button disabled={!grant.active || busy || !text.trim()} aria-label="Run local command" tabIndex={typing ? 0 : -1}><Icon name="arrow"/></button></form>
    </section>
    <footer className={s.footer}><span><i/>VOICE FIRST. ALWAYS YOURS.</span><span>ESC / CTRL SHIFT . TO STOP <b>·</b> CTRL K TO TYPE</span><span>Notepad · Explorer · Text files</span></footer>
  </div>;
}
