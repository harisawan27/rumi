"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  verifyAuth,
  getIdentity,
  startSession,
  endSession,
  connectObserveSocket,
  sendInterventionResponse,
  type InterventionMessage,
  type WsMessage,
} from "@/services/session";
import { ObservationState } from "@/components/ObservationIndicator";
import RumiFace from "@/components/RumiFace";
import InterventionCard from "@/components/InterventionCard";
import PauseButton from "@/components/PauseButton";

interface ActiveIntervention {
  interactionId: string;
  trigger: "A" | "B" | "C" | "E";
  text: string;
}

// Convert Float32 PCM samples to Int16 PCM bytes
function float32ToInt16(float32: Float32Array): ArrayBuffer {
  const buf = new ArrayBuffer(float32.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

export default function DashboardPage() {
  const router = useRouter();
  const [name, setName] = useState<string | null>(null);
  const [observationState, setObservationState] = useState<ObservationState>("paused");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [interventionQueue, setInterventionQueue] = useState<ActiveIntervention[]>([]);
  const intervention = interventionQueue[0] ?? null;
  const [speaking, setSpeaking] = useState(false);
  const [isTalking, setIsTalking] = useState(false);
  const [rumiEmotion, setRumiEmotion] = useState<"neutral" | "concerned" | "happy" | "thinking">("neutral");
  const [error, setError] = useState<string | null>(null);
  const [memoryToast, setMemoryToast] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const isTalkingRef = useRef<boolean>(false);
  const sessionIdRef = useRef<string | null>(null);
  const shouldReconnectRef = useRef<boolean>(true);
  const prevSpeakingRef = useRef<boolean>(false);

  useEffect(() => {
    let scriptProcessor: ScriptProcessorNode | null = null;
    let micSource: MediaStreamAudioSourceNode | null = null;
    let videoStream: MediaStream | null = null;
    let micStream: MediaStream | null = null;
    let ws: WebSocket | null = null;

    async function init() {
      try {
        await verifyAuth();
        const identity = await getIdentity();
        if (!identity) { router.push("/onboarding"); return; }
        setName(identity.name as string);

        const sid = await startSession();
        setSessionId(sid);

        // Start webcam
        try {
          videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
          if (videoRef.current) videoRef.current.srcObject = videoStream;
          setObservationState("active");
          setRumiEmotion("happy"); // reset to neutral when Rumi actually finishes speaking
        } catch {
          setObservationState("degraded");
        }

        // Start mic
        try {
          micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const audioCtx = new AudioContext({ sampleRate: 16000 });
          audioCtxRef.current = audioCtx;
          micSource = audioCtx.createMediaStreamSource(micStream);
          // eslint-disable-next-line @typescript-eslint/no-deprecated
          scriptProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
          scriptProcessor.onaudioprocess = (e) => {
            if (wsRef.current?.readyState !== WebSocket.OPEN) return;
            if (!isTalkingRef.current) return;
            const float32 = e.inputBuffer.getChannelData(0);
            const energy = float32.reduce((s, v) => s + v * v, 0) / float32.length;
            if (energy < 0.00001) return;
            const int16buf = float32ToInt16(float32);
            const bytes = new Uint8Array(int16buf);
            let binary = "";
            for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
            wsRef.current?.send(JSON.stringify({ type: "audio", data: btoa(binary) }));
          };
          micSource.connect(scriptProcessor);
          scriptProcessor.connect(audioCtx.destination);
        } catch {
          console.warn("Mic unavailable — audio input disabled");
        }

        const canvas = document.createElement("canvas");
        const canvasCtx = canvas.getContext("2d");

        const captureFrame = (): Promise<string | null> =>
          new Promise((resolve) => {
            if (!videoRef.current || !canvasCtx) return resolve(null);
            canvas.width = videoRef.current.videoWidth || 640;
            canvas.height = videoRef.current.videoHeight || 480;
            canvasCtx.drawImage(videoRef.current, 0, 0);
            canvas.toBlob((blob) => {
              if (!blob) return resolve(null);
              blob.arrayBuffer().then((buf) => {
                const bytes = new Uint8Array(buf);
                let binary = "";
                for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
                resolve(btoa(binary));
              });
            }, "image/jpeg", 0.7);
          });

        async function connectWs(sid: string) {
          const newWs = await connectObserveSocket(sid, async (msg) => {
            if (msg.type === "request_frame") {
              const b64 = await captureFrame();
              const current = wsRef.current;
              if (b64 && current?.readyState === WebSocket.OPEN) {
                current.send(JSON.stringify({ type: "frame", data: b64 }));
              }
              return;
            }
            handleWsMessage(msg);
          });
          wsRef.current = newWs;

          newWs.addEventListener("close", () => {
            if (!shouldReconnectRef.current) return;
            console.warn("WS closed — reconnecting in 3s…");
            setTimeout(() => {
              if (shouldReconnectRef.current && sessionIdRef.current) {
                connectWs(sessionIdRef.current);
              }
            }, 3000);
          });
        }

        sessionIdRef.current = sid;
        await connectWs(sid);
        ws = wsRef.current;

      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Session error";
        if (msg.includes("UNAUTHORISED") || msg.includes("Auth")) {
          router.push("/");
        } else {
          setError(msg);
        }
      }
    }

    init();

    return () => {
      shouldReconnectRef.current = false;
      wsRef.current?.close();
      scriptProcessor?.disconnect();
      micSource?.disconnect();
      videoStream?.getTracks().forEach((t) => t.stop());
      micStream?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close();
      playCtxRef.current?.close();
      playCtxRef.current = null;
    };
  }, [router]);

  // Reset emotion to neutral when Rumi finishes speaking — not on a timer
  useEffect(() => {
    if (prevSpeakingRef.current && !speaking) {
      setRumiEmotion("neutral");
    }
    prevSpeakingRef.current = speaking;
  }, [speaking]);

  useEffect(() => {
    const handleUnload = () => { if (sessionId) endSession(sessionId); };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [sessionId]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat) return;
      e.preventDefault();
      toggleTalking();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function toggleTalking() {
    const next = !isTalkingRef.current;
    isTalkingRef.current = next;
    setIsTalking(next);
    setRumiEmotion(next ? "thinking" : "neutral");
  }

  async function playAudio(b64: string) {
    try {
      if (!playCtxRef.current) {
        playCtxRef.current = new AudioContext({ sampleRate: 24000 });
      }
      const ctx = playCtxRef.current;
      if (ctx.state === "suspended") await ctx.resume();

      const raw = atob(b64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const int16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;

      const buffer = ctx.createBuffer(1, float32.length, 24000);
      buffer.copyToChannel(float32, 0);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);

      if (nextPlayTimeRef.current > ctx.currentTime + 10) nextPlayTimeRef.current = 0;
      const startAt = Math.max(ctx.currentTime + 0.02, nextPlayTimeRef.current);
      source.start(startAt);
      nextPlayTimeRef.current = startAt + buffer.duration;

      setSpeaking(true);
      source.onended = () => {
        if (ctx.currentTime >= nextPlayTimeRef.current - 0.05) {
          setSpeaking(false);
        }
      };
    } catch (e) {
      console.error("playAudio error:", e);
      setSpeaking(false);
    }
  }

  function handleWsMessage(msg: WsMessage) {
    if (msg.type === "intervention") {
      const m = msg as InterventionMessage;
      setInterventionQueue(q => [...q, { interactionId: m.interaction_id, trigger: m.trigger, text: m.text }]);
      const emotionMap: Record<string, typeof rumiEmotion> = {
        A: "concerned", B: "thinking", C: "concerned", E: "happy",
      };
      setRumiEmotion(emotionMap[m.trigger] ?? "neutral"); // reset to neutral when Rumi finishes speaking
    } else if (msg.type === "audio_response") {
      playAudio((msg as { type: string; data: string }).data);
    } else if (msg.type === "memory_updated") {
      const m = msg as { type: string; message: string };
      setMemoryToast(m.message);
      setTimeout(() => setMemoryToast(null), 6000);
    } else if (msg.type === "paused") {
      setObservationState("paused");
    } else if (msg.type === "error") {
      const m = msg as { type: string; code: string };
      if (m.code === "CAMERA_UNAVAILABLE") setObservationState("degraded");
    }
  }

  function handleInterventionRespond(interactionId: string, response: "accepted" | "dismissed") {
    if (wsRef.current) sendInterventionResponse(wsRef.current, interactionId, response);
    setInterventionQueue(q => q.slice(1));
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
        <div className="rumi-card text-center max-w-sm">
          <p className="text-sm mb-4" style={{ color: "var(--error)" }}>{error}</p>
          <button className="btn-ghost" onClick={() => router.push("/")}>Back to sign in</button>
        </div>
      </main>
    );
  }

  const stateColor =
    observationState === "active" ? "var(--teal)" :
    observationState === "degraded" ? "#f97316" :
    "var(--muted)";

  const stateLabel =
    observationState === "active" ? "Observing" :
    observationState === "degraded" ? "Degraded" :
    "Paused";

  return (
    <main
      className="dot-grid noise-overlay min-h-screen flex flex-col"
      style={{ background: "var(--bg)" }}
    >
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav
        className="glass sticky top-0 z-20 flex items-center justify-between px-5 py-3"
        style={{ borderLeft: "none", borderRight: "none", borderTop: "none" }}
      >
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor: stateColor,
              boxShadow: `0 0 8px ${stateColor}`,
              animation: observationState === "active" ? "pulse 2s ease-in-out infinite" : "none",
            }}
          />
          <span
            className="font-display text-gold"
            style={{ fontSize: "1.25rem", fontWeight: 400, letterSpacing: "0.06em" }}
          >
            Rumi
          </span>
        </div>

        {/* Status pill */}
        <div
          className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full"
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            fontSize: "0.7rem",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            color: stateColor,
          }}
        >
          <span>{stateLabel}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <a href="/profile" className="btn-icon" title="Your memory">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
            </svg>
          </a>
          {sessionId && (
            <PauseButton
              sessionId={sessionId}
              observationState={observationState}
              onStateChange={setObservationState}
            />
          )}
        </div>
      </nav>

      {/* ── Main content ────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 gap-8">

        {/* Greeting */}
        <div className="text-center animate-fade-up">
          {name ? (
            <h1
              className="font-display text-gold"
              style={{ fontSize: "2rem", fontWeight: 300, letterSpacing: "0.04em" }}
            >
              Marhaba, {name}
            </h1>
          ) : (
            <div
              className="h-8 w-40 rounded-lg mx-auto"
              style={{ background: "var(--surface-2)", animation: "pulse 1.5s ease-in-out infinite" }}
            />
          )}
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {speaking ? "Rumi is speaking…" :
             isTalking ? "Listening…" :
             observationState === "active" ? "Witnessing. Understanding." :
             observationState === "degraded" ? "Camera unavailable — text mode" :
             "Observation paused"}
          </p>
        </div>

        {/* Rumi face portal */}
        <div
          className="glass animate-fade-up delay-100 rounded-2xl p-8 flex flex-col items-center gap-4"
          style={{
            boxShadow: observationState === "active"
              ? "0 0 48px rgba(34,211,238,0.08), 0 0 80px rgba(201,168,76,0.05)"
              : "none",
          }}
        >
          <RumiFace state={observationState} speaking={speaking} emotion={rumiEmotion} />
        </div>

        {/* Hidden webcam */}
        <video ref={videoRef} autoPlay muted playsInline className="hidden" />

        {/* Talk button */}
        <div className="flex flex-col items-center gap-2 select-none animate-fade-up delay-200">
          <button
            onClick={toggleTalking}
            aria-label={isTalking ? "Stop talking" : "Talk to Rumi"}
            style={{
              width: 72,
              height: 72,
              borderRadius: "50%",
              border: `2px solid ${isTalking ? "var(--teal)" : "var(--border-2)"}`,
              background: isTalking
                ? "rgba(34,211,238,0.12)"
                : "var(--surface)",
              color: isTalking ? "var(--teal)" : "var(--muted)",
              boxShadow: isTalking
                ? "0 0 24px rgba(34,211,238,0.35), 0 0 48px rgba(34,211,238,0.15)"
                : "none",
              transform: isTalking ? "scale(0.96)" : "scale(1)",
              transition: "all 0.15s ease",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
              <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" />
            </svg>
          </button>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            {isTalking ? "Tap to send · Space" : "Tap to talk · Space"}
          </p>
        </div>

        {/* Intervention card */}
        {intervention && (
          <div className="w-full max-w-lg animate-fade-up">
            <InterventionCard
              interactionId={intervention.interactionId}
              trigger={intervention.trigger}
              text={intervention.text}
              onRespond={handleInterventionRespond}
            />
          </div>
        )}
      </div>

      {/* Memory toast */}
      {memoryToast && (
        <div
          className="animate-toast fixed bottom-6 left-1/2 glass rounded-xl px-5 py-3 text-sm text-center max-w-sm shadow-xl"
          style={{
            transform: "translateY(0) translateX(-50%)",
            border: "1px solid var(--border-2)",
            color: "var(--teal)",
          }}
        >
          <span style={{ color: "var(--gold)", marginRight: "0.5rem" }}>&#9670;</span>
          {memoryToast}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.15); }
        }
      `}</style>
    </main>
  );
}
