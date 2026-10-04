"""Owned, frameless library overlay; never reparents Chromium across DPI contexts."""
import ctypes
import threading
from ctypes import wintypes as W


def panel_bounds(width, height, origin=(0, 0), scale=1):
    margin = min(round(16 * scale), max(0, min(width, height) // 20))
    panel_width = min(round(1120 * scale), max(1, width - margin * 2))
    panel_height = min(round(760 * scale), max(1, height - margin * 2))
    return (origin[0] + (width - panel_width) // 2,
            origin[1] + (height - panel_height) // 2, panel_width, panel_height)


class NativePanel:
    def __init__(self, desktop):
        self.desktop, self.u = desktop, desktop.u
        self.hwnd = self.target = None
        self.saved = None
        self.visible = False
        self.bounds = None
        self.lock = threading.RLock()
        for name, args, result in [
            ('GetWindowLongPtrW', [W.HWND, ctypes.c_int], ctypes.c_ssize_t),
            ('SetWindowLongPtrW', [W.HWND, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t),
            ('GetClientRect', [W.HWND, ctypes.POINTER(W.RECT)], W.BOOL),
            ('ClientToScreen', [W.HWND, ctypes.POINTER(W.POINT)], W.BOOL),
            ('SetWindowPos', [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT], W.BOOL),
            ('GetWindowRect', [W.HWND, ctypes.POINTER(W.RECT)], W.BOOL),
            ('GetDpiForWindow', [W.HWND], W.UINT),
            ('GetSystemMetricsForDpi', [ctypes.c_int, W.UINT], ctypes.c_int),
            ('SetWindowRgn', [W.HWND, W.HANDLE, W.BOOL], ctypes.c_int),
            ('GetWindowRgnBox', [W.HWND, ctypes.POINTER(W.RECT)], ctypes.c_int),
            ('SetThreadDpiAwarenessContext', [W.HANDLE], W.HANDLE),
        ]:
            function = getattr(self.u, name)
            function.argtypes, function.restype = args, result
        self.gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        self.gdi.CreateRectRgn.argtypes, self.gdi.CreateRectRgn.restype = [ctypes.c_int]*4, W.HANDLE
        self.gdi.DeleteObject.argtypes, self.gdi.DeleteObject.restype = [W.HANDLE], W.BOOL

    def attach(self, hwnd, target):
        with self.lock:
            self.desktop.validate(target)
            if self.hwnd != hwnd:
                self.restore()
                self.hwnd = hwnd
                self.saved = tuple(self.u.GetWindowLongPtrW(hwnd, index) for index in (-16, -20, -8))
            style, extended, _ = self.saved
            # Caption, resize frame, system menu, min/max buttons; owned popup
            # stays above its CAD owner without covering unrelated applications.
            self.u.SetWindowLongPtrW(hwnd, -16, (style & ~0x00CF0000) | 0x80000000)
            self.u.SetWindowLongPtrW(hwnd, -20, (extended & ~0x00040000) | 0x00000080)
            self.u.SetWindowLongPtrW(hwnd, -8, target)
            self.target, self.bounds = target, None
            self.visible = True
            self.u.ShowWindowAsync(hwnd, 9)
            self.position()
            self.u.SetForegroundWindow(hwnd)

    def position(self):
        previous = self.u.SetThreadDpiAwarenessContext(W.HANDLE(-4))
        try:
            self._position()
        finally:
            if previous:
                self.u.SetThreadDpiAwarenessContext(previous)

    def _position(self):
        rectangle, point = W.RECT(), W.POINT(0, 0)
        if not self.u.GetClientRect(self.target, ctypes.byref(rectangle)) or not self.u.ClientToScreen(self.target, ctypes.byref(point)):
            return
        scale = (self.u.GetDpiForWindow(self.target) or 96) / 96
        toolbar = min(round(48 * scale), max(0, rectangle.bottom // 5))
        bounds = panel_bounds(rectangle.right, rectangle.bottom-toolbar, (point.x, point.y+toolbar), scale)
        dpi = self.u.GetDpiForWindow(self.hwnd) or 96
        border = self.u.GetSystemMetricsForDpi(32, dpi) + self.u.GetSystemMetricsForDpi(92, dpi)
        top = self.u.GetSystemMetricsForDpi(4, dpi) + border
        x, y, width, height = bounds
        if bounds != self.bounds:
            # Chromium draws an app caption independently of WS_CAPTION.
            # Clip this browser chrome from the owned window; geometry uses
            # physical pixels so mixed-DPI displays do not expose the frame.
            # SWP_NOACTIVATE | SWP_NOZORDER | SWP_FRAMECHANGED
            if self.u.SetWindowPos(self.hwnd, None, x-border, y-top, width+border*2, height+top+border, 0x0034):
                self.bounds = bounds
        clipped = W.RECT()
        result = self.u.GetWindowRgnBox(self.hwnd, ctypes.byref(clipped))
        expected = (border, top, border + width, top + height)
        # Chromium may reset the region after processing a restore/resize.
        if result != 2 or (clipped.left, clipped.top, clipped.right, clipped.bottom) != expected:
            region = self.gdi.CreateRectRgn(border, top, border + width, top + height)
            if not region:
                raise OSError('无法创建无边框面板区域')
            if not self.u.SetWindowRgn(self.hwnd, region, True):
                self.gdi.DeleteObject(region)
                raise OSError('无法隐藏组件库窗口边框')

    def hide(self):
        with self.lock:
            self.visible = False
            if self.hwnd and self.u.IsWindow(self.hwnd):
                self.u.ShowWindowAsync(self.hwnd, 0)

    def dismiss(self):
        self.hide()
        if self.target and self.u.IsWindow(self.target):
            self.desktop.activate(self.target)

    def frame_applied(self):
        with self.lock:
            if not self.hwnd or not self.u.IsWindow(self.hwnd):
                return False
            rectangle = W.RECT()
            return self.u.GetWindowRgnBox(self.hwnd, ctypes.byref(rectangle)) == 2

    def tick(self):
        with self.lock:
            if not self.hwnd:
                return
            if not self.u.IsWindow(self.hwnd):
                self.hwnd, self.saved, self.visible = None, None, False
                return
            if not self.target or not self.u.IsWindow(self.target):
                self.restore()
                return
            if not self.visible:
                return
            foreground = self.u.GetForegroundWindow()
            if self.u.IsIconic(self.hwnd) or self.u.IsIconic(self.target) or foreground not in (self.hwnd, self.target):
                self.hide()
                return
            self.position()

    def restore(self):
        with self.lock:
            if self.hwnd and self.saved and self.u.IsWindow(self.hwnd):
                self.u.SetWindowRgn(self.hwnd, None, True)
                for index, value in zip((-16, -20, -8), self.saved):
                    self.u.SetWindowLongPtrW(self.hwnd, index, value)
                self.u.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0037)
                self.u.ShowWindowAsync(self.hwnd, 9)
            self.hwnd = self.target = self.saved = self.bounds = None
            self.visible = False
