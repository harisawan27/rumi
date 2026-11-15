export type CompanionMood = "idle" | "greeting" | "waking" | "listening" | "speaking" | "thinking" | "reading" | "writing" | "searching" | "launching" | "confirming" | "success" | "acknowledging" | "confused" | "error" | "stopped" | "sleeping";

export const companionExpressions: { mood: CompanionMood; label: string; detail: string }[] = [
  { mood: "idle", label: "Here with you", detail: "Breathing, blinking and little moments of curiosity." },
  { mood: "greeting", label: "Hello, you", detail: "A wave and a smile when we connect." },
  { mood: "waking", label: "Waking up", detail: "Stretching into attention as local voice starts." },
  { mood: "listening", label: "All ears", detail: "Leaning closer, with a light that responds to your microphone level." },
  { mood: "speaking", label: "Something to say", detail: "An animated mouth and expressive hands while a spoken reply plays." },
  { mood: "thinking", label: "One moment", detail: "A thoughtful glance while a request is being handled." },
  { mood: "reading", label: "Reading your note", detail: "Eyes follow the lines of a little floating book." },
  { mood: "writing", label: "Making your note", detail: "A tiny pencil gets to work while the file action runs." },
  { mood: "searching", label: "Looking through files", detail: "Scanning the chosen folder, one local request at a time." },
  { mood: "launching", label: "Opening an app", detail: "Reaching toward a window as the launch is requested." },
  { mood: "confirming", label: "Your say", detail: "A raised eyebrow and open hands while awaiting your confirmation." },
  { mood: "success", label: "Done", detail: "A small celebration after a verified successful result." },
  { mood: "acknowledging", label: "Request sent", detail: "A nod for a dispatched launch; it does not claim the app was verified." },
  { mood: "confused", label: "Help me understand", detail: "A gentle head tilt when the request needs clarification." },
  { mood: "error", label: "Let's take a look", detail: "A concerned expression when something fails or is uncertain." },
  { mood: "stopped", label: "Taking a pause", detail: "Hands settle and the light softens when local access ends." },
  { mood: "sleeping", label: "Quiet company", detail: "A restful expression after a quiet idle moment." },
];

// Visual intent only. Execution always goes through the existing native parser.
export function actionExpression(text: string): CompanionMood {
  const command = text.trim().replace(/^(?:(?:hey\s+)?rumi[,!]?\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?/i, "");
  if (/^(?:list windows|inspect window)\b/i.test(command)) return "searching";
  if (/^focus window\b/i.test(command)) return "launching";
  if (/^(create|make|save|write)\b/i.test(command)) return "writing";
  if (/^(open|launch|start)\b/i.test(command)) return "launching";
  if (/^(list|show)(?:\s+me)?\s+(?:(?:the|my)\s+)?(?:text\s+)?files\b/i.test(command)) return "searching";
  if (/^(read|show)\b/i.test(command)) return "reading";
  return "thinking";
}

export function companionMood(input: { state: string; busy: boolean; action: CompanionMood; voiceBusy: boolean; speaking: boolean; listening: boolean; draft: boolean; cue?: CompanionMood; typing: boolean }): CompanionMood {
  if (["uncertain", "blocked", "disconnected", "stop-unconfirmed"].includes(input.state)) return "error";
  if (["stopped", "permission-ended"].includes(input.state)) return "stopped";
  if (input.voiceBusy) return "waking";
  if (input.busy) return input.state === "choosing" ? "thinking" : input.action;
  if (input.draft) return "confirming";
  if (input.speaking) return "speaking";
  if (input.state === "plan") return "confirming";
  if (input.cue) return input.cue;
  if (input.state === "failed" || input.state === "operator_uncertain") return "error";
  if (input.state === "clarification") return "confused";
  if (input.listening) return "listening";
  if (input.typing) return "thinking";
  return "idle";
}
