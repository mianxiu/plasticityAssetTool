"""Synthetic framing fixture; not a model to paste into a real CAD window."""
import json
import struct


def model_bytes(name="component", count=1, source=""):
    def block(value):
        return struct.pack("<I", len(value)) + value
    header = struct.pack("<7d", 0, 0, 0, 0, 0, 0, 1)
    geometry = b"PS\x00\x00\x003: TRANSMIT FILE created by modeller version 3500232\x00synthetic"
    item = block(geometry) + block(json.dumps({"name": name}).encode())
    return header + block(source.encode()) + block(b"[]") + struct.pack("<I", count) + item * count


def count_first_model_bytes(name="component", count=1):
    # Observed 25.2.5 framing, with synthetic geometry instead of user data.
    modern = model_bytes(name=name, count=count)
    return struct.pack('<I', count) + bytes(56) + modern[70:]
