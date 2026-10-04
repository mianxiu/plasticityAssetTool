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
from service_control import ServiceControl
from service_tray import ServiceTray
from control_window import ControlWindow
from single_instance import BackendInstance
from tornado.httpclient import AsyncHTTPClient, HTTPClientError

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
            result = await self.application.dispatch(request["action"], request.get("args", {}))
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

class ServiceHandler(LocalHandler):
    async def get(self):
        self.write(await self.application.control.status())

    async def post(self):
        try:
            request = json.loads(self.request.body)
            if not isinstance(request,dict) or not isinstance(request.get("action"),str):
                raise ValueError("无效的服务请求")
            result = await self.application.control.dispatch(request["action"], request.get("args",{}))
            self.write({"ok":True,"data":result})
        except (ValueError,RuntimeError,OSError) as exc:
            self.set_status(400)
            self.write({"ok":False,"error":str(exc)})

class PreviewHandler(LocalHandler):
    async def get(self, asset_id):
        try:
            preview = await asyncio.to_thread(self.application.service.library.preview, asset_id)
            self.set_header("Content-Type", "image/jpeg")
            self.set_header("Cache-Control", "private, max-age=3600")
            self.write(preview)
        except ValueError:
            raise web.HTTPError(404)


class GeometryHandler(LocalHandler):
    async def get(self, asset_id, thumbnail=None):
        try:
            geometry = self.application.service.geometry
            if thumbnail:
                self.set_header("Content-Type", "image/jpeg")
                self.write(await asyncio.to_thread(geometry.thumbnail, asset_id))
            else:
                mesh = await asyncio.to_thread(geometry.cached, asset_id)
                if mesh is None:
                    raise ValueError("未生成预览")
                self.write(mesh)
        except ValueError:
            raise web.HTTPError(404)


class GeometryWorkerHandler(LocalHandler):
    def post(self):
        try:
            request = json.loads(self.request.body)
            job = self.application.service.geometry.worker(request.get("target_id"), request.get("token"), request.get("result"))
            self.write({"job": job})
        except (ValueError, AttributeError) as error:
            self.set_status(400)
            self.write({"error": str(error)})

class NativeWorkerHandler(LocalHandler):
    def post(self):
        try:
            request = json.loads(self.request.body)
            job = self.application.service.native.worker(request.get("target_id"), request.get("token"), request.get("result"), request.get("capabilities"))
            self.write({"job": job})
        except (ValueError, AttributeError) as error:
            self.set_status(400)
            self.write({"error": str(error)})

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
    def is_html(self):
        return str(getattr(self,"absolute_path",self.path)).lower().endswith(".html") or not self.path

    def set_extra_headers(self, path):
        if self.is_html():
            self.set_header("Cache-Control", "no-store")

    def compute_etag(self):
        # HTML stays at the same path while Vite changes script filenames.
        # Tornado's cached file hash must not make a rebuilt index return 304.
        if self.is_html():
            return None
        return super().compute_etag()

    def should_return_304(self):
        return False if self.is_html() else super().should_return_304()

class Application(web.Application):
    def __init__(self, config, service=None):
        self.clients = set()
        self.service = service or AssetService(config, ROOT)
        self.control_window = ControlWindow(f'http://127.0.0.1:{config["server"]["http_port"]}', ROOT, self.service.desktop)
        self.stop_event = asyncio.Event()
        self.control = ServiceControl(self, self.stop_event)
        port = config["server"]["http_port"]
        super().__init__([
            (r"/websocket", WSHandler), (r"/api/health", HealthHandler),
            (r"/api/service", ServiceHandler),
            (r"/api/geometry/worker", GeometryWorkerHandler),
            (r"/api/native/worker", NativeWorkerHandler),
            (r"/api/assets/([a-f0-9]{32})/geometry(/preview)?", GeometryHandler),
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

    async def dispatch(self, action, args):
        if not isinstance(args,dict):
            raise ValueError("参数必须是对象")
        if action.startswith("service."):
            return await self.control.dispatch(action,args)
        result = await self.service.dispatch(action,args,self.settings["base_url"])
        if action == "state":
            result["panel_settings"] = self.service.panel_settings.snapshot()
        return result

async def reuse_backend(port, headless):
    url = f"http://127.0.0.1:{port}"
    response = await AsyncHTTPClient().fetch(url + "/api/health", request_timeout=1)
    if json.loads(response.body).get("app") != "plasticity-asset-tool":
        raise RuntimeError("端口被其他程序占用")
    if not headless:
        try:
            response = await AsyncHTTPClient().fetch(
                url + "/api/service", method="POST", headers={"Content-Type": "application/json"},
                body=json.dumps({"action": "service.open_control"}), request_timeout=10)
        except (HTTPClientError, OSError) as exc:
            raise RuntimeError("已有后台正在运行，但控制窗口打开失败；未启动重复实例") from exc
        if not json.loads(response.body).get("ok"):
            raise RuntimeError("已有后台的控制窗口打开失败")
    print(f"后台已运行，复用现有实例：{url}", flush=True)


async def run(port=None, headless=False, no_tray=False, reuse_only=False):
    instance = BackendInstance(ROOT / ".runtime")
    if not instance.acquire():
        # The winner may still be starting. Never start a second backend on timeout.
        deadline = asyncio.get_running_loop().time() + 5
        while asyncio.get_running_loop().time() < deadline:
            existing_port = instance.read_port()
            if existing_port is not None:
                try:
                    await reuse_backend(existing_port, headless)
                    return True
                except (HTTPClientError, OSError):
                    pass
            await asyncio.sleep(0.1)
        raise RuntimeError("后台实例正在启动或未响应，请稍后重试；未启动重复实例")
    try:
        if reuse_only:
            return False
        await run_backend(port, headless, no_tray, instance)
        return True
    finally:
        instance.close()


async def run_backend(port, headless, no_tray, instance):
    config = load_config()
    if port is not None:
        config["server"]["http_port"] = port
    app = Application(config)
    url = app.settings["base_url"]
    try:
        server = app.listen(config["server"]["http_port"], address="127.0.0.1", max_buffer_size=96 * 1024 * 1024)
    except OSError:
        # Compatibility with an already-running backend from before instance locks.
        await reuse_backend(config["server"]["http_port"], headless)
        return
    instance.publish(config["server"]["http_port"])
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
    async def tray_action(action):
        try:
            if action == "control":
                await asyncio.to_thread(app.control_window.open)
            elif action == "library":
                await asyncio.to_thread(webbrowser.open,url+"/")
            elif action == "toggle":
                await app.control.dispatch("service.connection",{"enabled":not app.service.model_enabled})
            elif action == "quit":
                await app.control.dispatch("service.quit",{})
            else:
                await app.control.status()
            if app.control.tray:
                app.control.tray.update(await app.control.status())
        except Exception:
            logging.exception("Tray action failed")
    tray = None
    if not no_tray:
        tray = ServiceTray(lambda action: loop.call_soon_threadsafe(lambda: asyncio.create_task(tray_action(action))))
        app.control.tray = tray
        await asyncio.to_thread(tray.start)
        if not tray.available:
            logging.error("系统托盘不可用：%s",tray.error)
            if headless:
                await asyncio.to_thread(app.control_window.open)
    async def update_tray():
        while not app.stop_event.is_set():
            try:
                if tray:
                    tray.update(await app.control.status())
            except Exception:
                logging.exception("Status refresh failed")
            try:
                await asyncio.wait_for(app.stop_event.wait(),timeout=3)
            except asyncio.TimeoutError:
                pass
    status_task = asyncio.create_task(update_tray())
    print(f"Plasticity 组件库：{url}", flush=True)
    if not headless:
        await asyncio.to_thread(app.control_window.open)
    try:
        await app.stop_event.wait()
    finally:
        launcher.close()
        status_task.cancel()
        await asyncio.gather(status_task,return_exceptions=True)
        if tray:
            await asyncio.to_thread(tray.close)
        server.stop()
        for client in tuple(app.clients):
            client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plasticity 模型组件库")
    parser.add_argument("--headless", action="store_true", help="只启动服务，不打开浏览器")
    parser.add_argument("--port", type=int)
    parser.add_argument("--no-tray",action="store_true",help="仅运行命令行服务，不创建托盘图标")
    parser.add_argument("--reuse-only", action="store_true", help="复用已有后台；没有实例时退出码为 3")
    args = parser.parse_args()
    try:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        logging.basicConfig(filename=ROOT/".runtime/service.log",level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
        reused = asyncio.run(run(args.port, args.headless,args.no_tray,args.reuse_only))
        if args.reuse_only and not reused:
            raise SystemExit(3)
    except KeyboardInterrupt:
        print("组件库已停止")
