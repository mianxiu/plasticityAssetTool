import asyncio
import base64
import binascii
from pathlib import Path
from asset_library import AssetLibrary, MAX_PREVIEW_BYTES
from plasticity_bridge import PlasticityBridge
from windows_bridge import WindowsBridge


def decode_preview(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not value.startswith("data:image/jpeg;base64,") or len(value) > MAX_PREVIEW_BYTES * 4 / 3 + 100:
        raise ValueError("预览必须是小于 5 MB 的 JPEG")
    try:
        preview = base64.b64decode(value.split(",", 1)[1], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("预览图编码无效，请重新选择 JPEG") from exc
    return AssetLibrary.validate_preview(preview)

class AssetService:
    def __init__(self, config, root, desktop=None):
        self.config = config
        self.library = AssetLibrary(Path(root) / "library")
        self.desktop = desktop
        self.desktop_error = ""
        if self.desktop is None:
            try:
                self.desktop = WindowsBridge()
            except Exception as exc:
                self.desktop_error = str(exc)
        self.bridge = PlasticityBridge(config, self.desktop)
        self.lock = asyncio.Lock()
        self.launcher = None

    async def state(self, library_id="default"):
        targets = await self.bridge.discover()
        return {"assets": await asyncio.to_thread(self.library.list, False, library_id), "libraries": await asyncio.to_thread(self.library.libraries), "folders": await asyncio.to_thread(self.library.folders, library_id), "launcher": self.launcher.snapshot() if self.launcher else {"registered": False, "message": "Ctrl+K 搜索"}, "targets": targets, "connection_note": self.desktop_error or self.bridge.last_error, "clipboard_supported": self.desktop is not None}

    def clipboard(self):
        if not self.desktop:
            raise ValueError("原生模型剪贴板不可用：" + self.desktop_error)
        return self.desktop

    async def dispatch(self, action, args, base_url):
        if not isinstance(args, dict):
            raise ValueError("参数必须是对象")
        async with self.lock:
            if action == "panel.dismiss":
                if self.launcher and self.launcher.panel:
                    await asyncio.to_thread(self.launcher.panel.dismiss)
                return {"dismissed": True}
            if action == "state":
                return await self.state(args.get("library_id", "default"))
            if action == "collection.create":
                return await asyncio.to_thread(self.library.create_library, args.get("name"))
            if action == "collection.rename":
                return await asyncio.to_thread(self.library.rename_library, args.get("id"), args.get("name"))
            if action == "folder.create":
                return await asyncio.to_thread(self.library.create_folder, args.get("library_id", "default"), args.get("parent_id"), args.get("name"))
            if action == "folder.list":
                return await asyncio.to_thread(self.library.folders, args.get("library_id", "default"))
            if action == "folder.rename":
                return await asyncio.to_thread(self.library.rename_folder, args.get("library_id", "default"), args.get("id"), args.get("name"))
            if action == "library.list":
                return await asyncio.to_thread(self.library.list, bool(args.get("archived", False)), args.get("library_id", "default"))
            if action == "library.capture":
                self.library.validate_fields(args)
                self.library.organization(args)
                preview = decode_preview(args.get("preview"))
                clipboard = self.clipboard()
                target_id, source_version = args.get("target_id"), "unknown"
                if args.get("copy_selection"):
                    self.bridge.target(target_id)
                    previous = await asyncio.to_thread(clipboard.sequence)
                    await self.bridge.command(target_id, "copy")
                    deadline = asyncio.get_running_loop().time() + 5
                    while await asyncio.to_thread(clipboard.sequence) == previous:
                        if asyncio.get_running_loop().time() >= deadline:
                            raise ValueError("未收到新的模型复制数据。请选中实体并退出当前工具，或手动 Ctrl+C 后从剪贴板保存")
                        await asyncio.sleep(0.05)
                model = await asyncio.to_thread(clipboard.read)
                if preview is None and target_id and args.get("copy_selection"):
                    try:
                        preview = await self.bridge.preview(target_id)
                    except Exception:
                        pass
                target = self.bridge.targets.get(target_id)
                if target and target.get("path"):
                    source_version = next((p[4:] for p in Path(target["path"]).parts if p.startswith("app-")), "unknown")
                return await asyncio.to_thread(self.library.add, model, args, preview, source_version)
            if action == "library.update":
                fields = dict(args)
                if "preview" in fields:
                    fields["preview"] = decode_preview(fields["preview"])
                return await asyncio.to_thread(self.library.update, args.get("id"), fields)
            if action in ("library.archive", "library.restore"):
                await asyncio.to_thread(self.library.archive, args.get("id"), action == "library.archive")
                return {"ok": True}
            if action in ("asset.copy", "asset.insert"):
                row = await asyncio.to_thread(self.library.get, args.get("id"))
                if row["archived"]:
                    raise ValueError("请先恢复归档组件")
                clipboard = self.clipboard()
                target_id, placement = args.get("target_id"), args.get("placement", True)
                if action == "asset.insert":
                    target = self.bridge.target(target_id)
                    if target["mode"] == "desktop":
                        await asyncio.to_thread(clipboard.activate, target["hwnd"])
                await asyncio.to_thread(clipboard.write, bytes(row["model"]))
                if action == "asset.copy":
                    return {"message": "组件已复制，可在 Plasticity 视口按 Ctrl+Shift+V 定位置入"}
                if await asyncio.to_thread(clipboard.read) != bytes(row["model"]):
                    raise RuntimeError("剪贴板发生变化，未发送粘贴，请重试")
                result = await self.bridge.command(target_id, "place" if placement else "paste")
                return {**result, "message": "已发送 Ctrl+Shift+V，请在视口定位并确认置入" if placement else "已发送 Ctrl+V，请在视口确认粘贴"}
            if action == "target.command":
                result = await self.bridge.command(args.get("target_id"), args.get("command"))
                return {**result, "message": "已发送原生工具命令，请在 Plasticity 视口完成操作"}
            if action == "target.embed":
                return await self.bridge.embed_panel(args.get("target_id"), base_url)
            raise ValueError("未知操作：" + str(action))
