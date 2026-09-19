"use client";

import React, { useEffect } from "react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  subtitle?: string;
}

export default function MobileSheet({ isOpen, onClose, title, subtitle, children }: Props) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="mobile-sheet-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="mobile-sheet-content"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2 cursor-pointer" onClick={onClose}>
          <div
            style={{
              width: 36,
              height: 4,
              borderRadius: 2,
              backgroundColor: "var(--border-2)",
            }}
          />
        </div>

        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <div>
            <h3
              className="text-sm font-semibold tracking-wider uppercase text-gold"
              style={{ fontSize: "0.8125rem", letterSpacing: "0.12em" }}
            >
              {title}
            </h3>
            {subtitle && (
              <p className="text-xs text-muted mt-0.5" style={{ fontSize: "0.7rem" }}>
                {subtitle}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex items-center justify-center text-muted hover:text-text"
            style={{
              width: 44,
              height: 44,
              borderRadius: 8,
              fontSize: "1.1rem",
              background: "transparent",
              border: "none",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div
          className="p-5 overflow-y-auto"
          style={{
            maxHeight: "calc(85vh - 75px)",
            paddingBottom: "max(24px, env(safe-area-inset-bottom, 24px))",
          }}
        >
          {children}
        </div>
      </div>

      <style jsx>{`
        .mobile-sheet-overlay {
          position: fixed;
          inset: 0;
          z-index: 100;
          background: rgba(4, 8, 15, 0.75);
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          display: flex;
          align-items: flex-end;
          justify-content: center;
          animation: fadeIn 0.2s ease-out both;
        }

        .mobile-sheet-content {
          width: 100%;
          max-width: 520px;
          background: var(--surface);
          border-top: 1px solid var(--border);
          border-left: 1px solid var(--border);
          border-right: 1px solid var(--border);
          border-top-left-radius: 20px;
          border-top-right-radius: 20px;
          box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.7);
          animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
