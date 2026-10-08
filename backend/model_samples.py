"""Local diagnostic archives; unknown model bytes never enter the asset library."""
import base64
import binascii
import hashlib
import json
import math
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from .native_layout import POINTS, validate_probe
from .version import APP_VERSION

MAX_SAMPLE_BYTES = 4 * 1024 * 1024


def validate_samples(report):
    validate_probe(report)
    inputs = report.get('test_inputs')
    if not isinstance(inputs, dict) or inputs.get('points') != POINTS:
        raise ValueError('测试输入缺失或无效')
    kind = inputs.get('orientation_kind')
    vectors = [[1,2,3,1],[-2,3,1,4]] if kind == 'quaternion' else [[1,2,3],[-2,3,1]] if kind == 'direction' else None
    if vectors is None:
        raise ValueError('测试方向类型无效')
    expected = [[n / math.sqrt(sum(v*v for v in row)) for n in row] for row in vectors]
    actual = inputs.get('orientations')
    try:
        if len(actual) != 2 or any(len(a) != len(b) or any(type(x) not in (int,float) or not math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-10) for x,y in zip(a,b)) for a,b in zip(actual,expected)):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('测试方向值无效')
    samples = []
    for probe in report['probes']:
        encoded = probe.get('model')
        if not isinstance(encoded, str) or len(encoded) > ((MAX_SAMPLE_BYTES + 2)//3)*4:
            raise ValueError('测试样本无效或超过 4 MB')
        try:
            model = base64.b64decode(encoded, validate=True)
            header = base64.b64decode(probe['header'], validate=True)
        except (binascii.Error, ValueError):
            raise ValueError('测试样本编码无效')
        if not len(header) <= len(model) <= MAX_SAMPLE_BYTES or not model.startswith(header) or type(probe.get('bytes')) is not int or probe['bytes'] != len(model) or probe.get('model_sha256') != hashlib.sha256(model).hexdigest():
            raise ValueError('测试样本与检测报告不匹配')
        samples.append(model)
    return samples


class ModelSamples:
    def __init__(self, root):
        self.directory = Path(root) / '.runtime/model-samples'

    def path(self, identity):
        if not isinstance(identity, str) or not re.fullmatch('[a-f0-9]{32}', identity):
            raise ValueError('测试包标识无效')
        return self.directory / (identity + '.zip')

    def save(self, version, report, capabilities):
        samples = validate_samples(report)
        identity = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        diagnostic = {key:report[key] for key in ('format','layout','test_inputs')}
        diagnostic['probes'] = [{key:p[key] for key in ('header','content_digest')} for p in report['probes']]
        manifest = {'schema_version':1, 'created_at':timestamp, 'tool_version':APP_VERSION,
                    'source_version':version, 'verified_layout':report['layout'] is not None,
                    'capabilities':sorted(capabilities), 'samples':[{'file':f'sample-{i+1}.bin','bytes':len(model),'sha256':hashlib.sha256(model).hexdigest()} for i,model in enumerate(samples)]}
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(identity)
        try:
            with path.open('xb') as output, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr('manifest.json', json.dumps(manifest,ensure_ascii=False,indent=2))
                bundle.writestr('report.json', json.dumps(diagnostic,ensure_ascii=False,indent=2))
                bundle.writestr('readme.txt', 'Local Plasticity format diagnostics. Contains the selected test geometry and metadata. No automatic upload. Unknown formats are collected without enabling compatibility. Controlled input coordinates and orientations are in report.json. SHA-256 checksums are in manifest.json.\n')
                for i,model in enumerate(samples):
                    bundle.writestr(f'sample-{i+1}.bin', model)
        except FileExistsError:
            raise
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {'id':identity,'source_version':version,'verified':manifest['verified_layout'],
                'download_url':f'/api/model-samples/{identity}.zip',
                'message':'测试包已保存在本机；包含选中模型，请确认内容后再手动分享'}
