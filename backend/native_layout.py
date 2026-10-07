"""Check a controlled native probe before accepting any coordinate offsets."""
import base64
import binascii
import math
import re
import struct

POINTS = [[123.125, -456.5, 789.75], [11.375, 22.625, -33.875]]


def validate_probe(report):
    if not isinstance(report, dict) or report.get('format') not in ('modern', 'count-first', 'unknown'):
        raise ValueError('模型格式检测结果无效')
    probes = report.get('probes')
    if not isinstance(probes, list) or len(probes) != 2:
        raise ValueError('模型格式检测样本不足')
    headers = []
    for probe in probes:
        try:
            encoded = probe['header']
            if not isinstance(encoded, str) or len(encoded) > 8192:
                raise ValueError()
            header = base64.b64decode(encoded, validate=True)
            if not 56 <= len(header) <= 4096:
                raise ValueError()
            headers.append(header)
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise ValueError('模型格式检测样本无效') from exc
    layout = report.get('layout')
    if layout is None:
        return report  # Diagnostics may legitimately find an unsupported layout.
    if report['format'] == 'unknown' or not isinstance(layout, dict):
        raise ValueError('未验证的模型定位结构')
    digests = [probe.get('content_digest') for probe in probes]
    if not all(isinstance(d,str) and re.fullmatch('[a-f0-9]{64}',d) for d in digests) or digests[0] != digests[1]:
        raise ValueError('改变基点时原生几何或元数据发生变化，不能离线修改定位字段')
    kind = layout.get('orientation_kind')
    if kind not in ('quaternion', 'direction'):
        raise ValueError('模型方向格式无效')
    size = 32 if kind == 'quaternion' else 24
    offsets = [layout.get('point'), layout.get('orientation')]
    minimum = 4 if report['format'] == 'count-first' else 0
    maximum = 60 if report['format'] == 'count-first' else 56
    ranges = []
    for offset, length in zip(offsets, [24, size]):
        if type(offset) is not int or offset < minimum or offset + length > min(maximum, *(len(h) for h in headers)):
            raise ValueError('模型定位字段越界或覆盖对象数量')
        ranges.append(set(range(offset, offset + length)))
    if ranges[0] & ranges[1]:
        raise ValueError('模型定位字段重叠')
    orientations = ([[1/math.sqrt(14),2/math.sqrt(14),3/math.sqrt(14)],
                     [-2/math.sqrt(14),3/math.sqrt(14),1/math.sqrt(14)]] if kind == 'direction' else
                    [[1/math.sqrt(15),2/math.sqrt(15),3/math.sqrt(15),1/math.sqrt(15)],
                     [-2/math.sqrt(30),3/math.sqrt(30),1/math.sqrt(30),4/math.sqrt(30)]])
    for index, header in enumerate(headers):
        for offset, expected in [(offsets[0], POINTS[index]), (offsets[1], orientations[index])]:
            actual = struct.unpack_from('<' + 'd'*len(expected), header, offset)
            if not all(math.isfinite(v) and math.isclose(v, e, rel_tol=1e-10, abs_tol=1e-10) for v,e in zip(actual,expected)):
                raise ValueError('原生检测值与定位字段不匹配')
    return report
