"use client";

import React from "react";
import Link from "next/link";

export type MobileTab = "rumi" | "canvas" | "history" | "memory";

interface Props {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
  hasCanvasContent?: boolean;
  unreadIntervention?: boolean;
}

export default function MobileNavigation({
  activeTab,
  onTabChange,
  hasCanvasContent = false,
  unreadIntervention = false,
}: Props) {
  return (
    <nav
      className="mobile-nav-bar sm:hidden"
      aria-label="Mobile Navigation"
    >
      {/* Rumi Tab */}
      <button
        onClick={() => onTabChange("rumi")}
        className={`mobile-nav-btn ${activeTab === "rumi" ? "active" : ""}`}
        aria-label="Rumi Companion"
      >
        <span className="nav-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 14s1.5 2 4 2 4-2 4-2" />
            <line x1="9" y1="9" x2="9.01" y2="9" />
            <line x1="15" y1="9" x2="15.01" y2="9" />
          </svg>
        </span>
        <span className="nav-label">Rumi</span>
      </button>

      {/* Canvas Tab */}
      <button
        onClick={() => onTabChange("canvas")}
        className={`mobile-nav-btn ${activeTab === "canvas" ? "active" : ""}`}
        aria-label="Artifact Canvas"
      >
        <div className="relative inline-block">
          <span className="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
          </span>
          {hasCanvasContent && (
            <span
              className="absolute -top-0.5 -right-1 w-2 h-2 rounded-full bg-[var(--teal)] shadow-[0_0_6px_var(--teal)]"
            />
          )}
        </div>
        <span className="nav-label">Canvas</span>
      </button>

      {/* History Tab */}
      <button
        onClick={() => onTabChange("history")}
        className={`mobile-nav-btn ${activeTab === "history" ? "active" : ""}`}
        aria-label="Conversation History"
      >
        <div className="relative inline-block">
          <span className="nav-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </span>
          {unreadIntervention && (
            <span
              className="absolute -top-0.5 -right-1 w-2 h-2 rounded-full bg-[var(--gold)] shadow-[0_0_6px_var(--gold)]"
            />
          )}
        </div>
        <span className="nav-label">History</span>
      </button>

      {/* Memory Tab (Navigates to /profile) */}
      <Link
        href="/profile"
        className="mobile-nav-btn"
        aria-label="Memory & Privacy Center"
      >
        <span className="nav-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21v-2a4 4 0 00-4-4H9a4 4 0 00-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </span>
        <span className="nav-label">Memory</span>
      </Link>

      <style jsx>{`
        .mobile-nav-bar {
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          z-index: 50;
          height: calc(58px + env(safe-area-inset-bottom, 12px));
          padding-bottom: env(safe-area-inset-bottom, 12px);
          background: rgba(10, 20, 34, 0.92);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border-top: 1px solid var(--border);
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          align-items: center;
        }

        .mobile-nav-btn {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 3px;
          min-height: 48px;
          color: var(--muted);
          background: transparent;
          border: none;
          cursor: pointer;
          transition: color 0.18s ease;
          text-decoration: none;
        }

        .mobile-nav-btn:hover {
          color: var(--text-2);
        }

        .mobile-nav-btn.active {
          color: var(--teal);
        }

        .nav-icon {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .nav-label {
          font-size: 0.65rem;
          font-weight: 500;
          letter-spacing: 0.05em;
          text-transform: capitalize;
        }
      `}</style>
    </nav>
  );
}
