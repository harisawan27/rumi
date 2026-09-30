/** Local console metadata only. Never accepts content, UID, artifact IDs or tokens. */
export type CreateStage = "planner_started" | "socket_result" | "authorized_load" | "canvas_interactive" | "load_failed" | "cancelled" | "acknowledgement_audio_scheduled";
const STAGES = new Set<CreateStage>(["planner_started", "socket_result", "authorized_load", "canvas_interactive", "load_failed", "cancelled", "acknowledgement_audio_scheduled"]);
export class CreateMetrics {
  private pending: { id: string; start: number; invoked: boolean; seen: Set<CreateStage> } | null = null;
  constructor(private write: (row: object) => void = row => console.info("rumi_create", JSON.stringify(row)), private now = () => performance.now()) {}
  begin(id: string) {
    this.cancel();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) return;
    this.pending = { id, start: this.now(), invoked: false, seen: new Set() };
  }
  mark(id: string, stage: CreateStage, duration?: number) {
    const pending = this.pending;
    if (!pending || pending.id !== id || !STAGES.has(stage) || pending.seen.has(stage)) return;
    pending.invoked = true; pending.seen.add(stage);
    this.write({ event: stage, request_id: id, elapsed_ms: Math.round(this.now() - pending.start),
      ...(typeof duration === "number" && Number.isFinite(duration) && duration >= 0 ? { duration_ms: Math.round(duration) } : {}) });
  }
  cancel() {
    if (this.pending?.invoked && !this.pending.seen.has("canvas_interactive") && !this.pending.seen.has("load_failed")) this.mark(this.pending.id, "cancelled");
    this.pending = null;
  }
}
