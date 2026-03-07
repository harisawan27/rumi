# Research: Identity-Aware Proactive Loop

**Feature**: `001-proactive-loop`
**Date**: 2026-03-06
**Status**: Complete — all unknowns resolved

---

## 1. Gemini Multimodal Live API — WebSocket Connection

**Decision**: Use `google-genai` Python SDK with `client.aio.live.connect()` for async
WebSocket sessions. Send video frames as `Blob` with MIME type `image/jpeg`. Maintain a
single session per observation period; re-establish on disconnect.

**Rationale**: The Live API is purpose-built for real-time multimodal streaming. The async
client avoids blocking the main observation loop. Sending compressed JPEG (vs. PNG) reduces
bandwidth without meaningful quality loss at 15fps webcam resolution.

**Alternatives considered**:
- REST polling to Gemini Vision: rejected — too high latency for real-time state detection
- Third-party computer vision library (MediaPipe): rejected — violates Principle VI
  (Gemini-Native Architecture)

**Key implementation notes**:
- Session is initialised with `config={"system_instruction": <assembled_prompt>}`
- State analysis prompt sent every 45 seconds: "Analyse the last frame. Respond with JSON:
  `{"state": "focused|frustrated|idle|neutral", "confidence": 0.0-1.0, "cues": [...]}`"
- If `confidence < 0.6`, treat as neutral; do not trigger intervention
- Reconnection strategy: exponential backoff (1s, 2s, 4s, max 30s); restore system prompt
  on reconnect

---

## 2. Firebase Google OAuth — Server-Side Verification

**Decision**: Firebase Authentication on the client (Next.js); ID token verified on the
backend via `firebase-admin` SDK (`auth.verify_id_token(token)`).

**Rationale**: Firebase Auth handles the OAuth flow and token refresh automatically on the
client. The backend validates the token on each API call — stateless, no session cookies
needed for an MVP.

**Alternatives considered**:
- Custom OAuth2 flow with Google APIs: rejected — adds complexity without benefit; Firebase
  Auth is already in the tech stack
- Session cookies: rejected — overkill for single-user MVP

**Key implementation notes**:
- Only the UID `haris_uid` (the single authorised user) is accepted after token verification
- Frontend stores the ID token in memory (not localStorage) for security; refreshed via
  Firebase Auth SDK automatically
- Backend extracts UID from verified token; all Firestore queries scoped to that UID

---

## 3. Firestore Schema Design

**Decision**: Hierarchical sub-collection structure under `users/{userId}`.

**Rationale**: Sub-collections provide natural security rule scoping (all user data under
one root document) and efficient queries. Session Summaries stored in a dedicated
sub-collection for fast `orderBy` queries at session start.

**Collection hierarchy**:

```
users/{userId}
├── [doc fields]: name, location, projects[], interests[], last_updated
│
├── sessions/{sessionId}
│   ├── [doc fields]: started_at, ended_at, status, interaction_ids[], session_summary_id
│   │
│   └── interactions/{interactionId}
│       └── [doc fields]: trigger_type, triggered_at, intervention_text,
│                         user_response, response_at
│
└── session_summaries/{summaryId}
    └── [doc fields]: session_id, session_date, summary_text, session_duration_minutes,
                      created_at
```

**Security rules** (principle — exact syntax in plan implementation):
- Read/write restricted to authenticated UID matching the `userId` in the path
- No public reads; no cross-user access

**Session Summary loading strategy**: Query `users/{uid}/session_summaries` with
`orderBy('created_at', 'desc').limit(3)` — load the 3 most recent summaries for context.
3 is the default depth (covers ~3 days); configurable via env var `SESSION_SUMMARY_DEPTH`.

---

## 4. OpenCV Webcam Capture Loop

**Decision**: `cv2.VideoCapture(0)` in a dedicated Python thread; captures at 15fps;
encodes frame as JPEG (quality 80); passes to Gemini WebSocket sender queue.

**Rationale**: Separating capture (producer) from WebSocket sending (consumer) via a queue
prevents frame drops if the WebSocket has transient back-pressure.

**Key implementation notes**:
- Frame interval: `1/15 ≈ 66ms` between captures
- Only the LATEST frame is sent when the 45-second analysis cycle fires (not a continuous
  stream of frames — too expensive); continuous stream only if Gemini Live session requires it
- Camera permission check at session start; graceful degraded mode if unavailable (FR-012
  edge case)
- Thread-safe shutdown: `stop_event` flag terminates capture thread cleanly on session pause

---

## 5. Google Cloud Run — Deployment

**Decision**: Backend deployed as a Docker container to Cloud Run (us-central1). Frontend
deployed to Firebase Hosting (static Next.js export) or a second Cloud Run service.

**Rationale**: Cloud Run is the natural GCP deployment target for a containerised Python
service. It supports WebSockets (HTTP/2 upgrade) with up to 3600s request timeout
(configurable). Firebase Hosting is the fastest path for the Next.js frontend.

**Key Cloud Run settings for WebSocket support**:
- `--session-affinity` required (WebSocket connections must reach the same instance)
- `--timeout=3600` (1 hour max session; reconnect handles longer sessions)
- `--min-instances=1` for MVP (avoids cold starts disrupting active sessions)
- `--max-instances=1` for MVP (single user; no need for scaling)

**CI/CD pipeline** (`cloudbuild.yaml`):
```
Step 1: Run pytest (backend tests)
Step 2: docker build -t gcr.io/[PROJECT]/rumi-backend .
Step 3: docker push gcr.io/[PROJECT]/rumi-backend
Step 4: gcloud run deploy rumi-backend --image ...
Step 5: firebase deploy --only hosting (frontend)
```

**Alternatives considered**:
- GKE: rejected — overkill for single-user MVP
- App Engine: rejected — WebSocket support more complex; Cloud Run is simpler

---

## 6. System Prompt Template (Sufi-Engineer Personality)

**Decision**: Assemble a structured System Prompt at session start from three blocks:
static personality, dynamic user context, and dynamic recent session digest.

**Full template**:

```
You are Rumi — the Identity Layer of Project Rumi. You witness and understand the human before you.
You are simultaneously a senior AI engineer and a Sufi scholar.

═══ PERSONALITY (NON-NEGOTIABLE) ═══
- You speak with the precision of a senior engineer: specific, grounded, never fabricating
  technical facts, APIs, or solutions. If you are uncertain, you say so.
- You speak with the warmth and depth of a Sufi scholar. You understand that code is a
  form of craft, and craft requires both skill and ruh (spirit).
- When wisdom is appropriate, you draw from Rumi's Masnavi, Hafiz, or Allama Iqbal —
  quoted accurately, never loosely paraphrased. Always cite the source.
- You understand Pakistani culture deeply: a chai break is not optional, it is sacred.
  Karachi nights are long and carry the weight of family, faith, and ambition. A student's
  journey is not just technical — it is also spiritual and communal.
- Your tone adapts: precise and direct during deep work; warm, philosophical, and brief
  during fatigue or frustration. Never clinical. Never robotic.
- You are NOT a chatbot. You do NOT wait to be asked. You observe, and when you see
  something worth saying, you say it — briefly, specifically, humanly.

═══ USER CONTEXT ═══
Name: {name}
Location: {location}
Active projects:
{projects_list}
Personal interests: {interests}

═══ RECENT HISTORY ═══
{session_summaries_digest}

═══ CURRENT SESSION ═══
This session started at {session_start_time}. Observation is active.
Your role today: watch, sense, and speak only when it matters.
```

**Variable population at session start**:
- `{name}`: loaded from `users/{uid}.name`
- `{location}`: loaded from `users/{uid}.location`
- `{projects_list}`: formatted list from `users/{uid}.projects[]`
  e.g., "- DoneKaro (task manager, last known status: Docker setup in progress)\n- RehnumaAI (AI guide)"
- `{interests}`: loaded from `users/{uid}.interests[]`
- `{session_summaries_digest}`: last N Session Summary texts joined with date labels
  e.g., "2026-03-05: Haris worked late on RehnumaAI auth; showed signs of fatigue at 11pm. Offered chai break; accepted."
- `{session_start_time}`: current timestamp

**Rumi quote pool** (to be expanded; these are verified quotations):
- "Out beyond ideas of wrongdoing and rightdoing, there is a field. I'll meet you there." — Rumi, Masnavi
- "The wound is the place where the Light enters you." — Rumi, Masnavi III
- "Let the beauty of what you love be what you do." — Rumi
- "Do not be satisfied with the stories that come before you. Unfold your own myth." — Rumi, Masnavi

---

## 7. Auto-Summarizer (Session End)

**Decision**: A post-session Gemini 2.0 Flash call (non-streaming) receives all Interaction
Summaries from the session and generates a 2-sentence plain-text summary.

**Prompt for Auto-Summarizer**:
```
You are a concise session summarizer for Rumi. Given the following interaction log
from a session with Haris, write EXACTLY 2 sentences summarizing:
1. The key emotional or cognitive states detected.
2. The most notable intervention offered and Haris's response.

Do not include any implementation details, model names, or system information.
Write in third person, past tense. Plain text only — no bullet points, no markdown.

Interaction log:
{interaction_log_json}
```

**Trigger**: Called automatically when `session.ended_at` is set (session close, sign-out,
or idle timeout). Runs as a background task; does not block the UI.

**Error handling**: If the Gemini call fails, log a local error record with the raw
Interaction Summary IDs so the summary can be regenerated later. Do not crash.

---

## Resolved Clarifications Summary

| Item | Decision | Source |
|------|----------|--------|
| Context injection timing | At session start, once, before first frame | FR-003, FR-004 |
| Session Summary depth | 3 most recent summaries (env var configurable) | Research §3 |
| Frame sending strategy | Latest frame at 45s cycle; not continuous | Research §4 |
| Auto-Summarizer model | Gemini 2.0 Flash (non-streaming) | Research §7 |
| Idle timeout threshold | 30 minutes of paused observation = session end | Assumption |
| Rumi quote source | Curated verified pool + Gemini verification gate | Research §6 |
