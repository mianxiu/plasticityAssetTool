"""Build the sidebar's wireframe cube as a transparent, multi-size Windows ICO.

Requires Pillow for packaging only; the installed application does not need it.
Run: python packaging/build_icon.py
"""
import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'plasticity-asset-tool-app/src/assets'
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 192, 256)
COLOR = (181, 205, 240)
# Same geometry as Home.jsx's Cube, with the top/right dividing edge.
OUTLINE = ((40, 9), (68, 25), (68, 56), (40, 72), (12, 56), (12, 25), (40, 9))
EDGES = (((12, 25), (40, 41), (68, 25)), ((40, 41), (40, 72)),
         ((26, 17), (54, 33), (54, 64)))


def render(size):
    scale = 8
    image = Image.new('RGBA', (size * scale, size * scale))
    draw = ImageDraw.Draw(image)
    # Tight square canvas keeps the thin cube legible at tray sizes.
    points = lambda path: [((x - 6) * size * scale / 68, (y - 6) * size * scale / 68) for x, y in path]
    draw.polygon(points(OUTLINE), fill=(*COLOR, 20))
    width = round(max(1, size * 1.5 / 68) * scale)
    for path in (OUTLINE, *EDGES):
        draw.line(points(path), fill=(*COLOR, 255), width=width, joint='curve')
    return image.resize((size, size), Image.Resampling.LANCZOS)


def build():
    frames = []
    for size in SIZES:
        output = io.BytesIO()
        render(size).save(output, format='PNG')
        frames.append(output.getvalue())
    offset = 6 + 16 * len(SIZES)
    data = bytearray(struct.pack('<HHH', 0, 1, len(SIZES)))
    for size, frame in zip(SIZES, frames):
        data.extend(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(frame), offset))
        offset += len(frame)
    for frame in frames:
        data.extend(frame)
    target = ASSETS / 'favicon.ico'
    target.write_bytes(data)
    print(target)


if __name__ == '__main__':
    build()
