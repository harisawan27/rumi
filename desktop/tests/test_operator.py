"""Offline operator policy, consent and execution regressions."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2] / "backend")]

from main import Bridge
from src.desktop.native_runtime import NativeRuntime
from src.desktop.operator import PlanError, Step, Unverified, parse_plan, window_instruction
from src.desktop.workspace import WorkspaceError
from unittest.mock import Mock


class App:
    def __init__(self):
        self.window = SimpleNamespace(title="Fixture")
        self.active = self.window
        self.actions = []
        self.failure = None
        self.launches = []

    def foreground(self, guard):
        guard()
        return self.active

    def validate_target(self, target, guard):
        guard()
        if target is not self.active:
            raise PlanError("Window changed.")

    def describe(self, target, guard):
        self.validate_target(target, guard)
        return ["Find (button)"]

    def windows(self, guard):
        guard()
        return [self.window]

    def focus(self, target, guard):
        guard()
        self.active = target

    def perform(self, target, step, guard):
        self.validate_target(target, guard)
        if self.failure and self.actions:
            raise self.failure
        self.actions.append(step)


class OperatorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = App()
        self.clock = 100.0
        self.desktop = Mock()
        self.runtime = NativeRuntime(Path(temporary.name) / "receipts.db", desktop_check=self.desktop,
            launcher=self.launch, clock=lambda: self.clock, wall_clock=lambda: self.clock, operator_factory=lambda: self.app)
        self.addCleanup(self.runtime.close)

    def launch(self, name, check):
        check()
        self.app.launches.append(name)
        return {"dispatched": True}

    def enable(self):
        return self.runtime.enable_operator(self.runtime.generation)

    def send(self, text, **fields):
        status = self.runtime.status()
        raw = {"request_id": str(uuid4()), "session_id": status["session_id"] or "missing",
               "expires_at": int(self.clock) + 90, "text": text}
        return self.runtime.command({**raw, **fields})

    def test_literal_values_keep_punctuation_and_quoted_separators(self):
        request = 'Rumi control window set "Note to self" to "food then coffee!"'
        self.assertEqual(parse_plan(window_instruction(request).removeprefix("control window ")),
                         (Step("set", "Note to self", "food then coffee!"),))
        self.assertEqual(window_instruction("control window set Note to Coffee!"), "control window set Note to Coffee!")
        self.assertEqual(parse_plan('click Find then expect Search then type "go into town" into Search'),
                         (Step("press", "Find", "Search"), Step("set", "Search", "go into town")))
        for invalid in ("press Find", "press Find then expect Search then expect Results", "run powershell", "set Note to"):
            with self.subTest(invalid=invalid), self.assertRaises(PlanError):
                parse_plan(invalid)

    def test_requires_separate_permission_and_confirm_consumes_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            self.runtime.enable(folder, self.runtime.generation)
            self.assertEqual(self.send("inspect window")["state"], "clarification")
            status = self.enable()
            self.assertTrue(status["windows_control"])
            self.assertEqual(status["workspace"], folder)
        preview = self.send("control window press Find then expect Search then set Search to invoice")
        self.assertEqual(preview["state"], "plan")
        self.assertIn("invoice", preview["message"])
        self.assertEqual(self.app.actions, [])
        confirm_id = str(uuid4())
        self.assertEqual(self.send("confirm window plan", request_id=confirm_id)["state"], "succeeded")
        self.assertIn("already handled", self.send("confirm window plan", request_id=confirm_id)["message"])
        self.assertEqual(self.send("confirm window plan")["state"], "clarification")
        self.assertEqual(self.app.actions, [Step("press", "Find", "Search"), Step("set", "Search", "invoice")])

    def test_expiry_focus_changes_and_cancel_prevent_execution(self):
        self.enable()
        for interruption in ("expire", "focus", "cancel"):
            self.assertEqual(self.send("control window set Search to invoice")["state"], "plan")
            if interruption == "expire":
                self.clock += 61
            if interruption == "focus":
                self.app.active = SimpleNamespace(title="Other")
            if interruption == "cancel":
                self.send("cancel window plan")
            self.assertEqual(self.send("confirm window plan")["state"], "clarification")
            self.assertEqual(self.app.actions, [])
            self.app.active = self.app.window

    def test_partial_failure_does_not_continue_and_describes_what_verified(self):
        self.enable()
        self.send("control window set One to 1 then set Two to 2 then set Three to 3")
        self.app.failure = Unverified("Second change is uncertain.")
        result = self.send("confirm window plan")
        self.assertEqual(result["state"], "operator_uncertain")
        self.assertIn("Verified 1 of 3", result["message"])
        self.assertEqual(self.app.actions, [Step("set", "One", "1")])

    def test_list_focus_and_operator_only_launch_replay(self):
        self.assertIsNone(self.enable()["workspace"])
        self.assertEqual(self.send("list files")["state"], "clarification")
        self.assertIn("1. Fixture", self.send("list windows")["message"])
        self.app.active = SimpleNamespace(title="Other")
        self.assertIn("Focused Fixture", self.send("focus window one")["message"])
        self.assertIn("Find (button)", self.send("inspect window")["message"])
        request_id = str(uuid4())
        self.assertEqual(self.send("open Notepad", request_id=request_id)["state"], "dispatched")
        self.assertEqual(self.send("open Notepad", request_id=request_id)["state"], "clarification")
        self.assertEqual(self.app.launches, ["notepad"])

    def test_stop_during_dispatch_cancels_remaining_actions(self):
        self.enable()
        self.send("control window set One to 1 then set Two to 2")
        started, release = threading.Event(), threading.Event()
        original = self.app.perform
        def blocked(target, step, guard):
            started.set()
            release.wait(2)
            original(target, step, guard)
        self.app.perform = blocked
        result = []
        worker = threading.Thread(target=lambda: result.append(self.send("confirm window plan")))
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            self.runtime.stop()
        finally:
            release.set()
            worker.join(3)
        self.assertEqual(result[0]["state"], "blocked")
        self.assertEqual(self.app.actions, [])
        self.assertFalse(self.runtime.status()["windows_control"])

    def test_bridge_requires_consent_and_rejects_late_grant(self):
        window = Mock()
        window.get_current_url.return_value = "local"
        bridge = Bridge(self.runtime, "local")
        bridge._window = window
        window.create_confirmation_dialog.return_value = False
        self.assertFalse(bridge.enable_windows_control()["windows_control"])
        def stop_first(*_):
            self.runtime.stop()
            return True
        window.create_confirmation_dialog.side_effect = stop_first
        self.assertFalse(bridge.enable_windows_control()["windows_control"])
        self.assertFalse(self.runtime.status()["active"])
        window.create_confirmation_dialog.side_effect = None
        window.create_confirmation_dialog.return_value = True
        self.assertTrue(bridge.enable_windows_control()["windows_control"])
        window.get_current_url.return_value = "http://other"
        with self.assertRaises(WorkspaceError):
            bridge.enable_windows_control()
        self.assertFalse(self.runtime.status()["windows_control"])


if __name__ == "__main__":
    unittest.main()
