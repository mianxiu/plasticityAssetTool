import base64
import copy
import math
import struct
import tempfile
import unittest
from pathlib import Path
from backend.native_layout import POINTS, validate_probe
from backend.asset_library import AssetLibrary
from backend.model_clipboard import model_base_point, with_base_point
from model_fixture import count_first_model_bytes


def report():
    headers = []
    for point, direction in zip(POINTS, [[1,2,3],[-2,3,1]]):
        h = bytearray(60)
        struct.pack_into('<I',h,0,1)
        struct.pack_into('<3d',h,8,*point)
        struct.pack_into('<3d',h,32,*(v/math.sqrt(14) for v in direction))
        headers.append({'header':base64.b64encode(h).decode(),'content_digest':'a'*64})
    return {'format':'count-first','layout':{'point':8,'orientation':32,'orientation_kind':'direction'},'probes':headers}


class NativeLayoutTests(unittest.TestCase):
    def test_two_probe_values_bounds_overlap_and_count_protected(self):
        self.assertEqual(validate_probe(report()),report())
        for key, value in [('point',0),('point',4),('point',40),('orientation',24),('orientation',500),('orientation_kind','matrix')]:
            broken=copy.deepcopy(report());broken['layout'][key]=value
            with self.assertRaises(ValueError):validate_probe(broken)
        broken=report();broken['probes'][1]=broken['probes'][0]
        with self.assertRaisesRegex(ValueError,'不匹配'):validate_probe(broken)
        broken=report();broken['probes'][1]['content_digest']='b'*64
        with self.assertRaisesRegex(ValueError,'几何或元数据'):validate_probe(broken)

    def test_uncalibrated_model_never_guesses_coordinate_offsets(self):
        model=count_first_model_bytes()
        with self.assertRaisesRegex(ValueError,'自动检测'):model_base_point(model)
        with self.assertRaisesRegex(ValueError,'自动检测'):with_base_point(model,[1,2,3])

    def test_calibration_edit_restart_and_package_round_trip_preserve_model(self):
        with tempfile.TemporaryDirectory() as root:
            library=AssetLibrary(Path(root)/'first')
            model=count_first_model_bytes(count=2)
            asset=library.add(model,{'name':'legacy'},source_version='25.2.5')
            self.assertTrue(library.base_point(asset['id'])['requires_native_detection'])
            library.register_native_format('25.2.5',report())
            # Registration maps two existing bodies, not just the probe's one body.
            self.assertEqual(library.base_point(asset['id'])['base_point'],[0,0,0])
            updated=library.update(asset['id'],{'name':'legacy','base_point':[10,20,30],'model_digest':asset['digest']})
            changed=bytes(library.get(asset['id'])['model'])
            self.assertEqual(changed[:8],model[:8]);self.assertEqual(changed[32:],model[32:])
            self.assertEqual(library.base_point(asset['id'])['base_point'],[10,20,30])
            self.assertFalse(library.base_point(asset['id'])['orientation_editable'])
            with self.assertRaisesRegex(ValueError,'原生方向'):
                library.update(asset['id'],{'name':'legacy','base_point':[1,2,3],'base_orientation':[0,0,0,1],'model_digest':updated['digest']})
            self.assertEqual(bytes(library.get(asset['id'])['model']),changed)
            library=AssetLibrary(Path(root)/'first')
            other=AssetLibrary(Path(root)/'other')
            imported=other.import_package(library.export(asset['id']))
            self.assertEqual(other.base_point(imported['id'])['base_point'],[10,20,30])
            self.assertEqual(bytes(other.get(imported['id'])['model']),changed)
