/** Closed data vocabulary. Presentation is owned by Rumi, never by payloads. */
export const COLOR_TOKENS = ["red", "blue", "green", "gold", "purple", "teal", "orange"] as const;
export type ColorToken = typeof COLOR_TOKENS[number];
export interface StudySubject { id: string; label: string; color_token: ColorToken }
export interface StudyEntry { id: string; subject_id: string; date: string; minutes: number }
export interface StudyTrackerSpec { week_start: string; subjects: StudySubject[]; show_daily_graph: boolean }
export interface StudyTrackerState { entries: StudyEntry[] }
export interface StudyTrackerV1 {
  artifact_id: string; kind: "generated_ui"; renderer: "study_tracker_v1"; schema_version: 1;
  revision: number; state_revision: number; title: string; spec: StudyTrackerSpec; state: StudyTrackerState;
  created_at: string; updated_at: string; source_session_id: string; validation_version: string; generation_version: string;
}
export type GeneratedArtifact = StudyTrackerV1;
export interface ArtifactResult {
  type: "artifact_result" | "artifact_update"; request_id: string; artifact_id: string;
  revision: number; state_revision: number; renderer: "study_tracker_v1"; artifact: GeneratedArtifact;
}
export type StudyStateEdit = { operation: "add_entry"; entry: StudyEntry } | { operation: "remove_entry"; entry_id: string };
export type StudySpecEdit = { operation: "set_subject_color"; subject_id: string; color_token: ColorToken }
  | { operation: "set_daily_graph_visibility"; enabled: boolean };
export interface StudyEditDecision {
  mode: "generated_ui"; renderer: "study_tracker_v1"; operation: "edit";
  artifact_id: string; expected_revision: number; edit: StudySpecEdit;
}

type Obj = Record<string, unknown>;
const object = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const keys = (v: Obj, required: string[], optional: string[] = []) =>
  required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => [...required, ...optional].includes(k));
const text = (v: unknown, max: number): v is string => typeof v === "string" && v.trim().length > 0 && Array.from(v.trim()).length <= max;
export const isArtifactId = (v: unknown): v is string => typeof v === "string" && v.length === 36 && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(v);
const stable = (v: unknown): v is string => typeof v === "string" && v.trim() === v && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(v);
const version = (v: unknown) => typeof v === "string" && v.trim() === v && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$/.test(v);
const revision = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const color = (v: unknown): v is ColorToken => COLOR_TOKENS.includes(v as ColorToken);
export function isISODate(v: unknown): v is string {
  if (typeof v !== "string" || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(v) || v.startsWith("0000")) return false;
  const d = new Date(`${v}T00:00:00Z`);
  return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === v;
}
const timestamp = (v: unknown): v is string => typeof v === "string"
  && /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$/.test(v)
  && isISODate(v.slice(0, 10)) && +v.slice(11, 13) < 24 && +v.slice(14, 16) < 60 && +v.slice(17, 19) < 60 && Number.isFinite(Date.parse(v));
export function weekDates(start: string): string[] {
  if (!isISODate(start)) return [];
  return Array.from({ length: 7 }, (_, day) => new Date(Date.parse(`${start}T00:00:00Z`) + day * 86400000).toISOString().slice(0, 10));
}
export function isStudyEntry(v: unknown): v is StudyEntry {
  return object(v) && keys(v, ["id", "subject_id", "date", "minutes"]) && stable(v.id) && stable(v.subject_id)
    && isISODate(v.date) && revision(v.minutes) && v.minutes > 0 && v.minutes <= 1440;
}
export function parseGeneratedArtifact(v: unknown): GeneratedArtifact | null {
  if (!object(v) || !keys(v, ["artifact_id", "kind", "renderer", "schema_version", "revision", "state_revision", "title", "spec", "created_at", "updated_at", "source_session_id", "validation_version", "generation_version"], ["state"])) return null;
  if (!isArtifactId(v.artifact_id) || v.kind !== "generated_ui" || v.renderer !== "study_tracker_v1" || v.schema_version !== 1
    || !revision(v.revision) || !revision(v.state_revision) || !text(v.title, 120) || !stable(v.source_session_id)
    || !version(v.validation_version) || !version(v.generation_version) || !timestamp(v.created_at) || !timestamp(v.updated_at)
    || Date.parse(v.updated_at) < Date.parse(v.created_at)) return null;
  const spec = v.spec;
  const state = v.state === undefined ? {} : v.state;
  if (!object(spec) || !keys(spec, ["week_start", "subjects"], ["show_daily_graph"]) || !isISODate(spec.week_start)
    || spec.week_start > "9999-12-25" || (spec.show_daily_graph !== undefined && typeof spec.show_daily_graph !== "boolean")
    || !Array.isArray(spec.subjects) || spec.subjects.length < 1 || spec.subjects.length > 20) return null;
  const subjects: StudySubject[] = [];
  for (const s of spec.subjects) {
    if (!object(s) || !keys(s, ["id", "label", "color_token"]) || !stable(s.id) || !text(s.label, 80) || !color(s.color_token) || subjects.some(x => x.id === s.id)) return null;
    subjects.push({ id: s.id, label: s.label.trim(), color_token: s.color_token });
  }
  if (!object(state) || !keys(state, [], ["entries"])) return null;
  const entries = state.entries === undefined ? [] : state.entries;
  if (!Array.isArray(entries) || entries.length > 200 || !entries.every(isStudyEntry)) return null;
  const dates = weekDates(spec.week_start);
  const ids = new Set<string>();
  const totals: Record<string, number> = {};
  for (const e of entries) {
    if (ids.has(e.id) || !subjects.some(s => s.id === e.subject_id) || !dates.includes(e.date)) return null;
    ids.add(e.id);
    totals[e.date] = (totals[e.date] ?? 0) + e.minutes;
    if (totals[e.date] > 1440) return null;
  }
  return { ...v, title: v.title.trim(), spec: { week_start: spec.week_start, subjects, show_daily_graph: spec.show_daily_graph ?? false }, state: { entries: entries.map(e => ({ ...e })) } } as GeneratedArtifact;
}
export function parseArtifactResult(v: unknown): ArtifactResult | null {
  if (!object(v) || !keys(v, ["type", "request_id", "artifact_id", "revision", "state_revision", "renderer", "artifact"]) || !isArtifactId(v.request_id)
    || !["artifact_result", "artifact_update"].includes(v.type as string)) return null;
  const artifact = parseGeneratedArtifact(v.artifact);
  if (!artifact || v.artifact_id !== artifact.artifact_id || v.revision !== artifact.revision || v.state_revision !== artifact.state_revision || v.renderer !== artifact.renderer) return null;
  return { ...v, artifact } as ArtifactResult;
}
export function isStudyEditDecision(v: unknown): v is StudyEditDecision {
  if (!object(v) || !keys(v, ["mode", "renderer", "operation", "artifact_id", "expected_revision", "edit"])
    || v.mode !== "generated_ui" || v.renderer !== "study_tracker_v1" || v.operation !== "edit" || !isArtifactId(v.artifact_id) || !revision(v.expected_revision) || !object(v.edit)) return false;
  const e = v.edit;
  return e.operation === "set_subject_color" ? keys(e, ["operation", "subject_id", "color_token"]) && stable(e.subject_id) && color(e.color_token)
    : e.operation === "set_daily_graph_visibility" && keys(e, ["operation", "enabled"]) && typeof e.enabled === "boolean";
}
