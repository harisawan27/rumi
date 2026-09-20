import { auth } from "./firebase";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Always returns a fresh token — forces refresh if close to expiry. */
async function getFreshToken(): Promise<string> {
  const user = auth.currentUser;
  if (user) {
    const token = await user.getIdToken(/* forceRefresh */ false);
    sessionStorage.setItem("id_token", token);
    return token;
  }
  // Fallback to cached token
  const cached = sessionStorage.getItem("id_token");
  if (cached) return cached;
  throw new Error("No auth token — please sign in again");
}

function getToken(): string {
  const token = sessionStorage.getItem("id_token");
  if (!token) throw new Error("No auth token — please sign in again");
  return token;
}

async function authHeaders(): Promise<HeadersInit> {
  const token = await getFreshToken();
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function verifyAuth(): Promise<{ uid: string; name: string }> {
  const token = await getFreshToken();
  const res = await fetch(`${BACKEND_URL}/auth/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: token }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Auth verification failed");
  }
  return res.json();
}

export async function getIdentity(): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${BACKEND_URL}/identity`, { headers: await authHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Failed to load identity");
  }
  return res.json();
}

export async function saveIdentity(data: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/identity`, {
    method: "PUT",
    headers: await authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to save identity");
  }
}

export async function getSessionSummaries(limit = 3): Promise<unknown[]> {
  const res = await fetch(`${BACKEND_URL}/session-summaries?limit=${limit}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.summaries ?? [];
}

// ---------------------------------------------------------------------------
// WebSocket observe (T038)
// ---------------------------------------------------------------------------

export interface InterventionMessage {
  type: "intervention";
  trigger: "A" | "B" | "C" | "E" | "G";
  text: string;
  interaction_id: string;
  options: string[];
}

export interface CanvasHistoryItem {
  kind?: "generated_ui";
  artifact_id?: string;
  query?: string;
  title: string;
  content?: string;
  content_type?: string;
  timestamp: string;
}

export async function getCanvasHistory(): Promise<CanvasHistoryItem[]> {
  const headers = await authHeaders();
  const res = await fetch(`${BACKEND_URL}/canvas/history`, { headers });
  if (!res.ok) return [];
  const data = await res.json();
  return data.items ?? [];
}

export type WsMessage =
  | InterventionMessage
  | { type: "state"; state: string; confidence: number }
  | { type: "ping" }
  | { type: "paused" }
  | { type: "request_frame" }
  | { type: "audio_response"; data: string; generation_id?: number }
  | { type: "transcript"; text: string }
  | { type: "audio_interrupt"; generation_id?: number }
  | { type: "canvas_history"; items: CanvasHistoryItem[] }
  | { type: "text_response"; title: string; content: string; content_type?: string; append?: boolean }
  | { type: "detection_update"; state: string; confidence: number; cues?: string[]; landmarks?: Record<string, number>; face_detected?: boolean; detector_status?: string }
  | { type: "memory_updated"; fields: string[]; message: string }
  | { type: "guest_detected"; name?: string; photo_url?: string; confidence?: number }
  | { type: "owner_returned" }
  | { type: "identity_verified" }
  | { type: "known_person_detected"; name: string; relationship: string }
  | { type: "profile_updated"; field: string }
  | { type: "known_person_added"; name: string }
  | { type: "away_mode" }
  | { type: "presence_returned" }
  | { type: "error"; code: string; message?: string };

export async function connectObserveSocket(
  sessionId: string,
  onMessage: (msg: WsMessage) => void,
): Promise<WebSocket> {
  const token = await getFreshToken();
  const wsBase = BACKEND_URL.replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/ws/observe?session_id=${sessionId}&token=${token}`);

  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data);
      if (msg.type === "ping") {
        ws.send(JSON.stringify({ type: "pong" }));
        return;
      }
      onMessage(msg);
    } catch {
      // ignore malformed messages
    }
  };

  return ws;
}

export function sendInterventionResponse(
  ws: WebSocket,
  interactionId: string,
  response: "accepted" | "dismissed",
): void {
  ws.send(JSON.stringify({ type: "intervention_response", interaction_id: interactionId, response }));
}

export async function refreshSessionContext(): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/session/refresh-context`, {
    method: "POST",
    headers: await authHeaders(),
  });
  // Silently ignore errors — no active session is fine (user may have ended it)
  if (!res.ok && res.status !== 404) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to refresh session context");
  }
}

export async function startSession(): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/session/start`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error("Failed to start session");
  const data = await res.json();
  return data.session_id;
}

export async function endSession(sessionId: string): Promise<void> {
  await fetch(`${BACKEND_URL}/session/${sessionId}/end`, {
    method: "POST",
    headers: await authHeaders(),
  });
}

// ---------------------------------------------------------------------------
// Known People
// ---------------------------------------------------------------------------

export interface KnownPerson {
  id:                string;
  name:              string;
  relationship:      string;
  photo_url:         string;
  added_by:          "manual" | "rumi_introduction";
  status:            "verified" | "draft";
  notes:             string;
  added_at:          string;
  last_seen:         string | null;
  interaction_count: number;
}

export async function getKnownPeople(): Promise<KnownPerson[]> {
  const res = await fetch(`${BACKEND_URL}/known-people`, { headers: await authHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.people ?? [];
}

export async function addKnownPerson(
  person: { name: string; relationship: string; photo_url: string; notes?: string }
): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/known-people`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ ...person, added_by: "manual" }),
  });
  if (!res.ok) throw new Error("Failed to add person");
  const data = await res.json();
  return data.id;
}

export async function updateKnownPerson(
  personId: string,
  updates: Partial<{ name: string; relationship: string; photo_url: string; notes: string }>
): Promise<void> {
  await fetch(`${BACKEND_URL}/known-people/${personId}`, {
    method: "PUT",
    headers: await authHeaders(),
    body: JSON.stringify(updates),
  });
}

export async function deleteKnownPerson(personId: string): Promise<void> {
  await fetch(`${BACKEND_URL}/known-people/${personId}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
}

// ---------------------------------------------------------------------------
// Photo upload — Firebase Storage direct (bypasses backend for binary data)
// ---------------------------------------------------------------------------

export async function uploadPersonPhoto(
  uid: string,
  file: File,
  personId: string,
): Promise<string> {
  const { storage } = await import("./firebase");
  const { ref, uploadBytes, getDownloadURL } = await import("firebase/storage");
  const path = `known-people/${uid}/${personId}_${Date.now()}.jpg`;
  const storageRef = ref(storage, path);
  await uploadBytes(storageRef, file, { contentType: file.type });
  return getDownloadURL(storageRef);
}

export async function uploadProfilePhoto(uid: string, file: File): Promise<string> {
  const { storage } = await import("./firebase");
  const { ref, uploadBytes, getDownloadURL } = await import("firebase/storage");
  const path = `profile-photos/${uid}/profile_${Date.now()}.jpg`;
  const storageRef = ref(storage, path);
  await uploadBytes(storageRef, file, { contentType: file.type });
  return getDownloadURL(storageRef);
}

// ---------------------------------------------------------------------------
// Memory Candidates (Phase 5)
// ---------------------------------------------------------------------------

export interface MemoryCandidate {
  id: string;
  field: string;
  suggested_value: unknown;
  source_session_id: string;
  confidence: number;
  status: "inferred" | "confirmed" | "rejected";
  created_at: string;
}

export async function getMemoryCandidates(): Promise<MemoryCandidate[]> {
  const res = await fetch(`${BACKEND_URL}/memory/candidates`, { headers: await authHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.candidates ?? [];
}

export async function confirmMemoryCandidate(candidateId: string): Promise<{ status: string; field: string }> {
  const res = await fetch(`${BACKEND_URL}/memory/candidates/${candidateId}/confirm`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to confirm memory candidate");
  }
  return res.json();
}

export async function rejectMemoryCandidate(candidateId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/memory/candidates/${candidateId}/reject`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to reject memory candidate");
  }
}

export async function dismissMemoryCandidate(candidateId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/memory/candidates/${candidateId}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to dismiss memory candidate");
  }
}

// ---------------------------------------------------------------------------
// Conversation History (Phase 4 & Data Controls)
// ---------------------------------------------------------------------------

export interface HistoryTurnEvent {
  type: "turn";
  user_text: string;
  rumi_response: string;
  source: string;
  timestamp: string;
}

export interface HistoryInterventionEvent {
  type: "intervention";
  trigger: "A" | "B" | "C" | "E" | "G";
  text: string;
  user_response: string;
  timestamp: string;
}

export type TimelineEvent = HistoryTurnEvent | HistoryInterventionEvent;

export interface SessionHistoryGroup {
  session_id: string;
  started_at: string;
  status: string;
  events: TimelineEvent[];
}

export async function getConversationHistory(limit = 15): Promise<SessionHistoryGroup[]> {
  const res = await fetch(`${BACKEND_URL}/conversation/history?limit=${limit}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.sessions ?? [];
}

export async function clearConversationHistory(): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/conversation/history`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to clear conversation history");
  }
}

export async function clearCanvasHistory(): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/canvas/history`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Failed to clear canvas history");
  }
}

// ---------------------------------------------------------------------------
// Privacy-Safe Minimal Local Telemetry (Phase 17)
// Strictly NO conversation text, transcript, audio, images, or embeddings.
// ---------------------------------------------------------------------------

export type UxEventType =
  | "SESSION_START"
  | "VOICE_TURN_START"
  | "VOICE_TURN_COMPLETE"
  | "CANVAS_OPENED"
  | "CANVAS_CLOSED"
  | "INTERVENTION_ACCEPTED"
  | "INTERVENTION_DISMISSED"
  | "CAMERA_TOGGLED"
  | "MIC_TOGGLED"
  | "RECONNECT_ATTEMPT"
  | "RECONNECT_SUCCESS";

export function logUxEvent(eventType: UxEventType): void {
  try {
    if (typeof window === "undefined") return;
    const MAX_EVENTS = 50;
    const raw = localStorage.getItem("rumi_ux_events");
    const list: Array<{ event: UxEventType; ts: number }> = raw ? JSON.parse(raw) : [];
    list.push({ event: eventType, ts: Date.now() });
    if (list.length > MAX_EVENTS) list.splice(0, list.length - MAX_EVENTS);
    localStorage.setItem("rumi_ux_events", JSON.stringify(list));
  } catch {
    // Non-critical telemetry — no failures
  }
}
