import { GeneratedArtifact, parseArtifactResult, StudyStateEdit, StudySpecEdit } from "../types/artifacts";

export type ArtifactTransport = (path: string, body: unknown, signal: AbortSignal) => Promise<unknown>;
export class ArtifactAccessDenied extends Error {}
export interface ArtifactView { artifact: GeneratedArtifact | null; busy: boolean; error: string }
/** Only selected identity survives a privacy lock. No payload goes to storage/history. */
export class ArtifactClient {
  private view: ArtifactView = { artifact: null, busy: false, error: "" };
  private listeners = new Set<() => void>();
  private epoch = 0;
  private controller: AbortController | null = null;
  private refreshing = false;
  private lease: ReturnType<typeof setTimeout> | null = null;
  private poll: ReturnType<typeof setInterval> | null = null;
  private session: string | null = null;
  private allowed = false;
  private selectedId: string | null = null;
  constructor(private transport: ArtifactTransport) {}
  snapshot = () => this.view;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private publish(view: ArtifactView) { this.view = view; this.listeners.forEach(fn => fn()); }
  private clear() {
    this.epoch++; this.controller?.abort(); this.controller = null;
    this.refreshing = false;
    if (this.lease) clearTimeout(this.lease);
    this.lease = null;
    this.publish({ artifact: null, busy: false, error: "" });
  }
  configure(session: string | null, allowed: boolean) {
    if (session !== this.session) { this.clear(); this.selectedId = null; this.session = session; }
    if (!allowed || !session) { this.revoke(); return; }
    const returning = !this.allowed;
    this.allowed = true;
    if (!this.poll) this.poll = setInterval(() => {
      if (this.allowed && this.selectedId && !this.controller) {
        void (this.view.artifact ? this.request("access") : this.reload()).catch(() => {});
      }
    }, 2000);
    if (returning && this.selectedId) void this.reload().catch(() => {});
  }
  revoke = () => {
    this.allowed = false;
    if (this.poll) clearInterval(this.poll);
    this.poll = null; this.clear();
  };
  dismiss = () => { this.clear(); this.selectedId = null; };
  dispose = () => { this.revoke(); this.listeners.clear(); };
  reload = async () => {
    this.cancelRefresh();
    if (this.selectedId) await this.request(this.selectedId);
  };
  load = async (id: string) => {
    this.clear(); this.selectedId = id;
    await this.request(id);
  };
  loadIfCurrent = async (id: string, current: () => boolean) => {
    if (!current()) return;
    this.clear(); this.selectedId = id;
    await this.request(id, undefined, false, current);
  };
  proof = async (graph = false) => {
    this.clear(); this.selectedId = null;
    await this.request(`proof&graph=${graph}`, {}, true);
  };
  edit = async (edit: StudyStateEdit) => {
    this.cancelRefresh();
    const artifact = this.view.artifact;
    if (!artifact || artifact.artifact_id !== this.selectedId || this.controller) throw new Error("Reload the tracker before editing.");
    await this.request("state", { artifact_id: artifact.artifact_id, expected_state_revision: artifact.state_revision, edit });
  };
  setGraph = async (enabled: boolean) => {
    await this.editSpec({ operation: "set_daily_graph_visibility", enabled });
  };
  editSpec = async (edit: StudySpecEdit) => {
    this.cancelRefresh();
    const artifact = this.view.artifact;
    if (!artifact) throw new Error("Reload the tracker before editing.");
    await this.request("spec", { mode: "generated_ui", renderer: "study_tracker_v1", operation: "edit",
      artifact_id: artifact.artifact_id, expected_revision: artifact.revision,
      edit });
  };
  private cancelRefresh() {
    if (this.refreshing) {
      this.epoch++; this.controller?.abort(); this.controller = null; this.refreshing = false;
    }
  }
  private async request(target: string, body?: unknown, proof = false, current?: () => boolean) {
    if (!this.allowed || !this.session) throw new Error("Owner verification is required.");
    if (this.controller) throw new Error("An update is already pending.");
    const epoch = this.epoch;
    const selected = this.selectedId;
    const requestId = crypto.randomUUID();
    const controller = new AbortController(); this.controller = controller;
    const accessOnly = target === "access";
    this.refreshing = accessOnly;
    const started = Date.now();
    if (!accessOnly) this.publish({ ...this.view, busy: true, error: "" });
    try {
      const route = proof ? `proof?graph=${target.endsWith("true")}` : `${encodeURIComponent(target)}?`;
      const path = `${route}${proof ? "&" : ""}session_id=${encodeURIComponent(this.session)}&request_id=${requestId}`;
      const payload = body === undefined ? undefined : target === "state" ? { ...(body as object), request_id: requestId } : body;
      const raw = await this.transport(path, payload, controller.signal) as { result?: unknown; lease_seconds?: unknown; request_id?: unknown };
      if (epoch !== this.epoch || !this.allowed || this.selectedId !== selected) return;
      if (current && !current()) { this.dismiss(); return; }
      const result = accessOnly ? null : parseArtifactResult(raw?.result);
      const seconds = raw?.lease_seconds;
      if ((accessOnly ? raw.request_id !== requestId : !result || result.request_id !== requestId || (!proof && result.artifact_id !== selected))
        || typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0 || seconds > 5) throw new Error("Invalid artifact response.");
      const previous = this.view.artifact;
      if (previous && result && (result.revision < previous.revision || result.state_revision < previous.state_revision)) throw new Error("Stale artifact response.");
      const remaining = started + seconds * 1000 - Date.now();
      if (remaining <= 0) throw new Error("Owner verification expired. Reload the tracker.");
      if (result) this.selectedId = result.artifact_id;
      if (this.lease) clearTimeout(this.lease);
      this.lease = setTimeout(() => this.clear(), remaining);
      if (!accessOnly && result) this.publish({ artifact: result.artifact, busy: false, error: "" });
    } catch (e) {
      if (epoch !== this.epoch) return;
      if (e instanceof ArtifactAccessDenied) this.revoke(); else this.clear();
      const message = e instanceof Error ? e.message : "Artifact unavailable.";
      this.publish({ artifact: null, busy: false, error: message });
      throw e;
    } finally { if (this.controller === controller) { this.controller = null; this.refreshing = false; } }
  }
}
