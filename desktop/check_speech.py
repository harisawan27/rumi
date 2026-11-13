"""Opt-in installed-engine diagnostic. Uses temporary WAVs, never microphone/speakers."""
import json
import tempfile
from pathlib import Path

from voice import WindowsSpeech, addressed


def main():
    engine = WindowsSpeech(lambda: None, lambda *_: None, lambda *_: None, lambda: None, lambda: None)
    try:
        results = []
        with tempfile.TemporaryDirectory(prefix="rumi-speech-") as directory:
            for index, phrase in enumerate(("Rumi stop", "Rumi open Notepad", "Rumi list files")):
                path = Path(directory) / f"{index}.wav"
                engine.synth.SetOutputToWaveFile(str(path))
                engine.synth.Speak(phrase)
                engine.synth.SetOutputToNull()
                engine.recognizer.SetInputToWaveFile(str(path))
                result = engine.recognizer.Recognize()
                words = str(result.Text) if result else ""
                confidence = float(result.Confidence) if result else 0
                results.append({"phrase": phrase, "recognized": words, "confidence": round(confidence, 3)})
                engine.recognizer.SetInputToNull()
        print(json.dumps({"language": engine.language, "results": results}, indent=2))
        if not all(row["recognized"].lower() == row["phrase"].lower() and addressed(row["recognized"]) and row["confidence"] >= .72 for row in results):
            raise SystemExit("Synthetic recognition did not meet the command threshold. This is not a live microphone test.")
    finally:
        engine.close()


if __name__ == "__main__":
    main()
