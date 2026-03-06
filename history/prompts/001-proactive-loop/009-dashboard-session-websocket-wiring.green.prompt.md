---
id: 009
title: Dashboard Session WebSocket Wiring
stage: green
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: /sp.implement
labels: ["implementation","green","websocket","dashboard","session","watchman"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/app/dashboard/page.tsx (updated — full session + WebSocket wiring)
  - cloudbuild.yaml (region us-central1 → asia-south1)
  - .env.example (added GOOGLE_CLOUD_REGION)
tests:
  - (no test tasks)
---

## Prompt

/sp.implement (second run — after MVP gate confirmed working with "Marhaba, Haris")

## Response snapshot

All remaining tasks are MANUAL STEP. Identified critical gap: dashboard was not calling
startSession() or opening WebSocket, so Watchman loop never started.

Wired full session lifecycle into dashboard/page.tsx:
- startSession() called on mount → backend creates Firestore session + connects Gemini Live
- getUserMedia() for webcam → frames sent at 15fps via WebSocket
- connectObserveSocket() → handles intervention/paused/error messages
- InterventionCard rendered on intervention WS message
- PauseButton wired with sessionId
- endSession() called on beforeunload
- Hidden <video> element feeds frames to canvas for JPEG encoding

Also updated: cloudbuild.yaml region → asia-south1 (Mumbai, matches Firestore); .env.example GOOGLE_CLOUD_REGION added.

## Outcome

- ✅ Impact: Full observation loop now wired end-to-end — sign-in → session start → webcam → frames → Gemini → triggers → InterventionCard
- 🧪 Tests: None
- 📁 Files: dashboard/page.tsx rewritten; cloudbuild.yaml + .env.example updated
- 🔁 Next prompts: T009 Firebase console ✅ done; T049 deploy test; T050 E2E validation
- 🧠 Reflection: The gap between "identity loads" and "observation loop runs" was the missing startSession()+WebSocket connect in the dashboard mount effect

## Evaluation notes (flywheel)

- Failure modes observed: WebSocket frame sending uses canvas.toBlob + arrayBuffer — may have latency on low-end hardware
- Graders run and results (PASS/FAIL): null
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Test Trigger A by holding frustration posture 2+ minutes
