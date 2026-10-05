"""Generate the shared Windows ICO from a simple cube at each native size."""
import math
import struct
import zlib
from pathlib import Path

SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
OUTPUT = Path(__file__).resolve().parents[1] / 'plasticity-asset-tool-app/src/assets/favicon.ico'
VERTICES = ((.5,.09),(.87,.3),(.87,.7),(.5,.91),(.13,.7),(.13,.3))
SEGMENTS = list(zip(VERTICES, VERTICES[1:]+VERTICES[:1])) + [
    ((.13,.3),(.5,.51)), ((.87,.3),(.5,.51)), ((.5,.51),(.5,.91))]

def bitmap(size):
    # Supersample independently per size; no enlargement of a tiny source image.
    pixels = bytearray()
    radius = max(.65, size*.018)/size
    for y in reversed(range(size)):
        for x in range(size):
            coverage = 0
            for sy in range(4):
                for sx in range(4):
                    px,py=(x+(sx+.5)/4)/size,(y+(sy+.5)/4)/size
                    for (ax,ay),(bx,by) in SEGMENTS:
                        ratio=max(0,min(1,((px-ax)*(bx-ax)+(py-ay)*(by-ay))/((bx-ax)**2+(by-ay)**2)))
                        if math.hypot(px-ax-ratio*(bx-ax),py-ay-ratio*(by-ay)) <= radius:
                            coverage+=1
                            break
            pixels.extend((230,230,230,round(255*coverage/16)))
    mask_stride=((size+31)//32)*4
    return struct.pack('<IiiHHIIiiII',40,size,size*2,1,32,0,len(pixels),0,0,0,0)+pixels+bytes(mask_stride*size)

def build():
    images=[]
    for size in SIZES:
        data=bitmap(size)
        if size >= 64:
            # Windows supports PNG entries; keep large DPI variants compact.
            rows=[]
            for y in reversed(range(size)):
                row=data[40+y*size*4:40+(y+1)*size*4]
                rgba=bytearray()
                for x in range(0,len(row),4):
                    rgba.extend((row[x+2],row[x+1],row[x],row[x+3]))
                rows.append(b'\0'+rgba)
            def chunk(kind,payload):
                return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))
            data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')
        images.append(data)
    offset=6+16*len(images)
    entries=[]
    for size,data in zip(SIZES,images):
        entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset))
        offset+=len(data)
    OUTPUT.write_bytes(struct.pack('<HHH',0,1,len(images))+b''.join(entries)+b''.join(images))
    return OUTPUT

if __name__ == '__main__':
    print(build())
