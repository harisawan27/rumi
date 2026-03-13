---
id: 017
title: Fix FER No Face Detected Unpack Bug
stage: green
date: 2026-03-08
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: fix fer no face detected expression card
labels: ["bugfix","fer","detection","local-observer","state-monitor"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/watchman/local_observer.py
tests:
  - manual: restart backend, open Expression HUD, verify emotion bars appear when face visible
---

## Prompt

the face is clearly visible more than before but expression live card is saying "No face detected"

## Response snapshot

Root cause identified in `backend/src/watchman/local_observer.py` line 102.

`_score_frustration()` returned `(0.0, [])` — a 2-tuple — when FER's OpenCV detector found no face.
The caller in `observe()` unpacked 3 values: `frustration_score, cues, emotions = ...` → `ValueError`.
This propagated to `run_cycle()` → `run_loop()` caught it silently with `logger.error` → `detection_update`
was never sent → frontend `detection` stayed `null` → `emotionEntries = []` → "No face detected" permanently.

Fix: changed `return 0.0, []` → `return 0.0, [], {}` (correct 3-tuple).

## Outcome

- ✅ Impact: Silent crash on every "no face" FER result eliminated; detection_update now always sent
- 🧪 Tests: Manual — restart backend, open Expression HUD by clicking Rumi's head zone
- 📁 Files: backend/src/watchman/local_observer.py (line 102)
- 🔁 Next prompts: If "No face detected" persists after fix, switch FER to mtcnn=True for better detection
- 🧠 Reflection: 2-tuple vs 3-tuple mismatch was masked by run_loop's broad except handler — easy to miss

## Evaluation notes (flywheel)

- Failure modes observed: Silent exception swallowed in run_loop; detection state never initialized on frontend
- Graders run and results (PASS/FAIL): Manual only
- Prompt variant (if applicable): null
- Next experiment: If FER still misses face, try `FER(mtcnn=True)` with `pip install mtcnn`
