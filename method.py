import asyncio
from cdp_payload import cdp_ws_injector,cdp_runtime_evaluate_payload,screenshot_payload
from getwebsocketInfo import get_plasticity_cdp_url




def init_id(websocket_url:str):
    
    javscritpString = open("./plasticity_javascript_payloads/init.js","r",encoding="UTF-8").read()
    res = asyncio.run(cdp_ws_injector(websocket_url,cdp_runtime_evaluate_payload(f'''{javscritpString}''')))
    print(res)
    
#init_id()


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

def get_document_tree(websocket_url:str):
    pass


ws = get_plasticity_cdp_url()
f = ws[0]["url"]

def plasticity_window_activate(websocket_url:str):
    import re
    tab_id = re.sub(r"(ws.*page\/)(.*)",r"\2",websocket_url)

    # _payload ={
    # "id": 1,
    # "method": "Page.bringToFront",
    # "params": {
    #     "sessionId": tab_id
    #     }
    # }
    _payload ={
    "id": 1,
    "method": "Browser.getWindowForTarget",
    "params": {
        "targetId": tab_id
        }
    }
    
    
    
    print(_payload)
    res = asyncio.run(cdp_ws_injector(websocket_url,_payload))
    print(res)
    import win32gui,win32con
    # 最大化指定窗口
    async def  maximize_window(window_title):
        # 查找窗口句柄
        hwnd = win32gui.FindWindow(None, window_title)
        if hwnd != 0:
            # 最大化窗口

            win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
            #win32gui.SetForegroundWindow(hwnd)

        else:
            print("未找到窗口:", window_title)

    asyncio.run(maximize_window("Plasticity"))

#plasticity_window_activate(f)
# import time
# time.sleep(2)
# screenshot(f)
import win32gui

def winEnumHandler( hwnd, ctx ):
    if win32gui.IsWindowVisible( hwnd ):
        print ( hwnd, hex( hwnd ), win32gui.GetWindowText( hwnd ) )

win32gui.EnumWindows( winEnumHandler, None )
#6820320 , 20843792
import win32con
hwnd =6820320 
win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
win32gui.SetForegroundWindow(hwnd)