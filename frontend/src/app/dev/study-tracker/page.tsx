import { notFound } from "next/navigation";
import StudyTrackerPreview from "../../../components/artifacts/StudyTrackerPreview";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export default async function Page() {
  if (process.env.NODE_ENV !== "development" || process.env.NEXT_PUBLIC_ARTIFACT_PROOF_MODE !== "1") notFound();
  const fixture = JSON.parse(await readFile(join(process.cwd(), "../tests/fixtures/artifacts/valid_study_tracker.json"), "utf8"));
  return <StudyTrackerPreview fixture={fixture} />;
}
