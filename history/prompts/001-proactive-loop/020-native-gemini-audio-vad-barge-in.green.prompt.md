---
id: 020
title: Native Gemini Live Audio Streaming VAD Barge-in
stage: green
date: 2026-03-17
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: master
user: Haris
command: implement Option B native Gemini audio streaming
labels: ["voice", "audio", "barge-in", "vad", "gemini-live", "webrtc"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/gemini/live_client.py
  - backend/src/session/session_manager.py
  - backend/src/api/main.py
  - frontend/src/app/dashboard/page.tsx
tests:
  - manual: mic press → startNativeAudio → PCM stream → Gemini responds with audio
  - manual: silence detection → audio_end → Gemini generates reply
  - manual: speaking=true + mic press → barge-in stops Rumi, starts recording
  - manual: wake word → startNativeAudio (not startListeningWithRef)
  - manual: transcript WS message updates UI transcript display
  - manual: audio_interrupt from server sets isProcessing=false
---

## Prompt

You are implementing Option B of the Rumi voice pipeline: replacing SpeechRecognition-based input with native Gemini Live API audio streaming, which gives true server-side VAD barge-in.

[Full implementation spec provided — see changes in backend/src/gemini/live_client.py, backend/src/session/session_manager.py, backend/src/api/main.py, frontend/src/app/dashboard/page.tsx]

## Response snapshot

Implemented all four files as specified:

1. `live_client.py`: Added `_on_interrupted` and `_on_input_transcript` fields; `set_interrupted_callback()` and `set_input_transcript_callback()` setters; `input_audio_transcription=types.AudioTranscriptionConfig()` in `LiveConnectConfig`; interrupted and input_transcription handling blocks in `_receive_loop` after turn_complete.

2. `session_manager.py`: Added `set_interrupted_callback(self._handle_gemini_interrupted)` call in `ensure_gemini_connected()`; added `_handle_gemini_interrupted()` method that suppresses audio, resets responding state, increments voice_gen, cancels speak_task, and sends `audio_interrupt` to frontend.

3. `main.py`: Replaced the simple `talk_start` handler with one that also wires `_on_user_transcript` closure (sends `transcript` WS message + canvas trigger check on user speech text) via `set_input_transcript_callback`.

4. `dashboard/page.tsx`: Added `nativeCtxRef`, `nativeStreamRef`, `nativeProcessorRef`; added cleanup in useEffect; replaced legacy `startBargeinListener` (no-op now) + VAD section with `stopNativeAudio()` + `startNativeAudio()` (getUserMedia 16kHz, ScriptProcessorNode, RMS silence detection, PCM resampling, base64 encode → `audio` WS messages); updated `handleMicToggle` to support barge-in when speaking=true; added `transcript` WS message handler; added `setIsProcessing(false)` on `audio_response`; updated wake word handler and speaking useEffect to call `startNativeAudio()` instead of `startListeningWithRef()`.

Committed as: `feat: native Gemini Live audio streaming — true server-side VAD barge-in` (f06641d)

## Outcome

- Impact: Voice path now uses native PCM streaming to Gemini Live with server-side VAD for barge-in; eliminates SpeechRecognition echo self-interruption problem; adds input transcription display; retains SpeechRecognition only for text override path (/) and wake word detection
- Tests: Manual validation required — PCM streaming, silence detection, barge-in, transcript display
- Files: 4 files changed, 210 insertions, 49 deletions
- Next prompts: Test latency of native audio path vs old path; tune SILENCE_THRESHOLD (currently 6 RMS) if too sensitive/not sensitive enough; verify AudioContext sampleRate negotiation at 16kHz across browsers
- Reflection: `startBargeinListener` retained as no-op for backwards compatibility with any code paths that might still reference it; legacy VAD refs kept since they are still cleaned up on unmount

## Evaluation notes (flywheel)

- Failure modes observed: ScriptProcessorNode is deprecated in modern Web Audio spec but remains the only synchronous PCM access method; browser may not honor 16kHz AudioContext request (resampling path handles this)
- Graders run and results (PASS/FAIL): none automated — manual only
- Prompt variant (if applicable): none
- Next experiment: Replace ScriptProcessorNode with AudioWorklet for future-proofing
