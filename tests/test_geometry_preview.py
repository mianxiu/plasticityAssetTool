import asyncio
import hashlib
import tempfile
import unittest
import uuid
import shutil
import subprocess
from pathlib import Path
from backend.asset_library import AssetLibrary
from backend.geometry_preview import GeometryPreview, validate_mesh
from model_fixture import model_bytes


def mesh():
    return {"version": 1, "parts": [{"positions": [0, 0, 0, 1, 0, 0, 0, 1, 0],
            "normals": [0, 0, 1] * 3, "indices": [0, 1, 2], "edges": [0, 0, 0, 1, 0, 0], "edge_groups": [0, 6]}]}


class GeometryTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_native_curve_sampling(self):
        root = Path(__file__).resolve().parent.parent
        subprocess.run(['node', str(root / 'tests/test_curve_preview.js')],
            cwd=root, check=True, capture_output=True, timeout=10)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_geometry_memory_cache(self):
        root = Path(__file__).resolve().parent.parent
        subprocess.run(['node', str(root / 'tests/test_geometry_cache.mjs')],
            cwd=root, check=True, capture_output=True, timeout=10)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.library = AssetLibrary(self.directory.name)
        self.preview = GeometryPreview(self.library)
        self.model = model_bytes()
        self.asset = self.library.add(self.model, {"name": "test"})
        self.target, self.token = "hwnd:123", str(uuid.uuid4())

    def tearDown(self):
        self.directory.cleanup()

    async def job(self):
        self.preview.worker(self.target, self.token)
        task = asyncio.create_task(self.preview.generate(self.asset["id"], self.target))
        for _ in range(20):
            if self.preview.jobs:
                break
            await asyncio.sleep(.01)
        job = self.preview.worker(self.target, self.token)
        self.assertIsNotNone(job)
        return task, job

    async def test_native_bytes_cache_thumbnail_and_offline_read(self):
        task, job = await self.job()
        self.preview.worker(self.target, self.token, {"id": job["id"], "mesh": mesh()})
        self.assertEqual(await task, mesh())
        self.assertEqual(self.library.get(self.asset["id"])["model"], self.model)
        self.assertEqual(self.library.get(self.asset["id"])["digest"], hashlib.sha256(self.model).hexdigest())
        self.preview.save_thumbnail(self.asset["id"], self.asset["digest"], b"\xff\xd8thumbnail")
        self.assertTrue(self.library.details(self.asset["id"])["has_geometry_preview"])
        self.preview.workers.clear()
        self.assertEqual(await self.preview.generate(self.asset["id"]), mesh())
        # Duplicates reuse the digest cache without loading a kernel again.
        duplicate = self.library.add(self.model, {"name": "duplicate"})
        self.assertEqual(self.preview.thumbnail(duplicate["id"]), b"\xff\xd8thumbnail")

    async def test_other_window_cannot_complete_job_and_errors_not_cached(self):
        task, job = await self.job()
        self.preview.worker("hwnd:456", str(uuid.uuid4()), {"id": job["id"], "mesh": mesh()})
        self.assertFalse(task.done())
        invalid = mesh();invalid["parts"][0]["indices"][0] = 99
        self.preview.worker(self.target, self.token, {"id": job["id"], "mesh": invalid})
        with self.assertRaisesRegex(ValueError, "越界"):
            await task
        self.assertIsNone(self.preview.cached(self.asset["id"]))
        self.assertEqual(self.library.get(self.asset["id"])["model"], self.model)

    async def test_digest_corruption_never_queues_native_work(self):
        with self.library.connect() as db:
            db.execute("UPDATE assets SET model=? WHERE id=?", (b"corrupt", self.asset["id"]))
        with self.assertRaisesRegex(ValueError, "校验失败"):
            await self.preview.generate(self.asset["id"])
        self.assertEqual(self.preview.jobs, {})

    async def test_disconnected_window_and_thumbnail_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "插件未连接"):
            await self.preview.generate(self.asset["id"], self.target)
        with self.assertRaisesRegex(ValueError, "不匹配"):
            self.preview.save_thumbnail(self.asset["id"], "wrong", b"\xff\xd8image")

    def test_invalid_coordinates_indices_and_edge_groups_rejected(self):
        for key, value in [("positions", [float('nan')] * 9), ("indices", [-1, 1, 2]),
                           ("edge_groups", [0, 9]), ("edge_groups", [1, 3]), ("normals", []),
                           ("indices", [False, 1, 2])]:
            data = mesh();data["parts"][0][key] = value
            with self.assertRaises(ValueError, msg=key):
                validate_mesh(data)

    def test_curve_only_is_supported(self):
        data = mesh();part = data["parts"][0]
        part["positions"] = part["normals"] = part["indices"] = []
        self.assertEqual(validate_mesh(data), data)

    def test_kernel_snap_validation_and_legacy_compatibility(self):
        data = mesh()
        data['parts'][0]['kernel_snaps'] = [0, 0, 0, 0, .25, 1, 0, 2]
        self.assertEqual(validate_mesh(data), data)
        for invalid in [[0, 0, 0], [0, 0, 0, 3], [0, 0, 0, True],
                        [float('nan'), 0, 0, 0], [1e13, 0, 0, 0], 'bad']:
            data['parts'][0]['kernel_snaps'] = invalid
            with self.assertRaises(ValueError):
                validate_mesh(data)
        self.assertEqual(validate_mesh(mesh()), mesh())

    async def test_kernel_snap_upgrade_preserves_existing_cache_until_success(self):
        task, job = await self.job()
        self.preview.worker(self.target, self.token, {'id': job['id'], 'mesh': mesh()})
        await task
        upgrade = asyncio.create_task(self.preview.generate(self.asset['id'], self.target, kernel_snaps=True))
        for _ in range(20):
            if self.preview.jobs:
                break
            await asyncio.sleep(.01)
        job = self.preview.worker(self.target, self.token)
        self.assertIsNotNone(job, 'Legacy mesh should request enriched geometry without deleting the existing preview')
        self.assertEqual(self.preview.cached(self.asset['id']), mesh())
        enriched = mesh(); enriched['parts'][0]['kernel_snaps'] = [0, 0, 0, 0]
        self.preview.worker(self.target, self.token, {'id': job['id'], 'mesh': enriched})
        self.assertEqual(await upgrade, enriched)
        self.preview.workers.clear()
        self.assertEqual(await self.preview.generate(self.asset['id'], kernel_snaps=True), enriched, 'Enriched points should work offline')

    async def test_kernel_snap_upgrade_error_retains_ordinary_preview(self):
        task, job = await self.job()
        self.preview.worker(self.target, self.token, {'id': job['id'], 'mesh': mesh()})
        await task
        self.preview.workers.clear()
        with self.assertRaisesRegex(ValueError, '插件未连接'):
            await self.preview.generate(self.asset['id'], self.target, kernel_snaps=True)
        self.assertEqual(await self.preview.generate(self.asset['id']), mesh())
