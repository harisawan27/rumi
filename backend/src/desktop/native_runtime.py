"""Local Windows-session grants. Separate from Firebase/face-authenticated HTTP mode.

Only the native host calls enable after its own folder picker and consent dialog.
The renderer cannot supply a workspace path or acquire the host credential.
"""
import hmac
import secrets
import threading
import time
from pathlib import Path
from pydantic import Field, ValidationError
from .contracts import RequestIdentity, ActionRequest
from .commands import parse_command, Clarification
from .executor import Executor
from .windows import require_unlocked_desktop, launch_app
from .workspace import Workspace, WorkspaceError


class NativeCommand(RequestIdentity):
    text: str = Field(min_length=1, max_length=18000)


class NativeRuntime:
    def __init__(self, journal, desktop_check=require_unlocked_desktop, launcher=launch_app,
                 clock=time.monotonic, wall_clock=time.time):
        self._journal = Path(journal)
        self._desktop_check, self._launcher = desktop_check, launcher
        self._clock, self._wall_clock = clock, wall_clock
        self._state = threading.RLock()
        self._operation = threading.Lock()
        self._executor = None
        self._session = None
        self._credential = None
        self._expires = 0
        self._last_file = None
        self._generation = 0

    @property
    def generation(self):
        with self._state:
            return self._generation

    def stop(self):
        # Must never wait for the executing action or a native picker/confirmation.
        with self._state:
            self._generation += 1
            self._session = self._credential = self._last_file = None
            self._expires = 0
            if self._executor:
                self._executor.stop()
        return {"active": False, "workspace": None, "session_id": None}

    def _authorize(self, credential, session):
        with self._state:
            try:
                self._desktop_check()
                if (not self._credential or not isinstance(credential, str)
                        or not hmac.compare_digest(credential, self._credential)
                        or session != self._session or self._clock() >= self._expires):
                    raise WorkspaceError("local_permission_required")
            except Exception:
                self.stop()
                raise WorkspaceError("local_permission_required")

    def enable(self, root, expected_generation):
        if not self._operation.acquire(blocking=False):
            raise WorkspaceError("busy")
        try:
            workspace = Workspace(root)
            with workspace.pinned():
                self._desktop_check()
            with self._state:
                if expected_generation != self._generation:
                    raise WorkspaceError("authorization_cancelled")
                if self._executor:
                    self._executor.close()
                self._journal.parent.mkdir(parents=True, exist_ok=True)
                self._executor = Executor(workspace, self._journal, self._authorize,
                    clock=self._wall_clock, launcher=self._launcher, desktop_check=self._desktop_check)
                self._session, self._credential = secrets.token_hex(16), secrets.token_urlsafe(32)
                self._expires = self._clock() + 900
                self._last_file = None
                self._generation += 1
                return self.status()
        finally:
            self._operation.release()

    def status(self):
        with self._state:
            if self._credential:
                try:
                    self._authorize(self._credential, self._session)
                except WorkspaceError:
                    pass
            return {"active": bool(self._credential), "session_id": self._session,
                    "workspace": str(self._executor.workspace.root) if self._credential else None,
                    "seconds_remaining": max(0, int(self._expires - self._clock())) if self._credential else 0}

    def command(self, raw):
        try:
            request = NativeCommand.model_validate(raw)
        except ValidationError:
            return {"state": "blocked", "message": "Use one supported command with a fresh request ID."}
        if not self._operation.acquire(blocking=False):
            return {"state": "blocked", "message": "Another action is still running. Nothing was queued."}
        try:
            with self._state:
                credential = self._credential
                self._authorize(credential, request.session_id)
                executor, last_file = self._executor, self._last_file
            if not self._wall_clock() < request.expires_at <= self._wall_clock() + 120:
                raise WorkspaceError("expired")
            try:
                action = parse_command(request.text, last_file)
            except Clarification as exc:
                self._authorize(credential, request.session_id)
                return {"request_id": request.request_id, "state": "clarification", "message": str(exc)}
            result = executor.execute(ActionRequest(**request.model_dump(exclude={"text"}), action=action), credential)
            with self._state:
                self._authorize(credential, request.session_id)
                if result["state"] == "succeeded" and not result["replayed"] and action.operation in ("read_text", "create_text"):
                    self._last_file = action.name
                return {**result, "operation": action.operation}
        except WorkspaceError as exc:
            return {"request_id": request.request_id, "state": "blocked", "message": exc.code}
        except Exception:
            self.stop()
            return {"request_id": request.request_id, "state": "uncertain",
                    "message": "Check the selected folder or app before retrying. Local permission was cleared."}
        finally:
            self._operation.release()

    def close(self):
        self.stop()
        with self._operation:
            if self._executor:
                self._executor.close()
                self._executor = None
