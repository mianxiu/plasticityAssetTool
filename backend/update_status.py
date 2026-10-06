"""Identify local UI and backend updates without installing or restarting anything."""
import hashlib
import json
import re
import time
from pathlib import Path


class UpdateStatus:
    def __init__(self, root):
        self.root = Path(root)
        self.loaded_backend = self.backend_revision()
        self.cached = None
        self.checked = 0

    def backend_revision(self):
        files = [self.root / 'main.py', self.root / 'config.json']
        for directory in ('backend', 'installer'):
            files += sorted((self.root / directory).rglob('*.py'))
        if not (self.root / 'backend/main.py').is_file():
            return None
        try:
            checksum = hashlib.sha256()
            for path in files:
                checksum.update(path.relative_to(self.root).as_posix().encode())
                checksum.update(b'\0')
                checksum.update(path.read_bytes())
                checksum.update(b'\0')
            return checksum.hexdigest()
        except OSError:
            return None

    def ui_build(self):
        dist = self.root / 'plasticity-asset-tool-app/dist'
        if not (dist / 'ui-build.json').exists():
            return {'state': 'not-built', 'revision': None}
        try:
            build = json.loads((dist / 'ui-build.json').read_text(encoding='utf-8'))
            revision, assets = build['revision'], build['assets']
            if not isinstance(revision, str) or not revision or not isinstance(assets, list) or not assets:
                raise ValueError('Invalid UI build')
            if any(not isinstance(name, str) or '..' in name or
                   not re.fullmatch(r'assets/[A-Za-z0-9_./-]+\.(js|css)', name) or
                   not (dist / name).is_file() for name in assets):
                raise ValueError('Incomplete UI build')
            html = (dist / 'index.html').read_text(encoding='utf-8')
            if not re.search(r'<meta\s+name="pat-ui-build"\s+content="' + re.escape(revision) + r'"\s*/?>', html):
                raise ValueError('UI manifest and HTML differ')
            return {'state': 'ready', 'revision': revision}
        except (OSError, ValueError, KeyError, TypeError):
            return {'state': 'building', 'revision': None}

    def snapshot(self, force=False):
        now = time.monotonic()
        if force or self.cached is None or now - self.checked >= 3:
            available = self.backend_revision()
            self.cached = {
                'ui': self.ui_build(),
                'backend': {'state': 'unknown' if not available or not self.loaded_backend else
                            'current' if available == self.loaded_backend else 'restart-required',
                            'loaded_revision': self.loaded_backend, 'available_revision': available},
            }
            self.checked = now
        return self.cached
