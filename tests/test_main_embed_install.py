import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess
import shutil
from installer.main_embed_install import install, patch_main, restore, upgrade


ORIGINAL = b'"use strict";\r\nrequire("./index.compiled.jsc");\r\n'


class MainEmbedInstallTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for session test')
    def test_secondary_window_sessions_receive_preload_once(self):
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            entry=Path(directory)/'hook.js'
            entry.write_bytes(patch_main(ORIGINAL,'function installAssetPanel(){}','http://127.0.0.1:15150/'))
            subprocess.run(['node',str(root/'tests/test_window_preloads.js'),str(entry)],check=True,capture_output=True,timeout=10)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for renderer test')
    def test_offline_notice_toggle_reconnect_and_cleanup(self):
        root = Path(__file__).resolve().parent.parent
        subprocess.run(['node',str(root/'tests/test_embed_offline.js'),str(root/'plasticity-javascript-payloads/init.js')],check=True,capture_output=True,timeout=10)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required for main hook test')
    def test_tab_probes_server_identity_and_closes_without_probe(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            entry=Path(directory)/'hook.js'
            entry.write_bytes(patch_main(ORIGINAL,'function installAssetPanel(){}','http://127.0.0.1:15150/'))
            subprocess.run(['node',str(root/'tests/test_main_health.js'),str(entry)],check=True,capture_output=True,timeout=10)

    def test_upgrade_keeps_previous_hook_and_can_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'main/index.js';target.parent.mkdir();target.write_bytes(ORIGINAL)
            original=Path(directory)/'original.js';install(target,original)
            prior=target.read_bytes()
            rollback=Path(directory)/'prior-hook.js'
            upgrade(target,original,rollback)
            self.assertEqual(rollback.read_bytes(),prior)
            target.write_bytes(target.read_bytes()+b'changed')
            with self.assertRaises(ValueError):upgrade(target,original,rollback)
            target.write_bytes(prior)
            restore(original)
            self.assertEqual(target.read_bytes(),ORIGINAL)

    def test_second_upgrade_uses_verified_unmodified_base_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'main/index.js';target.parent.mkdir();target.write_bytes(ORIGINAL)
            base=Path(directory)/'original.js';install(target,base)
            first=Path(directory)/'first.js';upgrade(target,base,first)
            previous=target.read_bytes()
            second=Path(directory)/'second.js';upgrade(target,first,second,base)
            self.assertTrue(target.read_bytes().endswith(ORIGINAL))
            restore(second)
            self.assertEqual(target.read_bytes(),previous)
    def test_preserves_compiled_loader_and_rejects_duplicate_or_unknown_entry(self):
        result = patch_main(ORIGINAL, 'function installAssetPanel(){}', 'http://127.0.0.1:15150/')
        self.assertTrue(result.endswith(ORIGINAL))
        self.assertNotIn(b'app.setPath', result)
        for invalid in (b'require("other.js");', result):
            with self.assertRaises(ValueError):
                patch_main(invalid, '', '')

    def test_restore_refuses_changes_then_recovers_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'main/index.js'
            target.parent.mkdir()
            target.write_bytes(ORIGINAL)
            backup = Path(directory) / 'original.js'
            install(target, backup)
            patched = target.read_bytes()
            target.write_bytes(patched + b'other change')
            with self.assertRaises(ValueError):
                restore(backup)
            target.write_bytes(patched)
            restore(backup)
            restore(backup)
            self.assertEqual(target.read_bytes(), ORIGINAL)

    def test_permission_failure_can_retry_with_existing_verified_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'main/index.js'
            target.parent.mkdir()
            target.write_bytes(ORIGINAL)
            backup = Path(directory) / 'original.js'
            write_bytes = Path.write_bytes

            def protected_write(path, data):
                if path == target:
                    raise PermissionError('protected application')
                return write_bytes(path, data)

            with patch.object(Path, 'write_bytes', protected_write):
                with self.assertRaises(PermissionError):
                    install(target, backup)
            self.assertEqual(target.read_bytes(), ORIGINAL)
            self.assertEqual(backup.read_bytes(), ORIGINAL)
            install(target, backup)
            restore(backup)
            backup.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                install(target, backup)
            self.assertEqual(target.read_bytes(), ORIGINAL)
