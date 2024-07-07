import asyncio
from cdp_payload import cdp_ws_injector,cdp_runtime_evaluate_payload,screenshot_payload,input_EnterKey_payload
from getwebsocketInfo import get_plasticity_cdp_url


def init_id():

    ws=get_plasticity_cdp_url()
    
    first = ws[0]["url"]
    javscritpString = open("./plasticity_javascript_payloads/init.js","r",encoding="UTF-8").read()
    res = asyncio.run(cdp_ws_injector(first,cdp_runtime_evaluate_payload(f'''{javscritpString}''')))
    print(res)
    
init_id()


def screenshot():
    ws=get_plasticity_cdp_url()
    """
    窗口不激活无法截图
    """
    jpeg_response =asyncio.run(cdp_ws_injector(ws[0]["url"],screenshot_payload))
    import json,base64
    jpeg_data = base64.b64decode(json.loads(jpeg_response)["result"]["data"])
    print(jpeg_response)
    with open("./test file/screen.jpg", "wb") as f:
            f.write(jpeg_data)

