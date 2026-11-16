"""Rumi Desktop: trusted bundled UI, native folder consent, no cloud imports."""
import ctypes
import os
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src.desktop.native_runtime import NativeRuntime, word_instruction
from src.desktop.native_assets import AssetServer
from src.desktop.workspace import WorkspaceError
from src.desktop.windows import require_unlocked_desktop
from activity import DesktopActivity
from pet_window import PetWindow
from voice import LocalVoice
from gemini_resume import configured_polisher
from wake_settings import WakeSettings
from windows_operator import WindowsControls
from windows_research import search_links
from windows_word import open_word


class Bridge:
    def __init__(self, runtime, url, settings=None, desktop_check=require_unlocked_desktop):
        self._runtime, self._url = runtime, url
        self._window = None
        self._pet = None
        self._activity = DesktopActivity()
        self._grant_was_active = False
        self._picker = threading.Lock()
        self._wake_lock = threading.Lock()
        self._settings = settings or WakeSettings()
        self._desktop_check = desktop_check
        self._wake_enabled = self._settings.enabled()
        self._wake_armed = False
        self._minimized = False
        self._wake_requested = threading.Event()
        self._wake_was_locked = False
        self._startup_cancelled = False
        self._voice = LocalVoice(lambda: not self._minimized and self._runtime.status()["active"],
                                 self._stop_all, background=self._can_wake, on_wake=self._wake_requested.set,
                                 on_request=lambda: self._activity.permission("workspace"))

    def _unlocked(self):
        try:
            self._desktop_check()
            return True
        except WorkspaceError:
            return False

    def _can_wake(self):
        return self._wake_armed and self._unlocked()

    def _stop_all(self, silent=False):
        with self._wake_lock:
            self._wake_armed = False
            self._wake_requested.clear()
            self._runtime.stop()
        self._voice.stop()
        if not silent:
            self._activity.stop("Rumi stopped.")

    def _minimize(self):
        self._minimized = True
        self._suspend()

    def _restore(self):
        self._minimized = False

    def watch(self):
        active = self._runtime.status()["active"]
        if self._grant_was_active and not active:
            self._activity.stop()
        self._grant_was_active = active
        if self._wake_armed and not self._unlocked():
            self._wake_was_locked = True
            self._wake_requested.clear()
        elif self._wake_was_locked:
            self._wake_was_locked = False
            if self._can_wake():
                self._voice.start()
        self._voice.watch()
        if self._wake_requested.is_set():
            self._wake_requested.clear()
            if self._minimized and self._can_wake() and not (self._pet and self._pet.enabled):
                try:
                    self._check_window()
                    self._window.restore()
                except Exception:
                    self._stop_all()

    def suspend_actions(self):
        self._check_window()
        self._suspend()

    def _suspend(self):
        if self._runtime.status()["active"]:
            self._activity.stop()
        self._runtime.stop()
        self._grant_was_active = False
        if self._wake_armed:
            self._voice.discard_events()
        else:
            self._voice.stop()

    def wake_set(self, enabled):
        self._check_window()
        if type(enabled) is not bool or self._minimized or not self._picker.acquire(blocking=False):
            return self.status()
        generation = self._runtime.generation
        review = self._activity.permission("wake") if enabled else None
        try:
            startup = bool(self._settings.command)
            if enabled and not self._window.create_confirmation_dialog(
                "Enable Hey Rumi in the background?",
                "Rumi will keep its microphone on while minimized and listen for Hey Rumi. "
                "Speech processing stays on this PC. Folder and app permissions end when you minimize Rumi. "
                + ("Rumi will also start minimized when you sign in to Windows. " if startup else "")
                + "Use Stop or Pause microphone to end capture for this run. Turn off Background wake to remove it from startup."
            ):
                return self.status()
            self._check_window()
            with self._wake_lock:
                if generation != self._runtime.generation or self._minimized or not self._unlocked():
                    return self._status()
                self._settings.set(enabled)
                self._wake_enabled = enabled
                self._wake_armed = enabled
            if enabled:
                self._voice.start()
            else:
                self._wake_requested.clear()
                self._voice.stop()
            return self.status()
        except OSError:
            return {**self.status(), "message": "Could not update Windows startup. Check whether another Rumi copy is registered."}
        finally:
            if review is not None:
                self._activity.dismiss(review)
            self._picker.release()

    def start_background(self):
        self._check_window()
        with self._wake_lock:
            if not self._wake_enabled or self._startup_cancelled:
                return
            self._wake_armed = True
        if self._unlocked():
            self._voice.start()

    def _check_window(self):
        if not self._window or self._window.get_current_url() != self._url:
            self._stop_all()
            raise WorkspaceError("native_window_required")

    def status(self):
        self._check_window()
        return self._status()

    def _status(self):
        return {**self._runtime.status(), "wake_enabled": self._wake_enabled, "wake_armed": self._wake_armed,
                "pet_enabled": bool(self._pet and self._pet.enabled)}

    def choose_workspace(self):
        self._check_window()
        if self._minimized or not self._picker.acquire(blocking=False):
            return {"active": False, "message": "A folder dialog is already open."}
        review = None
        try:
            import webview
            self.suspend_actions()
            review = self._activity.permission("workspace")
            generation = self._runtime.generation
            selected = self._window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=False)
            if not selected:
                return self._runtime.status()
            root = Path(selected[0]).absolute()
            if not self._window.create_confirmation_dialog("Enable local Rumi actions?",
                    f"Allow this Windows session to list, read and create text files and save a reviewed résumé in:\n{root}\n\n"
                    "Rumi may launch Notepad and Explorer and open the résumé it saved in Word. Existing files are never overwritten. "
                    "Permission lasts 15 minutes and ends on Stop, detected lock, minimize or app exit. "
                    "Local actions work without signing in or using an AI service."):
                return self._runtime.status()
            self._check_window()
            return self._runtime.enable(root, generation)
        except Exception:
            self._stop_all()
            return {"active": False, "message": "Could not enable this folder. Choose a local folder, then try again."}
        finally:
            if review is not None:
                self._activity.dismiss(review)
            self._picker.release()

    def command(self, request):
        self._check_window()
        if self._minimized:
            self._runtime.stop()
        text = request.get("text") if isinstance(request, dict) else None
        token = self._activity.begin(opening_word=word_instruction(text)) if isinstance(text, str) and len(text) <= 18000 else None
        receipt = {"state": "uncertain"}
        try:
            receipt = self._runtime.command(request)
            return receipt
        finally:
            self._activity.finish(token, receipt)

    def enable_windows_control(self):
        self._check_window()
        if self._minimized or not self._picker.acquire(blocking=False):
            return self._runtime.status()
        review = self._activity.permission("windows")
        try:
            generation = self._runtime.generation
            if not self._window.create_confirmation_dialog(
                "Allow Windows voice control?",
                "Rumi may read named controls and carry out confirmed plans in an app window you put in front. "
                "It can focus listed windows and use accessibility controls such as buttons and text fields. "
                "Use this for ordinary app tasks. Keep control of sign-in, payments and destructive actions. "
                "Permission lasts up to 15 minutes and ends at Stop, detected lock, minimize or exit."
            ):
                return self._runtime.status()
            self._check_window()
            return self._runtime.enable_operator(generation)
        except WorkspaceError:
            return {**self._runtime.status(), "message": "Windows control could not be enabled. Try again when ready."}
        finally:
            if review is not None:
                self._activity.dismiss(review)
            self._picker.release()

    def stop(self):
        self._check_window()
        with self._wake_lock:
            self._startup_cancelled = True
        self._stop_all()
        return self.status()

    def voice_start(self):
        self._check_window()
        with self._wake_lock:
            if self._wake_enabled and not self._minimized and self._unlocked():
                self._wake_armed = True
        return self._voice.start()

    def voice_stop(self):
        self._check_window()
        with self._wake_lock:
            self._startup_cancelled = True
            self._wake_armed = False
            self._wake_requested.clear()
        return self._voice.stop()

    def voice_poll(self):
        self._check_window()
        return self._voice.poll()

    def voice_speak(self, request):
        self._check_window()
        grant = self._runtime.status()
        if not isinstance(request, dict) or set(request) != {"session_id", "voice_id", "text"} or not grant["active"] or request["session_id"] != grant["session_id"]:
            return {"accepted": False}
        return self._voice.speak(request["text"], request["voice_id"])

    def pet_set(self, enabled):
        self._check_window()
        if self._pet and type(enabled) is bool:
            self._pet.enabled = enabled
        return bool(self._pet and self._pet.enabled)

    def pet_attention(self, reason):
        self._check_window()
        if isinstance(reason, str) and reason in {"workspace", "heard", "draft"}:
            self._activity.permission(reason)
        elif reason == "clear":
            self._activity.dismiss()

    def pet_status(self):
        state = self._activity.snapshot(self._voice.activity())
        if state["action"] == "word" and not self._runtime.status()["recent_resume"]:
            state["action"] = "show"
        return {**state, "visible": bool(self._pet and self._pet.visible)}

    def pet_action(self, action):
        if not self._pet or not self._pet.visible or not self._unlocked():
            return
        if action == "show":
            self._check_window()
            self._pet.restore_main()
        elif action == "stop":
            self.stop()
        elif action == "word" and self.pet_status()["action"] == "word":
            session = self._runtime.status()["session_id"]
            if session:
                self.command({"request_id": str(uuid4()), "session_id": session, "expires_at": int(time.time()) + 60,
                              "text": "open my résumé in Word"})


def expose_bridge(window, api):
    # Expose closures only. pywebview's generic js_api attribute resolver can
    # traverse private attributes when handed a crafted bridge message; a Python
    # object containing the runtime must never be supplied as js_api.
    def status():
        return api.status()
    def choose_workspace():
        return api.choose_workspace()
    def command(request):
        return api.command(request)
    def enable_windows_control():
        return api.enable_windows_control()
    def stop():
        return api.stop()
    def voice_start():
        return api.voice_start()
    def voice_stop():
        return api.voice_stop()
    def voice_poll():
        return api.voice_poll()
    def voice_speak(request):
        return api.voice_speak(request)
    def wake_set(enabled):
        return api.wake_set(enabled)
    def suspend_actions():
        return api.suspend_actions()
    def pet_set(enabled):
        return api.pet_set(enabled)
    def pet_attention(reason):
        return api.pet_attention(reason)
    window.expose(status, choose_workspace, command, enable_windows_control, stop, voice_start, voice_stop,
                  voice_poll, voice_speak, wake_set, suspend_actions, pet_set, pet_attention)


def expose_pet(window, url, api):
    def permitted():
        return window.get_current_url() == url and api._unlocked()

    def pet_status():
        return api.pet_status() if permitted() else None

    def pet_drag():
        if permitted():
            api._pet.begin_drag()

    def pet_action(action):
        if permitted() and isinstance(action, str):
            return api.pet_action(action)

    window.expose(pet_status, pet_drag, pet_action)


def main():
    if os.name != "nt":
        raise RuntimeError("Rumi Desktop currently supports Windows only")
    if ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.user32.MessageBoxW(None, "Start Rumi without administrator privileges.", "Rumi Desktop", 0x10)
        return
    import webview
    settings = WakeSettings()
    background = "--background-wake" in sys.argv[1:]
    if background and not settings.enabled():
        return
    # Keep an automatic startup and a manual launch from opening two microphones.
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    instance = kernel.CreateMutexW(None, False, r"Local\RumiDesktop")
    if not instance:
        raise OSError("Could not start a Rumi instance")
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(instance)
        if not background:
            ctypes.windll.user32.MessageBoxW(None, "Rumi is already running. Open it from the Windows taskbar.", "Rumi Desktop", 0x40)
        return
    root = Path(sys._MEIPASS) / "ui" if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1] / "frontend/out"
    server = AssetServer(root)
    data = Path(os.environ["LOCALAPPDATA"]) / "Rumi/desktop"
    runtime = NativeRuntime(data / "native-receipts.sqlite3", operator_factory=WindowsControls,
                            research=search_links, polish_resume=configured_polisher(), open_word=open_word)
    api = Bridge(runtime, server.url, settings)
    server.start()
    shutdown = threading.Event()
    window = webview.create_window("Rumi Desktop", server.url, width=1180, height=820,
        min_size=(700, 560), background_color="#050b12", text_select=True, minimized=background)
    api._window = window
    api._minimized = background
    expose_bridge(window, api)
    pet = webview.create_window("Rumi Pet", server.pet_url, width=234, height=96, hidden=True,
                               frameless=True, resizable=False, easy_drag=False, focus=False,
                               on_top=True, shadow=False, background_color="#141929", min_size=(1, 1))
    api._pet = PetWindow(window, pet, data / "pet-position.json")
    expose_pet(pet, server.pet_url, api)
    main_loaded = threading.Event()
    window.events.before_load += lambda: api._stop_all(silent=not main_loaded.is_set())
    window.events.loaded += main_loaded.set
    window.events.minimized += api._minimize
    window.events.restored += api._restore
    window.events.closing += api._stop_all
    def close_pet():
        shutdown.set()
        if pet.events.shown.is_set():
            pet.destroy()
    window.events.closed += close_pet
    if api._wake_enabled:
        def start_once():
            window.events.loaded -= start_once
            api.start_background()
        window.events.loaded += start_once

    def watch_lock():
        while not shutdown.wait(.25):
            api.watch()

    def watch_pet():
        delay = .12
        while not shutdown.wait(delay):
            try:
                delay = .018 if api._pet.watch(api._unlocked()) else .12
            except (AttributeError, OSError):
                delay = .12

    threading.Thread(target=watch_lock, daemon=True).start()
    threading.Thread(target=watch_pet, daemon=True).start()
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    try:
        webview.start(gui="edgechromium", debug=False, private_mode=True)
    finally:
        shutdown.set()
        api._voice.stop()
        runtime.close()
        server.close()
        kernel.CloseHandle(instance)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None,
                "Rumi could not start. Check that Microsoft Edge WebView2 Runtime is installed and the application folder is complete.",
                "Rumi Desktop", 0x10)
        raise
