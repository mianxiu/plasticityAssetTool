
from enum import Enum
import re
import win32gui,win32con

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
    
    




def split_message_to_arg(message:str):
    return message.split(":",1)


def websocket_handle(message:str):
        """
        message is like plasticity listener: [command:args], example: SW_MINMIZE:hwnd number -> make window minmize
        """

        _message = split_message_to_arg(message=message)

        if len(_message) > 1 : pass
        else: 
            return print("commit message need be like: [Command:args] -> [ SW_MINMIZE:hwnd number ]")

        _command = _message[0]
        _args = _message[1]

        print("message: ",_command,_args)

        # if re.match('^SW_',_command) == True:
        #         win32gui.ShowWindow(_args,win32con.SW_MAXIMIZE)

        match _command:
            case "PRINT_MESSAGE":
                pass
            case "SW_HIDE":
                win32gui.ShowWindow(_args,win32con.SW_HIDE)

            case "SW_SHOW":
                win32gui.ShowWindow(_args,win32con.SW_SHOW)

            case "SW_SHOWNORMAL":
                win32gui.ShowWindow(_args,win32con.SW_SHOWNORMAL)

            case "SW_SHOWMINIMIZED":
                win32gui.ShowWindow(_args,win32con.SW_SHOWMINIMIZED)

            case "SW_SHOWMAXIMIZED":
                win32gui.ShowWindow(_args,win32con.SW_SHOWMAXIMIZED)

            case "SW_MAXIMIZE":
                win32gui.ShowWindow(_args,win32con.SW_MAXIMIZE)

            case "SW_MINIMIZE":
                win32gui.ShowWindow(_args,win32con.SW_MINIMIZE)

            case "SW_RESTORE":
                win32gui.ShowWindow(_args,win32con.SW_RESTORE)

           
# websocket_handle("SW_MINMIZE:000000:222")