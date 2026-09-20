import type { CanvasContent } from "../components/ArtifactCanvas";
import type { CanvasHistoryItem } from "./session";
import { isArtifactId } from "../types/artifacts";

export function canvasFromHistory(item: CanvasHistoryItem): CanvasContent {
  if (item.kind === "generated_ui") {
    // A reference is navigation metadata only; never hydrate state from history.
    return { kind: "generated_reference", artifact_id: isArtifactId(item.artifact_id) ? item.artifact_id : undefined,
      title: item.title, timestamp: item.timestamp, exchanges: [] };
  }
  return { title: item.title, timestamp: item.timestamp,
    exchanges: [{ query: item.query ?? "", response: item.content ?? "", timestamp: item.timestamp,
      type: item.content_type === "code" || item.content_type === "text" ? item.content_type : "markdown" }] };
}
