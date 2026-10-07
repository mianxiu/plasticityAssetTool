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
sys.path.insert(0, str(ROOT))
from backend.version import APP_VERSION


def build(python_runtime, dependencies):
    python_runtime, dependencies = Path(python_runtime).resolve(), Path(dependencies).resolve()
    if not (python_runtime / 'pythonw.exe').is_file() or not (dependencies / 'tornado').is_dir():
        raise ValueError('需要完整 Windows Python 运行时及 Tornado 依赖目录')
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(ROOT / 'build-launcher.ps1')], cwd=ROOT, check=True)
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(ROOT / 'install-plugin.ps1'), '-BuildOnly'], cwd=ROOT, check=True)
    stage = ROOT / '.runtime/release-staging' / uuid.uuid4().hex / 'plasticityassettool'
    stage.mkdir(parents=True)
    shutil.copy2(ROOT / '.runtime/plasticityassettool.plugininstaller.exe', stage / 'plugininstaller.exe')
    for name in ['main.py', 'start.ps1', 'config.json', 'LICENSE', 'NOTICE', 'OFFICIAL-LICENSE.md', 'DISCLAIMER.md', 'requirements.txt',
                 'install-plugin.ps1', 'plasticityassettool.exe']:
        shutil.copy2(ROOT / name, stage / name)
    excluded = shutil.ignore_patterns('__pycache__', '*.pyc', 'node_modules', 'test', 'tests', 'site-packages')
    for name in ['backend', 'installer', 'plasticity-javascript-payloads']:
        shutil.copytree(ROOT / name, stage / name, ignore=excluded)
    shutil.copytree(ROOT / 'plasticity-asset-tool-app/dist', stage / 'plasticity-asset-tool-app/dist')
    shutil.copytree(ROOT / 'plasticity-asset-tool-app/src/assets', stage / 'plasticity-asset-tool-app/src/assets')
    notices = stage / 'third-party-licenses'
    notices.mkdir()
    modules = ROOT / 'plasticity-asset-tool-app/node_modules'
    for name in ('solid-js', 'three'):
        shutil.copy2(modules / name / 'LICENSE', notices / (name + '-LICENSE.txt'))
    for name in ('seroval', 'seroval-plugins'):
        matches = list((modules / '.pnpm').glob(name + '@*/node_modules/' + name + '/LICENSE*'))
        if not matches:
            raise ValueError('Missing third-party license: ' + name)
        shutil.copy2(matches[0], notices / (name + '-LICENSE.txt'))

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
    (stage / 'readme.txt').write_text(
        f'plasticity asset tool v{APP_VERSION}\n'
        '解压整个目录，双击 plasticityassettool.exe。无需另外安装 Python 或 Node.js。\n'
        '后台由托盘控制退出；重复打开复用已有实例。\n'
        '在后台控制中心的“更新与安装”查看下一步操作，选择安装、更新或重新安装内嵌插件。\n'
        '安装前自行保存并关闭对应 Plasticity 窗口，再在安装窗口确认 Windows 权限请求。\n'
        '用户组件保存在 library/，运行日志及插件恢复备份保存在 .runtime/。\n'
        '更新前请保留这两个目录。EXE 必须与整个发布目录一起使用。\n'
        '公众许可证：GPL-3.0-only，完整条款见 LICENSE，项目声明见 NOTICE。\n'
        'Plastic Software LLC 的单独官方集成授权见 OFFICIAL-LICENSE.md；不适用于无关第三方。\n'
        '第三方声明与使用风险见 DISCLAIMER.md；本工具非官方产品，尚未取得对注入方式的明确官方授权。\n'
        '安装前确认所需权限，备份文档与组件库，并先在独立测试文档中验证。\n'
        '第三方组件保留各自的许可证；用户模型数据不因使用本工具而采用 GPL。\n'
        '源码：https://github.com/mianxiu/plasticityassettool\n', encoding='utf-8-sig')
    releases = ROOT / '.runtime/releases'
    releases.mkdir(exist_ok=True)
    archive = releases / 'plasticityassettool-windows-x64.zip'
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
