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


def get_plasticity_cdp_url():

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
            return content
    
                
EXIST_PLASTICITY_WEBSOCKET_JSON = []
NEW_PLASTICITY_WEBSOCKET_JSON = []


def reflash_exist_websocket_json(dev_json_content):
        if dev_json_content is None : return
        #print(dev_json_content)
        EXIST_PLASTICITY_WEBSOCKET_JSON.clear()
        
        json_data = json.loads(dev_json_content)

        for ws_json in json_data:
            _ws_url = ws_json["webSocketDebuggerUrl"]
            _id = ws_json["id"] 
            _title = ws_json["title"]
            
            if _title == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(_ws_url,EXIST_PLASTICITY_WEBSOCKET_JSON)==False:
                # _res =  json.loads(asyncio.run(cdp_ws_injector(_ws_url,getFileNamePayload)))

                # filename =_res["result"]["result"]["value"]
                EXIST_PLASTICITY_WEBSOCKET_JSON.append({
                     "url":_ws_url,
                     "id":_id
                     })
        
        print("Exist Plasticity websocket json: ",EXIST_PLASTICITY_WEBSOCKET_JSON)
                #print(ws_json["title"])
                #print(ws_url_info)


def reflash_new_websocket_json(dev_json_content):
        if dev_json_content is None : return
        
        json_data = json.loads(dev_json_content)

        for ws_json in json_data:
            _ws_url = ws_json["webSocketDebuggerUrl"]
            _id = ws_json["id"] 
            _title = ws_json["title"]
            
            if _title == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(_ws_url,EXIST_PLASTICITY_WEBSOCKET_JSON)==False and check_value_in_dict_array(_ws_url,NEW_PLASTICITY_WEBSOCKET_JSON)==False:

                EXIST_PLASTICITY_WEBSOCKET_JSON.append({
                     "url":_ws_url,
                     "id":_id
                     })

        reflash_exist_websocket_json(dev_json_content=dev_json_content)

        print("New Plasticity websocket json: ",EXIST_PLASTICITY_WEBSOCKET_JSON)








EXIST_PLASTICITY_HWND =[]
NEW_PLASTICITY_HWND =[]

import win32gui,win32process
class Plasticity_Window:

    @staticmethod
    def ExistEnumWindowHandle(hwnd, ctx ):
        if win32gui.IsWindowVisible( hwnd ):
            name =win32gui.GetWindowText( hwnd )
            if name == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(hwnd,EXIST_PLASTICITY_HWND) == False:
                EXIST_PLASTICITY_HWND.append({
                        "title":_PROCESS_WINDOW_TITLE,
                        "hwnd":hwnd,
                        "pid":win32process.GetWindowThreadProcessId(hwnd)
                    })

            # print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )
    @staticmethod
    def NewEnumWindowHandle(hwnd, ctx ):
        if win32gui.IsWindowVisible( hwnd ):
            name =win32gui.GetWindowText( hwnd )
            if name == _PROCESS_WINDOW_TITLE and check_value_in_dict_array(hwnd,EXIST_PLASTICITY_HWND) == False and check_value_in_dict_array(hwnd,NEW_PLASTICITY_HWND) == False:
                NEW_PLASTICITY_HWND.append({
                        "title":_PROCESS_WINDOW_TITLE,
                        "hwnd":hwnd,
                        "pid":win32process.GetWindowThreadProcessId(hwnd)
                    })

            # print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )
    
    @staticmethod
    def reflash_exist_plasticity_window():
        EXIST_PLASTICITY_HWND.clear()
        win32gui.EnumWindows(Plasticity_Window.ExistEnumWindowHandle, None )
    
    @staticmethod
    def reflash_new_plasticity_window():
        win32gui.EnumWindows(Plasticity_Window.NewEnumWindowHandle,None)
        Plasticity_Window.reflash_exist_plasticity_window()
        
    # #6820320 , 20843792
    # import win32con
    # hwnd =18353662
    # win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
    # win32gui.SetForegroundWindow(hwnd)

    @staticmethod
    def open_new_file_asset(file_path):
        import psutil,subprocess
        Plasticity_Window.reflash_exist_plasticity_window()
        shell_process = subprocess.Popen(f'''cmd.exe /c "{file_path}"''',stdout=subprocess.PIPE) 
        import time
        time.sleep(3)
        Plasticity_Window.reflash_new_plasticity_window()
        print("EXIST-----")
        print(EXIST_PLASTICITY_HWND)
        print("NEW------")
        print(NEW_PLASTICITY_HWND)

if __name__ == '__main__':
    
    file_path = r'G:\Github\plasticityAssetTool\test file\test 1.plasticity'
    file_path2 =r'G:\Github\plasticityAssetTool\test file\test 2.plasticity'

    #Plasticity_Window.open_new_file_asset(file_path=file_path)
    content = get_plasticity_cdp_url()
    reflash_exist_websocket_json(dev_json_content=content)
    reflash_new_websocket_json(content)

#open_new_file_asset(file_path=file_path2)


