"use client";
import React, { useEffect, useRef, useState } from "react";
import RumiCompanion from "./RumiCompanion";
import { companionExpressions } from "@/services/companion";
import s from "./expressions.module.css";

export default function RumiExpressions({ reduced, fullMotion = false, onClose, onStop }: { reduced: boolean; fullMotion?: boolean; onClose(): void; onStop(): void }) {
  const [index, setIndex] = useState(0);
  const dialog = useRef<HTMLDivElement>(null), close = useRef<HTMLButtonElement>(null);
  const actions = useRef({ onClose, onStop }); actions.current = { onClose, onStop };
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    close.current?.focus({ preventScroll: true });
    function key(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); actions.current.onStop(); actions.current.onClose(); return; }
      if (event.key !== "Tab") return;
      const controls = dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),select');
      if (!controls?.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); previous?.focus({ preventScroll: true }); };
  }, []);
  const expression = companionExpressions[index];
  return <div className={s.backdrop}><div ref={dialog} className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="expressions-title" aria-describedby="expressions-note">
    <header><div><span>THE LITTLE THINGS THAT MAKE ME, ME</span><h2 id="expressions-title">Meet Rumi.</h2></div><button ref={close} onClick={onClose} aria-label="Close expression preview">✕</button></header>
    <p id="expressions-note">Expression preview · microphone paused · no computer commands</p>
    <div className={s.stage}><RumiCompanion mood={expression.mood} level={expression.mood === "listening" ? 65 : 0} preview reduced={reduced} fullMotion={fullMotion}/></div>
    <div className={s.caption} aria-live="polite"><h3>{expression.label}</h3><p>{expression.detail}</p></div>
    <nav aria-label="Character expressions"><button aria-label="Previous expression" onClick={() => setIndex(value => (value + companionExpressions.length - 1) % companionExpressions.length)}>←</button><select aria-label="Expression" value={index} onChange={event => setIndex(Number(event.target.value))}>{companionExpressions.map((item, i) => <option value={i} key={item.mood}>{i + 1}. {item.label}</option>)}</select><button aria-label="Next expression" onClick={() => setIndex(value => (value + 1) % companionExpressions.length)}>→</button></nav>
    <button className={s.stop} onClick={() => { onStop(); onClose(); }}>Stop & disconnect</button>
  </div></div>;
}
