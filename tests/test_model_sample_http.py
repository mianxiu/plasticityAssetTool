import io
import json
import tempfile
import zipfile
from tornado.testing import AsyncHTTPTestCase
from backend.main import Application, DEFAULT_SHORTCUTS
from backend.asset_service import AssetService
from test_asset_service import FakeDesktop
from test_model_samples import sample_report


class ModelSampleHttpTests(AsyncHTTPTestCase):
    def get_app(self):
        self.temp=tempfile.TemporaryDirectory()
        config={'server':{'http_port':15150},'plasticity':{'cdp_endpoints':[]},'keymap':{'desktop_shortcuts':DEFAULT_SHORTCUTS}}
        service=AssetService(config,self.temp.name,desktop=FakeDesktop())
        self.saved=service.model_samples.save('29.0.1',sample_report(True),[])
        return Application(config,service)

    def tearDown(self):
        super().tearDown()
        self.temp.cleanup()

    def test_download_saved_sample_and_reject_missing_and_foreign_origin(self):
        result=self.fetch(self.saved['download_url'])
        self.assertEqual(result.code,200)
        self.assertEqual(result.headers['Content-Type'],'application/zip')
        self.assertIn('attachment',result.headers['Content-Disposition'])
        with zipfile.ZipFile(io.BytesIO(result.body)) as bundle:
            self.assertEqual(json.loads(bundle.read('manifest.json'))['source_version'],'29.0.1')
        self.assertEqual(self.fetch('/api/model-samples/'+'0'*32+'.zip').code,404)
        self.assertEqual(self.fetch(self.saved['download_url'],headers={'Origin':'https://example.com'}).code,403)
