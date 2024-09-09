import requests
import psutil
import win32process
import win32gui
import json
import cdp_payload
import wmi
import threading
import pythoncom


_PROCESS_NAME = "Plasticity.exe"
_PROCESS_WINDOW_TITLE = "Plasticity"

_HWND_LEN = 0

def get_pid_from_hwnd(hwnd):
    _, pid= win32process.GetWindowThreadProcessId(hwnd)
    return pid
    
def get_process_name(pid):
    return psutil.Process(pid).name()

def get_plastcity_hwnd_lists(process_name:str):
    hwnd_list = []
    time_list = []

    def callback(hwnd, hwnd_list):
        if win32gui.IsWindowVisible(hwnd):
            try:
                pid = get_pid_from_hwnd(hwnd)
                if get_process_name(pid) == process_name:

                    t = psutil.Process(pid).create_time()
                    hwnd_list.append(hwnd)
                    time_list.append(t)
            except psutil.NoSuchProcess:
                pass
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
        
        
def get_ws_info():
    """
        {
            "ws_url": ws_url,
            "hwnd":hwnd,
            "filename":filename
        }
    """
    ws_info_lists = []
    try:
        cdp_info = find_plasticity_cdp_json()
        cdp_url = cdp_info["url"]
        cdp_content = cdp_info["content"]
        
    except TypeError:
        return
    
    for cdp_json in cdp_content:
        ws_url = cdp_json["webSocketDebuggerUrl"]
        try:
            filename = json.loads(
                cdp_payload.cdp_ws_injector_sync(
                    ws_url=ws_url,payload=cdp_payload.getFileNamePayload))["result"]["result"]["value"]
        except KeyError: 
            pass
        ws_info_lists.append({
            "ws_url": ws_url,
            # "hwnd":hwnd,
            "filename":filename
        })
                   
    return ws_info_lists

def get_program_info():
    """
    [
        {hwnd:ws_info}
    ]
    """
    
    info_list = {}
    
    ws_info = get_ws_info()
    try:
        hwnd_lists = get_plastcity_hwnd_lists(_PROCESS_NAME)
    except TypeError:
        return
    
    for ws,hwnd in zip(ws_info,hwnd_lists):
        filename = ws["filename"]
        # for hwnd in hwnd_lists:
        win32gui.SetWindowText(hwnd,filename)
        info_list[hwnd] = ws
        
    # for key in info_list:
      
    #     for hwnd in hwnd_lists:
    #         filename = info_list[key]["filename"]
    #         current_window_text = win32gui.GetWindowText(hwnd)
    #         if current_window_text != filename:
    #             print(current_window_text,"- hwnd:",hwnd)
    #             win32gui.SetWindowText(hwnd,filename)
    #         # print(hwnd)
    #     print(info_list[key])

        pass
            
        # info["hwnd"] = hwnd

    print(info_list)
    
    # for p in program_info:
    #     win32gui.SetWindowText(p["hwnd"],p["filename"])

def process_creation_listener():
    try:
        print("----wmi listener----")
        pythoncom.CoInitialize()
        c = wmi.WMI()
        process_watcher = c.Win32_Process.watch_for("creation",name="Plasticity.exe")
        while True:
            new_process = process_watcher()
            print("进程创建：", new_process.Caption)
    except KeyboardInterrupt:
        print("捕捉到 Ctrl + C，退出监听循环")

# process_creation_listener()
def run_process_creation_listener():
    t = threading.Thread(target=process_creation_listener)
    t.daemon = True
    t.start()
    while t.is_alive():
        t.join(timeout=1)
        # for _ in range(_HWND_LEN):
        #     pass

run_process_creation_listener()