import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from main_embed_install import install, patch_main, restore


ORIGINAL = b'"use strict";\r\nrequire("./index.compiled.jsc");\r\n'


class MainEmbedInstallTests(unittest.TestCase):
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
