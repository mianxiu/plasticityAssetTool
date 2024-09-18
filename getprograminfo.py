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


_PROCESS_NAME = "Plasticity.exe"
_PROCESS_WINDOW_TITLE = "Plasticity"


_HWND_LISTS = []
_CURRENT_WS_JSON = []
_PORT = []
_IS_CHECK_PORT = False


def get_pid_from_hwnd(hwnd):
    _, pid= win32process.GetWindowThreadProcessId(hwnd)
    return pid
    
def get_process_name(pid):
    return psutil.Process(pid).name()

async def get_plastcity_hwnd_lists(process_name:str):
    hwnd_list = []
    time_list = []

    def callback(hwnd, hwnd_list):
        if win32gui.IsWindowVisible(hwnd):
            # try:
                pid = get_pid_from_hwnd(hwnd)
                if get_process_name(pid) == process_name:

                    t = psutil.Process(pid).create_time()
                    hwnd_list.append(hwnd)
                    time_list.append(t)
            # except psutil.NoSuchProcess:
            #     pass
        return True
    

    win32gui.EnumWindows(callback, hwnd_list)
        
    print(hwnd_list)
    return hwnd_list

def get_ports_by_process_name(process_name:str):
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
            print("cccc")
            return 

async def get_ws_info():
    """
        {
            "ws_url": ws_url,
            "hwnd":hwnd,
            "filename":filename
        }
    """
    global _IS_CHECK_PORT,_PORT
    
    ws_info_lists = []

    # try:
    # print(_IS_CHECK_PORT)
    # print(_PORT)
    # print(len(_PORT))
    
    if len(_PORT) == 0:      
        _PORT = get_ports_by_process_name(_PROCESS_NAME)
        return
        
    # elif (_IS_CHECK_PORT is False) and (len(_PORT) > 0) :
    #         _IS_CHECK_PORT = True
    #         print(_PORT)      
    # else:
    #     return
    
    # else:
    #     return
    # except TypeError:
    #     _IS_CHECK_PORT = False
    #     print("Not Port Or Not Plasticity Runing")
    #     return
    # if _IS_CHECK_PORT is False:
    #     return
    # try:
    cdp_info =await find_plasticity_cdp_json(ports=_PORT)
    
    if cdp_info is None:
        _PORT.clear()
        _HWND_LISTS.clear()
        print("None Plasticity Runing")
        return
    
    cdp_url = cdp_info["url"]
    cdp_content = cdp_info["content"]
    ws_url_array = [d["webSocketDebuggerUrl"] for d in cdp_content]
    
    ws_url_length = len(ws_url_array)
    _current_ws_json_length = len(_CURRENT_WS_JSON)
    
    # print(ws_url_length,_current_ws_json_length)
    
    
    # except TypeError:
    #     return
    if ws_url_length > _current_ws_json_length:
        await check_new_ws_url(ws_url_array=ws_url_array)
        await check_new_hwnd()
        # print(_HWND_LISTS)
        
    elif ws_url_length < _current_ws_json_length:
        await check_old_ws_url(ws_url_array=ws_url_array)
        await check_old_hwnd()

            # filename = json.loads(
            #     cdp_payload.cdp_ws_injector_sync(
            #         ws_url=ws_url,payload=cdp_payload.getFileNamePayload))["result"]["result"]["value"]

    # return ws_info_lists

def get_program_info():
    """
    [
        {hwnd:ws_info}
    ]
    """
    
    info_list = {}
    
    ws_info = get_ws_info()
    # try:
    hwnd_lists = get_plastcity_hwnd_lists(_PROCESS_NAME)
    # except TypeError:
    #     return
    
    for ws,hwnd in zip(ws_info,hwnd_lists):
        filename = ws["filename"]
        # for hwnd in hwnd_lists:
        win32gui.SetWindowText(hwnd,filename)
        info_list[hwnd] = ws
        
        pass
            
        # info["hwnd"] = hwnd

    print(info_list)
    
    # for p in program_info:
    #     win32gui.SetWindowText(p["hwnd"],p["filename"])

async def check_new_ws_url(ws_url_array):
        for url in ws_url_array:
            if url not in _CURRENT_WS_JSON:
                        _CURRENT_WS_JSON.append(url)
                        print("new",url)

async def check_old_ws_url(ws_url_array):
        global _CURRENT_WS_JSON
        
        # cdp_content_set = set(ws_url_array)
        for url in _CURRENT_WS_JSON:

            if url not in ws_url_array:
                        _CURRENT_WS_JSON.remove(url)
                        print("remove",url)
        # result = [x for x in _CURRENT_WS_JSON if x in cdp_content_set]
        
        # _CURRENT_WS_JSON = result




async def check_new_hwnd():
    current_hwnd =await get_plastcity_hwnd_lists(_PROCESS_NAME)
    for n in current_hwnd:
        if n not in _HWND_LISTS:
            _HWND_LISTS.append(n)
            print("new",n)

async def check_old_hwnd():
    current_hwnd =await get_plastcity_hwnd_lists(_PROCESS_NAME)
    for n in _HWND_LISTS:
        if n not in current_hwnd:
            _HWND_LISTS.remove(n)
            print("remove",n)


    
async def run_process_listener():
    try:
        print("start listener...")
        while True:
                # time.sleep(0.3)
                await asyncio.sleep(0.5)
                await get_ws_info()
                # print(get_ws_info())
    except KeyboardInterrupt:
        print("stop listener")

if __name__ == "__main__":
    try:
        asyncio.run(run_process_listener())
    except KeyboardInterrupt:
        print("Exit listener")
