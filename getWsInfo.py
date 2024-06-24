import psutil

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
process_name = "Plasticity.exe"

# 获取目标进程的端口列表
ports = get_ports_by_process_name(process_name)

# 打印端口列表
print("目标进程", process_name, "的端口列表:", ports)

def get_plasticity_cdp_url():
    ws_url=[]
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
            print(response)
            json_data = json.loads(content)

            print(json_data[0]["webSocketDebuggerUrl"])

            
get_plasticity_cdp_url()