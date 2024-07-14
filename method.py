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


# ws = get_plasticity_cdp_url()
# f = ws[0]["url"]

def plasticity_window_activate(websocket_url:str):
    pass

#plasticity_window_activate(f)
# import time
# time.sleep(2)

#screenshot(f)

# import win32gui,win32event

# def get_associated_program_hwnd(file_path):
#     # 创建进程并打开文件

#     pid = win32process.CreateProcess(
#         None,  # 应用程序路径（如果为空，则使用系统关联）
#         f'''cmd.exe /c "{file_path}"''',  # 命令行参数（使用文件路径作为参数）
#         None,
#         None,
#         0,
#         win32process.CREATE_NO_WINDOW,
#         None,
#         None,
#         win32process.STARTUPINFO()
#     )
#     # win32event.WaitForInputIdle(pid[0],3000)
#     print(pid[0])

# # 获取关联程序的窗口句柄
# hwnd = get_associated_program_hwnd(file_path)

# print(f"关联程序的窗口句柄：{hwnd}")