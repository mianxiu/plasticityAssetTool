import tempfile
import unittest
from pathlib import Path
from embedded_install import install, patch_html, restore


class EmbedInstallTests(unittest.TestCase):
    def test_patch_keeps_app_root_and_script_and_is_not_duplicated(self):
        original = b'<html><script src="index.js"></script><body><div id="root"></div></body></html>'
        result = patch_html(original, 'function installAssetPanel(){}', 'http://127.0.0.1:15150/?embedded=1')
        self.assertIn(b'src="index.js"', result)
        self.assertIn(b'id="root"', result)
        self.assertIn(b'"hidden": true', result)
        with self.assertRaises(ValueError):
            patch_html(result,'','')

    def test_install_restore_exact_bytes_and_refuse_overwriting_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'app_window/index.html'
            target.parent.mkdir()
            original = b'<body><div id="root"></div></body>\r\n'
            target.write_bytes(original)
            backup = Path(folder)/'original.html'
            install(target,backup)
            patched = target.read_bytes()
            target.write_bytes(patched+b'other-change')
            with self.assertRaises(ValueError):
                restore(backup)
            target.write_bytes(patched)
            restore(backup)
            self.assertEqual(target.read_bytes(),original)

    def test_unknown_html_is_not_changed(self):
        with self.assertRaises(ValueError):
            patch_html(b'<body>other</body>','','')
