import { parseArtifactResult } from "../types/artifacts";

/** A socket response is only a notification; private content is loaded via the
 * existing authenticated, leased ArtifactClient before it can mount. */
export class CreateRequests {
  private id: string | null = null;
  private target: string | null = null;
  begin(target: string | null) { this.id = crypto.randomUUID(); this.target = target; return this.id; }
  cancel() { this.id = null; this.target = null; }
  current(id: string) { return this.id === id; }
  matchesTarget(id: string, target: string) { return this.current(id) && this.target === target; }
  result(raw: unknown) {
    const result = parseArtifactResult(raw);
    if (!result || !this.current(result.request_id) || (result.type === "artifact_update" && result.artifact_id !== this.target)) return null;
    return { request_id: result.request_id, artifact_id: result.artifact_id, type: result.type };
  }
}

export const CREATE_PROGRESS: Record<string, string> = {
  understanding: "Understanding request…", creating: "Creating tracker…", saving: "Saving…",
  updating: "Updating tracker…", writing: "Writing on Canvas…", ready: "Ready",
};
