"""Validate the observed Plasticity 26.x clipboard envelope without changing bytes.

This checks framing and Parasolid signatures, not kernel geometry validity.
Unknown encodings are rejected rather than sent to the native paste command.
"""
import json
import math
import struct

MAX_BYTES = 64 * 1024 * 1024


def parse_model(data):
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


def validate_model(data):
    parse_model(data)
    return data
