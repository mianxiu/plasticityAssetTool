"""Validate observed native clipboard envelopes without changing bytes.

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
PARASOLID_SIGNATURE = b'PS\x00\x00\x003: TRANSMIT FILE'


def placement_offset(prefix):
    # Count-first framing has an opaque 56-byte prefix after its count.
    # Its coordinate offsets must be established by a native probe.
    return 4 if len(prefix) >= 64 + len(PARASOLID_SIGNATURE) and prefix[64:].startswith(PARASOLID_SIGNATURE) else 0


class ModelFormatError(ValueError):
    """Framing diagnostics contain offsets only, never model contents."""
    def __init__(self, stage, offset, size):
        self.diagnostic = f'{stage}，偏移 {offset}，共 {size} 字节'
        super().__init__(f'数据不是完整的 Plasticity 模型（{self.diagnostic}），已阻止置入')


def model_base_point(data, layout=None):
    validate_model(data)
    if placement_offset(data) and layout is None:
        raise ValueError('请先在连接设置中自动检测模型格式，再编辑此版本的基点')
    return list(struct.unpack_from('<3d', data, layout['point'] if layout else 0))


def model_orientation(data, layout=None):
    validate_model(data)
    if placement_offset(data) and layout is None:
        raise ValueError('请先自动检测模型格式')
    if layout and layout['orientation_kind'] != 'quaternion':
        return direction_orientation(data, layout['orientation'])
    return list(struct.unpack_from('<4d', data, layout['orientation'] if layout else 24))


def direction_orientation(prefix, offset):
    x,y,z = struct.unpack_from('<3d', prefix, offset)
    length = math.sqrt(x*x+y*y+z*z)
    if not math.isfinite(length):
        raise ValueError('原生基点方向无效')
    if length < 1e-12:
        return [0,0,0,1]
    x,y,z = x/length,y/length,z/length
    if z < -1+1e-12:
        return [1,0,0,0]
    q = [-y,x,0,1+z]
    length = math.sqrt(sum(v*v for v in q))
    return [v/length for v in q]


def copy_model_placement(data, reference):
    validate_model(data)
    validate_model(reference)
    target_offset, source_offset = placement_offset(data), placement_offset(reference)
    if target_offset != source_offset:
        raise ValueError('原生定位结构不同，请在组件来源版本中修改基点')
    return data[:target_offset] + reference[source_offset:source_offset + 56] + data[target_offset + 56:]


def same_model_content(left, right):
    validate_model(left)
    validate_model(right)
    a, b = placement_offset(left), placement_offset(right)
    return a == b and left[:a] == right[:b] and left[a + 56:] == right[b + 56:]


def with_base_point(data, point, orientation=None, layout=None):
    validate_model(data)
    if not isinstance(point, list) or len(point) != 3 or any(
        type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e12 for v in point
    ):
        raise ValueError('基点必须是三个有限坐标')
    # Verified against native 26.1.3 copy(Vector3): XYZ uses the same units
    # as the kernel preview. Preserve quaternion, bodies and recipe bytes.
    if placement_offset(data) and layout is None:
        raise ValueError('请先在连接设置中自动检测模型格式，再编辑此版本的基点')
    point_offset = layout['point'] if layout else 0
    result = bytearray(data)
    struct.pack_into('<3d', result, point_offset, *point)
    if orientation is not None:
        if not isinstance(orientation, list) or len(orientation) != 4 or any(
            type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e12 for v in orientation
        ):
            raise ValueError('基点方向必须是有效四元数')
        length=math.sqrt(sum(v*v for v in orientation))
        if length<1e-12:
            raise ValueError('基点方向必须是有效四元数')
        # Native copy(point, Quaternion) verified in 26.1.3: XYZW.
        if layout and layout['orientation_kind'] != 'quaternion':
            raise ValueError('此版本仅保存原生方向，暂不支持离线旋转基点；请使用原生拾取')
        struct.pack_into('<4d', result, layout['orientation'] if layout else 24, *(v/length for v in orientation))
    return bytes(result)


def _parse_model(data):
    offset = 0
    stage = '数据长度'
    def invalid():
        return ModelFormatError(stage, offset, len(data) if isinstance(data, bytes) else 0)

    if not isinstance(data, bytes) or not 68 <= len(data) <= MAX_BYTES:
        raise invalid()
    start = placement_offset(data)
    offset = start + 56
    stage = '定位头'

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

    if not start and not all(math.isfinite(value) for value in struct.unpack_from("<7d", data)):
        raise invalid()
    if start:
        stage = '对象数量'
        count = struct.unpack_from('<I', data)[0]
    else:
        stage = '文档标识'
        try:
            block().decode("utf-8")  # Optional source document identifier.
        except UnicodeError as exc:
            raise invalid() from exc
        stage = '选择信息'
        if not isinstance(json_block(), (list, dict)):
            raise invalid()
        stage = '对象数量'
        count = integer()
    if not 0 < count <= (len(data) - offset) // 8:
        raise invalid()
    bodies = []
    for _ in range(count):
        stage = '几何数据'
        geometry = block()
        if not geometry.startswith(PARASOLID_SIGNATURE):
            raise invalid()
        stage = '对象元数据'
        metadata = json_block()
        if not isinstance(metadata, dict):
            raise invalid()
        bodies.append((geometry, metadata))
    # Win32 allocations may contain null padding; no other trailing payload.
    stage = '尾部数据'
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
