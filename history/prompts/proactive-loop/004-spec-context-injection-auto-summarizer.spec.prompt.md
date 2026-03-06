---
id: "004"
title: "Spec Context Injection Auto-Summarizer"
stage: spec
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: proactive-loop
branch: 001-proactive-loop
user: Haris
command: /sp.specify
labels: ["spec","proactive-loop","context-injection","auto-summarizer","session-summary","personality"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-proactive-loop/spec.md
  - specs/001-proactive-loop/checklists/requirements.md
  - history/prompts/proactive-loop/004-spec-context-injection-auto-summarizer.spec.prompt.md
tests:
  - none
---

## Prompt

you missed that part of previous prompt, also add this "Context Injection: Describe how the Firebase data is injected into the Gemini 'System Instruction' at the start of every session so the agent speaks with immediate familiarity.

Memory Logging: Define an 'Auto-Summarizer' that runs at the end of each session to save a 2-sentence summary of the interaction back to Firestore for the next day's context.

Requirements: > - Provide a clear folder structure for the Python/Next.js setup.

Define the Firebase schema (collections and fields).

Outline the 'System Prompt' template that includes the Rumi/Sufi/Engineer personality blend."

## Response snapshot

Amended spec (001-proactive-loop) with two new user stories and expanded requirements.
No new branch created — this is an amendment to the existing feature spec.

Added:
  US2 (P1): Session Start with Immediate Familiarity — Core Identity + Session Summaries
    loaded at session start before any intervention is generated; Sufi-Engineer personality
    configured for the session.
  US6 (P2): Automatic Session Summary at Close — Auto-Summarizer generates a 2-sentence
    text summary at session end; saved to persistent memory store; seeds next session.
  FR-003: Load most recent Session Summary(ies) at session start.
  FR-004: Configure Sufi-Engineer personality at session start.
  FR-017–020: Auto-Summarizer requirements (generate, save, text-only, rolling window).
  SC-002, SC-008, SC-009: New success criteria for session start load time and summary quality.
  New Key Entities: Session Summary, Personality Configuration (with field-level detail).

Architectural requests (folder structure, Firebase schema, System Prompt template) noted
as "deferred to plan.md" in Assumptions — these are HOW decisions, not WHAT decisions.
Spec now has 20 FRs, 9 SCs, 6 entities, 6 user stories.

## Outcome

- ✅ Impact: Spec now fully covers the complete proactive loop lifecycle: sign-in → context load →
  observation → intervention → session summary → next-session seed.
- 🧪 Tests: SC-002 and SC-008 add measurable criteria for session start load time and summary save time.
- 📁 Files: specs/001-proactive-loop/spec.md (updated), checklists/requirements.md (updated)
- 🔁 Next prompts: /sp.plan — must cover folder structure, Firebase schema, and System Prompt template.
- 🧠 Reflection: Third consecutive truncated input from user — all handled by treating follow-up as
  amendment rather than new feature. Correctly identified that folder/schema/template are plan.md artifacts.

## Evaluation notes (flywheel)

- Failure modes observed: Recurring truncated user inputs (3 of 4 prompts). Pattern: user types long
  prompts in a chat window that has a character limit. Should be surfaced as a note to user.
- Graders run and results (PASS/FAIL): All 16 spec quality checklist items PASS; all 5 Proactive
  Personalization Mandate checks PASS.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.plan and verify that Firebase schema, folder
  structure, and System Prompt template are cleanly addressed there.
