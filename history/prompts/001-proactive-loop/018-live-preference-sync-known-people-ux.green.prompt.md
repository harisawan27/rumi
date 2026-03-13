---
id: 018
title: Live Preference Sync and Known People UX
stage: green
date: 2026-03-11
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: live preference sync implementation
labels: ["live-reload","session-manager","known-people","ux","profile"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/session/session_manager.py
  - backend/src/api/main.py
  - frontend/src/services/session.ts
  - frontend/src/app/profile/page.tsx
tests:
  - manual: change companion language in profile mid-session, trigger intervention — should use new language immediately
  - manual: add known person — spinner appears, card slides in without page reload
---

## Prompt

i want it to take changes lively. like i setted english only in profile but in current session i changed it to mix with urdu but on 30 min break message it speaks pure english because session never restarted. I want if user ask him to add the person it shows loading animation and after completion that person should be appear on profile page without reloading. every change should be managed lively as it made

## Response snapshot

Implemented two features:

**Live preference sync:**
- Added `refresh_context()` method to `SessionManager` — reloads identity from Firestore, rebuilds `_system_prompt`, disconnects Gemini Live so it reconnects with the new prompt on the next query
- Added `POST /session/refresh-context` endpoint to `main.py` — silent no-op if no active session (returns `{"status": "no_active_session"}`)
- Added `refreshSessionContext()` to `session.ts`
- `patch()` in profile page now calls `refreshSessionContext().catch(() => {})` fire-and-forget after every `saveIdentity()` — any companion language, expression style, or tone change takes effect on the next Rumi voice response

**Known people live UX:**
- Replaced `getKnownPeople()` re-fetch with optimistic insert — new person card appears instantly in the list without any network round-trip
- Added spinner SVG (using existing `rotateSlow` @keyframes at 0.8s) inside the save button while uploading/saving
- Button text changes to "Uploading photo…" vs "Saving…" based on whether a photo file is attached
- Cancel button disabled during save to prevent state corruption
- Person cards get `fadeSlideUp 0.25s` entry animation when added

## Outcome

- ✅ Impact: Companion language/tone/expression changes take effect on the next intervention or voice response without session restart; known person appears immediately with animation
- 🧪 Tests: Manual — profile page language change → trigger intervention should speak in new language mix
- 📁 Files: 4 files modified (session_manager.py, main.py, session.ts, profile/page.tsx)
- 🔁 Next prompts: E2E validation, cloud deploy test
- 🧠 Reflection: The key insight was that ADK `generate_intervention()` already called `get_user_context()` fresh on every trigger, so interventions were already live. The only stale path was the Gemini Live system prompt — fixed by disconnecting and letting `ensure_gemini_connected()` reconnect with the new prompt.

## Evaluation notes (flywheel)

- Failure modes observed: None at implementation time
- Graders run and results (PASS/FAIL): null
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Add a subtle toast on dashboard "Rumi updated — changes active" when refreshSessionContext succeeds
