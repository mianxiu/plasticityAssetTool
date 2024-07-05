import websockets
import json
import plasticityCommand
import base64



async def injector_js(ws_url,payload):
    """
    asyncio.run(injector_js(ws_url,payload))
    if not have value, return None
    """
    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps(payload))
        response =await websocket.recv()
        #print(response)
        # try:
        #     return json.loads(response)['result']['result']['value']
        # except:
        #     try:
        #         return json.load(response)['result']['data']
        #     except:
        #         return None
        
        return response

def cdp_payload(*javascript_str:str)-> str:
        """
        return Chrome DevTools Protocol json str
        like:
        
        """
        _expression_str = "".join(javascript_str)
        return json.dumps( {
                'id' : 3,
                'method':'Runtime.evaluate',
                'params':{'expression':f'''{_expression_str}'''}
            })
        

 

javscritpString = open("./plasticity_javascript_payloads/test.js","r",encoding="UTF-8").read()

payload={
    'id' : 1,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''{javscritpString}'''}
}

domPayload = {
    'id' : 2,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''document.querySelectorAll('input')[0].value'''}
}
getFileNamePayload = {
    'id' : 3,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''document.querySelector('#left-sidebar > plasticity-filename > div > span').textContent'''}
}

selectObjectPayload ={
    
}

screenshot_payload={
    "id": 1,
    "method": "Page.captureScreenshot",
    "params": {
        "format": "jpeg",
        "fromSurface": True,
        "clip":{
            "x":368,
            "y":0,
            "width":691,
            "height":687,
            "scale":1
        }
    }
}

# n = plasticityCommand.Command.ALTERNATIVE_DUPLICATE._selector(selector="#viewport > plasticity-viewport > canvas")
# p = plasticityCommand.PointerEvent.POINTER_UP._selector(selector="#viewport > plasticity-viewport > canvas")
# print(n)
# print(p)