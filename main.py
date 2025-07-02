import re
import asyncio
import My_Modules.websocket_handle as websocket_handle
from My_Modules.my_modules import Webscoket_Send_Message
from webui import webui
import uuid
import tornado
from tornado import ioloop,websocket
import threading
import program_info
import json
from test import run_plasticity_hook

HTTP_PORT = 15150
WEBSOCKET_PORT = 15151

WEBSOCKET_URL =  f"ws://127.0.0.1:{HTTP_PORT}/websocket"
SEND_MESSAGE=Webscoket_Send_Message(False,[])

uuid_clients = {}
clients = []

class WSHandler(websocket.WebSocketHandler):
 
    async def open(self):
        self.id = uuid.uuid4()
        uuid_clients[self.id] = {'id':self.id}
        clients.append(self)
        print(f"WebSocket opened {self.id}")

        await self.write_message(f"{SEND_MESSAGE.msg}")

    async def on_message(self, message):
        global SEND_MESSAGE

        def websocket_hander_call_back():  
            global SEND_MESSAGE
            SEND_MESSAGE = websocket_handle.websocket_handle(message=message)

        await ioloop.IOLoop.current().run_in_executor(None,websocket_hander_call_back)
        
        print("on_msg")
        print(SEND_MESSAGE)
        
        if SEND_MESSAGE:
            
            # _JSON_SEND_MESSAGE = json.dumps(SEND_MESSAGE.msg)
            _JSON_SEND_MESSAGE = SEND_MESSAGE.msg
            # print(_JSON_SEND_MESSAGE)
            
            if SEND_MESSAGE.is_for_all: 
                for client in clients:
                        await client.write_message(_JSON_SEND_MESSAGE)
            else:
                await self.write_message(_JSON_SEND_MESSAGE)
        else:
            print("SEND_MESSAGE IS NONE")

    def on_close(self):
        # 清除客户端连接
        for client_id, client in uuid_clients.items():
            if client == self: 
                del uuid_clients[client_id]
        if self in clients:
            clients.remove(self)
                
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
    print("-------------")
    print(f'http server running: http://localhost:{HTTP_PORT}')
    print(f'websocket server running: ws://127.0.0.1:{HTTP_PORT}/websocket')
    print('Ctrl+C to exit')
    print("-------------")
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
    try:
        
        _thread_http_websocket = threading.Thread(target=run_all_server,args=(HTTP_PORT,))
        _thread_http_websocket.daemon = True
        _thread_http_websocket.start()
        # has error
        # _thread_ui = threading.Thread(target=run_webui)
        # _thread_ui.daemon = True
        # _thread_ui.start()
        _thread_plasticity_hook = threading.Thread(target=run_plasticity_hook())
        _thread_plasticity_hook.daemon= True
        _thread_plasticity_hook.start()
        # _thread_plasticity_hook.join()

        # run_all_server(HTTP_PORT)
    except ConnectionError:
        # _thread_plasticity_hook.start()
        print("Connection Close")
        
    except KeyboardInterrupt:
        print("Stop Server")
             

