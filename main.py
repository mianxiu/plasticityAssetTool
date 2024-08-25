
import asyncio
import tornado.websocket
import websockethandle
from webui import webui
import uuid
import tornado
from tornado import ioloop
import crossfiledialog
import concurrent.futures
import threading
from tornado import websocket
import multiprocessing



HTTP_PORT = 15150
WEBSOCKET_PORT = 15151

WEBSOCKET_URL =  f"ws://127.0.0.1:{HTTP_PORT}/websocket"

clients = {}
# 创建线程池
executor = concurrent.futures.ThreadPoolExecutor()
RECENT_PATH = []



class WSHandler(tornado.websocket.WebSocketHandler):
 
    async def open(self):
        self.id = uuid.uuid4()
        clients[self.id] = {'id':self.id}
        print(f"WebSocket opened {self.id}")
        
        
    # @classmethod
    # def on_m(self,msg):
    #         self.write_message(f"Received message: { self.id} {msg}")
            

    def on_message(self, message):
        global RECENT_PATH


        def oo():
            global RECENT_PATH
            r = websockethandle.websocket_handle(message=message)
            RECENT_PATH = r
            #ioloop.IOLoop.current().spawn_callback(WSHandler.write_message,r)
            
        
        t = threading.Thread(target=oo,name=self.id)
        t.setDaemon(True)
        t.start()
        t.join()
        
        
        self.write_message(f"{RECENT_PATH}")
        RECENT_PATH = []
        
        # futures = {executor.submit(oo):self.id}
        # # 等待每个任务完成并即时获取结果
        # for future in concurrent.futures.as_completed(futures):
        #     result = future.result()
        #     print(f"Result for {futures[future]} : {result}")   

        # await self.write_message(f"Received message: { self.id} holding select file... ")
        # await threading.Thread(target=futures.result).start()

        # threads.append(threading.Thread)
        
       
            #await ioloop.IOLoop.current().run_in_executor(None,oo)

    def on_close(self):
        # 清除客户端连接
        for client_id, client in clients.items():
            if client == self: 
                del clients[client_id]
                for thread in threading.enumerate():
                    if thread.name == "MyThread":
                        print(f"Closing thread {thread.name}")
                        thread.join(timeout=0)
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
    print(f'Ctrl+C to exit')
    await shutdown_event.wait() 

    
# async def run_all_server_with_websocket():
#     await websocket_server()
 
def run_webui():

    # MyWindow = webui.window()
    # MyWindow.set_size(800,640)
    # MyWindow.show( rf"http://127.0.0.1:{HTTP_PORT}/")
    # webui.wait()
        import tkinter as tk
        from tkinter import filedialog

        # 创建主窗口
        root = tk.Tk()
        root.iconify()  
        root.iconbitmap("plasticity asset tool.ico")
        
        
        # 创建一个顶级窗口来容纳文件选择对话框
        # top_level = tk.Toplevel(root)
        # top_level.withdraw()

        # button = tk.Button(top_level, text="Open File", command=open_file)
        # button.pack()

       # root.mainloop()
    
    
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
    
    # run_all_server()
    t1 = multiprocessing.Process(target=run_all_server,args=(15150,))
    t2 = multiprocessing.Process(target=run_all_server,args=(15151,))
    
    t1.start()
    t2.start()
    
    
    

    

   
    

