import asyncio
import base64
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from backend.asset_service import AssetService
from backend.main import DEFAULT_SHORTCUTS
from backend.plasticity_bridge import CdpConnection, local_url
from model_fixture import model_bytes
from test_group_recipe import recipe

class FakeDesktop:
    def __init__(self):
        self.data = model_bytes("original-model")
        self.number = 10
        self.calls = []
        self.change_on_copy = True

    def windows(self):
        return [{"id": "hwnd:42", "hwnd": 42, "title": "Test Plasticity", "path": "C:/Plasticity/app-26.1.3/Plasticity.exe", "mode": "desktop"}]

    def sequence(self):
        return self.number

    def read(self):
        return self.data

    def write(self, data):
        self.calls.append(("write", data))
        self.data = data
        self.number += 1

    def activate(self, hwnd):
        self.calls.append(("activate", hwnd))

    def shortcut(self, hwnd, shortcut):
        self.calls.append(("shortcut", hwnd, shortcut))
        if shortcut == "ctrl+c" and self.change_on_copy:
            self.data = model_bytes("new-selection")
            self.number += 1

class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_kernel_snap_request_and_paused_cache_rules(self):
        enriched = {'parts':[{'kernel_snaps':[0,0,0,0]}]}
        self.service.geometry.generate = AsyncMock(return_value=enriched)
        result = await self.call('asset.geometry', {'id':'fixture','kernel_snaps':True})
        self.assertEqual(result['mesh'], enriched)
        self.service.geometry.generate.assert_awaited_once_with('fixture', None, kernel_snaps=True)
        self.service.geometry.generate.reset_mock()
        self.service.model_enabled = False
        with patch.object(self.service.geometry, 'cached', return_value={'parts':[{}]}):
            with self.assertRaisesRegex(ValueError, '模型连接已暂停'):
                await self.call('asset.geometry', {'id':'fixture','kernel_snaps':True})
        self.service.geometry.generate.assert_not_awaited()
        with patch.object(self.service.geometry, 'cached', return_value=enriched):
            self.assertEqual((await self.call('asset.geometry', {'id':'fixture','kernel_snaps':True}))['mesh'], enriched)

    async def test_native_mixed_capture_overrides_manual_kind_and_disables_whole_model_boolean(self):
        self.service.native.worker('hwnd:42','a'*36,capabilities=['selection-kind-v1'])
        model=model_bytes(count=2)
        self.service.native.request=AsyncMock(return_value={'model':model,'kind':'mixed'})
        asset=await self.call('library.capture',{'name':'Mixed','kind':'solid','copy_selection':True,'transport':'native','target_id':'hwnd:42','preview_mode':'geometry','insert_mode':'difference'})
        self.assertEqual(asset['kind'],'mixed')
        self.assertEqual(asset['insert_mode'],'new-body')
        self.service.native.request.assert_awaited_once_with('hwnd:42','capture',with_metadata=True)
        # Older cached records must also be protected when inserting.
        with self.service.library.connect() as db:
            db.execute("UPDATE assets SET insert_mode='difference' WHERE id=?",(asset['id'],))
        self.service.native.request=AsyncMock(return_value={'started':True})
        await self.call('asset.insert',{'id':asset['id'],'transport':'native','target_id':'hwnd:42'})
        self.service.native.request.assert_awaited_once_with('hwnd:42','insert',model,True,'new-body')
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.desktop = FakeDesktop()
        config = {"server": {"http_port": 15150}, "plasticity": {"cdp_endpoints": []}, "keymap": {"desktop_shortcuts": DEFAULT_SHORTCUTS}}
        self.service = AssetService(config, self.directory.name, desktop=self.desktop)
        await self.service.state()

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def call(self, action, args):
        return await self.service.dispatch(action, args, "http://127.0.0.1:15150")

    async def test_default_insert_is_ctrl_shift_v_with_exact_model_bytes(self):
        asset = self.service.library.add(model_bytes("saved-component"), {"name": "test"})
        result = await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42"})
        self.assertEqual(self.desktop.data, model_bytes("saved-component"))
        self.assertIn(("shortcut", 42, "ctrl+shift+v"), self.desktop.calls)
        self.assertFalse(result["verified"])

    async def test_native_insert_and_capture_do_not_touch_clipboard(self):
        model = model_bytes("native-component")
        asset = self.service.library.add(model, {"name": "native"})
        original = self.desktop.data
        self.service.native.request = AsyncMock(return_value={"started": True})
        await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42", "transport": "native"})
        self.service.native.request.assert_awaited_once_with("hwnd:42", "insert", model, True, "new-body")
        self.service.native.request = AsyncMock(return_value=model)
        saved = await self.call("library.capture", {"name": "direct", "target_id": "hwnd:42", "transport": "native", "copy_selection": True, "preview_mode": "geometry"})
        self.assertEqual(bytes(self.service.library.get(saved["id"])["model"]), model)
        self.assertEqual(self.desktop.data, original)
        self.assertEqual(self.desktop.calls, [])

    async def test_insert_uses_saved_mode_and_original_position_stays_independent(self):
        model=model_bytes("cutter")
        asset=self.service.library.add(model,{"name":"cutter","insert_mode":"difference"})
        self.service.native.request=AsyncMock(return_value={"started":True})
        await self.call("asset.insert",{"id":asset["id"],"target_id":"hwnd:42","transport":"native","insert_mode":"union"})
        self.service.native.request.assert_awaited_once_with("hwnd:42","insert",model,True,"difference")
        self.service.native.request.reset_mock()
        await self.call("asset.insert",{"id":asset["id"],"target_id":"hwnd:42","transport":"native","placement":False})
        self.service.native.request.assert_awaited_once_with("hwnd:42","insert",model,False,"new-body")
        with self.assertRaisesRegex(ValueError,"原生模型直连"):
            await self.call("asset.insert",{"id":asset["id"],"target_id":"hwnd:42"})
        self.assertEqual(self.desktop.calls,[])

    async def test_connected_native_window_survives_missing_desktop_listing(self):
        self.service.native.worker('hwnd:43','b'*36)
        state=await self.service.state()
        self.assertIn('hwnd:43',[row['id'] for row in state['targets']])
        self.assertIn('hwnd:43',state['native_targets'])

    async def test_group_capture_uses_native_recipe_and_saved_recipe_for_insert(self):
        model=model_bytes(count=2)
        self.service.native.request=AsyncMock(return_value={'model':model,'recipe':recipe()})
        saved=await self.call('library.capture',{'name':'组组件','copy_selection':True,'transport':'native','target_id':'hwnd:42','group_signature':'selected-group','preview_mode':'geometry','recipe':{'fake':True}})
        self.service.native.request.assert_awaited_once_with('hwnd:42','capture-group',signature='selected-group')
        self.assertEqual(saved['recipe'],recipe())
        self.service.native.request=AsyncMock(return_value={'started':True})
        await self.call('asset.insert',{'id':saved['id'],'target_id':'hwnd:42','transport':'native'})
        self.service.native.request.assert_awaited_once_with('hwnd:42','insert',model,True,'new-body',recipe=recipe())
        with self.assertRaisesRegex(ValueError,'原生模型直连'):
            await self.call('asset.insert',{'id':saved['id'],'target_id':'hwnd:42'})
        self.assertEqual(self.desktop.calls,[])

    async def test_follow_active_is_resolved_at_insert_time(self):
        asset=self.service.library.add(model_bytes(),{'name':'follow'})
        self.desktop.windows=lambda:[{'id':'hwnd:42','hwnd':42,'title':'A','mode':'desktop'},{'id':'hwnd:43','hwnd':43,'title':'B','mode':'desktop'}]
        self.desktop.active_window=lambda:43
        self.service.native.request=AsyncMock(return_value={'started':True})
        await self.call('asset.insert',{'id':asset['id'],'target_id':'hwnd:42','transport':'native','follow_active':True})
        self.assertEqual(self.service.native.request.call_args.args[0],'hwnd:43')
        await self.call('asset.insert',{'id':asset['id'],'target_id':'hwnd:42','transport':'native'})
        self.assertEqual(self.service.native.request.call_args.args[0],'hwnd:42')

    async def test_plain_paste_is_explicit_and_copy_does_not_paste(self):
        asset = self.service.library.add(model_bytes(), {"name": "test"})
        await self.call("asset.copy", {"id": asset["id"]})
        self.assertFalse(any(c[0] == "shortcut" for c in self.desktop.calls))
        await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42", "placement": False})
        self.assertIn(("shortcut", 42, "ctrl+v"), self.desktop.calls)

    async def test_follow_active_never_falls_back_to_a_stale_ui_target(self):
        asset=self.service.library.add(model_bytes(),{'name':'saved'})
        self.service.native.request=AsyncMock(return_value={'started':True})
        with patch.object(self.service.bridge,'discover',new=AsyncMock()), patch.object(self.service.bridge,'active_target_id',None):
            for action,args in [
                ('asset.insert',{'id':asset['id']}),
                ('library.capture',{'name':'new','copy_selection':True}),
            ]:
                with self.assertRaisesRegex(ValueError,'激活 Plasticity'):
                    await self.call(action,args | {'target_id':'hwnd:42','transport':'native','follow_active':True})
        self.service.native.request.assert_not_awaited()
        self.assertEqual(self.desktop.calls,[])

    async def test_closed_target_and_archived_asset_never_change_clipboard(self):
        asset = self.service.library.add(b"geometry", {"name": "test"})
        with self.assertRaises(ValueError):
            await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:99"})
        self.service.library.archive(asset["id"], True)
        with self.assertRaises(ValueError):
            await self.call("asset.copy", {"id": asset["id"]})
        self.assertEqual(self.desktop.calls, [])

    async def test_capture_selection_waits_for_new_clipboard(self):
        asset = await self.call("library.capture", {"name": "selected", "copy_selection": True, "target_id": "hwnd:42"})
        self.assertEqual(self.service.library.get(asset["id"])["model"], model_bytes("new-selection"))
        self.assertEqual(asset["source_version"], "26.1.3")

    async def test_auto_copy_invalid_selection_never_saves_old_clipboard(self):
        def invalid_copy(hwnd, shortcut):
            self.desktop.calls.append(("shortcut", hwnd, shortcut))
            self.desktop.data = b"not a Plasticity model"
            self.desktop.number += 1
        with patch.object(self.desktop, "shortcut", side_effect=invalid_copy):
            with self.assertRaisesRegex(ValueError, "阻止置入"):
                await self.call("library.capture", {"name": "selected", "copy_selection": True, "target_id": "hwnd:42"})
        self.assertEqual(self.service.library.list(), [])
        self.assertEqual(self.desktop.calls, [("shortcut", 42, "ctrl+c")])

    async def test_auto_preview_and_manual_override_and_disable(self):
        jpeg=b"\xff\xd8viewport"
        with patch.object(self.service.bridge,"preview",new=AsyncMock(return_value=jpeg)) as preview:
            asset=await self.call("library.capture",{"name":"auto","target_id":"hwnd:42","auto_preview":True})
            self.assertEqual(self.service.library.get(asset["id"])["preview"],jpeg)
            preview.assert_awaited_once_with("hwnd:42")
            preview.reset_mock()
            manual="data:image/jpeg;base64,"+base64.b64encode(b"\xff\xd8manual").decode()
            asset=await self.call("library.capture",{"name":"manual","target_id":"hwnd:42","preview":manual})
            self.assertEqual(self.service.library.get(asset["id"])["preview"],b"\xff\xd8manual")
            await self.call("library.capture",{"name":"disabled","target_id":"hwnd:42","auto_preview":False})
            preview.assert_not_awaited()

    async def test_preview_failure_does_not_prevent_model_save_and_warns(self):
        with patch.object(self.service.bridge,"preview",new=AsyncMock(side_effect=RuntimeError("not available"))):
            asset=await self.call("library.capture",{"name":"saved","target_id":"hwnd:42"})
            self.assertEqual(self.service.library.get(asset["id"])["model"],self.desktop.data)
            self.assertFalse(asset["has_preview"])
            self.assertIn("preview_warning",asset)

    async def test_invalid_metadata_does_not_issue_copy(self):
        with self.assertRaises(ValueError):
            await self.call("library.capture", {"name": "", "copy_selection": True, "target_id": "hwnd:42"})
        self.assertEqual(self.desktop.calls, [])

    async def test_invalid_destination_does_not_touch_clipboard(self):
        with self.assertRaises(ValueError):
            await self.call("library.capture", {"name": "A", "copy_selection": True, "target_id": "hwnd:42", "library_id": "missing"})
        self.assertEqual(self.desktop.calls, [])

    async def test_state_and_rpc_operations_respect_selected_library(self):
        collection = await self.call("collection.create", {"name": "models"})
        folder = await self.call("folder.create", {"library_id": collection["id"], "name": "parts"})
        asset = await self.call("library.capture", {"name": "A", "library_id": collection["id"], "folder_id": folder["id"], "kind": "solid"})
        state = await self.call("state", {"library_id": collection["id"]})
        self.assertEqual(state["assets"][0]["id"], asset["id"])
        self.assertEqual(state["folders"][0]["id"], folder["id"])
        self.assertEqual((await self.call("state", {}))["assets"], [])

    async def test_invalid_preview_does_not_issue_copy_or_save(self):
        for value in ["data:image/jpeg;base64,%%%", "data:image/jpeg;base64," + base64.b64encode(b"not-jpeg").decode()]:
            with self.assertRaises(ValueError):
                await self.call("library.capture", {"name": "test", "copy_selection": True, "target_id": "hwnd:42", "preview": value})
        self.assertEqual(self.desktop.calls, [])
        self.assertEqual(self.service.library.list(), [])

    async def test_edit_preview_preserve_replace_and_clear(self):
        old, new = b"\xff\xd8old", b"\xff\xd8new"
        asset = self.service.library.add(b"geometry", {"name": "test"}, old)
        await self.call("library.update", {"id": asset["id"], "note": "keep"})
        self.assertEqual(self.service.library.get(asset["id"])["preview"], old)
        await self.call("library.update", {"id": asset["id"], "preview": "data:image/jpeg;base64," + base64.b64encode(new).decode()})
        self.assertEqual(self.service.library.get(asset["id"])["preview"], new)
        await self.call("library.update", {"id": asset["id"], "preview": ""})
        self.assertIsNone(self.service.library.get(asset["id"])["preview"])
        self.assertEqual(self.desktop.calls, [])

    async def test_multiple_requests_keep_responses_separate(self):
        a, b = await asyncio.gather(self.call("library.capture", {"name": "A"}), self.call("library.capture", {"name": "B"}))
        self.assertEqual((a["name"], b["name"]), ("A", "B"))
        self.assertNotEqual(a["id"], b["id"])

    async def test_native_transform_shortcuts(self):
        for command, shortcut in [("move", "g"), ("rotate", "r"), ("scale", "s")]:
            await self.call("target.command", {"target_id": "hwnd:42", "command": command})
            self.assertIn(("shortcut", 42, shortcut), self.desktop.calls)

    async def test_tracks_active_model_across_multiple_windows_and_browser_focus(self):
        first = self.desktop.windows()[0]
        second = {**first, "id": "hwnd:43", "hwnd": 43, "title": "Second model"}
        with patch.object(self.desktop, "windows", return_value=[first, second]), patch.object(self.desktop, "active_window", create=True, return_value=42) as active:
            self.assertEqual((await self.service.state())["active_target_id"], "hwnd:42")
            active.return_value = 43
            self.assertEqual((await self.service.state())["active_target_id"], "hwnd:43")
            active.return_value = None  # Opening the component UI retains the last model.
            self.assertEqual((await self.service.state())["active_target_id"], "hwnd:43")
            with patch.object(self.desktop, "windows", return_value=[first]):
                self.assertIsNone((await self.service.state())["active_target_id"])

    async def test_invalid_saved_or_imported_model_does_not_write_or_activate(self):
        asset = self.service.library.add(b"text disguised as a model", {"name": "invalid"})
        for action in ("asset.copy", "asset.insert"):
            with self.assertRaisesRegex(ValueError, "阻止置入"):
                await self.call(action, {"id": asset["id"], "target_id": "hwnd:42"})
        self.assertEqual(self.desktop.calls, [])

    async def test_corrupt_digest_does_not_write_or_activate(self):
        asset = self.service.library.add(model_bytes(), {"name": "test"})
        with self.service.library.connect() as db:
            db.execute("UPDATE assets SET digest='wrong' WHERE id=?", (asset["id"],))
        with self.assertRaisesRegex(ValueError, "校验失败"):
            await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42"})
        self.assertEqual(self.desktop.calls, [])

    async def test_invalid_clipboard_is_not_saved_or_pasted(self):
        self.desktop.data = b"plain text"
        with self.assertRaises(ValueError):
            await self.call("library.capture", {"name": "invalid"})
        for command in ("paste", "place"):
            with self.assertRaises(ValueError):
                await self.call("target.command", {"target_id": "hwnd:42", "command": command})
        self.assertEqual(self.service.library.list(), [])
        self.assertEqual(self.desktop.calls, [])

    async def test_clipboard_replaced_before_paste_never_sends_shortcut(self):
        asset = self.service.library.add(model_bytes(), {"name": "test"})
        for replacement in (b"text", model_bytes("other component")):
            with patch.object(self.desktop, "read", return_value=replacement):
                with self.assertRaises((ValueError, RuntimeError)):
                    await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42"})
        self.assertFalse(any(call[0] == "shortcut" for call in self.desktop.calls))

class CdpTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsolicited_events_do_not_replace_command_response(self):
        cdp = CdpConnection("ws://127.0.0.1:9223/devtools/page/test")
        cdp.socket = AsyncMock()
        cdp.socket.read_message.side_effect = [json.dumps({"method": "Runtime.consoleAPICalled"}), json.dumps({"id": 900, "result": {"wrong": True}}), json.dumps({"id": 1, "result": {"right": True}})]
        self.assertEqual(await cdp.call("Runtime.evaluate"), {"right": True})

    async def test_remote_exception_is_propagated(self):
        cdp = CdpConnection("ws://localhost:9223/test")
        cdp.call = AsyncMock(return_value={"exceptionDetails": {"exception": {"description": "busy"}}})
        with self.assertRaisesRegex(RuntimeError, "busy"):
            await cdp.evaluate("test")

    def test_remote_endpoints_rejected(self):
        for url in ["http://example.com:9223", "https://127.0.0.1:9223", "http://user:secret@127.0.0.1:9223"]:
            with self.assertRaises(ValueError):
                local_url(url)

if __name__ == "__main__":
    unittest.main()
