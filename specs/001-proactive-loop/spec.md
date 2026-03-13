# Feature Specification: Identity-Aware Proactive Loop

**Feature Branch**: `001-proactive-loop`
**Created**: 2026-03-06
**Last Updated**: 2026-03-06
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Secure Sign-In & Identity Loading (Priority: P1)

Haris opens Mirr'at for the first time in a session. He is presented with a "Sign in with
Google" prompt. After completing the sign-in, the system greets him by name, silently loads
his Core Identity Profile (projects, interests, location), and activates the ambient
observation session — all without Haris having to configure anything.

**Why this priority**: Without authentication and identity loading, no other story is
possible. This is the on-ramp for the entire Proactive Personalization model.

**Independent Test**: Sign in, verify that the system displays Haris's name and immediately
enters the observation state. Core Identity (DoneKaro, RehnumaAI, Rumi interests) must be
retrievable from the memory store after sign-in.

**Acceptance Scenarios**:

1. **Given** Mirr'at is open and Haris is not signed in, **When** Haris clicks "Sign in with
   Google" and authorises with his account, **Then** the system loads his Core Identity and
   enters active observation mode within 10 seconds of authorisation completing.
2. **Given** Haris is signed in, **When** he reopens Mirr'at after closing it, **Then** his
   session is resumed without requiring re-authentication, and identity data is loaded
   automatically.
3. **Given** a Google account that is NOT Haris's, **When** that account attempts sign-in,
   **Then** the system denies access and displays an appropriate message.

---

### User Story 2 — Session Start with Immediate Familiarity (Priority: P1)

Before Mirr'at speaks its first word in any session, it has already "remembered" who Haris
is and what happened yesterday. The system loads both his Core Identity and a digest of
recent past sessions, then configures its personality — Sufi-Engineer tone, culturally
grounded, aware of active projects — so that the very first interaction feels as though
Haris is resuming a conversation with a knowledgeable old friend, not starting from zero.

**Why this priority**: Immediate familiarity is the moment that converts a tool into a
companion. If the first interaction is generic, the emotional contract is broken. This is
the experience that must succeed for the product to resonate with judges and with Haris.

**Independent Test**: Close and reopen Mirr'at the day after a session that produced
Interaction Summaries. Trigger any intervention in the new session. Verify that the
response references something from the prior day's session (e.g., a project milestone or
emotional moment recorded in the Session Summary), without Haris mentioning it first.

**Acceptance Scenarios**:

1. **Given** one or more Session Summaries exist from prior sessions, **When** a new
   session starts and identity is loaded, **Then** the system incorporates the most recent
   Session Summary content into its active context before generating any intervention.
2. **Given** no prior Session Summaries exist (first-ever session), **When** the session
   starts, **Then** the system falls back to Core Identity alone and MUST NOT fail or
   display an error.
3. **Given** a session has started with context loaded, **When** Mirr'at generates any
   response, **Then** the response is tonally consistent with the Sufi-Engineer personality
   (technically precise, empathetic, culturally grounded) from the first interaction.
4. **Given** multiple Session Summaries exist, **When** context is loaded, **Then** the
   system uses the most recent summary (or the most recent N summaries, up to a reasonable
   depth) — not the entire history — to keep context current and relevant.

---

### User Story 3 — Frustration Detection & Compassionate Intervention (Priority: P2)

While working, Haris enters a prolonged state of frustration — visible through his posture
(hands on head, leaning back). After this persists for 2 minutes, Mirr'at proactively
reaches out with a culturally appropriate comfort: a Rumi quote, or a suggestion to take
a 5-minute break.

**Why this priority**: This is the most emotionally significant intervention and the one most
likely to wow competition judges. Detecting distress and responding with empathy — not a
generic alert — is the core promise of Mirr'at.

**Independent Test**: Simulate a sustained frustration posture in front of the camera for
2+ minutes. Verify that Mirr'at initiates an intervention within the next 45-second
analysis cycle (maximum 2 min 45 sec from posture onset). Verify the response contains a
Rumi quote OR a specific break suggestion.

**Acceptance Scenarios**:

1. **Given** Haris is in active observation mode, **When** he holds a frustration posture
   (hands on head or clearly leaning back with signs of distress) continuously for 2
   minutes, **Then** Mirr'at initiates a spoken or displayed intervention offering a Rumi
   quote or a 5-minute Chai break suggestion.
2. **Given** an intervention was recently offered, **When** the same trigger occurs again
   within 30 minutes, **Then** Mirr'at does NOT repeat the same intervention.
3. **Given** Haris dismisses an intervention (closes it or says "not now"), **When** the
   frustration posture reappears later, **Then** the frustration timer resets and the
   intervention will only fire again after another full 2 minutes.
4. **Given** an intervention is offered, **When** it completes, **Then** the system records
   a text-only Interaction Summary (trigger type, intervention offered, user response) in
   Haris's memory store — no raw video or audio is stored.

---

### User Story 4 — Coding Block Detection & Project-Aware Check-In (Priority: P3)

Haris has been staring at the same section of code for 10 minutes with no meaningful
change on screen. Mirr'at detects this stagnation and proactively asks a specific question
about the project he is working on — referencing it by name and asking about something
concrete (e.g., "How's the Docker setup going for DoneKaro?").

**Why this priority**: This story demonstrates that Mirr'at is genuinely context-aware, not
just reacting to emotional cues. A project-specific check-in is far more valuable than a
generic "Are you stuck?".

**Independent Test**: Keep a static screen (code editor, no scroll or edits) visible to the
camera for 10+ minutes. Verify that Mirr'at generates a question referencing one of Haris's
known projects by name.

**Acceptance Scenarios**:

1. **Given** Haris is in active observation mode with his Core Identity loaded, **When**
   the visible screen content remains unchanged for 10 consecutive minutes, **Then** Mirr'at
   initiates a check-in that references a specific project from Haris's identity profile by
   name.
2. **Given** Mirr'at initiates a check-in, **When** Haris responds verbally or in text,
   **Then** Mirr'at continues the conversation using the same project context.
3. **Given** a check-in was offered for a specific project, **When** the same coding block
   state reoccurs within 30 minutes, **Then** Mirr'at does NOT offer the same check-in
   message again.

---

### User Story 5 — Context-Injected Identity in Every Response (Priority: P2)

Every response Mirr'at generates — whether an intervention, a reply, or unsolicited wisdom
— MUST draw on Haris's Core Identity. The response should feel as though it comes from
someone who knows Haris well: his name, his projects, his love of Rumi, his cultural
context.

**Why this priority**: Without context injection, Mirr'at degrades into a generic AI
assistant. This story is the glue that makes every other story feel personal.

**Independent Test**: Trigger any intervention (Trigger A or B). Verify that the
intervention message references at least one piece of Haris's Core Identity (name,
project, cultural reference, or Rumi quote where appropriate).

**Acceptance Scenarios**:

1. **Given** Haris is signed in and his Core Identity is loaded, **When** Mirr'at generates
   any proactive intervention, **Then** the response incorporates at least one identity
   element (name, active project, or culturally resonant reference).
2. **Given** Mirr'at offers a Rumi quote, **When** the quote is displayed or spoken,
   **Then** it is attributed correctly and is an accurate quotation, not a paraphrase.

---

### User Story 6 — Automatic Session Summary at Close (Priority: P2)

When Haris ends his work session — whether by closing Mirr'at, signing out, or triggering
a prolonged idle state — the system automatically generates a concise 2-sentence summary
of what happened during the session: the emotional states detected, the interventions
offered, and any notable moments. This summary is saved silently so that tomorrow's session
begins with that memory already loaded.

**Why this priority**: The Auto-Summarizer is what converts a single session into a
long-term relationship. Without it, each session is stateless. With it, Mirr'at grows more
familiar with Haris over time — a key differentiator in the 'Live Agents' category.

**Independent Test**: Complete a session that included at least one intervention. Close
Mirr'at. Verify that a new Session Summary entry exists in the memory store containing
a human-readable 2-sentence description of the session's key events.

**Acceptance Scenarios**:

1. **Given** a session has ended (Mirr'at closed or user signed out), **When** the session
   contained at least one Interaction Summary, **Then** the system automatically generates
   a 2-sentence Session Summary and saves it to the persistent memory store within 30
   seconds of session end — without any action from Haris.
2. **Given** a session ends with no interventions (Haris worked uninterrupted), **When**
   the session closes, **Then** the system still generates a Session Summary noting the
   calm, focused session, and saves it.
3. **Given** the memory store is temporarily unreachable at session end, **When** the
   Auto-Summarizer attempts to save, **Then** it MUST retry at least once before logging
   a local failure record; the app MUST NOT crash.
4. **Given** many sessions have accumulated, **When** new Session Summaries are added,
   **Then** the system retains a rolling window of the most recent summaries (depth to be
   determined at planning) and does not allow the store to grow unboundedly.

---

### Edge Cases

- Camera unavailable or permission denied → Mirr'at MUST enter graceful degraded mode: no
  observation, identity still loaded, user clearly informed. Visual triggers are disabled;
  text-based interaction remains available.
- Memory store unreachable at sign-in → Sign-in MUST fail with a clear error. System MUST
  NOT operate without the Core Identity loaded.
- Memory store unreachable at session end → Auto-Summarizer MUST retry once, then log a
  local failure record. App MUST NOT crash.
- Trigger A and Trigger B active simultaneously → Trigger A (frustration) takes precedence;
  coding block check-in is deferred until the next cycle.
- Haris does not respond to an intervention → After 2 minutes, the system records "no
  response" in the Interaction Summary and resumes observation.
- Screen content changes just before the 10-minute threshold → Coding block timer MUST
  reset completely upon any meaningful screen change.
- No prior Session Summaries exist (first-ever session) → System falls back to Core
  Identity alone; MUST NOT error or display a warning to the user.
- Session ends immediately after starting (< 1 minute) → Auto-Summarizer MUST still run
  and produce a valid (brief) summary; zero-length sessions are not an error state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate Haris via his Google account and reject all other
  accounts without granting access.
- **FR-002**: System MUST load the Core Identity Profile (name, location, projects,
  interests) from the persistent memory store within 10 seconds of successful
  authentication.
- **FR-003**: System MUST load the most recent Session Summary (or summaries, up to a
  configured depth) from the persistent memory store at session start, before any
  interaction or intervention is generated.
- **FR-004**: System MUST configure its personality at session start to embody the
  Sufi-Engineer blend — technically precise, empathetic, culturally grounded, aware of
  Haris's projects and past sessions — for the duration of the session.
- **FR-005**: System MUST activate the visual observation session automatically upon
  successful sign-in, requiring no manual action from Haris.
- **FR-006**: System MUST analyze the visual feed at a regular interval (every 45 seconds)
  to detect trigger conditions.
- **FR-007**: System MUST detect Trigger A: frustration posture (hands on head or sustained
  lean-back with visible distress cues) persisting for 2 or more consecutive minutes.
- **FR-008**: System MUST respond to Trigger A with a proactive intervention containing
  either an accurate Rumi/Sufi quote or a specific break suggestion (e.g., Chai break).
- **FR-009**: System MUST detect Trigger B: visually unchanged screen content sustained for
  10 or more consecutive minutes.
- **FR-010**: System MUST respond to Trigger B with a contextually specific check-in
  question that references one of Haris's active projects by name.
- **FR-011**: System MUST inject the Core Identity Profile AND the loaded Session Summary
  context into the active context for EVERY generated intervention response, ensuring all
  responses are personalised and historically grounded.
- **FR-012**: System MUST NOT re-trigger the same intervention type within 30 minutes of
  its last occurrence.
- **FR-013**: System MUST record each completed intervention as a text-only Interaction
  Summary in the persistent memory store; raw video and audio MUST NOT be stored.
- **FR-014**: System MUST provide Haris with a single-action mechanism (one click or one
  keypress) to pause all observation at any time.
- **FR-015**: System MUST display a persistent visual indicator whenever observation is
  active.
- **FR-016**: System MUST resume a paused session when Haris explicitly re-enables
  observation; the session MUST restore context from the last known state.
- **FR-017**: System MUST automatically generate a 2-sentence Session Summary at the end
  of every session (on close, sign-out, or prolonged idle), capturing the key emotional
  states detected and interventions offered during that session.
- **FR-018**: The Session Summary MUST be saved to the persistent memory store without
  any action from Haris, within 30 seconds of session end.
- **FR-019**: Session Summaries MUST be stored as human-readable plain text only; no raw
  video, audio, or unprocessed sensor data may be included.
- **FR-020**: The system MUST retain only a rolling window of Session Summaries (exact
  depth defined at planning); it MUST NOT allow unbounded accumulation.

### Key Entities

- **Core Identity Profile**: The persistent record of Haris's identity attributes — name,
  location, known projects (with status/context), interests (Rumi, Turkish culture,
  craftsmanship). Loaded at session start; source of truth for personalisation.
  *Fields*: user_id, name, location, projects (list with name + last_known_status),
  interests (list), last_updated.

- **Session Summary**: A 2-sentence, human-readable text record auto-generated at the end
  of each session. Captures the session's key emotional states and notable interventions.
  Used to seed the next session's context. This is the long-term relationship memory unit.
  *Fields*: summary_id, user_id, session_date, summary_text (2 sentences max), session_duration_minutes.

- **Interaction Summary**: An immutable, text-only log entry written after each individual
  intervention within a session — captures trigger type, timestamp, intervention content
  offered, and user response (accepted/dismissed/no response).
  *Fields*: interaction_id, session_id, trigger_type (A/B), triggered_at, intervention_text,
  user_response, response_at.

- **Observation Session**: A bounded period of active monitoring — tracks start time,
  active/paused/ended status, list of Interaction Summary IDs generated, and links to
  the resulting Session Summary.
  *Fields*: session_id, user_id, started_at, ended_at, status, interaction_ids (list),
  session_summary_id.

- **Trigger State**: A transient (in-memory only, never persisted) record of the current
  posture or screen state being tracked — elapsed time, trigger type, threshold-crossed
  flag.

- **Personality Configuration**: The assembled set of behavioral rules, cultural context,
  and recent memory loaded into the AI's active context at session start. Defines tone,
  quote sources, and intervention style for the session. Constructed at runtime from Core
  Identity + Session Summaries; never stored directly.
  *Note*: The specific format of this configuration (the "System Prompt template") is an
  architectural decision documented in plan.md.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Haris can complete sign-in and reach active observation mode in under 10
  seconds from clicking "Sign in with Google".
- **SC-002**: At session start, the system loads Core Identity AND the most recent Session
  Summary and begins observation — all within 10 seconds of authentication.
- **SC-003**: The system correctly identifies a frustration posture (Trigger A) in at least
  80% of test cases when the posture is held for the required duration.
- **SC-004**: The system correctly identifies a coding block (Trigger B) in at least 85%
  of test cases when the screen is visually unchanged for the required duration.
- **SC-005**: Every proactive intervention references at least one element of Haris's Core
  Identity Profile — verifiable in 100% of triggered interventions.
- **SC-006**: Haris can pause all observation with a single action; pause takes effect
  within 2 seconds of the action.
- **SC-007**: No raw video or audio data is present in the persistent memory store at any
  point — verifiable by inspecting the store after any session.
- **SC-008**: A Session Summary is generated and saved within 30 seconds of every session
  end, in 100% of sessions that included at least one Interaction Summary.
- **SC-009**: All stored records (Interaction Summaries and Session Summaries) are
  human-readable plain text — verifiable by direct inspection of the memory store.

## Assumptions

- **Context Injection mechanism**: At session start, the system compiles Core Identity +
  recent Session Summaries into a single structured context block. This block is active for
  the entire session and used for every generated response. The exact format of this block
  (the "System Prompt template" including the Sufi-Engineer personality) is an
  architectural decision deferred to plan.md.
- **Firebase schema**: Key Entities above define the data model at business level, with
  field names as a guide. The exact Firestore collection hierarchy, indexing strategy, and
  security rules are architectural decisions deferred to plan.md.
- **Folder/project structure**: The Python (backend agent) + Next.js (frontend) code
  organisation is an architectural decision deferred to plan.md. This spec does not
  prescribe implementation structure.
- **Session Summary depth**: "Most recent N summaries" loaded at session start — exact N
  to be determined at planning based on context window constraints.
- **Auto-Summarizer trigger**: "Session end" is defined as: Mirr'at window closed, user
  signs out, or observation has been paused for more than a configurable idle threshold.
  Exact idle threshold defined at planning.
- **Single-user scope**: Only Haris's account is in scope; multi-user support is out of
  scope for this feature.
- **Analysis interval is fixed**: The 45-second analysis cycle is a fixed value for v1;
  runtime configuration is not required.
- **"Same code window" detection**: Coding block detection is based on visual similarity of
  screen content (static/unchanged frames), not application-level hooks or IDE plugins.
- **Rumi quote accuracy**: Quotes must be drawn from a verified source or explicitly marked
  as a paraphrase; hallucinated quotes are a Principle III violation.
