---
description: "Task list for Identity-Aware Proactive Loop"
---

# Tasks: Identity-Aware Proactive Loop

**Input**: Design documents from `/specs/001-proactive-loop/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅ · quickstart.md ✅

**Organization**: Tasks grouped by user story to enable independent implementation and testing.
**Tests**: Not requested — no test tasks generated.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable (different files, no shared dependencies)
- **[Story]**: User story this task belongs to (US1–US6)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository structure, environment, and tooling — enables all subsequent work.

- [x] T001 Create monorepo folder structure: `backend/`, `frontend/`, per plan.md project structure
- [x] T002 [P] Create `backend/requirements.txt` with: `google-generativeai`, `firebase-admin`, `opencv-python`, `fastapi`, `uvicorn`, `websockets`, `pillow`, `python-dotenv`
- [x] T003 [P] Create `frontend/package.json` with: `next@14`, `react`, `firebase`, `tailwindcss`
- [x] T004 [P] Create `.env.example` with all required keys: `GEMINI_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_PATH`, `NEXT_PUBLIC_FIREBASE_*`, `AUTHORISED_USER_UID`, `SESSION_SUMMARY_DEPTH`, `IDLE_TIMEOUT_MINUTES`, `BACKEND_URL`
- [x] T005 [P] Create `backend/Dockerfile` (Python 3.11-slim base, copy src/, install requirements, expose 8000, CMD uvicorn)
- [x] T006 [P] Create `docker-compose.yml` (backend service on port 8000 + frontend service on port 3000, shared `.env`)
- [x] T007 Create `backend/src/__init__.py` and all sub-package `__init__.py` files for: `auth/`, `identity/`, `session/`, `watchman/`, `gemini/`, `memory/`, `api/`
- [x] T008 [P] Initialise Next.js 14 app in `frontend/` with `src/app/`, `src/components/`, `src/services/` directories and Tailwind CSS configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Firebase project wiring, Firestore client, FastAPI skeleton, and Google Auth — MUST complete before any user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T009 Create Firebase project: enable Google Auth provider and create Firestore database (Native mode) in Firebase console — record Project ID in `.env` ⚠ MANUAL STEP (Firebase console)
- [x] T010 Create `backend/src/memory/firestore_client.py` — initialise `firebase-admin` with service account from `FIREBASE_SERVICE_ACCOUNT_PATH`; expose `get_db()` returning the Firestore client
- [x] T011 Create `backend/src/auth/firebase_auth.py` — function `verify_id_token(token: str) -> dict` using `firebase-admin auth.verify_id_token()`; raises `AuthError` if token invalid or UID does not match `AUTHORISED_USER_UID`
- [x] T012 [P] Create `backend/src/api/main.py` — FastAPI app with: `GET /health` returning `{"status": "ok", "version": "0.1.0"}`; CORS middleware for frontend origin; auth dependency injecting verified UID into all protected routes
- [x] T013 [P] Create `frontend/src/services/firebase.ts` — initialise Firebase client SDK from `NEXT_PUBLIC_FIREBASE_*` env vars; export `auth` and `db` instances
- [x] T014 Create `backend/src/identity/seed_identity.py` — script to write Haris's Core Identity document to `users/uid_haris_001` in Firestore: name, location, projects (DoneKaro + RehnumaAI with status), interests (Rumi, Turkish culture, software craftsmanship)

**Checkpoint**: `/health` returns 200; `seed_identity.py` runs without error; Firestore document visible in Firebase console.

---

## Phase 3: User Story 1 — Secure Sign-In & Identity Loading (Priority: P1) 🎯 MVP

**Goal**: Haris signs in with Google; system loads his Core Identity from Firestore; observation mode activates within 10 seconds.

**Independent Test**: Sign in with the authorised Google account → system displays "Haris" → Core Identity document is loaded → session document created in Firestore. All within 10 seconds of auth completion.

### Implementation for User Story 1

- [x] T015 [P] [US1] Create `backend/src/identity/identity_loader.py` — `load_core_identity(uid: str) -> dict` reading from `users/{uid}` in Firestore; raises `IdentityNotFoundError` if document missing
- [x] T016 [P] [US1] Add `GET /identity` endpoint to `backend/src/api/main.py` — calls `load_core_identity`; returns Core Identity Profile JSON per `contracts/api-contracts.md`
- [x] T017 [US1] Create `frontend/src/app/page.tsx` — sign-in page with "Sign in with Google" button using Firebase Auth SDK (`signInWithPopup`); on success stores ID token and redirects to `/dashboard`
- [x] T018 [US1] Create `frontend/src/services/session.ts` — `verifyAuth(idToken)` calls `POST /auth/verify`; `getIdentity()` calls `GET /identity`; both include `Authorization: Bearer <token>` header
- [x] T019 [US1] Create `frontend/src/app/dashboard/page.tsx` — on mount: calls `verifyAuth` then `getIdentity`; displays Haris's name; renders `ObservationIndicator` (inactive state initially); handles auth failure by redirecting to sign-in
- [x] T020 [US1] Create `frontend/src/components/ObservationIndicator.tsx` — shows green dot + "Observing" when active; grey dot + "Paused" when paused; red dot + "Camera unavailable" in degraded mode

**Checkpoint**: US1 independently functional — sign in, see "Haris", Core Identity in Firestore.

---

## Phase 4: User Story 2 — Session Start with Immediate Familiarity (Priority: P1)

**Goal**: At session start, the system loads Core Identity + recent Session Summaries and configures the Sufi-Engineer personality before any interaction is generated.

**Independent Test**: Sign in after a session that produced a Session Summary. Trigger any intervention. Verify response references prior session content without Haris mentioning it first.

### Implementation for User Story 2

- [x] T021 [P] [US2] Extend `backend/src/identity/identity_loader.py` — add `load_session_summaries(uid: str, limit: int) -> list` querying `users/{uid}/session_summaries` ordered by `created_at desc`, limit from `SESSION_SUMMARY_DEPTH` env var (default 3)
- [x] T022 [P] [US2] Add `GET /session-summaries` endpoint to `backend/src/api/main.py` — calls `load_session_summaries`; returns list of summaries per `contracts/api-contracts.md`
- [x] T023 [US2] Create `backend/src/gemini/prompt_builder.py` — `build_system_prompt(identity: dict, summaries: list) -> str` assembling the full System Prompt from the template in `research.md` (PERSONALITY block + USER CONTEXT block + RECENT HISTORY block + CURRENT SESSION block); populates all `{variable}` slots
- [x] T024 [US2] Create `backend/src/gemini/live_client.py` — `GeminiLiveClient` class: `connect(system_prompt: str)` establishes Gemini Multimodal Live API WebSocket via `google-generativeai` async SDK with the assembled system prompt as `system_instruction`; `disconnect()` closes cleanly; stores active session
- [x] T025 [US2] Create `backend/src/session/session_manager.py` — `SessionManager` class: `start_session(uid: str)` loads identity + summaries → builds system prompt → connects `GeminiLiveClient` → creates Observation Session document in Firestore → returns `session_id`; stores session state

**Checkpoint**: US2 independently testable — new session starts with prior context loaded; first Gemini response references Haris by name and mentions a known project.

---

## Phase 5: User Story 3 — Frustration Detection & Compassionate Intervention (Priority: P2)

**Goal**: Watchman detects Trigger A (frustration posture > 2 minutes) and proactively offers a Rumi quote or Chai break.

**Independent Test**: Hold a frustration posture for 2+ minutes in front of the camera. Verify Rumi initiates an intervention within 2 min 45 sec containing a Rumi quote OR Chai break suggestion.

### Implementation for User Story 3

- [x] T026 [P] [US3] Create `backend/src/watchman/state_monitor.py` — `StateMonitor` class: `run_cycle()` sends the current frame to the active Gemini Live session with the analysis prompt: "Analyse this frame. Respond with JSON: {state, confidence, cues[]}"; parses response; returns `StateResult(state, confidence, cues)`; runs every 45 seconds via `asyncio`
- [x] T027 [P] [US3] Create `backend/src/watchman/trigger_a.py` — `FrustrationTracker` class: `update(state_result: StateResult)` increments elapsed time when state is `frustrated`; resets if state changes; returns `should_fire: bool` when elapsed ≥ 120 seconds; enforces 30-minute cooldown between firings (`last_fired_at` check)
- [x] T028 [US3] Create `backend/src/memory/interaction_log.py` — `log_interaction(uid, session_id, trigger_type, intervention_text, user_response) -> str` writes Interaction Summary to `users/{uid}/sessions/{session_id}/interactions/` in Firestore; returns `interaction_id`; also appends `interaction_id` to the parent session document's `interaction_ids` array
- [x] T029 [US3] Wire Trigger A firing into `backend/src/session/session_manager.py` — on `FrustrationTracker.should_fire`: call `GeminiLiveClient` to generate intervention text (within the existing session/context); send intervention to frontend via WebSocket; call `log_interaction` with trigger type `"A"`
- [x] T030 [US3] Add `POST /session/{session_id}/start` and `POST /interactions` endpoints to `backend/src/api/main.py` per `contracts/api-contracts.md`
- [x] T031 [US3] Create `frontend/src/components/InterventionCard.tsx` — displays intervention text with "Accept" and "Dismiss" buttons; on click sends `intervention_response` WebSocket message back to backend; auto-dismisses after 2 minutes if no response
- [x] T032 [US3] Create `frontend/src/components/PauseButton.tsx` — single button: calls `PUT /session/{session_id}/pause` or `/resume` depending on current state; updates `ObservationIndicator` state within 2 seconds of click

**Checkpoint**: US3 independently functional — frustration posture triggers an Interaction Summary in Firestore and displays an `InterventionCard` in the UI.

---

## Phase 6: User Story 4 — Coding Block Detection & Project-Aware Check-In (Priority: P3)

**Goal**: Watchman detects Trigger B (static screen > 10 minutes) and generates a project-specific check-in question by name.

**Independent Test**: Keep a static screen for 10+ minutes. Verify Rumi generates a question naming one of Haris's active projects (DoneKaro or RehnumaAI).

### Implementation for User Story 4

- [x] T033 [P] [US4] Create `backend/src/watchman/trigger_b.py` — `CodingBlockTracker` class: accepts `StateResult`; compares current frame hash to previous frame hash (using `hashlib.md5` on frame bytes) to detect visual stasis; increments elapsed time when screen is unchanged; fires when elapsed ≥ 600 seconds; enforces 30-minute cooldown; distinct from Trigger A so both can track independently
- [x] T034 [US4] Wire Trigger B into `backend/src/session/session_manager.py` — on `CodingBlockTracker.should_fire`: call `GeminiLiveClient` for a project-specific check-in; the prompt MUST instruct Gemini to reference one of Haris's active projects by name from the loaded identity context; call `log_interaction` with trigger type `"B"`
- [x] T035 [US4] Update `backend/src/watchman/state_monitor.py` — pass both `FrustrationTracker` and `CodingBlockTracker` into each 45-second cycle; if both would fire simultaneously, fire Trigger A only and defer Trigger B to the next cycle (per spec edge case)

**Checkpoint**: US4 independently functional — static screen for 10+ minutes triggers a project-specific check-in naming DoneKaro or RehnumaAI; logged as Interaction Summary with trigger type "B".

---

## Phase 7: User Story 5 — Context-Injected Identity in Every Response (Priority: P2)

**Goal**: Every Rumi intervention references at least one Core Identity element; Rumi quotes are accurate and attributed.

**Independent Test**: Trigger any intervention (A or B). Verify the response includes Haris's name, a project name, or a verified Rumi quote with citation.

### Implementation for User Story 5

- [x] T036 [P] [US5] Add Rumi quote verification gate to `backend/src/gemini/prompt_builder.py` — include the curated Rumi quote pool from `research.md` as a JSON block in the System Prompt's PERSONALITY section; instruct the model: "When quoting Rumi, use ONLY the verified quotes below or explicitly say 'in the spirit of Rumi'. Never fabricate a quotation."
- [x] T037 [US5] Add intervention quality check to `backend/src/session/session_manager.py` — after Gemini generates intervention text, verify it contains at least one of: Haris's name, a known project name, a Rumi attribution, or a culturally specific reference (Chai, yaar, bhai); if not, retry once with an explicit instruction; log a warning if retry also fails
- [x] T038 [P] [US5] Create `frontend/src/services/session.ts` websocket handler — parse `intervention` WebSocket messages; extract `trigger`, `text`, `interaction_id`; pass to `InterventionCard`; send `intervention_response` back on user action

**Checkpoint**: US5 — 10 triggered interventions (5× Trigger A, 5× Trigger B), all 10 reference at least one identity element. Zero hallucinated Rumi quotes.

---

## Phase 8: User Story 6 — Automatic Session Summary at Close (Priority: P2)

**Goal**: Auto-Summarizer generates and saves a 2-sentence plain-text Session Summary to Firestore within 30 seconds of every session end.

**Independent Test**: Complete a session with at least one intervention. Close Rumi. Verify a `session_summaries` document appears in Firestore within 30 seconds, containing 2 plain-text sentences.

### Implementation for User Story 6

- [x] T039 [P] [US6] Create `backend/src/session/auto_summarizer.py` — `AutoSummarizer` class: `summarize(uid, session_id) -> str` reads all Interaction Summaries from `users/{uid}/sessions/{session_id}/interactions/`; calls Gemini 2.0 Flash (non-streaming) with the Auto-Summarizer prompt from `research.md`; validates response is exactly 2 sentences of plain text; returns summary text
- [x] T040 [US6] Add `POST /session/{session_id}/end` endpoint to `backend/src/api/main.py` — sets session `status="ended"`, `ended_at`; triggers `auto_summarizer.summarize()` as a `asyncio` background task; returns `202 Accepted` with `summary_status: "generating"` per contract
- [x] T041 [US6] Extend `backend/src/session/auto_summarizer.py` — `save_summary(uid, session_id, summary_text, duration_minutes)` writes Session Summary to `users/{uid}/session_summaries/`; updates parent session document with `session_summary_id`; implements one retry on Firestore write failure before logging error
- [x] T042 [US6] Add `PUT /session/{session_id}/pause` and `PUT /session/{session_id}/resume` endpoints to `backend/src/api/main.py` per contracts; `pause` halts the Watchman loop; `resume` restarts it with the existing system prompt (no reload needed)
- [x] T043 [US6] Implement idle timeout in `backend/src/session/session_manager.py` — if session remains `paused` for longer than `IDLE_TIMEOUT_MINUTES` (default 30), automatically call the session end flow to trigger Auto-Summarizer

**Checkpoint**: US6 independently functional — close the app after a session with interventions; verify Firestore `session_summaries` document created within 30 seconds.

---

## Phase 9: Cloud & Polish — Phase 4 of Roadmap (Day 6)

**Purpose**: Automated GCP deployment; Karachi-based 'Wise Engineer' personality tuning; privacy audit.

- [x] T044 Create `cloudbuild.yaml` — 4-step Cloud Build pipeline: (1) `pytest backend/tests/` (2) `docker build -t gcr.io/$PROJECT_ID/rumi-backend .` (3) `docker push gcr.io/$PROJECT_ID/rumi-backend` (4) `gcloud run deploy rumi-backend --image ... --session-affinity --timeout=3600 --min-instances=1 --max-instances=1`
- [x] T045 [P] Add Firebase Hosting config (`firebase.json`, `.firebaserc`) — configure Next.js static export for `frontend/`; add Hosting deploy as step 5 in `cloudbuild.yaml`
- [x] T046 Refine System Prompt in `backend/src/gemini/prompt_builder.py` for Karachi-based 'Wise Engineer' persona — add explicit Chai break phrasing examples, approved Urdu warmth terms (yaar, bhai), tone calibration instructions (precise + brief when focused; warm + unhurried when frustrated); include 4 verified Rumi quotes for engineering moments from `research.md`
- [x] T047 [P] Privacy audit: add assertion in `backend/src/gemini/live_client.py` that frame bytes are sent directly to the WebSocket and never written to any file path or Firestore; add `PRIVACY_CHECK` log line on each frame send confirming ephemeral processing
- [x] T048 Update `backend/src/memory/firestore_client.py` — add Firestore security rules file `firestore.rules` enforcing: read/write only for authenticated UID matching `AUTHORISED_USER_UID`; deploy rules with `firebase deploy --only firestore:rules`
- [ ] T049 Manual deploy test: `git push origin 001-proactive-loop` triggers Cloud Build; verify deployment succeeds; verify Cloud Run URL responds to `GET /health` ⚠ MANUAL STEP

---

## Phase 10: Submission — Phase 5 of Roadmap (Day 7)

**Purpose**: Final bug fixes, architecture diagram, 4-minute demo video, code freeze.

- [ ] T050 [P] End-to-end validation run: sign-in → identity load → observation → Trigger A (frustration) → Trigger B (coding block) → session close → session summary saved → new session opens → prior session summary referenced; verify all 9 SCs (SC-001 through SC-009) pass ⚠ MANUAL STEP
- [ ] T051 Fix any bugs found in T050; focus on Trigger A/B reliability and Session Summary Firestore write timing ⚠ MANUAL STEP
- [x] T052 Create architecture diagram in `docs/architecture.md` using Mermaid — diagram shows: Next.js frontend ↔ Python backend (REST + WebSocket); Python backend ↔ Gemini Multimodal Live API; Python backend ↔ Firebase Firestore; Cloud Build CI/CD → Cloud Run (backend) + Firebase Hosting (frontend); annotates ephemeral frame path vs. persisted text summary path
- [x] T053 [P] Update `README.md` — embed architecture diagram; add project description ("Not a chatbot — a Karachi-based Wise Engineer companion"); link to quickstart.md; add competition context (Google Gemini Live Agent Challenge)
- [ ] T054 Record 4-minute demo video following the script from `plan.md` Phase 5: intro → sign-in + identity load → Trigger A (Rumi quote) → Trigger B (DoneKaro check-in) → Firestore proof of Interaction Summary + Session Summary → next session loads yesterday's context ⚠ MANUAL STEP
- [ ] T055 Code freeze: `git tag v0.1.0-mvp && git push origin v0.1.0-mvp` ⚠ MANUAL STEP
- [ ] T056 Final commit: `git commit -m "chore: freeze mvp release v0.1.0; add architecture diagram"` ⚠ MANUAL STEP

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational; no dependency on other stories 🎯 MVP
- **US2 (Phase 4)**: Depends on Foundational + US1 (session model, auth, identity already built)
- **US3 (Phase 5)**: Depends on Foundational + US2 (Gemini Live client + session manager needed)
- **US4 (Phase 6)**: Depends on Foundational + US2 (shares StateMonitor and session infrastructure)
- **US5 (Phase 7)**: Depends on US3 + US4 (both intervention types must exist to validate)
- **US6 (Phase 8)**: Depends on US3 (Interaction Summary logging must exist for Auto-Summarizer input)
- **Cloud & Polish (Phase 9)**: Depends on all user stories complete
- **Submission (Phase 10)**: Depends on Phase 9

### Parallel Opportunities Within Phases

```bash
# Phase 1 — all [P] tasks run together:
T002, T003, T004, T005, T006, T008  # requirements, package.json, .env, Dockerfile, docker-compose, Next.js init

# Phase 2 — after T009 (Firebase setup):
T010, T011, T012, T013  # firestore_client, firebase_auth, FastAPI skeleton, firebase.ts client

# Phase 3 (US1) — after T012, T013:
T015, T016  # identity_loader + /identity endpoint (backend)
# T017, T018, T019, T020 sequential (frontend depends on services)

# Phase 4 (US2) — T021, T022 parallel:
T021, T022  # load_session_summaries + /session-summaries endpoint

# Phase 5 (US3) — T026, T027, T028 parallel (different files):
T026, T027, T028  # StateMonitor, FrustrationTracker, interaction_log

# Phase 6 (US4):
T033  # CodingBlockTracker (independent file, parallel with T034 prep)

# Phase 9 (Polish):
T044, T045, T047, T048  # cloudbuild, Firebase Hosting, privacy audit, security rules (parallel)
```

### User Story Dependencies (independence summary)

- **US1 (P1)**: Independent after Foundational ✅ Deploy/demo as MVP
- **US2 (P1)**: Builds on US1 session infrastructure — NOT fully independent, but P1 priority
- **US3 (P2)**: Depends on US2 for Gemini Live client — test Trigger A independently once US2 ✅
- **US4 (P3)**: Shares US2 infrastructure — test Trigger B independently once US2 ✅
- **US5 (P2)**: Validates US3 + US4 output quality — depends on both triggers existing
- **US6 (P2)**: Depends on US3 (Interaction Summary logging) for Auto-Summarizer input

---

## Implementation Strategy

### MVP First (Day 1–2: US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (Firebase + FastAPI skeleton)
3. Complete Phase 3: US1 (sign-in + identity load)
4. **STOP and VALIDATE**: Haris signs in, name displayed, Core Identity in Firestore
5. Demo: single-screen sign-in → greeting

### 7-Day Incremental Delivery

- **Day 1**: Phase 1 (Setup) + Phase 2 (Foundational)
- **Day 2**: Phase 3 (US1: Sign-In & Identity Loading) ← **MVP gate**
- **Day 3**: Phase 4 (US2: Session Start Familiarity) + Phase 5 partial (Gemini Live connect)
- **Day 4**: Phase 5 complete (US3: Frustration Detection + Trigger A)
- **Day 5**: Phase 6 (US4: Coding Block) + Phase 7 (US5: Context Injection) + Phase 8 (US6: Auto-Summarizer)
- **Day 6**: Phase 9 (Cloud & Polish: GCP deploy + Wise Engineer personality)
- **Day 7**: Phase 10 (Submission: bug fixes + diagram + demo video + freeze)

---

## Notes

- [P] tasks = different files, no shared dependencies — safe to parallelize
- [Story] label maps task to user story for traceability
- No test tasks generated (not requested); add `/sp.tasks --tdd` if TDD approach needed later
- Every user story has a **Checkpoint** — validate independently before moving to next story
- Privacy constraint: NEVER write raw video frames to disk or Firestore — enforced in T047
- Commit after each Checkpoint (US1, US2, US3, US4, US5, US6, Cloud, Submission)
- Total tasks: **56** across 10 phases
