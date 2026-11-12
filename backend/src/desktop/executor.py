"""Serial executor with durable duplicate suppression and model-independent stop."""
import hashlib
import json
import sqlite3
import threading
import time
from .contracts import ActionRequest
from .workspace import WorkspaceError
from .windows import launch_app


class Executor:
    def __init__(self, workspace, journal, authorize, clock=time.time, launcher=launch_app, desktop_check=lambda: None):
        self.workspace, self.authorize, self.clock = workspace, authorize, clock
        self.launcher = launcher
        self.desktop_check = desktop_check
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.db = sqlite3.connect(str(journal), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL)")
        self.db.commit()

    def stop(self):
        self.stopped.set()

    def resume(self):
        # Local operator only; never automatically resume an interrupted request.
        if not self.lock.acquire(blocking=False):
            raise WorkspaceError("busy")
        try:
            self.stopped.clear()
        finally:
            self.lock.release()

    def close(self):
        self.stop()
        with self.lock:
            self.db.close()

    def fingerprint(self, request):
        # A receipt from a different selected folder must never count as success
        # for this workspace after restarting the agent with new arguments.
        scope = str(self.workspace.root).casefold()
        return hashlib.sha256((scope + "\n" + request.model_dump_json()).encode()).hexdigest()

    def execute(self, raw, credential):
        request = ActionRequest.model_validate(raw)
        fingerprint = self.fingerprint(request)
        if not self.lock.acquire(blocking=False):
            raise WorkspaceError("busy")
        try:
            def local_check():
                self.desktop_check()
                if self.stopped.is_set():
                    raise WorkspaceError("stopped")
                if not self.clock() < request.expires_at <= self.clock() + 120:
                    raise WorkspaceError("expired")
            def check():
                local_check()
                self.authorize(credential, request.session_id)
                local_check()
            check()
            previous = self.db.execute("SELECT fingerprint,state,result FROM receipts WHERE id=?", (request.request_id,)).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise WorkspaceError("request_id_reused")
                # Private file contents are deliberately absent from the journal.
                return {"request_id": request.request_id, "state": previous[1] if previous[1] != "running" else "uncertain",
                        "replayed": True, "result": json.loads(previous[2])}
            self.db.execute("INSERT INTO receipts VALUES (?,?,?,?)", (request.request_id, fingerprint, "running", "{}"))
            self.db.commit()
            state, result, public = "failed", {}, {}
            try:
                action = request.action
                if action.operation == "create_text":
                    result = self.workspace.create_text(action.name, action.text, check)
                elif action.operation == "read_text":
                    public = self.workspace.read_text(action.name, check)
                elif action.operation == "open_app":
                    result = self.launcher(action.app, check)
                else:
                    public = self.workspace.list_files(local_check)
                state = "dispatched" if action.operation == "open_app" else "succeeded"
            except FileExistsError:
                result = {"reason": "already_exists"}
            except (WorkspaceError, OSError) as exc:
                result = {"reason": exc.code if isinstance(exc, WorkspaceError) else "filesystem_unavailable"}
                # A create may have committed before failure. Never call it cancelled/not written.
                if request.action.operation in ("create_text", "open_app"):
                    state = "uncertain"
            except Exception:
                result = {"reason": "authorization_or_execution_failed"}
                state = "uncertain" if request.action.operation in ("create_text", "open_app") else "failed"
            self.db.execute("UPDATE receipts SET state=?, result=? WHERE id=?", (state, json.dumps(result), request.request_id))
            self.db.commit()
            check()  # Suppress delivery on authorization loss; receipt remains honest.
            return {"request_id": request.request_id, "state": state, "replayed": False, "result": {**result, **public}}
        finally:
            self.lock.release()
