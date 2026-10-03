import asyncio
import base64
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from asset_service import AssetService
from main import DEFAULT_SHORTCUTS
from plasticity_bridge import CdpConnection, local_url

class FakeDesktop:
    def __init__(self):
        self.data = b"original-model"
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
            self.data = b"new-selection"
            self.number += 1

class ServiceTests(unittest.IsolatedAsyncioTestCase):
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
        asset = self.service.library.add(b"saved-component\0\xff", {"name": "test"})
        result = await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42"})
        self.assertEqual(self.desktop.data, b"saved-component\0\xff")
        self.assertIn(("shortcut", 42, "ctrl+shift+v"), self.desktop.calls)
        self.assertFalse(result["verified"])

    async def test_plain_paste_is_explicit_and_copy_does_not_paste(self):
        asset = self.service.library.add(b"geometry", {"name": "test"})
        await self.call("asset.copy", {"id": asset["id"]})
        self.assertFalse(any(c[0] == "shortcut" for c in self.desktop.calls))
        await self.call("asset.insert", {"id": asset["id"], "target_id": "hwnd:42", "placement": False})
        self.assertIn(("shortcut", 42, "ctrl+v"), self.desktop.calls)

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
        self.assertEqual(self.service.library.get(asset["id"])["model"], b"new-selection")
        self.assertEqual(asset["source_version"], "26.1.3")

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
