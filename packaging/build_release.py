"""Build a Windows folder release without local models or developer caches."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(python_runtime, dependencies):
    python_runtime, dependencies = Path(python_runtime).resolve(), Path(dependencies).resolve()
    if not (python_runtime / 'pythonw.exe').is_file() or not (dependencies / 'tornado').is_dir():
        raise ValueError('需要完整 Windows Python 运行时及 Tornado 依赖目录')
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(ROOT / 'build-launcher.ps1')], cwd=ROOT, check=True)
    stage = ROOT / '.runtime/release-staging' / uuid.uuid4().hex / 'PlasticityAssetTool'
    stage.mkdir(parents=True)
    for name in ['main.py', 'start.ps1', 'config.json', 'LICENSE', 'requirements.txt',
                 'install-plugin.ps1', 'PlasticityAssetTool.exe']:
        shutil.copy2(ROOT / name, stage / name)
    excluded = shutil.ignore_patterns('__pycache__', '*.pyc', 'node_modules', 'test', 'tests', 'site-packages')
    for name in ['backend', 'installer', 'plasticity-javascript-payloads']:
        shutil.copytree(ROOT / name, stage / name, ignore=excluded)
    shutil.copytree(ROOT / 'plasticity-asset-tool-app/dist', stage / 'plasticity-asset-tool-app/dist')
    shutil.copytree(ROOT / 'plasticity-asset-tool-app/src/assets', stage / 'plasticity-asset-tool-app/src/assets')
    runtime = stage / 'runtime/python'
    runtime.mkdir(parents=True)
    for path in python_runtime.iterdir():
        if path.is_file() and (path.suffix in ('.exe', '.dll') or path.name == 'LICENSE.txt'):
            shutil.copy2(path, runtime / path.name)
    for name in ['Lib', 'DLLs']:
        shutil.copytree(python_runtime / name, runtime / name, ignore=excluded)
    site = runtime / 'Lib/site-packages'
    site.mkdir()
    for path in dependencies.glob('tornado*'):
        if path.is_dir():
            shutil.copytree(path, site / path.name, ignore=excluded)
    # Model stores and status/settings are created locally on first launch.
    (stage / 'Readme.txt').write_text(
        '解压整个目录，双击 PlasticityAssetTool.exe。无需另外安装 Python 或 Node.js。\n'
        '后台由托盘控制退出；重复打开复用已有实例。\n'
        '在 Plasticity 内使用 Tab，需要先按项目说明安装内嵌插件。\n'
        '用户组件保存在 library/，运行日志及插件恢复备份保存在 .runtime/。\n'
        '更新前请保留这两个目录。EXE 必须与整个发布目录一起使用。\n'
        '源码：https://github.com/mianxiu/plasticityAssetTool\n', encoding='utf-8-sig')
    releases = ROOT / '.runtime/releases'
    releases.mkdir(exist_ok=True)
    archive = releases / 'PlasticityAssetTool-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in stage.rglob('*'):
            if path.is_file():
                bundle.write(path, path.relative_to(stage.parent))
    checksum = archive.with_suffix('.zip.sha256')
    checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n', encoding='ascii')
    return {'directory': str(stage), 'archive': str(archive), 'checksum': str(checksum), 'bytes': archive.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-runtime', required=True)
    parser.add_argument('--dependencies', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.python_runtime, args.dependencies), ensure_ascii=False))
