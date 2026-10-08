import base64
import copy
import hashlib
import json
import math
import tempfile
import unittest
import zipfile
from pathlib import Path
from backend.model_samples import ModelSamples, validate_samples, MAX_SAMPLE_BYTES
from backend.native_layout import POINTS
from test_native_layout import report


def sample_report(unknown=False):
    value = report()
    if unknown:
        value['format'] = 'unknown'
        value['layout'] = None
    value['test_inputs'] = {'points':POINTS,'orientation_kind':'direction','orientations':[[v/math.sqrt(14) for v in row] for row in [[1,2,3],[-2,3,1]]]}
    for probe in value['probes']:
        data = base64.b64decode(probe['header']) + b'UNSUPPORTED-FUTURE-GEOMETRY'
        probe.update(model=base64.b64encode(data).decode(),bytes=len(data),model_sha256=hashlib.sha256(data).hexdigest())
    return value


class ModelSampleTests(unittest.TestCase):
    def test_unknown_samples_are_archived_with_reproducible_inputs_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ModelSamples(directory)
            value=sample_report(True)
            first=store.save('29.0.1',value,['encoding-samples-v1'])
            second=store.save('29.0.1',value,['encoding-samples-v1'])
            self.assertNotEqual(first['id'],second['id'])
            self.assertFalse(first['verified'])
            with zipfile.ZipFile(store.path(first['id'])) as bundle:
                manifest=json.loads(bundle.read('manifest.json'))
                diagnostic=json.loads(bundle.read('report.json'))
                self.assertEqual(manifest['source_version'],'29.0.1')
                self.assertEqual(diagnostic['test_inputs'],value['test_inputs'])
                self.assertIsNone(diagnostic['layout'])
                self.assertNotIn('model',diagnostic['probes'][0])
                for sample in manifest['samples']:
                    data=bundle.read(sample['file'])
                    self.assertEqual(sample['sha256'],hashlib.sha256(data).hexdigest())
            self.assertFalse((Path(directory)/'library').exists())

    def test_corrupt_mismatched_or_oversized_samples_never_create_archive(self):
        for field,value in [('model','%%%'),('model_sha256','a'*64),('bytes',1),('header',base64.b64encode(b'wrong-header'*8).decode()),('model','A'*(((MAX_SAMPLE_BYTES+2)//3)*4+4))]:
            broken=sample_report(True);broken['probes'][0][field]=value
            with tempfile.TemporaryDirectory() as directory:
                store=ModelSamples(directory)
                with self.assertRaises(ValueError):store.save('unknown',broken,[])
                self.assertFalse(store.directory.exists())
        broken=sample_report();broken['test_inputs']['points']=[[0,0,0],[0,0,0]]
        with self.assertRaises(ValueError):validate_samples(broken)

    def test_identifier_collision_does_not_delete_existing_collection(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            store=ModelSamples(directory)
            with patch('backend.model_samples.uuid.uuid4',return_value=SimpleNamespace(hex='a'*32)):
                first=store.save('26.1.3',sample_report(),[])
                before=store.path(first['id']).read_bytes()
                with self.assertRaises(FileExistsError):store.save('29.0.1',sample_report(True),[])
                self.assertEqual(store.path(first['id']).read_bytes(),before)

    def test_path_cannot_escape_archive_directory(self):
        store=ModelSamples('.')
        for invalid in ['../sample',None,'A'*32,'a'*31]:
            with self.assertRaises(ValueError):store.path(invalid)
