import shutil
import subprocess
import unittest
from pathlib import Path


class UiUpdateTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_updates_wait_for_safe_complete_build_and_stop_cleanly(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', str(root / 'tests/test_ui_updates.js')], cwd=root,
                       check=True, capture_output=True, timeout=10)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_parent_handshake_survives_ui_reload_and_base_point_then_placement(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', str(root / 'tests/test_host_messaging.mjs')], cwd=root,
                       check=True, capture_output=True, timeout=10)
