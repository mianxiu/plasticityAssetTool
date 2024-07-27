
import asyncio
import multiprocessing.process

import websockets
from webui import webui
import multiprocessing

HTTP_PORT = 15150
WEBSOCKET_PORT = 15151

async def handler(websocket):
    while True:
        message = await websocket.recv()
        print(message)


async def websocket_server():
    print(f"websocket server run on port: ws://127.0.0.1:{WEBSOCKET_PORT}")
    async with websockets.serve(handler, "", WEBSOCKET_PORT):
        await asyncio.Future()  # run forever


# run gui serve
from bottle import route, run, static_file

@route('/')
def serve_index():
    return static_file('index.html', root='plasticity-asset-tool-app/dist')

@route('/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root='plasticity-asset-tool-app/dist')




def run_http_server():
    run(host='localhost', port=HTTP_PORT)
    

def run_all_server_with_websocket():
    asyncio.run(websocket_server())

    # _http = asyncio.create_task(run_http_server())

 
def run_webui():
    MyWindow = webui.window()
    MyWindow.set_size(800,640)
    MyWindow.show( rf"http://127.0.0.1:{HTTP_PORT}/")
    webui.wait()
    
    

if __name__ == "__main__":
    
    # websocket_thread = threading.Thread(target=run_websocket_server)
    # websocket_thread.start()
    # asyncio.run(run_http_server())
    # asyncio.run(run_websocket_server())
    # asyncio.run(run_all_server_with_websocket())
    
    _p_1 = multiprocessing.Process(target=run_all_server_with_websocket)
    _p_1.daemon = True
    _p_2 = multiprocessing.Process(target=run_http_server)
    _p_2.daemon = True
    
    _p_3 = multiprocessing.Process(target=run_webui)
    
    _p_1.start()
    _p_2.start()
    _p_3.start()
    
    _p_1.join()
    _p_2.join()
    _p_3.join()


    

   
    

