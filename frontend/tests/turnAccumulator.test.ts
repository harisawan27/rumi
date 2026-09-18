import { TurnAccumulator } from "../src/services/turnAccumulator";

declare const describe: (name: string, fn: () => void) => void;
declare const test: (name: string, fn: () => void) => void;
declare const beforeEach: (fn: () => void) => void;
declare const expect: (actual: unknown) => {
  toBe: (expected: unknown) => void;
};

describe("TurnAccumulator - Natural Pause and Turn Boundary Tests", () => {
  let accumulator: TurnAccumulator;
  let transcriptHistory: string[];

  beforeEach(() => {
    transcriptHistory = [];
    accumulator = new TurnAccumulator({
      onTranscriptChange: (text) => transcriptHistory.push(text),
    });
  });

  test("Test A: Speech 3 sec -> silence 200ms -> speech 2 sec yields ONE coherent turn", () => {
    // Clause 1
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "I was working on the project" },
    ]);
    expect(accumulator.getDisplayText()).toBe("I was working on the project");

    // 200ms pause (interim speech resumes)
    accumulator.handleSpeechResults([
      { isFinal: false, transcript: "and I think" },
    ]);
    expect(accumulator.getDisplayText()).toBe("I was working on the project and I think");

    // Clause 2 finalizes
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "and I think we should change the architecture" },
    ]);
    expect(accumulator.getDisplayText()).toBe("I was working on the project and I think we should change the architecture");

    const turn = accumulator.commit();
    expect(turn).toBe("I was working on the project and I think we should change the architecture");
  });

  test("Test B: Speech -> silence 500ms -> speech yields ONE coherent turn", () => {
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "Hello Rumi" },
    ]);
    expect(accumulator.getDisplayText()).toBe("Hello Rumi");

    // 500ms pause, speech resumes
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "can you help me with this bug" },
    ]);
    expect(accumulator.getDisplayText()).toBe("Hello Rumi can you help me with this bug");

    const turn = accumulator.commit();
    expect(turn).toBe("Hello Rumi can you help me with this bug");
  });

  test("Test C: Speech -> silence 800ms -> speech resumes just before endpoint yields ONE coherent turn", () => {
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "I've been thinking about the deployment" },
    ]);

    // 800ms natural breathing/thinking pause
    // Speech resumes with new clause
    accumulator.handleSpeechResults([
      { isFinal: false, transcript: "and what we really need" },
    ]);
    expect(accumulator.getDisplayText()).toBe("I've been thinking about the deployment and what we really need");

    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "and what we really need is Docker hardening" },
    ]);
    const turn = accumulator.commit();
    expect(turn).toBe("I've been thinking about the deployment and what we really need is Docker hardening");
  });

  test("Test D: Turn commits accumulated content when explicitly committed", () => {
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "Let's summarize the meeting notes" },
    ]);
    expect(accumulator.hasContent()).toBe(true);

    const turn = accumulator.commit();
    expect(turn).toBe("Let's summarize the meeting notes");
    expect(accumulator.hasContent()).toBe(false);
    expect(accumulator.getDisplayText()).toBe("");
  });

  test("Test E: Browser SpeechRecognition unexpectedly fires onend during a pause -> buffer remains intact", () => {
    // User speaks first clause
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "First part of my thought" },
    ]);

    // Browser fires onend due to internal segmentation or hiccup
    accumulator.handleSegmentEnd();

    // Buffer is preserved in committed, not wiped!
    expect(accumulator.getDisplayText()).toBe("First part of my thought");
    expect(accumulator.hasContent()).toBe(true);

    // Recognizer restarts and produces new speech segment
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "second part of my thought" },
    ]);
    expect(accumulator.getDisplayText()).toBe("First part of my thought second part of my thought");

    const turn = accumulator.commit();
    expect(turn).toBe("First part of my thought second part of my thought");
  });

  test("Test F: Multiple final transcript chunks merged without duplicate boundary words", () => {
    // Boundary overlap scenario: "I think" followed by "think we should"
    const merged = accumulator.mergeChunks("I think", "think we should go");
    expect(merged).toBe("I think we should go");

    // Multiple words overlap
    const multiOverlap = accumulator.mergeChunks("we should change the architecture", "the architecture right now");
    expect(multiOverlap).toBe("we should change the architecture right now");

    // No overlap
    const noOverlap = accumulator.mergeChunks("Hello world", "how are you");
    expect(noOverlap).toBe("Hello world how are you");
  });

  test("Test G: User manually presses Send / finishes push-to-talk -> immediate explicit turn completion", () => {
    accumulator.handleSpeechResults([
      { isFinal: true, transcript: "Urgent fix required on production" },
    ]);
    expect(accumulator.hasContent()).toBe(true);

    // Immediate commit
    const committed = accumulator.commit();
    expect(committed).toBe("Urgent fix required on production");
    expect(accumulator.hasContent()).toBe(false);
  });
});
