import sqlite3
import tempfile
import unittest
from backend.asset_library import AssetLibrary
from backend.library_launcher import parse_hotkey, LibraryLauncher


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.library = AssetLibrary(self.directory.name)
        self.second = self.library.create_library("机械件")
        self.model = b"native\0geometry\xff"

    def tearDown(self):
        self.directory.cleanup()

    def test_libraries_isolate_components_and_archive_counts(self):
        a = self.library.add(self.model, {"name": "A"})
        b = self.library.add(self.model, {"name": "B", "library_id": self.second["id"]})
        self.assertEqual([row["id"] for row in self.library.list()], [a["id"]])
        self.assertEqual([row["id"] for row in self.library.list(False, self.second["id"])], [b["id"]])
        self.library.archive(b["id"], True)
        self.assertEqual(self.library.list(False, self.second["id"]), [])
        self.assertEqual(self.library.libraries()[1]["count"], 0)
        self.assertEqual(self.library.list(True, self.second["id"])[0]["id"], b["id"])

    def test_nested_folders_and_names_persist_after_reopening(self):
        root = self.library.create_folder(self.second["id"], None, "紧固件")
        child = self.library.create_folder(self.second["id"], root["id"], "螺栓")
        self.library.rename_folder(self.second["id"], child["id"], "六角螺栓")
        self.library.rename_library(self.second["id"], "标准件")
        reopened = AssetLibrary(self.directory.name)
        folders = reopened.folders(self.second["id"])
        self.assertEqual(next(row for row in folders if row["id"] == child["id"])["parent_id"], root["id"])
        self.assertEqual(reopened.require_library(self.second["id"])["name"], "标准件")

    def test_move_to_another_library_clears_old_folder_and_preserves_geometry(self):
        folder = self.library.create_folder("default", None, "来源")
        asset = self.library.add(self.model, {"name": "A", "folder_id": folder["id"], "kind": "curve"})
        moved = self.library.update(asset["id"], {"library_id": self.second["id"]})
        self.assertIsNone(moved["folder_id"])
        self.assertEqual(moved["kind"], "curve")
        self.assertEqual(self.library.get(asset["id"])["model"], self.model)
        self.assertEqual(self.library.list(), [])

    def test_cross_library_folder_assignment_rejected_atomically(self):
        folder = self.library.create_folder(self.second["id"], None, "目的")
        asset = self.library.add(self.model, {"name": "before"})
        with self.assertRaises(ValueError):
            self.library.update(asset["id"], {"name": "after", "folder_id": folder["id"]})
        self.assertEqual(self.library.details(asset["id"])["name"], "before")
        with self.assertRaises(ValueError):
            self.library.create_folder("default", folder["id"], "错误子组")

    def test_package_import_uses_destination_instead_of_exported_database_ids(self):
        folder = self.library.create_folder(self.second["id"], None, "导入")
        asset = self.library.add(self.model, {"name": "A", "kind": "solid"})
        imported = self.library.import_package(self.library.export(asset["id"]), self.second["id"], folder["id"])
        self.assertEqual((imported["library_id"], imported["folder_id"], imported["kind"]), (self.second["id"], folder["id"], "solid"))
        self.assertEqual(self.library.get(imported["id"])["model"], self.model)

    def test_legacy_database_migrates_without_changing_bytes(self):
        with self.library.connect() as db:
            db.execute("INSERT INTO assets (id,name,category,tags,note,created_at,source_version,digest,model) VALUES ('legacy','old','未分类','','','2024','unknown','digest',?)", (self.model,))
            db.execute("DROP INDEX assets_library_archive")
            # A pre-index legacy database has neither this projection nor triggers.
            for event in ("insert", "update", "delete"):
                db.execute(f"DROP TRIGGER asset_metadata_{event}")
            db.execute("DROP TABLE asset_metadata")
            for column in ("library_id", "folder_id", "kind", "updated_at"):
                db.execute(f"ALTER TABLE assets DROP COLUMN {column}")
        migrated = AssetLibrary(self.directory.name)
        old = migrated.details("legacy")
        self.assertEqual((old["library_id"], old["folder_id"], old["kind"], old["updated_at"]), ("default", None, "unknown", "2024"))
        self.assertEqual(migrated.get("legacy")["model"], self.model)


class LauncherTests(unittest.TestCase):
    def test_hotkey_uses_no_repeat_and_supports_configured_modifiers(self):
        self.assertEqual(parse_hotkey("ctrl+alt+space"), (0x4003, 0x20))
        self.assertEqual(parse_hotkey("ctrl+shift+f8"), (0x4006, 0x77))
        self.assertEqual(parse_hotkey("tab"), (0x4000, 9))
        self.assertEqual(parse_hotkey("ctrl+tab"), (0x4002, 9))
        self.assertEqual(parse_hotkey("f8"), (0x4000, 0x77))
        for chord in ("capslock", "ctrl+ctrl+a", "ctrl+unknown", "win+space", None):
            with self.assertRaises(ValueError):
                parse_hotkey(chord)

    def test_disabled_launcher_does_not_register_or_launch(self):
        launcher = LibraryLauncher({"enabled": False}, object(), "http://127.0.0.1:15150", lambda _: self.fail("unexpected launch"))
        launcher.start()
        self.assertIsNone(launcher.thread)
        self.assertFalse(launcher.status["registered"])
