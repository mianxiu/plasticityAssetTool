"""Small Win32 adapter; no pywin32 dependency or import-time desktop changes."""
import ctypes
import os
import time
from contextlib import contextmanager
from ctypes import wintypes as W
from pathlib import Path

FORMAT_NAME = "application/vnd.plasticity.items"
MAX_BYTES = 64 * 1024 * 1024


class WindowsBridge:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("原生剪贴板模式需要 Windows")
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        declarations = [
            (self.u, "RegisterClipboardFormatW", [W.LPCWSTR], W.UINT),
            (self.u, "OpenClipboard", [W.HWND], W.BOOL),
            (self.u, "CloseClipboard", [], W.BOOL),
            (self.u, "EmptyClipboard", [], W.BOOL),
            (self.u, "GetClipboardData", [W.UINT], W.HANDLE),
            (self.u, "SetClipboardData", [W.UINT, W.HANDLE], W.HANDLE),
            (self.u, "IsClipboardFormatAvailable", [W.UINT], W.BOOL),
            (self.u, "GetClipboardSequenceNumber", [], W.DWORD),
            (self.k, "GlobalAlloc", [W.UINT, ctypes.c_size_t], W.HGLOBAL),
            (self.k, "GlobalLock", [W.HGLOBAL], ctypes.c_void_p),
            (self.k, "GlobalUnlock", [W.HGLOBAL], W.BOOL),
            (self.k, "GlobalSize", [W.HGLOBAL], ctypes.c_size_t),
            (self.k, "GlobalFree", [W.HGLOBAL], W.HGLOBAL),
            (self.u, "IsWindow", [W.HWND], W.BOOL),
            (self.u, "IsWindowVisible", [W.HWND], W.BOOL),
            (self.u, "GetWindowTextW", [W.HWND, W.LPWSTR, ctypes.c_int], ctypes.c_int),
            (self.u, "GetClassNameW", [W.HWND, W.LPWSTR, ctypes.c_int], ctypes.c_int),
            (self.u, "GetWindowThreadProcessId", [W.HWND, ctypes.POINTER(W.DWORD)], W.DWORD),
            (self.k, "OpenProcess", [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            (self.k, "QueryFullProcessImageNameW", [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)], W.BOOL),
            (self.k, "CloseHandle", [W.HANDLE], W.BOOL),
            (self.u, "GetForegroundWindow", [], W.HWND),
            (self.u, "SetForegroundWindow", [W.HWND], W.BOOL),
            (self.u, "ShowWindow", [W.HWND, ctypes.c_int], W.BOOL),
            (self.u, "ShowWindowAsync", [W.HWND, ctypes.c_int], W.BOOL),
            (self.u, "IsIconic", [W.HWND], W.BOOL),
            (self.u, "GetAsyncKeyState", [ctypes.c_int], ctypes.c_short),
        ]
        for dll, name, args, result in declarations:
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
        self.format_id = self.u.RegisterClipboardFormatW(FORMAT_NAME)
        if not self.format_id:
            raise ctypes.WinError(ctypes.get_last_error())
        # EmptyClipboard needs an owner window for SetClipboardData to succeed.
        self.u.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, ctypes.c_void_p]
        self.u.CreateWindowExW.restype = W.HWND
        self.owner = self.u.CreateWindowExW(0, "STATIC", "Plasticity Asset Tool Clipboard", 0, 0, 0, 0, 0, W.HWND(-3), None, None, None)
        if not self.owner:
            raise ctypes.WinError(ctypes.get_last_error())

    @contextmanager
    def opened(self):
        deadline = time.monotonic() + 1.5
        while not self.u.OpenClipboard(self.owner):
            if time.monotonic() >= deadline:
                raise RuntimeError("剪贴板正被其他程序使用，请稍后重试")
            time.sleep(0.03)
        try:
            yield
        finally:
            self.u.CloseClipboard()

    def sequence(self):
        return self.u.GetClipboardSequenceNumber()

    def read(self):
        with self.opened():
            if not self.u.IsClipboardFormatAvailable(self.format_id):
                raise ValueError("剪贴板没有 Plasticity 模型。请先选中实体并按 Ctrl+C")
            handle = self.u.GetClipboardData(self.format_id)
            size = self.k.GlobalSize(handle)
            if not handle or not 0 < size <= MAX_BYTES:
                raise ValueError("模型数据为空或超过 64 MB")
            pointer = self.k.GlobalLock(handle)
            if not pointer:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                return ctypes.string_at(pointer, size)
            finally:
                self.k.GlobalUnlock(handle)

    def write(self, data):
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
            raise ValueError("模型数据为空或超过 64 MB")
        handle = self.k.GlobalAlloc(0x0002, len(data))
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        owned = True
        try:
            pointer = self.k.GlobalLock(handle)
            if not pointer:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                ctypes.memmove(pointer, data, len(data))
            finally:
                self.k.GlobalUnlock(handle)
            with self.opened():
                if not self.u.EmptyClipboard() or not self.u.SetClipboardData(self.format_id, handle):
                    raise ctypes.WinError(ctypes.get_last_error())
                owned = False
        finally:
            if owned:
                self.k.GlobalFree(handle)

    def process_path(self, hwnd):
        pid = W.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = self.k.OpenProcess(0x1000, False, pid.value)
        if not process:
            return None
        try:
            path, size = ctypes.create_unicode_buffer(32768), W.DWORD(32768)
            return path.value if self.k.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)) else None
        finally:
            self.k.CloseHandle(process)

    def is_model_window(self, hwnd):
        path = self.process_path(hwnd)
        if not path or Path(path).name.lower() != "plasticity.exe":
            return False
        name = ctypes.create_unicode_buffer(256)
        self.u.GetClassNameW(hwnd, name, len(name))
        # Kernel console windows share Plasticity's process name. Only its
        # Electron workspaces can receive model placement commands.
        return name.value.startswith("Chrome_WidgetWin_")

    def windows(self):
        result = []
        callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        self.u.EnumWindows.argtypes = [callback_type, W.LPARAM]
        self.u.EnumWindows.restype = W.BOOL
        @callback_type
        def visit(hwnd, _):
            if not self.u.IsWindowVisible(hwnd):
                return True
            path = self.process_path(hwnd)
            if self.is_model_window(hwnd):
                title = ctypes.create_unicode_buffer(1024)
                self.u.GetWindowTextW(hwnd, title, len(title))
                result.append({"id": f"hwnd:{hwnd}", "hwnd": hwnd, "title": title.value or "Plasticity", "path": path, "mode": "desktop"})
            return True
        self.u.EnumWindows(visit, 0)
        return result

    def validate(self, hwnd):
        if not self.u.IsWindow(hwnd) or not self.is_model_window(hwnd):
            raise ValueError("目标 Plasticity 窗口已关闭，请刷新并重新选择")

    def activate(self, hwnd):
        self.validate(hwnd)
        foreground = self.u.GetForegroundWindow()
        if foreground == hwnd:
            return
        if self.u.IsIconic(hwnd):
            self.u.ShowWindowAsync(hwnd, 9)
        # The service is a background process. Yield the library app window's
        # foreground slot before switching, without merging browser/CAD input
        # queues (which can block on an unresponsive window).
        library_window = None
        if foreground:
            title = ctypes.create_unicode_buffer(1024)
            self.u.GetWindowTextW(foreground, title, len(title))
            path = self.process_path(foreground)
            if title.value.startswith("Plasticity 模型组件库") and path and Path(path).name.lower() == "msedge.exe":
                library_window = foreground
        minimized = False
        try:
            if library_window:
                minimized = bool(self.u.ShowWindowAsync(library_window, 6))
                deadline = time.monotonic() + 1.0
                while self.u.GetForegroundWindow() == library_window:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(0.02)
            self.u.SetForegroundWindow(hwnd)
            deadline = time.monotonic() + 1.0
            while self.u.GetForegroundWindow() != hwnd:
                if time.monotonic() >= deadline:
                    raise RuntimeError("无法激活目标窗口。请点击目标 Plasticity 视口，再唤起组件库重试")
                time.sleep(0.02)
            self.validate(hwnd)
        except Exception:
            if minimized and self.u.IsWindow(library_window):
                self.u.ShowWindowAsync(library_window, 9)
            raise

    def shortcut(self, hwnd, chord):
        codes = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "space": 0x20, "escape": 0x1B, "enter": 0x0D}
        keys = []
        for key in chord.lower().split("+"):
            if key in codes:
                keys.append(codes[key])
            elif len(key) == 1 and key.isascii() and key.isalnum():
                keys.append(ord(key.upper()))
            else:
                raise ValueError("不支持的快捷键，请在 config.json 中使用 ctrl/shift/alt 和字母")
        self.activate(hwnd)
        if any(self.u.GetAsyncKeyState(code) & 0x8000 for code in (0x10, 0x11, 0x12)):
            raise RuntimeError("请松开 Ctrl、Shift、Alt 后重试")
        class Keyboard(ctypes.Structure):
            _fields_ = [("vk", W.WORD), ("scan", W.WORD), ("flags", W.DWORD), ("time", W.DWORD), ("extra", ctypes.c_size_t)]
        class Mouse(ctypes.Structure):
            _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("data", W.DWORD), ("flags", W.DWORD), ("time", W.DWORD), ("extra", ctypes.c_size_t)]
        class Hardware(ctypes.Structure):
            _fields_ = [("message", W.DWORD), ("low", W.WORD), ("high", W.WORD)]
        class Union(ctypes.Union):
            _fields_ = [("keyboard", Keyboard), ("mouse", Mouse), ("hardware", Hardware)]
        class Input(ctypes.Structure):
            _fields_ = [("type", W.DWORD), ("value", Union)]
        events = [Input(1, Union(keyboard=Keyboard(code, 0, 0, 0, 0))) for code in keys]
        events += [Input(1, Union(keyboard=Keyboard(code, 0, 2, 0, 0))) for code in reversed(keys)]
        array = (Input * len(events))(*events)
        self.validate(hwnd)
        if self.u.GetForegroundWindow() != hwnd:
            raise RuntimeError("目标窗口焦点发生变化，请重试")
        self.u.SendInput.argtypes = [W.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.u.SendInput.restype = W.UINT
        if self.u.SendInput(len(events), array, ctypes.sizeof(Input)) != len(events):
            # Release modifiers if Windows accepted only part of the sequence.
            releases = (Input * len(keys))(*[Input(1, Union(keyboard=Keyboard(code, 0, 2, 0, 0))) for code in reversed(keys)])
            self.u.SendInput(len(releases), releases, ctypes.sizeof(Input))
            raise RuntimeError("快捷键发送失败，请确认工具和 Plasticity 以相同权限运行")
