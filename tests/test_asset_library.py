import hashlib
import io
import json
import tempfile
import tracemalloc
import unittest
import zipfile
from backend.asset_library import AssetLibrary


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.library = AssetLibrary(self.directory.name)
        self.model = bytes(range(256)) * 80 + b"\x00\xff\x00"

    def tearDown(self):
        self.directory.cleanup()

    def test_persistence_and_package_round_trip_preserve_every_byte(self):
        asset = self.library.add(self.model, {"name": "螺栓", "category": "紧固件", "tags": "M8"}, source_version="26.1.3")
        loaded = AssetLibrary(self.directory.name)
        self.assertEqual(loaded.get(asset["id"])["model"], self.model)
        imported = loaded.import_package(self.library.export(asset["id"]))
        self.assertNotEqual(imported["id"], asset["id"])
        self.assertEqual(loaded.get(imported["id"])["model"], self.model)
        self.assertEqual(imported["source_version"], "26.1.3")
        self.assertEqual(imported["name"], "螺栓")

    def test_edit_and_archive_do_not_change_geometry(self):
        asset = self.library.add(self.model, {"name": "原名称"})
        changed = self.library.update(asset["id"], {"name": "新名称", "note": "备注"})
        self.assertEqual(changed["digest"], hashlib.sha256(self.model).hexdigest())
        self.library.archive(asset["id"], True)
        self.assertEqual(self.library.list(), [])
        self.assertEqual(len(self.library.list(True)), 1)
        self.library.archive(asset["id"], False)
        self.assertEqual(self.library.get(asset["id"])["model"], self.model)

    def test_default_insert_mode_persists_and_round_trips(self):
        asset = self.library.add(self.model, {"name":"cutter","insert_mode":"difference"})
        self.assertEqual(AssetLibrary(self.directory.name).details(asset["id"])["insert_mode"], "difference")
        imported = self.library.import_package(self.library.export(asset["id"]))
        self.assertEqual(imported["insert_mode"], "difference")
        self.assertEqual(self.library.update(asset["id"], {"note":"changed"})["insert_mode"], "difference")
        for mode in ("new-body", "union", "intersection"):
            self.assertEqual(self.library.update(asset["id"], {"insert_mode":mode})["insert_mode"], mode)
        with self.assertRaisesRegex(ValueError, "默认置入模式"):
            self.library.update(asset["id"], {"insert_mode":"invalid"})
        self.assertEqual(self.library.get(asset["id"])["model"], self.model)

    def test_corrupt_package_rejected_without_partial_import(self):
        asset = self.library.add(self.model, {"name": "测试"})
        original = zipfile.ZipFile(io.BytesIO(self.library.export(asset["id"])))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as package:
            package.writestr("manifest.json", original.read("manifest.json"))
            package.writestr("model.bin", b"corrupt")
        original.close()
        with self.assertRaisesRegex(ValueError, "校验失败"):
            self.library.import_package(output.getvalue())
        self.assertEqual(len(self.library.list()), 1)

    def test_untrusted_package_paths_and_duplicates_rejected(self):
        for filename in ("../model.bin", "extra.txt"):
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as package:
                package.writestr(filename, b"test")
            with self.assertRaises(ValueError):
                self.library.import_package(output.getvalue())
        self.assertEqual(self.library.list(), [])

    def test_empty_model_and_name_rejected(self):
        for model, fields in [(b"", {"name": "test"}), (b"a", {"name": "  "})]:
            with self.assertRaises(ValueError):
                self.library.add(model, fields)

    def test_preview_replace_remove_and_package_preserve_geometry(self):
        first, second = b"\xff\xd8first-jpeg", b"\xff\xd8second-jpeg"
        asset = self.library.add(self.model, {"name": "test"}, first)
        unchanged = self.library.update(asset["id"], {"note": "metadata only"})
        self.assertTrue(unchanged["has_preview"])
        self.assertEqual(self.library.get(asset["id"])["preview"], first)
        changed = self.library.update(asset["id"], {"preview": second})
        self.assertNotEqual(asset["updated_at"], changed["updated_at"])
        imported = self.library.import_package(self.library.export(asset["id"]))
        self.assertEqual(self.library.get(imported["id"])["preview"], second)
        self.library.update(asset["id"], {"preview": None})
        row = self.library.get(asset["id"])
        self.assertIsNone(row["preview"])
        self.assertEqual(row["model"], self.model)

    def test_invalid_preview_update_is_atomic(self):
        asset = self.library.add(self.model, {"name": "before"})
        with self.assertRaises(ValueError):
            self.library.update(asset["id"], {"name": "after", "preview": b"not-jpeg"})
        self.assertEqual(self.library.details(asset["id"])["name"], "before")

    def test_large_models_do_not_get_loaded_when_listing_metadata(self):
        size = 8 * 1024 * 1024
        self.library.add(b"x" * size, {"name": "large"}, b"\xff\xd8" + b"y" * (1024 * 1024))
        tracemalloc.start()
        try:
            rows = self.library.list()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(rows[0]["bytes"], size)
        self.assertTrue(rows[0]["has_preview"])
        self.assertLess(peak, 1024 * 1024)

if __name__ == "__main__":
    unittest.main()
