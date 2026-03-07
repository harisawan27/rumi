"use client";

import { useState } from "react";
import { ObservationState } from "./ObservationIndicator";
import { auth } from "@/services/firebase";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

interface Props {
  sessionId: string;
  observationState: ObservationState;
  onStateChange: (state: ObservationState) => void;
}

export default function PauseButton({ sessionId, observationState, onStateChange }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (!sessionId) return;
    const user = auth.currentUser;
    const token = user ? await user.getIdToken() : sessionStorage.getItem("id_token");
    if (!token) return;
    setLoading(true);
    const isPaused = observationState === "paused";
    const endpoint = isPaused
      ? `/session/${sessionId}/resume`
      : `/session/${sessionId}/pause`;

    try {
      const res = await fetch(`${BACKEND_URL}${endpoint}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        onStateChange(isPaused ? "active" : "paused");
      }
    } finally {
      setLoading(false);
    }
  }

  const isPaused = observationState === "paused";
  const isDisabled = loading || observationState === "degraded";

  return (
    <button
      onClick={handleClick}
      disabled={isDisabled}
      className="btn-icon"
      title={isPaused ? "Resume observation" : "Pause observation"}
      style={
        !isDisabled && !isPaused
          ? { borderColor: "var(--gold-dim)", color: "var(--gold)" }
          : {}
      }
    >
      {loading ? (
        <span
          style={{
            display: "inline-block",
            width: 14,
            height: 14,
            borderRadius: "50%",
            border: "2px solid currentColor",
            borderTopColor: "transparent",
            animation: "spin 0.7s linear infinite",
          }}
        />
      ) : isPaused ? (
        /* Play icon */
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
          <path d="M3 2.5l9 4.5-9 4.5V2.5z" />
        </svg>
      ) : (
        /* Pause icon */
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
          <rect x="3" y="2" width="3" height="10" rx="1" />
          <rect x="8" y="2" width="3" height="10" rx="1" />
        </svg>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </button>
  );
}
