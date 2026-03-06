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
import MirratFace from "@/components/MirratFace";
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
  const [intervention, setIntervention] = useState<ActiveIntervention | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [isTalking, setIsTalking] = useState(false);
  const [mirratEmotion, setMirratEmotion] = useState<"neutral" | "concerned" | "happy" | "thinking">("neutral");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);      // mic capture (16kHz)
  const playCtxRef = useRef<AudioContext | null>(null);        // Gemini playback (24kHz)
  const nextPlayTimeRef = useRef<number>(0);                   // scheduled end of last chunk
  const isTalkingRef = useRef<boolean>(false);                 // push-to-talk gate

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
          // Show happy greeting face for 4 seconds
          setMirratEmotion("happy");
          setTimeout(() => setMirratEmotion("neutral"), 4000);
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
            if (ws?.readyState !== WebSocket.OPEN) return;
            if (!isTalkingRef.current) return;
            const float32 = e.inputBuffer.getChannelData(0);
            // Skip true silence only
            const energy = float32.reduce((s, v) => s + v * v, 0) / float32.length;
            if (energy < 0.00001) return;
            const int16buf = float32ToInt16(float32);
            // Safe base64 — no spread operator (stack overflow on large buffers)
            const bytes = new Uint8Array(int16buf);
            let binary = "";
            for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
            ws.send(JSON.stringify({ type: "audio", data: btoa(binary) }));
          };
          micSource.connect(scriptProcessor);
          scriptProcessor.connect(audioCtx.destination);
        } catch {
          console.warn("Mic unavailable — audio input disabled");
        }

        // Connect WebSocket — frame sending is on-demand (backend requests it)
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
                resolve(btoa(String.fromCharCode(...new Uint8Array(buf))));
              });
            }, "image/jpeg", 0.7);
          });

        ws = await connectObserveSocket(sid, async (msg) => {
          // Handle request_frame before passing to general handler
          if (msg.type === "request_frame") {
            const b64 = await captureFrame();
            if (b64 && ws?.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "frame", data: b64 }));
            }
            return;
          }
          handleWsMessage(msg);
        });
        wsRef.current = ws;

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
      ws?.close();
      scriptProcessor?.disconnect();
      micSource?.disconnect();
      videoStream?.getTracks().forEach((t) => t.stop());
      micStream?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close();
      playCtxRef.current?.close();
      playCtxRef.current = null;
    };
  }, [router]);

  // End session on page unload
  useEffect(() => {
    const handleUnload = () => { if (sessionId) endSession(sessionId); };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [sessionId]);

  // Space key toggle push-to-talk (desktop)
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
    setMirratEmotion(next ? "thinking" : "neutral");
  }

  // Play a PCM chunk from Gemini — chunks are scheduled sequentially, no gaps/overlap
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

      // Schedule this chunk to start exactly when the previous chunk ends
      const startAt = Math.max(ctx.currentTime + 0.02, nextPlayTimeRef.current);
      source.start(startAt);
      nextPlayTimeRef.current = startAt + buffer.duration;

      setSpeaking(true);
      source.onended = () => {
        // Only stop speaking indicator when all chunks have played
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
      setIntervention({ interactionId: m.interaction_id, trigger: m.trigger, text: m.text });
      // Show matching emotion on Mirr'at's face
      const emotionMap: Record<string, typeof mirratEmotion> = {
        A: "concerned", B: "thinking", C: "concerned", E: "happy",
      };
      setMirratEmotion(emotionMap[m.trigger] ?? "neutral");
      setTimeout(() => setMirratEmotion("neutral"), 8000);
    } else if (msg.type === "audio_response") {
      console.log("audio_response WS message received");
      playAudio((msg as { type: string; data: string }).data);
    } else if (msg.type === "paused") {
      setObservationState("paused");
    } else if (msg.type === "error") {
      const m = msg as { type: string; code: string };
      if (m.code === "CAMERA_UNAVAILABLE") setObservationState("degraded");
    }
  }

  function handleInterventionRespond(interactionId: string, response: "accepted" | "dismissed") {
    if (wsRef.current) sendInterventionResponse(wsRef.current, interactionId, response);
    setIntervention(null);
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-950 text-red-400">
        <p>{error}</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-2xl mx-auto flex flex-col items-center gap-8">

        {/* Header */}
        <div className="w-full flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">
              {name ? `Marhaba, ${name}` : "Loading…"}
            </h1>
            <p className="text-gray-500 text-sm mt-1">Your Wise Engineer companion is watching.</p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/profile"
              className="p-2 rounded-full bg-gray-800 hover:bg-gray-700 transition text-gray-300 hover:text-white"
              title="Edit your profile"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
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
        </div>

        {/* Robot face */}
        <MirratFace state={observationState} speaking={speaking} emotion={mirratEmotion} />

        {/* Hidden video for webcam frames */}
        <video ref={videoRef} autoPlay muted playsInline className="hidden" />

        {/* Hold-to-talk button */}
        <div className="flex flex-col items-center gap-2 select-none">
          <button
            onClick={toggleTalking}
            className={`
              w-20 h-20 rounded-full border-4 transition-all duration-150
              flex items-center justify-center text-3xl
              ${isTalking
                ? "bg-cyan-500 border-cyan-300 shadow-[0_0_24px_rgba(6,182,212,0.8)] scale-95"
                : "bg-gray-800 border-gray-600 hover:border-gray-400 active:scale-95"
              }
            `}
            aria-label={isTalking ? "Stop talking" : "Start talking"}
          >
            🎙️
          </button>
          <p className="text-xs text-gray-500">
            {isTalking ? "Listening… tap to send" : "Tap to talk · Space"}
          </p>
        </div>

        {/* Intervention card */}
        {intervention && (
          <InterventionCard
            interactionId={intervention.interactionId}
            trigger={intervention.trigger}
            text={intervention.text}
            onRespond={handleInterventionRespond}
          />
        )}
      </div>
    </main>
  );
}
