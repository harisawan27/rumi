/** A deliberately closed, network-free rehearsal model. Never dispatches OS actions. */
export type PreviewKind = "browser" | "files" | "theme" | "shutdown" | "creative" | "clarification" | "failure";
export type PreviewTask = { title: string; kind: PreviewKind; steps: string[]; detail: string };
export type PreviewRun = { id: number; task: PreviewTask; step: number; state: "running" | "completed" | "cancelled" | "waiting" };
export type PreviewEvent = { type: "start"; id: number; task: PreviewTask } | { type: "advance"; id: number } | { type: "stop" } | { type: "dismiss" };

export function previewTask(input: string): PreviewTask {
  const text = input.trim().toLowerCase().replace(/[.!?]+$/, "");
  if (/^(?:open chrome(?: and (?:open )?gmail)?|open gmail)$/.test(text)) return {
    kind: "browser", title: text.includes("gmail") ? "Open Chrome & Gmail" : "Open Chrome", steps: ["Find the browser", text.includes("gmail") ? "Open the destination" : "Open the window", "Check the result"],
    detail: "Browser workflow rehearsed. No browser was opened and no account was accessed.",
  };
  if (/^(?:organize|preview) (?:my |sample )?files$/.test(text)) return {
    kind: "files", title: "Give your files a little order", steps: ["Inspect sample files", "Group by file type", "Preview the arrangement"],
    detail: "Sample arrangement ready. Your real files have not been read or moved.",
  };
  if (/^(?:(?:switch|change)(?: rumi)? to (?:dark|light) mode|(?:dark|light) mode)$/.test(text)) return {
    kind: "theme", title: text.includes("light") ? "Switch Rumi to light mode" : "Switch Rumi to dark mode", steps: [],
    detail: "Only this Rumi preview changes appearance. Windows settings stay unchanged.",
  };
  if (/^(?:shut down|shutdown)(?: (?:my |the )?(?:laptop|computer))?$/.test(text)) return {
    kind: "shutdown", title: "Shut down your computer", steps: [],
    detail: "This is a confirmation preview. Shutdown is unavailable here; your computer will stay on.",
  };
  if (/^(?:write|draft|create) (?:a )?(?:welcome note|welcome message)$/.test(text)) return {
    kind: "creative", title: "A warmer welcome", steps: [],
    detail: "A prewritten sample, ready for your edits. No AI request was made.",
  };
  if (/^open (?:missing app|unavailable app)$/.test(text)) return {
    kind: "failure", title: "An app we couldn’t find", steps: [],
    detail: "Example failure: the selected app is unavailable. A real task would pause here and ask you to choose another app.",
  };
  return { kind: "clarification", title: "Let’s make that a little clearer", steps: [],
    detail: "This preview understands the example commands below. Try “open Chrome and Gmail”, “organize sample files”, or “write a welcome note”. Nothing was sent to AI." };
}

export function previewReducer(state: PreviewRun | null, event: PreviewEvent): PreviewRun | null {
  if (event.type === "dismiss") return state?.state === "running" ? state : null;
  if (event.type === "start") {
    if (state?.state === "running") return state; // A second request is never silently queued.
    return { id: event.id, task: event.task, step: 0, state: event.task.steps.length ? "running" : "waiting" };
  }
  if (!state) return state;
  if (event.type === "stop") return state.state === "running" ? { ...state, state: "cancelled" } : state;
  if (event.id !== state.id || state.state !== "running") return state;
  const step = state.step + 1;
  return { ...state, step, state: step >= state.task.steps.length ? "completed" : "running" };
}

export const WELCOME_SAMPLE = "Welcome to a little more breathing room.\n\nRumi helps you move from an idea to a finished task, one clear step at a time. Start small: open your workspace, put a few files in order, or make something your own.\n\nYou set the direction. Rumi helps with the next step.";
