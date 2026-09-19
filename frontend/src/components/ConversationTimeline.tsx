"use client";

import React, { useEffect, useState } from "react";
import {
  getConversationHistory,
  type SessionHistoryGroup,
  type TimelineEvent,
} from "@/services/session";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  guestMode?: boolean;
  activeEvents?: TimelineEvent[]; // live events from current active session
  onOpenCanvas?: () => void;
  isMobileView?: boolean;
}

export default function ConversationTimeline({
  isOpen,
  onClose,
  guestMode = false,
  activeEvents = [],
  onOpenCanvas,
  isMobileView = false,
}: Props) {
  const [durableSessions, setDurableSessions] = useState<SessionHistoryGroup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && !guestMode) {
      setLoading(true);
      getConversationHistory(10)
        .then((sessions) => setDurableSessions(sessions))
        .catch(() => setDurableSessions([]))
        .finally(() => setLoading(false));
    }
  }, [isOpen, guestMode]);

  if (!isOpen) return null;

  // Format relative timestamp
  const formatTime = (ts: string) => {
    if (!ts) return "";
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  const renderEvent = (ev: TimelineEvent, idx: number) => {
    if (ev.type === "turn") {
      const isVoice = ev.source === "voice";
      return (
        <div key={idx} className="flex flex-col gap-2 mb-4">
          {/* User Utterance */}
          <div className="flex items-start gap-2.5 max-w-[90%] self-end">
            <div
              className="rounded-2xl px-3.5 py-2.5 text-xs text-[var(--text)] leading-relaxed"
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border-2)",
                borderBottomRightRadius: 4,
              }}
            >
              <div className="flex items-center justify-between gap-3 mb-1 text-[0.6rem] text-muted uppercase tracking-wider">
                <span className="flex items-center gap-1 font-semibold text-[var(--teal)]">
                  {isVoice ? (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
                      <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" />
                    </svg>
                  ) : (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="2" y="4" width="20" height="16" rx="2" />
                    </svg>
                  )}
                  You
                </span>
                <span>{formatTime(ev.timestamp)}</span>
              </div>
              <p className="m-0 select-text">{ev.user_text}</p>
            </div>
          </div>

          {/* Rumi Response */}
          {ev.rumi_response && (
            <div className="flex items-start gap-2.5 max-w-[92%] self-start">
              <div
                className="rounded-2xl px-4 py-3 text-xs leading-relaxed"
                style={{
                  background: "rgba(10, 20, 34, 0.8)",
                  border: "1px solid rgba(201,168,76,0.22)",
                  borderBottomLeftRadius: 4,
                }}
              >
                <div className="flex items-center justify-between gap-3 mb-1 text-[0.6rem] uppercase tracking-wider">
                  <span className="font-display font-semibold text-gold tracking-widest">
                    Rumi
                  </span>
                  <span className="text-muted">{formatTime(ev.timestamp)}</span>
                </div>
                <p className="m-0 text-[var(--text-2)] select-text">{ev.rumi_response}</p>
                {ev.source === "canvas" && onOpenCanvas && (
                  <button
                    onClick={onOpenCanvas}
                    className="btn-ghost mt-2.5 flex items-center gap-1.5"
                    style={{ fontSize: "0.68rem", padding: "0.3rem 0.65rem", borderColor: "rgba(34,211,238,0.3)", color: "var(--teal)" }}
                  >
                    <span>◆</span> View on Canvas
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      );
    }

    if (ev.type === "intervention") {
      return (
        <div
          key={idx}
          className="my-3 p-3.5 rounded-xl text-xs"
          style={{
            background: "rgba(201,168,76,0.07)",
            border: "1px solid rgba(201,168,76,0.25)",
          }}
        >
          <div className="flex items-center justify-between text-[0.62rem] uppercase tracking-wider mb-1.5 text-gold font-semibold">
            <span className="flex items-center gap-1">
              <span>◉</span> Rumi · proactive
            </span>
            <span className="text-muted font-normal">{formatTime(ev.timestamp)}</span>
          </div>
          <p className="m-0 text-[var(--text)] leading-relaxed italic select-text">
            &ldquo;{ev.text}&rdquo;
          </p>
          {ev.user_response && (
            <div className="mt-2 text-[0.65rem] text-muted flex items-center gap-1">
              <span>Response:</span>
              <span className="capitalize text-[var(--text-2)] font-medium">
                {ev.user_response}
              </span>
            </div>
          )}
        </div>
      );
    }

    return null;
  };

  const timelineBody = (
    <div className="flex flex-col h-full">
      {guestMode ? (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <div className="p-3 rounded-full bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.3)] mb-3">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" />
              <path d="M7 11V7a5 5 0 0110 0v4" />
            </svg>
          </div>
          <h4 className="text-sm font-semibold text-[#ef4444] mb-1">Session Protected</h4>
          <p className="text-xs text-muted max-w-xs">
            Conversation history is hidden while Guest Mode is active to protect owner privacy.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-6">
          {/* Current Live Session */}
          {activeEvents.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--teal)] shadow-[0_0_6px_var(--teal)]" />
                <span className="uppercase-label text-[var(--teal)]" style={{ fontSize: "0.62rem" }}>
                  Current Session
                </span>
                <div className="flex-1 h-px bg-[rgba(34,211,238,0.12)]" />
              </div>
              <div className="flex flex-col">{activeEvents.map(renderEvent)}</div>
            </div>
          )}

          {/* Durable Past Sessions */}
          {loading && durableSessions.length === 0 ? (
            <div className="flex justify-center py-8">
              <span
                className="w-5 h-5 rounded-full border-2 border-[var(--gold-dim)] border-t-[var(--gold)] animate-spin"
              />
            </div>
          ) : durableSessions.length === 0 && activeEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-10 h-10 rounded-full flex items-center justify-center bg-[var(--surface-2)] border border-[var(--border)] mb-3 text-muted">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                </svg>
              </div>
              <p className="text-xs text-muted m-0">No past conversations yet.</p>
              <p className="text-[0.68rem] text-muted/70 mt-1">Speak or type to Rumi to begin.</p>
            </div>
          ) : (
            durableSessions.map((session, sIdx) => {
              if (!session.events || session.events.length === 0) return null;
              return (
                <div key={session.session_id || sIdx}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="uppercase-label text-muted" style={{ fontSize: "0.6rem" }}>
                      {session.started_at ? new Date(session.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : `Session ${sIdx + 1}`}
                    </span>
                    <div className="flex-1 h-px bg-[var(--border)]" />
                  </div>
                  <div className="flex flex-col">{session.events.map(renderEvent)}</div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );

  // If rendering inside mobile tab view directly:
  if (isMobileView) {
    return (
      <div className="flex flex-col h-full bg-[var(--bg)] pt-2 pb-16">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <h3 className="font-display text-gold text-lg tracking-wide m-0">Conversation History</h3>
          <span className="text-[0.65rem] text-muted uppercase tracking-widest">Durable Memory</span>
        </div>
        {timelineBody}
      </div>
    );
  }

  // Desktop slide-in side drawer
  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-[rgba(4,8,15,0.6)] backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md h-full bg-[var(--surface)] border-l border-[var(--border)] flex flex-col shadow-2xl animate-fade-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <div>
            <h3 className="font-display text-gold text-lg tracking-wider m-0">Conversation</h3>
            <span className="text-[0.65rem] text-muted uppercase tracking-widest">
              Session & Spoken Timeline
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-text p-2 rounded-lg transition-colors"
            aria-label="Close conversation history"
          >
            ✕
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 min-h-0">{timelineBody}</div>
      </div>
    </div>
  );
}
