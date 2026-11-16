import http.client
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.desktop.native_runtime import NativeRuntime
from src.desktop.native_assets import AssetServer
from src.desktop.resume import WORD
from src.desktop.workspace import WorkspaceError
from main import Bridge, expose_bridge, expose_pet


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "chosen"
        self.root.mkdir()
        self.clock = [100.0]
        self.desktop = Mock()
        self.launch = Mock(return_value={"dispatched": True, "verified_window": False})
        self.runtime = NativeRuntime(Path(self.temp.name) / "receipts.db", self.desktop, self.launch, clock=lambda: self.clock[0])

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def enable(self):
        return self.runtime.enable(self.root, self.runtime.generation)

    def request(self, text, **changes):
        return {"request_id": str(uuid4()), "session_id": self.runtime.status()["session_id"] or "missing", "expires_at": int(time.time()) + 90, "text": text, **changes}

    def test_no_grant_no_execution(self):
        self.assertEqual(self.runtime.command(self.request("open Notepad"))["state"], "blocked")
        self.launch.assert_not_called()

    def test_create_read_list_and_duplicate(self):
        self.enable()
        request = self.request("Create test.txt with content: local-only")
        first = self.runtime.command(request)
        self.assertEqual(first["state"], "succeeded")
        self.assertEqual((self.root / "test.txt").read_text(), "local-only")
        self.assertTrue(self.runtime.command(request)["replayed"])
        self.assertEqual(self.runtime.command(self.request("Read that file"))["result"]["text"], "local-only")
        self.assertEqual(self.runtime.command(self.request("List files"))["result"]["names"], ["test.txt"])
        collision = self.runtime.command(self.request("Create test.txt with content: replacement"))
        self.assertEqual(collision["result"]["reason"], "already_exists")
        self.assertEqual((self.root / "test.txt").read_text(), "local-only")

    def test_literal_contents_and_escape_rejection(self):
        self.enable()
        self.runtime.command(self.request("Create data.txt with content: open Notepad"))
        self.assertEqual((self.root / "data.txt").read_text(), "open Notepad")
        self.launch.assert_not_called()
        for text in ("read ../private.txt", "create CON.txt with content: x", "run powershell", "delete all files", "shutdown laptop"):
            with self.subTest(text=text):
                self.assertEqual(self.runtime.command(self.request(text))["state"], "clarification")

    def test_stop_revokes_and_clears_last_file(self):
        self.enable()
        self.runtime.command(self.request("Create data.txt with content: private"))
        self.runtime.stop()
        self.assertIsNone(self.runtime.status()["workspace"])
        self.enable()
        self.assertEqual(self.runtime.command(self.request("Read that file"))["state"], "clarification")

    def test_expiry_is_not_renewed_by_status_or_commands(self):
        self.enable()
        self.clock[0] += 899
        self.runtime.command(self.request("List files"))
        self.clock[0] += 2
        self.assertFalse(self.runtime.status()["active"])
        self.assertEqual(self.runtime.command(self.request("open Notepad"))["state"], "blocked")
        self.launch.assert_not_called()

    def test_lock_revokes_until_new_native_consent(self):
        self.enable()
        self.desktop.side_effect = WorkspaceError("desktop_locked")
        self.assertFalse(self.runtime.status()["active"])
        self.desktop.side_effect = None
        self.assertFalse(self.runtime.status()["active"])
        self.assertTrue(self.enable()["active"])

    def test_stop_during_consent_cannot_enable_later(self):
        generation = self.runtime.generation
        self.runtime.stop()
        with self.assertRaisesRegex(WorkspaceError, "authorization_cancelled"):
            self.runtime.enable(self.root, generation)

    def test_extra_fields_and_stale_deadline_rejected(self):
        self.enable()
        for extra in ({"root": "C:/"}, {"shell": "whoami"}, {"last_file": "private.txt"}):
            self.assertEqual(self.runtime.command(self.request("List files", **extra))["state"], "blocked")
        self.assertEqual(self.runtime.command(self.request("open Notepad", expires_at=1))["state"], "blocked")
        self.launch.assert_not_called()

    def test_wrong_session_revokes(self):
        self.enable()
        self.assertEqual(self.runtime.command(self.request("open Notepad", session_id="other"))["state"], "blocked")
        self.assertFalse(self.runtime.status()["active"])

    def test_reused_id_with_different_arguments_does_not_execute(self):
        self.enable()
        request = self.request("List files")
        self.runtime.command(request)
        self.assertEqual(self.runtime.command({**request, "text": "open Notepad"})["state"], "blocked")
        self.launch.assert_not_called()

    def test_stop_during_launch_suppresses_result_and_preserves_receipt(self):
        self.enable()
        entered, release = threading.Event(), threading.Event()
        def launch(app, check):
            entered.set()
            release.wait(5)
            check()
        self.runtime._launcher = launch
        self.runtime._executor.launcher = launch
        request = self.request("open Notepad")
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(self.runtime.command(request)))
        worker.start()
        self.assertTrue(entered.wait(3))
        try:
            self.assertEqual(self.runtime.command(self.request("List files"))["state"], "blocked")
            self.runtime.stop()
            self.assertFalse(self.runtime.status()["active"])
        finally:
            release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcome[0]["state"], "blocked")
        state = self.runtime._executor.db.execute("SELECT state FROM receipts WHERE id=?", (request["request_id"],)).fetchone()[0]
        self.assertEqual(state, "uncertain")

    def test_native_picker_and_confirmation_are_both_required(self):
        bridge = Bridge(self.runtime, "http://127.0.0.1:1234/private/")
        window = Mock()
        window.get_current_url.return_value = bridge._url
        window.create_file_dialog.return_value = [str(self.root)]
        window.create_confirmation_dialog.return_value = False
        bridge._window = window
        with patch.dict(sys.modules, {"webview": Mock()}):
            self.assertFalse(bridge.choose_workspace()["active"])
            window.create_confirmation_dialog.return_value = True
            self.assertTrue(bridge.choose_workspace()["active"])
        window.get_current_url.return_value = "https://example.com"
        with self.assertRaisesRegex(WorkspaceError, "native_window_required"):
            bridge.command(self.request("open Notepad"))
        self.assertFalse(self.runtime.status()["active"])

    def test_exports_have_no_runtime_object_surface(self):
        bridge = Bridge(self.runtime, "local")
        window = Mock()
        expose_bridge(window, bridge)
        exports = window.expose.call_args.args
        self.assertEqual({f.__name__ for f in exports}, {"status", "choose_workspace", "command", "enable_windows_control", "stop", "voice_start", "voice_stop", "voice_poll", "voice_speak", "wake_set", "suspend_actions", "pet_set", "pet_attention"})
        self.assertTrue(all(not hasattr(f, "__self__") for f in exports))

    def test_pet_exposes_only_its_own_trusted_controls(self):
        bridge = Bridge(self.runtime, "main", desktop_check=self.desktop)
        window = Mock()
        bridge._pet = Mock(visible=True)
        expose_pet(window, "pet", bridge)
        methods = {method.__name__: method for method in window.expose.call_args.args}
        self.assertEqual(set(methods), {"pet_status", "pet_drag", "pet_action"})
        window.get_current_url.return_value = "main"
        self.assertIsNone(methods["pet_status"]())
        methods["pet_drag"]()
        bridge._pet.begin_drag.assert_not_called()
        window.get_current_url.return_value = "pet"
        self.assertEqual(methods["pet_status"]()["phase"], "idle")
        methods["pet_drag"]()
        bridge._pet.begin_drag.assert_called_once()

    def test_minimize_preserves_only_opted_in_microphone(self):
        self.enable()
        settings = Mock(command='"RumiDesktop.exe" --background-wake')
        settings.enabled.return_value = False
        bridge = Bridge(self.runtime, "local", settings, self.desktop)
        bridge._window = Mock()
        bridge._window.get_current_url.return_value = "local"
        engine = Mock(language="en-US")
        callbacks = []
        def factory(*handlers):
            callbacks.extend(handlers)
            return engine
        bridge._voice._factory = factory
        bridge._window.create_confirmation_dialog.return_value = False
        self.assertFalse(bridge.wake_set(True)["wake_armed"])
        settings.set.assert_not_called()
        engine.start.assert_not_called()
        bridge._window.create_confirmation_dialog.return_value = True
        self.assertTrue(bridge.wake_set(True)["wake_armed"])
        settings.set.assert_called_once_with(True)
        bridge._minimize()
        self.assertTrue(bridge.voice_poll()["active"])
        self.assertFalse(bridge.status()["active"])
        callbacks[0]()
        callbacks[1]("Hey Rumi open Notepad", .99)
        bridge.watch()
        bridge._window.restore.assert_called_once()
        self.assertEqual(bridge.voice_poll()["events"][0]["kind"], "wake_request")
        self.launch.assert_not_called()
        self.desktop.side_effect = WorkspaceError("desktop_locked")
        bridge.watch()
        self.assertFalse(bridge.voice_poll()["active"])
        self.desktop.side_effect = None
        bridge.watch()
        self.assertTrue(bridge.voice_poll()["active"])
        bridge.stop()
        self.assertFalse(bridge.voice_poll()["active"])
        self.assertFalse(bridge.status()["wake_armed"])
        bridge.start_background()
        self.assertFalse(bridge.voice_poll()["active"])

    def start_resume(self):
        drive = self.root.drive.rstrip(":")
        command = f"Hey Rumi make new folder in {drive} drive and make a resume for me in it" if drive else "make a resume"
        self.assertEqual(self.runtime.command(self.request(command))["state"], "resume_details")
        self.runtime.command(self.request("resume name Jane & Jordan"))
        return self.runtime.command(self.request("resume details Built local Windows tools.\nEducation: BS Computer Science"))

    def test_resume_requires_facts_review_and_consent_then_verifies_word_file(self):
        self.enable()
        self.assertEqual(self.runtime.command(self.request("confirm resume save"))["state"], "clarification")
        preview = self.start_resume()
        path = self.root / "Resume/Resume.docx"
        self.assertEqual(preview["state"], "resume_review")
        self.assertEqual(preview["result"]["path"], str(path))
        self.assertFalse(path.parent.exists())
        request = self.request("confirm resume save")
        receipt = self.runtime.command(request)
        self.assertEqual(receipt["state"], "succeeded", receipt)
        self.assertEqual(receipt["result"]["path"], str(path))
        with zipfile.ZipFile(path) as document:
            self.assertIsNone(document.testzip())
            node = ET.fromstring(document.read("word/document.xml"))
        actual = "\n".join("".join(n.text or "" for n in row.iter(f"{{{WORD}}}t")) for row in node.iter(f"{{{WORD}}}p"))
        self.assertEqual(actual, preview["result"]["text"])
        self.assertEqual(self.runtime.command(request)["state"], "clarification")
        self.start_resume()
        self.assertEqual(self.runtime.command(self.request("confirm resume save"))["state"], "clarification")
        row = self.runtime._executor.db.execute("SELECT result FROM receipts WHERE id=?", (request["request_id"],)).fetchone()
        self.assertNotIn("Jane", row[0])

    def test_resume_checks_drive_folder_and_expiry(self):
        self.enable()
        other = "Z" if self.root.drive != "Z:" else "Q"
        result = self.runtime.command(self.request(f"make new folder in {other} drive and make a resume for me in it"))
        self.assertEqual(result["state"], "clarification")
        self.start_resume()
        for name in ("../outside", "CON", "C:\\other"):
            result = self.runtime.command(self.request(f"resume folder named {name}"))
            self.assertEqual(result["result"]["path"], str(self.root / "Resume/Resume.docx"))
        self.clock[0] += 181
        self.assertEqual(self.runtime.command(self.request("confirm resume save"))["state"], "clarification")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_gemini_requires_separate_share_confirmation_and_save_confirmation(self):
        self.runtime._polish_resume = Mock(return_value="Jane & Jordan\n\nBuilt Windows tools.")
        self.enable()
        self.start_resume()
        self.runtime.command(self.request("confirm Gemini draft"))
        self.runtime._polish_resume.assert_not_called()
        share = self.runtime.command(self.request("polish resume with Gemini"))
        self.assertEqual(share["state"], "resume_share")
        self.runtime._polish_resume.assert_not_called()
        polished = self.runtime.command(self.request("confirm Gemini draft"))
        self.assertEqual(self.runtime._polish_resume.call_args.args[0], share["result"]["text"])
        self.assertEqual(polished["state"], "resume_review")
        self.assertFalse((self.root / "Resume").exists())
        self.assertEqual(self.runtime.command(self.request("confirm resume save"))["state"], "succeeded")

    def test_word_handoff_uses_only_verified_recent_resume_and_checks_answer(self):
        self.runtime._open_word = Mock(side_effect=lambda path, guard: str(path))
        self.enable()
        command = "open it in Word"
        self.assertEqual(self.runtime.command(self.request(command))["state"], "clarification")
        self.start_resume()
        self.assertEqual(self.runtime.command(self.request("confirm resume save"))["state"], "succeeded")
        request = self.request(command)
        self.assertEqual(self.runtime.command(request)["state"], "succeeded")
        self.assertEqual(self.runtime._open_word.call_args.args[0], self.root / "Resume/Resume.docx")
        self.assertEqual(self.runtime.command(request)["state"], "clarification")
        self.runtime._open_word.return_value = str(self.root / "Other/Resume.docx")
        self.runtime._open_word.side_effect = None
        self.assertEqual(self.runtime.command(self.request(command))["state"], "operator_uncertain")
        self.runtime.stop()
        self.assertFalse(self.runtime.status()["recent_resume"])


class AssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "desktop-local").mkdir()
        (root / "desktop-local/index.html").write_text("<html>local UI</html>")
        (root / "desktop-pet").mkdir()
        (root / "desktop-pet/index.html").write_text("<html>pet UI</html>")
        (root / "_next/static").mkdir(parents=True)
        (root / "_next/static/app.js").write_text("/* bundled */")
        (root / "private.txt").write_text("do not serve")
        self.server = AssetServer(root)
        self.server.start()

    def tearDown(self):
        self.server.close(); self.temp.cleanup()

    def get(self, path, method="GET", headers=None):
        conn = http.client.HTTPConnection(self.server.host, timeout=3)
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_serves_only_bundle_with_closed_network_policy(self):
        status, headers, body = self.get(self.server.document_path)
        self.assertEqual(status, 200)
        self.assertIn(b"local UI", body)
        self.assertIn(b"pet UI", self.get(self.server.pet_path)[2])
        self.assertEqual(self.get("/desktop-pet/")[0], 404)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.get("/_next/static/app.js")[0], 200)

    def test_no_command_api_host_bypass_or_file_escape(self):
        for path in ("/", "/desktop-local/", "/private.txt", "/command", "/_next/static/../../private.txt", "/_next/static/%2e%2e/%2e%2e/private.txt"):
            self.assertEqual(self.get(path)[0], 404)
        self.assertEqual(self.get(self.server.document_path, headers={"Host": "attacker.invalid"})[0], 403)
        self.assertEqual(self.get("/command", method="POST")[0], 501)


if __name__ == "__main__":
    unittest.main()
