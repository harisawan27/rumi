"""Bounded text-file adapter, no recursive traversal or overwrites."""
import ctypes
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from .contracts import NamedFile

MAX_BYTES = 64000


class WorkspaceError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def regular(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise WorkspaceError("unsafe_file")
    return info


class Workspace:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if not self.root.is_dir() or self.root == Path(self.root.anchor):
            raise WorkspaceError("select_workspace_folder")
        self._validate_root()

    def _validate_root(self):
        for path in [*reversed(self.root.parents), self.root]:
            info = path.lstat()
            if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise WorkspaceError("unsafe_workspace")
        if os.name == "nt" and (not self.root.drive or self.root.drive.startswith("\\")):
            raise WorkspaceError("local_workspace_required")

    @contextmanager
    def pinned(self):
        """Keep Windows ancestors from being replaced while a file is accessed.

        Non-Windows execution is for temporary-fixture tests only. The launcher
        refuses non-Windows hosts. Same-user malicious processes are not sandboxed.
        """
        handles = []
        kernel = None
        try:
            if os.name == "nt":
                from ctypes import wintypes
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
                kernel.CreateFileW.restype = wintypes.HANDLE
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                for path in [*reversed(self.root.parents), self.root]:
                    handle = kernel.CreateFileW(str(path), 0x80, 3, None, 3, 0x02200000, None)
                    if handle == ctypes.c_void_p(-1).value:
                        raise WorkspaceError("workspace_busy")
                    handles.append(handle)
            self._validate_root()
            yield
        finally:
            if kernel:
                for handle in reversed(handles):
                    kernel.CloseHandle(handle)

    def path(self, name):
        return self.root / NamedFile(name=name).name

    def list_files(self, check):
        with self.pinned():
            check()
            names = []
            # Bounded enumeration, not a recursive home-directory index.
            with os.scandir(self.root) as entries:
                for index, entry in enumerate(entries):
                    if index >= 500:
                        return {"names": sorted(names), "truncated": True}
                    check()
                    try:
                        path = self.path(entry.name)
                        regular(path)
                        names.append(entry.name)
                    except (ValueError, OSError, WorkspaceError):
                        continue
            return {"names": sorted(names), "truncated": False}

    def read_text(self, name, check):
        with self.pinned():
            path = self.path(name)
            before = regular(path)
            if before.st_size > MAX_BYTES:
                raise WorkspaceError("file_too_large")
            check()
            with path.open("rb") as stream:
                after = os.fstat(stream.fileno())
                if (after.st_ino, after.st_dev) != (before.st_ino, before.st_dev) or after.st_nlink != 1:
                    raise WorkspaceError("file_changed")
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise WorkspaceError("file_too_large")
            check()
            try:
                return {"text": raw.decode("utf-8"), "bytes": len(raw)}
            except UnicodeDecodeError as exc:
                raise WorkspaceError("not_utf8") from exc

    def create_text(self, name, text, check):
        raw = text.encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise WorkspaceError("file_too_large")
        with self.pinned():
            path = self.path(name)
            check()
            # Atomic no-overwrite creation. A crash can leave a partial file;
            # the journal marks that request uncertain and never retries it.
            with path.open("x+b") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
                # Verify the bounded contents and identity of the file we created,
                # without reopening a path that another process could replace.
                stream.seek(0)
                if stream.read(MAX_BYTES + 1) != raw:
                    raise WorkspaceError("verification_failed")
                created, current = os.fstat(stream.fileno()), regular(path)
                if (created.st_ino, created.st_dev) != (current.st_ino, current.st_dev):
                    raise WorkspaceError("file_changed")
            return {"bytes": len(raw)}
