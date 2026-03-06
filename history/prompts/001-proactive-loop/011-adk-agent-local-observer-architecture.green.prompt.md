---
id: 011
title: ADK Agent LocalObserver Robot-Style Architecture
stage: green
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: sp.implement
labels: ["adk","mediapipe","local-observer","robot-perception","api-conservation","google-adk"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/requirements.txt
  - backend/src/watchman/local_observer.py
  - backend/src/agent/__init__.py
  - backend/src/agent/mirrat_agent.py
  - backend/src/watchman/state_monitor.py
  - backend/src/session/session_manager.py
tests:
  - python -c "import mediapipe; import google.adk" → PASS
---

## Prompt

is there not any free tier model for vision or speaking?
[followed by] yes bro [to implement robot-style local perception + ADK Agent]

## Response snapshot

Built robot-style 3-layer perception architecture:

Layer 1 — LocalObserver (mediapipe, always-on, zero API cost):
- MediaPipe Pose: head drop (+0.30), shoulder hunch (+0.20), hand-near-face (+0.25)
- MediaPipe Face Mesh: squinting eyes (+0.20)
- Frame diff: idle score (0.0 = active, 1.0 = static)
- Runs every 5s, no API calls ever

Layer 2 — Trigger trackers (unchanged):
- FrustrationTracker: 2 min of frustrated state → Trigger A
- CodingBlockTracker: 10 min of static screen → Trigger B
- CYCLE_INTERVAL_SECONDS changed 45s → 5s (free now)

Layer 3 — ADK Agent (only on trigger events):
- google.adk.agents.Agent with model gemini-2.5-flash-preview-05-20
- Tools: get_user_context() → Haris identity; get_rumi_wisdom() → Rumi quote
- generate_intervention(event_type, uid, session_id) → returns personalized text
- Fallback hardcoded message if ADK unavailable

SessionManager: _fire_trigger_a/b() now calls ADK Agent → Gemini Live speaks it → dispatch_intervention() shows UI card

All free tier: mediapipe (on-device) + gemini-2.5-flash-preview-05-20 (free API key)

## Outcome

- ✅ Impact: LLM never called during normal observation — only on rare trigger events. Matches humanoid robot architecture (local perception → event-driven LLM). Satisfies Google ADK hackathon requirement.
- 🧪 Tests: import check PASS (mediapipe 0.10.32, google-adk OK)
- 📁 Files: 6 files created/modified
- 🔁 Next prompts: restart backend and test live session; verify ADK agent generates personalized text on trigger
- 🧠 Reflection: The robot analogy (Layer 1=reflexes, Layer 2=reactive, Layer 3=deliberative) maps perfectly to Mirr'at's architecture and is the right framing for the hackathon demo

## Evaluation notes (flywheel)

- Failure modes observed: MediaPipe pose detection requires person to be visible in frame; poor lighting will reduce accuracy
- Graders run and results (PASS/FAIL): import check PASS
- Prompt variant (if applicable): null
- Next experiment: Test frustration detection accuracy with actual camera feed; tune score thresholds if too sensitive/insensitive
