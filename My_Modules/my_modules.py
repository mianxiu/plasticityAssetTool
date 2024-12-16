import json

class Plasticity_Instance_Info:
    """
    ws_url
    hwnd
    """
    def __init__(self,ws_url,hwnd):
        self.ws_url = ws_url
        self.hwnd = hwnd
    def __str__(self) -> str:
        return str({"ws_url":self.ws_url,"hwnd":self.hwnd})
    def __repr__(self) -> str:
        return str({"ws_url":self.ws_url,"hwnd":self.hwnd})

    # @staticmethod
    def toDict(self):
        return {
            "ws_url":self.ws_url,
            "hwnd":self.hwnd
        }
     
class Plasticity_Instance_Info_List(list):
         pass
         

class Webscoket_Send_Message:
    """
    is_for_all:bool
    msg:list
    """
    def __init__(self,is_for_all:bool,msg:list) :
        self.is_for_all = is_for_all
        self.msg = msg
    
    def __str__(self) -> str:
         return json.dumps({
             "is_for_all":self.is_for_all,
             "msg" : self.msg
         })
    
    
    def __repr__(self) -> str:
         return json.dumps({
             "is_for_all":self.is_for_all,
             "msg" : self.msg
         })
        
    def get(self)->dict:
        return {
             "is_for_all":self.is_for_all,
             "msg" : self.msg
         }
        