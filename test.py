import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.process
import os

class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        client_id = len(self.server.clients) + 1
        process = tornado.process.Subprocess(['python', 'test_1.py', str(os.getpid()), str(client_id)])
        process.set_exit_callback(self.on_process_exit)
        self.server.clients[client_id] = process

    def on_message(self, message):
        client_id = int(self.request.arguments["client_id"][0])
        process = self.server.clients.get(client_id)
        if process:
            process.write_message(message)

    def on_close(self):
        client_id = int(self.request.arguments["client_id"][0])
        process = self.server.clients.get(client_id)
        if process:
            process.kill()
            del self.server.clients[client_id]

    def on_process_exit(self, status):
        print("Process exited with status:", status)

class Application(tornado.web.Application):
    def __init__(self):
        self.clients = {}
        handlers = [
            (r"/ws", WSHandler),
        ]
        super().__init__(handlers)

if __name__ == "__main__":
    app = Application()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()