
import asyncio

import tornado.websocket

from webui import webui


import tornado

HTTP_PORT = 15150
WEBSOCKET_PORT = 15151

# async def handler(websocket):
#     while True:
#         try:
#             message = await websocket.recv()
#         except websockets.ConnectionClosedOK:
#             break
        
#         print(message)
        
# async def websocket_server():
#     print(f"websocket server run on port: ws://127.0.0.1:{WEBSOCKET_PORT}")
#     async with websockets.serve(handler, "", WEBSOCKET_PORT):
#         await asyncio.Future()  # run forever


# # run gui serve
# from bottle import route, run, static_file

# @route('/')
# def serve_index():
#     return static_file('index.html', root='plasticity-asset-tool-app/dist')

# @route('/<filepath:path>')
# def serve_static(filepath):
#     return static_file(filepath, root='plasticity-asset-tool-app/dist')

class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        print(f"from {message}")
        self.write_message(f"Received message: {message}")

    def on_close(self):
        print("WebSocket closed")

    def check_origin(self, origin):
        return True
    
    
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")
      

settings ={
    'template_path':"./plasticity-asset-tool-app/dist/",
    "static_path": "./plasticity-asset-tool-app/dist/assets/"
} 


html_root = r"plasticity-asset-tool-app/dist/"
def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/websocket", WSHandler),
         (r"/(.*)", tornado.web.StaticFileHandler, {"path": html_root, "default_filename": r"./index.html"}),
        
    ],debug=True,**settings)

async def run_http_server():
    app = make_app()
    app.listen(HTTP_PORT)
    shutdown_event = asyncio.Event()
    print(f'http server running: http://localhost:{HTTP_PORT}')
    print(f'websocket server running: ws://127.0.0.1:{HTTP_PORT}')
    await shutdown_event.wait() 

    
# async def run_all_server_with_websocket():
#     await websocket_server()
 
def run_webui():
    MyWindow = webui.window()
    MyWindow.set_size(800,640)
    MyWindow.show( rf"http://127.0.0.1:{HTTP_PORT}/")
    webui.wait()
    
    
async def main():
    pass
        # loop = asyncio.get_event_loop()
        # task1 =loop.create_task(run_http_server())
        # task2 = loop.create_task(run_all_server_with_websocket())
        
        # await task1
        # await task2

if __name__ == "__main__":
    
    asyncio.run(run_http_server())

    

   
    

