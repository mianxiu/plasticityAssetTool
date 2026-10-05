"""User-visible controls for the local service and native model connection."""
import asyncio
import os
import time
from .plugin_manager import PluginManager
from .version import APP_NAME, APP_VERSION


class ServiceControl:
    def __init__(self, app, stop_event):
        self.app, self.stop_event = app, stop_event
        self.started = time.monotonic()
        self.tray = None
        self.plugins = PluginManager(app.service.library.root.parent)

    async def status(self):
        service = self.app.service
        async with service.lock:
            targets = await service.bridge.discover()
        libraries = await asyncio.to_thread(service.library.libraries)
        return {"running": True, "app_name": APP_NAME, "app_version": APP_VERSION,
                "pid": os.getpid(), "uptime_seconds": int(time.monotonic()-self.started),
                "model_enabled": service.model_enabled, "clipboard_supported": service.desktop is not None,
                "targets": targets, "active_target_id": service.bridge.active_target_id, "panel_clients": len(self.app.clients),
                "component_count": sum(row["count"] for row in libraries), "libraries": libraries,
                "url": self.app.settings["base_url"],
                "panel_settings": service.panel_settings.snapshot(),
                "plugin_manager": self.plugins.snapshot(),
                "shortcut": service.config["keymap"].get("show_panel_event_key_code", "Tab"),
                "tray_available": bool(self.tray and self.tray.available),
                "tray_error": self.tray.error if self.tray else ""}

    async def dispatch(self, action, args):
        if not isinstance(args,dict):
            raise ValueError("参数必须是对象")
        service = self.app.service
        if action == "service.status":
            return await self.status()
        if action == "service.open_control":
            return await asyncio.to_thread(self.app.control_window.open)
        if action == "service.plugin_detect":
            if self.plugins.task and not self.plugins.task.done():
                return self.plugins.snapshot()
            return await asyncio.to_thread(self.plugins.scan, args.get('path'))
        if action == "service.plugin_install":
            return await self.plugins.start(args.get('id'), args.get('operation'))
        if action == "service.panel_settings":
            async with service.lock:
                settings = await asyncio.to_thread(service.panel_settings.update, args.get("position"), args.get("sidebar_mode"), args.get("card_size"))
            await self.app.broadcast({"type": "service_changed"})
            return {"message": "面板设置已保存", "panel_settings": settings}
        if action == "service.connection":
            if not isinstance(args.get("enabled"), bool):
                raise ValueError("请指定暂停或恢复连接")
            async with service.lock:
                service.model_enabled = args["enabled"]
            await self.app.broadcast({"type": "service_changed"})
            return await self.status()
        if action == "service.focus":
            async with service.lock:
                await service.bridge.discover()
                target = service.bridge.target(args.get("target_id"))
                if target["mode"] != "desktop" or service.desktop is None:
                    raise ValueError("请选择原生 Plasticity 窗口")
                await asyncio.to_thread(service.desktop.activate, target["hwnd"])
            return {"message": "已切换到 Plasticity 模型窗口"}
        if action == "service.quit":
            if self.plugins.task and not self.plugins.task.done():
                raise ValueError('插件安装正在进行，请先完成或取消安装，再退出后台')
            # Finish an in-flight model operation; send the reply before cleanup.
            async with service.lock:
                service.model_enabled = False
                asyncio.get_running_loop().call_later(0.2, self.stop_event.set)
            return {"message": "后台服务正在退出"}
        raise ValueError("未知的服务操作")
