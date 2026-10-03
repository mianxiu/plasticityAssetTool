import json
import tempfile
from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.websocket import websocket_connect
from asset_service import AssetService
from main import Application, DEFAULT_SHORTCUTS
from test_asset_service import FakeDesktop


class HttpTests(AsyncHTTPTestCase):
    def get_app(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = {"server": {"http_port": 15150}, "plasticity": {"cdp_endpoints": []}, "keymap": {"desktop_shortcuts": DEFAULT_SHORTCUTS}}
        self.service = AssetService(self.config, self.directory.name, desktop=FakeDesktop())
        return Application(self.config, self.service)

    def tearDown(self):
        super().tearDown()
        self.directory.cleanup()

    def test_health_and_origin_restriction(self):
        self.assertEqual(self.fetch("/api/health").code, 200)
        self.assertEqual(self.fetch("/api/health", headers={"Origin": "https://example.com"}).code, 403)

    def test_export_preserves_native_bytes(self):
        asset = self.service.library.add(b"native-model\0\xff", {"name": "test"})
        response = self.fetch(f"/api/assets/{asset['id']}/export")
        self.assertEqual(response.code, 200)
        imported = self.service.library.import_package(response.body)
        self.assertEqual(self.service.library.get(imported["id"])["model"], b"native-model\0\xff")

    def test_bad_import_does_not_create_component(self):
        boundary = "test-boundary"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="broken.patasset"\r\nContent-Type: application/zip\r\n\r\nbroken\r\n--{boundary}--\r\n').encode()
        response = self.fetch("/api/import", method="POST", body=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        self.assertEqual(response.code, 400)
        self.assertEqual(self.service.library.list(), [])

    def test_preview_replacement_and_removal(self):
        first, second = b"\xff\xd8first", b"\xff\xd8second"
        asset = self.service.library.add(b"geometry", {"name": "test"}, first)
        path = f"/api/assets/{asset['id']}/preview"
        self.assertEqual(self.fetch(path).body, first)
        changed = self.service.library.update(asset["id"], {"preview": second})
        response = self.fetch(path + "?v=" + changed["updated_at"])
        self.assertEqual(response.body, second)
        self.assertEqual(response.headers["Content-Type"], "image/jpeg")
        self.service.library.update(asset["id"], {"preview": None})
        self.assertEqual(self.fetch(path).code, 404)

    @gen_test
    async def test_rpc_error_then_valid_request_on_same_connection(self):
        ws = await websocket_connect(self.get_url("/websocket").replace("http", "ws", 1))
        self.assertEqual(json.loads(await ws.read_message())["type"], "connected")
        await ws.write_message("not-json")
        self.assertFalse(json.loads(await ws.read_message())["ok"])
        await ws.write_message(json.dumps({"id": "request-1", "action": "library.capture", "args": {"name": "test"}}))
        response = json.loads(await ws.read_message())
        self.assertEqual(response["id"], "request-1")
        self.assertTrue(response["ok"])
        self.assertEqual(json.loads(await ws.read_message())["type"], "library_changed")
        ws.close()

    @gen_test
    async def test_cross_origin_websocket_rejected(self):
        request = HTTPRequest(self.get_url("/websocket").replace("http", "ws", 1), headers={"Origin": "https://example.com"})
        with self.assertRaises(Exception) as context:
            await websocket_connect(request)
        self.assertEqual(context.exception.code, 403)
