
from enum import Enum
import re
import win32gui,win32con
import tkinter as tk
from tkinter import filedialog

class Websocket_Handle_Message(Enum):
    def __str__(self) -> str:
        return self.value 
    
    PRINT_MESSAGE = "PRINT_MESSAGE",
    SW_HIDE="SW_HIDE",
    SW_SHOW = "SW_SHOW",
    SW_SHOWNORMAL="SW_SHOWNORMAL",
    SW_SHOWMINIMIZED="SW_SHOWMINIMIZED",
    SW_SHOWMAXIMIZED="SW_SHOWMAXIMIZED",
    SW_MAXIMIZE="SW_MAXIMIZE",
    SW_MINIMIZE="SW_MINIMIZE",
    SW_RESTORE = "SW_RESTORE",
    
    
class Menu(Enum):
    def select_plasticity_file():


        # 创建主窗口
        root = tk.Tk()    
        root.iconbitmap("plasticity asset tool.ico")
        
        # top_level = tk.Toplevel(root)
        # top_level.withdraw()
        root.geometry("300x0")
        root.wm_title("plasticity asset tool")

        file_path = filedialog.askopenfilenames(title="Select file", filetypes=(
            ("All files", "*.plasticity *.plasticityassettooldb") ,("Plasticity files", "*.plasticity"),("Plasticity Asset Tool DB", "*.plasticityassettooldb")))

        if file_path:
            print("选择的文件路径为:", file_path)
            root.withdraw()  # 隐藏主窗口
            root.destroy()
            return file_path
        else:
            print("未选择任何文件")
            
        root.withdraw()  # 隐藏主窗口
        root.destroy()


class Window_Control(Enum):
    def window_control(hwnd,sw_str):
        match sw_str:
            case "SW_HIDE":
                win32gui.ShowWindow(hwnd,win32con.SW_HIDE)

            case "SW_SHOW":
                win32gui.ShowWindow(hwnd,win32con.SW_SHOW)

            case "SW_SHOWNORMAL":
                win32gui.ShowWindow(hwnd,win32con.SW_SHOWNORMAL)

            case "SW_SHOWMINIMIZED":
                win32gui.ShowWindow(hwnd,win32con.SW_SHOWMINIMIZED)

            case "SW_SHOWMAXIMIZED":
                win32gui.ShowWindow(hwnd,win32con.SW_SHOWMAXIMIZED)

            case "SW_MAXIMIZE":
                win32gui.ShowWindow(hwnd,win32con.SW_MAXIMIZE)

            case "SW_MINIMIZE":
                win32gui.ShowWindow(hwnd,win32con.SW_MINIMIZE)

            case "SW_RESTORE":
                win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)



def websocket_handle(message:str):
        """
        message is like plasticity listener: [command:args], example: SW_MINMIZE:hwnd number -> make window minmize
        """

        _message =  message.split(":",1)

        if len(_message) > 1 : pass
        else: 
            return print("commit message need be like: [Command:args] -> [ SW_MINMIZE:hwnd number ]")

        _command = _message[0]
        _args = _message[1]

        print("message: ",_command,_args)

        if bool(re.search(r'^SW_[A-Z]+',_command)) == True:
            Window_Control.window_control(hwnd=_args,sw_str=_command) 
        elif _command == "Menu" and _args == "select_plasticity_file":
           return  Menu.select_plasticity_file()
        else:
            print(f"not command:{_message}")

        # match _command:
        #     case "PRINT_MESSAGE":
                
        #         pass


           
# websocket_handle("SW_MINMIZE:000000:222")