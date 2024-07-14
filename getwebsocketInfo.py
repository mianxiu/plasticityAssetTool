import psutil
import asyncio
from cdp_payload import cdp_ws_injector,getFileNamePayload



#ws = "ws://127.0.0.1:9223/devtools/page/D1F330B6426643C50C7912FBC0ABAAC7"

_PROCESS_NAME = "Plasticity.exe"
_PROCESS_WINDOW_TITLE = "Plasticity"

def get_ports_by_process_name(process_name):
    ports = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            connections = proc.net_connections()
            for conn in connections:
                if conn.status == 'LISTEN':
                    ports.append(conn.laddr.port)
    return ports

# 指定目标进程名


def get_plasticity_cdp_url():

    """
    return {'filename':'ws://...'}
    """
    process_name = _PROCESS_NAME

# 获取目标进程的端口列表
    ports = get_ports_by_process_name(process_name)

    # 打印端口列表
    print("目标进程", process_name, "的端口列表:", ports)
        
    
    #
    ws_url_info=[]
    import requests
    import json
    # don't use proxy
    session = requests.Session()
    session.trust_env = False

    for p in ports:
        
        url = f"http://127.0.0.1:{p}/json"
        response = session.get(url,proxies={})
        
        if response.status_code == 200:
            content = response.text
            
            #print(response)
            
            json_data = json.loads(content)
            
            for ws_json in json_data:
                _ws_url = ws_json["webSocketDebuggerUrl"]
                _id = ws_json["id"] 
                _res =  json.loads(asyncio.run(cdp_ws_injector(_ws_url,getFileNamePayload)))
                #print(_res)
                try:
                    filename =_res["result"]["result"]["value"]
                    ws_url_info.append({'name':filename, "url":_ws_url,"id":_id})
                    #print(ws_json["title"])
                    #print(ws_url_info)
                except:
                    pass
                
    print(ws_url_info)
    return ws_url_info

          



EXIST_PLASTICITY_HWND =[]
NEW_PLASTICITY_HWND =[]
import win32gui,win32con,win32process


def check_value_in_dict_array(new_value, dict_array):
        return any(new_value in item.values() for item in dict_array)


def ExistEnumWindowHandle( hwnd, ctx ):
    
    if win32gui.IsWindowVisible( hwnd ):
        name =win32gui.GetWindowText( hwnd )
        if name == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(hwnd,EXIST_PLASTICITY_HWND) == False:
            EXIST_PLASTICITY_HWND.append({
                    "name":_PROCESS_WINDOW_TITLE,
                    "hwnd":hwnd,
                    "pid":win32process.GetWindowThreadProcessId(hwnd)
                })

        # print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )

def NewEnumWindowHandle( hwnd, ctx ):
    if win32gui.IsWindowVisible( hwnd ):
        name =win32gui.GetWindowText( hwnd )
        if name == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(hwnd,EXIST_PLASTICITY_HWND) == False and check_value_in_dict_array(hwnd,NEW_PLASTICITY_HWND) == False:
            NEW_PLASTICITY_HWND.append({
                    "name":_PROCESS_WINDOW_TITLE,
                    "hwnd":hwnd,
                    "pid":win32process.GetWindowThreadProcessId(hwnd)
                })

        # print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )


def reflash_exist_plasticity_window():
    EXIST_PLASTICITY_HWND.clear()
    win32gui.EnumWindows(ExistEnumWindowHandle, None )


def reflash_new_plasticity_window():
    win32gui.EnumWindows(NewEnumWindowHandle,None)
    reflash_exist_plasticity_window()
    
# #6820320 , 20843792
# import win32con
# hwnd =18353662
# win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
# win32gui.SetForegroundWindow(hwnd)


def open_new_file_asset(file_path):
    # def check_pid_has_hwnd(pid):
    #     hwnd = win32gui.FindWindow(None, None)  # 获取顶级窗口的句柄

    #     while hwnd:
    #         found_pid = win32process.GetWindowThreadProcessId(hwnd)
    #         if found_pid == pid:
    #             title = win32gui.GetWindowText(hwnd)     
    #             if title == "Plasticity" & check_value_in_dict_array(hwnd,EXIST_PLASTICITY_HWND):
    #                 print(title)
    #                 return hwnd  # 找到与指定 PID 匹配的窗口句柄

    #         hwnd = win32gui.FindWindowEx(None, hwnd, None, None)  # 获取下一个顶级窗口的句柄

    #     return False  # 未找到与指定 PID 匹配的窗口句柄



    import psutil,subprocess
    reflash_exist_plasticity_window()
    shell_process = subprocess.Popen(f'''cmd.exe /c "{file_path}"''',stdout=subprocess.PIPE) 
    import time
    time.sleep(3)
    reflash_new_plasticity_window()
    print("EXIST-----")
    print(EXIST_PLASTICITY_HWND)
    print("NEW------")
    print(NEW_PLASTICITY_HWND)
    # print("pppppid ",shell_process)
    # try:
    #     parent = psutil.Process(shell_process.pid)
    #     children = parent.children(recursive=True)
    #     #print("child pid",children)
    #     import re
    #     for child in children:

    #         child_pid = child.pid
    #         # print (re.sub(".*pid=(\d{1,}),.*","\1",child))
    #         hwnd = check_pid_has_hwnd(child_pid)
    #         if isinstance(hwnd,int):
    #             print("Plasticity Hwnd: ",hwnd)
    #             win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                
    #     shell_process.terminate()
    # except:
    #     pass
if __name__ == '__main__':
    
    file_path = r'G:\Github\plasticityAssetTool\test file\test 1.plasticity'
    file_path2 =r'G:\Github\plasticityAssetTool\test file\test 2.plasticity'

    open_new_file_asset(file_path=file_path)
#open_new_file_asset(file_path=file_path2)


