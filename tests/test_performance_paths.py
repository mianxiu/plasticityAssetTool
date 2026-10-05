import asyncio
import json
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from backend import model_clipboard as models
from backend.asset_service import AssetService
from backend.geometry_preview import GeometryPreview
from backend.plasticity_bridge import PlasticityBridge
from model_fixture import model_bytes
from test_asset_service import FakeDesktop
from test_geometry_preview import mesh


class PerformanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.desktop = FakeDesktop()
        self.service = AssetService({'plasticity': {'cdp_endpoints': []}}, self.temp.name, self.desktop)

    async def test_cached_previews_never_read_model_blob(self):
        asset = self.service.library.add(model_bytes(), {'name': 'cached'})
        with self.service.library.connect() as db:
            db.execute('INSERT INTO geometry_cache(digest,mesh,thumbnail) VALUES (?,?,?)',
                       (asset['digest'], zlib.compress(json.dumps(mesh()).encode()), b'\xff\xd8image'))
        with patch.object(self.service.library, 'get', side_effect=AssertionError('full row')), \
             patch.object(self.service.library, 'model_row', side_effect=AssertionError('model BLOB')):
            self.assertEqual(await self.service.geometry.generate(asset['id']), mesh())
            self.assertEqual(self.service.geometry.thumbnail(asset['id']), b'\xff\xd8image')
            self.service.geometry.save_thumbnail(asset['id'], asset['digest'], b'\xff\xd8new')

    async def test_library_refresh_does_not_wait_for_model_lock_or_discovery(self):
        async with self.service.lock:
            with patch.object(self.service.bridge, 'discover', side_effect=AssertionError('window scan')):
                state = await asyncio.wait_for(self.service.dispatch('library.state', {}, ''), 1)
        self.assertEqual(state['assets'], [])

    async def test_active_windows_stay_fresh_while_cdp_scan_is_cached(self):
        bridge = PlasticityBridge({'plasticity': {'cdp_endpoints': []}}, self.desktop)
        one = self.desktop.windows()[0]
        two = {**one, 'id': 'hwnd:43', 'hwnd': 43}
        with patch.object(self.desktop, 'windows', return_value=[one, two]) as windows, \
             patch.object(self.desktop, 'active_window', create=True, return_value=42) as active, \
             patch.object(bridge, '_discover', wraps=bridge._discover) as scan:
            await bridge.discover()
            active.return_value = 43
            await bridge.discover()
            self.assertEqual(bridge.active_target_id, 'hwnd:43')
            self.assertEqual(scan.call_count, 1)
            windows.return_value = [one]
            active.return_value = None
            await bridge.discover()
            self.assertIsNone(bridge.active_target_id)

    async def test_preview_dispatch_yields_to_model_commands(self):
        geometry = self.service.geometry
        import uuid
        token = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        geometry.jobs['job'] = {'target': 'hwnd:42', 'future': future, 'sent': False, 'parts': []}
        async with self.service.lock:
            self.assertIsNone(geometry.worker('hwnd:42', token))
            self.assertFalse(geometry.jobs['job']['sent'])
        self.assertEqual(geometry.worker('hwnd:42', token)['id'], 'job')
        future.cancel()

    def test_model_cache_reuses_validation_and_encoding_without_trusting_changed_bytes(self):
        data = model_bytes('cache-performance-unique')
        with patch.object(models, '_parse_model', wraps=models._parse_model) as parse, \
             patch.object(models.base64, 'b64encode', wraps=models.base64.b64encode) as encode:
            models.validate_model(data)
            parts = models.parse_model(data)
            parts[0][1]['name'] = 'modified'
            first = models.encoded_model(data)
            self.assertIs(first, models.encoded_model(bytes(data)))
            self.assertEqual(models.parse_model(data)[0][1]['name'], 'cache-performance-unique')
            self.assertEqual(parse.call_count, 1)
            self.assertEqual(encode.call_count, 1)
            with self.assertRaises(ValueError):
                models.validate_model(data + b'changed')
        self.assertLessEqual(models._cache_bytes, models._CACHE_LIMIT)

    def test_background_preview_queue(self):
        subprocess.run(['node', 'tests/test_preview_queue.mjs'], cwd=Path(__file__).resolve().parent.parent,
                       check=True, capture_output=True, timeout=10)
