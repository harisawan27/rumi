"use client";
import React, { useEffect, useId, useRef, useState } from "react";
import { companionExpressions, type CompanionMood } from "@/services/companion";
import s from "./companion.module.css";

export default function RumiCompanion({ mood, level = 0, reduced = false, fullMotion = false, preview = false, paused = false, reaction = 0 }: { mood: CompanionMood; level?: number; reduced?: boolean; fullMotion?: boolean; preview?: boolean; paused?: boolean; reaction?: number }) {
  const id = useId().replace(/:/g, "");
  const root = useRef<HTMLDivElement>(null), frame = useRef<number | null>(null);
  const [sleeping, setSleeping] = useState(false), [hello, setHello] = useState(false), [hidden, setHidden] = useState(false);
  useEffect(() => {
    const change = () => setHidden(document.hidden);
    change(); document.addEventListener("visibilitychange", change);
    return () => { document.removeEventListener("visibilitychange", change); if (frame.current !== null) cancelAnimationFrame(frame.current); };
  }, []);
  useEffect(() => {
    setSleeping(false);
    if (mood !== "idle" || preview || hello || hidden || paused) return;
    const timer = setTimeout(() => setSleeping(true), 45000);
    return () => clearTimeout(timer);
  }, [mood, preview, hello, hidden, paused]);
  useEffect(() => {
    if (!hello) return;
    const timer = setTimeout(() => setHello(false), 2200);
    return () => clearTimeout(timer);
  }, [hello]);
  const shown = mood === "idle" && hello ? "greeting" : mood === "idle" && sleeping ? "sleeping" : mood;
  const label = companionExpressions.find(item => item.mood === shown)?.label || "Here with you";
  const happy = shown === "success" || shown === "greeting";
  const uncertain = shown === "confused" || shown === "confirming";
  const calm = shown === "sleeping" || shown === "stopped";
  const eyes = happy ? ["M158 183q12-22 25 0", "M237 183q12-22 25 0"] : calm ? ["M158 181q12 10 25 0", "M237 181q12 10 25 0"] : shown === "error" ? ["M158 178l25-5", "M237 173l25 5"] : null;
  const mouth = happy ? "M192 199q18 23 36 0" : shown === "error" ? "M199 209q11-10 22 0" : uncertain ? "M205 205h10" : calm ? "M201 205q9 4 18 0" : "M199 201q11 9 22 0";
  function look(event: React.PointerEvent<HTMLDivElement>) {
    if (reduced || event.pointerType === "touch" || !["idle", "greeting"].includes(shown)) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, (event.clientX - bounds.left) / bounds.width * 2 - 1));
    const y = Math.max(-1, Math.min(1, (event.clientY - bounds.top) / bounds.height * 2 - 1));
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => { root.current?.style.setProperty("--look-x", `${x * 5}px`); root.current?.style.setProperty("--look-y", `${y * 3}px`); frame.current = null; });
  }
  function resetLook() {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null; root.current?.style.setProperty("--look-x", "0px"); root.current?.style.setProperty("--look-y", "0px");
  }
  return <div ref={root} className={s.companion} data-mood={shown} data-reduced={reduced} data-full-motion={fullMotion} data-paused={hidden || paused} onPointerMove={look} onPointerLeave={resetLook} style={{ "--voice-level": Math.max(0, Math.min(1, level / 100)) } as React.CSSProperties}>
    <div className={s.aura}/><div className={s.orbit}/><div className={s.orbitTwo}/>
    <svg className={s.robot} viewBox="0 0 420 420" role="img" aria-label={`Rumi companion: ${shown}`}>
      <title>{label}</title>
      <defs>
        <linearGradient id={`${id}shell`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f1fffd"/><stop offset=".4" stopColor="#8cb9c3"/><stop offset=".72" stopColor="#305a6d"/><stop offset="1" stopColor="#101d35"/></linearGradient>
        <linearGradient id={`${id}visor`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#0f2535"/><stop offset="1" stopColor="#030911"/></linearGradient>
        <radialGradient id={`${id}core`}><stop stopColor="#eaffff"/><stop offset=".3" stopColor="#80f7e4"/><stop offset="1" stopColor="#207a8b" stopOpacity="0"/></radialGradient>
      </defs>
      <g className={s.float}>
        <g className={s.gesture} key={`${shown}-${reaction}`}>
          <g className={s.torso}>
            <path d="M159 249Q210 230 261 249L252 301Q210 331 168 301Z" fill={`url(#${id}shell)`} stroke="#90d2d5" strokeWidth="1.2"/>
            <path d="M177 285Q210 302 243 285" fill="none" stroke="#244b5c"/>
            <circle className={s.core} cx="210" cy="273" r="24" fill={`url(#${id}core)`}/><circle cx="210" cy="273" r="5" fill="#cbfff5"/>
          </g>
          <g className={s.leftHand}><path d="M145 252Q122 244 117 263L113 287Q128 300 140 282Z" fill={`url(#${id}shell)`}/><path d="m117 277 16 5" stroke="#96ede7"/></g>
          <g className={s.rightHand}><path d="M275 252Q298 244 303 263L307 287Q292 300 280 282Z" fill={`url(#${id}shell)`}/><path d="m303 277-16 5" stroke="#96ede7"/></g>
          <g className={s.head}>
            <path d="M203 109v-22" stroke="#709eab" strokeWidth="4"/><circle className={s.antenna} cx="203" cy="81" r="7" fill="#aafeea"/>
            <path d="M112 153Q111 111 165 106L255 106Q309 111 308 153L304 204Q302 243 253 248H167Q118 243 116 204Z" fill={`url(#${id}shell)`} stroke="#b5e4e4" strokeWidth="1.3"/>
            <path d="M111 161Q95 158 96 179Q96 198 114 195M309 161Q325 158 324 179Q324 198 306 195" fill="#417083" stroke="#91cece"/>
            <path d="M133 152Q133 130 163 128H257Q287 130 287 152V194Q286 224 255 225H165Q134 224 133 194Z" fill={`url(#${id}visor)`} stroke="#194458" strokeWidth="2"/>
            <path d="M149 147Q187 134 225 139" stroke="#3f7081" strokeOpacity=".45" strokeWidth="3" strokeLinecap="round" fill="none"/>
            <g className={s.gaze}>
              <g className={s.brows} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d={uncertain ? "M157 150l24 6" : "M158 151h24"}/><path d={uncertain ? "M237 149l25-7" : "M238 151h24"}/></g>
              <g className={s.blink}><g className={s.eyes}>
                {eyes ? <g fill="none" stroke="currentColor" strokeWidth="7" strokeLinecap="round"><path d={eyes[0]}/><path d={eyes[1]}/></g> : <g fill="currentColor"><rect className={s.leftEye} x="158" y="163" width="25" height="33" rx="12"/><rect className={s.rightEye} x="237" y="163" width="25" height="33" rx="12"/></g>}
              </g></g>
              <path className={s.smile} d={mouth} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
              <ellipse className={s.talkingMouth} cx="210" cy="205" rx="10" ry="7" fill="currentColor"/>
              <g className={s.cheeks} stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M149 207h12M259 207h12"/></g>
            </g>
            <path d="M178 237h64" stroke="#bafaf0" strokeOpacity=".6" strokeWidth="2"/>
          </g>
          <g className={s.book} stroke="#8debdc" strokeWidth="1.5" fill="#0a2936" strokeLinejoin="round"><path d="M157 274q26-8 53 5q27-13 53-5v40q-27-8-53 5q-27-13-53-5Z"/><path d="M210 279v40M168 286l29 5m-29 6 29 5m25-11 29-5m-29 16 29-5"/></g>
          <g className={s.pencil} stroke="#acffe6" strokeWidth="3" strokeLinecap="round"><path d="m257 274 27-28m-27 28-4 9 9-4"/><path className={s.ink} d="M175 305h31m-31 8h54" strokeWidth="2"/></g>
          <g className={s.search} fill="none" stroke="#93dded" strokeWidth="2"><rect x="143" y="270" width="134" height="45" rx="7"/><path d="M157 284h50m-50 13h42"/><g className={s.lens}><circle cx="242" cy="285" r="11"/><path d="m250 293 10 10"/></g></g>
          <g className={s.window} fill="#0b2d3d" stroke="#93dded" strokeWidth="1.5"><rect x="277" y="198" width="65" height="48" rx="5"/><path d="M277 209h65M284 204h3m4 0h3"/><path className={s.launchArrow} d="m294 233 20-15m-12 0h12v11" fill="none"/></g>
          <g className={s.thoughts} fill="currentColor"><circle cx="311" cy="133" r="3"/><circle cx="325" cy="119" r="4"/><circle cx="342" cy="106" r="5"/></g>
          <g className={s.question} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M320 130q-1-15 12-15q16 0 9 13l-9 8v5m0 9v1"/></g>
          <g className={s.sparkles} fill="currentColor"><path d="m111 111 4 10 10 4-10 4-4 10-4-10-10-4 10-4Z"/><path d="m324 153 3 8 8 3-8 3-3 8-3-8-8-3 8-3Z"/><path d="m272 84 2 6 6 2-6 2-2 6-2-6-6-2 6-2Z"/></g>
          <g className={s.sleepMarks} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M306 147h12l-12 12h12M325 121h16l-16 16h16"/></g>
          <g className={s.listeningWaves} fill="none" stroke="currentColor" strokeWidth="2"><path d="M89 155q-14 25 0 48M77 147q-20 33 0 64M337 155q14 25 0 48M349 147q20 33 0 64"/></g>
        </g>
      </g>
      <ellipse className={s.shadow} cx="210" cy="354" rx="65" ry="7" fill="#49adba"/>
      <ellipse cx="210" cy="353" rx="110" ry="23" fill="none" stroke="#387488" strokeOpacity=".4"/>
      <ellipse cx="210" cy="353" rx="142" ry="33" fill="none" stroke="#387488" strokeOpacity=".16" strokeDasharray="3 11"/>
    </svg>
    {!preview && <button className={s.hello} aria-label="Say hello to Rumi" title="Say hello" onClick={() => { setSleeping(false); setHello(true); }}>✦</button>}
  </div>;
}
