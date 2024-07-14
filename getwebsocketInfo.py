import psutil
import asyncio
from cdp_payload import cdp_ws_injector,getFileNamePayload
import requests,json



#ws = "ws://127.0.0.1:9223/devtools/page/D1F330B6426643C50C7912FBC0ABAAC7"
def check_value_in_dict_array(new_value, dict_array):
        return any(new_value in item.values() for item in dict_array)
    

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

_CDP_JSON_URL = ""
def find_init_plasticity_cdp_json_url_response():
    global _CDP_JSON_URL
    """
    get http://localhost:port/json
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
            _CDP_JSON_URL = url
            return content
    
def reflash_plasticity_cdp_json_response():
        # don't use proxy
    session = requests.Session()
    session.trust_env = False
    response = session.get(_CDP_JSON_URL,proxies={})
    if response.status_code == 200:
        content = response.text
        return content
                
                
                
_EXIST_PLASTICITY_WEBSOCKET_JSON = []
_NEW_PLASTICITY_WEBSOCKET_JSON = []
def reflash_exist_websocket_json(dev_json_content):
    """
    {
        url:"ws://....",
        "id":id
    }
    """
    global _EXIST_PLASTICITY_WEBSOCKET_JSON,_NEW_PLASTICITY_WEBSOCKET_JSON
    if dev_json_content is None : return
    #print(dev_json_content)
    _EXIST_PLASTICITY_WEBSOCKET_JSON.clear()
    
    json_data = json.loads(dev_json_content)

    for ws_json in json_data:
        _ws_url = ws_json["webSocketDebuggerUrl"]
        _id = ws_json["id"] 
        _title = ws_json["title"]
        
        if _title == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(_ws_url,_EXIST_PLASTICITY_WEBSOCKET_JSON)==False:
            # _res =  json.loads(asyncio.run(cdp_ws_injector(_ws_url,getFileNamePayload)))

            # filename =_res["result"]["result"]["value"]
            _EXIST_PLASTICITY_WEBSOCKET_JSON.append({
                    "url":_ws_url,
                    "id":_id
                    })
    
    #print("Exist Plasticity websocket json: \n",_EXIST_PLASTICITY_WEBSOCKET_JSON)
            #print(ws_json["title"])
            #print(ws_url_info)

def reflash_new_websocket_json(dev_json_content):
        global _EXIST_PLASTICITY_WEBSOCKET_JSON,_NEW_PLASTICITY_WEBSOCKET_JSON
        """
    {
        url:"ws://....",
        "id":id
    }
    """
        if dev_json_content is None : return
        
        json_data = json.loads(dev_json_content)

        for ws_json in json_data:
            _ws_url = ws_json["webSocketDebuggerUrl"]
            _id = ws_json["id"] 
            _title = ws_json["title"]
            
            if _title == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(_ws_url,_EXIST_PLASTICITY_WEBSOCKET_JSON)==False and check_value_in_dict_array(_ws_url,_NEW_PLASTICITY_WEBSOCKET_JSON)==False:
                _NEW_PLASTICITY_WEBSOCKET_JSON.clear()
                _NEW_PLASTICITY_WEBSOCKET_JSON.append({
                     "url":_ws_url,
                     "id":_id
                     })

        reflash_exist_websocket_json(dev_json_content=dev_json_content)

        #print("New Plasticity websocket json: \n",_EXIST_PLASTICITY_WEBSOCKET_JSON)






_EXIST_PLASTICITY_HWND =[]
_NEW_PLASTICITY_HWND =[]

import win32gui,win32process
class Plasticity_Window:

    @staticmethod
    def __ExistEnumWindowHandle(hwnd, ctx ):
        if win32gui.IsWindowVisible( hwnd ):
            name =win32gui.GetWindowText( hwnd )
            if name == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(hwnd,_EXIST_PLASTICITY_HWND) == False:
                _EXIST_PLASTICITY_HWND.append({
                        "title":_PROCESS_WINDOW_TITLE,
                        "hwnd":hwnd,
                        "pid":win32process.GetWindowThreadProcessId(hwnd)
                    })

            # print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )
    @staticmethod
    def __NewEnumWindowHandle(hwnd, ctx ):
        if win32gui.IsWindowVisible( hwnd ):
            name =win32gui.GetWindowText( hwnd )
            if name == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(hwnd,_EXIST_PLASTICITY_HWND) == False and check_value_in_dict_array(hwnd,_NEW_PLASTICITY_HWND) == False:
                _NEW_PLASTICITY_HWND.clear()
                _NEW_PLASTICITY_HWND.append({
                        "title":_PROCESS_WINDOW_TITLE,
                        "hwnd":hwnd,
                        "pid":win32process.GetWindowThreadProcessId(hwnd)
                    })

            # print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )
    
    @staticmethod
    def reflash_exist_plasticity_window():
        """
                _EXIST_PLASTICITY_HWND.append({
                "title":_PROCESS_WINDOW_TITLE,
                "hwnd":hwnd,
                "pid":win32process.GetWindowThreadProcessId(hwnd)
            })

        """
        #_EXIST_PLASTICITY_HWND.clear()
        win32gui.EnumWindows(Plasticity_Window.__ExistEnumWindowHandle, None )
    
    @staticmethod
    def reflash_new_plasticity_window():
        """
                _EXIST_PLASTICITY_HWND.append({
                "title":_PROCESS_WINDOW_TITLE,
                "hwnd":hwnd,
                "pid":win32process.GetWindowThreadProcessId(hwnd)
            })

        """
        win32gui.EnumWindows(Plasticity_Window.__NewEnumWindowHandle,None)
        Plasticity_Window.reflash_exist_plasticity_window()
        
    # #6820320 , 20843792
    # import win32con
    # hwnd =18353662
    # win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
    # win32gui.SetForegroundWindow(hwnd)

ISOPEN_PLASTICITY_ASSET_FILE_INFO = []

def open_new_file_asset(file_path,sleep_time=0):
    """
    has reflash websocket json 
    """
    import psutil,subprocess
    # before create process to reflash 
    _cdp_content = find_init_plasticity_cdp_json_url_response()
    Plasticity_Window.reflash_exist_plasticity_window()
    reflash_exist_websocket_json(dev_json_content=_cdp_content)
    print("Before Plasticity websocket json: \n",_EXIST_PLASTICITY_WEBSOCKET_JSON)
    shell_process = subprocess.Popen(f'''cmd.exe /c "{file_path}"''',stdout=subprocess.PIPE) 
    import time
    time.sleep(sleep_time)
    _cdp_content = reflash_plasticity_cdp_json_response()
    Plasticity_Window.reflash_new_plasticity_window()
    # print("EXIST-----")
    # print(_EXIST_PLASTICITY_HWND)
    # print("NEW------")
    # print(_NEW_PLASTICITY_HWND)

    reflash_new_websocket_json(dev_json_content=_cdp_content)
    
    print("Exist Plasticity websocket json: \n",_EXIST_PLASTICITY_WEBSOCKET_JSON)
    
    if check_value_in_dict_array(_NEW_PLASTICITY_HWND[0]["hwnd"],ISOPEN_PLASTICITY_ASSET_FILE_INFO)==False:
        ISOPEN_PLASTICITY_ASSET_FILE_INFO.append({
            "title":_NEW_PLASTICITY_HWND[0]["title"],
            "hwnd":_NEW_PLASTICITY_HWND[0]["hwnd"],
            "url":_NEW_PLASTICITY_WEBSOCKET_JSON[0]["url"]
        })

if __name__ == '__main__':
    
    file_path = r'G:\Github\plasticityAssetTool\test file\test 1.plasticity'
    file_path2 =r'G:\Github\plasticityAssetTool\test file\test 2.plasticity'

    open_new_file_asset(file_path=file_path,sleep_time=3)
    #open_new_file_asset(file_path=file_path2,sleep_time=3)
    print(ISOPEN_PLASTICITY_ASSET_FILE_INFO)


