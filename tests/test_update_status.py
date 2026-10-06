import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from backend.update_status import UpdateStatus


class UpdateStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'backend').mkdir()
        (self.root/'backend/main.py').write_text('backend v1')
        (self.root/'main.py').write_text('entry')
        (self.root/'config.json').write_text('{}')
        self.dist=self.root/'plasticity-asset-tool-app/dist'
        (self.dist/'assets').mkdir(parents=True)
        self.build('one')
        self.updates=UpdateStatus(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def build(self,revision):
        (self.dist/'assets/main.js').write_text('UI '+revision)
        (self.dist/'ui-build.json').write_text(json.dumps({'revision':revision,'assets':['assets/main.js']}))
        (self.dist/'index.html').write_text('<meta name="pat-ui-build" content="'+revision+'">')

    def test_ui_and_backend_changes_are_classified_independently(self):
        self.assertEqual(self.updates.snapshot()['backend']['state'],'current')
        self.build('two')
        (self.root/'README.md').write_text('docs updated')
        status=self.updates.snapshot(force=True)
        self.assertEqual(status['ui'],{'state':'ready','revision':'two'})
        self.assertEqual(status['backend']['state'],'current')
        (self.root/'backend/main.py').write_text('backend v2')
        status=self.updates.snapshot(force=True)
        self.assertEqual(status['backend']['state'],'restart-required')
        self.assertNotEqual(status['backend']['loaded_revision'],status['backend']['available_revision'])
        self.assertEqual(UpdateStatus(self.root).snapshot()['backend']['state'],'current')

    def test_incomplete_build_and_unsafe_paths_are_never_ready(self):
        (self.dist/'assets/main.js').unlink()
        self.assertEqual(self.updates.snapshot(True)['ui']['state'],'building')
        self.build('two')
        (self.dist/'index.html').write_text('<meta name="pat-ui-build" content="one">')
        self.assertEqual(self.updates.snapshot(True)['ui']['state'],'building')
        (self.dist/'ui-build.json').write_text(json.dumps({'revision':'two','assets':['../config.json']}))
        self.assertEqual(self.updates.snapshot(True)['ui']['state'],'building')
        (self.dist/'ui-build.json').unlink()
        self.assertEqual(self.updates.snapshot(True)['ui']['state'],'not-built')

    def test_source_reverted_does_not_require_restart(self):
        (self.root/'backend/main.py').write_text('temporary edit')
        self.assertEqual(self.updates.snapshot(True)['backend']['state'],'restart-required')
        (self.root/'backend/main.py').write_text('backend v1')
        self.assertEqual(self.updates.snapshot(True)['backend']['state'],'current')

    def test_frontend_classification_does_not_request_install_for_current_running_plugin(self):
        subprocess.run(['node','tests/test_update_presentation.mjs'],cwd=Path(__file__).resolve().parents[1],capture_output=True,check=True,timeout=10)
