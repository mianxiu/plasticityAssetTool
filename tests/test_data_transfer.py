import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from backend.asset_library import AssetLibrary
from backend.data_transfer import DataTransfer
from model_fixture import model_bytes
from test_group_recipe import recipe


class DataTransferTests(unittest.TestCase):
    def test_batch_import_and_backup_restore_keep_native_calibration(self):
        from test_native_layout import report
        from model_fixture import count_first_model_bytes
        source=AssetLibrary(Path(self.temp.name)/'calibrated')
        source.register_native_format('25.2.5',report())
        asset=source.add(count_first_model_bytes(),{'name':'legacy'},source_version='25.2.5')
        source.update(asset['id'],{'name':'legacy','base_point':[10,20,30],'model_digest':asset['digest']})
        plan=self.transfer.preview([('legacy.patasset',source.export(asset['id']))])
        self.transfer.commit(plan['token'],[{'mode':'copy'}])
        imported=self.library.list()[0]
        self.assertEqual(self.library.base_point(imported['id'])['base_point'],[10,20,30])
        with self.transfer.backup() as output:
            payload=output.read()
        plan=self.transfer.preview([('backup.zip',payload)],kind='restore')
        self.transfer.commit(plan['token'],confirm_restore=True)
        self.assertEqual(self.library.base_point(imported['id'])['base_point'],[10,20,30])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.library=AssetLibrary(Path(self.temp.name)/'library')
        self.transfer=DataTransfer(self.library)

    def tearDown(self):
        for token in list(self.transfer.plans):
            self.transfer.discard(token)
        self.temp.cleanup()

    def package(self, name='A', model=b'original'):
        row=self.library.add(model,{'name':name})
        return self.library.export(row['id']),row

    def test_preview_has_no_writes_and_skip_copy_overwrite_preserve_native_bytes(self):
        package,old=self.package()
        result=self.transfer.preview([('A.patasset',package)])
        self.assertEqual(len(self.library.list()),1)
        self.assertEqual(result['items'][0]['conflict'],'identical')
        self.transfer.commit(result['token'],[{'mode':'skip'}])
        result=self.transfer.preview([('A.patasset',package)])
        self.transfer.commit(result['token'],[{'mode':'copy'}])
        self.assertEqual({row['name'] for row in self.library.list()},{'A','A (2)'})
        other=AssetLibrary(Path(self.temp.name)/'other')
        incoming=other.add(b'new-model',{'name':'A','tags':'new tags'},b'\xff\xd8new')
        result=self.transfer.preview([('A.patasset',other.export(incoming['id']))])
        self.transfer.commit(result['token'],[{'mode':'overwrite','target_id':old['id']}])
        restored=self.library.get(old['id'])
        self.assertEqual(restored['model'],b'new-model')
        self.assertEqual(restored['preview'],b'\xff\xd8new')
        self.assertEqual(restored['tags'],'new tags')

    def test_bad_file_rejects_whole_batch_and_stale_preview_cannot_write(self):
        package,_=self.package()
        with self.assertRaises(ValueError):
            self.transfer.preview([('ok.patasset',package),('bad.patasset',b'bad')])
        self.assertEqual(len(self.library.list()),1)
        self.assertEqual(self.transfer.plans,{})
        result=self.transfer.preview([('ok.patasset',package)])
        self.library.add(b'another',{'name':'B'})
        with self.assertRaisesRegex(ValueError,'已变化'):
            self.transfer.commit(result['token'],[{'mode':'copy'}])
        self.assertEqual(len(self.library.list()),2)

    def test_multiple_zips_and_packages_and_duplicate_detection(self):
        first,a=self.package('A',b'A')
        second,b=self.package('B',b'B')
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as bundle:
            bundle.writestr('folder/A.patasset',first)
            bundle.writestr('folder/B.patasset',second)
        result=self.transfer.preview([('components.zip',archive.getvalue()),('A.patasset',first)])
        self.assertEqual(result['count'],3)
        self.assertTrue(result['items'][2]['duplicate'])
        self.transfer.commit(result['token'],[{'mode':'copy'},{'mode':'skip'},{'mode':'skip'}])
        self.assertEqual(len(self.library.list()),3)

    def test_backup_restore_round_trip_preserves_ids_organization_archives_and_recipes(self):
        custom=self.library.create_library('Custom')
        parent=self.library.create_folder(custom['id'],None,'Parent')
        child=self.library.create_folder(custom['id'],parent['id'],'Child')
        native=model_bytes('group',count=2)
        asset=self.library.add(native,{'name':'Group','library_id':custom['id'],'folder_id':child['id'],'kind':'solid','recipe':recipe()},b'\xff\xd8preview')
        self.library.archive(asset['id'],True)
        original=dict(self.library.get(asset['id']))
        with self.transfer.backup() as output:
            payload=output.read()
        extra=self.library.add(b'extra',{'name':'Extra'})
        result=self.transfer.preview([('backup.zip',payload)],kind='restore')
        self.assertEqual(result['folders'],2)
        self.assertEqual(len(self.library.list()),1,'Restore preview must not modify current data')
        with self.assertRaisesRegex(ValueError,'确认'):
            self.transfer.commit(result['token'])
        completed=self.transfer.commit(result['token'],confirm_restore=True)
        self.assertEqual(dict(self.library.get(asset['id'])),original)
        self.assertEqual(self.library.list(),[])
        self.assertEqual(self.library.folders(custom['id'])[0]['library_id'],custom['id'])
        rollback=Path(completed['rollback_backup'])
        self.assertTrue(rollback.is_file())
        reverted=self.transfer.preview([('rollback.zip',rollback.read_bytes())],kind='restore')
        self.transfer.commit(reverted['token'],confirm_restore=True)
        self.assertEqual(self.library.get(extra['id'])['model'],b'extra')

    def test_invalid_later_choice_rolls_back_earlier_insert(self):
        package,_=self.package()
        result=self.transfer.preview([('A.patasset',package),('A.patasset',package)])
        with self.assertRaises(ValueError):
            self.transfer.commit(result['token'],[{'mode':'copy'},{'mode':'overwrite','target_id':'missing'}])
        self.assertEqual(len(self.library.list()),1)

    def test_restore_rejects_wrong_bundle_and_corrupt_backup(self):
        package,_=self.package()
        with self.assertRaises(ValueError):
            self.transfer.preview([('backup.zip',package)],kind='restore')
        with self.transfer.backup() as output:
            payload=output.read()
        bad=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(payload)) as source,zipfile.ZipFile(bad,'w') as target:
            for name in source.namelist():
                content=source.read(name)
                if name.endswith('.patasset'):
                    content=b'corrupted'
                target.writestr(name,content)
        with self.assertRaises(ValueError):
            self.transfer.preview([('bad.zip',bad.getvalue())],kind='restore')
        self.assertEqual(len(self.library.list()),1)


if __name__=='__main__':
    unittest.main()
