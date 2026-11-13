"use client";

import React, { useEffect, useId, useReducer, useRef, useState } from "react";
import { previewReducer, previewTask, WELCOME_SAMPLE, type PreviewTask } from "@/services/desktopPreview";
import s from "./desktop.module.css";

type IconName = "home" | "activity" | "routines" | "settings" | "arrow" | "close" | "check" | "folder" | "globe" | "spark" | "mic" | "stop" | "expand" | "sun" | "move";
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    home: <><path d="m3 10 9-7 9 7v10H3z" /><path d="M9 20v-7h6v7" /></>,
    activity: <><path d="M3 12h4l3-8 4 16 3-8h4" /></>,
    routines: <><path d="M5 7h14M5 17h14m-5-5H5" /><path d="m15 9 4 3-4 3" /></>,
    settings: <><path d="M4 7h16M4 17h16" /><circle cx="8" cy="7" r="3" /><circle cx="16" cy="17" r="3" /></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6" /></>, close: <path d="m6 6 12 12M6 18 18 6" />,
    check: <path d="m5 12 4 4L19 6" />, folder: <path d="M3 6h7l2 3h9v11H3z" />,
    globe: <><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18" /></>,
    spark: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z" /></>,
    mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-3 0h6" /></>,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
    expand: <><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2" /></>,
    move: <><path d="M12 3v18M3 12h18m-12-6 3-3 3 3m-6 12 3 3 3-3M6 9l-3 3 3 3m12-6 3 3-3 3" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export function Presence({ active = false, small = false }: { active?: boolean; small?: boolean }) {
  const id = useId().replace(/:/g, "");
  return <div className={`${s.presence} ${small ? s.smallPresence : ""} ${active ? s.activePresence : ""}`} aria-hidden="true">
    <svg viewBox="0 0 240 240"><defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#d7f6e9" /><stop offset=".45" stopColor="#70c3b4" /><stop offset="1" stopColor="#263f3b" /></linearGradient></defs>
      {Array.from({ length: 14 }, (_, i) => <ellipse key={i} cx="120" cy="120" rx="82" ry={25 + i * 2.8} transform={`rotate(${i * 13} 120 120)`} fill="none" stroke={`url(#${id})`} strokeWidth=".9" opacity={.35 + i * .035} />)}
      <circle cx="120" cy="120" r="27" fill="none" stroke={`url(#${id})`} strokeWidth=".8" />
      <circle cx="120" cy="120" r="4" fill="#c7f2dd" />
    </svg>
  </div>;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const label = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>("[data-initial-focus]")?.focus();
    return () => { dialog?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className={s.dialog} aria-labelledby={label} onCancel={e => { e.preventDefault(); onClose(); }}>
    <div className={s.dialogHeading}><h2 id={label}>{title}</h2><button className={s.iconButton} onClick={onClose} aria-label="Close dialog"><Icon name="close" /></button></div>
    {children}
  </dialog>;
}

const suggestions: { icon: IconName; label: string; description: string; command: string }[] = [
  { icon: "globe", label: "Open your everyday", description: "Chrome, then Gmail", command: "Open Chrome and Gmail" },
  { icon: "folder", label: "A place for everything", description: "Arrange a few sample files", command: "Organize sample files" },
  { icon: "spark", label: "Make a warm introduction", description: "Edit a sample welcome note", command: "Write a welcome note" },
];
const tour = [
  { title: "A space that follows your intention.", text: "Start with one request. The command bar is always a shortcut away: Ctrl+K. Everything in this preview runs without a cloud AI request." },
  { title: "Know what’s happening.", text: "Task steps explain what Rumi is doing. In this preview, computer workflows use sample data and are explicitly marked as simulations." },
  { title: "Stay in control.", text: "Stop cancels a running simulation immediately. Your microphone stays off. Themes and the note editor work locally; real computer actions need the existing verified session." },
];

export default function DesktopPreview() {
  const [view, setView] = useState("workspace");
  const [theme, setTheme] = useState("dark");
  const [reduceMotion, setReduceMotion] = useState(false);
  const [compact, setCompact] = useState(false);
  const [corner, setCorner] = useState(0);
  const [dialog, setDialog] = useState<"command" | "voice" | "tour" | "connect" | null>(null);
  const [tourStep, setTourStep] = useState(0);
  const [input, setInput] = useState("");
  const [notice, setNotice] = useState("");
  const [run, dispatch] = useReducer(previewReducer, null);
  const [history, setHistory] = useState<{ id: number; title: string; result: string }[]>([]);
  const [note, setNote] = useState(WELCOME_SAMPLE);
  const [undoTheme, setUndoTheme] = useState<string | null>(null);
  const sequence = useRef(0);
  const recorded = useRef(0);
  const commandInput = useRef<HTMLInputElement>(null);
  const running = run?.state === "running";

  useEffect(() => { window.scrollTo({ top: 0, behavior: "instant" }); }, [view, compact]);

  useEffect(() => {
    try {
      const prefs = JSON.parse(localStorage.getItem("rumi.desktop.preview.preferences") || "{}");
      if (prefs.theme === "light" || prefs.theme === "dark") setTheme(prefs.theme);
      if (prefs.reduceMotion === true) setReduceMotion(true);
    } catch { /* Storage can be disabled. The preview still works. */ }
  }, []);
  function preferences(nextTheme: string, motion = reduceMotion) {
    setTheme(nextTheme); setReduceMotion(motion);
    try { localStorage.setItem("rumi.desktop.preview.preferences", JSON.stringify({ theme: nextTheme, reduceMotion: motion })); } catch { /* Optional preferences only. */ }
  }
  useEffect(() => {
    function key(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setDialog("command"); }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && (event.code === "Period" || event.key === "." || event.key === ">")) { event.preventDefault(); dispatch({ type: "stop" }); }
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!running || !run) return;
    const timer = setTimeout(() => dispatch({ type: "advance", id: run.id }), 1400);
    return () => clearTimeout(timer);
  }, [running, run]);
  useEffect(() => {
    const hide = () => { if (document.hidden) dispatch({ type: "stop" }); };
    document.addEventListener("visibilitychange", hide);
    return () => document.removeEventListener("visibilitychange", hide);
  }, []);
  useEffect(() => {
    if (!run || run.state === "running" || recorded.current === run.id) return;
    recorded.current = run.id;
    const result = run.state === "cancelled" ? "Cancelled" : run.state === "completed" ? "Rehearsed" : run.task.kind === "theme" ? "Preview theme changed" : "Preview opened";
    setHistory(items => [{ id: run.id, title: run.task.title, result }, ...items].slice(0, 30));
  }, [run]);

  function submit(text: string) {
    if (!text.trim()) return;
    if (/^(stop|cancel)[.!]?$/i.test(text.trim())) { dispatch({ type: "stop" }); setInput(""); setDialog(null); return; }
    if (running) { setNotice("One task at a time. Stop the current rehearsal before starting another."); return; }
    const task = previewTask(text);
    setNotice(""); setInput(""); setDialog(null); setView("workspace");
    if (task.kind === "theme") { setUndoTheme(theme); preferences(task.title.includes("light") ? "light" : "dark"); }
    if (task.kind === "creative") setNote(WELCOME_SAMPLE);
    dispatch({ type: "start", id: ++sequence.current, task });
  }
  function downloadNote() {
    const url = URL.createObjectURL(new Blob([note], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "rumi-welcome-note.txt"; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice("Download requested. Check your browser’s downloads for the note.");
  }
  function commandForm(modal = false) {
    return <form className={`${s.command} ${modal ? s.modalCommand : ""}`} onSubmit={e => { e.preventDefault(); submit(input); }}>
      <span className={s.commandMark}><Icon name="spark" /></span>
      <input ref={modal ? undefined : commandInput} data-initial-focus={modal || undefined} aria-label={modal ? "Quick command" : "Ask Rumi"} value={input} maxLength={500} onChange={e => setInput(e.target.value)} placeholder="What would you like to do?" autoComplete="off" />
      <button type="button" className={s.iconButton} aria-label="Preview voice interaction; microphone stays off" onClick={() => setDialog("voice")}><Icon name="mic" /></button>
      <button className={s.send} disabled={!input.trim()} aria-label="Send command"><Icon name="arrow" /></button>
    </form>;
  }
  function taskContent(task: PreviewTask) {
    if (task.kind === "creative") return <div className={s.editor}>
      <div className={s.documentMeta}><span>WELCOME NOTE</span><span>Prewritten sample</span></div>
      <label className={s.srOnly} htmlFor="welcome-note">Edit welcome note</label><textarea id="welcome-note" value={note} maxLength={16000} onChange={e => setNote(e.target.value)} />
      <div className={s.editorFooter}><span>Kept in this tab · {note.length} characters</span><button className={s.primary} onClick={downloadNote}>Download .txt <Icon name="arrow" size={16} /></button></div>
    </div>;
    if (task.kind === "shutdown") return <div className={s.confirmation}><Icon name="stop" /><h3>Your work comes first.</h3><p>A real shutdown would ask you to save your work and offer a chance to cancel.</p><button className={s.secondary} onClick={() => { setNotice("Shutdown preview dismissed. Your computer is still on."); dispatch({ type: "dismiss" }); }}>Keep working</button><span>Shutdown is unavailable in this preview.</span></div>;
    if (task.kind === "theme") return <div className={s.themeResult}><Icon name="sun" size={40} /><p>The same space. A different light.</p>{undoTheme && <button className={s.secondary} onClick={() => { preferences(undoTheme); setUndoTheme(null); setNotice("Previous Rumi theme restored."); }}>Undo theme change</button>}</div>;
    if (task.kind === "failure" || task.kind === "clarification") return <div className={s.clarification}><span className={s.amberDot} /><p>{task.detail}</p><button className={s.secondary} onClick={() => { setInput("Open Chrome and Gmail"); commandInput.current?.focus(); }}>Try an example <Icon name="arrow" size={16} /></button></div>;
    return <>
      <ol className={s.steps}>{task.steps.map((step, i) => <li key={step} data-state={run && i < run.step ? "done" : run?.state === "running" && i === run.step ? "current" : "pending"}><span>{run && i < run.step ? <Icon name="check" size={14} /> : `0${i + 1}`}</span><div>{step}<small>{i === 0 ? "Use a specific target" : i === 1 ? "One bounded action" : "Report only an observed result"}</small></div></li>)}</ol>
      {task.kind === "files" && run?.state === "completed" && <div className={s.sampleFiles}><span><Icon name="folder" size={17} /> Documents <small>brief.pdf · notes.txt</small></span><span><Icon name="folder" size={17} /> Images <small>moodboard.png</small></span><p>Sample files only</p></div>}
      <div className={s.taskFoot}>{run?.state === "cancelled" ? "Rehearsal stopped. No computer actions were performed." : run?.state === "completed" ? task.detail : "Simulated workflow · no computer actions will be performed."}</div>
    </>;
  }

  return <div className={s.root} data-theme={theme} data-reduced-motion={reduceMotion}>
    <a href="#desktop-main" className={s.skip}>Skip to workspace</a>
    <div className={s.shell} hidden={compact}>
      <aside className={s.sidebar}>
        <a className={s.brand} href="/desktop/" aria-label="Rumi desktop preview"><span className={s.brandSymbol}>r.</span><span>rumi<span className={s.brandCaption}>A LITTLE MORE POSSIBLE</span></span></a>
        <button className={s.quickCommand} onClick={() => setDialog("command")}><Icon name="spark" size={17} /> Quick command <kbd>Ctrl K</kbd></button>
        <nav aria-label="Desktop navigation">{([{ id: "workspace", label: "Workspace", icon: "home" }, { id: "activity", label: "Activity", icon: "activity" }, { id: "routines", label: "Routines", icon: "routines" }] as const).map(item => <button key={item.id} aria-current={view === item.id ? "page" : undefined} onClick={() => setView(item.id)}><Icon name={item.icon} />{item.label}{item.id === "workspace" && <span className={s.navDot} />}</button>)}<button className={s.mobileNav} aria-label="Open preferences" aria-current={view === "settings" ? "page" : undefined} onClick={() => setView("settings")}><Icon name="settings" />Preferences</button></nav>
        <div className={s.sidebarNote}><span className={s.eyebrow}>BUILT AROUND YOU</span><p>Less between<br />intention and action.</p><span className={s.orbitLine} /></div>
        <div className={s.sidebarBottom}><button onClick={() => { setTourStep(0); setDialog("tour"); }}><span className={s.questionMark}>?</span> A quick introduction</button><button aria-current={view === "settings" ? "page" : undefined} onClick={() => setView("settings")}><Icon name="settings" /> Preferences</button><div className={s.localProfile}><span>Y</span><div>Your space<small>On this device</small></div><span className={s.statusDot} /></div></div>
      </aside>
      <div className={s.body}>
        <header className={s.topbar}><div className={s.breadcrumb}>Your space <span>/</span> <strong>{view === "settings" ? "Preferences" : view[0].toUpperCase() + view.slice(1)}</strong></div><div className={s.topActions}><button className={s.iconButton} aria-label="Open introduction" onClick={() => { setTourStep(0); setDialog("tour"); }}><span className={s.questionMark}>?</span></button><span className={s.previewBadge}>INTERACTIVE PREVIEW</span><button className={s.iconButton} aria-label="Switch to compact companion" title="Compact companion" onClick={() => setCompact(true)}><Icon name="expand" size={18} /></button></div></header>
        <main id="desktop-main" className={s.main} tabIndex={-1}>
          <div className={s.connectionLine}><span><i className={s.statusDot} /> Local preview <b>·</b> Cloud AI off</span><button onClick={() => setDialog("connect")}>About this preview <Icon name="arrow" size={14} /></button></div>
          {view === "workspace" && <>
            <div className={s.hero}><div><span className={s.eyebrow}>SPACE TO DO YOUR THING</span><h1>A little less effort.<br /><em>A lot more possibility.</em></h1><p>Your ideas, your everyday, your next big thing.<br />Start with what’s on your mind.</p></div><div className={s.heroPresence}><Presence active={!!running} /><span><i className={s.statusDot} />{running ? "Rehearsing a task" : "Here when you need me"}</span></div></div>
            {commandForm()}<div className={s.commandHint}><span><kbd>Enter</kbd> to send <span>·</span> <kbd>Ctrl K</kbd> from anywhere in this page</span><span>Microphone off</span></div>
            <div className={s.sectionHeading}><h2>A few places to start</h2><span>TRY SOMETHING SMALL</span></div>
            <div className={s.suggestions}>{suggestions.map((item, i) => <button key={item.command} onClick={() => submit(item.command)} disabled={!!running}><span className={s.suggestionTop}><Icon name={item.icon} /><span>0{i + 1}</span></span><strong>{item.label}</strong><span>{item.description}</span><Icon name="arrow" size={17} /></button>)}</div>
            <div className={s.workArea}>
              <section className={s.taskPanel} aria-labelledby="task-title"><div className={s.panelHeading}><span className={s.eyebrow}>IN FOCUS</span><span className={s.taskBadge}>{running ? "SIMULATING" : run?.state === "cancelled" ? "STOPPED" : run?.state === "completed" ? "REHEARSED" : "PREVIEW"}</span></div>
                <h2 id="task-title">{run?.task.title || "Good things start with a small step."}</h2>
                {run ? taskContent(run.task) : <div className={s.emptyTask}><span className={s.emptyCross}>✳</span><p>Give a task your attention.<br />We’ll make room for the details here.</p><button className={s.textButton} onClick={() => submit("Open Chrome and Gmail")}>Rehearse your first task <Icon name="arrow" size={16} /></button></div>}
                {running && <button className={s.stopButton} onClick={() => dispatch({ type: "stop" })}><Icon name="stop" size={16} /> Stop rehearsal</button>}
              </section>
              <aside className={s.sidePanel}><span className={s.eyebrow}>ON YOUR TERMS</span><h2>Quietly capable.<br /><em>Clearly yours.</em></h2><p>Explore freely. This preview uses sample tasks, keeps your microphone off, and makes no cloud AI requests.</p><div className={s.assurance}><Icon name="check" size={16} /><span>No app or file automation</span></div><button className={s.textButton} onClick={() => setView("settings")}>Make yourself at home <Icon name="arrow" size={16} /></button><div className={s.sideDecoration} aria-hidden="true"><span /><span /><span /><span /><span /></div></aside>
            </div>
          </>}
          {view === "activity" && <section className={s.pageSection}><span className={s.eyebrow}>A LITTLE CLARITY</span><h1>Your recent steps.</h1><p>Preview activity from this tab. Refreshing clears this list and your edited note.</p><div className={s.activityList}>{history.length ? history.map(item => <article key={item.id}><span className={s.activityIcon}><Icon name="activity" /></span><div><h2>{item.title}</h2><p>{item.result}</p></div><span>LOCAL PREVIEW</span></article>) : <div className={s.emptyTask}><Icon name="activity" size={36} /><h2>A fresh start.</h2><p>Your rehearsals will appear here.</p><button className={s.secondary} onClick={() => setView("workspace")}>Explore the workspace</button></div>}</div></section>}
          {view === "routines" && <section className={s.pageSection}><span className={s.eyebrow}>FIND YOUR RHYTHM</span><h1>Small rituals.<br /><em>More room to think.</em></h1><p>Rehearse a reusable workflow. These examples don’t launch apps or touch your files.</p><div className={s.routineGrid}>{suggestions.slice(0, 2).map(item => <article key={item.command}><Icon name={item.icon} size={30} /><h2>{item.label}</h2><p>{item.description}</p><button className={s.primary} disabled={!!running} onClick={() => submit(item.command)}>Rehearse routine <Icon name="arrow" size={16} /></button></article>)}</div></section>}
          {view === "settings" && <section className={s.pageSection}><span className={s.eyebrow}>MAKE ROOM FOR YOU</span><h1>Feels like your space.</h1><p>Only appearance preferences are saved on this device.</p><div className={s.settingsList}>
            <fieldset><legend>Appearance</legend><p>Choose the light you like working in.</p><div className={s.themeChoices}>{["dark", "light"].map(value => <label key={value}><input type="radio" name="appearance" value={value} checked={theme === value} onChange={() => preferences(value)} /><span className={value === "dark" ? s.darkSwatch : s.lightSwatch} /><span>{value === "dark" ? "After hours" : "Daylight"}</span><small>{value === "dark" ? "Dark" : "Light"}</small></label>)}</div></fieldset>
            <div className={s.settingRow}><div><h2>Gentler motion</h2><p>Keep transitions still. Your system’s reduced-motion preference is also respected.</p></div><input type="checkbox" aria-label="Gentler motion" checked={reduceMotion} onChange={e => preferences(theme, e.target.checked)} /></div>
            <div className={s.settingRow}><div><h2>Cloud AI</h2><p>Unavailable in this preview. No keys, model requests or background AI sessions.</p></div><span className={s.settingValue}>OFF</span></div>
            <div className={s.settingRow}><div><h2>Microphone</h2><p>The voice interaction is a visual rehearsal. No audio is recorded.</p></div><span className={s.settingValue}>OFF</span></div>
            <div className={s.settingRow}><div><h2>Real computer actions</h2><p>Available separately through Rumi’s verified owner session and paired helper.</p></div><button className={s.secondary} onClick={() => setDialog("connect")}>Details</button></div>
          </div><button className={s.textButton} onClick={() => submit("Open missing app")}>Explore an example failure <Icon name="arrow" size={16} /></button></section>}
          <div className={s.notice} role="status" aria-live="polite">{notice || (running ? `Simulation: ${run.task.steps[run.step]}` : run?.state === "cancelled" ? "Rehearsal stopped." : run?.state === "completed" ? "Rehearsal complete. No computer actions performed." : "")}</div>
        </main>
        <footer className={s.footer}><span><i className={s.statusDot} /> Designed for your everyday.</span><span>RUMI DESKTOP <b>/</b> CONCEPT 01</span></footer>
      </div>
    </div>
    {compact && <div className={s.compactStage}><div className={s.compactBackdrop}><span className={s.eyebrow}>A LITTLE PRESENCE. A LOT OF POSSIBILITY.</span><h1>Room for your world.</h1><p>The companion stays within this browser preview.<br />A system-wide Windows overlay comes in the packaging phase.</p><button className={s.secondary} onClick={() => setCompact(false)}>Return to workspace</button></div><section className={`${s.companion} ${s[`corner${corner}`]}`} aria-label="Compact Rumi companion"><Presence active={!!running} small /><div><strong>Rumi</strong><span>{running ? "Rehearsing · simulated" : "Here when you need me"}</span></div><button className={s.iconButton} aria-label="Move companion to another corner" onClick={() => setCorner(c => (c + 1) % 4)}><Icon name="move" size={17} /></button><button className={s.iconButton} aria-label="Expand workspace" onClick={() => setCompact(false)}><Icon name="expand" size={17} /></button><div className={s.companionActions}><button className={s.secondary} onClick={() => setDialog("command")}>Ask Rumi <kbd>Ctrl K</kbd></button><button className={s.stopButton} disabled={!running} onClick={() => dispatch({ type: "stop" })}>Stop</button></div><small role="status">Cloud AI off · microphone off{run?.state === "cancelled" ? " · stopped" : ""}</small></section></div>}
    {running && view !== "workspace" && !compact && <button className={s.floatingStop} onClick={() => dispatch({ type: "stop" })}><Icon name="stop" size={16} /> Stop rehearsal</button>}
    {dialog === "command" && <Modal title="A thought. A next step." onClose={() => setDialog(null)}>{commandForm(true)}<p className={s.modalHint}>Local interactive preview. Try one of these:</p><div className={s.commandOptions}>{[...suggestions.map(item => item.command), "Switch to light mode", "Shut down my laptop"].map(text => <button key={text} onClick={() => submit(text)}>{text}<Icon name="arrow" size={16} /></button>)}</div><p role="status">{notice}</p></Modal>}
    {dialog === "voice" && <Modal title="A glimpse of voice." onClose={() => setDialog(null)}><div className={s.voicePreview}><Presence active={!reduceMotion} /><span className={s.previewBadge}>VISUAL REHEARSAL</span><h3>“Open Chrome and Gmail.”</h3><p>Your microphone is off. Use the sample transcript to explore how a spoken request would become a task.</p><button className={s.primary} disabled={!!running} onClick={() => submit("Open Chrome and Gmail")}>Use sample transcript <Icon name="arrow" size={16} /></button></div></Modal>}
    {dialog === "tour" && <Modal title={`Meet your space · ${tourStep + 1} of 3`} onClose={() => setDialog(null)}><Presence small /><h3 className={s.tourTitle}>{tour[tourStep].title}</h3><p className={s.modalHint}>{tour[tourStep].text}</p><div className={s.tourActions}><button className={s.textButton} onClick={() => setDialog(null)}>Skip introduction</button><button className={s.primary} onClick={() => tourStep < 2 ? setTourStep(t => t + 1) : setDialog(null)}>{tourStep < 2 ? "Next" : "Make yourself at home"}<Icon name="arrow" size={16} /></button></div></Modal>}
    {dialog === "connect" && <Modal title="A preview, on your terms." onClose={() => setDialog(null)}><p className={s.modalHint}>This workspace is a local interaction prototype. Task progress uses sample scenarios. It cannot access your apps, files, microphone or Windows settings.</p><p className={s.modalHint}>Appearance changes and note editing work here. Real computer actions remain in the existing dashboard and require sign-in, owner verification and helper pairing. That session may use cloud services.</p><div className={s.tourActions}><button className={s.secondary} onClick={() => setDialog(null)}>Stay in preview</button><a className={s.textButton} href="/dashboard/">Open existing dashboard <Icon name="arrow" size={16} /></a></div></Modal>}
  </div>;
}
