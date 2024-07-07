import psutil
import asyncio
from cdp_payload import cdp_ws_injector,getFileNamePayload



#ws = "ws://127.0.0.1:9223/devtools/page/D1F330B6426643C50C7912FBC0ABAAC7"



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
    process_name = "Plasticity.exe"

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
                
                
                filename =json.loads(asyncio.run(cdp_ws_injector(_ws_url,getFileNamePayload)))["result"]["result"]["value"]
                ws_url_info.append({'name':filename, "url":ws_json["webSocketDebuggerUrl"]})
                #print(ws_json["title"])
                #print(ws_url_info)
                
    print(ws_url_info)
    return ws_url_info

          
