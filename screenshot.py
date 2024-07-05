import asyncio
from cdp_payload import injector_js,screenshot_payload
from getWsInfo import get_plasticity_cdp_url


ws=get_plasticity_cdp_url()
"""
窗口不激活无法截图
"""
jpeg_response =asyncio.run(injector_js(ws[0]["url"],screenshot_payload))
import json,base64
jpeg_data = base64.b64decode(json.loads(jpeg_response)["result"]["data"])
print(jpeg_response)
with open("./test file/screen.jpg", "wb") as f:
        f.write(jpeg_data)

