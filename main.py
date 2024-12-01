
import asyncio
import My_Modules.websocket_handle as websocket_handle
from webui import webui
import uuid
import tornado
from tornado import ioloop,websocket
import threading
import program_info

HTTP_PORT = 15150
WEBSOCKET_PORT = 15151

WEBSOCKET_URL =  f"ws://127.0.0.1:{HTTP_PORT}/websocket"
RECENT_PATH = []

uuid_clients = {}
clients = []

class WSHandler(websocket.WebSocketHandler):
 
    async def open(self):
        self.id = uuid.uuid4()
        uuid_clients[self.id] = {'id':self.id}
        clients.append(self)
        print(f"WebSocket opened {self.id}")
        

    async def on_message(self, message):
        global RECENT_PATH

        def websocket_hander_call_back():  
            global RECENT_PATH
            RECENT_PATH = websocket_handle.websocket_handle(message=message)

        await ioloop.IOLoop.current().run_in_executor(None,websocket_hander_call_back)
        for client in clients:
                await client.write_message(f"{RECENT_PATH}")
        await self.write_message(f"{RECENT_PATH}")
        

    def on_close(self):
        # 清除客户端连接
        for client_id, client in uuid_clients.items():
            if client == self: 
                del uuid_clients[client_id]
                
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


async def run_http_websocket_server(HTTP_PORT):
    app = make_app()
    app.listen(HTTP_PORT)
    shutdown_event = asyncio.Event()
    print(f'http server running: http://localhost:{HTTP_PORT}')
    print(f'websocket server running: ws://127.0.0.1:{HTTP_PORT}/websocket')
    print('Ctrl+C to exit')
    await shutdown_event.wait() 


 
def run_webui():

    MyWindow = webui.window()
    MyWindow.set_size(800,640)
    MyWindow.show( rf"http://127.0.0.1:{HTTP_PORT}/")
    webui.wait()

    
def run_webui_tk():
    pass
    
def run_all_server(http_port):
        asyncio.run(run_http_websocket_server(HTTP_PORT=http_port))
        pass

if __name__ == "__main__":

        
    # # _thread_http_websocket = threading.Thread(target=run_all_server)
    # # _thread_http_websocket.daemon = False
    # # _thread_http_websocket.start()
    # _thread_ui = threading.Thread(target=run_webui)
    # _thread_ui.daemon = True
    # _thread_ui.start()
    try:
        run_all_server(HTTP_PORT)
    except KeyboardInterrupt:
        print("Stop Server")
             



    

   
    

