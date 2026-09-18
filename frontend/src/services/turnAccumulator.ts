/**
 * TurnAccumulator: Manages conversational speech accumulation, segmentation recovery,
 * and stable transcript continuity for Project Rumi.
 *
 * Responsibilities:
 * - Maintains committedTranscript (all finalized speech chunks in the current turn)
 *   and interimTranscript (current spoken partial phrase).
 * - Prevents premature turn endings when browser SpeechRecognition segment stops
 *   or restarts during natural breathing/thinking pauses.
 * - Deduplicates overlapping boundary words when merging chunks.
 * - Leaves automatic conversational turn completion to Gemini Live server VAD,
 *   while supporting explicit manual sends (Send button, Enter key, push-to-talk release).
 */

export interface SpeechChunk {
  isFinal: boolean;
  transcript: string;
}

export interface TurnAccumulatorOptions {
  onTranscriptChange?: (text: string) => void;
}

export class TurnAccumulator {
  private committed: string = "";
  private interim: string = "";
  private onTranscriptChange?: (text: string) => void;

  constructor(options?: TurnAccumulatorOptions) {
    this.onTranscriptChange = options?.onTranscriptChange;
  }

  /**
   * Process incoming SpeechRecognition results.
   * Keeps final results and interim results distinct, updating display text smoothly.
   */
  public handleSpeechResults(results: SpeechChunk[], startIndex: number = 0): string {
    let newInterim = "";

    for (let i = startIndex; i < results.length; i++) {
      const item = results[i];
      if (item.isFinal) {
        this.committed = this.mergeChunks(this.committed, item.transcript);
      } else {
        newInterim = this.mergeChunks(newInterim, item.transcript);
      }
    }

    this.interim = newInterim;

    const display = this.getDisplayText();
    this.onTranscriptChange?.(display);
    return display;
  }

  /**
   * Called when SpeechRecognition ends (onend).
   * Interim text is discarded because it was not finalized, while committed text
   * remains completely intact for the ongoing conversational turn.
   */
  public handleSegmentEnd(): void {
    this.interim = "";
    this.onTranscriptChange?.(this.getDisplayText());
  }

  /**
   * Merge two text chunks while avoiding duplicate words at the boundary.
   * e.g. "I think" + "think we should" -> "I think we should"
   * e.g. "I was working on the project" + "and I think" -> "I was working on the project and I think"
   */
  public mergeChunks(base: string, addition: string): string {
    const cleanBase = base.trim();
    const cleanAddition = addition.trim();

    if (!cleanBase) return cleanAddition;
    if (!cleanAddition) return cleanBase;

    const lowerBase = cleanBase.toLowerCase();
    const lowerAddition = cleanAddition.toLowerCase();

    // 1. If base already ends with addition, or addition is identical
    if (lowerBase === lowerAddition || lowerBase.endsWith(" " + lowerAddition)) {
      return cleanBase;
    }
    if (lowerAddition.startsWith(lowerBase + " ")) {
      return cleanAddition;
    }

    // 2. Check suffix/prefix word overlap
    const baseWords = cleanBase.split(/\s+/);
    const additionWords = cleanAddition.split(/\s+/);

    const maxOverlap = Math.min(baseWords.length, additionWords.length);
    for (let overlap = maxOverlap; overlap > 0; overlap--) {
      const baseTail = baseWords.slice(-overlap).map(w => w.toLowerCase()).join(" ");
      const additionHead = additionWords.slice(0, overlap).map(w => w.toLowerCase()).join(" ");
      if (baseTail === additionHead) {
        return cleanBase + " " + additionWords.slice(overlap).join(" ");
      }
    }

    return cleanBase + " " + cleanAddition;
  }

  /**
   * Get the full text for display (committed + interim).
   */
  public getDisplayText(): string {
    if (!this.committed) return this.interim;
    if (!this.interim) return this.committed;
    return this.mergeChunks(this.committed, this.interim);
  }

  /**
   * Explicit turn commit (manual Send, Enter, or push-to-talk finish).
   * Returns the complete accumulated utterance and resets the accumulator.
   */
  public commit(): string {
    const fullText = this.committed.trim();
    this.reset();
    return fullText;
  }

  /**
   * Get the complete finalized text accumulated so far without resetting.
   */
  public getCommittedText(): string {
    return this.committed.trim();
  }

  /**
   * Reset/clear the entire accumulation buffer.
   */
  public reset(): void {
    this.committed = "";
    this.interim = "";
    this.onTranscriptChange?.("");
  }

  public hasContent(): boolean {
    return (this.committed + this.interim).trim().length > 0;
  }
}
