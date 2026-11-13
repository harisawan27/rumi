import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voice import LocalVoice, addressed


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.now = [100.0]
        self.allowed = True
        self.engines = []
        self.emergency = Mock()
        def factory(*callbacks):
            engine = Mock(language="en-US")
            engine.callbacks = callbacks
            self.engines.append(engine)
            return engine
        self.voice = LocalVoice(lambda: self.allowed, self.emergency, factory, lambda: self.now[0])

    def tearDown(self):
        self.voice.stop()

    def start(self):
        return self.voice.start()["voice_id"]

    def hear(self, text, confidence=.9):
        callbacks = self.engines[-1].callbacks
        callbacks[0]()
        callbacks[1](text, confidence)

    def test_permission_required_and_no_automatic_microphone(self):
        self.assertFalse(self.voice.poll()["active"])
        self.assertEqual(self.engines, [])
        self.allowed = False
        self.assertFalse(self.voice.start()["active"])
        self.assertEqual(self.engines, [])

    def test_only_addressed_confident_speech_is_emitted_once(self):
        self.start()
        self.hear("open Notepad")
        self.assertEqual(self.voice.poll()["events"], [])
        self.hear("Rumi open Notepad", .4)
        self.assertEqual(self.voice.poll()["events"][0]["kind"], "unclear")
        self.hear("Hey Roomie, open Notepad")
        event = self.voice.poll()["events"][0]
        self.assertEqual((event["kind"], event["text"]), ("transcript", "open Notepad"))
        self.assertEqual(self.voice.poll()["events"], [])

    def test_stop_revokes_immediately_and_late_callbacks_are_discarded(self):
        self.start()
        old = self.engines[-1].callbacks
        self.hear("Rumi stop", .6)
        self.emergency.assert_called_once()
        self.assertFalse(self.voice.poll()["active"])
        old[1]("Rumi open Notepad", .99)
        self.assertEqual(self.voice.poll()["events"], [])
        self.start()
        old[1]("Rumi create wrong dot txt with content hello", .99)
        self.assertEqual(self.voice.poll()["events"], [])

    def test_speech_echo_and_tail_cannot_issue_commands(self):
        token = self.start()
        self.assertTrue(self.voice.speak("File created.", token)["accepted"])
        self.hear("Rumi open Notepad")
        self.assertEqual(self.voice.poll()["events"], [])
        # Utterance started over playback; recognition completes after playback.
        self.engines[-1].callbacks[0]()
        self.engines[-1].callbacks[3]()
        self.now[0] += 2
        self.engines[-1].callbacks[1]("Rumi open Explorer", .99)
        self.assertEqual(self.voice.poll()["events"], [])
        self.hear("Rumi list files")
        self.assertEqual(self.voice.poll()["events"][0]["text"], "list files")

    def test_explicit_listen_interrupt_and_stale_speech_rejection(self):
        token = self.start()
        self.voice.speak("Hello.", token)
        self.hear("Rumi listen")
        self.engines[-1].quiet.assert_called_once()
        self.assertFalse(self.voice.poll()["speaking"])
        self.voice.stop()
        new_token = self.start()
        self.assertNotEqual(token, new_token)
        self.assertFalse(self.voice.speak("late response", token)["accepted"])

    def test_lock_and_quiet_timeout_release_capture(self):
        self.start()
        self.allowed = False
        self.voice.watch()
        self.assertFalse(self.voice.poll()["active"])
        self.allowed = True
        self.assertFalse(self.voice.poll()["active"])
        self.start()
        self.now[0] += 121
        self.voice.watch()
        self.assertFalse(self.voice.poll()["active"])

    def test_stop_during_initialization_never_starts_late_engine(self):
        entered, release = threading.Event(), threading.Event()
        engine = Mock(language="en-US")
        def factory(*callbacks):
            entered.set(); release.wait(4); return engine
        self.voice._factory = factory
        thread = threading.Thread(target=self.voice.start)
        thread.start()
        self.assertTrue(entered.wait(2))
        self.voice.stop()
        release.set(); thread.join(4)
        self.assertFalse(thread.is_alive())
        engine.start.assert_not_called()
        engine.close.assert_called_once()
        self.assertFalse(self.voice.poll()["active"])

    def test_bounded_events_fail_closed_and_no_speech_backlog(self):
        token = self.start()
        self.assertTrue(self.voice.speak("First", token)["accepted"])
        self.assertFalse(self.voice.speak("Second", token)["accepted"])
        self.engines[-1].callbacks[3]()
        self.now[0] += 2
        for _ in range(9): self.hear("Rumi list files")
        self.assertFalse(self.voice.poll()["active"])
        self.assertEqual(self.voice.poll()["events"], [])

    def test_stop_is_not_blocked_by_microphone_start(self):
        entered, release = threading.Event(), threading.Event()
        engine = Mock(language="en-US")
        engine.start.side_effect = lambda: (entered.set(), release.wait(4))
        self.voice._factory = lambda *args: engine
        thread = threading.Thread(target=self.voice.start)
        thread.start()
        self.assertTrue(entered.wait(2))
        self.assertFalse(self.voice.stop()["active"])
        release.set(); thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertFalse(self.voice.poll()["active"])

    def test_no_microphone_auto_retry_after_failure(self):
        self.voice._factory = Mock(side_effect=RuntimeError("device missing"))
        self.assertFalse(self.voice.start()["active"])
        self.voice.poll(); self.voice.watch()
        self.voice._factory.assert_called_once()

    def test_addressing_does_not_rewrite_content(self):
        self.assertIsNone(addressed("someone said open Notepad"))
        self.assertEqual(addressed("Rumi create a.txt with content: Rumi open Notepad"), "create a.txt with content: Rumi open Notepad")


if __name__ == "__main__":
    unittest.main()
