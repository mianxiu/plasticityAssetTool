"""Discover, validate and launch reversible plugin installation jobs."""
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from installer import discovery
from installer.main_embed_install import MARKER, patch_main
from installer.embedded_install import digest


class PluginManager:
    def __init__(self, root, process_reader=None, root_reader=None, runner=None):
        self.root = Path(root).resolve()
        self.process_reader = process_reader or discovery.running_processes
        self.root_reader = root_reader or discovery.roots
        self.runner = runner or self.run_installer
        self.records = {}
        self.job = None
        self.task = None
        self.lock = asyncio.Lock()

    def snapshot(self):
        return {'installations': list(self.records.values()), 'job': self.job,
                'supported_versions': sorted(discovery.SUPPORTED_VERSIONS)}

    def backups(self, target):
        runtime = self.root / '.runtime'
        candidates = list(runtime.glob('*.manifest.json')) + list((runtime / 'plugin-backups').glob('*.manifest.json'))
        result = []
        for manifest in candidates:
            try:
                data = json.loads(manifest.read_text(encoding='utf-8-sig'))
                backup = manifest.with_name(manifest.name[:-len('.manifest.json')] + '.js')
                original = backup.read_bytes()
                if Path(data['target']).resolve() == target and digest(original) == data['original_sha256']:
                    result.append((data, backup, original))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return result

    def inspect(self, folder, processes):
        row = discovery.inspect_directory(folder)
        target = Path(row['target'])
        current = target.read_bytes()
        source = current.decode('utf-8')
        if './index.compiled.jsc' not in source:
            raise ValueError('不是支持的 Plasticity main 入口')
        row.update(id=hashlib.sha256(str(target).casefold().encode()).hexdigest()[:24],
                   installed=MARKER in source, sha256=digest(current), state='not-installed',
                   running=any(not p.get('Path') or Path(p['Path']).resolve().parent == Path(row['path']) for p in processes))
        saved = self.backups(target)
        previous = next((item for item in saved if item[0]['patched_sha256'] == row['sha256']), None)
        base = next((item for item in saved if MARKER.encode() not in item[2] and current.endswith(item[2])), None)
        if row['installed']:
            row['state'] = 'backup-missing'
            if previous and base:
                config = json.loads((self.root / 'config.json').read_text(encoding='utf-8'))
                # patch_main reads payloads from the module's application root.
                expected = patch_main(base[2], (self.root / 'plasticity-javascript-payloads/init.js').read_text(encoding='utf-8'),
                                      f'http://127.0.0.1:{config["server"]["http_port"]}/?embedded=1',
                                      config['keymap'].get('show_panel_event_key_code', 'Tab'))
                row.update(state='current' if current == expected else 'update', previous_backup=str(previous[1]), base_backup=str(base[1]))
        row['can_install'] = row['supported'] and not row['running'] and not row['installed']
        row['can_update'] = row['supported'] and not row['running'] and row['state'] == 'update'
        row['can_restore'] = row['supported'] and not row['running'] and bool(previous and base)
        return row

    def scan(self, custom=None):
        processes = self.process_reader()
        roots = self.root_reader() + [Path(p['Path']).parent for p in processes if p.get('Path')]
        if custom:
            if not isinstance(custom, str) or len(custom) > 2048 or not Path(custom).is_absolute():
                raise ValueError('请输入 Plasticity 安装目录的完整路径')
            roots.append(Path(custom))
        rows = {}
        for folder in roots:
            for candidate in discovery.directories(folder):
                try:
                    row = self.inspect(candidate, processes)
                    rows[row['id']] = row
                except (OSError, ValueError, KeyError, UnicodeError):
                    continue
        if custom and not any(Path(r['path']) == Path(custom).resolve() or Path(r['path']).parent == Path(custom).resolve() for r in rows.values()):
            raise ValueError('指定目录中未找到完整的 Plasticity 安装')
        self.records = rows
        return self.snapshot()

    async def start(self, identity, action):
        async with self.lock:
            if self.task and not self.task.done():
                raise ValueError('插件安装正在进行，请等待当前操作完成')
            if not isinstance(action, str) or not isinstance(identity, str) or action not in ('install', 'update', 'restore') or identity not in self.records:
                raise ValueError('请先检测并选择有效的安装版本')
            processes = await asyncio.to_thread(self.process_reader)
            row = await asyncio.to_thread(self.inspect, self.records[identity]['path'], processes)
            if not row.get('can_' + action):
                raise ValueError('当前状态不允许此操作，请刷新检测；运行中的窗口需先自行关闭，更新和恢复需保留有效备份')
            runtime = self.root / '.runtime'
            directory = runtime / 'plugin-backups'
            directory.mkdir(parents=True, exist_ok=True)
            backup = directory / (row['id'] + '-' + uuid.uuid4().hex + '.js')
            if action == 'restore':
                # Restore the original entry, not just the previous patch.
                # Write a verified recovery pair for the exact current patch.
                base = Path(row['base_backup']).read_bytes()
                backup.write_bytes(base)
                backup.with_suffix('.manifest.json').write_text(json.dumps({'target': row['target'], 'original_sha256': digest(base), 'patched_sha256': row['sha256']}, indent=2), encoding='utf-8')
            args = ['--target', row['target'], '--backup', str(backup), '--expected-sha256', row['sha256'], '--managed']
            if action == 'update':
                args += ['--upgrade-from', row['previous_backup'], '--base-backup', row['base_backup']]
            if action == 'restore':
                args += ['--restore']
            token = uuid.uuid4().hex
            request = runtime / ('plugin-install-' + token + '.json')
            result = runtime / ('plugin-install-' + token + '.txt')
            python = self.root / 'runtime/python/python.exe'
            if not python.is_file():
                python = Path(sys.executable).with_name('python.exe') if os.name == 'nt' else Path(sys.executable)
            request.write_text(json.dumps({'root': str(self.root), 'python': str(python), 'target': row['target'], 'backup': str(backup),
                                           'description': {'install': '安装组件库内嵌插件', 'update': '更新组件库内嵌插件', 'restore': '恢复 Plasticity 原始入口'}[action],
                                           'arguments': args, 'result': str(result)}, ensure_ascii=False), encoding='utf-8')
            self.job = {'id': token, 'state': 'waiting', 'action': action, 'installation_id': identity, 'version': row['version'],
                        'path': row['path'], 'backup': str(backup), 'message': '请在插件安装窗口确认操作并批准 Windows 权限请求'}
            self.task = asyncio.create_task(self.finish(request, result, row))
            return self.snapshot()

    def run_installer(self, request):
        exe = self.root / 'PluginInstaller.exe'
        if not exe.is_file():
            exe = self.root / '.runtime/PlasticityAssetTool.PluginInstaller.exe'
        if not exe.is_file():
            subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(self.root / 'install-plugin.ps1'), '-BuildOnly'],
                           cwd=self.root, capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        process = subprocess.Popen([str(exe), str(request)], cwd=self.root)
        return process.wait()

    async def finish(self, request, result, row):
        try:
            code = await asyncio.to_thread(self.runner, request)
            if code == 1223:
                self.job.update(state='cancelled', message='安装或 Windows 权限请求已取消，未完成操作')
            elif code:
                lines = result.read_text(encoding='utf-8-sig').strip().splitlines() if result.exists() else []
                message = lines[-1][:500] if lines else '安装器未完成操作，请重新检测或查看安装窗口'
                self.job.update(state='failed', message=message)
            else:
                processes = await asyncio.to_thread(self.process_reader)
                updated = await asyncio.to_thread(self.inspect, row['path'], processes)
                success = not updated['installed'] if self.job['action'] == 'restore' else updated['state'] == 'current'
                if not success:
                    raise RuntimeError('安装器结束后入口校验未通过，请保留备份并重新检测')
                self.records[updated['id']] = updated
                self.job.update(state='complete', message='入口已验证，下次启动 Plasticity 时生效')
        except Exception as exc:
            self.job.update(state='failed', message=str(exc))
        finally:
            request.unlink(missing_ok=True)
