import asyncio
from cdp_payload import cdp_ws_injector,cdp_runtime_evaluate_payload,screenshot_payload
import win32gui
import win32con
import json,base64
import time




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
# init_panel("ws://127.0.0.1:9223/devtools/page/5E1B5B0A279D6E9A62DD1E11F953983A")

def screenshot(websocket_url:str):
    """
    窗口不激活无法截图
    """
    jpeg_response =asyncio.run(cdp_ws_injector(websocket_url,screenshot_payload))
   
    jpeg_data = base64.b64decode(json.loads(jpeg_response)["result"]["data"])
    print(jpeg_response)
    with open("./test file/screen.jpg", "wb") as f:
            f.write(jpeg_data)


def isolate_focus(websocket_url:str):
    from plasticity_command import Viewport,Command
    
    _selector ="#viewport > plasticity-viewport > canvas"
    _f = Viewport.FOCUS._selector(selector=_selector)
    _i = Command.ISOLATE._selector(selector=_selector)
    _t = Viewport.TOGGLE_OVERLAYS._selector(selector=_selector)
    _payload = cdp_runtime_evaluate_payload(_i,_f,_t)
    res = asyncio.run(cdp_ws_injector(websocket_url,_payload))
    print (_payload)
    pass


def select_obj_isolate_focus(websocket_url:str,selector:str):
    from plasticity_command import PointerEvent
    
    _p =PointerEvent.POINTER_UP._selector(selector=selector)
    # _payload = cdp_runtime_evaluate_payload(_p)
    isolate_focus(websocket_url=websocket_url)

def focus_plasticity_asset_file_window(websocket_url:str):
    pass

def get_filename_from_ws_url(websocket_url:str):
    time.sleep(1)
    msg = {
        'id':1,
        'method':'Runtime.enable',
    }
    getFileNamePayload = {
    'id' : 3,
    'method':'Runtime.evaluate',
    'params':{'expression':'''document.querySelector('#left-sidebar > plasticity-filename > div').textContent'''}
    }
    
    res1 = asyncio.run(cdp_ws_injector(websocket_url,msg))
    res = asyncio.run(cdp_ws_injector(websocket_url,getFileNamePayload))
    result1=json.loads(res1)
    result = json.loads(res)['result']['result']['value']
    # print(result)
    return result

def get_document_tree(websocket_url:str):
    pass



# ws = get_plasticity_cdp_url()
# f = ws[0]["url"]

def plasticity_window_activate(hwnd:int):
    pass

def plasticity_window_title_change(hwnd,title):
    #win32gui.ShowWindow(hwnd,win32con.SWP_HIDEWINDOW)
    win32gui.SetWindowText(hwnd,title)

title_ico_path_ = r"G:\Github\plasticityAssetTool\test file\ico.ico"

def plasticity_window_icon_change(hwnd,ico_path):
    icon_flags = win32con.LR_LOADFROMFILE
    hicon = win32gui.LoadImage(0, ico_path, win32con.IMAGE_ICON, 0, 0, icon_flags)
    
    # 设置窗口图标
    #win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, hicon)
    win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon)
    

def plasticity_window_setoverlay(hwnd,ico_path):
    import ctypes
    from ctypes import wintypes

    # # 定义常量
    # WM_SETICON = 0x0080
    # ICON_SMALL = 0
    # ICON_BIG = 1

    # 加载 user32.dll
    user32 = ctypes.WinDLL('user32')

    # 定义 ICONINFO 结构体
    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ('fIcon', wintypes.BOOL),
            ('xHotspot', wintypes.DWORD),
            ('yHotspot', wintypes.DWORD),
            ('hbmMask', wintypes.HBITMAP),
            ('hbmColor', wintypes.HBITMAP)
        ]

    icon_flags = win32con.LR_LOADFROMFILE
    hicon = win32gui.LoadImage(0, ico_path, win32con.IMAGE_ICON, 0, 0, icon_flags)

    # 创建 ICONINFO 结构体
    icon_info = ICONINFO()
    user32.GetIconInfo(hicon, ctypes.byref(icon_info))

    # 设置叠加图标

    win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon)
    # user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon_info.hbmMask)
    # user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon_info.hbmColor)

    # 释放资源
    # user32.DeleteObject(icon_info.hbmMask)
    # user32.DeleteObject(icon_info.hbmColor)
    # user32.DestroyIcon(hicon)

    #win32gui.UpdateWindow(hwnd)    
_hwnd = 2367588
#plasticity_window_setoverlay(_hwnd,ico_path=title_ico_path_)
#plasticity_window_icon_change(_hwnd,ico_path=title_ico_path_)
plasticity_window_title_change(_hwnd,"📘(asset) test 22222")




