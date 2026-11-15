"""Run the Windows operator against a disposable app with no Rumi-specific controls."""
import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src.desktop.native_runtime import NativeRuntime
from check_speech import recognize_samples
from windows_operator import WindowsControls


def fixture(title):
    import clr
    ctypes.windll.ole32.CoInitializeEx(None, 2)
    root = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetWindowsDirectoryW(root, len(root))
    framework = Path(root.value) / "Microsoft.NET/Framework64/v4.0.30319"
    clr.AddReference(str(framework / "WPF/PresentationFramework.dll"))
    clr.AddReference(str(framework / "WPF/PresentationCore.dll"))
    clr.AddReference(str(framework / "WPF/WindowsBase.dll"))
    from System import TimeSpan
    from System.Windows import Application, Visibility, Window
    from System.Windows.Automation import AutomationProperties
    from System.Windows.Controls import Button, CheckBox, StackPanel, TextBox
    from System.Windows.Threading import DispatcherTimer

    window = Window()
    window.Title = title
    window.Width, window.Height = 380, 200
    window.ShowInTaskbar = False
    panel = StackPanel()
    window.Content = panel
    field = TextBox()
    field.Visibility = Visibility.Collapsed
    AutomationProperties.SetName(field, "Search query")
    button = Button()
    button.Content = "Show search"
    button.Click += lambda *_: setattr(field, "Visibility", Visibility.Visible)
    checkbox = CheckBox()
    checkbox.Content = "Match case"
    panel.Children.Add(button)
    panel.Children.Add(field)
    panel.Children.Add(checkbox)
    timer = DispatcherTimer()
    timer.Interval = TimeSpan.FromSeconds(25)
    timer.Tick += lambda *_: window.Close()
    timer.Start()
    Application().Run(window)


def main():
    samples = recognize_samples(("Rumi inspect window",
        "Rumi control window click Show search then expect Search query then type hello into Search query then check Match case",
        "Rumi confirm window plan"))["results"]
    for row in samples:
        print(f'{row["confidence"]}: {row["recognized"]}')
        assert row["confidence"] >= .72 and row["recognized"].casefold() == row["phrase"].casefold()

    title = "Rumi test " + uuid4().hex[:9]
    child = subprocess.Popen([sys.executable, __file__, "--fixture", title])
    adapter = WindowsControls()
    try:
        deadline = time.monotonic() + 12
        target = None
        while time.monotonic() < deadline and child.poll() is None:
            target = next((window for window in adapter.windows(lambda: None) if window.title == title), None)
            if target:
                break
            time.sleep(0.1)
        if not target:
            raise RuntimeError("Disposable test window did not open.")
        adapter.focus(target, lambda: None)
        with tempfile.TemporaryDirectory() as directory:
            runtime = NativeRuntime(Path(directory) / "receipts.db", operator_factory=lambda: adapter)
            try:
                grant = runtime.enable_operator(runtime.generation)

                def command(text):
                    result = runtime.command({"request_id": str(uuid4()), "session_id": grant["session_id"],
                                              "expires_at": int(time.time()) + 90, "text": text})
                    print(f'{result["state"]}: {result["message"]}')
                    return result

                inspected = command(samples[0]["recognized"])
                assert inspected["state"] == "succeeded" and "Show search" in inspected["message"]
                preview = command(samples[1]["recognized"])
                assert preview["state"] == "plan"
                receipt = command(samples[2]["recognized"])
                assert receipt["state"] == "succeeded" and "Verified all 3 steps" in receipt["message"]
            finally:
                runtime.close()
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        fixture(sys.argv[2])
    else:
        main()
