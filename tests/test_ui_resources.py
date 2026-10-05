import json
import re
import struct
import unittest
from pathlib import Path
from backend.service_tray import ICON_PATH, icon_bitmap

ROOT = Path(__file__).resolve().parents[1]


class UiResourcesTests(unittest.TestCase):
    def test_translation_catalogs_cover_ui_and_preserve_parameters(self):
        source = ROOT / 'plasticity-asset-tool-app/src'
        english = json.loads((source / 'locales/en.json').read_text(encoding='utf-8'))
        chinese = json.loads((source / 'locales/zh-CN.json').read_text(encoding='utf-8'))
        self.assertEqual(english.keys(), chinese.keys())
        for file in ('Home.jsx', 'ControlCenter.jsx', 'GeometryPreview.jsx'):
            for literal in re.findall(r'\bt\(("(?:[^"\\]|\\.)*")', (source / file).read_text(encoding='utf-8')):
                self.assertIn(json.loads(literal), english, file)
        for key, value in english.items():
            self.assertEqual(sorted(re.findall(r'\{\w+\}', key)), sorted(re.findall(r'\{\w+\}', value)), key)

    def test_shared_icon_has_native_windows_sizes_and_visible_alpha(self):
        data = ICON_PATH.read_bytes()
        count = struct.unpack_from('<H', data, 4)[0]
        sizes = []
        for index in range(count):
            width, height, _, _, _, _, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + 16*index)
            size = width or 256
            self.assertEqual(size, height or 256)
            self.assertEqual(icon_bitmap(size=size), data[offset:offset+length])
            if data[offset:offset+8] == b'\x89PNG\r\n\x1a\n':
                self.assertEqual(struct.unpack_from('>II', data, offset+16), (size,size))
            else:
                alpha = data[offset+43:offset+40+size*size*4:4]
                self.assertIn(0, alpha)
                self.assertIn(255, alpha)
            sizes.append(size)
        self.assertTrue({16,20,24,32,48,64,128,256}.issubset(sizes))
