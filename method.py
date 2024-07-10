import asyncio
from cdp_payload import cdp_ws_injector,cdp_runtime_evaluate_payload,screenshot_payload
from getwebsocketInfo import get_plasticity_cdp_url



websocket_info=get_plasticity_cdp_url()
print(websocket_info)
first = websocket_info[0]["url"]

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
isolate_focus(first)


def focus_plasticity_asset_file_window(websocket_url:str):
    pass

def get_document_tree(websocket_url:str):
    pass

