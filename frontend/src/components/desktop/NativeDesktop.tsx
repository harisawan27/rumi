"use client";
import React, { useEffect, useRef, useState } from "react";
import { Icon } from "./DesktopPreview";
import RumiCompanion from "./RumiCompanion";
import RumiExpressions from "./RumiExpressions";
import TaskSheet from "./TaskSheet";
import { actionExpression, companionMood, type CompanionMood } from "@/services/companion";
import { localReply, receiptText, textPages, type LocalGrant, type LocalVoiceState, type NativeDesktopApi, type VoiceEvent, type WindowsTask } from "@/services/nativeDesktop";
import s from "./native.module.css";

const disconnected: LocalGrant = { active: false };
const quiet: LocalVoiceState = { active: false, message: "Microphone off" };
type Draft = { text: string; until: number };

export default function NativeDesktop() {
  const [available, setAvailable] = useState(false);
  const [grant, setGrant] = useState<LocalGrant>(disconnected);
  const [voice, setVoice] = useState<LocalVoiceState>(quiet);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [wake, setWake] = useState({ enabled: false, armed: false });
  const [wakeBusy, setWakeBusy] = useState(false);
  const [petEnabled, setPetEnabled] = useState(false);
  const [wakeRequest, setWakeRequest] = useState<Draft | null>(null);
  const [text, setText] = useState("");
  const [heard, setHeard] = useState("");
  const [result, setResult] = useState("");
  const [task, setTask] = useState<WindowsTask>();
  const [workflowName, setWorkflowName] = useState("");
  const [state, setState] = useState("ready");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("companion");
  const [typing, setTyping] = useState(false);
  const [motion, setMotion] = useState<"system" | "full" | "reduced">("system");
  const reduced = motion === "reduced";
  const [spoken, setSpoken] = useState(true);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [page, setPage] = useState(0);
  const [dimensions, setDimensions] = useState({ columns: 42, rows: 7 });
  const [action, setAction] = useState<CompanionMood>("thinking");
  const [cue, setCue] = useState<{ mood: CompanionMood; id: number } | null>(null);
  const [expressions, setExpressions] = useState(false);
  const expressionsOpen = useRef(false); expressionsOpen.current = expressions;
  const cueId = useRef(0);
  const api = useRef<NativeDesktopApi | null>(null);
  const epoch = useRef(0), voiceEpoch = useRef(0), lastEvent = useRef(0);
  const pending = useRef(false), choosing = useRef(false), hadGrant = useRef(false);
  const input = useRef<HTMLInputElement>(null), output = useRef<HTMLDivElement>(null);
  const live = useRef({ grant, voice, spoken, draft });
  live.current = { grant, voice, spoken, draft };
  const onVoice = useRef<(event: VoiceEvent) => void>(() => {});

  function react(mood: CompanionMood) { setCue({ mood, id: ++cueId.current }); }
  useEffect(() => {
    if (!cue || voice.speaking) return;
    const timer = setTimeout(() => setCue(null), 2600);
    return () => clearTimeout(timer);
  }, [cue, voice.speaking]);

  function updateWake(next: LocalGrant) {
    const enabled = !!next.wake_enabled, armed = !!next.wake_armed;
    setWake(current => current.enabled === enabled && current.armed === armed ? current : { enabled, armed });
  }
  function clear(keepVoice = false, keepWakeRequest = false) {
    epoch.current++;
    pending.current = hadGrant.current = false;
    live.current = { ...live.current, grant: disconnected, draft: null };
    if (!keepVoice) {
      voiceEpoch.current++;
      live.current.voice = quiet;
      setVoice(quiet); setVoiceBusy(false);
    }
    if (!keepWakeRequest) setWakeRequest(null);
    setGrant(disconnected); setDraft(null);
    setCue(null); setAction("thinking");
    setResult(""); setTask(undefined); setWorkflowName(""); setText(""); setHeard(""); setBusy(false); setPage(0); setView("companion");
  }
  function stop() {
    clear(); setState("stopped");
    setWake(current => current.armed ? { ...current, armed: false } : current);
    const generation = epoch.current;
    void api.current?.stop().catch(() => { if (generation === epoch.current) setState("stop-unconfirmed"); });
  }
  async function pauseVoice() {
    const generation = ++voiceEpoch.current;
    live.current.voice = quiet; live.current.draft = null;
    setVoice(quiet); setVoiceBusy(false); setDraft(null); setHeard(""); setWakeRequest(null);
    try {
      await api.current?.voice_stop?.();
      if (generation === voiceEpoch.current) setWake(prev => ({ ...prev, armed: false }));
      return generation === voiceEpoch.current;
    } catch {
      if (generation === voiceEpoch.current) setVoice({ active: false, message: "Microphone stop was not confirmed. Close Rumi to end capture." });
      return false;
    }
  }
  function announce(words: string) {
    const current = live.current;
    if (!current.spoken || !current.voice.active || current.voice.voice_id === undefined || !current.grant.session_id) return;
    void api.current?.voice_speak?.({ session_id: current.grant.session_id, voice_id: current.voice.voice_id, text: words.slice(0, 780) }).catch(() => {});
  }
  function showResult(value: string, nextState: string, sheet?: WindowsTask, name = "") { setResult(value); setTask(sheet); setWorkflowName(name); setState(nextState); setPage(0); setView("workspace"); }

  useEffect(() => {
    let gone = false, checking = false;
    async function check() {
      if (gone || checking || choosing.current || !api.current) return;
      checking = true;
      const generation = epoch.current;
      try {
        const next = await api.current.status();
        if (gone || generation !== epoch.current) return;
        updateWake(next);
        setPetEnabled(!!next.pet_enabled);
        if (!next.active && hadGrant.current) { clear(!!next.wake_armed); setState("permission-ended"); }
        else if (next.active && hadGrant.current) { live.current.grant = next; setGrant(next); }
        else if (!next.active) { return; }
        else { void api.current.stop().catch(() => {}); }
      } catch {
        if (!gone && generation === epoch.current) { clear(); setState("disconnected"); void api.current?.stop().catch(() => {}); }
      } finally { checking = false; }
    }
    function ready() { if (gone) return; api.current = window.pywebview?.api || null; setAvailable(!!api.current); void check(); }
    function key(e: KeyboardEvent) {
      if (expressionsOpen.current && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); return; }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setTyping(true); requestAnimationFrame(() => input.current?.focus({ preventScroll: true })); }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === "Period" || e.key === ">")) { e.preventDefault(); stop(); }
      if (e.key === "Escape") { stop(); }
    }
    function hide() {
      if (!document.hidden || !api.current) return;
      const suspend = api.current.suspend_actions;
      if (!suspend) { stop(); return; }
      const revoke = hadGrant.current || choosing.current;
      clear(true);
      setState("ready");
      if (revoke) void suspend().catch(() => stop());
    }
    ready();
    window.addEventListener("pywebviewready", ready); window.addEventListener("keydown", key); document.addEventListener("visibilitychange", hide);
    const timer = setInterval(check, 2000);
    return () => { gone = true; epoch.current++; voiceEpoch.current++; clearInterval(timer); window.removeEventListener("pywebviewready", ready); window.removeEventListener("keydown", key); document.removeEventListener("visibilitychange", hide); void api.current?.stop().catch(() => {}); };
  }, []);

  useEffect(() => {
    if ((!voice.active && !wake.armed) || !api.current?.voice_poll) return;
    let gone = false, checking = false;
    const generation = voiceEpoch.current;
    const timer = setInterval(async () => {
      if (checking || gone || document.hidden) return;
      checking = true;
      try {
        const next = await api.current!.voice_poll!();
        if (gone || generation !== voiceEpoch.current) return;
        const wasActive = live.current.voice.active;
        live.current.voice = next; setVoice(next);
        if (!next.active && wasActive) { setDraft(null); live.current.draft = null; setHeard(""); setWakeRequest(null); }
        for (const event of next.active ? next.events || [] : []) {
          if (event.id > lastEvent.current) { lastEvent.current = event.id; onVoice.current(event); }
        }
      } catch { if (!gone && generation === voiceEpoch.current) pauseVoice(); }
      finally { checking = false; }
    }, voice.active ? 250 : 700);
    return () => { gone = true; clearInterval(timer); };
  }, [voice.active, wake.armed]);

  useEffect(() => {
    if (!wakeRequest) return;
    const expiry = setTimeout(() => {
      setWakeRequest(null);
      void api.current?.pet_attention?.("clear").catch(() => {});
      setState(value => value === "wake_review" ? "wake_expired" : value);
    }, Math.max(0, wakeRequest.until - Date.now()));
    return () => clearTimeout(expiry);
  }, [wakeRequest]);

  useEffect(() => {
    if (!draft) return;
    const timer = setTimeout(() => { live.current.draft = null; setDraft(null); setHeard(""); void api.current?.pet_attention?.("clear").catch(() => {}); showResult("The confirmation expired. Nothing was created. Please ask again.", "clarification"); }, Math.max(0, draft.until - Date.now()));
    return () => clearTimeout(timer);
  }, [draft]);

  useEffect(() => {
    if (!output.current || typeof ResizeObserver === "undefined") return;
    const element = output.current;
    const observer = new ResizeObserver(() => {
      const style = getComputedStyle(element);
      const size = parseFloat(style.fontSize) || 14, line = parseFloat(style.lineHeight) || 24;
      const columns = Math.max(12, Math.floor((element.clientWidth - 4) / (size * .64)));
      const visibleRows = Math.floor((element.clientHeight - 4) / line);
      const spokenRows = Math.floor(700 / (columns + 1));
      setDimensions({ columns, rows: Math.max(1, Math.min(visibleRows, spokenRows)) });
    });
    observer.observe(element); return () => observer.disconnect();
  }, [view, task]);

  async function choose() {
    if (!api.current || choosing.current || pending.current) return;
    clear(wake.armed, true); choosing.current = true; setBusy(true); setState("choosing");
    const generation = epoch.current;
    try {
      const next = await api.current.choose_workspace();
      if (generation !== epoch.current) return;
      hadGrant.current = next.active; live.current.grant = next;
      setGrant(next); setState(next.active ? "ready" : "not-enabled");
      if (next.active) react("greeting");
      if (next.message) showResult(next.message, "not-enabled");
      else if (wakeRequest && wakeRequest.until > Date.now()) showResult("", "wake_review");
    } catch { if (generation === epoch.current) setState("disconnected"); }
    finally { choosing.current = false; if (generation === epoch.current) setBusy(false); }
  }
  async function enableVoice() {
    if (!api.current?.voice_start || (!live.current.grant.active && !wake.enabled) || voiceBusy) return;
    if (live.current.voice.active) { pauseVoice(); return; }
    const generation = ++voiceEpoch.current;
    setVoiceBusy(true);
    try {
      const next = await api.current.voice_start();
      if (generation !== voiceEpoch.current) return;
      lastEvent.current = 0; live.current.voice = next; setVoice(next);
      setCue(null);
      if (!next.active) react("confused");
      for (const event of next.active ? next.events || [] : []) { lastEvent.current = event.id; onVoice.current(event); }
    } catch { if (generation === voiceEpoch.current) setVoice({ active: false, message: "Local voice is unavailable. You can still type a command." }); }
    finally { if (generation === voiceEpoch.current) setVoiceBusy(false); }
  }

  async function toggleWake() {
    if (!api.current?.wake_set || wakeBusy || choosing.current || pending.current) return;
    const generation = epoch.current;
    setWakeBusy(true);
    try {
      const next = await api.current.wake_set(!wake.enabled);
      if (generation !== epoch.current) return;
      updateWake(next);
      setHeard(next.message || (next.wake_enabled ? 'Background wake is enabled. Say “Hey Rumi”.' : "Background wake is off."));
      if (!next.wake_enabled) setWakeRequest(null);
    } catch {
      if (generation === epoch.current) setHeard("Could not change background wake.");
    } finally { setWakeBusy(false); }
  }

  async function enableWindowsControl() {
    if (!api.current?.enable_windows_control || choosing.current || pending.current) return;
    if (live.current.grant.windows_control) {
      const message = 'Windows control is ready. Say “Rumi list windows”.';
      setHeard(message); announce(message);
      return;
    }
    const generation = ++epoch.current;
    choosing.current = true;
    setBusy(true); setState("choosing");
    try {
      const next = await api.current.enable_windows_control();
      if (generation !== epoch.current) return;
      hadGrant.current = next.active;
      live.current.grant = next;
      setGrant(next); setState("ready");
      if (next.active && wakeRequest && wakeRequest.until > Date.now()) showResult("", "wake_review");
      const message = next.message || (next.windows_control ? 'Windows control is ready. Turn on voice, then say “Rumi list windows”.' : 'Windows control remains off.');
      setHeard(message);
      if (live.current.voice.active) announce(next.windows_control ? "Windows control is ready. Say Rumi list windows." : message);
    } catch {
      if (generation === epoch.current) { setState("ready"); setHeard("Windows control could not be enabled."); }
    } finally {
      choosing.current = false;
      if (generation === epoch.current) setBusy(false);
    }
  }

  async function submit(value: string, fromVoice = false, confirmed = false) {
    if (/^(?:(?:hey\s+)?rumi[,!]?\s+)?(?:stop|cancel)[.!]?$/i.test(value.trim())) { stop(); return; }
    if (/^(?:(?:hey\s+)?rumi[,.:!]?\s+)?confirm workflow save[.!?]?$/i.test(value.trim()) && state !== "workflow_review") {
      setHeard("Ask me to prepare a note before confirming its save.");
      return;
    }
    if (/^(?:rumi[,!]?\s+)?enable windows control[.!]?$/i.test(value.trim())) { await enableWindowsControl(); return; }
    const current = live.current.grant;
    if (!api.current || !current.active || !current.session_id || pending.current || choosing.current || !value.trim()) return;
    setWakeRequest(null);
    const reply = localReply(value);
    if (reply) { react("greeting"); showResult(reply, "reply"); announce(reply); return; }
    const startsResume = /^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:create|make|write|draft)\s+(?:(?:a|my)\s+)?(?:r[eé]sum[eé](?=\s|$)|(?:new\s+)?folder\b.*\band\b.*\br[eé]sum[eé](?=\s|$))/i.test(value.trim().replace(/[.!?]+$/, ""));
    if (fromVoice && !confirmed && !startsResume && /^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:create|make|save|write)\b/i.test(value)) {
      const next = { text: value, until: Date.now() + 30000 };
      void api.current?.pet_attention?.("draft").catch(() => {});
      live.current.draft = next; setDraft(next); setResult(""); setTask(undefined); setWorkflowName(""); setPage(0); setView("workspace"); setState("confirming");
      announce("I've prepared your words. Review the request on screen. Say Rumi confirm to create the file, or Rumi cancel to stop.");
      return;
    }
    live.current.draft = null; setDraft(null);
    setCue(null); setAction(actionExpression(value));
    const generation = epoch.current, requestId = crypto.randomUUID();
    pending.current = true; setBusy(true); setState("working"); setResult(""); setTask(undefined); setWorkflowName(""); setText(""); setView("workspace"); setPage(0);
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
      react(["plan", "workflow_review", "resume_review", "resume_share"].includes(receipt.state) ? "confirming" : receipt.state === "succeeded" ? "success" : receipt.state === "dispatched" || receipt.state === "resume_details" ? "acknowledging" : ["clarification", "task_choice"].includes(receipt.state) ? "confused" : "error");
      const note = receipt.operation === "note_workflow" ? receipt.result : undefined;
      const resume = receipt.operation === "resume_workflow" ? receipt.result : undefined;
      if (resume && receipt.state === "succeeded") setGrant(value => ({ ...value, recent_resume: true }));
      const resumeText = resume?.path && receipt.state !== "succeeded" ? `${resume.path}\n\n${resume.text || content}` : resume?.text;
      showResult(resumeText || note?.text || content, receipt.state, receipt.result?.task, resume ? "Résumé" : note?.name);
      if (resume) setHeard(content);
      const more = content.length > 700 ? " Say Rumi read result page for more." : "";
      announce(receipt.operation === "read_text" ? `Here's your note. ${content.slice(0, 600)}${content.length > 600 ? " The rest is in your workspace." : ""}` : content.slice(0, 700) + more);
    } catch { if (generation === epoch.current) { clear(); setState("uncertain"); void api.current?.stop().catch(() => {}); } }
    finally { clearTimeout(timer); if (generation === epoch.current) { pending.current = false; setBusy(false); } }
  }

  function useHeardRequest() {
    if (wakeRequest && Date.now() < wakeRequest.until && live.current.grant.active) void submit(wakeRequest.text, true);
  }

  onVoice.current = event => {
    if (event.kind === "wake") { react("acknowledging"); setHeard("I hear you."); return; }
    if (event.kind === "wake_request") {
      if (/^pause microphone[.!?]?$/i.test(event.text.trim())) { void pauseVoice(); return; }
      const next = { text: event.text, until: Date.now() + 90000 };
      void api.current?.pet_attention?.(live.current.grant.active ? "heard" : "workspace").catch(() => {});
      setWakeRequest(next); react("acknowledging"); setHeard("I heard your request. Choose a workspace to continue.");
      showResult("", "wake_review"); return;
    }
    if (event.kind === "interrupted") { setCue(null); setHeard("I'm listening. Give me a moment, then speak."); return; }
    if (event.kind === "unclear") { react("confused"); setHeard(event.text); return; }
    setHeard(event.text);
    if (pending.current) { setHeard("I'm finishing the current action. Please ask again when it's done."); return; }
    const navigation = event.text.trim().replace(/[.!?]+$/, "").toLowerCase();
    if (navigation === "use heard request") { useHeardRequest(); return; }
    if (navigation === "pause microphone") { void pauseVoice(); return; }
    if (navigation === "read result page") { announce(task ? result : `Page ${currentPage + 1} of ${pages.length}. ${pages[currentPage]}`); return; }
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
    ready: "What shall we do?",
    choosing: "Waiting for your permission.", "not-enabled": "Local access is off.", working: "Working on your device.",
    stopped: "Local permission cleared. An action already committed may have completed; inspect it before retrying.",
    "stop-unconfirmed": "Stop was not confirmed. Close Rumi to end local access, and check the last action.",
    "permission-ended": "Local permission ended. Your private results were cleared.", disconnected: "The native connection is unavailable. Close and reopen Rumi.",
    uncertain: "The action may have completed. Check the folder or app before trying again. Local permission was cleared.",
    plan: "Ready for your approval", task_choice: "Choose a control", operator_uncertain: "Check the window before trying again.",
    workflow_review: "Review the note before saving",
    resume_details: "Add your résumé details",
    resume_review: "Review your résumé before saving",
    resume_share: "Review the text to send to Gemini",
    wake_review: "I heard your request",
    wake_expired: "Say Hey Rumi to ask again.",
    blocked: "The action was blocked. Re-enable local permission and check the folder before retrying.",
    dispatched: "Launch requested", succeeded: "Verified local result", failed: "Let's try another way.", clarification: "A little more detail.", confirming: "Your words. Your say.", reply: "One thing at a time. Together.",
  };
  const mood = companionMood({ state, busy, action, voiceBusy, speaking: !!voice.speaking, listening: voice.active, draft: !!draft, cue: cue?.mood, typing: typing && !!text });
  const pages = textPages((state === "wake_review" ? wakeRequest?.text : undefined) || draft?.text || result || "Your next result will appear here. Ask Rumi to list your files, read a note or open an app.", dimensions.columns, dimensions.rows);
  const currentPage = Math.min(page, pages.length - 1);
  const workspace = view === "workspace";
  return <div className={s.shell} data-reduced={reduced} data-full-motion={motion === "full"} data-view={view}>
    <div className={s.stars} aria-hidden="true"/><div className={s.horizon} aria-hidden="true"/>
    <header className={s.header}>
      <div className={s.brand}><span className={s.mark}>r.</span><span>Rumi</span></div>
      <div className={s.connection}><i className={available ? s.online : s.offline}/><span>{available ? "On your device" : "Desktop preview"}</span></div>
      <div className={s.headerActions}>
        {api.current?.pet_set && <button className={`${s.iconButton} ${s.wakeButton}`} aria-label="Desktop pet" aria-pressed={petEnabled} title="Show Rumi over other apps" onClick={() => void api.current?.pet_set?.(!petEnabled).then(setPetEnabled).catch(() => {})}><Icon name="move" size={15}/><span>Desktop pet</span></button>}
        {api.current?.wake_set && <button className={`${s.iconButton} ${s.wakeButton}`} aria-label="Background wake" aria-pressed={wake.enabled} title="Listen for Hey Rumi while minimized" disabled={!available || busy || wakeBusy} onClick={() => void toggleWake()}><Icon name="mic" size={15}/><span>Background wake</span></button>}
        <button className={`${s.iconButton} ${s.windowsButton}`} aria-label={grant.windows_control ? "Windows control enabled" : "Enable Windows control"} aria-pressed={!!grant.windows_control} title={grant.windows_control ? "Windows control enabled" : "Enable Windows control"} disabled={!available || !api.current?.enable_windows_control || busy} onClick={() => void enableWindowsControl()}><Icon name="expand"/><span>Windows control</span></button>
        <button className={s.iconButton} aria-label="Meet Rumi" title="Meet Rumi · pauses microphone" disabled={busy} onClick={() => { void pauseVoice().then(paused => { if (paused) setExpressions(true); }); }}><Icon name="spark"/></button>
        <button className={s.iconButton} aria-label={`Character motion: ${motion}`} onClick={() => setMotion(value => value === "system" ? "full" : value === "full" ? "reduced" : "system")} title={`Character motion: ${motion}. Click for ${motion === "system" ? "full animation" : motion === "full" ? "less motion" : "system preference"}.`}><Icon name="activity"/></button>
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
        <div className={s.sceneTop}><span className={s.sceneMode}>{voice.speaking ? "Speaking" : busy ? "Working" : voice.active ? wake.armed ? "Ready for Hey Rumi" : "Listening" : "Microphone off"}</span></div>
        <div className={s.characterStage}>
          <RumiCompanion mood={mood} level={voice.level} reduced={reduced} fullMotion={motion === "full"} paused={expressions} reaction={cue?.id}/>
        </div>
        <div className={s.greeting}><h1>{workspace ? "Your workspace" : "What shall we do?"}</h1><p>{voice.active ? wake.armed ? 'Say “Hey Rumi” followed by your request.' : "Start with my name, then tell me what you need." : "Enable Windows control or choose a folder to begin."}</p></div>
        <div className={s.permission} aria-label="Local permission"><Icon name="folder" size={17}/><div><strong>{grant.workspace ? "Connected to your folder" : grant.windows_control ? "Windows control enabled" : "A workspace you choose"}</strong><span title={grant.workspace || ""}>{grant.workspace || (grant.windows_control ? 'Say “Rumi list windows”' : "Local files. Your permission.")}</span></div><button disabled={!available || busy} onClick={choose}>{grant.workspace ? "Change folder" : "Choose folder & enable"}</button></div>
        {grant.active && <span className={s.grantTime}>{Math.ceil((grant.seconds_remaining || 0) / 60)} min remaining · this Windows session</span>}
      </section>
      {workspace && <section className={s.workspace} aria-label="Local workspace">
        <div className={s.workspaceHeading}><h2>{task?.heading || (draft ? "Review before creating" : workflowName && state === "succeeded" ? (workflowName === "Résumé" ? "Résumé saved and verified" : "Note saved and verified") : messages[state] || "Ready for your next step.")}</h2><button className={s.iconButton} aria-label="Return to companion" onClick={() => setView("companion")}><Icon name="close"/></button></div>
        {task ? <TaskSheet task={task} state={state}/> : <>
        <div className={s.resultFrame}><div className={s.pageTop}><span>{workflowName || (draft ? "Pending request" : state === "working" ? "Local action in progress" : "Local result")}</span><span>{String(currentPage + 1).padStart(2,"0")} / {String(pages.length).padStart(2,"0")}</span></div><div className={s.textSurface} ref={output}><pre aria-label="Local result">{state === "working" ? "Working on your device…" : pages[currentPage]}</pre></div><div className={s.pagination}><button aria-label="Previous result page" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>← Previous</button><button aria-label="Next result page" disabled={currentPage === pages.length - 1} onClick={() => setPage(currentPage + 1)}>Next →</button></div></div>
        {state === "wake_review" && wakeRequest ? <div className={s.confirmation}>
          <p>{grant.active ? 'Say “Rumi, use heard request” to continue.' : "Choose a workspace to use this request."}</p>
          <button disabled={!grant.active || busy} onClick={useHeardRequest}>Use heard request</button>
          <button onClick={() => { setWakeRequest(null); setHeard(""); void api.current?.pet_attention?.("clear").catch(() => {}); showResult("", "ready"); }}>Discard</button>
        </div> : state === "succeeded" && workflowName === "Résumé" && grant.recent_resume ? <div className={s.confirmation}>
          <p>Say <strong>“Rumi, open it in Word”</strong> to continue there.</p>
          <button onClick={() => void submit("open it in Word")}>Open in Word</button>
        </div> : state === "resume_review" ? <div className={s.confirmation}>
          <p>Say <strong>“Rumi, confirm resume save”</strong> once you’ve reviewed it.</p>
          <button onClick={() => void submit("confirm resume save")}>Save Word file</button>
          {grant.resume_ai && <button onClick={() => void submit("polish resume with Gemini")}>Polish with Gemini</button>}
          <button onClick={() => void submit("cancel resume")}>Discard résumé</button>
        </div> : state === "resume_share" ? <div className={s.confirmation}>
          <p>Say <strong>“Rumi, confirm Gemini draft”</strong> to send the text shown here.</p>
          <button onClick={() => void submit("confirm Gemini draft")}>Send text to Gemini</button>
          <button onClick={() => void submit("cancel Gemini draft")}>Return to local draft</button>
        </div> : state === "resume_details" ? <div className={s.confirmation}>
          <p>Say <strong>“Rumi, resume folder named”</strong> to choose a different folder name.</p>
          <button onClick={() => { setTyping(true); requestAnimationFrame(() => input.current?.focus({ preventScroll: true })); }}>Type details</button>
          <button onClick={() => void submit("cancel resume")}>Discard résumé</button>
        </div> : state === "workflow_review" ? <div className={s.confirmation}>
          <p>Say <strong>“Rumi, confirm workflow save”</strong> within one minute.</p>
          <button onClick={() => void submit("confirm workflow save")}>Save note</button>
          <button onClick={() => void submit("cancel workflow")}>Discard note</button>
        </div> :
        draft ? <div className={s.confirmation}><p>Say <strong>“Rumi confirm”</strong> within 30 seconds. Check the filename and every word first.</p><button onClick={() => { const saved = live.current.draft; if (saved && Date.now() < saved.until) void submit(saved.text, true, true); }}>Confirm creation</button><button onClick={() => { live.current.draft = null; setDraft(null); void api.current?.pet_attention?.("clear").catch(() => {}); showResult("Nothing was created.", "clarification"); }}>Discard</button></div> : <div className={s.shortcuts}><button disabled={!grant.active || busy} onClick={() => void submit("Open Notepad")}><Icon name="expand" size={15}/>Open Notepad</button><button disabled={!grant.active || busy} onClick={() => void submit("List files")}><Icon name="folder" size={15}/>List text files</button><button disabled={!grant.active || busy} onClick={() => void submit("Read that file")}><Icon name="activity" size={15}/>Read that file</button></div>}
        </>}
      </section>}
      {!workspace && <aside className={s.whisper} aria-label="Example requests">
        <strong>Try a request</strong>
        <p>{grant.windows_control ? '“Rumi, find hello in this document.”' : '“Rumi, open Notepad.”'}</p>
        <p>{grant.windows_control ? '“Rumi, search for meeting notes.”' : '“Rumi, list my files.”'}</p>
        {grant.active && <div className={s.homeShortcuts}>
          <button disabled={busy} onClick={() => void submit("Open Notepad")} aria-label="Open Notepad">Open Notepad</button>
          <button disabled={!grant.workspace || busy} onClick={() => void submit("List files")} aria-label="List text files">List text files</button>
          <button disabled={!grant.workspace || busy} onClick={() => void submit("Read that file")} aria-label="Read that file">Read that file</button>
        </div>}
      </aside>}
    </main>
    <section className={s.conversation} aria-label="Conversation controls">
      <div className={s.liveLine} role="status">{!available ? "Open this workspace in Rumi Desktop." : heard || (state === "ready" ? voice.message || messages.ready : messages[state])}</div>
      <div className={s.dock}>
        <button className={s.typeToggle} aria-label="Type a command" aria-pressed={typing} onClick={() => { setTyping(v => !v); requestAnimationFrame(() => input.current?.focus({ preventScroll: true })); }}><span>⌨</span><small>Type</small></button>
        <button className={s.talkButton} disabled={!(grant.active || wake.enabled) || !api.current?.voice_start || voiceBusy || wakeBusy} onClick={() => void enableVoice()} aria-label={voice.active ? "Pause microphone" : "Enable local voice"} aria-pressed={voice.active}><Icon name={voice.active ? "stop" : "mic"} size={23}/><span>{voiceBusy ? "Waking up…" : voice.active ? "We're listening" : "Let's talk"}<small>{voice.active ? wake.armed ? '“Hey Rumi, stop” ends access and listening' : '“Rumi stop” ends access · “Rumi listen” interrupts speech' : "Enable your microphone · audio stays on this PC"}</small></span><span className={s.signal} aria-hidden="true">{[.4,.8,1,.6,.9].map((x,i) => <i key={i} style={{height: `${4 + (voice.active ? (voice.level || 0) * .24 * x : 3*x)}px`}}/>)}</span></button>
        <span className={s.localSeal}><i/>{voice.active ? "MIC ON" : "MIC OFF"}<small>{voice.language || "LOCAL ONLY"}</small></span>
      </div>
      <form className={`${s.command} ${typing ? s.commandOpen : ""}`} aria-label="Typed command" onSubmit={e => { e.preventDefault(); void submit(text); }}><input ref={input} aria-label="Local command" value={text} onChange={e => setText(e.target.value)} maxLength={18000} disabled={!grant.active} tabIndex={typing ? 0 : -1} placeholder="Type a request. Same Rumi, same local actions."/><button disabled={!grant.active || busy || !text.trim()} aria-label="Run local command" tabIndex={typing ? 0 : -1}><Icon name="arrow"/></button></form>
    </section>
    <footer className={s.footer}><span>Esc to stop</span><span>Ctrl+K to type</span></footer>
    {expressions && <RumiExpressions reduced={reduced} fullMotion={motion === "full"} onClose={() => setExpressions(false)} onStop={stop}/>}
  </div>;
}
