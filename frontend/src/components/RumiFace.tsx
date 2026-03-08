"use client";

import { useEffect, useRef } from "react";

export type ObservationState = "active" | "paused" | "degraded";
export type RumiEmotion = "neutral" | "concerned" | "happy" | "thinking";

interface Props {
  state: ObservationState;
  speaking: boolean;
  emotion?: RumiEmotion;
}

// ── Layout ────────────────────────────────────────────────────────────────────
const IMG_W  = 220;
const IMG_H  = 416;
const PAD    = 32;   // padding around image so drop-shadow has room to render
const WRAP_W = IMG_W + PAD * 2;
const WRAP_H = IMG_H + PAD * 2;

// Mouth position (calibrated on rumi.png, relative to image top-left)
const MOUTH_CX = 110;
const MOUTH_Y  = 76;

export default function RumiFace({ state, speaking, emotion = "neutral" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  const isActive   = state === "active";
  const isPaused   = state === "paused";
  const isDegraded = state === "degraded";

  const accentColor =
    isDegraded              ? "#f97316" :
    isPaused                ? "#64748b" :
    emotion === "concerned" ? "#fb923c" :
    emotion === "happy"     ? "#fbbf24" :
    emotion === "thinking"  ? "#a78bfa" :
    "#00e87a";

  // Mouth element
  const cx = MOUTH_CX + PAD;
  const my = MOUTH_Y  + PAD;

  const mouthEl = (() => {
    if (speaking) {
      return <>{[0, 1, 2, 3, 4].map(i => (
        <rect key={i} x={cx - 13 + i * 6.5} y={my} width="5" height="7" rx="2.5"
          fill={accentColor}>
          <animate attributeName="height" values="3;12;3"
            dur={`${0.22 + i * 0.06}s`} begin={`${i * 0.05}s`} repeatCount="indefinite" />
          <animate attributeName="y"
            values={`${my + 2};${my - 3};${my + 2}`}
            dur={`${0.22 + i * 0.06}s`} begin={`${i * 0.05}s`} repeatCount="indefinite" />
        </rect>
      ))}</>;
    }
    if (emotion === "happy") {
      return <path d={`M${cx-11},${my} Q${cx},${my+11} ${cx+11},${my}`}
        fill="none" stroke={accentColor} strokeWidth="3" strokeLinecap="round" />;
    }
    if (emotion === "concerned") {
      return <path d={`M${cx-11},${my+8} Q${cx},${my-3} ${cx+11},${my+8}`}
        fill="none" stroke={accentColor} strokeWidth="3" strokeLinecap="round" />;
    }
    if (emotion === "thinking") {
      return <>
        <path d={`M${cx-4},${my+4} Q${cx+4},${my+1} ${cx+10},${my+5}`}
          fill="none" stroke={accentColor} strokeWidth="2.5" strokeLinecap="round" />
        {[0, 1, 2].map(i => (
          <circle key={i} cx={cx - 9 + i * 9} cy={my - 7} r="2" fill={accentColor}>
            <animate attributeName="opacity" values="0.2;1;0.2"
              dur="1s" begin={`${i * 0.3}s`} repeatCount="indefinite" />
          </circle>
        ))}
      </>;
    }
    return <>
      <line x1={cx - 9} y1={my + 4} x2={cx + 9} y2={my + 4}
        stroke={accentColor} strokeWidth="2.5" strokeLinecap="round" opacity="0.8" />
      {isActive && (
        <line x1={cx - 9} y1={my + 4} x2={cx + 9} y2={my + 4}
          stroke="white" strokeWidth="1" strokeLinecap="round" opacity="0.5"
          strokeDasharray="5 13">
          <animate attributeName="stroke-dashoffset" values="18;0"
            dur="1.8s" repeatCount="indefinite" />
        </line>
      )}
    </>;
  })();

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        display: "inline-block",
        width:  WRAP_W,
        height: WRAP_H,
        animation: "rumiBodyFloat 5s ease-in-out infinite",
        userSelect: "none",
        flexShrink: 0,
      }}
    >
      {/* Robot image — drop-shadow traces the transparent PNG silhouette */}
      <img
        src="/rumi.png"
        alt="Rumi"
        draggable={false}
        style={{
          position: "absolute",
          top:  PAD,
          left: PAD,
          width:  IMG_W,
          height: IMG_H,
          objectFit: "fill",
          display: "block",
          userSelect: "none",
          pointerEvents: "none",
          filter: [
            `drop-shadow(0 0  6px ${accentColor}cc)`,
            `drop-shadow(0 0 14px ${accentColor}99)`,
            `drop-shadow(0 0 28px ${accentColor}55)`,
          ].join(" "),
        }}
      />

      {/* SVG mouth overlay */}
      <svg
        style={{
          position: "absolute", top: 0, left: 0,
          width: "100%", height: "100%",
          pointerEvents: "none",
          overflow: "visible",
        }}
        viewBox={`0 0 ${WRAP_W} ${WRAP_H}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <filter id="mGlow" x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <g filter="url(#mGlow)">{mouthEl}</g>
      </svg>

      <style>{`
        @keyframes rumiBodyFloat {
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
