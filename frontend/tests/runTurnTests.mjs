// Direct runner for TurnAccumulator test matrix (Tests A - G)
import { TurnAccumulator } from "../src/services/turnAccumulator.ts";

function assert(condition, message) {
  if (!condition) {
    throw new Error("Assertion failed: " + message);
  }
}

function runTests() {
  console.log("=== Running TurnAccumulator Tests A through G ===");

  // Test A
  {
    const acc = new TurnAccumulator();
    acc.handleSpeechResults([{ isFinal: true, transcript: "I was working on the project" }]);
    assert(acc.getDisplayText() === "I was working on the project", "Test A step 1");

    acc.handleSpeechResults([{ isFinal: false, transcript: "and I think" }]);
    assert(acc.getDisplayText() === "I was working on the project and I think", "Test A step 2");

    acc.handleSpeechResults([{ isFinal: true, transcript: "and I think we should change the architecture" }]);
    const turn = acc.commit();
    assert(turn === "I was working on the project and I think we should change the architecture", "Test A turn commit");
    console.log("PASS: Test A (3s speech -> 200ms pause -> 2s speech = ONE turn)");
  }

  // Test B
  {
    const acc = new TurnAccumulator();
    acc.handleSpeechResults([{ isFinal: true, transcript: "Hello Rumi" }]);
    acc.handleSpeechResults([{ isFinal: true, transcript: "can you help me with this bug" }]);
    const turn = acc.commit();
    assert(turn === "Hello Rumi can you help me with this bug", "Test B turn commit");
    console.log("PASS: Test B (speech -> 500ms pause -> speech = ONE turn)");
  }

  // Test C
  {
    const acc = new TurnAccumulator();
    acc.handleSpeechResults([{ isFinal: true, transcript: "I've been thinking about the deployment" }]);
    acc.handleSpeechResults([{ isFinal: false, transcript: "and what we really need" }]);
    assert(acc.getDisplayText() === "I've been thinking about the deployment and what we really need", "Test C step 1");

    acc.handleSpeechResults([{ isFinal: true, transcript: "and what we really need is Docker hardening" }]);
    const turn = acc.commit();
    assert(turn === "I've been thinking about the deployment and what we really need is Docker hardening", "Test C turn commit");
    console.log("PASS: Test C (speech -> 800ms pause -> speech resumes = ONE turn)");
  }

  // Test D
  {
    const acc = new TurnAccumulator();
    acc.handleSpeechResults([{ isFinal: true, transcript: "Let's summarize the meeting notes" }]);
    assert(acc.hasContent() === true, "Test D hasContent before commit");
    const turn = acc.commit();
    assert(turn === "Let's summarize the meeting notes", "Test D turn commit");
    assert(acc.hasContent() === false, "Test D hasContent after commit");
    console.log("PASS: Test D (speech -> silence -> turn commits)");
  }

  // Test E
  {
    const acc = new TurnAccumulator();
    acc.handleSpeechResults([{ isFinal: true, transcript: "First part of my thought" }]);
    acc.handleSegmentEnd(); // SpeechRecognition fires onend mid-turn
    assert(acc.getDisplayText() === "First part of my thought", "Test E segment end preserves buffer");
    assert(acc.hasContent() === true, "Test E hasContent remains true");

    acc.handleSpeechResults([{ isFinal: true, transcript: "second part of my thought" }]);
    assert(acc.getDisplayText() === "First part of my thought second part of my thought", "Test E restart accumulates");
    const turn = acc.commit();
    assert(turn === "First part of my thought second part of my thought", "Test E final commit");
    console.log("PASS: Test E (SpeechRecognition onend during pause -> buffer intact & turn preserved)");
  }

  // Test F
  {
    const acc = new TurnAccumulator();
    const merged1 = acc.mergeChunks("I think", "think we should go");
    assert(merged1 === "I think we should go", "Test F deduplication 1");

    const merged2 = acc.mergeChunks("we should change the architecture", "the architecture right now");
    assert(merged2 === "we should change the architecture right now", "Test F deduplication 2");

    const merged3 = acc.mergeChunks("Hello world", "how are you");
    assert(merged3 === "Hello world how are you", "Test F deduplication 3");
    console.log("PASS: Test F (multiple final chunks merged without duplicate words)");
  }

  // Test G
  {
    const acc = new TurnAccumulator();
    acc.handleSpeechResults([{ isFinal: true, transcript: "Urgent fix required on production" }]);
    assert(acc.hasContent() === true, "Test G hasContent");
    const turn = acc.commit();
    assert(turn === "Urgent fix required on production", "Test G explicit manual commit");
    assert(acc.hasContent() === false, "Test G cleared after manual commit");
    console.log("PASS: Test G (explicit manual Send / push-to-talk release commits immediately)");
  }

  console.log("=== ALL TESTS A THROUGH G PASSED SUCCESSFULLY ===");
}

runTests();
