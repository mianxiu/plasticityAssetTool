"""CDP transport with request-id matching and reversible panel injection."""
import asyncio
import base64
import json
from pathlib import Path
from urllib.parse import urlparse, quote
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.websocket import websocket_connect

ROOT = Path(__file__).resolve().parent
EVENTS = {"copy": "edit:copy", "paste": "edit:paste", "place": "edit:paste-with-placement", "move": "command:move", "rotate": "command:rotate", "scale": "command:scale", "focus": "viewport:focus", "undo": "edit:undo", "redo": "edit:redo"}

def local_url(url, schemes=("http",)):
    parsed = urlparse(url)
    if parsed.scheme not in schemes or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password:
        raise ValueError("连接地址必须是本机调试接口")
    return url

class CdpConnection:
    def __init__(self, url):
        self.url = local_url(url, ("ws",))
        self.sequence = 0

    async def __aenter__(self):
        self.socket = await websocket_connect(HTTPRequest(self.url, connect_timeout=3, request_timeout=3), max_message_size=70 * 1024 * 1024)
        return self

    async def __aexit__(self, *_):
        self.socket.close()

    async def call(self, method, params=None, timeout=5):
        self.sequence += 1
        request_id = self.sequence
        await self.socket.write_message(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        async def receive():
            while True:
                raw = await self.socket.read_message()
                if raw is None:
                    raise RuntimeError("Plasticity 调试连接已断开；请检查视口，不要重复置入")
                response = json.loads(raw)
                if response.get("id") != request_id:
                    continue
                if response.get("error"):
                    raise RuntimeError(response["error"].get("message", "CDP 命令失败"))
                return response.get("result", {})
        try:
            return await asyncio.wait_for(receive(), timeout)
        except asyncio.TimeoutError as exc:
            raise RuntimeError("操作响应超时；结果未知，请检查 Plasticity 视口后再操作") from exc

    async def evaluate(self, expression):
        response = await self.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
        if response.get("exceptionDetails"):
            detail = response["exceptionDetails"]
            raise RuntimeError(detail.get("exception", {}).get("description", detail.get("text", "脚本执行失败")))
        return response.get("result", {}).get("value")

class PlasticityBridge:
    def __init__(self, config, desktop):
        self.config, self.desktop = config, desktop
        self.targets = {}
        self.last_error = ""
        self.active_target_id = None

    async def discover(self):
        desktop = await asyncio.to_thread(self.desktop.windows) if self.desktop else []
        endpoints = self.config.get("plasticity", {}).get("cdp_endpoints", ["http://127.0.0.1:9223"])
        client, cdp = AsyncHTTPClient(), []
        for endpoint in endpoints:
            try:
                endpoint = local_url(endpoint).rstrip("/")
                response = await client.fetch(HTTPRequest(endpoint + "/json/list", connect_timeout=0.5, request_timeout=0.8, follow_redirects=False))
                for row in json.loads(response.body):
                    if row.get("type") != "page" or not ("plasticity" in (row.get("url", "") + row.get("title", "")).lower()):
                        continue
                    ws_url = local_url(row["webSocketDebuggerUrl"], ("ws",))
                    cdp.append({"id": endpoint + "#" + row["id"], "target_id": row["id"], "title": row.get("title", "Plasticity"), "ws_url": ws_url, "mode": "cdp"})
            except Exception:
                continue
        # Never pair HWND and CDP targets by list order.
        targets = cdp + desktop
        self.targets = {target["id"]: target for target in targets}
        if self.desktop and hasattr(self.desktop, "active_window"):
            hwnd = await asyncio.to_thread(self.desktop.active_window)
            active = f"hwnd:{hwnd}" if hwnd else None
            if active in self.targets:
                self.active_target_id = active
        if self.active_target_id not in self.targets:
            self.active_target_id = None
        self.last_error = "调试接口未连接，仍可使用原生剪贴板模式" if not cdp else ""
        return targets

    def target(self, target_id):
        if not isinstance(target_id, str) or target_id not in self.targets:
            raise ValueError("请选择仍在运行的 Plasticity 窗口")
        return self.targets[target_id]

    async def command(self, target_id, action):
        target = self.target(target_id)
        if action not in EVENTS:
            raise ValueError("不支持的 Plasticity 操作")
        if target["mode"] == "desktop":
            shortcuts = self.config["keymap"]["desktop_shortcuts"]
            if action not in shortcuts:
                raise ValueError("该操作需要 CDP 连接")
            await asyncio.to_thread(self.desktop.shortcut, target["hwnd"], shortcuts[action])
        else:
            async with CdpConnection(target["ws_url"]) as cdp:
                await cdp.call("Page.bringToFront")
                await cdp.evaluate("""(() => {
                    if (document.body.hasAttribute('command') || document.body.hasAttribute('gizmo'))
                        throw new Error('请先确认或取消 Plasticity 当前操作');
                    const canvas = document.querySelector('plasticity-viewport canvas') || document.querySelector('canvas');
                    if (!canvas) throw new Error('Plasticity 视口尚未加载');
                    document.activeElement?.blur(); canvas.focus();
                    canvas.dispatchEvent(new Event(""" + json.dumps(EVENTS[action]) + """, {bubbles:true,cancelable:true}));
                    return {dispatched:true};
                })()""")
        return {"dispatched": True, "verified": False, "mode": target["mode"]}

    async def preview(self, target_id):
        target = self.target(target_id)
        if target["mode"] != "cdp":
            return None
        async with CdpConnection(target["ws_url"]) as cdp:
            response = await cdp.call("Page.captureScreenshot", {"format": "jpeg", "quality": 65})
            return base64.b64decode(response["data"])

    async def embed_panel(self, target_id, base_url):
        target = self.target(target_id)
        if target["mode"] != "cdp":
            raise ValueError("嵌入面板需要 CDP 调试连接；当前可使用独立组件库窗口")
        script = (ROOT / "plasticity-javascript-payloads" / "init.js").read_text(encoding="utf-8")
        options = {"url": base_url + "/?target=" + quote(target_id, safe=""), "key": self.config["keymap"].get("show_panel_event_key_code", "Backquote")}
        async with CdpConnection(target["ws_url"]) as cdp:
            return await cdp.evaluate("(" + script + ")(" + json.dumps(options) + ")")
