---
id: "005"
title: "7-Day MVP Plan Proactive Loop"
stage: plan
date: 2026-03-06
surface: agent
model: claude-sonnet-4-6
feature: proactive-loop
branch: 001-proactive-loop
user: Haris
command: /sp.plan
labels: ["plan","proactive-loop","architecture","gemini","firebase","cloud-run","websocket","7-day"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-proactive-loop/plan.md
  - specs/001-proactive-loop/research.md
  - specs/001-proactive-loop/data-model.md
  - specs/001-proactive-loop/quickstart.md
  - specs/001-proactive-loop/contracts/api-contracts.md
  - history/prompts/proactive-loop/005-7-day-mvp-plan.plan.prompt.md
tests:
  - none
---

## Prompt

I need a high-velocity, 7-day development plan to build the Mirr'at MVP for the Google Gemini Live Agent Challenge.

Goal: Build a functional 'Live Agent' that recognizes me as Haris, uses my Firebase memory (Rumi, DoneKaro, Karachi context), and proactively initiates a voice/vision interaction based on my workspace state.

Plan Requirements:

Phase 1: Foundation (Days 1-2): Focus on Firebase Google OAuth setup, Firestore schema creation (User Profile + Session Logs), and the initial Next.js/Python boilerplate.

Phase 2: The 'Senses' (Days 3-4): Establish the Gemini Multimodal Live API WebSocket connection. Implement the vision capture loop (OpenCV/Webcam) and the initial 'Watchman' trigger logic.

Phase 3: The 'Soul' (Day 5): Integrate the Context Injection. Ensure the agent greets me by name, mentions my Rumi/Turkish interests, and asks about specific projects (DoneKaro/RehnumaAI).

Phase 4: Cloud & Polish (Day 6): Automate deployment to Google Cloud Run (Dockerized). Fine-tune the personality/voice to sound like a Karac [truncated]

## Response snapshot

Generated full architecture plan for the 7-day Mirr'at MVP. All Phase 0 and Phase 1 artifacts produced:

plan.md: Technical Context, Constitution Check (all 6 principles + Mandate = PASS), 7-Day Roadmap,
  project folder structure (Python backend + Next.js frontend), 5 key architectural decisions, risks.
research.md: 7 research topics resolved — Gemini Live API WebSocket, Firebase OAuth, Firestore schema,
  OpenCV capture loop, Cloud Run deployment, System Prompt template, Auto-Summarizer.
data-model.md: Full Firestore schema — users, sessions, interactions, session_summaries entities with
  field-level detail, security rules outline, and index requirements.
contracts/api-contracts.md: 8 REST endpoints + 1 WebSocket contract (WS /ws/observe) with request/
  response schemas, error codes, and message flow.
quickstart.md: Local setup, Docker Compose, test commands, Cloud Run deploy, troubleshooting.

Phase 4 input truncated at "to sound like a Karac" — interpreted as "Karachi companion" (cultural tuning).
Agent context updated in CLAUDE.md with Python/Next.js/Firestore stack.

## Outcome

- ✅ Impact: Full architecture ready for /sp.tasks; folder structure, Firestore schema, System Prompt template,
  and API contracts all resolved (the three items deferred from spec).
- 🧪 Tests: No test code written yet; contract tests, integration tests, and unit tests defined in quickstart.md.
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, contracts/api-contracts.md, CLAUDE.md (updated)
- 🔁 Next prompts: /sp.tasks to generate task list; /sp.adr for Gemini Live API architecture decision.
- 🧠 Reflection: Fourth consecutive truncated prompt. Plan inferred Phase 4 ending ("Karachi companion" polish)
  from context. All three spec-deferred items (folder structure, schema, System Prompt) fully resolved here.

## Evaluation notes (flywheel)

- Failure modes observed: Recurring prompt truncation (4/5 prompts). Pattern is consistent.
- Graders run and results (PASS/FAIL): Constitution Check — all 6 principles PASS; Proactive Personalization
  Mandate — all 5 PASS; no violations detected.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.tasks to validate that the plan produces a clean,
  dependency-ordered task list aligned with the 7-day roadmap.
