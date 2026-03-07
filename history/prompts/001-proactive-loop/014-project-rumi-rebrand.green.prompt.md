---
id: 014
title: Project Rumi Rebrand — Identity Layer Naming
stage: green
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: rebrand / refactor
labels: ["rebrand","constitution","identity","rumi","documentation"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .specify/memory/constitution.md
  - README.md
  - backend/src/api/main.py
  - backend/src/gemini/prompt_builder.py
  - backend/src/agent/mirrat_agent.py
  - backend/src/session/session_manager.py
  - frontend/src/app/layout.tsx
  - frontend/src/app/dashboard/page.tsx
tests:
  - (manual) verify startup log shows [RUMI CORE] Initializing Identity Protocol...
  - (manual) verify browser tab title shows "Project Rumi — The Identity Layer"
  - (manual) verify dashboard subtitle shows "Rumi is watching. Witnessing. Understanding."
---

## Prompt

Task: Execute a global refactor and documentation update to rename our identity-aware robotics project to "Project Rumi".

The Context & Essence (Read Carefully):

We are pivoting the branding and core philosophy of this project. The industry treats humanoid robots as blind workers. We are building the "Identity Layer" that gives them memory, empathy, and recognition.

We are naming this Project Rumi.

Just as OpenAI uses "DaVinci" and Nvidia uses "Turing" or "Hopper," we are paying tribute to a historical giant. Naming our product after one of history's most influential philosophers isn't just branding; it is a statement. "We are not just welding metals, but we respect the persons who make us think about human existence again."

Rumi represents the search for the Self and the Connection to the Other. Our robotic architecture literally searches for the identity of the user and connects with them. The AI agent acting as this core protocol will be named Rumi.

Execution Steps:
1. Update the Constitution: Rewrite the .sp/constitution to explicitly state that the AI is Rumi. Inject the philosophy that it must "Witness and Understand".
2. Update the README: Rewrite the introduction with the quote and explain Project Rumi as the first empathetic, persistent memory layer for physical AI.
3. Update Logs & UI: Ensure logs/initialization sequences say: [RUMI CORE] Initializing Identity Protocol...

## Response snapshot

7 files updated with surgical, tone-matched changes:

- **Constitution**: Added "Identity Declaration — The Agent is Rumi" preamble before Core Principles. Defines the Rumi Mandate ("Witness and Understand"): observe → understand → speak. Version bumped 1.1.0 → 1.2.0.
- **README**: Rewritten intro opens with the pivotal quote, frames Project Rumi as "the first empathetic, persistent memory layer for physical AI", explains the naming philosophy.
- **main.py**: `_startup()` now logs `[RUMI CORE] Initializing Identity Protocol...` first; subsequent multi-user log also prefixed `[RUMI CORE]`. FastAPI title updated to "Project Rumi — Rumi Core".
- **prompt_builder.py**: System prompt opening rewritten — "You are Rumi — the Identity Layer of Project Rumi." Witness-and-Understand mandate injected above personality section.
- **mirrat_agent.py**: `MIRRAT_INSTRUCTION` opens with Rumi identity and mandate. ADK Agent `name` changed from `mirrat_companion` to `rumi_core`.
- **session_manager.py**: Session-started log prefixed `[RUMI CORE]`.
- **layout.tsx**: Browser metadata title → "Project Rumi — The Identity Layer"; description → "The first empathetic, persistent memory layer for physical AI."
- **dashboard/page.tsx**: Subtitle → "Rumi is watching. Witnessing. Understanding."

## Outcome

- ✅ Impact: Full identity pivot from "Mirr'at the chatbot" to "Rumi — the Identity Layer". The product name Mirr'at is preserved as the surface/app name; the AI agent within it is now Rumi. Every initialization sequence, system prompt, and UI surface reflects the new philosophy.
- 🧪 Tests: Manual verification steps noted above.
- 📁 Files: 8 files modified (7 source + 1 PHR created).
- 🔁 Next prompts: Consider /sp.adr for the naming decision; update docs/architecture.md to reference Rumi Core.
- 🧠 Reflection: Change was NOT a find-and-replace — each file received tone-matched, philosophically coherent edits. The product (Mirr'at) and the agent (Rumi) are now clearly distinct, as intended.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): Update docs/architecture.md header to reference Rumi Core
