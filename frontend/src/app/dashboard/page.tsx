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

export default function DashboardPage() {
  const router = useRouter();
  const [name, setName] = useState<string | null>(null);
  const [observationState, setObservationState] = useState<ObservationState>("paused");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [interventionQueue, setInterventionQueue] = useState<ActiveIntervention[]>([]);
  const intervention = interventionQueue[0] ?? null;
  const [speaking, setSpeaking] = useState(false);
  const [isTalking, setIsTalking] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState<string>("");
  const [rumiEmotion, setRumiEmotion] = useState<"neutral" | "concerned" | "happy" | "thinking">("neutral");
  const [error, setError] = useState<string | null>(null);
  const [memoryToast, setMemoryToast] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const sessionIdRef = useRef<string | null>(null);
  const shouldReconnectRef = useRef<boolean>(true);
  const prevSpeakingRef = useRef<boolean>(false);
  const processingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const isTalkingRef = useRef<boolean>(false);

  // ── Init ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    let videoStream: MediaStream | null = null;
    let ws: WebSocket | null = null;

    async function init() {
      try {
        await verifyAuth();
        const identity = await getIdentity();
        if (!identity) { router.push("/onboarding"); return; }
        setName(identity.name as string);

        const sid = await startSession();
        setSessionId(sid);

        // Webcam — stay paused until user starts observation
        try {
          videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
          if (videoRef.current) videoRef.current.srcObject = videoStream;
        } catch {
          setObservationState("degraded");
        }

        // Frame capture helper
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

        // WS connect
        async function connectWs(sid: string) {
          const newWs = await connectObserveSocket(sid, async (msg) => {
            if (msg.type === "request_frame") {
              const b64 = await captureFrame();
              if (b64 && wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "frame", data: b64 }));
              }
              return;
            }
            handleWsMessage(msg);
          });
          wsRef.current = newWs;
          newWs.addEventListener("close", () => {
            if (!shouldReconnectRef.current) return;
            setTimeout(() => {
              if (shouldReconnectRef.current && sessionIdRef.current) connectWs(sessionIdRef.current);
            }, 3000);
          });
        }

        sessionIdRef.current = sid;
        await connectWs(sid);
        ws = wsRef.current;
        setSessionReady(true);

      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Session error";
        if (msg.includes("UNAUTHORISED") || msg.includes("Auth")) router.push("/");
        else setError(msg);
      }
    }

    init();

    return () => {
      shouldReconnectRef.current = false;
      wsRef.current?.close();
      videoStream?.getTracks().forEach((t) => t.stop());
      playCtxRef.current?.close();
      playCtxRef.current = null;
      recognitionRef.current?.abort();
      if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
    };
  }, [router]);

  useEffect(() => {
    const handleUnload = () => { if (sessionId) endSession(sessionId); };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [sessionId]);

  // Reset emotion when Rumi finishes speaking
  useEffect(() => {
    if (prevSpeakingRef.current && !speaking) setRumiEmotion("neutral");
    prevSpeakingRef.current = speaking;
  }, [speaking]);

  // Space bar shortcut
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat || e.target !== document.body) return;
      e.preventDefault();
      handleMicToggle();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Speech Recognition ────────────────────────────────────────────────────
  function startListening() {
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: typeof window.SpeechRecognition; webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError("Voice input not supported in this browser. Please use Chrome.");
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";
    recognitionRef.current = rec;

    rec.onstart = () => {
      isTalkingRef.current = true;
      setIsTalking(true);
      setTranscript("");
      setRumiEmotion("thinking");
    };

    // Show live transcript while speaking
    rec.onresult = (e: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t;
        else interim += t;
      }
      setTranscript(final || interim);
    };

    // Auto-send when recognition ends (user paused long enough)
    rec.onend = () => {
      isTalkingRef.current = false;
      setIsTalking(false);
      const text = recognitionRef.current ? "" : ""; // captured in onresult
      // Send whatever final transcript we have
      sendTranscript();
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      isTalkingRef.current = false;
      setIsTalking(false);
      setIsProcessing(false);
      setRumiEmotion("neutral");
      setTranscript("");
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("SpeechRecognition error:", e.error);
      }
    };

    rec.start();
  }

  // Accumulated final transcript across results
  const transcriptRef = useRef<string>("");

  function startListeningWithRef() {
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: typeof window.SpeechRecognition; webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError("Voice input not supported. Please use Chrome or Edge.");
      return;
    }

    transcriptRef.current = "";
    const rec = new SpeechRecognition();
    rec.continuous = true;      // don't auto-stop on natural mid-sentence pauses
    rec.interimResults = true;
    rec.lang = "en-US";
    recognitionRef.current = rec;

    // Auto-stop after 1.8 s of silence — reset on every new speech chunk
    let silenceTimer: ReturnType<typeof setTimeout> | null = null;
    const resetSilenceTimer = () => {
      if (silenceTimer) clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => rec.stop(), 1800);
    };

    rec.onstart = () => {
      isTalkingRef.current = true;
      setIsTalking(true);
      setTranscript("");
      setRumiEmotion("thinking");
    };

    rec.onresult = (e: SpeechRecognitionEvent) => {
      resetSilenceTimer();
      let display = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          transcriptRef.current += e.results[i][0].transcript + " ";
          display += e.results[i][0].transcript + " ";
        } else {
          display += e.results[i][0].transcript;
        }
      }
      setTranscript(display.trim());
    };

    rec.onend = () => {
      if (silenceTimer) clearTimeout(silenceTimer);
      isTalkingRef.current = false;
      setIsTalking(false);
      const text = transcriptRef.current.trim();
      transcriptRef.current = "";
      if (text) {
        sendToRumi(text);
      } else {
        setTranscript("");
        setRumiEmotion("neutral");
      }
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      if (silenceTimer) clearTimeout(silenceTimer);
      isTalkingRef.current = false;
      setIsTalking(false);
      setIsProcessing(false);
      setRumiEmotion("neutral");
      setTranscript("");
      transcriptRef.current = "";
      if (e.error !== "no-speech" && e.error !== "aborted") {
        console.warn("SpeechRecognition error:", e.error);
      }
    };

    rec.start();
  }

  function stopListening() {
    recognitionRef.current?.stop(); // triggers onend → sendToRumi
  }

  function sendToRumi(text: string) {
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setRumiEmotion("neutral");
      setTranscript("");
      return;
    }
    setIsProcessing(true);
    setTranscript(text);
    wsRef.current.send(JSON.stringify({ type: "user_text", text }));
    // Safety timeout — clear if no reply in 20s
    if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
    processingTimeoutRef.current = setTimeout(() => {
      setIsProcessing(false);
      setTranscript("");
      setRumiEmotion("neutral");
    }, 20000);
  }

  function handleMicToggle() {
    if (speaking) return; // don't interrupt Rumi
    if (isTalkingRef.current) {
      stopListening();
    } else {
      startListeningWithRef();
    }
  }

  // ── Audio playback ────────────────────────────────────────────────────────
  async function playAudio(b64: string) {
    try {
      if (!playCtxRef.current) playCtxRef.current = new AudioContext({ sampleRate: 24000 });
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
        if (ctx.currentTime >= nextPlayTimeRef.current - 0.05) setSpeaking(false);
      };
    } catch (e) {
      console.error("playAudio error:", e);
      setSpeaking(false);
    }
  }

  // ── WS message handler ────────────────────────────────────────────────────
  function handleWsMessage(msg: WsMessage) {
    if (msg.type === "intervention") {
      const m = msg as InterventionMessage;
      setInterventionQueue(q => [...q, { interactionId: m.interaction_id, trigger: m.trigger, text: m.text }]);
      const emotionMap: Record<string, typeof rumiEmotion> = { A: "concerned", B: "thinking", C: "concerned", E: "happy" };
      setRumiEmotion(emotionMap[m.trigger] ?? "neutral");
    } else if (msg.type === "audio_response") {
      if (processingTimeoutRef.current) { clearTimeout(processingTimeoutRef.current); processingTimeoutRef.current = null; }
      setIsProcessing(false);
      setTranscript("");
      setRumiEmotion(prev => prev === "neutral" || prev === "thinking" ? "happy" : prev);
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

  // ── Render ─────────────────────────────────────────────────────────────────
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
    observationState === "degraded" ? "#f97316" : "var(--muted)";

  return (
    <main className="dot-grid noise-overlay min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>

      {/* Navbar */}
      <nav className="glass sticky top-0 z-20 flex items-center justify-between px-5 py-3"
        style={{ borderLeft: "none", borderRight: "none", borderTop: "none" }}>
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full" style={{
            backgroundColor: stateColor,
            boxShadow: `0 0 8px ${stateColor}`,
            animation: observationState === "active" ? "statusPulse 2s ease-in-out infinite" : "none",
          }} />
          <span className="font-display text-gold" style={{ fontSize: "1.25rem", fontWeight: 400, letterSpacing: "0.06em" }}>
            Rumi
          </span>
        </div>
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full" style={{
          background: "var(--surface-2)", border: "1px solid var(--border)",
          fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase", color: stateColor,
        }}>
          {observationState === "active" ? "Observing" : observationState === "degraded" ? "Degraded" : "Paused"}
        </div>
        <div className="flex items-center gap-2">
          <a href="/profile" className="btn-icon" title="Your memory">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
            </svg>
          </a>
          {sessionId && (
            <PauseButton sessionId={sessionId} observationState={observationState} onStateChange={setObservationState} />
          )}
        </div>
      </nav>

      {/* Main */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 gap-8">

        {/* Greeting */}
        <div className="text-center animate-fade-up">
          {name ? (
            <h1 className="font-display text-gold" style={{ fontSize: "2rem", fontWeight: 300, letterSpacing: "0.04em" }}>
              Marhaba, {name}
            </h1>
          ) : (
            <div className="h-8 w-40 rounded-lg mx-auto" style={{ background: "var(--surface-2)", animation: "statusPulse 1.5s ease-in-out infinite" }} />
          )}
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {speaking ? "Rumi is speaking…"
              : isProcessing ? "Rumi is thinking…"
              : isTalking ? "Listening — stop talking to send"
              : observationState === "active" ? "Witnessing. Understanding."
              : observationState === "degraded" ? "Camera unavailable — text mode"
              : "Observation paused"}
          </p>
        </div>

        {/* Rumi face */}
        <div className="glass animate-fade-up delay-100 rounded-2xl p-8 flex flex-col items-center gap-4"
          style={{ boxShadow: observationState === "active" ? "0 0 48px rgba(34,211,238,0.08), 0 0 80px rgba(201,168,76,0.05)" : "none" }}>
          <RumiFace state={observationState} speaking={speaking} emotion={rumiEmotion} />
        </div>

        <video ref={videoRef} autoPlay muted playsInline className="hidden" />

        {/* Begin observation */}
        {sessionReady && observationState === "paused" && (
          <div className="animate-fade-up delay-200 text-center">
            <button
              onClick={() => {
                setObservationState("active");
                if (sessionId) {
                  const token = sessionStorage.getItem("id_token");
                  const url = `${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/session/${sessionId}/resume`;
                  fetch(url, { method: "PUT", headers: { Authorization: `Bearer ${token}` } });
                }
              }}
              className="btn-primary"
              style={{ fontSize: "0.9rem", padding: "0.75rem 2rem" }}
            >
              Begin Observation
            </button>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              Rumi will start watching when you&apos;re ready
            </p>
          </div>
        )}

        {/* Talk button — Google Voice Search style */}
        {observationState !== "paused" && (
          <div className="flex flex-col items-center gap-3 select-none animate-fade-up delay-200">

            {/* Live transcript */}
            {(isTalking || isProcessing) && transcript && (
              <div className="glass rounded-xl px-4 py-2 max-w-xs text-center" style={{ minWidth: 200 }}>
                <p className="text-sm" style={{ color: isTalking ? "var(--text)" : "var(--muted)", fontStyle: isProcessing ? "italic" : "normal" }}>
                  &ldquo;{transcript}&rdquo;
                </p>
              </div>
            )}

            {/* Waveform bars — visible while listening */}
            {isTalking && (
              <div className="flex items-end gap-0.5 h-6">
                {[3, 5, 8, 5, 10, 6, 4, 9, 6, 3].map((h, i) => (
                  <div key={i} style={{
                    width: 3, borderRadius: 2,
                    backgroundColor: "var(--teal)",
                    height: h * 2,
                    animation: `waveBar 0.6s ease-in-out ${i * 0.06}s infinite alternate`,
                  }} />
                ))}
              </div>
            )}

            {/* Mic button */}
            <button
              onClick={handleMicToggle}
              disabled={speaking}
              aria-label={isTalking ? "Stop and send" : "Talk to Rumi"}
              style={{
                width: 72, height: 72, borderRadius: "50%",
                border: `2px solid ${isTalking ? "var(--teal)" : isProcessing ? "var(--gold-dim)" : "var(--border-2)"}`,
                background: isTalking ? "rgba(34,211,238,0.12)" : isProcessing ? "rgba(201,168,76,0.08)" : "var(--surface)",
                color: isTalking ? "var(--teal)" : isProcessing ? "var(--gold)" : "var(--muted)",
                boxShadow: isTalking ? "0 0 24px rgba(34,211,238,0.4), 0 0 48px rgba(34,211,238,0.15)"
                  : isProcessing ? "0 0 20px rgba(201,168,76,0.2)" : "none",
                transform: isTalking ? "scale(0.95)" : "scale(1)",
                transition: "all 0.2s ease",
                cursor: speaking ? "default" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              {isProcessing ? (
                <span style={{
                  display: "inline-block", width: 22, height: 22, borderRadius: "50%",
                  border: "2.5px solid var(--gold-dim)", borderTopColor: "var(--gold)",
                  animation: "spin 0.8s linear infinite",
                }} />
              ) : speaking ? (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
                </svg>
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
                  <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" />
                </svg>
              )}
            </button>

            <p className="text-xs" style={{
              color: isTalking ? "var(--teal)" : isProcessing ? "var(--gold)" : speaking ? "var(--gold)" : "var(--muted)"
            }}>
              {isTalking ? "Tap or Space to send"
                : isProcessing ? "Sending to Rumi…"
                : speaking ? "Rumi is speaking"
                : "Tap to talk · Space"}
            </p>
          </div>
        )}

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
        <div className="animate-toast fixed bottom-6 left-1/2 glass rounded-xl px-5 py-3 text-sm text-center max-w-sm shadow-xl"
          style={{ transform: "translateY(0) translateX(-50%)", border: "1px solid var(--border-2)", color: "var(--teal)" }}>
          <span style={{ color: "var(--gold)", marginRight: "0.5rem" }}>&#9670;</span>
          {memoryToast}
        </div>
      )}

      <style>{`
        @keyframes statusPulse { 0%, 100% { opacity: 0.5; transform: scale(1); } 50% { opacity: 1; transform: scale(1.15); } }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes waveBar { from { transform: scaleY(0.4); opacity: 0.6; } to { transform: scaleY(1); opacity: 1; } }
      `}</style>
    </main>
  );
}
