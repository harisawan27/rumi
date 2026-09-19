"use client";

import React, { useState, useRef, useEffect } from "react";
import MobileSheet from "./MobileSheet";

export interface RumiStatusProps {
  observationState: "active" | "paused" | "degraded" | "away";
  identityVerified: boolean;
  guestMode: boolean;
  // Derived camera status string: "observing" | "available" | "paused" | "disabled"
  cameraStatus: string;
  // Derived mic status string: "listening" | "wake_listening" | "available" | "disabled"
  micStatus: string;
  memoryCandidatesCount?: number;
  onToggleCamera: () => void;
  onToggleMic: () => void;
  onOpenMemoryCenter?: () => void;
}

export default function RumiStatusMenu({
  observationState,
  identityVerified,
  guestMode,
  cameraStatus,
  micStatus,
  memoryCandidatesCount = 0,
  onToggleCamera,
  onToggleMic,
  onOpenMemoryCenter,
}: RumiStatusProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 640);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // Close desktop popover on outside click
  useEffect(() => {
    if (!isOpen || isMobile) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, isMobile]);

  // Derived booleans from status strings
  const cameraEnabled = cameraStatus !== "disabled";
  const micEnabled = micStatus !== "disabled";
  const isTalking = micStatus === "listening";
  const wakeListening = micStatus === "wake_listening";
  const isObserving = cameraStatus === "observing";

  // Pill color
  const pillColor = guestMode
    ? "#ef4444"
    : observationState === "active"
    ? "var(--teal)"
    : observationState === "degraded"
    ? "#f97316"
    : "var(--muted)";

  const pillLabel = guestMode
    ? "Guest protected"
    : observationState === "active"
    ? cameraEnabled
      ? "Rumi is observing"
      : "Voice active · Camera off"
    : observationState === "degraded"
    ? "Voice active · Camera unavailable"
    : "Observation paused";

  // Detailed mic status text
  const micStatusText = !micEnabled
    ? "Microphone disabled"
    : isTalking
    ? "Listening now"
    : wakeListening
    ? "Wake-word standby"
    : "Microphone available";

  // Detailed camera status text
  const cameraStatusText = !cameraEnabled
    ? "Camera disabled"
    : isObserving
    ? "Actively observing"
    : cameraStatus === "paused"
    ? "Paused"
    : "Camera available";

  const statusContent = (
    <div className="flex flex-col gap-4 text-sm">
      {/* Identity */}
      <div className="flex items-center justify-between py-1.5 border-b border-[var(--border)]">
        <span className="text-[var(--text-2)] font-medium">Owner Identity</span>
        {guestMode ? (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-[#ef4444] bg-[rgba(239,68,68,0.12)] px-2.5 py-1 rounded-full border border-[rgba(239,68,68,0.4)]">
            <span>🔒</span> Guest Protected
          </span>
        ) : identityVerified ? (
          <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--teal)] bg-[rgba(34,211,238,0.1)] px-2.5 py-1 rounded-full border border-[rgba(34,211,238,0.35)]">
            <span>✓</span> Owner Verified
          </span>
        ) : (
          <span className="text-xs text-muted">Awaiting Face Recognition</span>
        )}
      </div>

      {/* Camera */}
      <div className="flex items-center justify-between py-1.5 border-b border-[var(--border)]">
        <div>
          <span className="block text-[var(--text)] font-medium">Camera</span>
          <span className="block text-xs text-muted mt-0.5">{cameraStatusText}</span>
        </div>
        <button
          onClick={onToggleCamera}
          className="btn-ghost"
          style={{
            fontSize: "0.75rem",
            padding: "0.4rem 0.85rem",
            color: cameraEnabled ? "var(--teal)" : "#ef4444",
            borderColor: cameraEnabled ? "rgba(34,211,238,0.3)" : "rgba(239,68,68,0.3)",
          }}
        >
          {cameraEnabled ? "Turn Off" : "Turn On"}
        </button>
      </div>

      {/* Microphone */}
      <div className="flex items-center justify-between py-1.5 border-b border-[var(--border)]">
        <div>
          <span className="block text-[var(--text)] font-medium">Microphone</span>
          <span className="block text-xs text-muted mt-0.5">{micStatusText}</span>
        </div>
        <button
          onClick={onToggleMic}
          className="btn-ghost"
          style={{
            fontSize: "0.75rem",
            padding: "0.4rem 0.85rem",
            color: micEnabled ? "var(--gold)" : "#ef4444",
            borderColor: micEnabled ? "rgba(201,168,76,0.3)" : "rgba(239,68,68,0.3)",
          }}
        >
          {micEnabled ? "Turn Off" : "Turn On"}
        </button>
      </div>

      {/* Memory candidates badge */}
      {memoryCandidatesCount > 0 && (
        <div className="flex items-center justify-between py-1.5 border-b border-[var(--border)]">
          <div>
            <span className="block text-[var(--text)] font-medium">Memory</span>
            <span className="block text-xs text-muted mt-0.5">
              {memoryCandidatesCount} candidate{memoryCandidatesCount > 1 ? "s" : ""} awaiting review
            </span>
          </div>
          {onOpenMemoryCenter && (
            <button
              onClick={() => { setIsOpen(false); onOpenMemoryCenter(); }}
              className="btn-ghost"
              style={{ fontSize: "0.75rem", padding: "0.4rem 0.85rem", color: "var(--gold)", borderColor: "rgba(201,168,76,0.3)" }}
            >
              Review
            </button>
          )}
        </div>
      )}

      {/* Privacy notice */}
      <p className="text-[0.68rem] text-muted leading-relaxed pt-1">
        Rumi uses a private face-recognition model to recognize familiar people.
        Face embeddings are kept private and are not treated as security-grade authentication.
      </p>
    </div>
  );

  return (
    <div className="relative inline-block" ref={popoverRef}>
      {/* Consolidated Status Pill */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full transition-all duration-200"
        style={{
          background: "var(--surface-2)",
          border: `1px solid ${isOpen ? pillColor : "var(--border)"}`,
          cursor: "pointer",
        }}
        aria-label="Rumi status menu"
        aria-expanded={isOpen}
      >
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{
            backgroundColor: pillColor,
            boxShadow: observationState === "active" ? `0 0 8px ${pillColor}` : "none",
            animation: observationState === "active" ? "statusPulse 2.2s infinite" : "none",
          }}
        />
        <span
          className="text-xs tracking-wider uppercase font-medium select-none hidden sm:inline"
          style={{ fontSize: "0.68rem", letterSpacing: "0.1em", color: pillColor }}
        >
          {pillLabel}
        </span>
        {memoryCandidatesCount > 0 && (
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ background: "var(--gold)", animation: "statusPulse 2s infinite" }}
          />
        )}
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            color: "var(--muted)",
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Desktop Popover */}
      {!isMobile && isOpen && (
        <div
          className="rumi-status-popover animate-fade-up"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
            zIndex: 40,
            width: 320,
            background: "rgba(10, 20, 34, 0.95)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            border: "1px solid var(--border-2)",
            borderRadius: 14,
            padding: "16px 18px",
            boxShadow: "0 12px 36px rgba(0,0,0,0.6)",
          }}
        >
          <div className="flex items-center justify-between pb-3 mb-2 border-b border-[var(--border)]">
            <span className="uppercase-label" style={{ color: "var(--gold)" }}>
              Rumi Status
            </span>
            <button
              onClick={() => setIsOpen(false)}
              className="text-muted hover:text-text text-sm leading-none"
            >
              ✕
            </button>
          </div>
          {statusContent}
        </div>
      )}

      {/* Mobile Sheet */}
      {isMobile && (
        <MobileSheet
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          title="Rumi Status & Privacy"
          subtitle="Realtime sensor and identity state"
        >
          {statusContent}
        </MobileSheet>
      )}
    </div>
  );
}
