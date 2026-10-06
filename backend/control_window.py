"""Open the local WebUI in a reusable, normal framed Edge app window."""
import ctypes
import os
import subprocess
import threading
import time
import webbrowser
from ctypes import wintypes as W
from pathlib import Path
from .window_icons import WindowIcons

TITLE = "plasticity asset tool — control center"


class ControlWindow:
    def __init__(self, url, root, desktop=None):
        self.url = url.rstrip("/") + "/?control=1"
        self.root, self.desktop = Path(root), desktop
        self.lock = threading.Lock()
        self.icons = WindowIcons()
        self.icon_thread = None
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
                self.icons.apply(hwnd)
                self._watch_icons()
                if self.desktop.u.IsIconic(hwnd):
                    self.desktop.u.ShowWindowAsync(hwnd, 9)
                self.desktop.u.SetForegroundWindow(hwnd)
                return {"message": "后台管理窗口已打开", "mode": "window", "reused": True}
            if self.edge:
                profile = self.root / ".runtime" / "control-window-profile"
                subprocess.Popen([str(self.edge), "--app=" + self.url,
                                  "--user-data-dir=" + str(profile), "--no-first-run", "--window-size=960,720"],
                                 creationflags=0x08000000 if os.name == "nt" else 0)
                self._watch_icons()
                return {"message": "后台管理窗口已打开", "mode": "window", "reused": False}
            webbrowser.open(self.url)
            return {"message": "已在浏览器打开后台 WebUI", "mode": "browser", "reused": False}

    def _watch_icons(self):
        if os.name != 'nt' or not self.desktop or (self.icon_thread and self.icon_thread.is_alive()):
            return
        def watch():
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                hwnd = self.existing_window()
                if hwnd:
                    break
                time.sleep(.25)
            else:
                return
            while self.existing_window() == hwnd and self.icons.apply(hwnd):
                # Edge may replace its favicon after navigation; monitor moves
                # can also change DPI. Repair only when the handle differs.
                time.sleep(2)
        self.icon_thread = threading.Thread(target=watch, name='control-window-icons', daemon=True)
        self.icon_thread.start()
