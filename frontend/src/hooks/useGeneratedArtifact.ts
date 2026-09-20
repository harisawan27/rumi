"use client";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { ArtifactAccessDenied, ArtifactClient } from "../services/artifactClient";
import { auth } from "../services/firebase";

export function useGeneratedArtifact(sessionId: string | null, allowed: boolean, authorizationSignal = 0) {
  const ref = useRef<ArtifactClient | null>(null);
  if (!ref.current) ref.current = new ArtifactClient(async (path, body, signal) => {
    const user = auth.currentUser;
    if (!user) throw new ArtifactAccessDenied("Please sign in again.");
    const token = await user.getIdToken();
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/generated-artifacts/${path}`, {
      method: body === undefined ? "GET" : "POST", signal, cache: "no-store",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 401 || response.status === 403) throw new ArtifactAccessDenied("Owner verification is required to reload this tracker.");
    if (!response.ok) throw new Error(response.status === 409 ? "This tracker changed. Reload before trying again." : "Artifact unavailable. Reload the tracker.");
    return response.json();
  });
  const client = ref.current;
  const view = useSyncExternalStore(client.subscribe, client.snapshot, client.snapshot);
  useEffect(() => { client.configure(sessionId, allowed); }, [client, sessionId, allowed, authorizationSignal]);
  useEffect(() => () => client.revoke(), [client]);
  return { ...view, client };
}
