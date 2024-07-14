import asyncio
from cdp_payload import cdp_ws_injector,cdp_runtime_evaluate_payload,screenshot_payload





def init_panel(websocket_url:str):
    import json

    javscritpString = open("./plasticity-javascript-payloads/init.js","r",encoding="UTF-8").read()
    config = json.loads(open("./config.json","r").read())
    replacements = {
    '%websocket_port%': config["server"]["websocket_port"],
    '%http_port%': config["server"]["http_port"],
    '%show_panel_event_key_code%':config["keymap"]["show_panel_event_key_code"]
    # 添加更多的替换规则
    }
    for key,value in replacements.items():
        javscritpString =  javscritpString.replace(f"`{key}`",str(value))
        
    res = asyncio.run(cdp_ws_injector(websocket_url,cdp_runtime_evaluate_payload(f'''{javscritpString}''')))
    # print(res)
    # print(javscritpString)
init_panel("ws://127.0.0.1:9223/devtools/page/5E1B5B0A279D6E9A62DD1E11F953983A")

def screenshot(websocket_url:str):
    """
    窗口不激活无法截图
    """
    jpeg_response =asyncio.run(cdp_ws_injector(websocket_url,screenshot_payload))
    import json,base64
    jpeg_data = base64.b64decode(json.loads(jpeg_response)["result"]["data"])
    print(jpeg_response)
    with open("./test file/screen.jpg", "wb") as f:
            f.write(jpeg_data)


def isolate_focus(websocket_url:str):
    from plasticitycommand import Viewport,Command
    
    _selector ="#viewport > plasticity-viewport > canvas"
    _f = Viewport.FOCUS._selector(selector=_selector)
    _i = Command.ISOLATE._selector(selector=_selector)
    _t = Viewport.TOGGLE_OVERLAYS._selector(selector=_selector)
    _payload = cdp_runtime_evaluate_payload(_i,_f,_t)
    res = asyncio.run(cdp_ws_injector(websocket_url,_payload))
    print (_payload)
    pass


def select_obj_isolate_focus(websocket_url:str,selector:str):
    from plasticitycommand import PointerEvent
    
    _p =PointerEvent.POINTER_UP._selector(selector=selector)
    # _payload = cdp_runtime_evaluate_payload(_p)
    isolate_focus(websocket_url=websocket_url)

def focus_plasticity_asset_file_window(websocket_url:str):
    pass

def get_filename_from_ws_url(websocket_url:str):
    return

def get_document_tree(websocket_url:str):
    pass



# ws = get_plasticity_cdp_url()
# f = ws[0]["url"]
import win32gui,win32con
def plasticity_window_activate(websocket_url:str):
    pass

def plasticity_winddow_minimize(hwnd):
    win32gui.ShowWindow(hwnd,win32con.SW_MINIMIZE)
    
plasticity_winddow_minimize(1443174)

