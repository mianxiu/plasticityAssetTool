
from enum import Enum

class Websocket_Handle_Message(Enum):
    def __str__(self) -> str:
        return self.value 
    
    PRINT_MESSAGE = "PRINT_MESSAGE",
    SW_HIDE="SW_HIDE",
    SW_SHOW = "SW_SHOW"
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
    
   match _command:
            case "PRINT_MESSAGE":
                pass
            case"SW_HIDE":
                pass
            case "SW_SHOW":
                pass
            case"SW_SHOWNORMAL":
                pass
            case"SW_SHOWMINIMIZED":
                pass
            case"SW_SHOWMAXIMIZED":
                pass
            case"SW_MAXIMIZE":
                pass
            case"SW_MINIMIZE":
                pass
            case "SW_RESTORE":
                pass
           
# websocket_handle("SW_MINMIZE:000000:222")