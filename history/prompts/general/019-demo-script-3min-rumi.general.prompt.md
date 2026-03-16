---
id: "019"
title: Demo Script 3-Minute Rumi Google Gemini Challenge
stage: general
date: 2026-03-16
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: Haris
command: Write a tight, natural 3-minute demo script for Project Rumi
labels: ["demo", "script", "google-gemini-challenge", "live-agents", "presentation"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - history/prompts/general/019-demo-script-3min-rumi.general.prompt.md
tests:
  - none
---

## Prompt

Write a tight, natural 3-minute demo script for Project Rumi — a proactive ambient AI companion built for the Google Gemini Challenge "Live Agents" category.

**Context:**
- Demo presenter: Haris (software engineering student, Karachi, Pakistan)
- Rumi is NOT a chatbot — it lives on the desktop, watches via camera, listens passively, speaks proactively
- Voice pipeline: Web Speech API → text → Gemini 2.5 Flash Native Audio Live API → real-time audio response
- Features to show: wake word, voice conversation, barge-in mid-response, camera awareness (who's in front), known person recognition, proactive intervention card, Firebase memory of past sessions
- Rumi's personality: warm Sufi-engineer soul, Rumi poetry references, natural mentor energy

**Format:** Timestamped sections with PRESENTER / RUMI / SHOW blocks.

**Constraints:**
- Total: exactly 3 minutes
- Rumi's responses must sound NATURAL and SHORT for voice (1-3 sentences max)
- Include barge-in demo, proactive ambient intervention, camera awareness, memory/context demo
- End with Google Gemini + Firebase tech stack callout
- Make it feel like a LIVE product, not a rehearsed chatbot demo
- Haris: natural, casual Karachi-engineer energy

## Response snapshot

Full 3-minute script delivered across 8 timestamped segments:
- [0:00–0:18] Cold open: Rumi speaks unprompted on ambient observation
- [0:18–0:45] Wake word + first conversation; memory recall of backend deadline
- [0:45–1:08] Memory/context demo: Rumi recalls past voice pipeline decision from Firestore
- [1:08–1:35] Barge-in demo: Haris interrupts mid-sentence, Rumi stops cleanly
- [1:35–1:55] Camera awareness: "who's in front of you?" → "That's Haris." (0.94 confidence)
- [1:55–2:18] Proactive intervention: Rumi fires unprompted after 12s of focus in same file
- [2:18–2:42] Tech stack callout: Gemini 2.5 Flash Native Audio + ADK + Firebase + Cloud Run
- [2:42–3:00] Close: Rumi's final line — "Yesterday you were a student. Today you built something. I noticed."
Timing table and presenter notes included. Rumi's Masnavi "reed" reference contextualized.

## Outcome

- Impact: Ready-to-use competition demo script covering all key product differentiators in 3:00 with correct timestamps
- Tests: none
- Files: history/prompts/general/019-demo-script-3min-rumi.general.prompt.md
- Next prompts: /sp.phr if further refinement needed; polish individual Rumi lines for tone; rehearsal run-through
- Reflection: Script surfaces all six constitution principles naturally without naming them — proactive presence, identity persistence, multimodal awareness, privacy-first, Gemini-native, Sufi-engineer soul all appear as live product behavior

## Evaluation notes (flywheel)

- Failure modes observed: none — request was clear and fully specified
- Graders run and results (PASS/FAIL): n/a (creative artifact, not code)
- Prompt variant (if applicable): none
- Next experiment: Record a dry run and check whether Rumi's longer turn at [2:18] needs to be cut for breath pacing
