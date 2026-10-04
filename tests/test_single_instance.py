import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.single_instance import BackendInstance
from backend import main
from tornado import web
from tornado.testing import AsyncHTTPTestCase, gen_test


class InstanceLockTests(unittest.TestCase):
    def test_concurrent_processes_and_crash_release(self):
        script = """
import sys
from backend.single_instance import BackendInstance
instance = BackendInstance(sys.argv[1])
owned = instance.acquire()
if owned: instance.publish(15150)
print(int(owned), flush=True)
sys.stdin.readline()
instance.close()
"""
        with tempfile.TemporaryDirectory() as directory:
            processes = [subprocess.Popen([sys.executable, "-c", script, directory],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(8)]
            try:
                owners = [p for p in processes if p.stdout.readline().strip() == "1"]
                self.assertEqual(len(owners), 1)
                observer = BackendInstance(directory)
                self.assertEqual(observer.read_port(), 15150)
                # A contender must not remove the live owner's discovery metadata.
                self.assertFalse(observer.acquire())
                self.assertEqual(observer.read_port(), 15150)
                owners[0].kill()
                owners[0].wait(timeout=5)
                self.assertTrue(observer.acquire())
                self.assertIsNone(observer.read_port())
                observer.publish(15151)
                self.assertEqual(observer.read_port(), 15151)
                observer.close()
                self.assertFalse(observer.metadata.exists())
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.communicate("exit\n", timeout=5)
                    else:
                        process.communicate(timeout=5)

    def test_invalid_metadata_cannot_redirect_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = BackendInstance(directory)
            for port in ["http://example.com", -1, 65536, True, None]:
                instance.metadata.write_text(json.dumps({"port": port}))
                self.assertIsNone(instance.read_port())


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_different_port_reuses_owner_without_constructing_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = BackendInstance(root / ".runtime")
            self.assertTrue(owner.acquire())
            owner.publish(15150)
            try:
                with patch.object(main, "ROOT", root), patch.object(main, "Application") as app, \
                        patch.object(main, "reuse_backend", new_callable=AsyncMock) as reuse:
                    self.assertTrue(await main.run(15151, headless=False))
                    reuse.assert_awaited_once_with(15150, False)
                    app.assert_not_called()
            finally:
                owner.close()

    async def test_secondary_waits_for_primary_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = BackendInstance(root / ".runtime")
            owner.acquire()
            try:
                with patch.object(main, "ROOT", root), \
                        patch.object(main, "reuse_backend", new_callable=AsyncMock) as reuse:
                    pending = asyncio.create_task(main.run(15151, headless=True))
                    await asyncio.sleep(0.15)
                    self.assertFalse(pending.done())
                    owner.publish(15150)
                    await asyncio.wait_for(pending, 2)
                    reuse.assert_awaited_once_with(15150, True)
            finally:
                owner.close()

    async def test_failed_start_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(main, "ROOT", root), \
                    patch.object(main, "run_backend", new_callable=AsyncMock, side_effect=RuntimeError("failed")):
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    await main.run()
            next_instance = BackendInstance(root / ".runtime")
            self.assertTrue(next_instance.acquire())
            next_instance.close()

    async def test_reuse_only_does_not_start_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, "ROOT", Path(directory)), patch.object(main, "Application") as app:
                self.assertFalse(await main.run(reuse_only=True))
                app.assert_not_called()


class ReuseHttpTests(AsyncHTTPTestCase):
    def get_app(self):
        self.actions = []
        self.identity = "plasticity-asset-tool"
        test = self

        class Health(web.RequestHandler):
            def get(self):
                self.write({"app": test.identity})

        class Control(web.RequestHandler):
            def post(self):
                test.actions.append(json.loads(self.request.body)["action"])
                self.write({"ok": True})

        return web.Application([(r"/api/health", Health), (r"/api/service", Control)])

    @gen_test
    async def test_open_is_delegated_to_owner_and_headless_does_not_open(self):
        await main.reuse_backend(self.get_http_port(), True)
        self.assertEqual(self.actions, [])
        await main.reuse_backend(self.get_http_port(), False)
        self.assertEqual(self.actions, ["service.open_control"])

    @gen_test
    async def test_foreign_service_is_not_reused(self):
        self.identity = "other-app"
        with self.assertRaisesRegex(RuntimeError, "端口"):
            await main.reuse_backend(self.get_http_port(), False)
        self.assertEqual(self.actions, [])
