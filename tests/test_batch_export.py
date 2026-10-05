import io
import json
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from backend.asset_library import AssetLibrary
from tornado.testing import AsyncHTTPTestCase
from test_service_control import make_application
from test_group_recipe import recipe
from model_fixture import model_bytes


class BatchExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.library = AssetLibrary(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_bundle_contains_individually_importable_packages_with_safe_unique_names(self):
        first = self.library.add(b'first-model', {'name':'../同名/组件','category':'分类','tags':'tag','insert_mode':'union'}, b'\xff\xd8preview')
        second = self.library.add(b'second-model', {'name':'../同名/组件','category':'分类','note':'note'})
        output,count = self.library.export_batch([first['id'],second['id'],first['id']])
        try:
            self.assertEqual(count,2)
            with zipfile.ZipFile(output) as bundle:
                names = bundle.namelist()
                self.assertEqual(len(names),2)
                for name in names:
                    self.assertTrue(name.endswith('.patasset'))
                    self.assertNotIn('/',name)
                    self.assertFalse(name.startswith('.'))
                copied = [self.library.import_package(bundle.read(name)) for name in names]
            self.assertEqual([self.library.get(row['id'])['model'] for row in copied], [b'first-model',b'second-model'])
            self.assertEqual(copied[0]['insert_mode'],'union')
            self.assertEqual(copied[0]['category'],'分类')
            self.assertEqual(copied[0]['tags'],'tag')
            self.assertEqual(copied[1]['note'],'note')
            self.assertEqual(self.library.get(copied[0]['id'])['preview'],b'\xff\xd8preview')
        finally:
            output.close()

    def test_invalid_or_missing_selection_creates_no_partial_bundle(self):
        first = self.library.add(b'model',{'name':'A'})
        for ids in (None, [], 'invalid', [None], ['../path'], [first['id'],'0'*32]):
            with patch.object(self.library,'export') as export:
                with self.assertRaises(ValueError):
                    self.library.export_batch(ids)
                export.assert_not_called()

    def test_sequence_recipe_and_part_order_survive_bundle_round_trip(self):
        model = model_bytes('group', count=2)
        saved = self.library.add(model, {'name':'Group','recipe':recipe(),'kind':'solid'})
        output,count = self.library.export_batch([saved['id']])
        try:
            with zipfile.ZipFile(output) as bundle:
                copied = self.library.import_package(bundle.read(bundle.namelist()[0]))
            self.assertEqual(copied['recipe'],recipe())
            self.assertEqual(self.library.get(copied['id'])['model'],model)
        finally:
            output.close()

    def test_large_export_spills_to_disk(self):
        first = self.library.add(b'model',{'name':'A'})
        with patch.object(self.library,'export',return_value=b'x'*(9*1024*1024)):
            output,count = self.library.export_batch([first['id']])
        try:
            self.assertTrue(output._rolled)
            with zipfile.ZipFile(output) as bundle:
                self.assertEqual(bundle.infolist()[0].file_size,9*1024*1024)
        finally:
            output.close()


class BatchExportHttpTests(AsyncHTTPTestCase):
    def get_app(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = make_application(self.temp.name)
        self.asset = self.app.service.library.add(b'model',{'name':'A'})
        return self.app

    def tearDown(self):
        for token in list(self.app.batch_exports):
            self.app.discard_export(token)
        super().tearDown()
        self.temp.cleanup()

    def prepare(self, ids, headers=None):
        return self.fetch('/api/export',method='POST',body=json.dumps({'ids':ids}),headers=headers or {'Content-Type':'application/json'})

    def test_prepare_download_stream_and_release(self):
        response = self.prepare([self.asset['id']])
        self.assertEqual(response.code,200)
        metadata = json.loads(response.body)
        self.assertEqual(metadata['count'],1)
        output = next(iter(self.app.batch_exports.values()))
        archive = self.fetch(metadata['download_url'])
        self.assertEqual(archive.code,200)
        self.assertIn('attachment',archive.headers['Content-Disposition'])
        with zipfile.ZipFile(io.BytesIO(archive.body)) as bundle:
            self.assertEqual(len(bundle.namelist()),1)
        self.assertTrue(output.closed)
        self.assertEqual(self.app.batch_exports,{})
        self.assertEqual(self.fetch(metadata['download_url']).code,404)

    def test_invalid_and_cross_origin_requests_are_rejected(self):
        self.assertEqual(self.prepare([]).code,400)
        self.assertEqual(self.prepare([self.asset['id']],{'Origin':'https://example.com','Content-Type':'application/json'}).code,403)
        self.assertEqual(self.app.batch_exports,{})

    def test_expired_export_releases_file(self):
        metadata = json.loads(self.prepare([self.asset['id']]).body)
        token = metadata['download_url'].split('/')[-1].removesuffix('.zip')
        output = self.app.batch_exports[token]
        self.app.discard_export(token)
        self.assertTrue(output.closed)
        self.assertEqual(self.fetch(metadata['download_url']).code,404)
