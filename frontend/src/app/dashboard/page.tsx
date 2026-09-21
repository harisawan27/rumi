"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  verifyAuth,
  getIdentity,
  saveIdentity,
  startSession,
  endSession,
  connectObserveSocket,
  sendInterventionResponse,
  getCanvasHistory,
  type InterventionMessage,
  type WsMessage,
  getMemoryCandidates,
} from "@/services/session";
import { ObservationState } from "@/components/ObservationIndicator";
import InterventionCard from "@/components/InterventionCard";
import PauseButton from "@/components/PauseButton";
import RumiFace from "@/components/RumiFace";
import ArtifactCanvas, { type CanvasContent, type CanvasExchange } from "@/components/ArtifactCanvas";
import { TurnAccumulator } from "@/services/turnAccumulator";
import RumiStatusMenu from "@/components/RumiStatusMenu";
import MobileNavigation, { type MobileTab } from "@/components/MobileNavigation";
import MobileSheet from "@/components/MobileSheet";
import ConversationTimeline from "@/components/ConversationTimeline";
import { canvasFromHistory } from "@/services/canvasHistory";
import { CreateRequests, CREATE_PROGRESS } from "@/services/createRequests";
import { useGeneratedArtifact } from "@/hooks/useGeneratedArtifact";

interface ActiveIntervention {
  interactionId: string;
  trigger: "A" | "B" | "C" | "E" | "G";
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
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [guestMode, setGuestMode] = useState(false);
  const [identityVerified, setIdentityVerified] = useState(false);
  const [micEnabled, setMicEnabled] = useState(true);
  const [liveStream, setLiveStream] = useState<MediaStream | null>(null);
  const [detection, setDetection] = useState<{
    state: string;
    confidence: number;
    cues: string[];
    emotions: Record<string, number>;
    face_detected?: boolean;
    detector_status?: string;
  } | null>(null);
  const [showCameraPopup, setShowCameraPopup] = useState(false);
  const [showEmotionPopup, setShowEmotionPopup] = useState(false);
  const [screenActive, setScreenActive] = useState(false);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const screenVideoRef = useRef<HTMLVideoElement | null>(null);
  const screenCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // ── Conversational Turn Accumulator & Auto-Restart Guards ────────────────
  const turnAccumulatorRef = useRef<TurnAccumulator>(new TurnAccumulator());
  const isStartingRecRef = useRef(false);
  const isManualStopRef = useRef(false);
  const isUnmountedRef = useRef(false);
  const turnDebounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const VOICE_END_SILENCE_MS = 1200; // Natural pause tolerance (default 1200ms)

  // ── Canvas state ────────────────────────────────────────────────────────────
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasHistory, setCanvasHistory] = useState<CanvasContent[]>([]);
  const [canvasIndex, setCanvasIndex] = useState(0);
  const [isFollowingUp, setIsFollowingUp] = useState(false);
  const canvasContent = canvasHistory[canvasIndex] ?? null;

  // ── Override command state ──────────────────────────────────────────────────
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideText, setOverrideText] = useState("");

  // ── Experience v1 states ────────────────────────────────────────────────────
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activeMobileTab, setActiveMobileTab] = useState<MobileTab>("rumi");
  const [pendingCandidatesCount, setPendingCandidatesCount] = useState(0);
  const [isMobileDevice, setIsMobileDevice] = useState(false);
  const [supportsScreenShare, setSupportsScreenShare] = useState(false);
  const [isTabHidden, setIsTabHidden] = useState(false);
  const [showGuidance, setShowGuidance] = useState(false);
  const [artifactAuthorizationSignal, setArtifactAuthorizationSignal] = useState(0);
  const artifactAllowed = sessionReady && identityVerified && !guestMode && observationState !== "away" && !isTabHidden;
  const generated = useGeneratedArtifact(sessionId, artifactAllowed, artifactAuthorizationSignal);
  const createRequests = useRef(new CreateRequests());
  const [createProgress, setCreateProgress] = useState("");
  const canvasContextRef = useRef({ allowed: artifactAllowed, hasCanvas: !!canvasContent });
  canvasContextRef.current = { allowed: artifactAllowed, hasCanvas: !!canvasContent };
  useEffect(() => {
    if (!artifactAllowed) { createRequests.current.cancel(); setCreateProgress(""); }
  }, [artifactAllowed]);
  const visibleCanvas = artifactAllowed && generated.artifact
    ? { kind: "generated_ui" as const, artifact: generated.artifact } : canvasContent;

  useEffect(() => {
    if (artifactAllowed && canvasContent?.artifact_id) {
      if (generated.client.snapshot().artifact?.artifact_id === canvasContent.artifact_id) return;
      void generated.client.load(canvasContent.artifact_id).catch(() => {});
    }
  }, [artifactAllowed, canvasContent?.artifact_id, generated.client]);

  const wsRef = useRef<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const cameraPopupVideoRef = useRef<HTMLVideoElement | null>(null);
  const videoStreamRef = useRef<MediaStream | null>(null);
  const playCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const sessionIdRef = useRef<string | null>(null);
  const shouldReconnectRef = useRef<boolean>(true);
  const prevSpeakingRef = useRef<boolean>(false);
  const processingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const isTalkingRef = useRef<boolean>(false);
  const overrideInputRef = useRef<HTMLInputElement | null>(null);
  const captureFrameRef = useRef<(() => Promise<string | null>) | null>(null);
  const preListenerRef = useRef<SpeechRecognition | null>(null);
  const wakeWordActiveRef = useRef<boolean>(false);
  const micEnabledRef = useRef<boolean>(true);
  const cameraEnabledRef = useRef<boolean>(true);
  const lastFollowUpQueryRef = useRef<string>("");
  const lastSentQueryRef = useRef<string>("");   // always-current ref — avoids stale closure in WS handler
  const pendingAttachmentRef = useRef<{ dataUrl: string; name: string } | null>(null);
  const bargeinRef = useRef<SpeechRecognition | null>(null); // VAD barge-in listener (active while Rumi speaks)
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]); // all playing sources — stopped on interrupt
  const speakingRef = useRef<boolean>(false); // closure-safe speaking state for rec.onend
  const audioGenRef = useRef<number>(0);                        // incremented on stopAllAudio to cancel pending chunks
  const audioChainRef = useRef<Promise<void>>(Promise.resolve()); // sequential scheduling chain — prevents chunk racing

  const [wakeListening, setWakeListening] = useState(false);

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

        // Silently sync device timezone — never ask the user for this
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (identity.timezone !== tz) {
          saveIdentity({ ...identity, timezone: tz }).catch(() => {});
        }

        const sid = await startSession();
        setSessionId(sid);

        // Load canvas history via REST immediately — no WS timing dependency
        getCanvasHistory().then(items => {
          if (items.length > 0) {
            const mapped = items.map(canvasFromHistory);
            setCanvasHistory(mapped);
            setCanvasIndex(mapped.length - 1);
          }
        }).catch(() => { /* silently fall back to WS canvas_history message */ });

        // Webcam
        try {
          videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
          videoStreamRef.current = videoStream;
          setLiveStream(videoStream);
        } catch {
          setObservationState("degraded");
          setCameraEnabled(false);
        }

        // Frame capture helper
        const canvas = document.createElement("canvas");
        const canvasCtx = canvas.getContext("2d");
        const captureFrame = (): Promise<string | null> =>
          new Promise((resolve) => {
            if (!videoRef.current || !canvasCtx || !cameraEnabledRef.current) return resolve(null);
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

        // Expose captureFrame so voice onend can attach a snapshot (Phase 5)
        captureFrameRef.current = captureFrame;

        // WS connect
        async function connectWs(sid: string) {
          const newWs = await connectObserveSocket(sid, async (msg) => {
            if (msg.type === "request_frame") {
              // Honour camera privacy toggle — never send frames when user disabled camera
              if (cameraEnabledRef.current) {
                const b64 = await captureFrame();
                if (b64 && wsRef.current?.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: "frame", data: b64 }));
                }
              }
              return;
            }
            handleWsMessage(msg);
          });
          wsRef.current = newWs;
          newWs.addEventListener("open", () => setSessionReady(true));
          newWs.addEventListener("close", () => {
            generated.client.revoke();
            setSessionReady(false);
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
      isUnmountedRef.current = true;
      if (turnDebounceTimerRef.current) clearTimeout(turnDebounceTimerRef.current);
      shouldReconnectRef.current = false;
      wsRef.current?.close();
      videoStreamRef.current?.getTracks().forEach((t) => t.stop());
      videoStream?.getTracks().forEach((t) => t.stop());
      playCtxRef.current?.close();
      playCtxRef.current = null;
      recognitionRef.current?.abort();
      wakeWordActiveRef.current = false;
      preListenerRef.current?.abort();
      preListenerRef.current = null;
      bargeinRef.current?.abort();
      bargeinRef.current = null;
      if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
    };
  }, [router]);

  useEffect(() => {
    const handleUnload = () => { if (sessionId) endSession(sessionId); };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [sessionId]);

  // Attach stream to hidden video
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !liveStream) return;
    v.srcObject = liveStream;
    v.play().catch(() => {});
  }, [liveStream]);

  // Attach stream to camera popup video when popup opens
  useEffect(() => {
    if (showCameraPopup && cameraPopupVideoRef.current && liveStream) {
      cameraPopupVideoRef.current.srcObject = liveStream;
      cameraPopupVideoRef.current.play().catch(() => {});
    }
  }, [showCameraPopup, liveStream]);

  // Keep speakingRef in sync for closure-safe access in rec.onend
  useEffect(() => { speakingRef.current = speaking; }, [speaking]);

  // Reset emotion + open conversation window when Rumi finishes speaking
  useEffect(() => {
    if (!prevSpeakingRef.current && speaking) {
      // Rumi just started speaking — kill the main listener immediately so it
      // cannot transcribe Rumi's own speaker output and send a phantom user_text.
      // This is the root cause of double-speak: listener stays active after the
      // conversation window, picks up Rumi's audio, fires onend → sendToRumi.
      if (!isTalkingRef.current) {
        transcriptRef.current = "";          // discard any partial transcript
        recognitionRef.current?.abort();     // onend fires with empty text → no send
        recognitionRef.current = null;
        stopWakeWordListener();
      }
    } else if (prevSpeakingRef.current && !speaking) {
      setRumiEmotion("neutral");
      // Conversation window — skip wake word, listen immediately for follow-up
      if (micEnabledRef.current && !isTalkingRef.current) {
        stopWakeWordListener();
        setTimeout(() => {
          if (micEnabledRef.current && !isTalkingRef.current) startListeningWithRef();
        }, 300);
      }
    }
    prevSpeakingRef.current = speaking;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speaking]);

  // Keep refs in sync for closure-safe access
  useEffect(() => { micEnabledRef.current = micEnabled; }, [micEnabled]);
  useEffect(() => { cameraEnabledRef.current = cameraEnabled; }, [cameraEnabled]);


  // Space bar shortcut for mic
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.repeat || e.target !== document.body) return;
      if (e.code === "Space") {
        e.preventDefault();
        handleMicToggle();
      } else if (e.code === "Backslash") {
        // Secret demo trigger — fires an intervention card instantly (\ key)
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "demo_trigger" }));
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Start/stop wake word listener based on active state
  useEffect(() => {
    if (observationState === "active" && micEnabled && sessionReady) {
      startWakeWordListener();
    } else {
      stopWakeWordListener();
    }
    return () => stopWakeWordListener();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [observationState, micEnabled, sessionReady]);

  // "/" opens override command — Escape closes it
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && e.target === document.body) {
        e.preventDefault();
        setOverrideOpen(true);
      }
      if (e.key === "Escape") {
        setOverrideOpen(false);
        setOverrideText("");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Auto-focus override input when it opens
  useEffect(() => {
    if (overrideOpen) setTimeout(() => overrideInputRef.current?.focus(), 40);
  }, [overrideOpen]);

  // ── Experience v1: Device detection & Screen Share support ──────────────────
  useEffect(() => {
    const checkDevice = () => {
      const mobile = window.innerWidth < 640;
      setIsMobileDevice(mobile);
      if (typeof navigator !== "undefined" && navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === "function") {
        setSupportsScreenShare(!mobile);
      }
    };
    checkDevice();
    window.addEventListener("resize", checkDevice);
    return () => window.removeEventListener("resize", checkDevice);
  }, []);

  // ── Experience v1: Document visibility (Correction 6) ──────────────────────
  // Pauses expensive rendering/animations when tab is hidden, without killing
  // WebSocket presence/safety streams or heartbeat.
  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsTabHidden(document.visibilityState === "hidden");
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  // ── Experience v1: Fetch pending memory candidates for badge ────────────────
  useEffect(() => {
    getMemoryCandidates()
      .then((candidates) => setPendingCandidatesCount(candidates.length))
      .catch(() => {});
  }, []);

  // ── Experience v1: First-use guidance tooltip ──────────────────────────────
  useEffect(() => {
    const seen = localStorage.getItem("rumi_guidance_seen");
    if (!seen) {
      setShowGuidance(true);
    }
  }, []);

  function dismissGuidance() {
    setShowGuidance(false);
    localStorage.setItem("rumi_guidance_seen", "1");
  }

  // ── Experience v1: Empathic connection for proactive interventions ──────────
  useEffect(() => {
    if (intervention) {
      if (intervention.trigger === "A" || intervention.trigger === "C") {
        setRumiEmotion("concerned");
      } else if (intervention.trigger === "B") {
        setRumiEmotion("happy");
      } else {
        setRumiEmotion("thinking");
      }
      const timer = setTimeout(() => {
        setInterventionQueue((q) => q.filter((i) => i.interactionId !== intervention.interactionId));
        setRumiEmotion("neutral");
      }, 60000);
      return () => clearTimeout(timer);
    }
  }, [intervention]);

  // ── Speech Recognition ────────────────────────────────────────────────────
  const transcriptRef = useRef<string>("");

  // ── Wake word pre-listener ("Hey Rumi" / "Rumi") ─────────────────────────
  // Phonetic variants — speech recognition often mishears "Rumi" as these
  const WAKE_WORDS = [
    // Direct
    "rumi", "rumi,", "rumi.", "rumi!",
    // Phonetic mishearings (far-field, accented, noisy)
    "roomy", "roomie", "room me", "room e", "room-e", "roome", "room i",
    "rue me", "rhumie", "rhumi", "lumi", "loomie", "loomi", "numi",
    "dumi", "yumi", "gumi", "bumi", "fumi", "tumi", "zumi",
    "rumee", "rume", "rumy", "roomi",
    // With hey/ok prefix
    "hey rumi", "hey roomy", "hey roomie", "hey room", "hey, rumi",
    "hey lumi", "hey numi", "hey loomi", "hey rumy",
    "ok rumi", "okay rumi", "ok roomy", "okay roomy",
    // Partial / run-on
    "a rumi", "arumi", "the rumi", "ooh rumi",
  ];

  function stopWakeWordListener() {
    wakeWordActiveRef.current = false;
    preListenerRef.current?.abort();
    preListenerRef.current = null;
    setWakeListening(false);
  }

  function startWakeWordListener() {
    const SR =
      (window as unknown as { SpeechRecognition?: typeof window.SpeechRecognition; webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .webkitSpeechRecognition;
    if (!SR || !micEnabledRef.current || isTalkingRef.current) return;
    if (preListenerRef.current) return; // already running

    wakeWordActiveRef.current = true;
    setWakeListening(true);

    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    preListenerRef.current = rec;

    rec.onresult = (e: SpeechRecognitionEvent) => {
      // Check only new results (from e.resultIndex) to avoid re-triggering on old text.
      // Accept even low-confidence hits — better to false-positive than miss a far-field call.
      let fullText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        fullText += e.results[i][0].transcript.toLowerCase() + " ";
      }
      // Also always check interim results for speed
      fullText = fullText.trim();
      if (!fullText) return;
      if (WAKE_WORDS.some(w => fullText.includes(w))) {
        wakeWordActiveRef.current = false;
        rec.abort();
        preListenerRef.current = null;
        setWakeListening(false);
        // Brief pause lets mic hardware fully release before main listener grabs it
        setTimeout(() => startListeningWithRef(), 180);
      }
    };

    rec.onend = () => {
      preListenerRef.current = null;
      // Auto-restart — handles browser's 15-min recognition kill
      if (wakeWordActiveRef.current && micEnabledRef.current && !isTalkingRef.current) {
        setTimeout(() => {
          wakeWordActiveRef.current = false; // reset so startWakeWordListener() passes the guard
          startWakeWordListener();
        }, 200);
      } else {
        setWakeListening(false);
      }
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      console.warn("Wake word listener error:", e.error);
    };

    try { rec.start(); } catch { /* ignore race */ }
  }

  function commitConversationalTurn() {
    if (turnDebounceTimerRef.current) {
      clearTimeout(turnDebounceTimerRef.current);
      turnDebounceTimerRef.current = null;
    }
    const text = turnAccumulatorRef.current.commit();
    if (!text) {
      setTranscript("");
      setRumiEmotion("neutral");
      setIsTalking(false);
      isTalkingRef.current = false;
      return;
    }

    try { recognitionRef.current?.stop(); } catch {}

    isTalkingRef.current = false;
    setIsTalking(false);

    const lower = text.toLowerCase();
    const shouldAutoAttach = AUTO_ATTACH_KEYWORDS.some(kw => lower.includes(kw));
    if (shouldAutoAttach && captureFrameRef.current) {
      captureFrameRef.current().then(image => sendToRumi(text, image));
    } else {
      sendToRumi(text);
    }

    setTimeout(() => {
      if (micEnabledRef.current && !isTalkingRef.current && !speakingRef.current && !isUnmountedRef.current) {
        startWakeWordListener();
      }
    }, 400);
  }

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

    isManualStopRef.current = false;
    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    recognitionRef.current = rec;

    rec.onstart = () => {
      isStartingRecRef.current = false;
      isTalkingRef.current = true;
      setIsTalking(true);
      // Retain already accumulated text without wiping
      setTranscript(turnAccumulatorRef.current.getDisplayText());
      setRumiEmotion("thinking");
    };

    rec.onresult = (e: SpeechRecognitionEvent) => {
      const chunks = [];
      for (let i = 0; i < e.results.length; i++) {
        chunks.push({
          isFinal: e.results[i].isFinal,
          transcript: e.results[i][0].transcript,
        });
      }
      const display = turnAccumulatorRef.current.handleSpeechResults(chunks);
      setTranscript(display);

      // Reset conversational turn debounce timer on incoming speech
      if (turnDebounceTimerRef.current) clearTimeout(turnDebounceTimerRef.current);
      turnDebounceTimerRef.current = setTimeout(() => {
        commitConversationalTurn();
      }, VOICE_END_SILENCE_MS);
    };

    rec.onend = () => {
      isStartingRecRef.current = false;
      turnAccumulatorRef.current.handleSegmentEnd();

      // Guarded auto-restart check (User Correction 3)
      const isTurnOngoing = Boolean(turnDebounceTimerRef.current && turnAccumulatorRef.current.hasContent());
      const canRestart = (
        !isUnmountedRef.current &&
        !isManualStopRef.current &&
        micEnabledRef.current &&
        !speakingRef.current &&
        !isStartingRecRef.current &&
        wsRef.current?.readyState === WebSocket.OPEN
      );

      if (isTurnOngoing && canRestart) {
        // Recognizer stopped mid-utterance during a natural pause — auto-restart smoothly
        isStartingRecRef.current = true;
        setTimeout(() => {
          if (!isUnmountedRef.current && !speakingRef.current && micEnabledRef.current && !isManualStopRef.current) {
            try {
              startListeningWithRef();
            } catch {
              isStartingRecRef.current = false;
            }
          } else {
            isStartingRecRef.current = false;
          }
        }, 60);
        return;
      }

      // If no turn timer active or cannot restart:
      if (turnDebounceTimerRef.current) {
        clearTimeout(turnDebounceTimerRef.current);
        turnDebounceTimerRef.current = null;
      }
      isTalkingRef.current = false;
      setIsTalking(false);

      if (turnAccumulatorRef.current.hasContent() && !isManualStopRef.current) {
        const text = turnAccumulatorRef.current.commit();
        if (text) {
          sendToRumi(text);
        } else {
          setTranscript("");
          setRumiEmotion("neutral");
        }
      } else {
        turnAccumulatorRef.current.reset();
        setTranscript("");
        setRumiEmotion("neutral");
      }

      setTimeout(() => {
        if (micEnabledRef.current && !isTalkingRef.current && !speakingRef.current && !isUnmountedRef.current) {
          startWakeWordListener();
        }
      }, 400);
    };

    rec.onerror = (e: SpeechRecognitionErrorEvent) => {
      isStartingRecRef.current = false;
      if (e.error === "no-speech" || e.error === "aborted") {
        return;
      }
      console.warn("SpeechRecognition error:", e.error);
      if (turnDebounceTimerRef.current) {
        clearTimeout(turnDebounceTimerRef.current);
        turnDebounceTimerRef.current = null;
      }
      isTalkingRef.current = false;
      setIsTalking(false);
      setIsProcessing(false);
      setRumiEmotion("neutral");
    };

    try {
      rec.start();
    } catch {
      isStartingRecRef.current = false;
    }
  }

  function stopListening(commit = true) {
    isManualStopRef.current = true;
    if (turnDebounceTimerRef.current) {
      clearTimeout(turnDebounceTimerRef.current);
      turnDebounceTimerRef.current = null;
    }
    if (commit && turnAccumulatorRef.current.hasContent()) {
      const text = turnAccumulatorRef.current.commit();
      recognitionRef.current?.stop();
      if (text) sendToRumi(text);
    } else {
      turnAccumulatorRef.current.reset();
      recognitionRef.current?.abort();
      setTranscript("");
      setRumiEmotion("neutral");
      setIsTalking(false);
      isTalkingRef.current = false;
    }
  }

  // ── VAD barge-in ─────────────────────────────────────────────────────────
  // Runs ONLY while Rumi is speaking. Any speech >2 chars immediately interrupts
  // without requiring the wake word — true VAD barge-in.
  function stopBargeinListener() {
    bargeinRef.current?.abort();
    bargeinRef.current = null;
  }

  function startBargeinListener() {
    if (!micEnabledRef.current || bargeinRef.current) return;
    // Chrome allows only one active SpeechRecognition per tab — kill wake word first
    // or it will get aborted mid-capture when barge-in tries to start.
    stopWakeWordListener();
    const SR =
      (window as unknown as { SpeechRecognition?: typeof window.SpeechRecognition; webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .webkitSpeechRecognition;
    if (!SR) return;

    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";
    bargeinRef.current = rec;

    rec.onresult = (e: SpeechRecognitionEvent) => {
      if (activeSourcesRef.current.length === 0) return; // no audio playing — echo of last word, ignore
      const text = Array.from(e.results)
        .map(r => r[0].transcript)
        .join("")
        .trim();
      // Require 15+ chars — wind/fan produces short spurious transcripts.
      // Real interruptions ("actually stop", "wait no", "hey rumi") are longer.
      if (text.length >= 15) {
        stopBargeinListener();
        stopWakeWordListener(); // release mic fully before main listener grabs it
        // Stop all audio immediately (synchronous) — no context close
        stopAllAudio();
        window.speechSynthesis.cancel();
        // Notify backend to cancel its speak task
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "audio_interrupt" }));
        }
        // 250ms lets browser fully release mic before main listener grabs it
        setTimeout(() => startListeningWithRef(), 250);
      }
    };

    rec.onend = () => {
      if (bargeinRef.current === rec) bargeinRef.current = null;
    };

    rec.onerror = () => {
      if (bargeinRef.current === rec) bargeinRef.current = null;
    };

    try { rec.start(); } catch { /* ignore race */ }
  }

  // Start/stop barge-in listener whenever Rumi's speaking state changes
  // 2s delay before enabling barge-in — protects the opening of every response
  // from being instantly cancelled by ambient noise or mic pickup of Rumi's voice.
  useEffect(() => {
    // Barge-in disabled — mic picks up Rumi's own speaker output and self-interrupts.
    // Standard voice demo flow: Rumi speaks fully, user waits, then responds.
    if (!speaking) stopBargeinListener();
    return () => stopBargeinListener();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speaking]);

  function sendToRumi(text: string, image?: string | null) {
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setRumiEmotion("neutral");
      setTranscript("");
      return;
    }
    setIsProcessing(true);
    setTranscript(text);
    lastSentQueryRef.current = text;
    const selected = generated.client.snapshot().artifact?.artifact_id ?? null;
    const requestId = createRequests.current.begin(selected);
    setCreateProgress("");
    const payload: Record<string, unknown> = { type: "user_text", text, request_id: requestId,
      active_artifact_id: selected, has_canvas_context: canvasContextRef.current.hasCanvas };
    if (image) payload.image = image;
    wsRef.current.send(JSON.stringify(payload));
    if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
    processingTimeoutRef.current = setTimeout(() => {
      setIsProcessing(false);
      setTranscript("");
      setRumiEmotion("neutral");
    }, 20000);
  }

  // Keywords that trigger auto-attach of camera frame
  const AUTO_ATTACH_KEYWORDS = [
    // Pointing at something
    "show you", "showing you", "what is this", "what's this", "attach",
    "look at this", "can you see this", "see this", "what do you see",
    // Hand / object queries
    "in my hand", "what's in my", "what is in my", "can you see my",
    "what am i holding", "what is this i",
    // Identity / face questions
    "who is in front", "who do you see", "who am i", "can you see me",
    "do you see me", "who is this", "look at me", "see me",
    // Camera awareness
    "what do i look", "how do i look", "am i on camera",
  ];

  function handleFollowUp(text: string, image?: string | null, attachment?: { dataUrl: string; name: string }) {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    createRequests.current.cancel(); setCreateProgress("");
    lastFollowUpQueryRef.current = text;
    lastSentQueryRef.current = text;
    pendingAttachmentRef.current = attachment ?? null;
    setIsFollowingUp(true);
    // Build context from current canvas session (last 3 exchanges)
    const currentCanvas = canvasHistory[canvasIndex];
    const contextExchanges = currentCanvas?.exchanges.slice(-3).map(ex => ({
      q: ex.query,
      a: ex.response.slice(0, 400),
    })) ?? [];
    const payload: Record<string, unknown> = {
      type: "user_text",
      text,
      is_followup: true,
      context: contextExchanges,
    };
    if (image) payload.image = image;
    if (attachment && !image && attachment.dataUrl.startsWith("data:image")) {
      payload.image = attachment.dataUrl.split(",")[1];
    }
    wsRef.current.send(JSON.stringify(payload));
    if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
    processingTimeoutRef.current = setTimeout(() => { setIsFollowingUp(false); }, 25000);
  }

  async function startScreenShare() {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      screenStreamRef.current = stream;
      const video = document.createElement("video");
      video.srcObject = stream;
      video.muted = true;
      await video.play();
      screenVideoRef.current = video;
      screenCanvasRef.current = document.createElement("canvas");
      setScreenActive(true);
      stream.getVideoTracks()[0].onended = () => {
        setScreenActive(false);
        screenStreamRef.current = null;
        screenVideoRef.current = null;
      };
    } catch { /* user cancelled */ }
  }

  function stopScreenShare() {
    screenStreamRef.current?.getTracks().forEach(t => t.stop());
    screenStreamRef.current = null;
    screenVideoRef.current = null;
    setScreenActive(false);
  }

  function captureScreenFrame(): string | null {
    const video = screenVideoRef.current;
    const canvas = screenCanvasRef.current;
    if (!video || !canvas || !screenActive) return null;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.5).split(",")[1];
  }

  // Send screen frame to backend every 15s when screen sharing is active
  // eslint-disable-next-line react-hooks/exhaustive-deps
  React.useEffect(() => {
    if (!screenActive) return;
    const send = () => {
      const frame = captureScreenFrame();
      if (frame && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "screen_frame", data: frame }));
      }
    };
    send(); // send immediately on share start
    const interval = setInterval(send, 15000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screenActive]);

  function handleCancel() {
    cancelCreate();
    stopAllAudio();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "audio_interrupt" }));
    }
    setIsProcessing(false);
    recognitionRef.current?.stop();
    isTalkingRef.current = false;
    setIsTalking(false);
    setTranscript("");
    setTimeout(() => {
      if (micEnabledRef.current && !isTalkingRef.current) startWakeWordListener();
    }, 400);
  }

  function handleMicToggle() {
    if (speaking || !micEnabled) return;
    if (isTalkingRef.current) {
      stopListening();
    } else {
      isManualStopRef.current = false;
      stopWakeWordListener();
      startListeningWithRef();
    }
  }

  async function handleCameraToggle() {
    if (cameraEnabled) {
      videoStreamRef.current?.getTracks().forEach((t) => t.stop());
      videoStreamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
      setLiveStream(null);
      setCameraEnabled(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        videoStreamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        setLiveStream(stream);
        setCameraEnabled(true);
      } catch {
        setError("Camera access denied.");
      }
    }
  }

  function handleMicDeviceToggle() {
    if (!micEnabled) {
      setMicEnabled(true);
    } else {
      // Kill both listeners immediately — don't wait for useEffect
      stopWakeWordListener();
      stopListening();
      setMicEnabled(false);
    }
  }

  // ── Override command ──────────────────────────────────────────────────────
  function handleOverrideSubmit() {
    const text = overrideText.trim();
    if (!text) return;
    sendToRumi(text);
    setOverrideText("");
    setOverrideOpen(false);
  }

  // ── Canvas ────────────────────────────────────────────────────────────────
  function handleCanvasDismiss() {
    cancelCreate();
    generated.client.dismiss();
    setCanvasOpen(false);
  }

  function cancelCreate() {
    createRequests.current.cancel(); setCreateProgress("");
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "cancel_create" }));
  }

  function navigateCanvas(index: number) {
    cancelCreate(); generated.client.dismiss(); setCanvasIndex(index);
  }

  function openCanvas(item: CanvasContent) {
    generated.client.dismiss();
    setCanvasHistory(prev => {
      const next = [...prev, item];
      setCanvasIndex(next.length - 1);
      return next;
    });
    setCanvasOpen(true);
    if (isMobileDevice) {
      setActiveMobileTab("canvas");
    }
  }

  // ── Audio interrupt helper ────────────────────────────────────────────────
  // Stops all currently playing audio sources immediately (synchronous).
  // Does NOT close the AudioContext — closing is async and the context keeps
  // playing during the close, which was causing two voices simultaneously.
  function stopAllAudio() {
    audioGenRef.current++;          // invalidate any chunks still waiting in the chain
    activeSourcesRef.current.forEach(s => { try { s.stop(0); } catch { /* already stopped */ } });
    activeSourcesRef.current = [];
    nextPlayTimeRef.current = 0;
    setSpeaking(false);
  }

  // ── Audio playback ────────────────────────────────────────────────────────
  // Uses a sequential promise chain (audioChainRef) so chunks always schedule
  // in arrival order — no race on nextPlayTimeRef regardless of WS batching.
  // audioGenRef lets stopAllAudio() cancel chunks still waiting in the chain.
  function playAudio(b64: string, serverGenId?: number) {
    if (serverGenId !== undefined && serverGenId < audioGenRef.current) {
      return; // Discard stale audio from prior generation immediately
    }
    const myGen = audioGenRef.current;

    // Decode PCM synchronously before entering the chain — keeps chain slots short.
    const raw = atob(b64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const sampleCount = Math.floor(bytes.byteLength / 2); // PCM16 = 2 bytes/sample
    const int16 = new Int16Array(bytes.buffer, 0, sampleCount);
    const float32 = new Float32Array(sampleCount);
    for (let i = 0; i < sampleCount; i++) float32[i] = int16[i] / 32768;

    audioChainRef.current = audioChainRef.current.then(async () => {
      // Chunk was cancelled by stopAllAudio() while waiting in the chain
      if (audioGenRef.current !== myGen || (serverGenId !== undefined && serverGenId < audioGenRef.current)) return;

      try {
        if (!playCtxRef.current) playCtxRef.current = new AudioContext({ sampleRate: 24000 });
        const ctx = playCtxRef.current;

        // Await resume so source.start() never fires on a suspended context.
        // Safe here because the chain serialises calls — no concurrent awaits.
        if (ctx.state === "suspended") await ctx.resume();

        if (audioGenRef.current !== myGen || (serverGenId !== undefined && serverGenId < audioGenRef.current)) return;

        const buffer = ctx.createBuffer(1, float32.length, 24000);
        buffer.copyToChannel(float32, 0);
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);

        // Anchor nextPlayTime when it drifts behind now or jumps >10s ahead
        const now = ctx.currentTime;
        if (nextPlayTimeRef.current < now || nextPlayTimeRef.current > now + 10) {
          nextPlayTimeRef.current = now + 0.05;
        }
        source.start(nextPlayTimeRef.current);
        nextPlayTimeRef.current += buffer.duration;

        activeSourcesRef.current.push(source);
        setSpeaking(true);
        source.onended = () => {
          activeSourcesRef.current = activeSourcesRef.current.filter(s => s !== source);
          if (activeSourcesRef.current.length === 0) setSpeaking(false);
        };
      } catch (e) {
        console.error("playAudio error:", e);
        setSpeaking(false);
      }
    }).catch(() => { setSpeaking(false); });
  }

  // ── WS message handler ────────────────────────────────────────────────────
  function handleWsMessage(msg: WsMessage) {
    if (msg.type === "create_status") {
      if (!createRequests.current.current(msg.request_id) || !canvasContextRef.current.allowed) return;
      setCreateProgress(msg.stage === "failed" ? (msg.message || "Could not update the tracker.") : CREATE_PROGRESS[msg.stage] || "");
      if (msg.stage === "failed" || msg.stage === "ready") setIsProcessing(false);
      if (msg.stage === "failed" && msg.reload_artifact_id && createRequests.current.matchesTarget(msg.request_id, msg.reload_artifact_id)) {
        const current = () => createRequests.current.current(msg.request_id) && canvasContextRef.current.allowed;
        void generated.client.loadIfCurrent(msg.reload_artifact_id, current).then(() => {
          if (current() && generated.client.snapshot().artifact) setCreateProgress("Tracker reloaded. Please try the change again.");
        }).catch(() => {});
      }
    } else if (msg.type === "generated_artifact") {
      const result = createRequests.current.result(msg.result);
      if (!result || !canvasContextRef.current.allowed) return;
      const current = () => createRequests.current.current(result.request_id) && canvasContextRef.current.allowed;
      void generated.client.loadIfCurrent(result.artifact_id, current).then(() => {
        const artifact = generated.client.snapshot().artifact;
        if (!current() || !artifact || artifact.artifact_id !== result.artifact_id) return;
        const reference = canvasFromHistory({ kind: "generated_ui", artifact_id: artifact.artifact_id,
          title: artifact.title, timestamp: artifact.updated_at });
        setCanvasHistory(previous => {
          const index = previous.findIndex(item => item.artifact_id === artifact.artifact_id);
          if (index >= 0) { setCanvasIndex(index); return previous.map((item, i) => i === index ? reference : item); }
          setCanvasIndex(previous.length); return [...previous, reference];
        });
        setCanvasOpen(true); setActiveMobileTab("canvas"); setCreateProgress("Ready"); setIsProcessing(false);
      }).catch(() => { if (current()) setCreateProgress("Could not open the tracker. Please reload."); });
    } else if (msg.type === "intervention") {
      const m = msg as InterventionMessage;
      setInterventionQueue(q => [...q, { interactionId: m.interaction_id, trigger: m.trigger, text: m.text }]);
      const emotionMap: Record<string, typeof rumiEmotion> = { A: "concerned", B: "thinking", C: "concerned", E: "happy", G: "neutral" };
      setRumiEmotion(emotionMap[m.trigger] ?? "neutral");
    } else if (msg.type === "audio_interrupt") {
      if (msg.generation_id !== undefined && msg.generation_id > audioGenRef.current) {
        audioGenRef.current = msg.generation_id;
      }
      stopAllAudio();
      window.speechSynthesis.cancel();
    } else if (msg.type === "audio_response") {
      setRumiEmotion(prev => prev === "neutral" || prev === "thinking" ? "happy" : prev);
      playAudio(msg.data, msg.generation_id);
    } else if (msg.type === "canvas_history") {
      const items = msg.items.map(canvasFromHistory);
      if (items.length > 0) { setCanvasHistory(items); setCanvasIndex(items.length - 1); }
    } else if (msg.type === "text_response") {
      if (msg.request_id && !createRequests.current.current(msg.request_id)) return;
      if (processingTimeoutRef.current) { clearTimeout(processingTimeoutRef.current); processingTimeoutRef.current = null; }
      setIsProcessing(false);
      setIsFollowingUp(false);
      setTranscript("");
      const m = msg;
      const stamp = new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" });
      const exchange: CanvasExchange = {
        query: lastSentQueryRef.current || "",
        response: m.content,
        type: (m.content_type as "text" | "code" | "markdown") ?? "markdown",
        timestamp: stamp,
        attachment: pendingAttachmentRef.current ?? undefined,
      };
      pendingAttachmentRef.current = null;
      if (m.append) {
        // Append to current canvas session
        setCanvasHistory(prev => {
          const next = [...prev];
          const idx = next.length - 1;
          if (idx >= 0) next[idx] = { ...next[idx], exchanges: [...next[idx].exchanges, exchange] };
          return next;
        });
      } else {
        // New canvas session
        const newItem: CanvasContent = { title: m.title, timestamp: stamp, exchanges: [exchange] };
        setCanvasHistory(prev => { const next = [...prev, newItem]; setCanvasIndex(next.length - 1); return next; });
      }
      setCanvasOpen(true);
    } else if (msg.type === "detection_update") {
      const d = msg;
      // Map detection state → Rumi face emotion (only when Rumi is not speaking)
      if (!speaking) {
        const stateToEmotion: Record<string, "neutral" | "concerned" | "happy" | "thinking"> = {
          frustrated: "concerned",
          coding_block: "thinking",
          focused: "neutral",
          idle: "neutral",
          neutral: "neutral",
        };
        const mapped = stateToEmotion[d.state];
        if (mapped) setRumiEmotion(mapped);
      }
      const newEmotions = d.landmarks ?? {};
      setDetection(prev => ({
        state: d.state,
        confidence: d.confidence,
        cues: d.cues ?? [],
        emotions: Object.keys(newEmotions).length > 0 ? newEmotions : (prev?.emotions ?? {}),
        face_detected: d.face_detected !== undefined ? d.face_detected : (Object.keys(newEmotions).length > 0),
        detector_status: d.detector_status ?? "ready",
      }));
    } else if (msg.type === "memory_updated") {
      const m = msg as { type: string; message: string };
      setMemoryToast(m.message);
      setTimeout(() => setMemoryToast(null), 6000);
    } else if (msg.type === "identity_verified") {
      setIdentityVerified(true);
      setArtifactAuthorizationSignal(value => value + 1);
    } else if (msg.type === "guest_detected") {
      cancelCreate(); canvasContextRef.current.allowed = false;
      generated.client.revoke();
      setGuestMode(true);
      setIdentityVerified(false);
      setRumiEmotion("neutral");
      sessionStorage.setItem("rumiGuestMode", "true");
    } else if (msg.type === "owner_returned") {
      setArtifactAuthorizationSignal(value => value + 1);
      setGuestMode(false);
      setIdentityVerified(true);
      sessionStorage.removeItem("rumiGuestMode");
      setRumiEmotion("happy");
      setTimeout(() => setRumiEmotion("neutral"), 3000);
    } else if (msg.type === "known_person_detected") {
      const m = msg as { type: string; name: string; relationship: string };
      setMemoryToast(`${m.name} is here — ${m.relationship}`);
      setTimeout(() => setMemoryToast(null), 6000);
    } else if (msg.type === "profile_updated") {
      const m = msg as { type: string; field: string };
      setMemoryToast(`Profile updated — ${m.field} saved`);
      setTimeout(() => setMemoryToast(null), 4000);
    } else if (msg.type === "known_person_added") {
      const m = msg as { type: string; name: string };
      setMemoryToast(`${m.name} added to known people`);
      setTimeout(() => setMemoryToast(null), 4000);
    } else if (msg.type === "paused") {
      setObservationState("paused");
    } else if (msg.type === "away_mode") {
      cancelCreate(); canvasContextRef.current.allowed = false;
      generated.client.revoke();
      setObservationState("away");
    } else if (msg.type === "presence_returned") {
      setArtifactAuthorizationSignal(value => value + 1);
      setObservationState("active");
      setMemoryToast("Welcome back! Rumi resumed active observation.");
      setTimeout(() => setMemoryToast(null), 4000);
    } else if (msg.type === "error") {
      const m = msg as { type: string; code: string };
      if (m.code === "ARTIFACT_ACCESS_DENIED" || m.code === "CAMERA_UNAVAILABLE") {
        generated.client.revoke();
        setIdentityVerified(false);
      }
      if (m.code === "CAMERA_UNAVAILABLE") setObservationState("degraded");
    }
  }

  function handleInterventionRespond(interactionId: string, response: "accepted" | "dismissed") {
    if (wsRef.current) sendInterventionResponse(wsRef.current, interactionId, response);
    setInterventionQueue(q => q.slice(1));
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  const EMOTION_COLORS: Record<string, string> = {
    happy: "#22c55e", neutral: "#64748b", angry: "#ef4444",
    sad: "#60a5fa", disgust: "#f97316", fear: "#a855f7", surprise: "#eab308",
  };
  const emotionEntries = detection
    ? Object.entries(detection.emotions).sort(([, a], [, b]) => b - a)
    : [];
  const dominantEmotion = emotionEntries[0] ?? null;

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
    <main className="dot-grid noise-overlay" style={{ height: "100dvh", overflow: "hidden", display: "flex", flexDirection: "column", background: "var(--bg)" }}>
      {createProgress && <p role="status" aria-live="polite" style={{ margin: 0, padding: "8px 16px", color: "var(--teal)" }}>{createProgress}</p>}

      {/* Hidden video — always in DOM so captureFrame works */}
      <video ref={videoRef} autoPlay muted playsInline style={{ position: "absolute", width: 1, height: 1, opacity: 0, pointerEvents: "none", top: 0, left: 0 }} />

      {/* Navbar — Clean, calm and consolidated */}
      <nav className="glass sticky top-0 z-20 flex items-center justify-between px-4 sm:px-6 py-3"
        style={{ borderLeft: "none", borderRight: "none", borderTop: "none" }}>
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full" style={{
            backgroundColor: stateColor,
            boxShadow: `0 0 8px ${stateColor}`,
            animation: observationState === "active" && !isTabHidden ? "statusPulse 2s ease-in-out infinite" : "none",
          }} />
          <img src="/rumi-logo.svg" alt="Rumi" style={{ width: 22, height: 22, objectFit: "contain", filter: "brightness(0) saturate(100%) invert(75%) sepia(40%) saturate(500%) hue-rotate(5deg) brightness(95%)" }} />
          <span className="font-display text-gold" style={{ fontSize: "1.25rem", fontWeight: 400, letterSpacing: "0.06em" }}>
            Rumi
          </span>
        </div>

        {/* Center / Right controls */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Consolidated Level 3 Status Menu */}
          <RumiStatusMenu
            observationState={observationState}
            cameraStatus={
              !cameraEnabled
                ? "disabled"
                : observationState === "active"
                ? (isTabHidden ? "available" : "observing")
                : observationState === "paused"
                ? "paused"
                : "available"
            }
            micStatus={
              !micEnabled
                ? "disabled"
                : isTalking
                ? "listening"
                : wakeListening
                ? "wake_listening"
                : "available"
            }
            guestMode={guestMode}
            identityVerified={identityVerified}
            memoryCandidatesCount={pendingCandidatesCount}
            onToggleCamera={handleCameraToggle}
            onToggleMic={handleMicDeviceToggle}
            onOpenMemoryCenter={() => router.push("/profile")}
          />

          {process.env.NEXT_PUBLIC_ARTIFACT_PROOF_MODE === "1" && (
            <div className="flex flex-wrap gap-2 text-xs" aria-label="Study tracker preview controls">
              <button className="btn-ghost min-h-11" disabled={!artifactAllowed || generated.busy} onClick={() => {
                setCanvasOpen(true); setActiveMobileTab("canvas");
                void generated.client.proof().catch(() => {});
              }}>Load study tracker</button>
              {generated.artifact && <button className="btn-ghost min-h-11" disabled={generated.busy} onClick={() => {
                void generated.client.setGraph(!generated.artifact!.spec.show_daily_graph).catch(() => {});
              }}>{generated.artifact.spec.show_daily_graph ? "Hide graph" : "Show graph"}</button>}
              {generated.error && <span role="alert">{generated.error}</span>}
            </div>
          )}
          {/* Desktop Artifact Canvas Toggle */}
          <button
            type="button"
            onClick={() => setCanvasOpen(o => !o)}
            className={`hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono transition-all ${
              canvasOpen ? "bg-teal/15 text-teal border border-teal/40" : "bg-surface-2 text-muted hover:text-text border border-border"
            }`}
            title="Toggle Artifact Canvas"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
            <span>Canvas</span>
            {canvasHistory.length > 0 && <span className="w-1.5 h-1.5 rounded-full bg-teal" />}
          </button>

          {/* Desktop History Drawer Toggle */}
          <button
            type="button"
            onClick={() => setHistoryOpen(h => !h)}
            className={`hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono transition-all ${
              historyOpen ? "bg-gold/15 text-gold border border-gold/40" : "bg-surface-2 text-muted hover:text-text border border-border"
            }`}
            title="Conversation History"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>History</span>
          </button>

          {/* Memory & Privacy Center */}
          <a href="/profile" className="btn-icon relative" title="Memory & Privacy Center">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
            </svg>
            {pendingCandidatesCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-gold animate-pulse" />
            )}
          </a>

          {/* Pause / Resume button */}
          {sessionId && (
            <PauseButton sessionId={sessionId} observationState={observationState} onStateChange={setObservationState} />
          )}
        </div>
      </nav>

      {/* ── Main Workspace Body ─────────────────────────────────────────── */}
      {isMobileDevice ? (
        /* Mobile Dedicated Tab View */
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden relative pb-16">
          {/* TAB 1: Rumi Core */}
          {activeMobileTab === "rumi" && (
            <div className="flex-1 flex flex-col items-center justify-start gap-3 p-4 overflow-y-auto">
              {/* First-use gentle guidance */}
              {showGuidance && (
                <div
                  className="w-full max-w-sm px-3.5 py-2 rounded-xl flex items-center gap-2 text-xs font-mono animate-fade-up"
                  style={{
                    background: "rgba(201,168,76,0.08)",
                    border: "1px solid rgba(201,168,76,0.3)",
                    color: "var(--gold)",
                  }}
                >
                  <span className="text-sm">✦</span>
                  <span className="flex-1 text-[11px] leading-tight">
                    Tap face for expressions · Tap chest for camera · Tap mic to speak
                  </span>
                  <button onClick={dismissGuidance} className="text-muted hover:text-gold px-1 font-bold">✕</button>
                </div>
              )}

              {/* Greeting */}
              {name ? (
                <p className="rumi-greeting">Hi, {name}</p>
              ) : (
                <div style={{ height: 22, width: 100, borderRadius: 6, background: "var(--surface-2)", animation: "statusPulse 1.5s ease-in-out infinite" }} />
              )}

              {/* Robot with clickable zones */}
              <div className="robot-wrap" style={{ position: "relative", display: "inline-block" }}>
                <RumiFace state={observationState} speaking={speaking} emotion={rumiEmotion} />
                <div className="body-zone zone-head" onClick={() => { setShowCameraPopup(false); setShowEmotionPopup(p => !p); }} />
                <div className="body-zone zone-chest" onClick={() => { setShowEmotionPopup(false); setShowCameraPopup(p => !p); }} />
              </div>

              {/* Zone hints */}
              <div className="flex items-center gap-3 justify-center text-xs font-mono text-muted">
                <span className="zone-tag" onClick={() => setShowEmotionPopup(p => !p)}>
                  Tap face for expressions
                </span>
                <span>·</span>
                <span className="zone-tag" onClick={() => setShowCameraPopup(p => !p)}>
                  Tap chest for camera
                </span>
              </div>

              {/* State description */}
              <p style={{ fontSize: "0.78rem", color: "var(--muted)", margin: 0, textAlign: "center" }}>
                {speaking ? "Rumi is speaking…" : isProcessing ? "Rumi is thinking…"
                  : isTalking ? "Listening — stop talking to send"
                  : observationState === "active" ? "Witnessing. Understanding."
                  : observationState === "degraded" ? "Camera unavailable — text mode"
                  : "Observation paused"}
              </p>

              {/* Begin Observation button if paused */}
              {sessionReady && observationState === "paused" && (
                <div className="text-center mt-2">
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
                    style={{ fontSize: "0.9rem", padding: "0.65rem 2rem" }}
                  >
                    Begin Observation
                  </button>
                  <p className="mt-1 text-xs text-muted">Rumi will start watching when you&apos;re ready</p>
                </div>
              )}

              {/* Talk controls */}
              {observationState !== "paused" && (
                <div className="flex flex-col items-center gap-2 select-none mt-2">
                  {(isTalking || isProcessing) && transcript && (
                    <div className="px-4 py-1.5 rounded-full bg-surface-2 border border-teal/20 max-w-[280px] text-center">
                      <p className="text-xs text-text italic leading-snug">&ldquo;{transcript}&rdquo;</p>
                    </div>
                  )}
                  {isTalking && !isTabHidden && (
                    <div className="flex items-end gap-0.5" style={{ height: 20 }}>
                      {[3,5,8,5,10,6,4,9,6,3].map((h,i) => (
                        <div key={i} style={{ width: 3, borderRadius: 2, backgroundColor: "var(--teal)", height: h*2, animation: `waveBar 0.6s ease-in-out ${i*0.06}s infinite alternate` }} />
                      ))}
                    </div>
                  )}
                  <button
                    onClick={handleMicToggle}
                    disabled={speaking}
                    aria-label={isTalking ? "Stop and send" : "Talk to Rumi"}
                    style={{
                      width: 64, height: 64, borderRadius: "50%",
                      border: `2px solid ${isTalking ? "var(--teal)" : isProcessing ? "var(--gold-dim)" : "var(--border-2)"}`,
                      background: isTalking ? "rgba(34,211,238,0.12)" : isProcessing ? "rgba(201,168,76,0.08)" : "var(--surface)",
                      color: isTalking ? "var(--teal)" : isProcessing ? "var(--gold)" : "var(--muted)",
                      boxShadow: isTalking ? "0 0 24px rgba(34,211,238,0.4), 0 0 48px rgba(34,211,238,0.15)" : isProcessing ? "0 0 20px rgba(201,168,76,0.2)" : "none",
                      transform: isTalking ? "scale(0.95)" : "scale(1)", transition: "all 0.2s ease",
                      cursor: speaking ? "default" : "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}
                  >
                    {isProcessing ? (
                      <span style={{ display: "inline-block", width: 20, height: 20, borderRadius: "50%", border: "2.5px solid var(--gold-dim)", borderTopColor: "var(--gold)", animation: "spin 0.8s linear infinite" }} />
                    ) : speaking ? (
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02z" /></svg>
                    ) : (
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
                        <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" />
                      </svg>
                    )}
                  </button>
                  <p style={{ margin: 0, fontSize: "0.72rem", color: isTalking ? "var(--teal)" : isProcessing ? "var(--gold)" : speaking ? "var(--gold)" : "var(--muted)" }}>
                    {isTalking ? "Tap to finish" : isProcessing ? "Sending to Rumi…" : speaking ? "Rumi is speaking" : "Tap to speak"}
                  </p>
                  {(isProcessing || speaking) && (
                    <button
                      onClick={handleCancel}
                      className="mt-1 px-3 py-1 rounded-full text-xs font-mono border border-gold/30 text-muted hover:text-gold"
                    >
                      ✕ Cancel
                    </button>
                  )}
                  {!isTalking && !isProcessing && !speaking && (
                    <button
                      onClick={() => setOverrideOpen(true)}
                      className="min-h-[44px] px-4 py-2 rounded-full text-xs font-mono flex items-center gap-1.5 text-muted hover:text-teal bg-surface-2 border border-border"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <rect x="2" y="4" width="20" height="16" rx="2" />
                        <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M6 16h12" />
                      </svg>
                      <span>Type command</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Canvas (Full-width dedicated mobile experience) */}
          {activeMobileTab === "canvas" && (
            <div className="flex-1 min-h-0 flex flex-col p-3 overflow-hidden">
              <ArtifactCanvas
                content={visibleCanvas}
                onArtifactEdit={generated.client.edit}
                onArtifactSpecEdit={generated.client.editSpec}
                artifactBusy={generated.busy}
                artifactMessage={!artifactAllowed ? "Verify owner presence to open this tracker." : generated.error || undefined}
                onDismiss={() => { handleCanvasDismiss(); setActiveMobileTab("rumi"); }}
                history={canvasHistory}
                historyIndex={canvasIndex}
                onNavigate={navigateCanvas}
                onFollowUp={handleFollowUp}
                isFollowingUp={isFollowingUp}
              />
            </div>
          )}

          {/* TAB 3: History (Full-width dedicated mobile experience) */}
          {activeMobileTab === "history" && (
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
              <ConversationTimeline
                isOpen={true}
                onClose={() => setActiveMobileTab("rumi")}
                guestMode={guestMode}
                isMobileView={true}
              />
            </div>
          )}

          {/* Mobile Sheets for Camera & Expression */}
          <MobileSheet
            isOpen={showEmotionPopup}
            onClose={() => setShowEmotionPopup(false)}
            title="Expression Analysis"
          >
            <div className="p-4 flex flex-col gap-3">
              {dominantEmotion && detection?.face_detected !== false && cameraEnabled && (
                <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2 border border-border">
                  <span className="text-sm font-semibold uppercase tracking-wider" style={{ color: EMOTION_COLORS[dominantEmotion[0]] ?? "var(--teal)" }}>
                    {dominantEmotion[0]}
                  </span>
                  <span className="text-sm font-mono text-muted">{Math.round(dominantEmotion[1] * 100)}%</span>
                </div>
              )}
              {!cameraEnabled ? (
                <p className="text-xs text-muted text-center py-4 font-mono">Camera unavailable</p>
              ) : detection?.detector_status === "unavailable" ? (
                <p className="text-xs text-muted text-center py-4 font-mono">Expression detection unavailable</p>
              ) : detection?.detector_status === "loading" ? (
                <p className="text-xs text-muted text-center py-4 font-mono">Loading expression model...</p>
              ) : emotionEntries.length > 0 && detection?.face_detected !== false ? (
                <div className="flex flex-col gap-2">
                  {emotionEntries.map(([emotion, score]) => (
                    <div key={emotion} className="flex items-center gap-3">
                      <span className="w-16 text-xs text-muted font-mono capitalize">{emotion}</span>
                      <div className="flex-1 h-2 bg-surface-2 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${Math.round(score * 100)}%`, background: EMOTION_COLORS[emotion] ?? "var(--teal)" }}
                        />
                      </div>
                      <span className="w-8 text-xs font-mono text-muted text-right">{Math.round(score * 100)}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted text-center py-4 font-mono">No face detected</p>
              )}
            </div>
          </MobileSheet>

          <MobileSheet
            isOpen={showCameraPopup}
            onClose={() => setShowCameraPopup(false)}
            title="Camera Preview"
          >
            <div className="p-4 flex flex-col gap-3">
              <div className="relative aspect-video rounded-xl overflow-hidden bg-surface-2 border border-border">
                <video
                  ref={(el) => {
                    if (el && liveStream && isMobileDevice && showCameraPopup) {
                      el.srcObject = liveStream;
                      el.play().catch(() => {});
                    }
                  }}
                  autoPlay
                  muted
                  playsInline
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: cameraEnabled ? "block" : "none" }}
                />
                {!cameraEnabled && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round">
                      <line x1="1" y1="1" x2="23" y2="23" />
                      <path d="M16.5 16.5H4a2 2 0 01-2-2V7a2 2 0 012-2h1.5M20 8.5V17a2 2 0 01-2 2h-.5M22 10.5l-4-4" />
                    </svg>
                    <span className="text-xs font-mono text-error uppercase tracking-wider">Camera Off</span>
                    <span className="text-[11px] text-muted">Rumi cannot see you</span>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCameraToggle}
                  className="flex-1 min-h-[44px] py-2.5 px-4 rounded-xl text-xs font-mono font-medium border flex items-center justify-center gap-2"
                  style={{
                    background: cameraEnabled ? "rgba(34,211,238,0.1)" : "rgba(239,68,68,0.1)",
                    borderColor: cameraEnabled ? "rgba(34,211,238,0.3)" : "rgba(239,68,68,0.3)",
                    color: cameraEnabled ? "var(--teal)" : "#ef4444",
                  }}
                >
                  <span>{cameraEnabled ? "Camera Active (Tap to Disable)" : "Camera Off (Tap to Enable)"}</span>
                </button>
              </div>
            </div>
          </MobileSheet>

          {/* Mobile Bottom Navigation */}
          <MobileNavigation
            activeTab={activeMobileTab}
            onTabChange={(tab) => {
              if (tab === "memory") router.push("/profile");
              else setActiveMobileTab(tab);
            }}
            hasCanvasContent={canvasHistory.length > 0}
          />
        </div>
      ) : (
        /* Desktop Two-Zone Fluid Layout */
        <div className={`app-body${canvasOpen ? " canvas-open" : ""}`} style={{ position: "relative" }}>
          {/* ZONE 1 — Rumi Core */}
          <div className="rumi-zone">
            <div className="rumi-stage">
              {/* Guidance tip on desktop */}
              {showGuidance && (
                <div
                  className="mx-auto mb-1 px-3.5 py-1.5 rounded-full flex items-center gap-2 text-xs font-mono animate-fade-up"
                  style={{
                    background: "rgba(201,168,76,0.08)",
                    border: "1px solid rgba(201,168,76,0.3)",
                    color: "var(--gold)",
                  }}
                >
                  <span style={{ fontSize: "0.85rem" }}>✦</span>
                  <span className="text-[11px] leading-tight">
                    Tap face for expressions · Tap chest for camera · Press Space to speak
                  </span>
                  <button onClick={dismissGuidance} className="text-muted hover:text-gold px-1 font-bold">✕</button>
                </div>
              )}

              {/* Greeting */}
              {name ? (
                <p className="rumi-greeting">Hi, {name}</p>
              ) : (
                <div style={{ height: 22, width: 100, borderRadius: 6, background: "var(--surface-2)", animation: "statusPulse 1.5s ease-in-out infinite" }} />
              )}

              {/* Robot — Clickable body zones */}
              <div className="robot-wrap" style={{ position: "relative", display: "inline-block" }}>
                <RumiFace state={observationState} speaking={speaking} emotion={rumiEmotion} />

                {/* Zone: head → expression panel */}
                <div className="body-zone zone-head" onClick={() => {
                  setShowCameraPopup(false);
                  setShowEmotionPopup(p => !p);
                }} />

                {/* Zone: chest → camera panel */}
                <div className="body-zone zone-chest" onClick={() => {
                  setShowEmotionPopup(false);
                  setShowCameraPopup(p => !p);
                }} />

                {/* ── Expression HUD panel (Desktop) ───────────────────────── */}
                {showEmotionPopup && (
                  <div className="hud-panel popup-head">
                    <div className="hud-corner tl"/><div className="hud-corner tr"/>
                    <div className="hud-corner bl"/><div className="hud-corner br"/>
                    <div className="hud-header">
                      <span className="hud-live-dot" />
                      <span className="hud-title">Expression Analysis</span>
                      <button className="hud-close" onClick={(e) => { e.stopPropagation(); setShowEmotionPopup(false); }}>✕</button>
                    </div>
                    {dominantEmotion && detection?.face_detected !== false && cameraEnabled && (
                      <div className="hud-dominant">
                        <span style={{ color: EMOTION_COLORS[dominantEmotion[0]] ?? "var(--teal)" }}>
                          {dominantEmotion[0].toUpperCase()}
                        </span>
                        <span className="hud-dominant-score">{Math.round(dominantEmotion[1] * 100)}%</span>
                      </div>
                    )}
                    <div className="hud-divider" />
                    {!cameraEnabled ? (
                      <p className="hud-empty">Camera unavailable</p>
                    ) : detection?.detector_status === "unavailable" ? (
                      <p className="hud-empty">Expression detection unavailable</p>
                    ) : detection?.detector_status === "loading" ? (
                      <p className="hud-empty">Loading expression model...</p>
                    ) : emotionEntries.length > 0 && detection?.face_detected !== false ? (
                      emotionEntries.map(([emotion, score]) => (
                        <div key={emotion} className="hud-row">
                          <span className="hud-label">{emotion}</span>
                          <div className="hud-bar-track">
                            <div className="hud-bar-fill" style={{ width: `${Math.round(score * 100)}%`, background: EMOTION_COLORS[emotion] ?? "var(--teal)" }} />
                          </div>
                          <span className="hud-value">{Math.round(score * 100)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="hud-empty">No face detected</p>
                    )}
                  </div>
                )}

                {/* ── Camera HUD panel (Desktop) ──────────────────────────── */}
                {showCameraPopup && (
                  <div className="hud-panel popup-chest">
                    <div className="hud-corner tl"/><div className="hud-corner tr"/>
                    <div className="hud-corner bl"/><div className="hud-corner br"/>
                    <div className="hud-header">
                      {observationState === "active" && cameraEnabled && <span className="hud-live-dot" />}
                      <span className="hud-title">Camera Preview</span>
                      <button className="hud-close" onClick={(e) => { e.stopPropagation(); setShowCameraPopup(false); }}>✕</button>
                    </div>
                    <div className="hud-video-wrap" style={{ borderColor: observationState === "active" ? "var(--teal)" : "var(--border)", boxShadow: observationState === "active" ? "0 0 10px rgba(34,211,238,0.15)" : "none" }}>
                      <video ref={cameraPopupVideoRef} autoPlay muted playsInline
                        style={{ width: "100%", height: "100%", objectFit: "cover", display: cameraEnabled ? "block" : "none" }} />
                      {!cameraEnabled && (
                        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, background: "rgba(4,8,15,0.92)" }}>
                          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round">
                            <line x1="1" y1="1" x2="23" y2="23"/>
                            <path d="M16.5 16.5H4a2 2 0 01-2-2V7a2 2 0 012-2h1.5M20 8.5V17a2 2 0 01-2 2h-.5M22 10.5l-4-4"/>
                          </svg>
                          <span style={{ fontSize: "0.65rem", letterSpacing: "0.15em", textTransform: "uppercase", color: "#ef4444", fontWeight: 700 }}>Camera Off</span>
                          <span style={{ fontSize: "0.58rem", color: "var(--muted)", textAlign: "center", lineHeight: 1.4, padding: "0 8px" }}>Rumi cannot see you</span>
                        </div>
                      )}
                      {observationState === "active" && cameraEnabled && !isTabHidden && (
                        <div style={{ position: "absolute", top: 6, left: 6, width: 6, height: 6, borderRadius: "50%", background: "var(--teal)", boxShadow: "0 0 6px rgba(34,211,238,0.9)", animation: "statusPulse 2s ease-in-out infinite" }} />
                      )}
                    </div>
                    <div className="hud-divider" />
                    <div className="hud-controls">
                      <button onClick={handleCameraToggle} className={`hud-ctrl-btn ${cameraEnabled ? "active-teal" : "active-red"}`} title={cameraEnabled ? "Disable camera — Rumi will stop seeing you" : "Enable camera"}>
                        {cameraEnabled ? (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M18 10.5V6a2 2 0 00-2-2H4a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-4.5l4 4v-11l-4 4z"/></svg>
                        ) : (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.5 16.5H4a2 2 0 01-2-2V7a2 2 0 012-2h1.5M20 8.5V17a2 2 0 01-2 2h-.5M22 10.5l-4-4"/></svg>
                        )}
                        <span>{cameraEnabled ? "Cam On" : "Cam Off — not seeing"}</span>
                      </button>
                      <button onClick={handleMicDeviceToggle} className={`hud-ctrl-btn ${micEnabled ? "active-gold" : "active-red"}`} title={micEnabled ? "Disable mic — Rumi will stop listening" : "Enable mic"}>
                        {micEnabled ? (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z"/><path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z"/></svg>
                        ) : (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V5a3 3 0 00-5.94-.6M17 16.95A7 7 0 015 12v-2m14 0v2a7 7 0 01-.11 1.23M12 19v3M8 23h8"/></svg>
                        )}
                        <span>{micEnabled ? "Mic On" : "Mic Off — not hearing"}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Zone hints */}
              <div style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "center" }}>
                <span className="zone-tag" onClick={() => setShowEmotionPopup(p => !p)}>
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                  Tap face for expressions
                </span>
                <span style={{ color: "var(--border)", fontSize: "0.5rem", opacity: 0.4 }}>·</span>
                <span className="zone-tag" onClick={() => setShowCameraPopup(p => !p)}>
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                  Tap chest for camera
                </span>
              </div>

              {/* Status */}
              <p style={{ fontSize: "0.78rem", color: "var(--muted)", margin: 0, textAlign: "center" }}>
                {speaking ? "Rumi is speaking…" : isProcessing ? "Rumi is thinking…"
                  : isTalking ? "Listening — stop talking to send"
                  : observationState === "active" ? "Witnessing. Understanding."
                  : observationState === "degraded" ? "Camera unavailable — text mode"
                  : "Observation paused"}
              </p>

              {/* Begin observation */}
              {sessionReady && observationState === "paused" && (
                <div style={{ textAlign: "center" }}>
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
                    style={{ fontSize: "0.9rem", padding: "0.65rem 2rem" }}
                  >
                    Begin Observation
                  </button>
                  <p style={{ marginTop: 5, fontSize: "0.7rem", color: "var(--muted)" }}>Rumi will start watching when you&apos;re ready</p>
                </div>
              )}

              {/* Talk controls */}
              {observationState !== "paused" && (
                <div className="select-none" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  {/* Subtitle */}
                  {(isTalking || isProcessing) && transcript && (
                    <div style={{
                      padding: "5px 16px", borderBottom: "1px solid rgba(34,211,238,0.12)",
                      background: "rgba(4,8,15,0.65)", backdropFilter: "blur(10px)",
                      borderRadius: 20, maxWidth: 280, textAlign: "center",
                    }}>
                      <p style={{
                        margin: 0, fontSize: "0.8rem",
                        color: isTalking ? "var(--text)" : "var(--muted)",
                        fontStyle: isProcessing ? "italic" : "normal",
                        letterSpacing: "0.01em",
                      }}>&ldquo;{transcript}&rdquo;</p>
                    </div>
                  )}
                  {isTalking && !isTabHidden && (
                    <div className="flex items-end gap-0.5" style={{ height: 20 }}>
                      {[3,5,8,5,10,6,4,9,6,3].map((h,i) => (
                        <div key={i} style={{ width: 3, borderRadius: 2, backgroundColor: "var(--teal)", height: h*2, animation: `waveBar 0.6s ease-in-out ${i*0.06}s infinite alternate` }} />
                      ))}
                    </div>
                  )}
                  <button
                    onClick={handleMicToggle}
                    disabled={speaking}
                    aria-label={isTalking ? "Stop and send" : "Talk to Rumi"}
                    style={{
                      width: 64, height: 64, borderRadius: "50%",
                      border: `2px solid ${isTalking ? "var(--teal)" : isProcessing ? "var(--gold-dim)" : "var(--border-2)"}`,
                      background: isTalking ? "rgba(34,211,238,0.12)" : isProcessing ? "rgba(201,168,76,0.08)" : "var(--surface)",
                      color: isTalking ? "var(--teal)" : isProcessing ? "var(--gold)" : "var(--muted)",
                      boxShadow: isTalking ? "0 0 24px rgba(34,211,238,0.4), 0 0 48px rgba(34,211,238,0.15)" : isProcessing ? "0 0 20px rgba(201,168,76,0.2)" : "none",
                      transform: isTalking ? "scale(0.95)" : "scale(1)", transition: "all 0.2s ease",
                      cursor: speaking ? "default" : "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}
                  >
                    {isProcessing ? (
                      <span style={{ display: "inline-block", width: 20, height: 20, borderRadius: "50%", border: "2.5px solid var(--gold-dim)", borderTopColor: "var(--gold)", animation: "spin 0.8s linear infinite" }} />
                    ) : speaking ? (
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02z" /></svg>
                    ) : (
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
                        <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z" />
                      </svg>
                    )}
                  </button>
                  {/* Status label under mic */}
                  <p style={{ margin: 0, fontSize: "0.72rem", color: isTalking ? "var(--teal)" : isProcessing ? "var(--gold)" : speaking ? "var(--gold)" : "var(--muted)" }}>
                    {isTalking ? "Tap or Space to send" : isProcessing ? "Sending to Rumi…" : speaking ? "Rumi is speaking" : "Tap or Space to speak"}
                  </p>
                  {(isProcessing || speaking) && (
                    <button
                      onClick={handleCancel}
                      style={{
                        marginTop: 2, background: "transparent", border: "1px solid rgba(201,168,76,0.25)",
                        borderRadius: 99, padding: "3px 14px", cursor: "pointer",
                        color: "var(--muted)", fontSize: "0.68rem", letterSpacing: "0.04em",
                      }}
                    >
                      ✕ Cancel
                    </button>
                  )}
                  {/* Screen share button (desktop only) */}
                  {!isTalking && !isProcessing && !speaking && supportsScreenShare && (
                    <button
                      onClick={screenActive ? stopScreenShare : startScreenShare}
                      title={screenActive ? "Stop screen sharing" : "Share screen with Rumi"}
                      style={{
                        display: "flex", alignItems: "center", gap: 5,
                        background: screenActive ? "rgba(34,211,238,0.12)" : "rgba(34,211,238,0.06)",
                        border: `1px solid ${screenActive ? "rgba(34,211,238,0.5)" : "rgba(34,211,238,0.18)"}`,
                        borderRadius: 99, padding: "5px 14px", cursor: "pointer",
                        color: screenActive ? "var(--teal)" : "var(--muted)", transition: "all 0.15s",
                      }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
                      </svg>
                      <span style={{ fontSize: "0.72rem" }}>{screenActive ? "Sharing screen" : "Share screen"}</span>
                      {screenActive && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--teal)", animation: "pulseRing 1.5s infinite" }} />}
                    </button>
                  )}
                  {/* Type button */}
                  {!isTalking && !isProcessing && !speaking && (
                    <button
                      onClick={() => setOverrideOpen(true)}
                      style={{
                        display: "flex", alignItems: "center", gap: 5,
                        background: "rgba(34,211,238,0.06)", border: "1px solid rgba(34,211,238,0.18)",
                        borderRadius: 99, padding: "5px 14px", cursor: "pointer",
                        color: "var(--muted)", transition: "all 0.15s",
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = "rgba(34,211,238,0.12)"; e.currentTarget.style.color = "var(--teal)"; }}
                      onMouseLeave={e => { e.currentTarget.style.background = "rgba(34,211,238,0.06)"; e.currentTarget.style.color = "var(--muted)"; }}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="2" y="4" width="20" height="16" rx="2"/>
                        <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M6 16h12"/>
                      </svg>
                      <span style={{ fontSize: "0.65rem", letterSpacing: "0.06em" }}>Type</span>
                    </button>
                  )}
                  {/* Wake word standby indicator */}
                  {wakeListening && !isTalking && !isProcessing && !speaking && (
                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <div style={{
                        width: 5, height: 5, borderRadius: "50%",
                        background: "var(--teal)", opacity: 0.55,
                        animation: !isTabHidden ? "statusPulse 2.4s ease-in-out infinite" : "none",
                      }} />
                      <span style={{ fontSize: "0.58rem", color: "var(--muted)", opacity: 0.7, letterSpacing: "0.06em" }}>
                        Say &ldquo;Hey Rumi&rdquo;
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ZONE 2 — Artifact Canvas (Desktop Side-by-Side) */}
          <div className={`canvas-zone${canvasOpen ? " canvas-open" : ""}`} style={{
            position: "relative",
            filter: guestMode ? "blur(10px) saturate(0.2)" : "none",
            transition: "filter 0.5s ease",
            pointerEvents: guestMode ? "none" : "auto",
          }}>
            <ArtifactCanvas
              content={visibleCanvas}
              onArtifactEdit={generated.client.edit}
              onArtifactSpecEdit={generated.client.editSpec}
              artifactBusy={generated.busy}
              artifactMessage={!artifactAllowed ? "Verify owner presence to open this tracker." : generated.error || undefined}
              onDismiss={handleCanvasDismiss}
              history={canvasHistory}
              historyIndex={canvasIndex}
              onNavigate={navigateCanvas}
              onFollowUp={handleFollowUp}
              isFollowingUp={isFollowingUp}
            />
          </div>

          {/* Desktop Canvas pull tab — visible when canvas closed */}
          {observationState !== "paused" && !canvasOpen && (
            <div
              className="canvas-pull-tab"
              onClick={() => setCanvasOpen(true)}
              title="Open artifact canvas"
            >
              <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="9 18 15 12 9 6"/></svg>
              <span>CANVAS</span>
            </div>
          )}

          {/* Desktop History Drawer */}
          <ConversationTimeline
            isOpen={historyOpen}
            onClose={() => setHistoryOpen(false)}
            guestMode={guestMode}
            isMobileView={false}
          />
        </div>
      )}

      {/* Guest Mode privacy overlay */}
      {guestMode && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 30,
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          background: "rgba(4,8,15,0.55)", backdropFilter: "blur(2px)",
          animation: "fadeSlideUp 0.4s ease both",
          pointerEvents: "none",
        }}>
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
            padding: "20px 32px", borderRadius: 16,
            background: "rgba(4,8,15,0.8)", border: "1px solid rgba(239,68,68,0.3)",
            boxShadow: "0 0 40px rgba(239,68,68,0.08)",
          }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round">
              <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>
            </svg>
            <span style={{ fontSize: "0.75rem", letterSpacing: "0.2em", textTransform: "uppercase", color: "#ef4444", fontWeight: 700 }}>Session Locked</span>
            <span style={{ fontSize: "0.65rem", color: "var(--muted)", letterSpacing: "0.05em", textAlign: "center" }}>
              Rumi has protected this workspace.<br/>Owner identity required to continue.
            </span>
          </div>
        </div>
      )}

      {/* Intervention card — fixed overlay */}
      {intervention && (
        <div style={{
          position: "fixed", bottom: isMobileDevice ? 75 : 90, left: "50%", transform: "translateX(-50%)",
          zIndex: 50, width: "min(420px, calc(100vw - 32px))",
          animation: "interventionIn 0.3s ease",
        }}>
          <InterventionCard
            interactionId={intervention.interactionId}
            trigger={intervention.trigger}
            text={intervention.text}
            onRespond={handleInterventionRespond}
          />
        </div>
      )}

      {/* Override command — slides up from bottom */}
      <div className={`override-panel${overrideOpen ? " open" : ""}`}>
        <span style={{ color: "var(--teal)", fontSize: "0.85rem", flexShrink: 0, fontFamily: "monospace" }}>›</span>
        <input
          ref={overrideInputRef}
          type="text"
          value={overrideText}
          onChange={e => setOverrideText(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter") handleOverrideSubmit();
            if (e.key === "Escape") { setOverrideOpen(false); setOverrideText(""); }
          }}
          placeholder="Override command… (or press Space to speak)"
          style={{
            flex: 1, background: "rgba(10,20,34,0.92)", color: "var(--text)",
            border: "1px solid rgba(34,211,238,0.28)", borderRadius: 999,
            padding: "0.6rem 1.1rem", fontSize: "0.82rem", fontFamily: "inherit",
            outline: "none", transition: "border-color 0.2s",
          }}
          onFocus={e => (e.currentTarget.style.borderColor = "rgba(34,211,238,0.6)")}
          onBlur={e => (e.currentTarget.style.borderColor = "rgba(34,211,238,0.28)")}
        />
        <button
          onClick={handleOverrideSubmit}
          className="btn-primary"
          style={{ padding: "0.6rem 1.3rem", fontSize: "0.78rem", borderRadius: 999, flexShrink: 0 }}
        >
          Send
        </button>
        <button
          onClick={() => { setOverrideOpen(false); setOverrideText(""); }}
          style={{
            background: "none", border: "none", color: "var(--muted)", cursor: "pointer",
            fontSize: "1rem", padding: "0 4px", lineHeight: 1, flexShrink: 0,
          }}
          title="Close (Esc)"
        >✕</button>
      </div>

      {/* Guest mode banner */}
      {guestMode && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, zIndex: 60,
          background: "rgba(201,168,76,0.08)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(201,168,76,0.25)",
          padding: "10px 20px",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          animation: "fadeSlideUp 0.3s ease",
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--gold)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
          </svg>
          <span style={{ fontSize: "0.8rem", color: "var(--gold)" }}>
            Guest mode — <strong>{name}</strong> isn&apos;t at their desk. Rumi is here to help.
          </span>
          <span style={{
            marginLeft: 8,
            fontSize: "0.68rem",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "#ef4444",
            border: "1px solid rgba(239, 68, 68, 0.4)",
            borderRadius: 4,
            padding: "2px 6px",
            fontWeight: 600,
          }}>
            Locked
          </span>
        </div>
      )}

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
        @keyframes popupIn {
          from { opacity: 0; transform: scale(0.96); }
          to   { opacity: 1; transform: scale(1); }
        }

        /* ── Fluid zones ───────────────────────────────────────────────── */
        .app-body {
          flex: 1;
          display: grid;
          grid-template-columns: 1fr 0fr;
          min-height: 0;
          overflow: hidden;
          transition: grid-template-columns 0.55s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .app-body.canvas-open {
          grid-template-columns: minmax(300px, 36fr) 64fr;
        }
        @media (min-width: 1200px) {
          .app-body.canvas-open {
            grid-template-columns: 30fr 70fr;
          }
        }
        .rumi-zone {
          display: flex;
          flex-direction: column;
          min-width: 0;
          min-height: 0;
          overflow: visible;
          position: relative;
        }
        .canvas-zone {
          min-width: 0;
          min-height: 0;
          overflow: hidden;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.38s ease 0.2s;
        }
        .canvas-zone.canvas-open {
          opacity: 1;
          pointer-events: auto;
        }

        /* ── Override command panel ─────────────────────────────────────── */
        .override-panel {
          position: fixed;
          bottom: 0; left: 0; right: 0;
          z-index: 60;
          padding: 12px 20px 24px;
          background: linear-gradient(to top, rgba(4,8,15,0.98) 55%, transparent);
          display: flex;
          align-items: center;
          gap: 10px;
          transform: translateY(110%);
          transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .override-panel.open {
          transform: translateY(0);
        }

        /* ── Rumi stage ────────────────────────────────────────────────── */
        .rumi-stage {
          flex: 1; display: flex; flex-direction: column; align-items: center;
          justify-content: flex-start; gap: 8px; overflow-y: auto; overflow-x: hidden;
          padding: clamp(6px, 2vh, 24px) 16px 16px;
          min-height: 0;
          scrollbar-width: none;
        }
        .rumi-stage::-webkit-scrollbar { display: none; }
        .rumi-greeting {
          font-family: var(--font-cormorant), 'Cormorant Garamond', serif;
          font-size: clamp(1.1rem, 3vw, 1.5rem); color: var(--gold);
          font-weight: 400; letter-spacing: 0.06em; margin: 0;
        }

        /* ── Clickable zones ────────────────────────────────────────────── */
        .body-zone {
          position: absolute; cursor: pointer; border-radius: 40%;
          transition: background 0.15s ease;
        }
        .body-zone:hover { background: rgba(255,255,255,0.05); }
        .zone-head  { top: 2%;  left: 20%; width: 60%; height: 20%; }
        .zone-chest { top: 24%; left: 14%; width: 72%; height: 24%; border-radius: 12px; }

        /* ── Zone tag hints ─────────────────────────────────────────────── */
        .zone-tag {
          display: inline-flex; align-items: center; gap: 4px;
          font-size: 0.52rem; letter-spacing: 0.06em;
          color: var(--muted); cursor: pointer; opacity: 0.6;
          transition: opacity 0.15s ease, color 0.15s ease;
          user-select: none;
        }
        .zone-tag:hover { opacity: 1; color: var(--text); }

        /* ── HUD panel base ─────────────────────────────────────────────── */
        .hud-panel {
          position: absolute; z-index: 30;
          background: rgba(4, 8, 15, 0.92);
          backdrop-filter: blur(18px);
          border: 1px solid rgba(34,211,238,0.18);
          border-radius: 10px;
          padding: 10px 12px;
          width: 200px;
          animation: popupIn 0.16s ease;
          box-shadow: 0 0 0 1px rgba(34,211,238,0.04), 0 12px 40px rgba(0,0,0,0.6), inset 0 0 30px rgba(34,211,238,0.02);
        }
        .hud-corner {
          position: absolute; width: 8px; height: 8px;
          border-color: rgba(34,211,238,0.5); border-style: solid;
        }
        .hud-corner.tl { top: -1px; left: -1px; border-width: 1.5px 0 0 1.5px; border-radius: 3px 0 0 0; }
        .hud-corner.tr { top: -1px; right: -1px; border-width: 1.5px 1.5px 0 0; border-radius: 0 3px 0 0; }
        .hud-corner.bl { bottom: -1px; left: -1px; border-width: 0 0 1.5px 1.5px; border-radius: 0 0 0 3px; }
        .hud-corner.br { bottom: -1px; right: -1px; border-width: 0 1.5px 1.5px 0; border-radius: 0 0 3px 0; }
        .hud-header { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
        .hud-live-dot {
          width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0;
          background: var(--teal); box-shadow: 0 0 5px var(--teal);
          animation: statusPulse 2s ease-in-out infinite;
        }
        .hud-title {
          flex: 1; font-size: 0.52rem; letter-spacing: 0.14em;
          text-transform: uppercase; color: var(--teal); font-weight: 500;
        }
        .hud-close {
          background: none; border: none; color: var(--muted); cursor: pointer;
          font-size: 0.7rem; line-height: 1; padding: 0; opacity: 0.6;
          transition: opacity 0.15s;
        }
        .hud-close:hover { opacity: 1; }
        .hud-divider { height: 1px; background: rgba(34,211,238,0.1); margin: 7px 0; }
        .hud-dominant { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
        .hud-dominant span:first-child { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; }
        .hud-dominant-score { font-size: 0.62rem; color: var(--muted); }
        .hud-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
        .hud-label { width: 44px; font-size: 0.5rem; color: var(--muted); text-transform: capitalize; flex-shrink: 0; letter-spacing: 0.04em; }
        .hud-bar-track { flex: 1; height: 2px; background: rgba(255,255,255,0.06); border-radius: 1px; }
        .hud-bar-fill { height: 100%; border-radius: 1px; transition: width 0.5s ease; }
        .hud-value { width: 20px; font-size: 0.48rem; color: var(--muted); text-align: right; flex-shrink: 0; }
        .hud-empty { font-size: 0.5rem; color: var(--muted); margin: 0; text-align: center; padding: 4px 0; }
        .hud-video-wrap {
          width: 100%; aspect-ratio: 16/9; overflow: hidden;
          border-radius: 6px; background: var(--surface);
          position: relative; border: 1px solid var(--border);
          transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }
        .hud-controls { display: flex; gap: 6px; justify-content: center; }
        .hud-ctrl-btn {
          display: flex; align-items: center; gap: 4px;
          padding: 4px 10px; border-radius: 20px; border: none; cursor: pointer;
          font-size: 0.5rem; letter-spacing: 0.06em; text-transform: uppercase;
          transition: opacity 0.15s ease;
        }
        .hud-ctrl-btn:hover { opacity: 0.8; }
        .hud-ctrl-btn.active-teal { background: rgba(34,211,238,0.1); color: var(--teal); }
        .hud-ctrl-btn.active-gold { background: rgba(201,168,76,0.1); color: var(--gold); }
        .hud-ctrl-btn.active-red  { background: rgba(239,68,68,0.1);  color: #ef4444; }

        /* HUD positions (Desktop) */
        @media (min-width: 640px) {
          .popup-head  { top: 72px;    left: 14px; right: auto; bottom: auto; }
          .popup-chest { bottom: 80px; right: 14px; left: auto; top: auto; }
          .app-body.canvas-open .popup-chest { left: 14px; right: auto; bottom: 80px; top: auto; }
        }

        /* ── Canvas pull tab ────────────────────────────────────────────── */
        .canvas-pull-tab {
          position: fixed;
          right: 0;
          top: 50%;
          transform: translateY(-50%);
          z-index: 25;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 5px;
          padding: 12px 5px;
          background: rgba(4,8,15,0.85);
          border: 1px solid rgba(34,211,238,0.2);
          border-right: none;
          border-radius: 8px 0 0 8px;
          cursor: pointer;
          color: rgba(34,211,238,0.5);
          transition: color 0.2s, background 0.2s, border-color 0.2s;
          backdrop-filter: blur(12px);
        }
        .canvas-pull-tab:hover {
          color: var(--teal);
          background: rgba(34,211,238,0.08);
          border-color: rgba(34,211,238,0.4);
        }
        .canvas-pull-tab span {
          font-size: 0.42rem;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          writing-mode: vertical-rl;
          font-weight: 600;
        }

        /* ── Robot scale-down for smaller viewports ────────────────────── */
        .robot-wrap { transform-origin: top center; }

        @media (max-height: 780px) {
          .robot-wrap { transform: scale(0.82); margin-bottom: -86px; }
        }
        @media (max-height: 660px) {
          .robot-wrap { transform: scale(0.65); margin-bottom: -168px; }
          .rumi-stage { gap: 4px; }
        }
        @media (max-height: 520px) {
          .robot-wrap { transform: scale(0.5); margin-bottom: -240px; }
          .rumi-stage { gap: 2px; padding: 4px 8px 8px; }
        }
        @supports (padding: env(safe-area-inset-bottom)) {
          .rumi-stage   { padding-bottom: max(16px, env(safe-area-inset-bottom)); }
          .override-panel { padding-bottom: max(24px, env(safe-area-inset-bottom)); }
        }
      `}</style>
    </main>
  );
}
