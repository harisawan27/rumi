---
id: 008
title: VisionClient StateMonitor Gemini Robotics ER Integration
stage: green
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: sp.implement
labels: ["vision","watchman","gemini-robotics-er","state-monitor","api-conservation"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/watchman/state_monitor.py
  - backend/src/api/main.py
tests:
  - none
---

## Prompt

(Continued from previous context — session resumed)

We are officially using Gemini 2.5 Flash Native Audio Dialog as our primary engine for real-time voice/multimodal. For the proactive 'Watchman' vision logic, we will utilize Gemini Robotics ER 1.5 Preview to analyze user posture and desk state. Route all API calls to asia-south1 (Mumbai) via Vertex AI.

vision_client.py was created with VisionClient using gemini-robotics-er-1.5-preview. state_monitor.py still uses self._gemini.query(STATE_ANALYSIS_PROMPT) — needs to be wired to VisionClient.analyse_frame().

## Response snapshot

Updated `state_monitor.py`:
- Removed `STATE_ANALYSIS_PROMPT` constant (no longer querying Gemini Live for posture)
- Added `from src.gemini.vision_client import VisionClient`
- `__init__`: instantiates `VisionClient()` as `self._vision`; adds `_current_frame: Optional[bytes]` buffer
- Added `update_frame(frame_bytes)` method — called by WS handler on every incoming frame
- `run_cycle()`: calls `self._vision.analyse_frame(effective_frame)` → Gemini Robotics ER 1.5 Preview; no JSON parsing needed (VisionClient returns dict); frame diff gate still applies
- `run_loop()`: passes `self._current_frame` to `run_cycle()`

Updated `main.py` WS frame handler:
- Added `mgr._state_monitor.update_frame(frame_bytes)` alongside existing CodingBlockTracker call

Data flow: Frontend frame → send_frame() to Gemini Live + CodingBlockTracker.update_frame() + StateMonitor.update_frame() → every 45s: VisionClient.analyse_frame() → Gemini Robotics ER → StateResult → triggers

## Outcome

- ✅ Impact: Watchman Trigger A/B now powered by dedicated vision model (Gemini Robotics ER 1.5 Preview) instead of text-only Gemini Live query; frame diff gating preserved for API conservation
- 🧪 Tests: none run (runtime integration test needed with live camera)
- 📁 Files: backend/src/watchman/state_monitor.py, backend/src/api/main.py
- 🔁 Next prompts: Test full session flow (camera → frame → VisionClient → trigger); add GOOGLE_CLOUD_PROJECT to .env for Vertex AI routing; deploy to Cloud Run asia-south1
- 🧠 Reflection: The async frame delivery pattern (request_frame → WS callback → update_frame buffer) cleanly decouples the Watchman cycle timing from frame arrival latency

## Evaluation notes (flywheel)

- Failure modes observed: VisionClient will fall back to gemini-2.5-flash-preview-05-20 if Robotics ER unavailable on API key account (Vertex AI project required for ER model)
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): null
- Next experiment: Test with GOOGLE_CLOUD_PROJECT set to verify Vertex AI routing to asia-south1 works end-to-end
