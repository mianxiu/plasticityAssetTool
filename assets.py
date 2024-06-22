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

async def hello():
    async with websockets.connect("ws://127.0.0.1:9223/devtools/page/B92BF01F324E72FD6182CE407B1E10AD") as websocket:
        d = await websocket.send(json.dumps(payload))
        g =await websocket.recv()
        print(d)

asyncio.run(hello())