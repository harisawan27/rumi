/**
 * Voice Architecture & Playback Controller for Project Rumi.
 *
 * State ownership:
 * - Backend owns Gemini generation lifecycle and generation counters.
 * - Frontend owns microphone recognition, AudioBufferSourceNode playback, and manual interruption.
 *
 * NOTE ON BARGE-IN:
 * Automatic hands-free voice barge-in is intentionally disabled because local microphone
 * captures Rumi's own speaker output, creating feedback interruption loops.
 * Manual interruption (Stop button, Space bar, Escape, typing in override) is fully supported.
 */

export type VoiceState =
  | "IDLE"
  | "WAKE_LISTENING"
  | "LISTENING"
  | "THINKING"
  | "SPEAKING"
  | "INTERRUPTED"
  | "PAUSED";

export interface AudioPlaybackController {
  playAudioChunk: (b64: string, serverGenId?: number) => void;
  stopAllAudio: (reason?: string) => number;
  getCurrentGeneration: () => number;
  getActiveSourceCount: () => number;
}

export function createAudioPlaybackController(
  onSpeakingChange: (speaking: boolean) => void,
): AudioPlaybackController {
  let playCtx: AudioContext | null = null;
  let activeSources: AudioBufferSourceNode[] = [];
  let nextPlayTime = 0;
  let audioChain: Promise<void> = Promise.resolve();
  let audioGen = 0;

  function stopAllAudio(_reason = "manual_interrupt"): number {
    audioGen++;
    activeSources.forEach((s) => {
      try {
        s.stop(0);
      } catch {
        // already stopped
      }
    });
    activeSources = [];
    nextPlayTime = 0;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    onSpeakingChange(false);
    return audioGen;
  }

  function playAudioChunk(b64: string, serverGenId?: number): void {
    const myGen = audioGen;

    // Discard immediately if server generation id is older than current frontend generation
    if (serverGenId !== undefined && serverGenId < audioGen) {
      return;
    }

    try {
      const raw = atob(b64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const sampleCount = Math.floor(bytes.byteLength / 2); // PCM16 = 2 bytes/sample
      const int16 = new Int16Array(bytes.buffer, 0, sampleCount);
      const float32 = new Float32Array(sampleCount);
      for (let i = 0; i < sampleCount; i++) float32[i] = int16[i] / 32768;

      audioChain = audioChain.then(async () => {
        if (audioGen !== myGen) return;

        try {
          if (!playCtx) {
            playCtx = new AudioContext({ sampleRate: 24000 });
          }
          if (playCtx.state === "suspended") {
            await playCtx.resume();
          }
          if (audioGen !== myGen) return;

          const buffer = playCtx.createBuffer(1, float32.length, 24000);
          buffer.copyToChannel(float32, 0);
          const source = playCtx.createBufferSource();
          source.buffer = buffer;
          source.connect(playCtx.destination);

          const now = playCtx.currentTime;
          if (nextPlayTime < now || nextPlayTime > now + 10) {
            nextPlayTime = now + 0.05;
          }
          source.start(nextPlayTime);
          nextPlayTime += buffer.duration;

          activeSources.push(source);
          onSpeakingChange(true);

          source.onended = () => {
            activeSources = activeSources.filter((s) => s !== source);
            if (activeSources.length === 0) {
              onSpeakingChange(false);
            }
          };
        } catch {
          // audio scheduling error
        }
      });
    } catch {
      // base64 decode error
    }
  }

  return {
    playAudioChunk,
    stopAllAudio,
    getCurrentGeneration: () => audioGen,
    getActiveSourceCount: () => activeSources.length,
  };
}
