"""Open the local WebUI in a reusable, normal framed Edge app window."""
import ctypes
import os
import subprocess
import threading
import webbrowser
from ctypes import wintypes as W
from pathlib import Path

TITLE = "Plasticity Asset Tool — Control Center"


class ControlWindow:
    def __init__(self, url, root, desktop=None):
        self.url = url.rstrip("/") + "/?control=1"
        self.root, self.desktop = Path(root), desktop
        self.lock = threading.Lock()
        self.edge = next((path for path in (
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        ) if path.is_file()), None)

    def existing_window(self):
        if os.name != "nt" or not self.desktop:
            return None
        desktop, matches = self.desktop, []
        callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        @callback_type
        def visit(hwnd, _):
            if not desktop.u.IsWindowVisible(hwnd):
                return True
            title = ctypes.create_unicode_buffer(512)
            desktop.u.GetWindowTextW(hwnd, title, len(title))
            if title.value.startswith((TITLE, "Plasticity 组件库控制中心")):
                path = desktop.process_path(hwnd)
                if path and Path(path).name.lower() == "msedge.exe":
                    matches.append(hwnd)
            return True

        desktop.u.EnumWindows(visit, 0)
        return matches[0] if matches else None

    def open(self):
        with self.lock:
            hwnd = self.existing_window()
            if hwnd:
                if self.desktop.u.IsIconic(hwnd):
                    self.desktop.u.ShowWindowAsync(hwnd, 9)
                self.desktop.u.SetForegroundWindow(hwnd)
                return {"message": "后台管理窗口已打开", "mode": "window", "reused": True}
            if self.edge:
                profile = self.root / ".runtime" / "control-window-profile"
                subprocess.Popen([str(self.edge), "--app=" + self.url,
                                  "--user-data-dir=" + str(profile), "--no-first-run", "--window-size=960,720"],
                                 creationflags=0x08000000 if os.name == "nt" else 0)
                return {"message": "后台管理窗口已打开", "mode": "window", "reused": False}
            webbrowser.open(self.url)
            return {"message": "已在浏览器打开后台 WebUI", "mode": "browser", "reused": False}
