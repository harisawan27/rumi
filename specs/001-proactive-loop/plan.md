# Implementation Plan: Identity-Aware Proactive Loop

**Branch**: `001-proactive-loop` | **Date**: 2026-03-06 | **Spec**: [spec.md](./spec.md)

## Summary

Build Mirr'at's core agentic loop: a Python backend agent that continuously observes Haris's
workspace via webcam (Gemini Multimodal Live API), detects emotional and cognitive state
triggers, and proactively initiates contextualised voice/text interventions — grounded in
Haris's Firebase-stored identity and prior session history. A Next.js frontend provides the
session UI, privacy indicator, and pause control. Everything deploys to Google Cloud Run in
7 days for the Google Gemini Live Agent Challenge.

## Technical Context

**Language/Version**: Python 3.11 (backend agent) · Next.js 14 / Node.js 20 (frontend)
**Primary Dependencies**:
- Backend: `google-generativeai` (Gemini SDK), `firebase-admin`, `opencv-python`,
  `websockets`, `fastapi`, `uvicorn`, `pillow`, `python-dotenv`
- Frontend: `next`, `react`, `firebase` (client SDK), `tailwindcss`

**Storage**: Firebase Firestore (cloud-hosted, ephemeral WebSocket sessions not stored)
**Testing**: `pytest` + `pytest-asyncio` (backend) · `jest` + `@testing-library/react` (frontend)
**Target Platform**: Desktop (macOS/Windows/Linux); deployed to Google Cloud Run
**Project Type**: Web application — Python backend + Next.js frontend
**Performance Goals**:
- Session start (auth + identity load): < 10 seconds (SC-001, SC-002)
- Trigger detection-to-intervention: < 2 min 45 sec from posture onset (SC-003, SC-004)
- Pause response time: < 2 seconds (SC-006)
- Session summary saved after close: < 30 seconds (SC-008)

**Constraints**:
- NO raw video or audio written to disk or database at any point (Principle V, FR-013, FR-019)
- Single authorised user (Haris's Google account); no multi-user support
- All AI capabilities via Gemini APIs only (Principle VI)
- Secrets in `.env` only; never committed

**Scale/Scope**: Single-user hackathon MVP; one concurrent session

## Constitution Check

*GATE: Must pass before Phase 0. Re-checked post-design.*

| # | Principle | Design Status | Evidence |
|---|-----------|---------------|----------|
| I | **Identity Persistence** | ✅ PASS | Core Identity Profile loaded from Firestore at session start (FR-002); injected into every Gemini prompt (FR-011) |
| II | **Proactive Ambient Presence** | ✅ PASS | Watchman loop triggers without user prompt; 45s analysis cycle; Trigger A/B fire autonomously (FR-005–010) |
| III | **Sufi-Engineer Soul** | ✅ PASS | System Prompt template (see research.md) embeds personality; Rumi quotes sourced accurately; Chai break suggestions included |
| IV | **Multimodal Awareness First** | ✅ PASS | All trigger detection via Gemini Multimodal Live API WebSocket video feed; text-only fallback only when camera unavailable |
| V | **Privacy-First by Design** | ✅ PASS | OpenCV frames sent directly to Gemini WebSocket — never written to disk; only text Interaction Summaries and Session Summaries stored in Firestore |
| VI | **Gemini-Native Architecture** | ✅ PASS | Core AI: Gemini Multimodal Live API + Gemini 2.0 Flash; Memory: Firebase Firestore; no third-party LLM |
| + | **Proactive Personalization Mandate** | ✅ ALL 5 PASS | Personalised ✅ · Proactive ✅ · Culturally grounded ✅ · Privacy-safe ✅ · Multimodal-first ✅ |

**No violations.** No complexity justification required.

## Project Structure

### Documentation (this feature)

```text
specs/001-proactive-loop/
├── plan.md              # This file
├── research.md          # Phase 0 — technology decisions
├── data-model.md        # Phase 0 — Firestore schema
├── quickstart.md        # Phase 1 — local dev setup
├── contracts/
│   └── api-contracts.md # REST + WebSocket contracts
└── tasks.md             # Phase 2 output (/sp.tasks — NOT created here)
```

### Source Code (repository root)

```text
mirrat/
├── backend/                        # Python agent
│   ├── src/
│   │   ├── auth/
│   │   │   └── firebase_auth.py    # Google OAuth token verification (Admin SDK)
│   │   ├── identity/
│   │   │   └── identity_loader.py  # Core Identity Profile + Session Summary loading
│   │   ├── session/
│   │   │   ├── session_manager.py  # Observation session lifecycle
│   │   │   └── auto_summarizer.py  # End-of-session 2-sentence summary generator
│   │   ├── watchman/
│   │   │   ├── state_monitor.py    # 45s analysis cycle orchestration
│   │   │   ├── trigger_a.py        # Frustration posture detection
│   │   │   └── trigger_b.py        # Coding block detection
│   │   ├── gemini/
│   │   │   ├── live_client.py      # Gemini Multimodal Live API WebSocket client
│   │   │   └── prompt_builder.py   # System Prompt assembly (identity + personality)
│   │   ├── memory/
│   │   │   ├── firestore_client.py # Firestore read/write operations
│   │   │   └── interaction_log.py  # Interaction Summary writer
│   │   └── api/
│   │       └── main.py             # FastAPI app (auth, session, health endpoints)
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── contract/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                       # Next.js UI
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Login / Sign-in with Google
│   │   │   └── dashboard/
│   │   │       └── page.tsx        # Main session view
│   │   ├── components/
│   │   │   ├── ObservationIndicator.tsx  # Active/paused camera indicator
│   │   │   ├── InterventionCard.tsx      # Displays proactive intervention
│   │   │   └── PauseButton.tsx           # One-click pause control
│   │   └── services/
│   │       ├── firebase.ts         # Firebase client initialisation
│   │       └── session.ts          # Session API calls to backend
│   ├── tests/
│   ├── next.config.ts
│   └── package.json
│
├── specs/001-proactive-loop/       # SDD artifacts (this directory)
├── .env.example                    # Required env vars (never commit .env)
├── docker-compose.yml              # Local dev: backend + frontend together
├── cloudbuild.yaml                 # GCP Cloud Build CI/CD pipeline
└── CLAUDE.md                       # Agent guidance (existing)
```

**Structure Decision**: Web application layout (Option 2) — Python backend is the agent
brain; Next.js frontend is the UX layer. Clean separation per constitution architecture
principle. Backend deploys as a Docker container to Cloud Run; frontend deploys as a
Next.js app (Cloud Run or Firebase Hosting).

## 7-Day Development Roadmap

> User-specified phases mapped to spec user stories and FRs.

### Phase 1 — Foundation (Days 1–2)
*Delivers: US1 (Sign-In & Identity Loading)*

**Day 1 — Auth & Identity**
- Firebase project setup: enable Google OAuth, create Firestore database
- Backend: `firebase_auth.py` — verify Google OAuth ID tokens with Admin SDK
- Backend: `firestore_client.py` — CRUD for Core Identity Profile
- Backend: `identity_loader.py` — load Core Identity + Session Summaries at session start
- Frontend: Sign-in page with Firebase Auth SDK (Google OAuth button)
- `.env.example` with all required keys documented

**Day 2 — Boilerplate & Session Skeleton**
- Backend: FastAPI app (`main.py`) with `/health`, `/auth/verify`, `/session/start`, `/session/end`
- Frontend: Dashboard page skeleton; `ObservationIndicator` component (static)
- Docker: `Dockerfile` for backend; `docker-compose.yml` for local dev
- Firestore seed: Create Haris's Core Identity document (name, location, projects, interests)

**Gate**: Haris can sign in, and Core Identity is retrievable from Firestore. ✅ US1 acceptance scenarios 1–3 testable.

---

### Phase 2 — The Senses (Days 3–4)
*Delivers: US3 (Coding Block Detection), US4 (Frustration Detection)*

**Day 3 — Gemini Multimodal Live Connection**
- Backend: `live_client.py` — establish WebSocket connection to Gemini Multimodal Live API
- Backend: OpenCV webcam capture loop at 15fps; encode frames as base64 JPEG; stream to Gemini
- Backend: `state_monitor.py` — 45-second analysis cycle; parse Gemini state response
- Backend: `trigger_b.py` — visual similarity check for coding block (10-minute threshold)

**Day 4 — Watchman Trigger Logic**
- Backend: `trigger_a.py` — frustration posture detection (hands on head / lean-back, 2-minute threshold)
- Backend: Trigger cooldown logic (30-minute suppression per trigger type)
- Backend: `interaction_log.py` — write Interaction Summary to Firestore on trigger fire
- Frontend: `InterventionCard` component — displays intervention text; accept/dismiss actions
- Frontend: `PauseButton` — calls `/session/pause`; updates `ObservationIndicator`

**Gate**: Camera observation loop running; Trigger A and B fire under simulated conditions; Interaction Summaries appear in Firestore. ✅ US3/US4 acceptance scenarios testable.

---

### Phase 3 — The Soul (Day 5)
*Delivers: US2 (Session Start Familiarity), US5 (Context-Injected Identity)*

**Day 5 — Context Injection & Personality**
- Backend: `prompt_builder.py` — assemble System Prompt from Core Identity + Session Summaries
  (see System Prompt Template in research.md)
- Backend: `session_manager.py` — load Session Summary at session start; inject into Gemini context
- Backend: `auto_summarizer.py` — generate 2-sentence Session Summary at session end using
  Gemini 2.0 Flash; write to Firestore `session_summaries` sub-collection
- Integrate: All Gemini interventions now use the assembled prompt; verify personalisation
- Test: First interaction in a new session references prior session content

**Gate**: Mirr'at greets Haris by name, mentions DoneKaro/RehnumaAI, can produce a Rumi quote. Session Summary saved at close. ✅ US2, US5, US6 acceptance scenarios testable.

---

### Phase 4 — Cloud & Polish (Day 6)
*Delivers: Automated deployment; Karachi-based 'Wise Engineer' personality; hackathon bonus criteria*

**Day 6 — GCP Deployment & Personality Tuning**
- `cloudbuild.yaml` — Cloud Build pipeline: test → Docker build → push to Artifact Registry
  → deploy to Cloud Run
- Verify WebSocket support on Cloud Run (concurrency = 1 for MVP; session affinity)
- Frontend: Deploy to Firebase Hosting or Cloud Run (second service)
- Personality target: **Karachi-based 'Wise Engineer'** — the agent must sound like someone who
  has debugged production systems at 2am AND quoted Rumi to a friend the same night.
  Concretely:
  - Chai break suggestions are specific and warm (not generic wellness prompts)
  - Urdu terms of warmth woven in naturally (yaar, bhai) when the moment calls for it
  - Rumi quotes selected for engineering situations (struggle, patience, flow)
  - Tone calibration: precise + brief when Haris is focused; warm + unhurried when frustrated
- Voice: Configure Gemini Live API voice output if available; calibrate tone to match the
  Wise Engineer persona; fallback to text display if voice unavailable
- Privacy audit: Confirm no raw frames reach Firestore; review Firestore security rules

**Gate**: `git push` triggers automated deployment to Cloud Run. Live URL accessible.
Wise Engineer personality verified by reviewing 3 triggered interventions. Privacy audit passes. ✅

---

### Phase 5 — The Submission (Day 7)
*Delivers: Competition-ready MVP; architecture diagram; 4-minute demo video*

**Day 7 — Bug Fixes, Diagram, Demo, Freeze**
- Final bug fixes: triage and resolve any issues found in Phase 4 end-to-end testing;
  focus on Trigger A/B reliability and session summary persistence
- End-to-end validation: sign-in → identity load → observation → Trigger A → Trigger B →
  session close → summary saved → next session loads summary; verify all 9 SCs
- **Architecture Diagram**: Generate a clean system diagram showing:
  - User (webcam + screen) → Next.js Frontend → Python Backend
  - Python Backend → Gemini Multimodal Live API (WebSocket)
  - Python Backend → Firebase Firestore (identity, summaries, interactions)
  - Cloud Build CI/CD → Cloud Run (backend) + Firebase Hosting (frontend)
  - Data flow: frame (ephemeral) vs. text summary (persisted)
  - Tool: draw.io, Excalidraw, or Mermaid embedded in README
- **4-minute demo video** recording — script outline:
  - 0:00–0:30 — Introduce Mirr'at: "not a chatbot, a companion"
  - 0:30–1:30 — Sign in as Haris; system loads identity; observation activates
  - 1:30–2:30 — Demonstrate Trigger A (frustration posture → Rumi quote + Chai break)
  - 2:30–3:30 — Demonstrate Trigger B (coding block → project-aware check-in for DoneKaro)
  - 3:30–4:00 — Show Firestore: Interaction Summary + Session Summary saved; next session
    opens and references yesterday's context
- Code freeze; tag release `v0.1.0-mvp`
- Final commit: `chore: freeze mvp release v0.1.0; add architecture diagram`

---

## Key Architectural Decisions

### 1. WebSocket Architecture (Gemini Multimodal Live API)

The backend maintains a persistent WebSocket connection to the Gemini Multimodal Live API
for the duration of each observation session. Frames are captured by OpenCV, encoded as
base64 JPEG, and streamed at 15fps. The Gemini session is initialised with the full System
Prompt (identity + personality) before the first frame is sent. State analysis is requested
every 45 seconds by querying the model within the existing WebSocket session.

**Why this approach**: The Gemini Multimodal Live API is designed for real-time streaming;
maintaining a single session avoids reconnection latency and preserves conversational
context across the full observation period.

### 2. Ephemeral Frame Processing

OpenCV captures frames in-memory → base64 encoded → sent to Gemini WebSocket → discarded.
No frame is written to disk or to Firestore. The only persistence is the text Interaction
Summary written after a trigger fires.

**Why this approach**: Directly satisfies Principle V (Privacy-First by Design) and FR-013.
There is no simpler approach that achieves the same privacy guarantee.

### 3. Firestore Sub-Collection Hierarchy

```
users/{userId}
  └── sessions/{sessionId}
        ├── interactions/{interactionId}
        └── (session_summary_id → top-level ref)

users/{userId}
  └── session_summaries/{summaryId}
```

Session Summaries are stored in a top-level sub-collection (not nested under sessions) so
they can be queried independently for session-start loading without reading all session data.

**Why this approach**: Efficient query pattern — loading the last N Session Summaries at
session start requires only one Firestore query with `orderBy created_at DESC, limit N`.

### 4. System Prompt Template (Sufi-Engineer Personality)

See `research.md` for the full template. Key design decisions:
- Template has a fixed "PERSONALITY" block (static, defines character)
- Template has a dynamic "USER CONTEXT" block (populated at session start from Firestore)
- Template has a dynamic "RECENT SESSION" block (populated from Session Summary)
- Assembled once at session start; reused for all interventions in the session

### 5. Auto-Summarizer (Gemini 2.0 Flash)

At session end, a separate Gemini 2.0 Flash call (not the Live API WebSocket) receives the
list of Interaction Summaries from the session and generates a 2-sentence summary. This
is a short-lived, non-streaming call — no need for a Live API connection.

**Why separate model call**: Live API WebSocket is closed at session end. A standard Gemini
call is sufficient for summarisation and is cheaper than maintaining a live connection.

## Risks

1. **Gemini Multimodal Live API WebSocket stability**: If the connection drops mid-session,
   the Watchman loop stalls. Mitigation: implement reconnection with exponential backoff;
   restore System Prompt on reconnect.
2. **Cloud Run WebSocket support**: Cloud Run has a 60-minute request timeout; persistent
   WebSocket sessions may be terminated. Mitigation: implement client-side keepalive ping;
   gracefully re-establish if dropped.
3. **Trigger A detection accuracy**: Hands-on-head / lean-back posture detection accuracy
   depends on Gemini's visual understanding. If < 80% (SC-003), fall back to asking "Are
   you doing okay?" after any prolonged static posture.

## Follow-ups & ADR Candidates

- 📋 **ADR candidate**: Gemini Multimodal Live API as the exclusive real-time AI interface —
  long-term consequences, no fallback LLM. Run `/sp.adr gemini-live-api-architecture`.
- 📋 **ADR candidate**: Firestore sub-collection hierarchy vs. flat collection design.
  Run `/sp.adr firestore-schema-design`.
- The System Prompt template format (research.md) should be reviewed before Phase 3
  implementation — changes after Day 5 are costly.
