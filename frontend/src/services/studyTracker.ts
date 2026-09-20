import { GeneratedArtifact, StudyEntry, parseGeneratedArtifact, weekDates } from "../types/artifacts";

export function calculateDailyTotals(artifact: GeneratedArtifact) {
  return weekDates(artifact.spec.week_start).map(date => ({ date, minutes: artifact.state.entries.filter(e => e.date === date).reduce((n, e) => n + e.minutes, 0) }));
}
export function calculateSubjectTotals(artifact: GeneratedArtifact) {
  return artifact.spec.subjects.map(s => ({ ...s, minutes: artifact.state.entries.filter(e => e.subject_id === s.id).reduce((n, e) => n + e.minutes, 0) }));
}
export function addStudyEntry(artifact: GeneratedArtifact, entry: StudyEntry): GeneratedArtifact {
  const next = parseGeneratedArtifact({ ...artifact, state: { entries: [...artifact.state.entries, entry] } });
  if (!next) throw new Error("Choose a subject, a date in this week, and whole minutes from 1 to 1440. Daily total cannot exceed 1440; maximum 200 entries.");
  return next;
}
export function removeStudyEntry(artifact: GeneratedArtifact, id: string): GeneratedArtifact {
  if (!artifact.state.entries.some(e => e.id === id)) throw new Error("Entry no longer exists. Reload the tracker.");
  return { ...artifact, state: { entries: artifact.state.entries.filter(e => e.id !== id) } };
}
