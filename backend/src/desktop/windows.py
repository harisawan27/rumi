"""Fixed Windows application entry points; never execute a model-supplied command."""
import os
import subprocess
from pathlib import Path
from .workspace import WorkspaceError


def require_unlocked_desktop():
    if os.name != "nt":
        raise WorkspaceError("windows_required")
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user.OpenInputDesktop.restype = wintypes.HANDLE
    user.CloseDesktop.argtypes = [wintypes.HANDLE]
    user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    handle = user.OpenInputDesktop(0, False, 1)
    if not handle:
        raise WorkspaceError("desktop_locked")
    try:
        name = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD()
        if not user.GetUserObjectInformationW(handle, 2, name, ctypes.sizeof(name), ctypes.byref(needed)) or name.value != "Default":
            raise WorkspaceError("desktop_locked")
    finally:
        user.CloseDesktop(handle)


def launch_app(app, check):
    if os.name != "nt":
        raise WorkspaceError("windows_required")
    # Resolve system location through Windows, not PATH or model-controlled arguments.
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise WorkspaceError("windows_unavailable")
    root = Path(buffer.value)
    executable = {"notepad": root / "System32/notepad.exe", "explorer": root / "explorer.exe"}.get(app)
    if executable is None or not executable.is_file():
        raise WorkspaceError("unsupported_app")
    check()
    subprocess.Popen([str(executable)], shell=False, close_fds=True)
    # Process launch is evidence only of dispatch, not window readiness or focus.
    return {"dispatched": True, "verified_window": False}
