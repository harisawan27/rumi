"""Open one workspace-verified document through Microsoft Word automation."""
import ctypes
import os
import subprocess
import time
from pathlib import Path

from src.desktop.workspace import WorkspaceError


# Static automation. The verified filename is data in the child environment.
_OPEN = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$path = $env:RUMI_WORD_DOCUMENT
try { $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application') }
catch {
    try { $word = New-Object -ComObject Word.Application }
    catch { exit 3 }
}
$doc = $null
foreach ($item in $word.Documents) {
    if ([string]::Equals($item.FullName, $path, [StringComparison]::OrdinalIgnoreCase)) { $doc = $item; break }
}
if ($null -eq $doc) {
    $security = $word.AutomationSecurity
    try {
        $word.AutomationSecurity = 3
        $doc = $word.Documents.Open($path, $false, $false, $false)
    } finally { $word.AutomationSecurity = $security }
}
$word.Visible = $true
$doc.Activate()
[Console]::Write($doc.FullName)
"""


def open_word(path, check):
    windows = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetWindowsDirectoryW(windows, len(windows)):
        raise WorkspaceError("word_unavailable")
    executable = Path(windows.value) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    check()
    try:
        with subprocess.Popen([str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _OPEN],
                              env={**os.environ, "RUMI_WORD_DOCUMENT": str(path)}, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW) as child:
            deadline = time.monotonic() + 28
            try:
                while True:
                    check()
                    if time.monotonic() >= deadline:
                        raise WorkspaceError("word_unverified")
                    try:
                        output, _ = child.communicate(timeout=.2)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                if child.poll() is None:
                    child.kill()
            check()
            if child.returncode == 3:
                raise WorkspaceError("word_unavailable")
            if child.returncode != 0 or not output:
                raise WorkspaceError("word_unverified")
            return output.decode("utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise WorkspaceError("word_unverified") from exc
