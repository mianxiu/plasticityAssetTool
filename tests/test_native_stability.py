"""Execute injected scripts against isolated native lifecycle test doubles."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js required for native lifecycle tests')
class NativeStabilityTests(unittest.TestCase):
    def test_worker_disconnect_and_window_lifecycle(self):
        root=Path(__file__).resolve().parent.parent
        subprocess.run(['node','tests/test_native_worker_lifecycle.js'],cwd=root,check=True,capture_output=True,timeout=10)

    def test_boolean_transaction_failure_and_rollback_lock(self):
        root=Path(__file__).resolve().parent.parent
        subprocess.run(['node','tests/test_boolean_rollback.js'],cwd=root,check=True,capture_output=True,timeout=10)

    def test_websocket_reconnect_does_not_replay_operations(self):
        root=Path(__file__).resolve().parent.parent
        subprocess.run(['node','tests/test_websocket_reconnect.js'],cwd=root,check=True,capture_output=True,timeout=10)
