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
        self.geometry.can_dispatch = lambda: not self.lock.locked() and not self.native.jobs
        self.launcher = None
        self.model_enabled = True

    async def state(self, library_id="default"):
        library, connection = await asyncio.gather(self.library_state(library_id), self.connection_state())
        return {**library, **connection}

    async def library_state(self, library_id="default", archived=False):
        assets, libraries, folders = await asyncio.gather(
            asyncio.to_thread(self.library.list, archived, library_id),
            asyncio.to_thread(self.library.libraries), asyncio.to_thread(self.library.folders, library_id))
        return {"assets": assets, "libraries": libraries, "folders": folders,
                "launcher": self.launcher.snapshot() if self.launcher else {"registered": False}}

    async def connection_state(self):
        targets = await self.bridge.discover()
        native_targets = self.native.connected_targets()
        listed = {target['id'] for target in targets}
        targets += [{'id':target, 'hwnd':int(target[5:]), 'title':'Plasticity · '+target[5:], 'mode':'native'} for target in native_targets if target not in listed]
        return {"native_targets": self.native.connected_targets(), "geometry_targets": self.geometry.connected_targets(), "model_enabled": self.model_enabled, "launcher": self.launcher.snapshot() if self.launcher else {"registered": False, "message": "Ctrl+K 搜索"}, "targets": targets, "active_target_id": self.bridge.active_target_id, "connection_note": self.desktop_error or self.bridge.last_error, "clipboard_supported": self.desktop is not None}

    def clipboard(self):
        if not self.desktop:
            raise ValueError("原生模型剪贴板不可用：" + self.desktop_error)
        return self.desktop

    async def dispatch(self, action, args, base_url):
        if not isinstance(args, dict):
            raise ValueError("参数必须是对象")
        if action == "library.state":
            return await self.library_state(args.get("library_id", "default"), bool(args.get("archived", False)))
        if action == "connection.state":
            return await self.connection_state()
        if action == 'library.base_point':
            return await asyncio.to_thread(self.library.base_point, args.get('id'))
        if action == "asset.geometry":
            kernel_snaps = args.get("kernel_snaps") is True
            if not self.model_enabled:
                cached = self.geometry.cached(args.get("id"))
                if not cached or kernel_snaps and not all("kernel_snaps" in part for part in cached["parts"]):
                    raise ValueError("模型连接已暂停，请在托盘控制中心恢复")
            return {"mesh": await self.geometry.generate(args.get("id"), args.get("target_id"), **({"kernel_snaps":True} if kernel_snaps else {}))}
        if action == "asset.geometry.thumbnail":
            return await asyncio.to_thread(self.geometry.save_thumbnail, args.get("id"), args.get("digest"), decode_preview(args.get("preview")))
        async with self.lock:
            if not self.model_enabled and (action.startswith("asset.") or action in ("target.command", "library.rebase") or (action == "library.capture" and args.get("copy_selection"))):
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
                    target_id = self.bridge.active_target_id
                    if not target_id:
                        raise ValueError('没有可用的激活 Plasticity 窗口，请激活目标窗口或选择固定目标')
                native = args.get("transport") == "native" and args.get("copy_selection")
                base_mode = args.get('base_mode', 'world')
                if base_mode not in ('world', 'pick'):
                    raise ValueError('无效的组件基点模式')
                if base_mode == 'pick' and not native:
                    raise ValueError('基点拾取需要直接保存选中的模型')
                base_options = {'base_mode': 'pick'} if base_mode == 'pick' else {}
                recipe = None
                if native:
                    if args.get("group_signature"):
                        captured = await self.native.request(target_id, "capture-group", signature=args['group_signature'], **base_options)
                        model, recipe = captured['model'], captured['recipe']
                        args = args | {'kind': 'solid'}
                    else:
                        capabilities = self.native.workers.get(target_id, {}).get('capabilities', [])
                        if 'selection-kind-v1' in capabilities:
                            captured = await self.native.request(target_id, "capture", with_metadata=True, **base_options)
                            model = captured['model']
                            args = args | {'kind': captured['kind']}
                        else:
                            model = await self.native.request(target_id, "capture", **base_options)
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
            if action == 'library.rebase':
                if args.get('base_mode') not in ('world', 'pick'):
                    raise ValueError('请选择世界原点或视口拾取')
                original = await asyncio.to_thread(self.library.model_row, args.get('id'))
                model = validate_model(bytes(original['model']))
                if original['archived'] or hashlib.sha256(model).hexdigest() != original['digest']:
                    raise ValueError('组件已归档或数据校验失败，未修改基点')
                # Native copy is the authority for the placement envelope; do
                # not guess coordinate order, units or quaternion conventions.
                reference = await self.native.request(args.get('target_id'), 'rebase', model, base_mode=args['base_mode'])
                updated = validate_model(reference[:56] + model[56:])
                result = await asyncio.to_thread(self.library.rebase, original['id'], original['digest'], updated)
                from .model_clipboard import model_base_point
                import struct
                return result | {'base_point': model_base_point(updated),'base_orientation':list(struct.unpack_from('<4d',updated,24))}
            if action == "library.update":
                fields = dict(args)
                if "preview" in fields:
                    fields["preview"] = decode_preview(fields["preview"])
                return await asyncio.to_thread(self.library.update, args.get("id"), fields)
            if action in ("library.archive", "library.restore"):
                await asyncio.to_thread(self.library.archive, args.get("id"), action == "library.archive")
                return {"ok": True}
            if action in ("asset.copy", "asset.insert"):
                row = await asyncio.to_thread(self.library.model_row, args.get("id"))
                if row["archived"]:
                    raise ValueError("请先恢复归档组件")
                model = validate_model(bytes(row["model"]))
                if hashlib.sha256(model).hexdigest() != row["digest"]:
                    raise ValueError("组件数据校验失败，已阻止置入。请重新保存或导入组件")
                if action == "asset.insert" and args.get("transport") == "native":
                    target_id = args.get("target_id")
                    if args.get("follow_active"):
                        await self.bridge.discover()
                        target_id = self.bridge.active_target_id
                        if not target_id:
                            raise ValueError('没有可用的激活 Plasticity 窗口，请激活目标窗口或选择固定目标')
                    supported = row['kind'] not in ('curve', 'mixed')
                    recipe=json.loads(row['recipe_json']) if supported else None
                    mode = row["insert_mode"] if supported and args.get("placement", True) else "new-body"
                    result = await self.native.request(target_id, "insert", model, args.get("placement", True), mode, **({'recipe':recipe} if recipe else {}))
                    return {**result, "message": "请在视口定位并确认置入" if args.get("placement", True) else "组件已原位置入"}
                clipboard = self.clipboard()
                target_id, placement = args.get("target_id"), args.get("placement", True)
                if action == "asset.insert" and placement and row['kind'] not in ('curve', 'mixed') and (row["insert_mode"] != "new-body" or json.loads(row['recipe_json']) is not None):
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
