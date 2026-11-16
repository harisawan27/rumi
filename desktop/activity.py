"""Small, shared desktop activity snapshot. Values are safe to show over other apps."""
import threading
import time


REVIEW = {
    "workspace": "Choose a workspace to continue.",
    "windows": "Review Windows access.",
    "wake": "Review background microphone access.",
    "draft": "Review the draft before saving.",
    "heard": "Review the request Rumi heard.",
}


class DesktopActivity:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._version = 0
        self._state = ("idle", "", None, 0)

    def _set(self, phase, message, action=None, duration=0):
        self._version += 1
        self._state = (phase, message, action, self._clock() + duration if duration else 0)
        return self._version

    def begin(self, opening_word=False):
        with self._lock:
            if self._state[0] == "working":
                return None
            note = "Opening your résumé in Word…" if opening_word else "Working on your request…"
            return self._set("working", note)

    def permission(self, kind):
        with self._lock:
            if kind in REVIEW and self._state[0] != "working":
                return self._set("permission", REVIEW[kind], "review", 120)
            return None

    def dismiss(self, token=None):
        with self._lock:
            if self._state[0] == "permission" and (token is None or token == self._version):
                self._set("idle", "")

    def stop(self, message="Paused. Local access ended."):
        with self._lock:
            self._set("paused", message, "show", 16)

    def finish(self, token, receipt):
        with self._lock:
            if token is None or self._version != token or self._state[0] != "working":
                return
            state, operation = receipt.get("state"), receipt.get("operation")
            if state == "succeeded":
                message, action = {"word_open": ("Your résumé is open in Word.", "show"),
                                   "resume_workflow": ("Your résumé is saved.", "word")}.get(operation, ("Done.", "show"))
                self._set("done", message, action, 22)
            elif state in {"plan", "workflow_review", "resume_review", "resume_share", "task_choice", "resume_details"}:
                self._set("permission", "Rumi is waiting for your next step.", "review", 180)
            elif state == "dispatched":
                self._set("dispatched", "Launch requested.", "show", 14)
            elif state in {"blocked", "uncertain", "operator_uncertain", "failed"}:
                self._set("attention", "Check the result in Rumi.", "review", 22)
            else:
                self._set("attention", "Rumi needs a little more detail.", "review", 22)

    def snapshot(self, voice):
        with self._lock:
            phase, message, action, expiry = self._state
            version = self._version
            if expiry and self._clock() >= expiry:
                phase, message, action = "idle", "", None
        if phase == "idle" and voice["speaking"]:
            phase, message = "speaking", "Rumi is speaking."
        elif phase == "idle" and voice["level"] >= 10:
            phase, message = "listening", "Rumi is listening."
        return {"version": version, "phase": phase, "message": message, "action": action, "level": voice["level"]}
