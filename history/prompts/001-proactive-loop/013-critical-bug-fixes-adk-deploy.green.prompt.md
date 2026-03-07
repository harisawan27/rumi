---
id: "013"
title: critical bug fixes adk deploy
stage: green
date: 2026-03-07
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: audit
labels: ["bug-fix","adk","deploy","firestore","cors","frontend"]
links:
  spec: specs/001-proactive-loop/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/agent/mirrat_agent.py
  - frontend/next.config.ts
  - cloudbuild.yaml
tests:
  - none
---

## Prompt

Is there anything left that will cause point deductions? Going for gold or nothing.

## Response snapshot

Found 3 issues:

1. CRITICAL — ADK `get_user_context()` read from `users/{uid}/core_identity` subcollection (doesn't exist). Identity is at `users/{uid}` doc directly. Tool silently always returned hardcoded fallback. Fixed to read `users.limit(1).stream()` → `to_dict()`.

2. CRITICAL — `next.config.ts` had `output: "standalone"` (Node.js server) but `firebase.json` expected `public: "frontend/out"` (static export). Firebase Hosting would serve empty folder. Also `cloudbuild.yaml` ran `firebase deploy` without ever running `npm run build`. Fixed: changed to `output: "export"` + `trailingSlash: true`, added npm build step in cloudbuild.yaml.

3. MODERATE — `FRONTEND_URL` not injected into backend CORS on deploy. All API calls from deployed frontend would be blocked. Fixed: added `FRONTEND_URL` to `--set-env-vars` and `availableSecrets`; added `BACKEND_URL` secret for frontend build env var.

## Outcome

- Impact: ADK tool now actually loads live Firestore identity. Frontend deploy now produces static export correctly. CORS won't block production API calls.
- Tests: none (manual verification needed)
- Files: 3 files modified
- Next prompts: add NEXT_PUBLIC_BACKEND_URL usage in session.ts, surface ADK status in UI
- Reflection: The ADK Firestore bug was the most dangerous — it would have worked in demo but judges inspecting logs would see the tool always returning hardcoded data.

## Evaluation notes (flywheel)

- Failure modes observed: Wrong Firestore subcollection path, wrong Next.js output mode, missing build step, missing CORS origin
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add NEXT_PUBLIC_BACKEND_URL to .env.local and use it in session.ts instead of hardcoded localhost
