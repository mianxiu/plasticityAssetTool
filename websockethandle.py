#!/usr/bin/env python

import asyncio
import websockets

async def handler(websocket):
    while True:
        message = await websocket.recv()
        print(message)


async def web_socket_server():
    async with websockets.serve(handler, "", 15151):
        await asyncio.Future()  # run forever


# run gui serve
from bottle import route, run, static_file

@route('/')
def serve_index():
    return static_file('index.html', root='plasticity-asset-tool-app/dist')

@route('/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root='plasticity-asset-tool-app/dist')


if __name__ == "__main__":
    run(host='localhost', port=15150)
    asyncio.run(web_socket_server())