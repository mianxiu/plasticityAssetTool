
import asyncio
import threading
import tornado.websocket
import websockethandle
from webui import webui
import uuid

import tornado

HTTP_PORT = 15150
WEBSOCKET_PORT = 15151

clients = {}

class WSHandler(tornado.websocket.WebSocketHandler):
 
    def open(self):
        self.id = uuid.uuid4()
        clients[self.id] = {'id':self.id}
        print(f"WebSocket opened {self.id}")

    def on_message(self, message):
        # print(f"from {self.id}----")
        d =websockethandle.websocket_handle(message=message)
        self.write_message(f"Received message: {d}")

    def on_close(self):
                # 清除客户端连接
        for client_id, client in clients.items():
            if client == self: 
                del clients[client_id]
        print(f"WebSocket closed for {client_id}")
                
                
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
        
    ],**settings)


async def run_http_websocket_server():
    app = make_app()
    app.listen(HTTP_PORT)
    shutdown_event = asyncio.Event()
    print(f'http server running: http://localhost:{HTTP_PORT}')
    print(f'websocket server running: ws://127.0.0.1:{HTTP_PORT}/websocket')
    print(f'Ctrl+C to exit')
    await shutdown_event.wait() 

    
# async def run_all_server_with_websocket():
#     await websocket_server()
 
def run_webui():

    MyWindow = webui.window()
    MyWindow.set_size(800,640)
    MyWindow.show( rf"http://127.0.0.1:{HTTP_PORT}/")
    webui.wait()
    
    
def run_all_server():
        asyncio.run(run_http_websocket_server())
        pass

if __name__ == "__main__":

    # # _thread_http_websocket = threading.Thread(target=run_all_server)
    # # _thread_http_websocket.daemon = False
    # # _thread_http_websocket.start()
    # _thread_ui = threading.Thread(target=run_webui)
    # _thread_ui.daemon = True
    # _thread_ui.start()
    run_all_server()
    
    
    

    

   
    

