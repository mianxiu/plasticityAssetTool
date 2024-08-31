from enum import Enum
import re
import win32gui
import win32con
import tkinter as tk
from tkinter import filedialog
from peewee import *
import time
import os
import win32clipboard
import ctypes
import io


RECENT_PATH_DB = "recent_path.db"
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
        PLASTICITY_CUSTOM_FORMAT_NAME = "application/vnd.plasticity.items"


        
        @staticmethod
        def get_plasticity_format_id():
                RegisterClipboardFormat = ctypes.windll.user32.RegisterClipboardFormatA
                format_id = RegisterClipboardFormat(Clipboard.PLASTICITY_CUSTOM_FORMAT_NAME.encode("utf-8"))
                # print(f"Registered custom clipboard format '{PLASTICITY_CUSTOM_FORMAT_NAME}' with ID: {format_id}")
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
            
        print(check_plasticity_clipboard_data_is_has())

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




class File(Enum):
    def run_command(command):
        match command:
            case "select_plasticity_file":
                return File.select_plasticity_file()

    def select_plasticity_file():
        root = tk.Tk()
        root.iconbitmap("plasticity asset tool.ico")
        root.withdraw()

        t = tk.Toplevel(root)
        t.iconbitmap("plasticity asset tool.ico")
        t.geometry("300x0")
        t.wm_title("plasticity asset tool")
        t.wm_attributes("-topmost", True)
        t.wm_attributes("-topmost", False)

        file_paths = filedialog.askopenfilenames(
            title="Select file",
            parent=t,
            filetypes=(
                ("All files", "*.plasticity *.plasticityassettooldb"),
                ("Plasticity files", "*.plasticity"),
                ("Plasticity Asset Tool DB", "*.plasticityassettooldb"),
            ),
        )

        if file_paths and len(file_paths) > 0:
            root.destroy()
            File.write_recent_db_file(file_paths)
            return file_paths

        root.destroy()

    def open_plasticity_file(file_path: str):
        pass

    def open_plasticity_asset_tool_db(file_path: str):
        pass

    def write_recent_db_file(file_paths: list):
        db = SqliteDatabase(f"{RECENT_PATH_DB}")
        db.connect()

        class FilePath(Model):
            name = CharField()
            path = CharField()
            last_read_date = TimeField()
            has_db = BooleanField()

            class Meta:
                database = db

        db.create_tables([FilePath])

        # 插入文件路径数据
        for file in file_paths:
            filename = os.path.basename(file)
            l = time.time()
            s = FilePath.create(
                name=f"{filename}", path=file, last_read_date=l, has_db=False
            )
            s.has_db = True
            s.save()

        for file_paths in FilePath.select():
            print(file_paths.path)
        # 关闭数据库连接
        db.close()
        pass

    def read_recent_db_file(file_paths: list):
        pass


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

    else:
        print(f"not command:{_message}")


# websocket_handle("SW_MINMIZE:000000:222")
