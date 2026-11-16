"""Opt-in Windows sign-in launch for the current portable executable."""
import sys
import winreg


class WakeSettings:
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "RumiDesktopBackgroundWake"

    def __init__(self):
        self.command = f'"{sys.executable}" --background-wake' if getattr(sys, "frozen", False) else None

    def enabled(self):
        if self.command is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key) as key:
                return winreg.QueryValueEx(key, self.name) == (self.command, winreg.REG_SZ)
        except OSError:
            return False

    def set(self, enabled):
        if self.command is None:
            return
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.key, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            try:
                current = winreg.QueryValueEx(key, self.name)
            except FileNotFoundError:
                current = None
            if current == (self.command, winreg.REG_SZ):
                if not enabled:
                    winreg.DeleteValue(key, self.name)
            elif enabled:
                if current is not None:
                    raise OSError("Another Rumi executable is registered for startup")
                winreg.SetValueEx(key, self.name, 0, winreg.REG_SZ, self.command)
