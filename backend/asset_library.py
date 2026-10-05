"""Local component storage. Model bytes are kept exactly as Plasticity copied them."""
import hashlib
import io
import json
import sqlite3
import uuid
import zipfile
from .group_recipe import validate_recipe
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MAX_MODEL_BYTES = 64 * 1024 * 1024
MAX_PREVIEW_BYTES = 5 * 1024 * 1024
METADATA_COLUMNS = """id,name,category,tags,note,created_at,updated_at,
    source_version,digest,archived,library_id,folder_id,kind,insert_mode,recipe_json,length(model) AS bytes,
    (preview IS NOT NULL AND length(preview)>0) AS has_preview,
    EXISTS(SELECT 1 FROM geometry_cache g WHERE g.digest=assets.digest) AS has_geometry,
    EXISTS(SELECT 1 FROM geometry_cache g WHERE g.digest=assets.digest AND g.thumbnail IS NOT NULL) AS has_geometry_preview"""


class AssetLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "library.sqlite3"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                tags TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL,
                source_version TEXT NOT NULL, digest TEXT NOT NULL,
                model BLOB NOT NULL, preview BLOB, archived INTEGER NOT NULL DEFAULT 0
            )""")
            if "updated_at" not in {row["name"] for row in db.execute("PRAGMA table_info(assets)")}:
                db.execute("ALTER TABLE assets ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
                db.execute("UPDATE assets SET updated_at=created_at")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(assets)")}
            for name, declaration in [("library_id", "TEXT NOT NULL DEFAULT 'default'"), ("folder_id", "TEXT"), ("kind", "TEXT NOT NULL DEFAULT 'unknown'"), ("insert_mode", "TEXT NOT NULL DEFAULT 'new-body'"), ("recipe_json", "TEXT NOT NULL DEFAULT 'null'")]:
                if name not in columns:
                    db.execute(f"ALTER TABLE assets ADD COLUMN {name} {declaration}")
            db.execute("CREATE TABLE IF NOT EXISTS libraries (id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS folders (id TEXT PRIMARY KEY,library_id TEXT NOT NULL,parent_id TEXT,name TEXT NOT NULL,created_at TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO libraries VALUES ('default','默认库',?)", (datetime.now(timezone.utc).isoformat(),))
            db.execute("CREATE INDEX IF NOT EXISTS assets_library_archive ON assets(library_id,archived)")
            db.execute("CREATE TABLE IF NOT EXISTS geometry_cache (digest TEXT PRIMARY KEY,mesh BLOB NOT NULL,thumbnail BLOB)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def metadata(row):
        return {key: row[key] for key in (
            "id", "name", "category", "tags", "note", "created_at", "updated_at", "source_version", "digest", "archived", "library_id", "folder_id", "kind", "insert_mode"
        )} | {"recipe": json.loads(row["recipe_json"]), "bytes": row["bytes"] if "bytes" in row.keys() else len(row["model"]),
              "has_preview": bool(row["has_preview"] if "has_preview" in row.keys() else row["preview"]),
              "has_geometry": bool(row["has_geometry"]) if "has_geometry" in row.keys() else False,
              "has_geometry_preview": bool(row["has_geometry_preview"]) if "has_geometry_preview" in row.keys() else False}

    def list(self, archived=False, library_id="default"):
        self.require_library(library_id)
        with self.connect() as db:
            return [self.metadata(row) for row in db.execute(
                f"SELECT {METADATA_COLUMNS} FROM assets WHERE archived=? AND library_id=? ORDER BY created_at DESC", (int(archived), library_id)
            )]

    def require_library(self, library_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM libraries WHERE id=?", (library_id,)).fetchone()
        if row is None:
            raise ValueError("资产库不存在，请刷新")
        return dict(row)

    def libraries(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT l.*, (SELECT count(*) FROM assets a WHERE a.library_id=l.id AND a.archived=0) AS count FROM libraries l ORDER BY created_at,id")]

    def create_library(self, name):
        name = self.validate_fields({"name": name})["name"]
        row = {"id": uuid.uuid4().hex, "name": name, "created_at": datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute("INSERT INTO libraries VALUES (:id,:name,:created_at)", row)
        return row

    def rename_library(self, library_id, name):
        self.require_library(library_id)
        name = self.validate_fields({"name": name})["name"]
        with self.connect() as db:
            db.execute("UPDATE libraries SET name=? WHERE id=?", (name, library_id))
        return self.require_library(library_id)

    def folders(self, library_id="default"):
        self.require_library(library_id)
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM folders WHERE library_id=? ORDER BY name,id", (library_id,))]

    def validate_location(self, library_id, folder_id):
        self.require_library(library_id)
        if folder_id is not None:
            with self.connect() as db:
                row = db.execute("SELECT library_id FROM folders WHERE id=?", (folder_id,)).fetchone()
            if row is None or row["library_id"] != library_id:
                raise ValueError("分组不属于当前资产库")

    def create_folder(self, library_id, parent_id, name):
        self.validate_location(library_id, parent_id)
        name = self.validate_fields({"name": name})["name"]
        row = {"id": uuid.uuid4().hex, "library_id": library_id, "parent_id": parent_id, "name": name, "created_at": datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute("INSERT INTO folders VALUES (:id,:library_id,:parent_id,:name,:created_at)", row)
        return row

    def rename_folder(self, library_id, folder_id, name):
        if folder_id is None:
            raise ValueError("请选择分组")
        self.validate_location(library_id, folder_id)
        name = self.validate_fields({"name": name})["name"]
        with self.connect() as db:
            db.execute("UPDATE folders SET name=? WHERE id=?", (name, folder_id))
        return {"id": folder_id, "name": name}

    def organization(self, fields, current=None):
        current = current or {"library_id": "default", "folder_id": None, "kind": "unknown"}
        library_id = fields.get("library_id", current["library_id"])
        folder_id = fields.get("folder_id", current["folder_id"] if library_id == current["library_id"] else None)
        kind = fields.get("kind", current["kind"])
        if kind not in ("solid", "curve", "mixed", "unknown"):
            raise ValueError("不支持的组件类型")
        self.validate_location(library_id, folder_id)
        return library_id, folder_id, kind

    def details(self, asset_id):
        with self.connect() as db:
            row = db.execute(f"SELECT {METADATA_COLUMNS} FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError("组件不存在，请刷新组件库")
        return self.metadata(row)

    @staticmethod
    def validate_preview(preview):
        if preview is not None and (not isinstance(preview, bytes) or not 2 <= len(preview) <= MAX_PREVIEW_BYTES or not preview.startswith(b"\xff\xd8")):
            raise ValueError("预览必须是小于 5 MB 的 JPEG")
        return preview

    def get(self, asset_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError("组件不存在，请刷新组件库")
        return row

    def model_row(self, asset_id):
        with self.connect() as db:
            row = db.execute("SELECT id,digest,model,archived,insert_mode,recipe_json FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError("组件不存在，请刷新组件库")
        return row

    def digest(self, asset_id):
        with self.connect() as db:
            row = db.execute("SELECT digest FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError("组件不存在，请刷新组件库")
        return row["digest"]

    def preview(self, asset_id):
        with self.connect() as db:
            row = db.execute("SELECT preview FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None or not row["preview"]:
            raise ValueError("组件没有预览图")
        return row["preview"]

    @staticmethod
    def validate_fields(fields):
        result = {}
        for key, default, limit in [("name", "", 120), ("category", "未分类", 80), ("tags", "", 300), ("note", "", 2000)]:
            value = fields.get(key, default)
            if not isinstance(value, str):
                raise ValueError("组件信息必须是文本")
            value = value.strip()
            if len(value) > limit:
                raise ValueError(f"{key} 超过最大长度 {limit}")
            result[key] = value
        if not result["name"]:
            raise ValueError("请输入组件名称")
        result["category"] = result["category"] or "未分类"
        mode = fields.get("insert_mode", "new-body")
        if mode not in ("new-body", "union", "difference", "intersection"):
            raise ValueError("无效的默认置入模式")
        result["insert_mode"] = mode
        return result

    def add(self, model, fields, preview=None, source_version="unknown"):
        location = self.organization(fields)
        recipe = validate_recipe(fields.get("recipe"), model)
        fields = self.validate_fields(fields)
        if not isinstance(model, bytes) or not 1 <= len(model) <= MAX_MODEL_BYTES:
            raise ValueError("模型数据为空或超过 64 MB")
        self.validate_preview(preview)
        if not isinstance(source_version, str) or len(source_version) > 80:
            raise ValueError("无效的来源版本")
        asset_id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("""INSERT INTO assets
                (id,name,category,tags,note,created_at,updated_at,source_version,digest,model,preview,library_id,folder_id,kind,insert_mode,recipe_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                asset_id, fields["name"], fields["category"], fields["tags"], fields["note"],
                timestamp, timestamp, source_version,
                hashlib.sha256(model).hexdigest(), model, preview, *location, fields["insert_mode"], json.dumps(recipe,ensure_ascii=False),
            ))
        return self.details(asset_id)

    def update(self, asset_id, fields):
        current = self.details(asset_id)
        location = self.organization(fields, current)
        update_preview = "preview" in fields
        preview = self.validate_preview(fields.get("preview")) if update_preview else None
        fields = self.validate_fields(current | fields)
        with self.connect() as db:
            db.execute("UPDATE assets SET name=?,category=?,tags=?,note=?,updated_at=?,library_id=?,folder_id=?,kind=?,insert_mode=? WHERE id=?", (
                fields["name"], fields["category"], fields["tags"], fields["note"], datetime.now(timezone.utc).isoformat(), *location, fields["insert_mode"], asset_id,
            ))
            if update_preview:
                db.execute("UPDATE assets SET preview=? WHERE id=?", (preview, asset_id))
        return self.details(asset_id)

    def archive(self, asset_id, archived):
        self.details(asset_id)
        with self.connect() as db:
            db.execute("UPDATE assets SET archived=? WHERE id=?", (int(archived), asset_id))

    def export(self, asset_id):
        row = self.get(asset_id)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps({
                "format": "plasticity-asset-tool", "version": 1, **self.metadata(row),
            }, ensure_ascii=False))
            archive.writestr("model.bin", row["model"])
            if row["preview"]:
                archive.writestr("preview.jpg", row["preview"])
        return output.getvalue()

    def import_package(self, payload, library_id="default", folder_id=None):
        self.validate_location(library_id, folder_id)
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                if len(entries) > 3 or len({e.filename for e in entries}) != len(entries):
                    raise ValueError("组件包包含多余或重复文件")
                for entry in entries:
                    limit = {"manifest.json": 65536, "model.bin": MAX_MODEL_BYTES, "preview.jpg": MAX_PREVIEW_BYTES}.get(entry.filename)
                    if limit is None or entry.file_size > limit:
                        raise ValueError("组件包格式无效或文件过大")
                manifest = json.loads(archive.read("manifest.json"))
                if manifest.get("format") != "plasticity-asset-tool" or manifest.get("version") != 1:
                    raise ValueError("不支持的组件包版本")
                model = archive.read("model.bin")
                if hashlib.sha256(model).hexdigest() != manifest.get("digest"):
                    raise ValueError("组件包模型校验失败")
                preview = archive.read("preview.jpg") if "preview.jpg" in archive.namelist() else None
                return self.add(model, manifest | {"library_id": library_id, "folder_id": folder_id}, preview, manifest.get("source_version", "unknown"))
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeError, AttributeError) as exc:
            raise ValueError("无效的 .patasset 组件包") from exc
