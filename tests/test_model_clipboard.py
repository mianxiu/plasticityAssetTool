import struct
import unittest
from model_clipboard import validate_model
from model_fixture import model_bytes


class ModelClipboardTests(unittest.TestCase):
    def test_valid_single_multiple_and_source_identifier_preserve_bytes(self):
        for data in (model_bytes(), model_bytes(count=2, source="document-id"), model_bytes() + b"\0\0"):
            self.assertIs(validate_model(data), data)

    def test_text_image_json_empty_and_fake_format_payload_rejected(self):
        for data in (b"", b"hello" * 30, b"\x89PNG" + b"\0" * 100, b"{}" * 100, b"\0" * 100):
            with self.assertRaises(ValueError):
                validate_model(data)

    def test_truncation_at_every_boundary_is_rejected(self):
        data = model_bytes()
        for end in range(len(data)):
            with self.assertRaises(ValueError):
                validate_model(data[:end])

    def test_bad_lengths_count_transform_json_signature_and_trailing_data(self):
        data = model_bytes()
        cases = [data[:56] + struct.pack("<I", 0xffffffff) + data[60:],
                 data[:66] + struct.pack("<I", 0) + data[70:],
                 data[:66] + struct.pack("<I", 0xffffffff) + data[70:],
                 struct.pack("<d", float("nan")) + data[8:],
                 data.replace(b"[]", b"xx", 1),
                 data.replace(b"PS\0\0\0", b"XX\0\0\0", 1),
                 data.replace(b'{"name"', b'{!name"', 1), data + b"other"]
        for changed in cases:
            with self.assertRaises(ValueError):
                validate_model(changed)
