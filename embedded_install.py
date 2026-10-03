"""Reversible HTML iframe integration for a user-selected Plasticity install."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = '<!-- plasticity-asset-tool:embedded -->'


def patch_html(original, script, url, key='Tab'):
    text = original.decode('utf-8')
    if MARKER in text:
        raise ValueError('HTML 已安装组件库，请先恢复备份')
    if '</body>' not in text or 'id="root"' not in text:
        raise ValueError('不是预期的 Plasticity HTML 入口，停止修改')
    options = json.dumps({'url':url, 'key':key, 'hidden':True})
    payload = MARKER + '\n<script>\n' + script.replace('</script', '<\\/script') + '\n;window.addEventListener("load", () => installAssetPanel(' + options + '), {once:true});\n</script>\n'
    return text.replace('</body>', payload + '</body>', 1).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def install(target, backup):
    target, backup = Path(target).resolve(), Path(backup).resolve()
    if target.name != 'index.html' or target.parent.name != 'app_window':
        raise ValueError('只允许修改 app_window/index.html')
    original = target.read_bytes()
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    url = f'http://127.0.0.1:{config["server"]["http_port"]}/?embedded=1'
    patched = patch_html(original, (ROOT/'plasticity-javascript-payloads/init.js').read_text(encoding='utf-8'), url, config['keymap'].get('show_panel_event_key_code', 'Tab'))
    manifest = {'target':str(target), 'original_sha256':digest(original), 'patched_sha256':digest(patched)}
    if backup.exists() or backup.with_suffix('.manifest.json').exists():
        saved = json.loads(backup.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        if saved != manifest or backup.read_bytes() != original:
            raise ValueError('已有备份与当前文件不同，请使用新的备份路径')
    else:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original)
        backup.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    target.write_bytes(patched)
    if target.read_bytes() != patched:
        raise RuntimeError('HTML 写入校验失败')
    return manifest


def restore(backup):
    backup = Path(backup).resolve()
    manifest = json.loads(backup.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    target, original = Path(manifest['target']), backup.read_bytes()
    if digest(original) != manifest['original_sha256']:
        raise ValueError('备份校验失败')
    current = digest(target.read_bytes())
    if current == manifest['original_sha256']:
        return
    if current != manifest['patched_sha256']:
        raise ValueError('安装文件在补丁后发生变化，停止恢复以免覆盖其他修改')
    target.write_bytes(original)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target')
    parser.add_argument('--backup', required=True)
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--result')
    args = parser.parse_args()
    if args.restore:
        restore(args.backup)
        print('已恢复原始 HTML')
    elif args.target:
        result = install(args.target,args.backup)
        if args.result:
            Path(args.result).write_text(json.dumps(result),encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
    else:
        parser.error('安装需要 --target')
