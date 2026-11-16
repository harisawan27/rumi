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
from .contracts import RequestIdentity, ActionRequest, ResumeSaveRequest
from .commands import parse_command, Clarification
from .executor import Executor
from .operator import PlanError, WindowOperator, window_instruction
from .resume import ResumeWorkflow, resume_instruction
from .windows import require_unlocked_desktop, launch_app
from .workflow import Workflow, workflow_instruction
from .workspace import Workspace, WorkspaceError


class NativeCommand(RequestIdentity):
    text: str = Field(min_length=1, max_length=18000)


class NativeRuntime:
    def __init__(self, journal, desktop_check=require_unlocked_desktop, launcher=launch_app,
                 clock=time.monotonic, wall_clock=time.time, operator_factory=None, research=None, polish_resume=None):
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
        self._operator_factory = operator_factory
        self._operator = None
        self._folder_enabled = False
        self._workflow = None
        self._resume = None
        self._research = research
        self._polish_resume = polish_resume

    @property
    def generation(self):
        with self._state:
            return self._generation

    def stop(self):
        # Must never wait for the executing action or a native picker/confirmation.
        with self._state:
            self._generation += 1
            self._session = self._credential = self._last_file = None
            self._operator = None
            self._workflow = None
            self._resume = None
            self._folder_enabled = False
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
                self._folder_enabled = True
                self._workflow = Workflow(self._clock)
                self._resume = ResumeWorkflow(self._clock)
                self._session, self._credential = secrets.token_hex(16), secrets.token_urlsafe(32)
                self._expires = self._clock() + 900
                self._last_file = None
                self._generation += 1
                return self.status()
        finally:
            self._operation.release()

    def enable_operator(self, expected_generation):
        if not self._operator_factory or not self._operation.acquire(blocking=False):
            raise WorkspaceError("windows_control_unavailable")
        try:
            adapter = self._operator_factory()
            with self._state:
                self._desktop_check()
                if expected_generation != self._generation:
                    raise WorkspaceError("authorization_cancelled")
                if self._credential:
                    self._authorize(self._credential, self._session)
                    if self._workflow:
                        self._workflow.cancel()
                    if self._resume:
                        self._resume.cancel()
                else:
                    self._session = secrets.token_hex(16)
                    self._credential = secrets.token_urlsafe(32)
                    self._expires = self._clock() + 900
                self._operator = WindowOperator(adapter, self._clock)
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
            return {"active": bool(self._credential), "session_id": self._session, "resume_ai": self._polish_resume is not None,
                    "workspace": str(self._executor.workspace.root) if self._folder_enabled else None,
                    "windows_control": self._operator is not None,
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
                executor = self._executor if self._folder_enabled else None
                last_file, operator, workflow = self._last_file, self._operator, self._workflow
                resume = self._resume
            if not self._wall_clock() < request.expires_at <= self._wall_clock() + 120:
                raise WorkspaceError("expired")
            resume_step = resume_instruction(request.text)
            if resume_step:
                if workflow:
                    workflow.cancel()
                if operator:
                    operator.pending = operator.choice = None
                return self._resume_command(request, resume_step, resume, executor, credential)
            if resume:
                resume.cancel()
            try:
                compound = workflow_instruction(request.text)
            except PlanError as exc:
                if workflow:
                    workflow.cancel()
                return {"request_id": request.request_id, "state": "clarification", "message": str(exc)}
            if compound:
                return self._workflow_command(request, compound, workflow, operator, executor, credential)
            if workflow:
                workflow.cancel()
            instruction = window_instruction(request.text)
            if instruction:
                return self._window_command(request, instruction, operator, credential)
            try:
                action = parse_command(request.text, last_file)
            except Clarification as exc:
                self._authorize(credential, request.session_id)
                return {"request_id": request.request_id, "state": "clarification", "message": str(exc)}
            if executor is None:
                if action.operation == "open_app":
                    try:
                        operator.claim(request.request_id)
                    except PlanError as exc:
                        return {"request_id": request.request_id, "state": "clarification", "message": str(exc)}
                    self._launcher(action.app, lambda: self._authorize(credential, request.session_id))
                    self._authorize(credential, request.session_id)
                    return {"request_id": request.request_id, "state": "dispatched", "operation": "open_app"}
                return {"request_id": request.request_id, "state": "clarification",
                        "message": "Choose a folder to read, list or create its files."}
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

    def _resume_command(self, request, instruction, resume, executor, credential):
        receipt = {"request_id": request.request_id, "operation": "resume_workflow"}
        if not resume or not executor:
            return {**receipt, "state": "clarification", "message": "Choose a workspace folder before starting your résumé."}

        def guard():
            self._authorize(credential, request.session_id)
            if self._wall_clock() >= request.expires_at:
                raise WorkspaceError("expired")

        def write(action):
            guard()
            return executor.execute(ResumeSaveRequest(**request.model_dump(exclude={"text"}), action=action), credential)

        state, message, result = resume.run(request.request_id, instruction, executor.workspace.root,
                                           write, self._polish_resume, guard)
        guard()
        return {**receipt, "state": state, "message": message, "result": result}

    def _window_command(self, request, instruction, operator, credential):
        deadline = self._clock() + 14

        def guard():
            self._authorize(credential, request.session_id)
            if self._clock() >= deadline or self._wall_clock() >= request.expires_at:
                raise PlanError("The Windows request ran out of time.")

        if operator is None:
            state, message = "clarification", "Enable Windows control in Rumi first."
        else:
            try:
                state, message = operator.run(request.request_id, instruction, guard)
            except PlanError as exc:
                state, message = "clarification", str(exc)
            self._authorize(credential, request.session_id)
        receipt = {"request_id": request.request_id, "operation": "window_control", "state": state, "message": message}
        if operator and operator.task_sheet:
            receipt["result"] = {"task": operator.task_sheet}
        return receipt

    def _workflow_command(self, request, instruction, workflow, operator, executor, credential):
        receipt = {"request_id": request.request_id, "operation": "note_workflow"}
        if not workflow or not executor:
            return {**receipt, "state": "clarification", "message": "Choose a folder before starting a note workflow."}
        if operator:
            operator.pending = operator.choice = None
        deadline = self._clock() + 12

        def guard():
            self._authorize(credential, request.session_id)
            if self._clock() >= deadline or self._wall_clock() >= request.expires_at:
                raise PlanError("This workflow ran out of time. Ask again.")

        def document(query, check):
            if not operator:
                raise PlanError("Enable Windows control, then bring the document to the front.")
            target = operator.adapter.foreground(check)
            found = operator.adapter.find_document_text(target, query, check)
            return target.title[:120], found

        def write(action):
            guard()
            response = executor.execute(ActionRequest(**request.model_dump(exclude={"text"}), action=action), credential)
            with self._state:
                self._authorize(credential, request.session_id)
                if response["state"] == "succeeded" and not response.get("replayed"):
                    self._last_file = action.name
            return response

        try:
            state, message, result = workflow.run(request.request_id, instruction, document, self._research, write, guard)
        except PlanError as exc:
            state, message, result = "clarification", str(exc), {}
        self._authorize(credential, request.session_id)
        return {**receipt, "state": state, "message": message, "result": result}

    def close(self):
        self.stop()
        with self._operation:
            if self._executor:
                self._executor.close()
                self._executor = None
