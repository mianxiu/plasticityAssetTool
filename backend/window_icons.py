"""Assign native, DPI-sized icons to the Edge-hosted control window."""
import ctypes
import os
from ctypes import wintypes as W
from .service_tray import ICON_PATH


def icon_sizes(dpi):
    return tuple(max(16, round(size * (dpi or 96) / 96)) for size in (16, 32))


class WindowIcons:
    def __init__(self, user32=None):
        self.u = user32
        self.handles = {}

    def _api(self):
        if self.u is None:
            self.u = ctypes.WinDLL('user32', use_last_error=True)
            for name, arguments, result in [
                ('IsWindow', [W.HWND], W.BOOL),
                ('GetDpiForWindow', [W.HWND], W.UINT),
                ('LoadImageW', [W.HINSTANCE,W.LPCWSTR,W.UINT,ctypes.c_int,ctypes.c_int,W.UINT], W.HANDLE),
                ('SendMessageTimeoutW', [W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,ctypes.POINTER(ctypes.c_size_t)], W.LPARAM),
            ]:
                function = getattr(self.u, name)
                function.argtypes, function.restype = arguments, result
        return self.u

    def message(self, hwnd, message, kind, value):
        result = ctypes.c_size_t()
        if not self._api().SendMessageTimeoutW(hwnd, message, kind, value, 0x2, 300, ctypes.byref(result)):
            return None
        return result.value

    def apply(self, hwnd):
        if os.name != 'nt' and self.u is None:
            return False
        u = self._api()
        if not u.IsWindow(hwnd):
            return False
        dpi = u.GetDpiForWindow(hwnd) or 96
        for kind, size in enumerate(icon_sizes(dpi)):
            if size not in self.handles:
                # Keep these handles for the backend lifetime: another process's
                # window still references them. Never destroy Edge-owned icons.
                icon = u.LoadImageW(None, str(ICON_PATH), 1, size, size, 0x10)
                if not icon:
                    return False
                self.handles[size] = icon
            icon = self.handles[size]
            current = self.message(hwnd, 0x7f, kind, dpi)  # WM_GETICON
            if current is None:
                return False
            if current != icon and self.message(hwnd, 0x80, kind, icon) is None:  # WM_SETICON
                return False
        return True
