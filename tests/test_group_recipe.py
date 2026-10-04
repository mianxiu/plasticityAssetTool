import copy
import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from asset_library import AssetLibrary
from group_recipe import validate_recipe
from model_fixture import model_bytes


def recipe():
    return {"version": 1, "name": "螺栓孔", "parts": [
        {"index": 0, "name": "+ 外壳", "mode": "union"},
        {"index": 1, "name": "- 内孔", "mode": "difference"}]}


class GroupRecipeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_native_group_execution(self):
        root=Path(__file__).resolve().parent.parent
        subprocess.run(['node',str(root/'tests/test_group_recipe.js')],cwd=root,check=True,capture_output=True,timeout=10)

    def test_round_trip_and_edit_preserve_order_and_original_model(self):
        with tempfile.TemporaryDirectory() as root:
            library=AssetLibrary(root)
            model=model_bytes("same-name", count=2)
            saved=library.add(model, {"name":"复合组件", "recipe":recipe()})
            self.assertEqual(saved['recipe'],recipe())
            library.update(saved['id'], {'name':'重命名'})
            imported=library.import_package(library.export(saved['id']))
            self.assertEqual(imported['recipe'],recipe())
            self.assertEqual(bytes(library.get(imported['id'])['model']),model)
            self.assertEqual(library.list()[0]['recipe'],recipe())

    def test_rejects_wrong_count_order_and_prefix(self):
        with self.assertRaisesRegex(ValueError,'数量'):
            validate_recipe(recipe(),model_bytes())
        for key,value in [('index',True),('index',0),('mode','union'),('name','x'*121)]:
            invalid=copy.deepcopy(recipe());invalid['parts'][1][key]=value
            with self.assertRaises(ValueError): validate_recipe(invalid)

    def test_all_prefixes_and_unmarked_independent(self):
        names=['+ 合并','- 减去','& 相交','^ 保留','保留']
        modes=['union','difference','intersection','new-body','new-body']
        data={'version':1,'name':'组','parts':[{'index':i,'name':n,'mode':m} for i,(n,m) in enumerate(zip(names,modes))]}
        self.assertEqual(validate_recipe(data)['parts'],data['parts'])

    def test_legacy_asset_has_no_recipe(self):
        with tempfile.TemporaryDirectory() as root:
            library=AssetLibrary(root)
            self.assertIsNone(library.add(model_bytes(),{'name':'旧组件'})['recipe'])
