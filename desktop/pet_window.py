"""Windows placement and non-activating show/hide for the bundled pet view."""
import ctypes
import json
from ctypes import wintypes


class MonitorInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                ("work", wintypes.RECT), ("flags", wintypes.DWORD)]


def clamp_position(x, y, width, height, work):
    left, top, right, bottom = work
    return (max(left, min(x, right - width)), max(top, min(y, bottom - height)))


class PetWindow:
    def __init__(self, main, view, position_file):
        self.main, self.view = main, view
        self.position_file = position_file
        self.position = self._load_position()
        self.enabled = True
        self.visible = False
        self._drag = None
        self._configured = None
        self._previous_size = None
        self._user = ctypes.WinDLL("user32", use_last_error=True)
        self._gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        handle, integer = wintypes.HWND, ctypes.c_int
        self._bind(self._user, "GetForegroundWindow", handle)
        self._bind(self._user, "IsIconic", wintypes.BOOL, handle)
        self._bind(self._user, "GetAncestor", handle, handle, wintypes.UINT)
        self._bind(self._user, "GetWindowRect", wintypes.BOOL, handle, ctypes.POINTER(wintypes.RECT))
        self._bind(self._user, "GetCursorPos", wintypes.BOOL, ctypes.POINTER(wintypes.POINT))
        self._bind(self._user, "GetAsyncKeyState", ctypes.c_short, integer)
        self._bind(self._user, "SetWindowPos", wintypes.BOOL, handle, handle, integer, integer, integer, integer, wintypes.UINT)
        self._bind(self._user, "GetWindowLongW", wintypes.LONG, handle, integer)
        self._bind(self._user, "SetWindowLongW", wintypes.LONG, handle, integer, wintypes.LONG)
        self._bind(self._user, "SetWindowRgn", integer, handle, wintypes.HRGN, wintypes.BOOL)
        self._bind(self._user, "MonitorFromPoint", wintypes.HMONITOR, wintypes.POINT, wintypes.DWORD)
        self._bind(self._user, "MonitorFromWindow", wintypes.HMONITOR, handle, wintypes.DWORD)
        self._bind(self._user, "GetMonitorInfoW", wintypes.BOOL, wintypes.HMONITOR, ctypes.POINTER(MonitorInfo))
        self._bind(self._gdi, "CreateRoundRectRgn", wintypes.HRGN, integer, integer, integer, integer, integer, integer)
        self._bind(self._gdi, "DeleteObject", wintypes.BOOL, wintypes.HGDIOBJ)

    @staticmethod
    def _bind(library, name, result, *args):
        function = getattr(library, name)
        function.argtypes, function.restype = list(args), result

    def _load_position(self):
        try:
            if self.position_file.stat().st_size <= 128:
                value = json.loads(self.position_file.read_text(encoding="utf-8"))
                if isinstance(value, list) and len(value) == 2 and all(type(item) is int and abs(item) <= 100000 for item in value):
                    return tuple(value)
        except (OSError, ValueError):
            pass
        return None

    def _save_position(self):
        try:
            self.position_file.parent.mkdir(parents=True, exist_ok=True)
            pending = self.position_file.with_suffix(".tmp")
            pending.write_text(json.dumps(self.position), encoding="utf-8")
            pending.replace(self.position_file)
        except OSError:
            pass

    @staticmethod
    def _hwnd(window):
        return window.native.Handle.ToInt64()

    def _configure(self, hwnd, width, height):
        if self._configured != hwnd:
            style = self._user.GetWindowLongW(hwnd, -20)
            # Hide from Alt+Tab and keep the active app's keyboard focus.
            self._user.SetWindowLongW(hwnd, -20, (style | 0x08000080) & ~0x00040000)
            self._configured = hwnd
            self._previous_size = None
        if self._previous_size != (width, height):
            corner = max(20, height // 2)
            region = self._gdi.CreateRoundRectRgn(0, 0, width + 1, height + 1, corner, corner)
            if region and not self._user.SetWindowRgn(hwnd, region, True):
                self._gdi.DeleteObject(region)
            self._previous_size = (width, height)

    def _work_area(self, monitor):
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if not self._user.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return (info.work.left, info.work.top, info.work.right, info.work.bottom)

    def _rect(self, hwnd):
        rect = wintypes.RECT()
        return rect if self._user.GetWindowRect(hwnd, ctypes.byref(rect)) else None

    def _cursor(self):
        point = wintypes.POINT()
        return point if self._user.GetCursorPos(ctypes.byref(point)) else None

    def begin_drag(self):
        if not self.visible or not self._user.GetAsyncKeyState(1) & 0x8000:
            return
        point, rect = self._cursor(), self._rect(self._hwnd(self.view))
        if point and rect and rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom:
            self._drag = (point.x - rect.left, point.y - rect.top)

    def watch(self, unlocked):
        if not self.view.events.loaded.is_set() or not self.main.events.shown.is_set():
            return False
        hwnd, main = self._hwnd(self.view), self._hwnd(self.main)
        foreground = self._user.GetForegroundWindow() if unlocked and self.enabled else None
        visible = bool(foreground and self._user.GetAncestor(foreground, 3) != main and foreground != hwnd)
        rect = self._rect(hwnd)
        if not rect:
            return False
        width, height = rect.right - rect.left, rect.bottom - rect.top
        self._configure(hwnd, width, height)
        if not visible:
            if self.visible:
                self._user.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0097)
                self.visible = False
            self._drag = None
            return False

        held = bool(self._drag and self._user.GetAsyncKeyState(1) & 0x8000)
        if self._drag and not held:
            self._drag = None
            self._save_position()
        point = self._cursor() if held else None
        if point:
            monitor = self._user.MonitorFromPoint(point, 2)
            position = (point.x - self._drag[0], point.y - self._drag[1])
        elif self.position is not None:
            position = self.position
            monitor = self._user.MonitorFromPoint(wintypes.POINT(*position), 2)
        else:
            position = None
            monitor = self._user.MonitorFromWindow(foreground, 2)
        work = self._work_area(monitor)
        if work:
            x, y = position or (work[2] - width - 24, work[3] - height - 28)
            self.position = clamp_position(x, y, width, height, work)
            if not self.visible or self.position != (rect.left, rect.top):
                self.visible = bool(self._user.SetWindowPos(hwnd, -1, *self.position, 0, 0, 0x0051))
        return held

    def restore_main(self):
        # Only called after the user clicks a control on the pet.
        if self._user.IsIconic(self._hwnd(self.main)):
            self.main.restore()
        self.main.show()
