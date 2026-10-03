"""Plasticity component library: python main.py [--headless] [--port 15150]."""
import argparse
import asyncio
import json
import logging
import webbrowser
from pathlib import Path
from urllib.parse import urlparse
from tornado import web, websocket
from asset_service import AssetService
from library_launcher import LibraryLauncher

ROOT = Path(__file__).resolve().parent
DEFAULT_SHORTCUTS = {"copy": "ctrl+c", "paste": "ctrl+v", "place": "ctrl+shift+v", "move": "g", "rotate": "r", "scale": "s", "focus": "space", "undo": "ctrl+z", "redo": "ctrl+shift+z"}

def load_config():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config.setdefault("keymap", {}).setdefault("desktop_shortcuts", DEFAULT_SHORTCUTS.copy())
    return config

def allowed_origin(origin, port):
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost") and parsed.port in (port, 3000)

class LocalHandler(web.RequestHandler):
    def prepare(self):
        if self.request.host.split(":", 1)[0] not in ("127.0.0.1", "localhost"):
            raise web.HTTPError(403)
        origin = self.request.headers.get("Origin")
        if origin and not allowed_origin(origin, self.application.settings["port"]):
            raise web.HTTPError(403)

class WSHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        return allowed_origin(origin, self.application.settings["port"])

    async def open(self):
        if self.request.host.split(":", 1)[0] not in ("127.0.0.1", "localhost"):
            self.close(1008, "Local connections only")
            return
        self.application.clients.add(self)
        await self.write_message({"type": "connected"})

    async def on_message(self, message):
        request_id = None
        try:
            request = json.loads(message)
            if not isinstance(request, dict) or not isinstance(request.get("id"), str) or not isinstance(request.get("action"), str):
                raise ValueError("无效的请求")
            request_id = request["id"]
            result = await self.application.service.dispatch(request["action"], request.get("args", {}), self.application.settings["base_url"])
            if self.ws_connection:
                await self.write_message({"type": "response", "id": request_id, "ok": True, "data": result})
            if request["action"].startswith(("library.", "collection.", "folder.")) and request["action"] not in ("library.list", "folder.list"):
                await self.application.broadcast({"type": "library_changed"})
        except Exception as exc:
            if not isinstance(exc, (ValueError, RuntimeError)):
                logging.exception("Request failed")
            if self.ws_connection:
                await self.write_message({"type": "response", "id": request_id, "ok": False, "error": str(exc) or "操作失败"})

    def on_close(self):
        self.application.clients.discard(self)

class HealthHandler(LocalHandler):
    def get(self):
        self.write({"ok": True, "app": "plasticity-asset-tool"})

class PreviewHandler(LocalHandler):
    async def get(self, asset_id):
        try:
            preview = await asyncio.to_thread(self.application.service.library.preview, asset_id)
            self.set_header("Content-Type", "image/jpeg")
            self.set_header("Cache-Control", "private, max-age=3600")
            self.write(preview)
        except ValueError:
            raise web.HTTPError(404)

class ExportHandler(LocalHandler):
    async def get(self, asset_id):
        try:
            payload = await asyncio.to_thread(self.application.service.library.export, asset_id)
        except ValueError:
            raise web.HTTPError(404)
        self.set_header("Content-Type", "application/zip")
        self.set_header("Content-Disposition", f'attachment; filename="component-{asset_id}.patasset"')
        self.write(payload)

class ImportHandler(LocalHandler):
    async def post(self):
        files = self.request.files.get("file", [])
        if len(files) != 1:
            self.set_status(400)
            self.write({"error": "请选择一个 .patasset 文件"})
            return
        try:
            async with self.application.service.lock:
                result = await asyncio.to_thread(self.application.service.library.import_package, files[0]["body"], self.get_body_argument("library_id", "default"), self.get_body_argument("folder_id", None) or None)
            self.write({"ok": True, "data": result})
            await self.application.broadcast({"type": "library_changed"})
        except (ValueError, OSError) as exc:
            self.set_status(400)
            self.write({"error": str(exc)})

class StaticHandler(web.StaticFileHandler):
    def set_extra_headers(self, path):
        if path.endswith(".html"):
            self.set_header("Cache-Control", "no-store")

    def compute_etag(self):
        # HTML stays at the same path while Vite changes script filenames.
        # Tornado's cached file hash must not make a rebuilt index return 304.
        if self.path.endswith(".html"):
            return None
        return super().compute_etag()

    def should_return_304(self):
        return False if self.path.endswith(".html") else super().should_return_304()

class Application(web.Application):
    def __init__(self, config, service=None):
        self.clients = set()
        self.service = service or AssetService(config, ROOT)
        port = config["server"]["http_port"]
        super().__init__([
            (r"/websocket", WSHandler), (r"/api/health", HealthHandler),
            (r"/api/assets/([a-f0-9]{32})/preview", PreviewHandler),
            (r"/api/assets/([a-f0-9]{32})/export", ExportHandler),
            (r"/api/import", ImportHandler),
            (r"/(.*)", StaticHandler, {"path": str(ROOT / "plasticity-asset-tool-app" / "dist"), "default_filename": "index.html"}),
        ], port=port, base_url=f"http://127.0.0.1:{port}", websocket_max_message_size=8 * 1024 * 1024)

    async def broadcast(self, message):
        for client in tuple(self.clients):
            try:
                await client.write_message(message)
            except websocket.WebSocketClosedError:
                self.clients.discard(client)

async def run(port=None, headless=False):
    config = load_config()
    if port is not None:
        config["server"]["http_port"] = port
    app = Application(config)
    server = app.listen(config["server"]["http_port"], address="127.0.0.1", max_buffer_size=72 * 1024 * 1024)
    url = app.settings["base_url"]
    loop = asyncio.get_running_loop()
    async def quick_launch(target_id):
        try:
            opened = await asyncio.to_thread(launcher.toggle, target_id)
            if opened:
                await app.broadcast({"type": "quick_launch", "target_id": target_id})
        except (ValueError, RuntimeError, OSError) as exc:
            await app.broadcast({"type": "launcher_error", "message": str(exc) or "面板打开失败"})
    launcher = LibraryLauncher(config.get("launcher", {}), app.service.desktop, url, lambda target_id: loop.call_soon_threadsafe(lambda: asyncio.create_task(quick_launch(target_id))))
    launcher.start()
    app.service.launcher = launcher
    print(f"Plasticity 组件库：{url}", flush=True)
    if not headless:
        webbrowser.open(url)
    try:
        await asyncio.Event().wait()
    finally:
        launcher.close()
        server.stop()
        for client in tuple(app.clients):
            client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plasticity 模型组件库")
    parser.add_argument("--headless", action="store_true", help="只启动服务，不打开浏览器")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.port, args.headless))
    except KeyboardInterrupt:
        print("组件库已停止")
