from enum import Enum
import re
import win32gui
import win32con


import os
import win32clipboard
import ctypes
import io
from My_Modules.file_handle import File


        # 指定要保存到的文件路径
file_path = "./test file/clipboard_binary_data.bin"

class Websocket_Handle_Message(Enum):
    def __str__(self) -> str:
        return self.value

    PRINT_MESSAGE = ("PRINT_MESSAGE",)
    SW_HIDE = ("SW_HIDE",)
    SW_SHOW = ("SW_SHOW",)
    SW_SHOWNORMAL = ("SW_SHOWNORMAL",)
    SW_SHOWMINIMIZED = ("SW_SHOWMINIMIZED",)
    SW_SHOWMAXIMIZED = ("SW_SHOWMAXIMIZED",)
    SW_MAXIMIZE = ("SW_MAXIMIZE",)
    SW_MINIMIZE = ("SW_MINIMIZE",)
    SW_RESTORE = ("SW_RESTORE",)


class AssetDatabase(Enum):
    pass

class Clipboard(Enum):
        
        PLASTICITY_CUSTOM_FORMAT_NAME = "application/vnd.plasticity.items".encode("utf-8")

        @staticmethod
        def get_plasticity_format_id():
                RegisterClipboardFormat = ctypes.windll.user32.RegisterClipboardFormatA
                format_id = RegisterClipboardFormat(Clipboard.PLASTICITY_CUSTOM_FORMAT_NAME.value)
                return format_id
                

        @staticmethod
        def check_plasticity_clipboard_data_is_has():
            format_id = Clipboard.get_plasticity_format_id()

            win32clipboard.OpenClipboard()
            i = win32clipboard.IsClipboardFormatAvailable(format_id)
            win32clipboard.CloseClipboard()
            if i == 1:
                return True
            else:
                return False
            
        
        @staticmethod
        def get_plasticity_clipboard_data(path:str):
            
            format_id = Clipboard.get_plasticity_format_id()
            win32clipboard.OpenClipboard()
            try:
                # 尝试获取剪贴板数据
                clipboard_data = win32clipboard.GetClipboardData(format_id)

                with open(path, 'wb') as file:
                    file.write(clipboard_data)
                    
                print(f"剪贴板数据已保存为二进制文件: {path}")
            except Exception as e:
                print("无法获取剪贴板数据或数据无法保存为二进制格式")

            # 关闭剪贴板
            win32clipboard.CloseClipboard()
        
        @staticmethod
        def set_plasticity_clipboard_data(path:str):
            
            if not os.path.exists(path):
                print("没有文件")
                return
            
            format_id = Clipboard.get_plasticity_format_id()
            # 打开剪贴板
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            
            try:
                with open(path, 'rb') as f:
                    clipboard_data = f.read()
                
                buffer = io.BytesIO()
                buffer.write(clipboard_data)
                win32clipboard.SetClipboardData(format_id,buffer.getvalue())
            except Exception as e:
                print("无法设置剪贴板内容")

            # 关闭剪贴板
            win32clipboard.CloseClipboard()

# print(Clipboard.set_plasticity_clipboard_data(file_path))

class PlasticityInfo(Enum):
    @staticmethod
    def send_plasticity_program_info():
        return "plasticity_program_info_str"
    


class Window_Control(Enum):
    def window_control(hwnd, sw_str):
        match sw_str:
            case "SW_HIDE":
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

            case "SW_SHOW":
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

            case "SW_SHOWNORMAL":
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)

            case "SW_SHOWMINIMIZED":
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMINIMIZED)

            case "SW_SHOWMAXIMIZED":
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)

            case "SW_MAXIMIZE":
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

            case "SW_MINIMIZE":
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

            case "SW_RESTORE":
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)


def websocket_handle(message: str):
    """
    message is like plasticity listener: [command:args], example: SW_MINMIZE:hwnd number -> make window minmize
    """

    _message = message.split(":", 1)

    if len(_message) > 1:
        pass
    else:
        return print(
            "commit message need be like: [Command:args] -> [ SW_MINMIZE:hwnd number ]"
        )

    _menu = _message[0]
    _command = _message[1]

    print("message: ", _menu, _command)

    if bool(re.search(r"^SW_[A-Z]+", _menu)):
        return Window_Control.window_control(hwnd=_command, sw_str=_menu)
    elif bool(re.search(r"^File", _menu)):
        return File.run_command(_command)
    elif bool(re.search(r"Info",_menu)):
        return PlasticityInfo.send_plasticity_program_info()
        pass

    else:
        print(f"not command:{_message}")


# websocket_handle("SW_MINMIZE:000000:222")
