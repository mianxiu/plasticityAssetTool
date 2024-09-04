import requests
import psutil
import win32process
import win32gui
import json
import cdp_payload
import asyncio

_PROCESS_NAME = "Plasticity.exe"
_PROCESS_WINDOW_TITLE = "Plasticity"



def get_pid_from_hwnd(hwnd):
    _, pid= win32process.GetWindowThreadProcessId(hwnd)
    return pid
    
def get_process_name(pid):
    return psutil.Process(pid).name()

def get_plastcity_hwnd_lists(process_name:str):
    hwnd_list = []

    def callback(hwnd, hwnd_list):
        if win32gui.IsWindowVisible(hwnd):
            try:
                pid = get_pid_from_hwnd(hwnd)
                if get_process_name(pid) == process_name:
                    hwnd_list.append(hwnd)
            except psutil.NoSuchProcess:
                pass
        return True

    win32gui.EnumWindows(callback, hwnd_list)

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

def find_plasticity_cdp_json():

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
    ports = get_ports_by_process_name(_PROCESS_NAME)

    # 打印端口列表
    print("目标进程", _PROCESS_NAME, "的端口列表:", ports)
        
    # don't use proxy
    session = requests.Session()
    session.trust_env = False

    for p in ports:
        
        url = f"http://127.0.0.1:{p}/json"
        response = session.get(url,proxies={})
        if response.status_code == 200:
            content = response.text
            
            return {
                "url":url,"content":json.loads(content)}
        
        
def get_program_info():
    info_lists = []
    
    cdp_info = find_plasticity_cdp_json()
    cdp_url = cdp_info["url"]
    cdp_content = cdp_info["content"]
    hwnd_lists = get_plastcity_hwnd_lists(_PROCESS_NAME)
    
    for cdp_json,hwnd in zip(cdp_content,hwnd_lists):
        ws_url = cdp_json["webSocketDebuggerUrl"]
        try:
            filename = json.loads(
                cdp_payload.cdp_ws_injector_sync(
                    ws_url=ws_url,payload=cdp_payload.getFileNamePayload))["result"]["result"]["value"]
        except KeyError: 
            pass
        info_lists.append({
            "ws_url": ws_url,
            "hwnd":hwnd,
            "filename":filename
        })
        win32gui.SetWindowText(hwnd,filename)
    return info_lists

print(get_program_info())
        
        

