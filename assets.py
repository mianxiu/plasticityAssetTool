#!/usr/bin/env python

import asyncio
import websockets
import json


javscritpString = open("./test file/test.js","r",encoding="UTF-8").read()

payload={
    'id' : 1337,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''{javscritpString}'''}
}

domPayload = {
    'id' : 1337,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''document.querySelectorAll('input')[0].value'''}
}
import struct
async def injectorJs():
    async with websockets.connect("ws://127.0.0.1:9223/devtools/page/D1F330B6426643C50C7912FBC0ABAAC7") as websocket:
        
       # d = await websocket.send(json.dumps(domPayload))
        e = await websocket.send(json.dumps(domPayload))
        g =await websocket.recv()
        print(g)

asyncio.run(injectorJs())