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

  const label = observationState === "paused" ? "Resume" : "Pause";

  return (
    <button
      onClick={handleClick}
      disabled={loading || observationState === "degraded"}
      className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm rounded-lg disabled:opacity-50 transition"
    >
      {loading ? "…" : label}
    </button>
  );
}
