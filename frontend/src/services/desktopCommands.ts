export type DesktopNotice = {
  request_id: string; session_id: string; expires_at: number;
  state: "succeeded" | "dispatched" | "uncertain" | "failed" | "clarification";
  operation?: "list_files" | "read_text" | "create_text" | "open_app";
};
export type DesktopHandle = { submit: (text: string) => void; stop: () => void };

function commandText(text: string) {
  return text.trim().replace(/^(?:(?:hey\s+)?rumi[,!]?\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?/i, "").replace(/[.!?]+$/, "").trim();
}
export function isDesktopStop(text: string) {
  return /^(?:stop|cancel|stop (?:that|the task|computer actions)|cancel (?:that|the task))$/i.test(commandText(text));
}
export function isDesktopCommand(text: string) {
  const value = commandText(text);
  return isDesktopStop(text)
    || /^(?:open|launch|start)\s+(?:(?:the|an?)\s+)?(?:notepad|(?:file\s+)?explorer|chrome|edge|browser|app)\b/i.test(value)
    || /^(?:read|show)(?:\s+me)?\s+(?:(?:the|a)\s+)?(?:file\b|(?:that|this) file\b|it$|[^\r\n]*\.(?:txt|md|csv|json)\b)/i.test(value)
    || /^(?:list|show)(?:\s+me)?\s+(?:the\s+|my\s+)?(?:text\s+)?files\b/i.test(value)
    || /^(?:read|show|create|make|save|write)\s+[^\r\n]*\s+dot\s+(?:txt|md|csv|json)\b/i.test(value)
    || /^(?:create|make|save|write|delete|remove|rename|move|overwrite)\s+(?:(?:a|the|my|all)\s+)?(?:files?\b|[^\r\n]*\.(?:txt|md|csv|json)\b)/i.test(value);
}

/** Return true only when this input has been consumed; never also send it to chat. */
export function dispatchDesktop(text: string, target: DesktopHandle | null): boolean {
  if (!target || !isDesktopCommand(text)) return false;
  target.submit(text);
  return true;
}
