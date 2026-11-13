export type LocalGrant = { active: boolean; workspace?: string | null; session_id?: string | null; seconds_remaining?: number; message?: string };
export type LocalReceipt = { request_id?: string; state: string; operation?: string; replayed?: boolean; message?: string; result?: { text?: string; names?: string[]; truncated?: boolean; reason?: string } };
export type NativeDesktopApi = {
  status(): Promise<LocalGrant>;
  choose_workspace(): Promise<LocalGrant>;
  command(request: { request_id: string; session_id: string; expires_at: number; text: string }): Promise<LocalReceipt>;
  stop(): Promise<LocalGrant>;
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
