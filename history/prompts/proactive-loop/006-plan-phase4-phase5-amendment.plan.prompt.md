---
id: "006"
title: "Plan Phase 4 Phase 5 Amendment"
stage: plan
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: proactive-loop
branch: 001-proactive-loop
user: Haris
command: /sp.plan
labels: ["plan","proactive-loop","amendment","cloud-run","demo","architecture-diagram","wise-engineer"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-proactive-loop/plan.md
  - history/prompts/proactive-loop/006-plan-phase4-phase5-amendment.plan.prompt.md
tests:
  - none
---

## Prompt

add this remaining part of previus prompt to plan "Phase 4: Cloud & Polish (Day 6): Automate deployment to Google Cloud Run (Dockerized). Fine-tune the personality/voice to sound like a Karachi-based 'Wise Engineer'.

Phase 5: The Submission (Day 7): Final bug fixes, Architecture Diagram generation, and recording the 4-minute demo video (showing the real-time proactive interaction)."

## Response snapshot

Amended plan.md (001-proactive-loop) — two targeted updates, no new artifacts:

Phase 4 (Day 6): Added "Karachi-based 'Wise Engineer'" as the explicit personality target with
  concrete calibration criteria (Chai breaks specific and warm, Urdu warmth terms, Rumi quotes for
  engineering situations, precise when focused/unhurried when frustrated). Deployment gates unchanged.

Phase 5 (Day 7): Renamed "Integration Testing & Demo Prep" → "The Submission". Added:
  - Architecture Diagram as a required deliverable (system diagram showing all components and data flows;
    tool: draw.io/Excalidraw/Mermaid)
  - 4-minute demo video (was 3-minute in draft); scripted outline: intro → identity load → Trigger A →
    Trigger B → Firestore verification
  - Final bug fixes explicitly called out
  - Code freeze tag: v0.1.0-mvp

## Outcome

- ✅ Impact: Plan now fully reflects the 7-day roadmap as intended; Phase 5 is submission-ready.
- 🧪 Tests: No new tests; Phase 5 end-to-end validation of all 9 SCs still required.
- 📁 Files: specs/001-proactive-loop/plan.md (amended)
- 🔁 Next prompts: /sp.tasks to generate implementation task list; /sp.adr for architecture decisions.
- 🧠 Reflection: Fifth consecutive truncated prompt — handled cleanly as amendment. Demo video duration
  corrected from 3-min (inferred) to 4-min (confirmed by user).

## Evaluation notes (flywheel)

- Failure modes observed: Recurring truncated inputs (5/6 prompts). Consider noting to user.
- Graders run and results (PASS/FAIL): N/A — plan amendment only; no new constitution checks needed.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.tasks to verify that the 7-day structure generates
  a clean, ordered task list.
