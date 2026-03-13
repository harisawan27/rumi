"use client";

import { useRef, useEffect, useState } from "react";

export type ObservationState = "active" | "paused" | "degraded";
export type RumiEmotion = "neutral" | "concerned" | "happy" | "thinking";

interface Props {
  state: ObservationState;
  speaking: boolean;
  emotion?: RumiEmotion;
}

const IMG_W  = 220;
const IMG_H  = 416;
const PAD    = 32;
const WRAP_W = IMG_W + PAD * 2;
const WRAP_H = IMG_H + PAD * 2;

// ── Face feature positions in IMAGE coordinate space (0 0 220 416) ──────────
// Measured from actual pixel data: visor x=68–158, y=24–91
// The overlay SVG sits directly on the image with viewBox="0 0 220 416",
// so these coords scale perfectly regardless of rendered size.
const EYE_L  = { x: 98,  y: 57 };
const EYE_R  = { x: 130, y: 57 };
const EYE_RX = 7;
const EYE_RY = 4.5;
const MX     = 113;
const MY     = 70;

export default function RumiFace({ state, speaking, emotion = "neutral" }: Props) {
  const [blinkOpen, setBlinkOpen] = useState(true);

  const isActive   = state === "active";
  const isPaused   = state === "paused";
  const isDegraded = state === "degraded";

  const acc =
    isDegraded              ? "#f97316" :
    isPaused                ? "#64748b" :
    emotion === "concerned" ? "#fb923c" :
    emotion === "happy"     ? "#fbbf24" :
    emotion === "thinking"  ? "#a78bfa" :
    "#00e87a";

  const animState = isPaused ? "paused" : "running";

  // Random blink every 3–6 s
  useEffect(() => {
    if (isPaused) return;
    const schedule = () => {
      const delay = 3000 + Math.random() * 3000;
      return setTimeout(() => {
        setBlinkOpen(false);
        setTimeout(() => {
          setBlinkOpen(true);
          timerRef.current = schedule();
        }, 120);
      }, delay);
    };
    const timerRef = { current: schedule() };
    return () => clearTimeout(timerRef.current);
  }, [isPaused]);

  const glow = [
    `drop-shadow(0 0  6px ${acc}cc)`,
    `drop-shadow(0 0 14px ${acc}99)`,
    `drop-shadow(0 0 28px ${acc}55)`,
  ].join(" ");

  // ── Eye shape per emotion ───────────────────────────────────────────────
  const eyeRY = (() => {
    if (!blinkOpen)              return 0.5;
    if (emotion === "happy")     return EYE_RY * 0.5;   // squinting happy
    if (emotion === "concerned") return EYE_RY * 1.1;   // wide open
    if (emotion === "thinking")  return EYE_RY * 0.7;   // narrowed
    return EYE_RY;
  })();

  // Upper eyelid offset (drops down when thinking/squinting)
  const lidOffset = (() => {
    if (emotion === "thinking") return EYE_RY * 0.45;
    if (emotion === "happy")    return EYE_RY * 0.3;
    return 0;
  })();

  const renderEye = (cx: number, cy: number) => (
    <g key={cx}>
      {/* Glow base */}
      <ellipse cx={cx} cy={cy} rx={EYE_RX} ry={Math.max(eyeRY, 0.5)}
        fill={acc} opacity="0.25" />
      {/* Main eye */}
      <ellipse cx={cx} cy={cy} rx={EYE_RX - 1} ry={Math.max(eyeRY - 0.5, 0.5)}
        fill={acc} opacity="0.9" />
      {/* Pupil glint */}
      {blinkOpen && eyeRY > 2 && (
        <ellipse cx={cx - 3} cy={cy - 2} rx={3} ry={2}
          fill="white" opacity="0.45" />
      )}
      {/* Upper eyelid (drops for thinking/happy) */}
      {lidOffset > 0 && (
        <rect
          x={cx - EYE_RX} y={cy - EYE_RY - 1}
          width={EYE_RX * 2} height={lidOffset + 1}
          fill="#1a2235"
        />
      )}
    </g>
  );

  // ── Mouth shape per state ───────────────────────────────────────────────
  const mouthEl = (() => {
    if (speaking) return (
      <>{[0,1,2,3,4].map(i => (
        <rect key={i} x={MX - 13 + i * 6.5} y={MY} width="5" height="7" rx="2.5" fill={acc}>
          <animate attributeName="height" values="3;12;3"
            dur={`${0.22 + i * 0.06}s`} begin={`${i * 0.05}s`} repeatCount="indefinite"/>
          <animate attributeName="y"
            values={`${MY + 2};${MY - 3};${MY + 2}`}
            dur={`${0.22 + i * 0.06}s`} begin={`${i * 0.05}s`} repeatCount="indefinite"/>
        </rect>
      ))}</>
    );
    if (emotion === "happy") return (
      <path d={`M${MX-11},${MY} Q${MX},${MY+10} ${MX+11},${MY}`}
        fill="none" stroke={acc} strokeWidth="2.5" strokeLinecap="round"/>
    );
    if (emotion === "concerned") return (
      <path d={`M${MX-11},${MY+8} Q${MX},${MY-2} ${MX+11},${MY+8}`}
        fill="none" stroke={acc} strokeWidth="2.5" strokeLinecap="round"/>
    );
    if (emotion === "thinking") return (
      <>{[0,1,2].map(i => (
        <circle key={i} cx={MX - 3 + i * 6} cy={MY + 3} r="2.2" fill={acc}>
          <animate attributeName="opacity" values="0.2;1;0.2"
            dur="1s" begin={`${i * 0.3}s`} repeatCount="indefinite"/>
        </circle>
      ))}</>
    );
    // Neutral
    return (<>
      <line x1={MX-9} y1={MY+3} x2={MX+9} y2={MY+3}
        stroke={acc} strokeWidth="2.5" strokeLinecap="round" opacity="0.85"/>
      {isActive && (
        <line x1={MX-9} y1={MY+3} x2={MX+9} y2={MY+3}
          stroke="white" strokeWidth="1" strokeLinecap="round" opacity="0.4" strokeDasharray="4 12">
          <animate attributeName="stroke-dashoffset" values="16;0" dur="1.8s" repeatCount="indefinite"/>
        </line>
      )}
    </>);
  })();

  return (
    <div style={{
      position: "relative",
      display: "inline-block",
      width: WRAP_W,
      height: WRAP_H,
      animation: "rumiFloat 5s ease-in-out infinite",
      animationPlayState: animState,
      userSelect: "none",
      flexShrink: 0,
    }}>
      {/* ── Robot image ─────────────────────────────────────────────────── */}
      <img
        src="/rumi.svg"
        alt="Rumi"
        draggable={false}
        style={{
          position: "absolute",
          top: PAD, left: PAD,
          width: IMG_W, height: IMG_H,
          objectFit: "fill",
          pointerEvents: "none",
          userSelect: "none",
          filter: glow,
        }}
      />

      {/* ── Face overlay: eyes + mouth — sits exactly on the image ─────── */}
      <svg
        style={{
          position: "absolute",
          top: PAD, left: PAD,          // same offset as the <img>
          width: IMG_W, height: IMG_H,  // same size as the <img>
          pointerEvents: "none",
          overflow: "visible",
        }}
        viewBox={`0 0 ${IMG_W} ${IMG_H}`}
      >
        <defs>
          <filter id="faceGlow" x="-150%" y="-150%" width="400%" height="400%">
            <feGaussianBlur stdDeviation="3" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        <g filter="url(#faceGlow)">
          {/* Eyes */}
          {renderEye(EYE_L.x, EYE_L.y)}
          {renderEye(EYE_R.x, EYE_R.y)}
          {/* Mouth */}
          {mouthEl}
        </g>
      </svg>

      <style>{`
        @keyframes rumiFloat {
          0%   { transform: translateY(0px)   rotate(0deg)    translateX(0px);  }
          18%  { transform: translateY(-6px)  rotate(-0.7deg) translateX(-2px); }
          42%  { transform: translateY(-11px) rotate(-0.2deg) translateX(1px);  }
          68%  { transform: translateY(5px)   rotate(0.6deg)  translateX(2px);  }
          86%  { transform: translateY(9px)   rotate(0.3deg)  translateX(-1px); }
          100% { transform: translateY(0px)   rotate(0deg)    translateX(0px);  }
        }
      `}</style>
    </div>
  );
}
