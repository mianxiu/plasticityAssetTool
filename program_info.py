import requests
import psutil
import win32process
import win32gui
import json
import cdp_payload
import threading
import pythoncom
import time
import asyncio
from  My_Modules.my_modules import Plasticity_Instance_Info

# class Plasticity_Instance_Info:
#     """
#     ws_url
#     hwnd
#     """
#     def __init__(self,ws_url,hwnd):
#         self.ws_url = ws_url
#         self.hwnd = hwnd
    
#     # @staticmethod
#     def toDict(self):
#         return {
#             "ws_url":self.ws_url,
#             "hwnd":self.hwnd
#         }
     
_PROCESS_NAME = "Plasticity.exe"
_PROCESS_WINDOW_TITLE = "Plasticity"


_HWND_LISTS = []
_CURRENT_WS_JSON_LISTS = []
_PORT = []
_IS_CHECK_PORT = False

PLASTICITY_INSTANCE_INFO = []
_HAS_NEW_CALLBACK = None
_HAS_REMOVE_CALLBACK = None


def get_plastcity_hwnd_lists(process_name:str):
    
    def get_pid_from_hwnd(hwnd):
        _, pid= win32process.GetWindowThreadProcessId(hwnd)
        return pid
    

    def get_process_name(pid):
        return psutil.Process(pid).name()

    
    hwnd_list = []
    time_list = []

    def callback(hwnd, hwnd_list):
        if win32gui.IsWindowVisible(hwnd):
            # try:
                pid =get_pid_from_hwnd(hwnd)
                if get_process_name(pid) == process_name:

                    t = psutil.Process(pid).create_time()
                    hwnd_list.append(hwnd)
                    time_list.append(t)
            # except psutil.NoSuchProcess:
            #     pass
        return True
    

    win32gui.EnumWindows(callback, hwnd_list)
        
    # print(hwnd_list)
    return hwnd_list

async def get_ports_by_process_name(process_name:str):
    ports = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            connections = proc.net_connections()
            for conn in connections:
                if conn.status == 'LISTEN':
                    ports.append(conn.laddr.port)
    return ports
    

session = requests.Session()
session.trust_env = False
async def find_plasticity_cdp_json(ports):

    """
    return
    {
        url:http://localhost:port/json,
        content:[ {
            "description": "",
            "devtoolsFrontendUrl": "/devtools/inspector.html?ws=...",      
            "id": "...",
            "title": "Plasticity",
            "type": "page",
            "url": "file:///F:/P...",
            "webSocketDebuggerUrl": "ws://..."
            } ]
    }
    """

# 获取目标进程的端口列表

    # 打印端口列表
    # print("目标进程", _PROCESS_NAME, "的端口列表:", ports)
        
    # don't use proxy
    if(len(ports) > 0):
        try:
            for p in ports:
                url = f"http://127.0.0.1:{p}/json"
                response = session.get(url,proxies={},timeout=1)

                if response.status_code == 200:
                    content = response.text
                    return {
                        "url":url,"content":json.loads(content)}
                    
        except requests.exceptions.ConnectTimeout:
            print("CDP Server Timeout")
            return
        except requests.exceptions.ConnectionError:
            print("CDP Server Error")

async def get_ws_info():
    """
        {
            "ws_url": ws_url,
            "hwnd":hwnd,
            "filename":filename
        }
    """
    global _IS_CHECK_PORT,_PORT
    


    
    if len(_PORT) == 0:      
        _PORT =await get_ports_by_process_name(_PROCESS_NAME)
        return

    cdp_info =await find_plasticity_cdp_json(ports=_PORT)
    
    if cdp_info is None:
        _PORT.clear()
        _HWND_LISTS.clear()
        _CURRENT_WS_JSON_LISTS.clear()
        await Hwnd_Callback.has_remove_hwnd_callback()
        # await has_new_hwnd_callback()
        print("None Plasticity.exe Runing")
        return
    
    cdp_url = cdp_info["url"]
    cdp_content = cdp_info["content"]
    ws_url_array = [d["webSocketDebuggerUrl"] for d in cdp_content]
    
    _new_ws_url_length = len(ws_url_array)
    _current_ws_json_length = len(_CURRENT_WS_JSON_LISTS)
    _current_hwnd_list_length = len(_HWND_LISTS)
    
    # print(_new_ws_url_length,_current_ws_json_length)
    
    
    # except TypeError:
    #     return
    if _new_ws_url_length > _current_hwnd_list_length:
        await check_new_ws_url(ws_url_array=ws_url_array)
        await check_new_hwnd()
        await Hwnd_Callback.has_new_hwnd_callback()
        

        
        # print(_HWND_LISTS)
        
    elif _new_ws_url_length <_current_hwnd_list_length:
        await check_old_ws_url(ws_url_array=ws_url_array)
        await check_old_hwnd()
        await Hwnd_Callback.has_remove_hwnd_callback()


    elif _new_ws_url_length == _current_hwnd_list_length:
        # await check_new_hwnd_callback()
        pass
    # elif _current_ws_json_length != _current_hwnd_list_length:
        


async def check_new_ws_url(ws_url_array):
        for url in ws_url_array:
            if url not in _CURRENT_WS_JSON_LISTS:
                        _CURRENT_WS_JSON_LISTS.append(url)
                        print("new",url)

async def check_old_ws_url(ws_url_array):
        global _CURRENT_WS_JSON_LISTS
        
        for url in _CURRENT_WS_JSON_LISTS:
            if url not in ws_url_array:
                        _CURRENT_WS_JSON_LISTS.remove(url)
                        print("remove",url)

async def check_new_hwnd():
    loop = asyncio.get_event_loop()
    current_hwnd =await loop.run_in_executor(None,get_plastcity_hwnd_lists,_PROCESS_NAME)

    # is_odd = lambda num:False if num %2==0 else True
    
    # if len(current_hwnd) > 1 and is_odd(len(current_hwnd)) == True:
    #     current_hwnd = list(reversed(current_hwnd))
    
    for n in current_hwnd:
        if n not in _HWND_LISTS:
            _HWND_LISTS.append(n)
            print("new",n)
            # await check_new_hwnd_callback()

async def check_old_hwnd():
    loop = asyncio.get_event_loop()
    current_hwnd =await loop.run_in_executor(None,get_plastcity_hwnd_lists,_PROCESS_NAME)
    for n in _HWND_LISTS:
        if n not in current_hwnd:
            _HWND_LISTS.remove(n)
            print("remove",n)

class Hwnd_Callback:
    @staticmethod
    def clear():
            global PLASTICITY_INSTANCE_INFO
            PLASTICITY_INSTANCE_INFO.clear()
            _HWND_LISTS_LEN = len(_HWND_LISTS) 
           
            if _HWND_LISTS_LEN != 0: 
                print(f"_HWND_LIST_LEN:{_HWND_LISTS_LEN}")
              
            if  _HWND_LISTS_LEN == 2:
                # _HWND_LISTS_FINAL =  reversed(_HWND_LISTS)
                _HWND_LISTS_FINAL =_HWND_LISTS
                pass
            elif _HWND_LISTS_LEN == 3:
                # _HWND_LISTS_FINAL = [_HWND_LISTS[-1]] + _HWND_LISTS[:-1]
                _HWND_LISTS_FINAL = _HWND_LISTS
                pass
            elif _HWND_LISTS_LEN > 4 :
                _HWND_LISTS_FINAL =  reversed(_HWND_LISTS)
            else:
                _HWND_LISTS_FINAL = _HWND_LISTS

            PLASTICITY_INSTANCE_INFO = [Plasticity_Instance_Info(x,y) for x, y in zip(_CURRENT_WS_JSON_LISTS, _HWND_LISTS_FINAL)]
            # print(PLASTICITY_INSTANCE_INFO)
            
    @staticmethod
    async def has_new_hwnd_callback(): 
        def update():
            Hwnd_Callback.clear()
            """ callback """
            if callable(_HAS_NEW_CALLBACK):
                _HAS_NEW_CALLBACK()
            else:
                # print("callback no callable")
                pass 
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None,update)
        
    @staticmethod
    async def has_remove_hwnd_callback():
        def update():
            Hwnd_Callback.clear()
            """ callback """
            if callable(_HAS_REMOVE_CALLBACK):
                _HAS_REMOVE_CALLBACK()
            else:
                # print("callback no callable")
                pass 
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None,update)

def process_listener_callback(has_new_callback=None,has_remove_callback=None):
     global _HAS_NEW_CALLBACK,_HAS_REMOVE_CALLBACK
     _HAS_NEW_CALLBACK = has_new_callback
     _HAS_REMOVE_CALLBACK = has_remove_callback
     

    
def run_process_listener(intervalTimeSec=0.5):
    """
    first time PLASTICITY_INSTANCE_INFO maybe is empty
    after has new hwnd: callback new
    after remove hwnd: callback (even is empty when afte remove)
    """
    async def loop():
        try:
            print("Start Listener...\n------")
            while True:
    
                    await asyncio.sleep(intervalTimeSec)
                    await get_ws_info()
           
        except KeyboardInterrupt:
            print("Stop Listener")
            
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        print("Exit listener")
        
        


if __name__ == "__main__":
    run_process_listener()