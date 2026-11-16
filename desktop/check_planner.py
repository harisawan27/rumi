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
from windows_research import search_links


def verify(variant, phrases, note_workflow=False):
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
                if note_workflow:
                    folder = Path(directory) / "notes"
                    folder.mkdir()
                    runtime.enable(folder, runtime.generation)
                grant = runtime.enable_operator(runtime.generation)

                def run(text):
                    reply = runtime.command({"request_id": str(uuid4()), "session_id": grant["session_id"],
                                             "expires_at": int(time.time()) + 25, "text": text})
                    print(f"{variant}: {reply['state']} — {reply['message']}", flush=True)
                    return reply

                if note_workflow:
                    draft = run(phrases[0])
                    assert draft["state"] == "workflow_review" and "Found" in draft["result"]["text"]
                    assert not list(folder.iterdir())
                    saved = run(phrases[1])
                    assert saved["state"] == "succeeded"
                    assert (folder / "document-search.txt").read_bytes().decode() == draft["result"]["text"]
                    return

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


def main(note_workflow=False):
    phrases = (("Rumi find hello in this document and save it as a note", "Rumi confirm workflow save") if note_workflow else
               ("Rumi find hello in this document", "Rumi search for hello", "Rumi confirm window plan"))
    samples = recognize_samples(phrases)["results"]
    for row in samples:
        print(f"{row['confidence']}: {row['recognized']}", flush=True)
        assert row["confidence"] >= .72 and row["recognized"].casefold() == row["phrase"].casefold()
    for variant in (("planner",) if note_workflow else ("planner", "alternate")):
        verify(variant, [row["recognized"] for row in samples], note_workflow)


def verify_web_workflow():
    phrases = ("Rumi search for Windows keyboard shortcuts and save the first three links",
               "Rumi confirm workflow save")
    samples = recognize_samples(phrases)["results"]
    for row in samples:
        print(f"{row['confidence']}: {row['recognized']}", flush=True)
        assert row["confidence"] >= .72 and row["recognized"].casefold() == row["phrase"].casefold()
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory) / "notes"
        folder.mkdir()
        runtime = NativeRuntime(Path(directory) / "receipts.sqlite3", research=search_links)
        try:
            grant = runtime.enable(folder, runtime.generation)

            def run(text):
                reply = runtime.command({"request_id": str(uuid4()), "session_id": grant["session_id"],
                                         "expires_at": int(time.time()) + 25, "text": text})
                print(f"{reply['state']}: {reply['message']}", flush=True)
                return reply

            draft = run(samples[0]["recognized"])
            assert draft["state"] == "workflow_review" and not list(folder.iterdir())
            expected = draft["result"]["text"]
            assert sum(line.startswith("https://") for line in expected.splitlines()) == 3
            assert run(samples[1]["recognized"])["state"] == "succeeded"
            assert (folder / "research-links.txt").read_bytes().decode() == expected
        finally:
            runtime.close()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--fixture":
        fixture(sys.argv[2], sys.argv[3])
    elif "--web-workflow" in sys.argv:
        verify_web_workflow()
    else:
        main("--note-workflow" in sys.argv)
