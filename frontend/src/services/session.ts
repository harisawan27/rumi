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

export async function getIdentity(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BACKEND_URL}/identity`, { headers: await authHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Failed to load identity");
  }
  return res.json();
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
  trigger: "A" | "B";
  text: string;
  interaction_id: string;
  options: string[];
}

export type WsMessage =
  | InterventionMessage
  | { type: "state"; state: string; confidence: number }
  | { type: "ping" }
  | { type: "paused" }
  | { type: "request_frame" }
  | { type: "audio_response"; data: string }
  | { type: "transcript"; text: string }
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
