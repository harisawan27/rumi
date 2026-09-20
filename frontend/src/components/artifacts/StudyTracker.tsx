"use client";
import React, { useState } from "react";
import { ColorToken, GeneratedArtifact, StudyStateEdit, weekDates } from "../../types/artifacts";
import { addStudyEntry, calculateDailyTotals, calculateSubjectTotals } from "../../services/studyTracker";

export const SUBJECT_COLORS: Record<ColorToken, string> = {
  red: "#f87171", blue: "#60a5fa", green: "#4ade80", gold: "#c9a84c", purple: "#c084fc", teal: "#22d3ee", orange: "#fb923c",
};
export interface TrackerProps { artifact: GeneratedArtifact; onEdit: (edit: StudyStateEdit) => Promise<void>; busy?: boolean }
export default function StudyTracker({ artifact, onEdit, busy = false }: TrackerProps) {
  const [subject, setSubject] = useState(artifact.spec.subjects[0].id);
  const [date, setDate] = useState(artifact.spec.week_start);
  const [minutes, setMinutes] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const days = calculateDailyTotals(artifact);
  const subjects = calculateSubjectTotals(artifact);
  const dates = weekDates(artifact.spec.week_start);
  async function send(edit: StudyStateEdit) {
    setError(""); setSaving(true);
    try { await onEdit(edit); setMinutes(""); } catch (e) { setError(e instanceof Error ? e.message : "Could not save. Please reload."); }
    finally { setSaving(false); }
  }
  function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const entry = { id: crypto.randomUUID(), subject_id: subject, date, minutes: Number(minutes) };
      addStudyEntry(artifact, entry);
      void send({ operation: "add_entry", entry });
    } catch (e) { setError((e as Error).message); }
  }
  return <section className="study-tracker" aria-label="Study tracker">
    <h2>{artifact.title}</h2>
    <p>{dates[0]} – {dates[6]}</p>
    <p aria-live="polite"><strong>{days.reduce((n, d) => n + d.minutes, 0)} minutes</strong> this week</p>
    <ul className="study-subjects">{subjects.map(s => <li key={s.id}><span className="study-dot" style={{ backgroundColor: SUBJECT_COLORS[s.color_token] }} />{s.label}: <strong>{s.minutes} min</strong></li>)}</ul>
    <form onSubmit={submit} noValidate>
      <label>Subject<select value={subject} onChange={e => setSubject(e.target.value)}>{artifact.spec.subjects.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
      <label>Date<input type="date" value={date} min={dates[0]} max={dates[6]} onChange={e => setDate(e.target.value)} /></label>
      <label>Minutes<input type="number" inputMode="numeric" min="1" max="1440" step="1" value={minutes} onChange={e => setMinutes(e.target.value)} /></label>
      <button disabled={busy || saving} type="submit">{busy || saving ? "Saving…" : "Add entry"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    <h3>Study entries</h3>
    {artifact.state.entries.length === 0 ? <p>No study entries yet.</p> : <ul className="study-entries">{artifact.state.entries.map(e => {
      const label = artifact.spec.subjects.find(s => s.id === e.subject_id)!.label;
      return <li key={e.id}><span>{label} · {e.date} · {e.minutes} min</span><button disabled={busy || saving} onClick={() => void send({ operation: "remove_entry", entry_id: e.id })} aria-label={`Remove ${label} entry on ${e.date}`}>Remove</button></li>;
    })}</ul>}
    <h3>Daily totals</h3>
    <ul aria-label={artifact.spec.show_daily_graph ? "Daily study graph" : "Daily study totals"} className="study-days">{days.map(d => <li key={d.date}>
      <span>{d.date}: <strong>{d.minutes} min</strong></span>
      {artifact.spec.show_daily_graph && <div aria-hidden="true" className="study-bar-track"><div className="study-bar" style={{ width: `${d.minutes / Math.max(1, ...days.map(day => day.minutes)) * 100}%` }} /></div>}
    </li>)}</ul>
    <style>{`
      .study-tracker { min-width:0; color:var(--text,#e2e8f0); overflow-wrap:anywhere; font-size:14px; }
      .study-tracker h2 { color:var(--gold,#c9a84c); font-size:24px; margin:0 0 8px; }
      .study-tracker h3 { margin:22px 0 8px; font-size:16px; }
      .study-tracker p { margin:8px 0; }
      .study-tracker ul { list-style:none; padding:0; margin:12px 0; }
      .study-tracker li { margin:8px 0; }
      .study-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; }
      .study-tracker form { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr)); gap:12px; margin-top:20px; align-items:end; }
      .study-tracker label { display:flex; flex-direction:column; gap:6px; min-width:0; }
      .study-tracker input,.study-tracker select { color-scheme:dark; }
      .study-tracker input,.study-tracker select,.study-tracker button { box-sizing:border-box; width:100%; min-width:0; min-height:44px; border:1px solid #334155; border-radius:8px; background:#0c1624; color:#e2e8f0; padding:8px; font:inherit; }
      .study-tracker button { color:#67e8f9; cursor:pointer; width:auto; }
      .study-tracker button:disabled { opacity:.55; cursor:wait; }
      .study-tracker :focus-visible { outline:2px solid #22d3ee; outline-offset:2px; }
      .study-entries li { display:flex; flex-wrap:wrap; align-items:center; gap:8px; border-bottom:1px solid #334155; padding-bottom:8px; }
      .study-entries li span { flex:1; min-width:120px; }
      .study-bar-track { height:8px; background:#1e293b; margin-top:6px; border-radius:4px; overflow:hidden; }
      .study-bar { height:100%; background:#22d3ee; }
      .study-tracker [role=alert] { color:#fca5a5; }
    `}</style>
  </section>;
}
