"""Optional Windows global hotkey and reusable Edge app window for the library."""
import ctypes
import os
import subprocess
import threading
import time
import webbrowser
from ctypes import wintypes as W
from pathlib import Path
from urllib.parse import urlencode
from .native_panel import NativePanel


def parse_hotkey(chord):
    if not isinstance(chord, str):
        raise ValueError("快捷键必须是文本")
    parts = chord.lower().split("+")
    modifiers = {"alt": 1, "ctrl": 2, "shift": 4}
    keys = {"tab": 0x09, "space": 0x20, **{f"f{i}": 0x6F+i for i in range(1, 13)}}
    if len(set(parts)) != len(parts) or any(part not in modifiers for part in parts[:-1]):
        raise ValueError("请使用 Tab、F1–F12，或 ctrl/alt/shift 加字母、Tab、Space")
    key = parts[-1]
    code = keys.get(key)
    if code is None and len(key) == 1 and key.isascii() and key.isalnum():
        code = ord(key.upper())
    if code is None or (len(parts) == 1 and key not in keys) or (len(parts) == 1 and key == "space"):
        raise ValueError("不支持的全局快捷键")
    return sum(modifiers[part] for part in parts[:-1]) | 0x4000, code


class LibraryLauncher:
    def __init__(self, settings, desktop, url, notify):
        self.settings, self.desktop, self.url, self.notify = settings, desktop, url, notify
        self.status = {"registered": False, "message": "Ctrl+K 搜索"}
        self.thread = None
        self.thread_id = None
        self.panel = None
        self.targets = set()
        self.stop = threading.Event()
        self.operation_lock = threading.RLock()
        self.monitor = None
        self.edge = next((path for path in [Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe", Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe"] if path.is_file()), None)

    def start(self):
        if os.name != "nt" or self.desktop is None or not self.settings.get("enabled", True):
            return
        try:
            self.modifiers, self.key = parse_hotkey(self.settings.get("shortcut", "tab"))
        except ValueError as exc:
            self.status["message"] = str(exc) + "；仍可用 Ctrl+K 搜索"
            return
        if self.settings.get("frameless", True):
            self.panel = NativePanel(self.desktop)
        self.targets = {row['hwnd'] for row in self.desktop.windows()}
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        self.monitor.start()
        ready = threading.Event()
        self.thread = threading.Thread(target=self._listen, args=(ready,), daemon=True)
        self.thread.start()
        ready.wait(2)

    def _monitor(self):
        refresh_at = 0
        while not self.stop.wait(0.1):
            try:
                # Keep the last CAD target when the user switches to the WebUI.
                self.desktop.active_window()
                if time.monotonic() >= refresh_at:
                    self.targets = {row['hwnd'] for row in self.desktop.windows()}
                    refresh_at = time.monotonic() + 0.5
                if self.panel:
                    self.panel.tick()
            except (OSError, ValueError):
                pass

    def _listen(self, ready):
        u, k = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
        u.RegisterHotKey.argtypes, u.RegisterHotKey.restype = [W.HWND, ctypes.c_int, W.UINT, W.UINT], W.BOOL
        u.UnregisterHotKey.argtypes, u.UnregisterHotKey.restype = [W.HWND, ctypes.c_int], W.BOOL
        u.GetMessageW.argtypes, u.GetMessageW.restype = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT], W.BOOL
        u.PeekMessageW.argtypes, u.PeekMessageW.restype = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT], W.BOOL
        k.GetCurrentThreadId.restype = W.DWORD
        self.thread_id = k.GetCurrentThreadId()
        hook = None
        # Bare Tab uses a scoped hook: registering it globally would remove Tab
        # navigation from every application. Callback only checks cached HWNDs.
        if self.modifiers == 0x4000:
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, W.WPARAM, W.LPARAM)
            class KeyEvent(ctypes.Structure):
                _fields_ = [('vk', W.DWORD), ('scan', W.DWORD), ('flags', W.DWORD), ('time', W.DWORD), ('extra', ctypes.c_size_t)]
            u.SetWindowsHookExW.argtypes, u.SetWindowsHookExW.restype = [ctypes.c_int, callback_type, W.HINSTANCE, W.DWORD], W.HANDLE
            u.CallNextHookEx.argtypes, u.CallNextHookEx.restype = [W.HANDLE, ctypes.c_int, W.WPARAM, W.LPARAM], ctypes.c_ssize_t
            u.UnhookWindowsHookEx.argtypes, u.UnhookWindowsHookEx.restype = [W.HANDLE], W.BOOL
            k.GetModuleHandleW.argtypes, k.GetModuleHandleW.restype = [W.LPCWSTR], W.HMODULE
            modifier_keys = (0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C)
            held = {code for code in modifier_keys[3:] if self.desktop.u.GetAsyncKeyState(code) & 0x8000}
            consumed = False
            @callback_type
            def keyboard(code, message_id, pointer):
                nonlocal consumed
                if code >= 0:
                    event = ctypes.cast(pointer, ctypes.POINTER(KeyEvent)).contents
                    down = message_id in (0x100, 0x104)
                    if event.vk in modifier_keys:
                        held.add(event.vk) if down else held.discard(event.vk)
                    if event.vk == self.key:
                        if consumed:
                            if not down:
                                consumed = False
                            return 1
                        hwnd = self.desktop.u.GetForegroundWindow()
                        target = self.hotkey_target(hwnd)
                        if down and not held and target is not None:
                            consumed = True
                            self.notify(f'hwnd:{target}')
                            return 1
                return u.CallNextHookEx(None, code, message_id, pointer)
            self.keyboard_callback = keyboard
            hook = u.SetWindowsHookExW(13, keyboard, k.GetModuleHandleW(None), 0)
            registered = bool(hook)
        else:
            registered = bool(u.RegisterHotKey(None, 1, self.modifiers, self.key))
        if not registered:
            self.status["message"] = "全局快捷键注册失败（可能已被占用）；仍可用 Ctrl+K 搜索"
            ready.set()
            return
        self.status = {"registered": True, "message": self.settings.get("shortcut", "tab").title() + " 打开 / 关闭 · Esc 收起 · Ctrl+K 搜索", "shortcut": self.settings.get("shortcut", "tab"), "frameless": bool(self.panel)}
        # Create the thread queue before close() can post WM_QUIT.
        message = W.MSG()
        u.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        ready.set()
        try:
            while u.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312:
                    hwnd = self.desktop.u.GetForegroundWindow()
                    path = self.desktop.process_path(hwnd) if hwnd else None
                    target_id = f"hwnd:{hwnd}" if path and Path(path).name.lower() == "plasticity.exe" else None
                    self.notify(target_id)
        finally:
            if hook:
                u.UnhookWindowsHookEx(hook)
            else:
                u.UnregisterHotKey(None, 1)
            self.status["registered"] = False

    def open(self, target_id=None):
        with self.operation_lock:
            return self._open(target_id)

    def hotkey_target(self, hwnd):
        if self.panel and self.panel.visible and hwnd == self.panel.hwnd:
            return self.panel.target if self.panel.target in self.targets else None
        return hwnd if hwnd in self.targets else None

    def toggle(self, target_id=None):
        with self.operation_lock:
            if self.panel and self.panel.visible and target_id == f'hwnd:{self.panel.target}':
                self.panel.dismiss()
                return False
            self._open(target_id)
            return True

    def _open(self, target_id=None):
        target = None
        if target_id and target_id.startswith('hwnd:') and self.desktop:
            target = int(target_id[5:])
            self.desktop.validate(target)
        if self.edge and self.desktop:
            candidates = []
            callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
            @callback_type
            def visit(hwnd, _):
                title = ctypes.create_unicode_buffer(1024)
                self.desktop.u.GetWindowTextW(hwnd, title, len(title))
                if title.value.startswith("Plasticity 模型组件库"):
                    path = self.desktop.process_path(hwnd)
                    if path and Path(path).name.lower() == "msedge.exe":
                        candidates.append(hwnd)
                return True
            self.desktop.u.EnumWindows.argtypes = [callback_type, W.LPARAM]
            self.desktop.u.EnumWindows(visit, 0)
            if candidates:
                if self.panel and target:
                    self.panel.attach(candidates[0], target)
                else:
                    self.desktop.u.ShowWindowAsync(candidates[0], 9)
                    self.desktop.u.SetForegroundWindow(candidates[0])
                return
        url = self.url + "/?" + urlencode({"quick": "1", "panel": "1" if self.panel else "0", **({"target": target_id} if target_id else {})})
        if self.edge:
            subprocess.Popen([str(self.edge), "--app=" + url, "--no-first-run"], creationflags=0x08000000)
            if self.panel and target:
                # Edge returns before its window exists. The next pass locates
                # and attaches it; no second browser process is started.
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and not self.stop.wait(0.1):
                    candidates.clear()
                    self.desktop.u.EnumWindows(visit, 0)
                    if candidates:
                        self.panel.attach(candidates[0], target)
                        break
        else:
            webbrowser.open(url)

    def close(self):
        self.stop.set()
        if self.monitor:
            self.monitor.join(timeout=2)
        if self.thread_id and self.thread and self.thread.is_alive():
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, W.WPARAM, W.LPARAM]
            u.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.thread.join(timeout=2)
        with self.operation_lock:
            if self.panel:
                self.panel.restore()

    def snapshot(self):
        state = dict(self.status)
        if self.panel:
            with self.panel.lock:
                state['panel'] = {'attached': bool(self.panel.hwnd), 'visible': self.panel.visible,
                                  'focused': bool(self.panel.hwnd and self.desktop.u.GetForegroundWindow() == self.panel.hwnd),
                                  'frame_applied': self.panel.frame_applied(),
                                  'target_id': f'hwnd:{self.panel.target}' if self.panel.target else None}
        return state
