"""Validate the observed Plasticity 26.x clipboard envelope without changing bytes.

This checks framing and Parasolid signatures, not kernel geometry validity.
Unknown encodings are rejected rather than sent to the native paste command.
"""
import json
import math
import struct
import base64
import hashlib
import threading
import copy
from collections import OrderedDict

MAX_BYTES = 64 * 1024 * 1024


def model_base_point(data):
    validate_model(data)
    return list(struct.unpack_from('<3d', data))


def with_base_point(data, point, orientation=None):
    validate_model(data)
    if not isinstance(point, list) or len(point) != 3 or any(
        type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e12 for v in point
    ):
        raise ValueError('基点必须是三个有限坐标')
    # Verified against native 26.1.3 copy(Vector3): XYZ uses the same units
    # as the kernel preview. Preserve quaternion, bodies and recipe bytes.
    tail = data[24:]
    if orientation is not None:
        if not isinstance(orientation, list) or len(orientation) != 4 or any(
            type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e12 for v in orientation
        ):
            raise ValueError('基点方向必须是有效四元数')
        length=math.sqrt(sum(v*v for v in orientation))
        if length<1e-12:
            raise ValueError('基点方向必须是有效四元数')
        # Native copy(point, Quaternion) verified in 26.1.3: XYZW.
        tail=struct.pack('<4d',*(v/length for v in orientation))+data[56:]
    return struct.pack('<3d', *point) + tail


def _parse_model(data):
    def invalid():
        return ValueError("数据不是完整的 Plasticity 模型，已阻止置入。请在 Plasticity 中重新复制模型")

    if not isinstance(data, bytes) or not 68 <= len(data) <= MAX_BYTES:
        raise invalid()
    offset = 56

    def integer():
        nonlocal offset
        if offset + 4 > len(data):
            raise invalid()
        value = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        return value

    def block():
        nonlocal offset
        size = integer()
        if size > len(data) - offset:
            raise invalid()
        value = data[offset:offset + size]
        offset += size
        return value

    def json_block():
        try:
            return json.loads(block())
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise invalid() from exc

    if not all(math.isfinite(value) for value in struct.unpack_from("<7d", data)):
        raise invalid()
    try:
        block().decode("utf-8")  # Optional source document identifier.
    except UnicodeError as exc:
        raise invalid() from exc
    if not isinstance(json_block(), (list, dict)):
        raise invalid()
    count = integer()
    if not 0 < count <= (len(data) - offset) // 8:
        raise invalid()
    bodies = []
    for _ in range(count):
        geometry = block()
        if not geometry.startswith(b"PS\x00\x00\x003: TRANSMIT FILE"):
            raise invalid()
        metadata = json_block()
        if not isinstance(metadata, dict):
            raise invalid()
        bodies.append((geometry, metadata))
    # Win32 allocations may contain null padding; no other trailing payload.
    if any(data[offset:]):
        raise invalid()
    return bodies


_CACHE_LIMIT = 32 * 1024 * 1024
_cache = OrderedDict()
_cache_bytes = 0
_cache_lock = threading.RLock()


def prepared_model(data):
    global _cache_bytes
    if not isinstance(data, bytes) or not 68 <= len(data) <= MAX_BYTES:
        _parse_model(data)
    digest = hashlib.sha256(data).digest()
    with _cache_lock:
        cached = _cache.get(digest)
        if cached and cached[0][0] == data:
            _cache.move_to_end(digest)
            return cached[0]
        parts = _parse_model(data)
        entry = [data, parts, None]
        # Conservatively account for Python JSON objects, not just body bytes.
        cost = 8 * len(data) + (len(data) * 4 // 3 + 4) + sum(len(body) for body, _ in parts) + 1024 * len(parts)
        if cost <= _CACHE_LIMIT:
            while _cache and (_cache_bytes + cost > _CACHE_LIMIT or len(_cache) >= 16):
                _, old = _cache.popitem(last=False)
                _cache_bytes -= old[1]
            _cache[digest] = (entry, cost)
            _cache_bytes += cost
        return entry


def parse_model(data):
    return [(body, copy.deepcopy(meta)) for body, meta in prepared_model(data)[1]]


def encoded_model(data):
    with _cache_lock:
        entry = prepared_model(data)
        if entry[2] is None:
            entry[2] = base64.b64encode(data).decode('ascii')
        return entry[2]


def validate_model(data):
    prepared_model(data)
    return data
