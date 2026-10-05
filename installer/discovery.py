"""Read-only Windows Plasticity installation and process discovery."""
import json
import os
import re
import subprocess
from pathlib import Path

SUPPORTED_VERSIONS = {'26.1.3'}
ENTRY = Path('resources/app/.webpack/main/index.js')


def running_processes():
    if os.name != 'nt':
        return []
    command = '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-Process -Name Plasticity -ErrorAction SilentlyContinue | Select-Object Id,Path | ConvertTo-Json -Compress'
    powershell = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
    try:
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, encoding='utf-8', timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError('无法检查 Plasticity 运行状态，请重试')
        data = json.loads(result.stdout) if result.stdout.strip() else []
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise RuntimeError('无法检查 Plasticity 运行状态，请重试') from exc
    return data if isinstance(data, list) else [data]


def roots():
    found = []
    for variable, tail in (('ProgramFiles', 'Plasticity'), ('ProgramFiles(x86)', 'Plasticity'),
                           ('LOCALAPPDATA', 'Plasticity'), ('LOCALAPPDATA', 'Programs/Plasticity')):
        if os.environ.get(variable):
            found.append(Path(os.environ[variable]) / tail)
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as key:
                        for index in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                with winreg.OpenKey(key, winreg.EnumKey(key, index)) as item:
                                    if 'plasticity' in str(winreg.QueryValueEx(item, 'DisplayName')[0]).lower():
                                        found.append(Path(winreg.QueryValueEx(item, 'InstallLocation')[0]))
                            except OSError:
                                continue
                except OSError:
                    continue
    return found


def inspect_directory(folder):
    folder = Path(folder).resolve()
    package = folder / 'resources/app/package.json'
    target = folder / ENTRY
    if not (folder / 'Plasticity.exe').is_file() or not package.is_file() or not target.is_file() or not target.with_name('index.compiled.jsc').is_file():
        raise ValueError('目录中未找到完整的 Plasticity 安装，请选择 app-版本号目录或它的上级目录')
    metadata = json.loads(package.read_text(encoding='utf-8'))
    version = metadata.get('version', '')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][\w.-]+)?', version):
        raise ValueError('无法识别 Plasticity 版本')
    return {'path': str(folder), 'target': str(target), 'version': version,
            'supported': version in SUPPORTED_VERSIONS}


def directories(folder):
    folder = Path(folder).resolve()
    yield folder
    if folder.is_dir():
        yield from sorted(folder.glob('app-*'))


def assert_closed(target):
    folder = Path(target).resolve().parents[4]
    for process in running_processes():
        path = process.get('Path')
        if not path or Path(path).resolve().parent == folder:
            raise ValueError('此版本 Plasticity 正在运行，请自行保存文档并关闭它的所有窗口后再安装')
