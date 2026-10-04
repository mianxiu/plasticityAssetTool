"""Digest-keyed mesh cache and jobs handled by an initialized Plasticity kernel.

Only validated stored model bytes reach a worker. Workers never receive filenames
or code, and their temporary partitions never enter the editor's database.
"""
import asyncio
import base64
import hashlib
import json
import math
import time
import uuid
import zlib
from model_clipboard import parse_model

MAX_MESH_BYTES = 32 * 1024 * 1024
MAX_VALUES = 2_000_000


def validate_mesh(mesh):
    if not isinstance(mesh, dict) or mesh.get("version") != 1:
        raise ValueError("无效的预览网格版本")
    parts = mesh.get("parts")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 256:
        raise ValueError("预览网格数量无效")
    total = 0
    nonempty = False
    clean = []
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError("预览网格格式无效")
        item = {}
        for key in ("positions", "normals", "indices", "edges", "edge_groups"):
            values = part.get(key)
            if not isinstance(values, list) or len(values) > MAX_VALUES:
                raise ValueError("预览网格超过限制")
            total += len(values)
            if total > MAX_VALUES:
                raise ValueError("预览网格超过限制")
            if key in ("indices", "edge_groups"):
                if any(type(v) is not int or v < 0 for v in values):
                    raise ValueError("预览网格索引无效")
            elif any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e12 for v in values):
                raise ValueError("预览网格坐标无效")
            item[key] = values
        vertices = len(item["positions"]) // 3
        if len(item["positions"]) % 3 or len(item["normals"]) != len(item["positions"]) or len(item["indices"]) % 3 or len(item["edges"]) % 3:
            raise ValueError("预览网格长度无效")
        if any(i >= vertices for i in item["indices"]):
            raise ValueError("预览网格索引越界")
        groups = item["edge_groups"]
        if len(groups) % 2 or any(start % 3 or count % 3 or start + count > len(item["edges"]) for start, count in zip(groups[::2], groups[1::2])):
            raise ValueError("预览边线分组无效")
        nonempty |= bool(item["indices"] or item["edges"])
        clean.append(item)
    if not nonempty:
        raise ValueError("模型没有可预览的面或曲线")
    result = {"version": 1, "parts": clean}
    if len(json.dumps(result, separators=(",", ":"))) > MAX_MESH_BYTES:
        raise ValueError("预览网格超过限制")
    return result


class GeometryPreview:
    def __init__(self, library):
        self.library = library
        self.workers = {}
        self.jobs = {}
        self.inflight = {}

    def connected_targets(self):
        now = time.monotonic()
        return [target for target, worker in self.workers.items() if now - worker["seen"] < 5]

    def cached(self, asset_id):
        row = self.library.get(asset_id)
        with self.library.connect() as db:
            cached = db.execute("SELECT mesh FROM geometry_cache WHERE digest=?", (row["digest"],)).fetchone()
        return json.loads(zlib.decompress(cached["mesh"])) if cached else None

    def thumbnail(self, asset_id):
        row = self.library.get(asset_id)
        with self.library.connect() as db:
            cached = db.execute("SELECT thumbnail FROM geometry_cache WHERE digest=?", (row["digest"],)).fetchone()
        if not cached or not cached["thumbnail"]:
            raise ValueError("组件没有几何预览图")
        return cached["thumbnail"]

    def save_thumbnail(self, asset_id, digest, preview):
        self.library.validate_preview(preview)
        if preview is None or self.library.get(asset_id)["digest"] != digest:
            raise ValueError("几何预览与组件不匹配")
        with self.library.connect() as db:
            if not db.execute("UPDATE geometry_cache SET thumbnail=? WHERE digest=?", (preview, digest)).rowcount:
                raise ValueError("请先生成预览网格")
        return {"ok": True}

    def worker(self, target, token, result=None):
        if not isinstance(target, str) or not target.startswith("hwnd:") or not target[5:].isdigit() or not isinstance(token, str) or len(token) != 36:
            raise ValueError("无效的预览工作连接")
        now = time.monotonic()
        self.workers = {key: value for key, value in self.workers.items() if now - value["seen"] < 30}
        if target not in self.workers and len(self.workers) >= 64:
            raise ValueError("预览工作连接过多")
        previous = self.workers.get(target)
        if previous and previous["token"] != token and now - previous["seen"] < 5:
            raise ValueError("预览窗口已有连接")
        self.workers[target] = {"token": token, "seen": now}
        if result:
            job = self.jobs.get(result.get("id"))
            if job and job["target"] == target and job.get("token") == token and not job["future"].done():
                try:
                    if result.get("error"):
                        raise ValueError("几何预览失败：" + str(result["error"])[:300])
                    mesh = validate_mesh(result.get("mesh"))
                    with self.library.connect() as db:
                        db.execute("INSERT OR REPLACE INTO geometry_cache(digest,mesh) VALUES (?,?)", (job["digest"], zlib.compress(json.dumps(mesh, separators=(",", ":")).encode())))
                    job["future"].set_result(mesh)
                except ValueError as error:
                    job["future"].set_exception(error)
        for job_id, job in self.jobs.items():
            if job["target"] == target and not job["sent"] and not job["future"].done():
                job["sent"] = True
                job["token"] = token
                return {"id": job_id, "parts": job["parts"]}
        return None

    async def generate(self, asset_id, target=None):
        row = await asyncio.to_thread(self.library.get, asset_id)
        cached = await asyncio.to_thread(self.cached, asset_id)
        if cached:
            return cached
        model = bytes(row["model"])
        if hashlib.sha256(model).hexdigest() != row["digest"]:
            raise ValueError("组件数据校验失败，已阻止生成预览")
        bodies = parse_model(model)
        if len(bodies) > 256:
            raise ValueError("组件对象过多，请拆分后生成预览")
        now = time.monotonic()
        live = {key: value for key, value in self.workers.items() if now - value["seen"] < 5}
        if target and target not in live:
            raise ValueError("目标窗口的几何预览插件未连接，请重新打开已安装插件的 Plasticity")
        target = target or next(iter(live), None)
        if not target:
            raise ValueError("请启动已安装内嵌插件的 Plasticity，生成几何预览")
        existing = self.inflight.get(row["digest"])
        if existing:
            return await asyncio.shield(existing)
        if len(self.jobs) >= 8:
            raise ValueError("预览队列已满，请稍后重试")
        future = asyncio.get_running_loop().create_future()
        job_id = uuid.uuid4().hex
        self.inflight[row["digest"]] = future
        self.jobs[job_id] = {"target": target, "future": future, "digest": row["digest"], "sent": False,
                             "parts": [base64.b64encode(body).decode() for body, _ in bodies]}
        try:
            return await asyncio.wait_for(asyncio.shield(future), 25)
        except asyncio.TimeoutError as error:
            raise ValueError("几何预览生成超时，模型已保留，可稍后重试") from error
        finally:
            self.jobs.pop(job_id, None)
            self.inflight.pop(row["digest"], None)
            if not future.done():
                future.cancel()
