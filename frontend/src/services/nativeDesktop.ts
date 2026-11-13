export type LocalGrant = { active: boolean; workspace?: string | null; session_id?: string | null; seconds_remaining?: number; message?: string };
export type LocalReceipt = { request_id?: string; state: string; operation?: string; replayed?: boolean; message?: string; result?: { text?: string; names?: string[]; truncated?: boolean; reason?: string } };
export type VoiceEvent = { id: number; kind: "transcript" | "unclear" | "interrupted"; text: string };
export type LocalVoiceState = { active: boolean; voice_id?: number; speaking?: boolean; starting?: boolean; level?: number; language?: string; message?: string; events?: VoiceEvent[] };
export type NativeDesktopApi = {
  status(): Promise<LocalGrant>;
  choose_workspace(): Promise<LocalGrant>;
  command(request: { request_id: string; session_id: string; expires_at: number; text: string }): Promise<LocalReceipt>;
  stop(): Promise<LocalGrant>;
  voice_start?(): Promise<LocalVoiceState>;
  voice_stop?(): Promise<LocalVoiceState>;
  voice_poll?(): Promise<LocalVoiceState>;
  voice_speak?(request: {session_id: string; voice_id: number; text: string}): Promise<{accepted: boolean}>;
};
declare global { interface Window { pywebview?: { api: NativeDesktopApi } } }

export function receiptText(receipt: LocalReceipt): string {
  if (receipt.state === "uncertain") return "The action may have completed. Check your folder or app before trying again.";
  if (receipt.state === "blocked") return "This action was blocked. Check local permission and the selected folder before trying again.";
  if (receipt.state === "clarification") return receipt.message || "Please name one supported action.";
  if (receipt.state === "dispatched") return "App launch requested. Check that its window opened; window focus has not been verified.";
  if (receipt.state !== "succeeded") return receipt.result?.reason === "already_exists"
    ? "That file already exists. Its contents were not overwritten. Choose a different filename."
    : "The action could not be completed. Check the folder and filename.";
  if (receipt.operation === "read_text") return typeof receipt.result?.text === "string" ? receipt.result.text : "This request already completed. Read the file again to retrieve its contents.";
  if (receipt.operation === "list_files") return Array.isArray(receipt.result?.names)
    ? (receipt.result.names.join("\n") || "No supported text files in this folder.") + (receipt.result.truncated ? "\nOnly the first 500 folder entries were checked." : "")
    : "This request already completed. List again to refresh the results.";
  return "File created and its contents verified.";
}

// Pages preserve every character. The UI measures its text surface to determine
// a conservative monospace width/height, including wide characters and tabs.
export function textPages(text: string, columns = 44, rows = 8): string[] {
  columns = Math.max(8, columns); rows = Math.max(1, rows);
  const pages: string[] = []; let page = "", column = 0, row = 0;
  for (const char of Array.from(text)) {
    const width = char === "\t" ? 4 - column % 4 : (char.codePointAt(0) || 0) >= 0x1100 ? 2 : 1;
    if (char !== "\n" && column + width > columns) { row++; column = 0; }
    if (row >= rows) { pages.push(page); page = ""; row = column = 0; }
    page += char;
    if (char === "\n") { row++; column = 0; } else column += width;
  }
  if (page || !pages.length) pages.push(page);
  return pages;
}

export function localReply(text: string): string | null {
  const plain = text.trim().replace(/^(?:hey\s+)?rumi[,!]?\s+/i, "").replace(/[.!?]+$/, "").toLowerCase();
  if (/^(hi|hello|hey|good morning|good evening)$/.test(plain)) return "I'm here. Let's take one thing at a time. You can ask me to open Notepad, list your files, or read a note.";
  if (/^(thank you|thanks|thanks rumi)$/.test(plain)) return "You're welcome. I'm here when you need me.";
  if (/^(what can you do|help|help me)$/.test(plain)) return "I can open Notepad or Explorer, list text files, read a note, and create a file with your exact words. Begin voice requests with Rumi. Creative AI is offline for now.";
  if (/^(how are you|are you there)$/.test(plain)) return "I'm here and ready to help. Everything available in this space runs on your computer.";
  return null;
}
