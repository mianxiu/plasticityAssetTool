"""Windows notification-area controller, using only the standard library."""
import ctypes
import os
import struct
import threading
from pathlib import Path
from ctypes import wintypes as W
from .version import APP_NAME, APP_VERSION


ICON_PATH = Path(__file__).resolve().parents[1] / "plasticity-asset-tool-app/src/assets/favicon.ico"


def tray_menu_items(state):
    return [
        (3, 0, f'{APP_NAME} · v{APP_VERSION}'),
        (0x800, 0, None),
        (0, 1, '打开控制中心'), (0, 2, '查看模型组件库'),
        (0x800, 0, None),
        (3, 0, f"Plasticity 窗口：{len(state.get('targets', []))} · 组件：{state.get('component_count', 0)}"),
        (0, 3, '刷新连接状态'),
        (0, 4, '恢复模型连接' if not state.get('model_enabled', True) else '暂停模型连接'),
        (0x800, 0, None), (0, 9, '退出组件库后台服务'),
    ]


def icon_bitmap(paused=False, size=32):
    """Read the same native-size ICO entry used by the launcher and WebUI."""
    data = ICON_PATH.read_bytes()
    reserved, kind, count = struct.unpack_from('<HHH', data)
    if reserved or kind != 1:
        raise ValueError("Invalid application ICO")
    for index in range(count):
        width, height, _, _, _, _, length, offset = struct.unpack_from('<BBBBHHII', data, 6+16*index)
        if (width or 256) == size and (height or 256) == size:
            return data[offset:offset+length]
    raise ValueError(f"Missing {size}px application icon")


class ServiceTray:
    def __init__(self, callback):
        self.callback = callback
        self.available = False
        self.error = ""
        self.hwnd = None
        self.state = {"model_enabled": True, "targets": [], "component_count": 0}
        self.lock = threading.Lock()
        self.ready = threading.Event()

    def start(self):
        if os.name != 'nt':
            self.error = "系统托盘仅支持 Windows"
            return
        self.thread = threading.Thread(target=self._run, name='component-library-tray', daemon=True)
        self.thread.start()
        self.ready.wait(3)

    def update(self, state):
        with self.lock:
            self.state = dict(state)
        if self.hwnd:
            self.u.PostMessageW(self.hwnd, 0x8002, 0, 0)

    def close(self):
        if self.hwnd:
            self.u.PostMessageW(self.hwnd, 0x0010, 0, 0)
        if getattr(self, 'thread', None):
            self.thread.join(3)

    def _run(self):
        try:
            self._native_loop()
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.available = False
            self.hwnd = None
            self.ready.set()

    def _native_loop(self):
        self.u = u = ctypes.WinDLL('user32', use_last_error=True)
        shell = ctypes.WinDLL('shell32', use_last_error=True)
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
        class WindowClass(ctypes.Structure):
            _fields_ = [('style',W.UINT),('proc',proc_type),('clsExtra',ctypes.c_int),('wndExtra',ctypes.c_int),('instance',W.HINSTANCE),('icon',W.HICON),('cursor',W.HANDLE),('background',W.HBRUSH),('menu',W.LPCWSTR),('name',W.LPCWSTR)]
        class NotifyIcon(ctypes.Structure):
            _fields_ = [('size',W.DWORD),('hwnd',W.HWND),('id',W.UINT),('flags',W.UINT),('message',W.UINT),('icon',W.HICON),('tip',W.WCHAR*128),('state',W.DWORD),('stateMask',W.DWORD),('info',W.WCHAR*256),('version',W.UINT),('infoTitle',W.WCHAR*64),('infoFlags',W.DWORD),('guid',ctypes.c_byte*16),('balloonIcon',W.HICON)]
        declarations = [
            ('FindWindowW',[W.LPCWSTR,W.LPCWSTR],W.HWND),
            ('GetDpiForWindow',[W.HWND],W.UINT),
            ('LoadImageW',[W.HINSTANCE,W.LPCWSTR,W.UINT,ctypes.c_int,ctypes.c_int,W.UINT],W.HANDLE),
            ('RegisterClassW',[ctypes.POINTER(WindowClass)],W.WORD),
            ('UnregisterClassW',[W.LPCWSTR,W.HINSTANCE],W.BOOL),
            ('CreateWindowExW',[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,W.LPVOID],W.HWND),
            ('DefWindowProcW',[W.HWND,W.UINT,W.WPARAM,W.LPARAM],ctypes.c_ssize_t),
            ('PostMessageW',[W.HWND,W.UINT,W.WPARAM,W.LPARAM],W.BOOL),
            ('DestroyWindow',[W.HWND],W.BOOL),('DestroyIcon',[W.HICON],W.BOOL),
            ('CreateIconFromResourceEx',[W.LPVOID,W.DWORD,W.BOOL,W.DWORD,ctypes.c_int,ctypes.c_int,W.UINT],W.HICON),
            ('CreatePopupMenu',[],W.HMENU),('AppendMenuW',[W.HMENU,W.UINT,ctypes.c_size_t,W.LPCWSTR],W.BOOL),
            ('DestroyMenu',[W.HMENU],W.BOOL),('SetForegroundWindow',[W.HWND],W.BOOL),
            ('GetCursorPos',[ctypes.POINTER(W.POINT)],W.BOOL),
            ('TrackPopupMenu',[W.HMENU,W.UINT,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.LPVOID],W.UINT),
            ('GetMessageW',[ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT],ctypes.c_int),
            ('TranslateMessage',[ctypes.POINTER(W.MSG)],W.BOOL),('DispatchMessageW',[ctypes.POINTER(W.MSG)],ctypes.c_ssize_t),
            ('PostQuitMessage',[ctypes.c_int],None),('RegisterWindowMessageW',[W.LPCWSTR],W.UINT),
        ]
        for name, arguments, result in declarations:
            method = getattr(u,name)
            method.argtypes, method.restype = arguments, result
        k.GetModuleHandleW.argtypes, k.GetModuleHandleW.restype = [W.LPCWSTR], W.HMODULE
        shell.Shell_NotifyIconW.argtypes, shell.Shell_NotifyIconW.restype = [W.DWORD,ctypes.POINTER(NotifyIcon)],W.BOOL
        icons = []
        taskbar = u.FindWindowW('Shell_TrayWnd',None)
        dpi = (u.GetDpiForWindow(taskbar) if taskbar else 96) or 96
        size = max(16,round(16*dpi/96))
        icon = u.LoadImageW(None,str(ICON_PATH),1,size,size,0x10)
        if not icon:
            raise ctypes.WinError(ctypes.get_last_error())
        icons.append(icon)
        notification = NotifyIcon()
        notification.size, notification.id = ctypes.sizeof(notification), 1
        notification.flags, notification.message = 1|2|4, 0x8001
        taskbar_created = u.RegisterWindowMessageW('TaskbarCreated')
        def publish(operation):
            with self.lock:
                state = dict(self.state)
            paused = not state.get('model_enabled',True)
            notification.icon = icons[0]
            notification.tip = f"Plasticity 组件库 v{APP_VERSION} · {'连接暂停' if paused else '服务运行中'}\n{len(state.get('targets',[]))} 个窗口 · {state.get('component_count',0)} 个组件"[:127]
            return shell.Shell_NotifyIconW(operation,ctypes.byref(notification))
        def menu():
            with self.lock:
                state = dict(self.state)
            popup = u.CreatePopupMenu()
            try:
                for flags,item,label in tray_menu_items(state):
                    u.AppendMenuW(popup,flags,item,label)
                point = W.POINT()
                u.GetCursorPos(ctypes.byref(point))
                u.SetForegroundWindow(self.hwnd)
                chosen = u.TrackPopupMenu(popup,0x100|0x2,point.x,point.y,0,self.hwnd,None)
                u.PostMessageW(self.hwnd,0,0,0)
                if chosen:
                    self.callback({1:'control',2:'library',3:'refresh',4:'toggle',9:'quit'}[chosen])
            finally:
                u.DestroyMenu(popup)
        def procedure(hwnd,message,wparam,lparam):
            if message == taskbar_created:
                publish(0)
            elif message == 0x8002:
                publish(1)
            elif message == 0x8001:
                if lparam == 0x203:
                    self.callback('control')
                elif lparam in (0x205,0x7b):
                    menu()
            elif message == 0x10:
                u.DestroyWindow(hwnd)
            elif message == 2:
                u.PostQuitMessage(0)
            else:
                return u.DefWindowProcW(hwnd,message,wparam,lparam)
            return 0
        self._procedure = proc_type(procedure)
        instance = k.GetModuleHandleW(None)
        name = f'plasticityassettooltray{os.getpid()}'
        window_class = WindowClass(0,self._procedure,0,0,instance,icons[0],None,None,None,name)
        registered = u.RegisterClassW(ctypes.byref(window_class))
        try:
            if not registered:
                raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd = u.CreateWindowExW(0,name,'Plasticity 组件库后台',0,0,0,0,0,None,None,instance,None)
            notification.hwnd = self.hwnd
            if not self.hwnd or not publish(0):
                raise ctypes.WinError(ctypes.get_last_error())
            self.available = True
            self.ready.set()
            message = W.MSG()
            while u.GetMessageW(ctypes.byref(message),None,0,0) > 0:
                u.TranslateMessage(ctypes.byref(message))
                u.DispatchMessageW(ctypes.byref(message))
        finally:
            shell.Shell_NotifyIconW(2,ctypes.byref(notification))
            if self.hwnd:
                u.DestroyWindow(self.hwnd)
            if registered:
                u.UnregisterClassW(name,instance)
            for icon in icons:
                u.DestroyIcon(icon)
