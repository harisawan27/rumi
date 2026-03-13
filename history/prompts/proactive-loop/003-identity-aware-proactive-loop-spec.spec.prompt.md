---
id: "003"
title: "Identity-Aware Proactive Loop Spec"
stage: spec
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: proactive-loop
branch: 001-proactive-loop
user: Haris
command: /sp.specify
labels: ["spec","proactive-loop","watchman","identity","multimodal","gemini","firebase"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-proactive-loop/spec.md
  - specs/001-proactive-loop/checklists/requirements.md
  - history/prompts/proactive-loop/003-identity-aware-proactive-loop-spec.spec.prompt.md
tests:
  - none
---

## Prompt

I need a detailed technical specification for the 'Identity-Aware Proactive Loop' module. This is the core 'agentic' feature of Mirr'at.

Module Objectives:

User Authentication & Profile Retrieval: Implement Google OAuth using Firebase. Upon login, the system must fetch the user's 'Core Identity' (Name: Haris, Location: Karachi, Projects: DoneKaro/RehnumaAI, Interests: Rumi/Turkish) from Firestore.

Multimodal Live Connection: Define the WebSocket architecture for the Gemini Multimodal Live API. It must handle a continuous 15fps video stream from the webcam.

The 'Watchman' Logic (Proactivity): Define a 'State Monitor' that analyzes the visual feed every 45 seconds. It should look for specific triggers:

Trigger A (Frustration): User hands on head or leaning back for > 2 mins. -> Action: Offer a Rumi quote or a 5-min break.

Trigger B (Coding Block): User staring at the same code window for > 10 mins. -> Action: Ask about the specific project progress (e.g., 'How's the Docker setup going?').

Context Injection: Describe how [truncated]

## Response snapshot

Created feature branch `001-proactive-loop` and wrote spec at `specs/001-proactive-loop/spec.md`.
4 user stories defined (P1–P3, one P2 added for context injection):
  US1 (P1): Secure Sign-In & Identity Loading — Google auth + Core Identity loaded in <10s
  US2 (P2): Frustration Detection & Compassionate Intervention — Trigger A; Rumi quote/Chai break
  US3 (P3): Coding Block Detection & Project-Aware Check-In — Trigger B; project-specific question
  US4 (P2): Context-Injected Identity in Every Response — personalisation mandate story
14 functional requirements (FR-001–FR-014), 7 success criteria (SC-001–007), 4 key entities defined.
Truncated "Context Injection" input handled as assumption: Core Identity injected at generation time.
All 5 Proactive Personalization Mandate checks: PASS.
Spec quality checklist: all items PASS.

## Outcome

- ✅ Impact: Full feature spec for the core agentic module; ready for /sp.plan.
- 🧪 Tests: Acceptance scenarios defined for all 4 user stories; SC-002/003 specify detection accuracy thresholds.
- 📁 Files: specs/001-proactive-loop/spec.md, specs/001-proactive-loop/checklists/requirements.md
- 🔁 Next prompts: /sp.plan to design architecture; /sp.clarify if any requirements need refinement.
- 🧠 Reflection: Input was truncated mid-sentence at "Context Injection: Describe how" — treated as
  identity-at-generation-time injection (documented in Assumptions). No clarification questions needed;
  all 5 Proactive Personalization mandate checks passed without requiring user input.

## Evaluation notes (flywheel)

- Failure modes observed: Truncated user input (second occurrence); pattern noted. PowerShell script had a
  parameter error but branch+spec directory creation succeeded before the error.
- Graders run and results (PASS/FAIL): Requirements checklist — all PASS; Proactive Personalization
  Mandate — all 5 PASS.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.plan to validate that the 14 FRs are sufficient to
  drive a clean architecture without ambiguity.
