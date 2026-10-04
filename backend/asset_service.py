import asyncio
import base64
import binascii
import hashlib
import json
from pathlib import Path
from .asset_library import AssetLibrary, MAX_PREVIEW_BYTES
from .plasticity_bridge import PlasticityBridge
from .windows_bridge import WindowsBridge
from .model_clipboard import validate_model
from .geometry_preview import GeometryPreview
from .native_transport import NativeTransport
from .panel_settings import PanelSettings


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
        self.panel_settings = PanelSettings(root)
        self.library = AssetLibrary(Path(root) / "library")
        self.geometry = GeometryPreview(self.library)
        self.native = NativeTransport()
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
        self.model_enabled = True

    async def state(self, library_id="default"):
        targets = await self.bridge.discover()
        native_targets = self.native.connected_targets()
        listed = {target['id'] for target in targets}
        targets += [{'id':target, 'hwnd':int(target[5:]), 'title':'Plasticity · '+target[5:], 'mode':'native'} for target in native_targets if target not in listed]
        return {"native_targets": self.native.connected_targets(), "geometry_targets": self.geometry.connected_targets(), "model_enabled": self.model_enabled, "assets": await asyncio.to_thread(self.library.list, False, library_id), "libraries": await asyncio.to_thread(self.library.libraries), "folders": await asyncio.to_thread(self.library.folders, library_id), "launcher": self.launcher.snapshot() if self.launcher else {"registered": False, "message": "Ctrl+K 搜索"}, "targets": targets, "active_target_id": self.bridge.active_target_id, "connection_note": self.desktop_error or self.bridge.last_error, "clipboard_supported": self.desktop is not None}

    def clipboard(self):
        if not self.desktop:
            raise ValueError("原生模型剪贴板不可用：" + self.desktop_error)
        return self.desktop

    async def dispatch(self, action, args, base_url):
        if not isinstance(args, dict):
            raise ValueError("参数必须是对象")
        if action == "asset.geometry":
            if not self.model_enabled and not self.geometry.cached(args.get("id")):
                raise ValueError("模型连接已暂停，请在托盘控制中心恢复")
            return {"mesh": await self.geometry.generate(args.get("id"), args.get("target_id"))}
        if action == "asset.geometry.thumbnail":
            return await asyncio.to_thread(self.geometry.save_thumbnail, args.get("id"), args.get("digest"), decode_preview(args.get("preview")))
        async with self.lock:
            if not self.model_enabled and (action.startswith("asset.") or action == "target.command" or (action == "library.capture" and args.get("copy_selection"))):
                raise ValueError("模型连接已暂停，请在托盘控制中心恢复")
            if action == "panel.dismiss":
                if self.launcher and self.launcher.panel:
                    await asyncio.to_thread(self.launcher.panel.dismiss)
                return {"dismissed": True}
            if action == "state":
                return await self.state(args.get("library_id", "default"))
            if action == "selection.group":
                if not self.model_enabled: raise ValueError("模型连接已暂停")
                return await self.native.request(args.get("target_id"), "inspect-group")
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
                target_id, source_version = args.get("target_id"), "unknown"
                if args.get("transport") == "native" and args.get("follow_active"):
                    await self.bridge.discover()
                    target_id = self.bridge.active_target_id or target_id
                native = args.get("transport") == "native" and args.get("copy_selection")
                recipe = None
                if native:
                    if args.get("group_signature"):
                        captured = await self.native.request(target_id, "capture-group", signature=args['group_signature'])
                        model, recipe = captured['model'], captured['recipe']
                    else:
                        model = await self.native.request(target_id, "capture")
                else:
                    clipboard = self.clipboard()
                if args.get("copy_selection") and not native:
                    self.bridge.target(target_id)
                    previous = await asyncio.to_thread(clipboard.sequence)
                    await self.bridge.command(target_id, "copy")
                    deadline = asyncio.get_running_loop().time() + 5
                    while await asyncio.to_thread(clipboard.sequence) == previous:
                        if asyncio.get_running_loop().time() >= deadline:
                            raise ValueError("未收到新的模型复制数据。请选中实体并完成当前工具，或手动复制后从剪贴板保存")
                        await asyncio.sleep(0.05)
                if not native:
                    model = await asyncio.to_thread(clipboard.read)
                validate_model(model)
                if preview is None and target_id and args.get("auto_preview", True) and args.get("preview_mode") != "geometry":
                    try:
                        preview = await self.bridge.preview(target_id)
                        AssetLibrary.validate_preview(preview)
                    except Exception:
                        preview = None
                target = self.bridge.targets.get(target_id)
                if target and target.get("path"):
                    source_version = next((p[4:] for p in Path(target["path"]).parts if p.startswith("app-")), "unknown")
                result = await asyncio.to_thread(self.library.add, model, args | {"recipe": recipe}, preview, source_version)
                if args.get("auto_preview", True) and preview is None and args.get("preview_mode") != "geometry":
                    result["preview_warning"] = "模型已保存，但未能生成预览。请重新加载内嵌插件，或在编辑组件时上传预览图。"
                return result
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
                model = validate_model(bytes(row["model"]))
                if hashlib.sha256(model).hexdigest() != row["digest"]:
                    raise ValueError("组件数据校验失败，已阻止置入。请重新保存或导入组件")
                if action == "asset.insert" and args.get("transport") == "native":
                    target_id = args.get("target_id")
                    if args.get("follow_active"):
                        await self.bridge.discover()
                        target_id = self.bridge.active_target_id or target_id
                    recipe=json.loads(row['recipe_json'])
                    result = await self.native.request(target_id, "insert", model, args.get("placement", True), row["insert_mode"] if args.get("placement", True) else "new-body", **({'recipe':recipe} if recipe else {}))
                    return {**result, "message": "请在视口定位并确认置入" if args.get("placement", True) else "组件已原位置入"}
                clipboard = self.clipboard()
                target_id, placement = args.get("target_id"), args.get("placement", True)
                if action == "asset.insert" and placement and (row["insert_mode"] != "new-body" or json.loads(row['recipe_json']) is not None):
                    raise ValueError("布尔置入需要原生模型直连")
                if action == "asset.insert":
                    target = self.bridge.target(target_id)
                    if target["mode"] == "desktop":
                        await asyncio.to_thread(clipboard.activate, target["hwnd"])
                await asyncio.to_thread(clipboard.write, model)
                current = await asyncio.to_thread(clipboard.read)
                validate_model(current)
                if current != model:
                    raise RuntimeError("剪贴板发生变化，未发送粘贴，请重试")
                if action == "asset.copy":
                    return {"message": "组件已复制，可在 Plasticity 视口粘贴置入"}
                result = await self.bridge.command(target_id, "place" if placement else "paste")
                return {**result, "message": "请在视口定位并确认置入" if placement else "请在视口确认粘贴"}
            if action == "target.command":
                if args.get("command") in ("paste", "place"):
                    validate_model(await asyncio.to_thread(self.clipboard().read))
                result = await self.bridge.command(args.get("target_id"), args.get("command"))
                return {**result, "message": "已发送原生工具命令，请在 Plasticity 视口完成操作"}
            if action == "target.embed":
                return await self.bridge.embed_panel(args.get("target_id"), base_url)
            raise ValueError("未知操作：" + str(action))
