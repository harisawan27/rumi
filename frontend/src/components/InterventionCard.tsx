"use client";

import { useEffect, useState } from "react";

interface Props {
  interactionId: string;
  trigger: "A" | "B";
  text: string;
  onRespond: (interactionId: string, response: "accepted" | "dismissed") => void;
}

const AUTO_DISMISS_MS = 2 * 60 * 1000; // 2 minutes

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

  const label = trigger === "A" ? "Mirr'at senses frustration" : "Mirr'at checks in";

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-5 space-y-4 shadow-lg max-w-lg">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-white text-sm leading-relaxed">{text}</p>
      <div className="flex gap-3">
        <button
          onClick={() => handle("accepted")}
          className="px-4 py-2 bg-green-700 hover:bg-green-600 text-white text-sm rounded-lg transition"
        >
          Accept
        </button>
        <button
          onClick={() => handle("dismissed")}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
