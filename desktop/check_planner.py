"""Opt-in end-to-end check using generated speech and two disposable app layouts."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from check_windows_control import fixture
from check_speech import recognize_samples
from src.desktop.native_runtime import NativeRuntime
from windows_operator import WindowsControls


def verify(variant, phrases):
    title = "Rumi planner test " + uuid4().hex[:8]
    process = subprocess.Popen([sys.executable, __file__, "--fixture", title, variant])
    adapter = WindowsControls()
    try:
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline and process.poll() is None:
            target = next((window for window in adapter.windows(lambda: None) if window.title == title), None)
            if target:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Disposable window did not open (process status {process.poll()}).")
        adapter.focus(target, lambda: None)
        with tempfile.TemporaryDirectory() as directory:
            runtime = NativeRuntime(Path(directory) / "receipts.sqlite3", operator_factory=lambda: adapter)
            try:
                grant = runtime.enable_operator(runtime.generation)

                def run(text):
                    reply = runtime.command({"request_id": str(uuid4()), "session_id": grant["session_id"],
                                             "expires_at": int(time.time()) + 25, "text": text})
                    print(f"{variant}: {reply['state']} — {reply['message']}", flush=True)
                    return reply

                field = "Find what" if variant == "alternate" else "Search query"
                requests = ((phrases[0], "found"), (phrases[1], "contains"),
                            (f"Rumi fill {field} with weekly review", "weekly review"),
                            ("Rumi switch to details view", "is selected"))
                for request, evidence in requests:
                    assert run(request)["state"] == "plan"
                    result = run(phrases[2])
                    assert result["state"] == "succeeded" and evidence in result["message"].casefold()
            finally:
                runtime.close()
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def main():
    phrases = ("Rumi find hello in this document", "Rumi search for hello", "Rumi confirm window plan")
    samples = recognize_samples(phrases)["results"]
    for row in samples:
        print(f"{row['confidence']}: {row['recognized']}", flush=True)
        assert row["confidence"] >= .72 and row["recognized"].casefold() == row["phrase"].casefold()
    for variant in ("planner", "alternate"):
        verify(variant, [row["recognized"] for row in samples])


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--fixture":
        fixture(sys.argv[2], sys.argv[3])
    else:
        main()
