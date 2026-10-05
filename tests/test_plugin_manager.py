import asyncio
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.plugin_manager import PluginManager
from installer import discovery
from installer.embedded_install import digest
from installer.main_embed_install import install, restore, upgrade, validate_managed

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = b'"use strict";\nrequire("./index.compiled.jsc");\n'


def fixture(root, version='26.1.3'):
    folder = root / 'Plasticity' / ('app-' + version)
    target = folder / discovery.ENTRY
    target.parent.mkdir(parents=True)
    target.write_bytes(ORIGINAL)
    target.with_name('index.compiled.jsc').write_bytes(b'compiled-fixture')
    (folder / 'Plasticity.exe').write_bytes(b'not-an-executable')
    (folder / 'resources/app/package.json').write_text(json.dumps({'version': version}))
    return folder, target


class PluginManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'config.json').write_text(json.dumps({'server': {'http_port': 15150}, 'keymap': {'show_panel_event_key_code': 'Tab'}}))
        shutil.copytree(ROOT / 'plasticity-javascript-payloads', self.root / 'plasticity-javascript-payloads')
        self.folder, self.target = fixture(self.root)
        self.processes = []
        self.manager = PluginManager(self.root, process_reader=lambda: self.processes,
                                     root_reader=lambda: [self.folder.parent], runner=self.run_request)

    def tearDown(self):
        self.temp.cleanup()

    def run_request(self, path):
        request = json.loads(path.read_text(encoding='utf-8'))
        arguments = request['arguments']
        value = lambda key: arguments[arguments.index(key) + 1]
        with patch('installer.discovery.running_processes', return_value=self.processes):
            validate_managed(value('--target'), value('--expected-sha256'),
                             '--allow-unverified-version' in arguments, '--restore' in arguments)
        with patch('installer.main_embed_install.ROOT', self.root):
            if '--restore' in arguments:
                restore(value('--backup'))
            elif '--upgrade-from' in arguments:
                upgrade(value('--target'), value('--upgrade-from'), value('--backup'), value('--base-backup'))
            else:
                install(value('--target'), value('--backup'))
        return 0

    def row(self):
        return self.manager.scan()['installations'][0]

    async def perform(self, action):
        row = self.row()
        await self.manager.start(row['id'], action)
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'complete', self.manager.job)
        return self.row()

    async def test_install_update_and_restore_original_after_multiple_updates(self):
        row = await self.perform('install')
        self.assertEqual(row['state'], 'current')
        self.assertTrue(row['can_restore'])
        for index in range(2):
            script = self.root / 'plasticity-javascript-payloads/init.js'
            script.write_text(script.read_text(encoding='utf-8') + f'\n// new payload {index}', encoding='utf-8')
            self.assertTrue(self.row()['can_update'])
            self.assertEqual((await self.perform('update'))['state'], 'current')
        row = await self.perform('restore')
        self.assertFalse(row['installed'])
        self.assertEqual(self.target.read_bytes(), ORIGINAL)
        self.assertGreaterEqual(len(list((self.root / '.runtime/plugin-backups').glob('*.js'))), 4)

    async def test_running_selected_version_rejects_without_writing_or_launching(self):
        self.processes = [{'Id': 42, 'Path': str(self.folder / 'Plasticity.exe')}]
        row = self.row()
        self.assertTrue(row['running'])
        with self.assertRaises(ValueError):
            await self.manager.start(row['id'], 'install')
        self.assertEqual(self.target.read_bytes(), ORIGINAL)
        self.assertIsNone(self.manager.task)

    def test_other_running_version_does_not_block_selected_version(self):
        other, _ = fixture(self.root, '26.2.0')
        self.processes = [{'Id': 43, 'Path': str(other / 'Plasticity.exe')}]
        row = self.manager.inspect(self.folder, self.processes)
        self.assertTrue(row['can_install'])
        unknown = self.manager.inspect(self.folder, [{'Id': 42, 'Path': None}])
        self.assertFalse(unknown['can_install'])

    async def test_unsupported_version_detected_but_never_installed(self):
        fixture(self.root, '26.2.0')
        row = next(r for r in self.manager.scan()['installations'] if r['version'] == '26.2.0')
        self.assertFalse(row['supported'])
        with self.assertRaises(ValueError):
            await self.manager.start(row['id'], 'install')

    async def test_opt_in_persists_and_other_version_installs_updates_and_restores(self):
        folder, target = fixture(self.root, '26.2.0')
        self.manager.scan()
        state = await self.manager.update_settings(True)
        row = next(r for r in state['installations'] if r['version'] == '26.2.0')
        self.assertTrue(row['experimental'])
        self.assertFalse(row['supported'])
        self.assertTrue(row['can_install'])
        restarted = PluginManager(self.root)
        self.assertTrue(restarted.snapshot()['allow_unverified_versions'])
        await self.manager.start(row['id'], 'install')
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'complete', self.manager.job)
        script = self.root / 'plasticity-javascript-payloads/init.js'
        script.write_text(script.read_text(encoding='utf-8') + '\n// updated', encoding='utf-8')
        row = self.manager.inspect(folder, [])
        self.assertTrue(row['can_update'])
        await self.manager.start(row['id'], 'update')
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'complete', self.manager.job)
        await self.manager.update_settings(False)
        row = self.manager.inspect(folder, [])
        self.assertFalse(row['experimental'])
        self.assertTrue(row['can_restore'])
        await self.manager.start(row['id'], 'restore')
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'complete', self.manager.job)
        self.assertEqual(target.read_bytes(), ORIGINAL)
        self.assertFalse(self.manager.inspect(folder, [])['can_install'])
        self.assertFalse(PluginManager(self.root).allow_unverified_versions)

    async def test_opt_in_keeps_process_and_entry_guards(self):
        folder, target = fixture(self.root, '26.2.0')
        await self.manager.update_settings(True)
        self.processes = [{'Id': 42, 'Path': str(folder / 'Plasticity.exe')}]
        row = self.manager.scan()['installations'][-1]
        self.assertFalse(row['can_install'])
        with self.assertRaises(ValueError):
            await self.manager.start(row['id'], 'install')
        self.assertEqual(target.read_bytes(), ORIGINAL)
        target.write_text('unexpected entry', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'main'):
            self.manager.inspect(folder, [])

    async def test_settings_validate_boolean_and_reject_changes_during_install(self):
        for invalid in (None, 'true', 1, {}, []):
            with self.assertRaises(ValueError):
                await self.manager.update_settings(invalid)
        event = asyncio.Event()
        self.manager.task = asyncio.create_task(event.wait())
        try:
            with self.assertRaisesRegex(ValueError, '正在进行'):
                await self.manager.update_settings(True)
            self.assertFalse(self.manager.allow_unverified_versions)
        finally:
            event.set()
            await self.manager.task

    async def test_cancelled_uac_preserves_original_and_cleans_request(self):
        self.manager.runner = lambda request: 1223
        row = self.row()
        await self.manager.start(row['id'], 'install')
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'cancelled')
        self.assertEqual(self.target.read_bytes(), ORIGINAL)
        self.assertFalse(list((self.root / '.runtime').glob('plugin-install-*.json')))

    async def test_second_install_is_rejected_while_first_waits(self):
        event = threading.Event()
        self.manager.runner = lambda request: event.wait(5) and 1223
        row = self.row()
        await self.manager.start(row['id'], 'install')
        try:
            with self.assertRaisesRegex(ValueError, '正在进行'):
                await self.manager.start(row['id'], 'install')
        finally:
            event.set()
            await self.manager.task

    async def test_modified_installed_entry_is_not_overwritten(self):
        await self.perform('install')
        changed = self.target.read_bytes() + b'\n// unrelated edit'
        self.target.write_bytes(changed)
        row = self.row()
        self.assertEqual(row['state'], 'backup-missing')
        with self.assertRaises(ValueError):
            await self.manager.start(row['id'], 'update')
        self.assertEqual(self.target.read_bytes(), changed)

    async def test_success_exit_without_write_is_detected_as_failure(self):
        self.manager.runner = lambda request: 0
        row = self.row()
        await self.manager.start(row['id'], 'install')
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'failed')
        self.assertFalse(self.row()['installed'])

    def test_custom_directory_deduplicates_and_invalid_directory_rejected(self):
        self.assertEqual(len(self.manager.scan(str(self.folder))['installations']), 1)
        self.assertEqual(len(self.manager.scan(str(self.folder.parent))['installations']), 1)
        for path in ('relative', str(self.root / 'missing')):
            with self.assertRaises(ValueError):
                self.manager.scan(path)

    def test_elevated_guard_rechecks_hash_process_and_version(self):
        with patch('installer.discovery.running_processes', return_value=[]):
            validate_managed(self.target, digest(ORIGINAL))
            with self.assertRaisesRegex(ValueError, '发生变化'):
                validate_managed(self.target, '0' * 64)
            other, entry = fixture(self.root, '26.2.0')
            with self.assertRaisesRegex(ValueError, '尚未验证'):
                validate_managed(entry, digest(ORIGINAL))
            validate_managed(entry, digest(ORIGINAL), allow_unverified_version=True)
            with self.assertRaisesRegex(ValueError, '发生变化'):
                validate_managed(entry, '0' * 64, allow_unverified_version=True)
        with patch('installer.discovery.running_processes', return_value=[{'Id': 43, 'Path': str(other / 'Plasticity.exe')}]):
            with self.assertRaisesRegex(ValueError, '正在运行'):
                validate_managed(entry, digest(ORIGINAL), allow_unverified_version=True)
        with patch('installer.discovery.running_processes', return_value=[{'Id': 42, 'Path': str(self.folder / 'Plasticity.exe')} ]):
            with self.assertRaisesRegex(ValueError, '正在运行'):
                validate_managed(self.target, digest(ORIGINAL))

    async def test_launch_failure_returns_failed_status(self):
        def fail(request):
            raise OSError('installer not found')
        self.manager.runner = fail
        row = self.row()
        await self.manager.start(row['id'], 'install')
        await self.manager.task
        self.assertEqual(self.manager.job['state'], 'failed')
        self.assertIn('installer not found', self.manager.job['message'])
