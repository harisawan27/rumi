"use client";

import { useEffect, useState } from "react";

interface Props {
  interactionId: string;
  trigger: "A" | "B" | "C" | "E" | "G";
  text: string;
  onRespond: (interactionId: string, response: "accepted" | "dismissed") => void;
}

const AUTO_DISMISS_MS = 2 * 60 * 1000; // 2 minutes

const TRIGGER_META: Record<string, { label: string; icon: string; accent: string }> = {
  A: { label: "Rumi senses frustration",   icon: "◈", accent: "var(--error)" },
  B: { label: "Rumi checks in",            icon: "◇", accent: "var(--teal)" },
  C: { label: "Time for a break",          icon: "◉", accent: "var(--gold)" },
  E: { label: "Rumi celebrates your focus",icon: "◆", accent: "var(--success)" },
};

export default function InterventionCard({ interactionId, trigger, text, onRespond }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (visible) {
        onRespond(interactionId, "dismissed");
        setVisible(false);
      }
    }, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [interactionId, visible, onRespond]);

  if (!visible) return null;

  function handle(response: "accepted" | "dismissed") {
    onRespond(interactionId, response);
    setVisible(false);
  }

  const meta = TRIGGER_META[trigger] ?? TRIGGER_META.B;

  return (
    <div
      className="glass-gold rounded-2xl p-5 w-full max-w-lg animate-intervention"
      style={{ boxShadow: "0 8px 40px rgba(201,168,76,0.12)" }}
    >
      {/* Label row */}
      <div className="flex items-center gap-2 mb-3">
        <span style={{ color: meta.accent, fontSize: "0.9rem" }}>{meta.icon}</span>
        <span className="uppercase-label" style={{ color: meta.accent, letterSpacing: "0.18em" }}>
          {meta.label}
        </span>
      </div>

      {/* Text */}
      <p
        className="leading-relaxed mb-5"
        style={{ color: "var(--text)", fontSize: "0.9375rem", lineHeight: 1.65 }}
      >
        {text}
      </p>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => handle("accepted")}
          className="btn-primary"
          style={{ flex: 1, fontSize: "0.8125rem", padding: "0.6rem 1rem" }}
        >
          Thank you
        </button>
        <button
          onClick={() => handle("dismissed")}
          className="btn-ghost"
          style={{ flex: 1, fontSize: "0.8125rem", padding: "0.6rem 1rem" }}
        >
          Not now
        </button>
      </div>
    </div>
  );
}
