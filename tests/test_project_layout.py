"""Verify entry points and resource lookup after moving the Python modules."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.main import ROOT as BACKEND_ROOT
from backend.plasticity_bridge import ROOT as BRIDGE_ROOT
from installer.main_embed_install import ROOT as INSTALLER_ROOT


class ProjectLayoutTests(unittest.TestCase):
    def test_resource_roots_still_point_to_repository(self):
        root = Path(__file__).resolve().parent.parent
        for resource_root in (BACKEND_ROOT, BRIDGE_ROOT, INSTALLER_ROOT):
            self.assertEqual(resource_root, root)
            self.assertTrue((resource_root / 'config.json').is_file())
            self.assertTrue((resource_root / 'plasticity-javascript-payloads/init.js').is_file())

    def test_root_launcher_works_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(BACKEND_ROOT / 'main.py'), '--help'],
                cwd=directory, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'--reuse-only', result.stdout)

    def test_installer_module_installs_and_restores_a_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'main/index.js'
            target.parent.mkdir()
            original = b"require('./index.compiled.jsc');\n"
            target.write_bytes(original)
            backup = Path(directory) / 'backup.js'
            command = [sys.executable, '-m', 'installer.main_embed_install']
            result = subprocess.run(command + ['--target', str(target), '--backup', str(backup)],
                cwd=BACKEND_ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['target'], str(target.resolve()))
            self.assertNotEqual(target.read_bytes(), original)
            result = subprocess.run(command + ['--restore', '--backup', str(backup)],
                cwd=BACKEND_ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), original)
