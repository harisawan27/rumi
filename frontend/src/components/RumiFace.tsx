"use client";

import { useEffect, useRef, useState, useMemo } from "react";

export type ObservationState = "active" | "paused" | "degraded";
export type RumiEmotion = "neutral" | "concerned" | "happy" | "thinking";

interface Props {
  state: ObservationState;
  speaking: boolean;
  emotion?: RumiEmotion;
}

// Eye geometry constants
const EL = { cx: 36, cy: 62, rx: 15, ry: 11 }; // left eye
const ER = { cx: 84, cy: 62, rx: 15, ry: 11 }; // right eye

const PALETTE = {
  active:   { primary: "#22d3ee", iris: "#67e8f9", deep: "#0891b2", face: "#060f1c", border: "#22d3ee" },
  paused:   { primary: "#475569", iris: "#94a3b8", deep: "#334155", face: "#080b10", border: "#475569" },
  degraded: { primary: "#f97316", iris: "#fdba74", deep: "#c2410c", face: "#12060000", border: "#f97316" },
  concerned:{ primary: "#fb923c", iris: "#fcd34d", deep: "#d97706", face: "#060f1c", border: "#fb923c" },
  happy:    { primary: "#fbbf24", iris: "#fde68a", deep: "#d97706", face: "#060f1c", border: "#fbbf24" },
  thinking: { primary: "#a78bfa", iris: "#c4b5fd", deep: "#7c3aed", face: "#060c1c", border: "#a78bfa" },
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export default function RumiFace({ state, speaking, emotion = "neutral" }: Props) {
  const [blink, setBlink]           = useState(false);
  const [pupil, setPupil]           = useState({ x: 0, y: 0 });
  const [targetPupil, setTarget]    = useState({ x: 0, y: 0 });
  const [breathScale, setBreath]    = useState(1);
  const breathT                     = useRef(0);
  const lerpFrame                   = useRef<number>(0);

  const isActive   = state === "active";
  const isPaused   = state === "paused";
  const isDegraded = state === "degraded";

  // Resolve effective emotion key for palette
  const emoKey: keyof typeof PALETTE = isDegraded
    ? "degraded"
    : isPaused
    ? "paused"
    : emotion === "concerned"
    ? "concerned"
    : emotion === "happy"
    ? "happy"
    : emotion === "thinking"
    ? "thinking"
    : "active";

  const c = PALETTE[emoKey];

  // ── Blink ────────────────────────────────────────────────────────────────
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const delay = isPaused ? 6000 + Math.random() * 4000 : 2500 + Math.random() * 3000;
      t = setTimeout(() => {
        setBlink(true);
        setTimeout(() => setBlink(false), 110);
        schedule();
      }, delay);
    };
    schedule();
    return () => clearTimeout(t);
  }, [isPaused]);

  // ── Pupil drift (look around) ─────────────────────────────────────────────
  useEffect(() => {
    if (!isActive) {
      setTarget({ x: 0, y: 0 });
      return;
    }
    const interval = setInterval(() => {
      setTarget({
        x: (Math.random() - 0.5) * 6,
        y: (Math.random() - 0.5) * 4,
      });
    }, 1800 + Math.random() * 2200);
    return () => clearInterval(interval);
  }, [isActive]);

  // ── Smooth pupil lerp ─────────────────────────────────────────────────────
  useEffect(() => {
    const animate = () => {
      setPupil(prev => ({
        x: lerp(prev.x, targetPupil.x, 0.07),
        y: lerp(prev.y, targetPupil.y, 0.07),
      }));
      lerpFrame.current = requestAnimationFrame(animate);
    };
    lerpFrame.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(lerpFrame.current);
  }, [targetPupil]);

  // ── Breathing pulse ───────────────────────────────────────────────────────
  useEffect(() => {
    let frame: number;
    const animate = () => {
      breathT.current += 0.008;
      setBreath(1 + Math.sin(breathT.current) * 0.007);
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, []);

  // ── Eye openness ──────────────────────────────────────────────────────────
  // topLidDrop: how many px the upper eyelid droops down into the eye (0=fully open)
  const topLidDrop = blink
    ? EL.ry * 2.2          // fully closed
    : isPaused
    ? EL.ry * 0.52         // half-closed sleepy
    : emotion === "thinking"
    ? EL.ry * 0.15         // slight squint on one side handled below
    : 0;

  // ── Eyebrow configs ───────────────────────────────────────────────────────
  // Each brow is a quadratic bezier: M lx,ly Q mx,my rx,ry
  // Lift = vertical offset (negative = higher)
  const brL = { x1: 22, x2: 48, mid: 35 };
  const brR = { x1: 72, x2: 98, mid: 85 };
  const browY = {
    neutral:   { lL: 45, lM: 42, lR: 45, rL: 45, rM: 42, rR: 45 },
    concerned: { lL: 47, lM: 43, lR: 42, rL: 42, rM: 43, rR: 47 }, // inner corners up = worried V
    happy:     { lL: 42, lM: 39, lR: 42, rL: 42, rM: 39, rR: 42 }, // arched high
    thinking:  { lL: 43, lM: 41, lR: 46, rL: 44, rM: 41, rR: 42 }, // asymmetric
  }[emotion in ["concerned","happy","thinking"] ? emotion : "neutral"] ??
    { lL: 45, lM: 42, lR: 45, rL: 45, rM: 42, rR: 45 };

  // ── Mouth path ────────────────────────────────────────────────────────────
  const mouth =
    isDegraded                   ? "M 44,92 Q 60,87 76,92"  // flat frown
    : speaking                   ? "M 40,90 Q 60,104 80,90" // open happy
    : emotion === "happy"        ? "M 38,90 Q 60,105 82,90" // big smile
    : emotion === "concerned"    ? "M 44,93 Q 60,88 76,93"  // slight frown
    : emotion === "thinking"     ? "M 46,91 Q 60,90 70,87"  // asymmetric
    : isPaused                   ? "M 44,91 Q 60,91 76,91"  // neutral flat
    :                              "M 42,89 Q 60,99 78,89"; // gentle smile

  // ── Render one eye ────────────────────────────────────────────────────────
  const renderEye = (eye: typeof EL, side: "l" | "r") => {
    const clipId  = `ec-${side}`;
    const glowId  = `eg-${side}`;
    const px = eye.cx + pupil.x;
    const py = eye.cy + pupil.y;
    const lidDrop = side === "l" && emotion === "thinking" ? topLidDrop + EL.ry * 0.2 : topLidDrop;
    const lidY    = eye.cy - EL.ry;     // top of eye
    const lidH    = lidDrop + 2;        // how tall the lid rect is

    return (
      <g key={side}>
        <defs>
          <clipPath id={clipId}>
            <ellipse cx={eye.cx} cy={eye.cy} rx={eye.rx + 1} ry={EL.ry + 1} />
          </clipPath>
          <radialGradient id={glowId} cx="38%" cy="32%" r="65%">
            <stop offset="0%" stopColor={c.iris} stopOpacity="0.25" />
            <stop offset="100%" stopColor={c.deep} stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Eye socket — deep dark background */}
        <ellipse cx={eye.cx} cy={eye.cy} rx={eye.rx} ry={EL.ry} fill="#020810" />

        {/* Subtle iris ambient glow inside socket */}
        <ellipse cx={eye.cx} cy={eye.cy} rx={eye.rx} ry={EL.ry} fill={`url(#${glowId})`} />

        {/* Iris outer ring */}
        <circle cx={px} cy={py} r={7.5} fill={c.deep}  clipPath={`url(#${clipId})`} />

        {/* Iris fill */}
        <circle cx={px} cy={py} r={5.8} fill={c.iris}  clipPath={`url(#${clipId})`} />

        {/* Pupil */}
        <circle cx={px} cy={py} r={2.9} fill="#020810" clipPath={`url(#${clipId})`} />

        {/* Primary highlight (bright) */}
        <circle cx={px + 1.8} cy={py - 1.8} r={1.2} fill="white" opacity="0.9" clipPath={`url(#${clipId})`} />

        {/* Secondary small highlight */}
        <circle cx={px - 1.5} cy={py + 1.5} r={0.6} fill="white" opacity="0.4" clipPath={`url(#${clipId})`} />

        {/* Eye rim glow */}
        <ellipse
          cx={eye.cx} cy={eye.cy}
          rx={eye.rx} ry={EL.ry}
          fill="none"
          stroke={c.iris}
          strokeWidth={speaking ? "1.2" : "0.7"}
          opacity={speaking ? 0.9 : 0.45}
          filter="url(#faceGlow)"
        />

        {/* Top eyelid overlay (expression / blink) */}
        {lidH > 0 && (
          <rect
            x={eye.cx - eye.rx - 1}
            y={lidY - 1}
            width={eye.rx * 2 + 2}
            height={lidH + 1}
            fill={c.face}
            clipPath={`url(#${clipId})`}
          />
        )}

        {/* Bottom eyelid — subtle line */}
        <path
          d={`M ${eye.cx - eye.rx + 2},${eye.cy + EL.ry - 1} Q ${eye.cx},${eye.cy + EL.ry + 1} ${eye.cx + eye.rx - 2},${eye.cy + EL.ry - 1}`}
          stroke={c.deep}
          strokeWidth="0.8"
          fill="none"
          opacity="0.5"
        />
      </g>
    );
  };

  return (
    <div className="flex flex-col items-center gap-4 select-none">
      {/* Outer ambient glow ring */}
      <div className="relative">
        {isActive && (
          <div
            className="absolute rounded-full animate-ping opacity-10"
            style={{
              inset: -14,
              backgroundColor: c.primary,
              animationDuration: "2.5s",
            }}
          />
        )}
        {speaking && (
          <div
            className="absolute rounded-full animate-ping opacity-20"
            style={{
              inset: -6,
              backgroundColor: c.iris,
              animationDuration: "1s",
            }}
          />
        )}

        <svg
          width="180"
          height="210"
          viewBox="0 0 120 140"
          xmlns="http://www.w3.org/2000/svg"
          style={{ transform: `scale(${breathScale})`, transition: "transform 0.1s ease" }}
        >
          <defs>
            {/* Soft glow filter */}
            <filter id="faceGlow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="strongGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            {/* Face gradient */}
            <radialGradient id="faceGrad" cx="50%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#0d1f35" />
              <stop offset="100%" stopColor={c.face} />
            </radialGradient>
            {/* Antenna gradient */}
            <radialGradient id="antennaGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={c.iris} />
              <stop offset="100%" stopColor={c.primary} stopOpacity="0.6" />
            </radialGradient>
          </defs>

          {/* ── Antenna ── */}
          <line x1="60" y1="9" x2="60" y2="20" stroke={c.primary} strokeWidth="2.2" strokeLinecap="round" opacity="0.8" />
          <circle cx="60" cy="6.5" r="4.5" fill="url(#antennaGlow)" filter="url(#strongGlow)">
            {isActive && (
              <animate attributeName="opacity" values="0.7;1;0.7" dur="2s" repeatCount="indefinite" />
            )}
          </circle>
          {/* Antenna side ears */}
          <line x1="52" y1="14" x2="46" y2="11" stroke={c.primary} strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
          <line x1="68" y1="14" x2="74" y2="11" stroke={c.primary} strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />

          {/* ── Head ── */}
          <rect
            x="8" y="18" width="104" height="88"
            rx="26"
            fill="url(#faceGrad)"
            stroke={c.border}
            strokeWidth="1.2"
            opacity={isPaused ? 0.75 : 1}
            filter="url(#faceGlow)"
          />

          {/* Head inner detail — subtle circuit lines (decorative) */}
          <line x1="8" y1="40" x2="20" y2="40" stroke={c.deep} strokeWidth="0.5" opacity="0.3" />
          <line x1="100" y1="40" x2="112" y2="40" stroke={c.deep} strokeWidth="0.5" opacity="0.3" />
          <line x1="8" y1="75" x2="18" y2="75" stroke={c.deep} strokeWidth="0.5" opacity="0.2" />
          <line x1="102" y1="75" x2="112" y2="75" stroke={c.deep} strokeWidth="0.5" opacity="0.2" />

          {/* ── Eyebrows ── */}
          {!isDegraded && (
            <>
              <path
                d={`M ${brL.x1},${browY.lL} Q ${brL.mid},${browY.lM} ${brL.x2},${browY.lR}`}
                stroke={c.iris}
                strokeWidth="1.8"
                fill="none"
                strokeLinecap="round"
                opacity="0.75"
                style={{ transition: "d 0.3s ease" }}
              />
              <path
                d={`M ${brR.x1},${browY.rL} Q ${brR.mid},${browY.rM} ${brR.x2},${browY.rR}`}
                stroke={c.iris}
                strokeWidth="1.8"
                fill="none"
                strokeLinecap="round"
                opacity="0.75"
              />
            </>
          )}

          {/* ── Eyes ── */}
          {isDegraded ? (
            <>
              {/* Error X eyes */}
              {[EL, ER].map((eye, i) => (
                <g key={i}>
                  <ellipse cx={eye.cx} cy={eye.cy} rx={eye.rx} ry={EL.ry} fill="#120400" />
                  <line x1={eye.cx-8} y1={eye.cy-6} x2={eye.cx+8} y2={eye.cy+6} stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
                  <line x1={eye.cx+8} y1={eye.cy-6} x2={eye.cx-8} y2={eye.cy+6} stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
                </g>
              ))}
            </>
          ) : (
            <>
              {renderEye(EL, "l")}
              {renderEye(ER, "r")}
            </>
          )}

          {/* ── Nose (subtle) ── */}
          {!isDegraded && (
            <circle cx="60" cy="77" r="1.2" fill={c.deep} opacity="0.6" />
          )}

          {/* ── Mouth ── */}
          <path
            d={mouth}
            stroke={speaking ? c.iris : c.primary}
            strokeWidth={speaking ? "2.2" : "1.8"}
            fill="none"
            strokeLinecap="round"
            opacity={speaking ? 1 : 0.85}
            filter={speaking ? "url(#faceGlow)" : undefined}
          />

          {/* ── Speaking sound waves ── */}
          {speaking && (
            <g>
              {[-12, -6, 0, 6, 12].map((offset, i) => (
                <rect
                  key={i}
                  x={60 + offset - 1}
                  y={100}
                  width="2"
                  height="5"
                  rx="1"
                  fill={c.iris}
                  opacity="0.7"
                >
                  <animate
                    attributeName="height"
                    values={`2;${4 + Math.random() * 6};2`}
                    dur={`${0.3 + i * 0.07}s`}
                    begin={`${i * 0.06}s`}
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="y"
                    values={`103;${101 - Math.random() * 3};103`}
                    dur={`${0.3 + i * 0.07}s`}
                    begin={`${i * 0.06}s`}
                    repeatCount="indefinite"
                  />
                </rect>
              ))}
            </g>
          )}

          {/* Happy cheek blush */}
          {emotion === "happy" && !blink && (
            <>
              <ellipse cx="22" cy="72" rx="8" ry="5" fill="#fbbf24" opacity="0.12" />
              <ellipse cx="98" cy="72" rx="8" ry="5" fill="#fbbf24" opacity="0.12" />
            </>
          )}

          {/* ── Neck ── */}
          <rect x="46" y="105" width="28" height="10" rx="5" fill="#0d1525" />
          <line x1="52" y1="105" x2="52" y2="115" stroke={c.deep} strokeWidth="0.6" opacity="0.4" />
          <line x1="68" y1="105" x2="68" y2="115" stroke={c.deep} strokeWidth="0.6" opacity="0.4" />

          {/* ── Body ── */}
          <rect x="30" y="113" width="60" height="24" rx="10" fill="#0d1525" stroke={c.border} strokeWidth="0.8" strokeOpacity="0.4" />
          {/* Chest light */}
          <circle cx="60" cy="124" r="5.5" fill={c.primary} opacity={speaking ? 0.8 : 0.5} filter="url(#strongGlow)">
            {speaking && (
              <animate attributeName="opacity" values="0.4;0.9;0.4" dur="0.8s" repeatCount="indefinite" />
            )}
          </circle>
          {/* Body detail dots */}
          <circle cx="42" cy="124" r="2" fill={c.deep} opacity="0.5" />
          <circle cx="78" cy="124" r="2" fill={c.deep} opacity="0.5" />
        </svg>
      </div>

      {/* Status label */}
      <div className="flex flex-col items-center gap-1">
        <p
          className="text-xs font-semibold tracking-widest uppercase"
          style={{ color: c.primary, letterSpacing: "0.2em" }}
        >
          {isDegraded
            ? "Unavailable"
            : isPaused
            ? "Resting"
            : speaking
            ? "Speaking"
            : emotion === "thinking"
            ? "Thinking…"
            : emotion === "concerned"
            ? "Concerned"
            : emotion === "happy"
            ? "Greeting"
            : "Observing"}
        </p>
        {/* Subtle pulse indicator */}
        {isActive && !speaking && (
          <div className="flex gap-1">
            {[0, 1, 2].map(i => (
              <div
                key={i}
                className="rounded-full"
                style={{
                  width: 4, height: 4,
                  backgroundColor: c.primary,
                  opacity: 0.5,
                  animation: `pulse 1.4s ease-in-out ${i * 0.2}s infinite`,
                }}
              />
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 0.3; }
          50%       { transform: scale(1.4); opacity: 0.8; }
        }
      `}</style>
    </div>
  );
}
