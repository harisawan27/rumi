"use client";

import { useRef, useState, useEffect } from "react";

interface CameraPreviewProps {
  stream: MediaStream | null;
  cameraEnabled: boolean;
  micEnabled: boolean;
  observationState: string;
  onCameraToggle: () => void;
  onMicToggle: () => void;
}

export default function CameraPreview({
  stream,
  cameraEnabled,
  micEnabled,
  observationState,
  onCameraToggle,
  onMicToggle,
}: CameraPreviewProps) {
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const [pos, setPos] = useState({ x: 16, y: 16 });
  const [ready, setReady] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const dragRef = useRef({ active: false, startX: 0, startY: 0, ox: 0, oy: 0 });

  const W = typeof window !== "undefined" && window.innerWidth < 640 ? 96 : 160;
  const H = typeof window !== "undefined" && window.innerWidth < 640 ? 72 : 120;

  // Position on mount
  useEffect(() => {
    setPos({ x: window.innerWidth - W - 16, y: window.innerHeight - H - 88 });
    setReady(true);
  }, [W, H]);

  // Attach stream to local video element
  useEffect(() => {
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = stream ?? null;
      if (stream) localVideoRef.current.play().catch(() => {});
    }
  }, [stream]);

  // ── Drag ───────────────────────────────────────────────────────────────────
  const startDrag = (clientX: number, clientY: number) => {
    dragRef.current = { active: true, startX: clientX, startY: clientY, ox: pos.x, oy: pos.y };
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current.active) return;
      setPos({
        x: Math.max(0, Math.min(window.innerWidth - W, dragRef.current.ox + e.clientX - dragRef.current.startX)),
        y: Math.max(0, Math.min(window.innerHeight - H, dragRef.current.oy + e.clientY - dragRef.current.startY)),
      });
    };
    const onTouchMove = (e: TouchEvent) => {
      if (!dragRef.current.active) return;
      setPos({
        x: Math.max(0, Math.min(window.innerWidth - W, dragRef.current.ox + e.touches[0].clientX - dragRef.current.startX)),
        y: Math.max(0, Math.min(window.innerHeight - H, dragRef.current.oy + e.touches[0].clientY - dragRef.current.startY)),
      });
    };
    const onEnd = () => { dragRef.current.active = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onEnd);
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    window.addEventListener("touchend", onEnd);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onEnd);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onEnd);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [W, H]);

  const active = observationState === "active";

  return (
    <div
      onMouseDown={(e) => { e.preventDefault(); startDrag(e.clientX, e.clientY); }}
      onTouchStart={(e) => startDrag(e.touches[0].clientX, e.touches[0].clientY)}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
      style={{
        position: "fixed",
        left: pos.x,
        top: pos.y,
        width: W,
        height: H,
        borderRadius: 10,
        border: `1.5px solid ${active ? "var(--teal)" : "var(--border)"}`,
        overflow: "hidden",
        cursor: "grab",
        zIndex: 50,
        background: "var(--surface)",
        boxShadow: active ? "0 0 14px rgba(34,211,238,0.3)" : "0 4px 20px rgba(0,0,0,0.5)",
        userSelect: "none",
        touchAction: "none",
        visibility: ready ? "visible" : "hidden",
        transition: "border-color 0.3s, box-shadow 0.3s",
      }}
    >
      {/* Live video */}
      <video
        ref={localVideoRef}
        autoPlay
        muted
        playsInline
        style={{
          width: "100%", height: "100%",
          objectFit: "cover", display: "block",
          opacity: cameraEnabled ? 1 : 0,
          transform: "scaleX(-1)", // mirror so it feels like a selfie view
        }}
      />

      {/* Camera-off placeholder */}
      {!cameraEnabled && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 4,
          background: "var(--surface-2)",
        }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="var(--muted)">
            <path d="M18 10.5V6a2 2 0 00-2-2H4a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-4.5l4 4v-11l-4 4z" opacity="0.4" />
            <line x1="2" y1="2" x2="22" y2="22" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span style={{ fontSize: "0.6rem", color: "var(--muted)", letterSpacing: "0.08em" }}>CAM OFF</span>
        </div>
      )}

      {/* Active indicator */}
      {active && cameraEnabled && (
        <div style={{
          position: "absolute", top: 6, left: 6,
          width: 6, height: 6, borderRadius: "50%",
          background: "var(--teal)",
          boxShadow: "0 0 6px rgba(34,211,238,0.8)",
          animation: "statusPulse 2s ease-in-out infinite",
        }} />
      )}

      {/* Controls — on hover or when disabled */}
      {(showControls || !cameraEnabled || !micEnabled) && (
        <div
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: "absolute", bottom: 0, left: 0, right: 0,
            display: "flex", justifyContent: "center", gap: 8, padding: "5px 0",
            background: "rgba(4,8,15,0.72)", backdropFilter: "blur(6px)",
          }}
        >
          <ControlBtn active={cameraEnabled} onClick={onCameraToggle} title={cameraEnabled ? "Camera off" : "Camera on"} color="teal">
            {cameraEnabled ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18 10.5V6a2 2 0 00-2-2H4a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-4.5l4 4v-11l-4 4z" />
              </svg>
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18 10.5V6a2 2 0 00-2-2H4a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-4.5l4 4v-11l-4 4z" opacity="0.4" />
                <line x1="2" y1="2" x2="22" y2="22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            )}
          </ControlBtn>

          <ControlBtn active={micEnabled} onClick={onMicToggle} title={micEnabled ? "Mute mic" : "Unmute mic"} color="gold">
            {micEnabled ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
                <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" />
              </svg>
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" opacity="0.35" />
                <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" opacity="0.35" />
                <line x1="2" y1="2" x2="22" y2="22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            )}
          </ControlBtn>
        </div>
      )}
    </div>
  );
}

function ControlBtn({ active, onClick, title, color, children }: {
  active: boolean; onClick: () => void; title: string; color: "teal" | "gold"; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 28, height: 28, borderRadius: "50%", border: "none", cursor: "pointer",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: active
          ? color === "teal" ? "rgba(34,211,238,0.15)" : "rgba(201,168,76,0.15)"
          : "rgba(239,68,68,0.2)",
        color: active
          ? color === "teal" ? "var(--teal)" : "var(--gold)"
          : "#ef4444",
      }}
    >
      {children}
    </button>
  );
}
