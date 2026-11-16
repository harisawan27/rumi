"""Windows UI Automation adapter. No global key injection or coordinate guessing."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
from pathlib import Path
import re
import time

from src.desktop.operator import PlanError, Unverified
from src.desktop.planner import SEARCH_FIELDS


BLOCKED_APPS = {
    "cmd", "powershell", "pwsh", "wt", "windowsterminal", "openconsole", "conhost",
    "regedit", "taskmgr", "mmc", "control", "systemsettings", "securityhealthsystray",
    "sechealthui", "credentialuibroker", "consent", "lockapp", "logonui", "winlogon",
    "rundll32", "msiexec", "wscript", "cscript", "chatgpt", "codex", "rumidesktop",
}
PROTECTED_CONTROL = re.compile(
    r"\b(?:password|passcode|credential|verification code|address bar|terminal|"
    r"command prompt|powershell|run|execute|delete|remove|uninstall|send|submit|"
    r"purchase|buy|pay|checkout|sign in|log in|shutdown|shut down|restart)\b", re.I
)
CONTROL_TYPES = {"button", "splitbutton", "menuitem", "tabitem", "listitem", "treeitem",
                 "combobox", "checkbox", "radiobutton", "edit", "hyperlink"}


@dataclass(frozen=True)
class Window:
    handle: int
    pid: int
    started: int
    title: str


def normalized(label):
    return " ".join(label.replace("&", "").casefold().split())


class WindowsControls:
    def __init__(self, own_process=None):
        self.own_process = os.getpid() if own_process is None else own_process
        self._user = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user.GetForegroundWindow.restype = wintypes.HWND
        self._user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self._user.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        self._user.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        for name in ("IsWindowVisible", "IsIconic", "SetForegroundWindow"):
            getattr(self._user, name).argtypes = (wintypes.HWND,)
        self._enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self._user.EnumWindows.argtypes = (self._enum_callback, wintypes.LPARAM)
        self._kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self._kernel.OpenProcess.restype = wintypes.HANDLE
        self._kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        self._kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        self._uia = None

    def _automation(self):
        if self._uia is None:
            import clr
            root = ctypes.create_unicode_buffer(32768)
            if not self._kernel.GetWindowsDirectoryW(root, len(root)):
                raise PlanError("Windows accessibility is unavailable.")
            framework = Path(root.value) / "Microsoft.NET/Framework64/v4.0.30319/WPF"
            for name in ("UIAutomationTypes", "UIAutomationClient"):
                clr.AddReference(str(framework / f"{name}.dll"))
            from System import IntPtr
            from System.Windows import Automation
            self._uia = IntPtr, Automation
        return self._uia

    def _identify(self, handle):
        if not handle or not self._user.IsWindowVisible(handle) or self._user.IsIconic(handle):
            return None
        title, kind = ctypes.create_unicode_buffer(241), ctypes.create_unicode_buffer(128)
        if not self._user.GetWindowTextW(handle, title, len(title)):
            return None
        self._user.GetClassNameW(handle, kind, len(kind))
        if kind.value in {"Progman", "WorkerW", "Shell_TrayWnd", "ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"}:
            return None
        pid = wintypes.DWORD()
        self._user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if not pid.value or pid.value == self.own_process:
            return None
        process = self._kernel.OpenProcess(0x1000, False, pid.value)
        if not process:
            return None
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not self._kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                return None
            if Path(path.value).stem.casefold() in BLOCKED_APPS:
                return None
            created = wintypes.FILETIME()
            other = [wintypes.FILETIME() for _ in range(3)]
            if not self._kernel.GetProcessTimes(process, ctypes.byref(created), *(ctypes.byref(item) for item in other)):
                return None
            started = (created.dwHighDateTime << 32) | created.dwLowDateTime
            return Window(handle, pid.value, started, " ".join(title.value.split()))
        finally:
            self._kernel.CloseHandle(process)

    def _same_window(self, target):
        current = self._identify(target.handle)
        return current is not None and (current.pid, current.started) == (target.pid, target.started)

    def windows(self, guard):
        guard()
        results = []

        @self._enum_callback
        def append(handle, _):
            window = self._identify(handle)
            if window and window.title:
                results.append(window)
            return len(results) < 10

        self._user.EnumWindows(append, 0)
        guard()
        return results

    def foreground(self, guard):
        guard()
        target = self._identify(self._user.GetForegroundWindow())
        if not target:
            raise PlanError("Bring a supported app window to the front, or say list windows and then focus its number.")
        return target

    def validate_target(self, target, guard):
        guard()
        if self._user.GetForegroundWindow() != target.handle or not self._same_window(target):
            raise PlanError("The selected window changed. Bring it to the front and prepare a new plan.")

    def focus(self, target, guard):
        guard()
        if not self._same_window(target):
            raise PlanError("That window is no longer available. List windows again.")
        guard()
        self._user.SetForegroundWindow(target.handle)
        until = time.monotonic() + 0.6
        while self._user.GetForegroundWindow() != target.handle and time.monotonic() < until:
            guard()
            time.sleep(0.05)
        self.validate_target(target, guard)

    def _elements(self, target, guard):
        self.validate_target(target, guard)
        pointer, automation = self._automation()
        walker = automation.TreeWalker.ControlViewWalker
        root = automation.AutomationElement.FromHandle(pointer(target.handle))
        # Iterate a single pinned tree, including controls inside nested panes.
        parents = []
        node = walker.GetFirstChild(root)
        visited = 0
        while node is not None:
            visited += 1
            if visited > 400:
                raise PlanError("That window exposes too many controls. Open a smaller pane first.")
            if visited % 20 == 1:
                self.validate_target(target, guard)
            info = node.Current
            if info.ProcessId == target.pid and not info.IsOffscreen:
                yield node, info
            child = walker.GetFirstChild(node)
            if child is not None:
                parents.append(node)
                node = child
            else:
                node = walker.GetNextSibling(node)
                while node is None and parents:
                    node = walker.GetNextSibling(parents.pop())
        self.validate_target(target, guard)

    def _nodes(self, target, guard):
        for node, info in self._elements(target, guard):
            if info.IsPassword:
                continue
            label = str(info.Name or "").strip()
            kind = str(info.ControlType.ProgrammaticName).split(".")[-1].casefold()
            if (label and len(label) <= 120 and all(ord(char) >= 32 for char in label)
                    and kind in CONTROL_TYPES and not PROTECTED_CONTROL.search(label)):
                yield node, label, kind

    def controls(self, target, guard):
        return [(label, kind) for node, label, kind in self._nodes(target, guard) if node.Current.IsEnabled]

    def document(self, target, guard):
        _, automation = self._automation()
        documents = []
        for node, info in self._elements(target, guard):
            if info.ControlType != automation.ControlType.Document or info.IsPassword:
                continue
            supported, pattern = node.TryGetCurrentPattern(automation.TextPattern.Pattern)
            if supported:
                documents.append(pattern)
        if len(documents) != 1:
            raise PlanError("Open one document whose app exposes readable text, then ask me again.")
        return documents[0]

    def find_document_text(self, target, words, guard):
        document = self.document(target, guard)
        self.validate_target(target, guard)
        found = document.DocumentRange.FindText(words, False, True)
        self.validate_target(target, guard)
        return found is not None

    def reveal_search(self, target, label, guard):
        from src.desktop.operator import Step

        def search_visible():
            return any(kind == "edit" and name.casefold() in SEARCH_FIELDS
                       for name, kind in self.controls(target, guard))

        self.perform(target, Step("press", label, "search field"), guard, expected=search_visible)

    def describe(self, target, guard):
        labels = []
        for _, label, kind in self._nodes(target, guard):
            labels.append(f"{label} ({kind})")
            if len(labels) >= 20:
                labels.append("Showing the first 20 named controls.")
                break
        self.validate_target(target, guard)
        return labels

    def _find(self, target, label, guard, optional=False):
        result = None
        for node, name, _ in self._nodes(target, guard):
            if normalized(name) != normalized(label):
                continue
            if result is not None:
                raise PlanError(f'More than one control is named "{label}". Open the right pane first.')
            result = node
        if result is None and not optional:
            raise PlanError(f'I could not find "{label}". Say inspect window to hear the control names.')
        return result

    @staticmethod
    def _pattern(node, pattern, label):
        supported, result = node.TryGetCurrentPattern(pattern)
        if not supported:
            raise PlanError(f'"{label}" does not support that action in Windows accessibility.')
        return result

    def perform(self, target, step, guard, expected=None):
        if PROTECTED_CONTROL.search(step.label):
            raise PlanError("This control needs your direct interaction.")
        _, automation = self._automation()
        node = self._find(target, step.label, guard)
        info = node.Current
        if not info.IsEnabled or info.IsOffscreen or info.IsPassword:
            raise PlanError(f'"{step.label}" is unavailable.')
        if step.verb == "press":
            pattern = self._pattern(node, automation.InvokePattern.Pattern, step.label)
            postcondition = expected or (lambda: self._find(target, step.value, guard, optional=True) is not None)
            if postcondition():
                raise PlanError(f'"{step.value}" is already visible. Choose a control that will appear after the press.')
            apply = pattern.Invoke
        elif step.verb == "set":
            if info.ControlType != automation.ControlType.Edit:
                raise PlanError("Set works only with an editable text field.")
            pattern = self._pattern(node, automation.ValuePattern.Pattern, step.label)
            if pattern.Current.IsReadOnly:
                raise PlanError("The field is read-only.")
            apply = lambda: pattern.SetValue(step.value)
            postcondition = lambda: str(pattern.Current.Value) == step.value
        elif step.verb == "expand":
            pattern = self._pattern(node, automation.ExpandCollapsePattern.Pattern, step.label)
            apply = pattern.Expand
            postcondition = lambda: pattern.Current.ExpandCollapseState == automation.ExpandCollapseState.Expanded
        elif step.verb == "select":
            pattern = self._pattern(node, automation.SelectionItemPattern.Pattern, step.label)
            apply = pattern.Select
            postcondition = lambda: pattern.Current.IsSelected
        else:
            pattern = self._pattern(node, automation.TogglePattern.Pattern, step.label)
            expected = automation.ToggleState.On if step.verb == "check" else automation.ToggleState.Off
            if pattern.Current.ToggleState == automation.ToggleState.Indeterminate:
                raise PlanError("The control is in a mixed state and needs direct interaction.")
            apply = pattern.Toggle
            postcondition = lambda: pattern.Current.ToggleState == expected
        self.validate_target(target, guard)
        if step.verb != "press" and postcondition():
            return  # The requested state already holds.
        self.validate_target(target, guard)
        # A provider can return after dispatch or raise after making a change.
        # Do not invoke it twice. Stop can still revoke the grant while it runs.
        try:
            apply()
            until = time.monotonic() + 2
            while True:
                self.validate_target(target, guard)
                if postcondition():
                    guard()
                    return
                if time.monotonic() >= until:
                    break
                time.sleep(0.1)
        except Exception as exc:
            raise Unverified(f'The result of {step.verb} "{step.label}" could not be confirmed.') from exc
        raise Unverified(f'The result of {step.verb} "{step.label}" could not be confirmed.')
