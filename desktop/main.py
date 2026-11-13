"""Rumi Desktop: trusted bundled UI, native folder consent, no cloud imports."""
import ctypes
import os
import sys
import threading
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src.desktop.native_runtime import NativeRuntime
from src.desktop.native_assets import AssetServer
from src.desktop.workspace import WorkspaceError


class Bridge:
    def __init__(self, runtime, url):
        self._runtime, self._url = runtime, url
        self._window = None
        self._picker = threading.Lock()

    def _check_window(self):
        if not self._window or self._window.get_current_url() != self._url:
            self._runtime.stop()
            raise WorkspaceError("native_window_required")

    def status(self):
        self._check_window()
        return self._runtime.status()

    def choose_workspace(self):
        self._check_window()
        if not self._picker.acquire(blocking=False):
            return {"active": False, "message": "A folder dialog is already open."}
        try:
            import webview
            self._runtime.stop()
            generation = self._runtime.generation
            selected = self._window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=False)
            if not selected:
                return self._runtime.status()
            root = Path(selected[0]).absolute()
            if not self._window.create_confirmation_dialog("Enable local Rumi actions?",
                    f"Allow this Windows session to list, read and create text files in:\n{root}\n\n"
                    "Rumi may also launch Notepad and Explorer. Existing files are never overwritten. "
                    "Permission lasts 15 minutes and ends on Stop, detected lock, minimize or app exit. "
                    "No Google sign-in, face verification or AI service is used in this local mode."):
                return self._runtime.status()
            self._check_window()
            return self._runtime.enable(root, generation)
        except Exception:
            self._runtime.stop()
            return {"active": False, "message": "Could not enable this folder. Choose a local folder, then try again."}
        finally:
            self._picker.release()

    def command(self, request):
        self._check_window()
        return self._runtime.command(request)

    def stop(self):
        self._check_window()
        return self._runtime.stop()


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
    def stop():
        return api.stop()
    window.expose(status, choose_workspace, command, stop)


def main():
    if os.name != "nt":
        raise RuntimeError("Rumi Desktop currently supports Windows only")
    if ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.user32.MessageBoxW(None, "Start Rumi without administrator privileges.", "Rumi Desktop", 0x10)
        return
    import webview
    root = Path(sys._MEIPASS) / "ui" if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1] / "frontend/out"
    server = AssetServer(root)
    runtime = NativeRuntime(Path(os.environ["LOCALAPPDATA"]) / "Rumi/desktop/native-receipts.sqlite3")
    api = Bridge(runtime, server.url)
    server.start()
    shutdown = threading.Event()
    window = webview.create_window("Rumi Desktop", server.url, width=1180, height=820,
        min_size=(700, 560), background_color="#101514", text_select=True)
    api._window = window
    expose_bridge(window, api)
    window.events.before_load += runtime.stop
    window.events.minimized += runtime.stop
    window.events.closing += runtime.stop

    def watch_lock():
        while not shutdown.wait(1):
            runtime.status()  # Revokes on lock/expiry, never renews a grant.

    threading.Thread(target=watch_lock, daemon=True).start()
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    try:
        webview.start(gui="edgechromium", debug=False, private_mode=True)
    finally:
        shutdown.set()
        runtime.close()
        server.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None,
                "Rumi could not start. Check that Microsoft Edge WebView2 Runtime is installed and the application folder is complete.",
                "Rumi Desktop", 0x10)
        raise
