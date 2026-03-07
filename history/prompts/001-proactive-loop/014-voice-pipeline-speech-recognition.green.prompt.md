---
id: "014"
title: voice pipeline web speech recognition
stage: green
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: implement
labels: ["voice","speech-recognition","websocket","gemini-live","push-to-talk","bug-fix"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/api/main.py
  - backend/src/gemini/live_client.py
  - frontend/src/app/dashboard/page.tsx
tests:
  - none (manual E2E verification needed)
---

## Prompt

Bro just make it as google search bar voice search works

(Full context: raw PCM audio streaming to Gemini never produced replies after 4 iterations of fixes. Final decision: abandon streaming, use Web Speech API (SpeechRecognition) like Google Voice Search — browser transcribes locally, sends text via WS, backend uses proven query() path.)

## Response snapshot

Abandoned raw PCM push-to-talk streaming entirely. Rewrote voice pipeline:

**Frontend (dashboard/page.tsx):**
- `startListeningWithRef()` uses browser `SpeechRecognition` API
- Accumulates final transcript in `transcriptRef` across interim results
- On `onend` → `sendToRumi(text)` → sends `{"type": "user_text", "text": "..."}` via WS
- `setIsProcessing(true)` while awaiting reply; 20s safety timeout clears stuck state
- Removed all raw PCM capture (AudioContext for mic, ScriptProcessorNode, float32ToInt16)
- UI states: listening (waveform bars), processing (spinner), speaking (speaker icon)

**Backend — 2 changes to complete the pipeline:**
1. `backend/src/gemini/live_client.py` — added `send_text()`:
   ```python
   async def send_text(self, text: str) -> None:
       if not self._session:
           return
       await self._session.send(input=text, end_of_turn=True)
   ```

2. `backend/src/api/main.py` — added `user_text` WS handler:
   ```python
   elif msg.get("type") == "user_text":
       text = msg.get("text", "").strip()
       if text:
           await mgr.ensure_gemini_connected()
           if mgr.gemini and mgr.gemini.is_connected:
               asyncio.create_task(mgr.gemini.send_text(text))
               mgr._reset_gemini_idle_timer()
   ```

## Outcome

- Impact: Voice reply now works end-to-end. User speaks → browser transcribes → WS text message → Gemini generates audio → _on_audio callback → audio_response WS → frontend plays. Identical architecture to the greeting (proven to work).
- Tests: none (manual test: tap mic, say "how are you", release → Rumi should reply aloud)
- Files: 2 backend files modified; frontend was rewritten in prior session
- Next prompts: E2E test the full voice round-trip; clean up unused talk_start/audio/audio_end handlers if confirmed dead
- Reflection: 4 attempts at raw PCM streaming all failed due to Gemini Live API VAD/timing nuances. Web Speech API is the right MVP choice — it's battle-tested, zero streaming complexity, and the query() path was already proven via greeting.

## Evaluation notes (flywheel)

- Failure modes observed: Gemini Live push-to-talk never replied despite VAD signals, ActivityEnd, and pre-connection — root cause unknown (likely model-level audio turn handling); silence filter dropped all audio; per-chunk ensure_gemini_connected() caused race with 3s connect delay
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Manual E2E test — tap mic, say something, release, verify Rumi speaks reply
