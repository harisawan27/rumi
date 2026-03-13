---
id: "015"
title: voice pipeline fixed gemini api compat
stage: green
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: bugfix
labels: ["voice","gemini-live","speech-recognition","bug-fix","vad"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/gemini/live_client.py
  - frontend/src/app/dashboard/page.tsx
tests:
  - manual E2E: tap mic, say "hello how are you", wait 1.8s → Rumi replies aloud
---

## Prompt

it did the same shit again please solve this error:
"LocalObserver: mediapipe not installed — using frame diff only
SessionManager: greeting failed: explicit_vad_signal parameter is not supported in Gemini API.
ws_observe: user_text response failed: explicit_vad_signal parameter is not supported in Gemini API."

Also sentence was being cut on natural mid-sentence pauses.

## Response snapshot

Two bugs fixed:

**Bug 1 — Root cause of ALL voice failures (backend):**
`explicitVadSignal=True` in `LiveConnectConfig` is Vertex AI only — not supported on standard Gemini API. This made every single Gemini connection fail silently, blocking greetings AND voice replies. Removed the parameter entirely. Since Web Speech API handles transcription locally, PTT mode is not needed.

**Bug 2 — Sentence cutting (frontend):**
`rec.continuous = false` caused SpeechRecognition to auto-stop on any brief natural pause. Changed to `rec.continuous = true` with a 1.8s silence timer that auto-sends. Timer resets on every new speech chunk so mid-sentence pauses never trigger early sends.

**Also fixed in prior session (live_client.py):**
`_receive_loop` now sets `self._connected = False` in finally block so that if Gemini drops the session server-side, `ensure_gemini_connected()` correctly reconnects instead of sending into a dead session.

## Outcome

- Impact: Voice pipeline fully working end-to-end. User speaks → browser transcribes → backend queries Gemini → Rumi replies aloud.
- Tests: confirmed working by user ("perfect man it's working")
- Files: 2 files modified
- Next prompts: production deploy, E2E validation
- Reflection: The `explicitVadSignal` bug was the single root cause blocking everything from session 1. It was introduced when implementing push-to-talk and never removed when switching to Web Speech API.

## Evaluation notes (flywheel)

- Failure modes observed: Gemini API compat flags (explicitVadSignal is Vertex-only); SpeechRecognition auto-stop on brief pauses
- Graders run and results (PASS/FAIL): manual — PASS
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): test with longer sentences and natural Urdu/English code-switching
