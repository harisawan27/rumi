import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from activity import DesktopActivity
from pet_window import PetWindow, clamp_position


class PetTests(unittest.TestCase):
    def test_approval_progress_and_completion_share_only_short_messages(self):
        activity = DesktopActivity(clock=lambda: 100)
        voice = {"level": 20, "speaking": False}
        self.assertEqual(activity.snapshot(voice)["phase"], "listening")
        approval = activity.permission("workspace")
        self.assertEqual(activity.snapshot(voice)["action"], "review")
        token = activity.begin(opening_word=True)
        activity.dismiss(approval)
        self.assertEqual(activity.snapshot(voice)["phase"], "working")
        activity.finish(token, {"state": "succeeded", "operation": "word_open", "result": {"secret": "my private resume"}})
        state = activity.snapshot(voice)
        self.assertEqual(state["phase"], "done")
        self.assertNotIn("private", str(state))

    def test_late_receipt_cannot_overwrite_stop(self):
        activity = DesktopActivity()
        token = activity.begin(opening_word=True)
        activity.stop()
        activity.finish(token, {"state": "succeeded", "operation": "word_open"})
        self.assertEqual(activity.snapshot({"level": 0, "speaking": False})["phase"], "paused")

    def test_window_hides_for_rumi_and_owned_prompts_and_shows_without_activation(self):
        pet = PetWindow.__new__(PetWindow)
        pet.main, pet.view = Mock(), Mock()
        pet._hwnd = lambda window: 1 if window is pet.main else 2
        pet._user = Mock()
        pet._configured = None
        pet._configure = Mock()
        pet._rect = Mock(return_value=Mock(left=0, top=0, right=234, bottom=96))
        pet._work_area = Mock(return_value=(0, 0, 1000, 800))
        pet.position, pet.visible, pet.enabled, pet._drag = None, False, True, None
        pet._user.GetForegroundWindow.return_value = 5
        pet._user.GetAncestor.return_value = 5
        pet.watch(True)
        self.assertTrue(pet.visible)
        self.assertEqual(pet._user.SetWindowPos.call_args.args[-1], 0x51)
        pet._user.GetAncestor.return_value = 1
        pet.watch(True)
        self.assertFalse(pet.visible)
        self.assertEqual(pet._user.SetWindowPos.call_args.args[-1], 0x97)
        self.assertEqual(clamp_position(-2000, 999, 234, 96, (-1920, 0, 0, 1000)), (-1920, 904))
