# API Contracts: Identity-Aware Proactive Loop

**Feature**: `001-proactive-loop`
**Date**: 2026-03-06
**Base URL**: `http://localhost:8000` (dev) · `https://rumi-backend-[hash]-uc.a.run.app` (prod)
**Auth**: All endpoints require `Authorization: Bearer <firebase_id_token>` except `/health`

---

## REST Endpoints

### GET /health

Health check — no auth required.

**Response** `200 OK`:
```json
{ "status": "ok", "version": "0.1.0" }
```

---

### POST /auth/verify

Verifies a Firebase ID token and returns the resolved user identity.

**Request body**:
```json
{ "id_token": "<firebase_id_token>" }
```

**Response** `200 OK`:
```json
{
  "uid": "uid_haris_001",
  "name": "Haris",
  "authenticated": true
}
```

**Errors**:
| Status | Code | Meaning |
|--------|------|---------|
| 401 | `INVALID_TOKEN` | Token is malformed or expired |
| 403 | `UNAUTHORISED_USER` | Token valid but UID is not the authorised user |

---

### GET /identity

Returns the Core Identity Profile for the authenticated user.

**Response** `200 OK`:
```json
{
  "user_id": "uid_haris_001",
  "name": "Haris",
  "location": "Karachi, Pakistan",
  "projects": [
    { "name": "DoneKaro", "status": "Docker setup in progress", "context": "Task manager app" },
    { "name": "RehnumaAI", "status": "Auth flow complete", "context": "AI guide for students" }
  ],
  "interests": ["Rumi", "Turkish culture", "software craftsmanship"],
  "last_updated": "2026-03-06T00:00:00Z"
}
```

**Errors**:
| Status | Code | Meaning |
|--------|------|---------|
| 404 | `IDENTITY_NOT_FOUND` | No user document exists in Firestore |
| 503 | `FIRESTORE_UNAVAILABLE` | Firestore connection failed |

---

### GET /session-summaries

Returns the most recent Session Summaries for context injection at session start.

**Query params**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | integer | 3 | Number of summaries to return (max 10) |

**Response** `200 OK`:
```json
{
  "summaries": [
    {
      "summary_id": "sum_20260305",
      "session_date": "2026-03-05",
      "summary_text": "Haris worked on RehnumaAI auth flow late into the evening, showing signs of fatigue around 11pm. A chai break was suggested and accepted; he returned refreshed and resolved the OAuth redirect issue.",
      "session_duration_minutes": 187,
      "created_at": "2026-03-05T23:44:00Z"
    }
  ],
  "count": 1
}
```

**Errors**:
| Status | Code | Meaning |
|--------|------|---------|
| 503 | `FIRESTORE_UNAVAILABLE` | Firestore connection failed |

---

### POST /session/start

Creates a new Observation Session and returns the session ID.

**Request body**: (empty — user identity derived from auth token)
```json
{}
```

**Response** `201 Created`:
```json
{
  "session_id": "sess_20260306_001",
  "started_at": "2026-03-06T09:00:00Z",
  "status": "active"
}
```

**Errors**:
| Status | Code | Meaning |
|--------|------|---------|
| 409 | `SESSION_ALREADY_ACTIVE` | An active session already exists for this user |
| 503 | `FIRESTORE_UNAVAILABLE` | Could not persist session |

---

### PUT /session/{session_id}/pause

Pauses the current Observation Session. Stops the Watchman loop.

**Response** `200 OK`:
```json
{
  "session_id": "sess_20260306_001",
  "status": "paused",
  "paused_at": "2026-03-06T10:30:00Z"
}
```

---

### PUT /session/{session_id}/resume

Resumes a paused session. Restarts the Watchman loop with prior context.

**Response** `200 OK`:
```json
{
  "session_id": "sess_20260306_001",
  "status": "active",
  "resumed_at": "2026-03-06T10:45:00Z"
}
```

---

### POST /session/{session_id}/end

Ends the session and triggers the Auto-Summarizer asynchronously.

**Response** `202 Accepted`:
```json
{
  "session_id": "sess_20260306_001",
  "status": "ended",
  "ended_at": "2026-03-06T18:00:00Z",
  "summary_status": "generating"
}
```

**Note**: `202 Accepted` because the Auto-Summarizer runs asynchronously. The client can
poll `GET /session/{session_id}` to check `session_summary_id` once it's populated.

---

### POST /interactions

Records a completed Interaction Summary after a trigger fires.

**Request body**:
```json
{
  "session_id": "sess_20260306_001",
  "trigger_type": "A",
  "triggered_at": "2026-03-06T11:15:00Z",
  "intervention_text": "يا Haris، 'The wound is the place where the Light enters you.' — Rumi. Chai break?",
  "user_response": "accepted",
  "response_at": "2026-03-06T11:15:30Z"
}
```

**Response** `201 Created`:
```json
{
  "interaction_id": "int_20260306_001",
  "session_id": "sess_20260306_001",
  "recorded_at": "2026-03-06T11:15:32Z"
}
```

**Validation**:
- `trigger_type` MUST be `"A"` or `"B"`
- `user_response` MUST be `"accepted"`, `"dismissed"`, or `"no_response"`
- `intervention_text` MUST NOT contain image data or raw sensor output

---

## WebSocket Contract

### WS /ws/observe

The main real-time channel for the Watchman observation loop. The backend manages
the Gemini Multimodal Live API connection internally; this WebSocket is between the
backend and the frontend (for receiving intervention events).

**Connection**: `ws://localhost:8000/ws/observe?session_id=<session_id>&token=<id_token>`

**Message flow**:

```
Client → Server: { "type": "frame", "data": "<base64_jpeg>" }   // 15fps from webcam
Server → Client: { "type": "state", "state": "focused|frustrated|neutral", "confidence": 0.85 }
Server → Client: { "type": "intervention", "trigger": "A", "text": "..." }  // when trigger fires
Server → Client: { "type": "ping" }  // keepalive every 30s
Client → Server: { "type": "pong" }  // keepalive response
```

**Intervention message schema**:
```json
{
  "type": "intervention",
  "trigger": "A",
  "text": "يا Haris، الجرح هو المكان الذي يدخل منه النور — Rumi. Chai break?",
  "interaction_id": "int_20260306_001",
  "options": ["accept", "dismiss"]
}
```

**Client acknowledgement** (after user responds):
```json
{
  "type": "intervention_response",
  "interaction_id": "int_20260306_001",
  "response": "accepted"
}
```

**Error messages**:
```json
{ "type": "error", "code": "GEMINI_DISCONNECTED", "retry_in_seconds": 2 }
{ "type": "error", "code": "CAMERA_UNAVAILABLE", "message": "Degraded mode: text-only" }
```

**Connection lifecycle**:
1. Client connects with valid `session_id` and `token`
2. Backend verifies token; loads System Prompt; starts Watchman loop
3. Client streams frames; backend forwards to Gemini Live API
4. Backend sends `state` updates every 45s; `intervention` on trigger
5. On `PUT /session/{id}/pause` → backend sends `{ "type": "paused" }` and halts loop
6. On disconnect: backend marks session as `paused`; reconnect resumes from last state
