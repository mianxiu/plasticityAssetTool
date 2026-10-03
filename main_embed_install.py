"""Reversible, post-load iframe hook for Plasticity's Electron main entry."""
import argparse
import json
from pathlib import Path
from embedded_install import digest, restore

ROOT = Path(__file__).resolve().parent
MARKER = '// plasticity-asset-tool:main-embedded'


def patch_main(original, script, url, key='Tab', profile=None):
    source = original.decode('utf-8')
    if MARKER in source:
        raise ValueError('Main 入口已安装组件库，请先恢复备份')
    if './index.compiled.jsc' not in source:
        raise ValueError('不是预期的 Plasticity main 入口')
    options = json.dumps({'url':url, 'key':key, 'hidden':True})
    isolate = ''
    if profile:
        isolate = 'const p=' + json.dumps(str(Path(profile).resolve())) + ';require("fs").mkdirSync(p,{recursive:true});app.setPath("userData",p);app.setPath("logs",p+"/logs");'
    hook = MARKER + '\n;(() => {\nconst {app}=require("electron");\n' + isolate + '''
app.on("browser-window-created", (_event, win) => {
  win.webContents.on("before-input-event", (event, input) => {
    if (input.key === ''' + json.dumps(key) + ''' || input.code === ''' + json.dumps(key) + ''') console.log("PAT_EMBED_INPUT", JSON.stringify(input));
    if (!["keyDown","rawKeyDown"].includes(input.type) || (input.code !== ''' + json.dumps(key) + ''' && input.key !== ''' + json.dumps(key) + ''') || input.control || input.shift || input.alt || input.meta) return;
    const address = win.webContents.getURL();
    if (!address.includes("/renderer/app_window/index.html")) return;
    event.preventDefault();
    if (input.isAutoRepeat) return;
    win.webContents.executeJavaScript("window.__plasticityAssetToolPanel?.toggle()")
      .then(result => console.log("PAT_EMBED_TOGGLE", JSON.stringify(result)))
      .catch(error => console.error("PAT_EMBED_ERROR", error.message));
  });
  win.webContents.on("did-finish-load", async () => {
    try {
      const address = new URL(win.webContents.getURL());
      if (address.protocol !== "file:" || !decodeURIComponent(address.pathname).endsWith("/renderer/app_window/index.html")) return;
      const handle = win.getNativeWindowHandle();
      const hwnd = handle.length === 8 ? Number(handle.readBigUInt64LE()) : handle.readUInt32LE();
      const options = ''' + options + ''';
      const panelURL = new URL(options.url);
      panelURL.searchParams.set("target", "hwnd:"+hwnd);
      options.url = panelURL.href;
      const result = await win.webContents.executeJavaScript("("+''' + json.dumps(script) + '''+")("+JSON.stringify(options)+")");
      console.log("PAT_EMBED_READY", hwnd, JSON.stringify(result));
    } catch (error) { console.error("PAT_EMBED_ERROR", error.stack || error.message); }
  });
});
})();
'''
    return hook.encode('utf-8') + original


def install(target, backup, profile=None):
    target, backup = Path(target).resolve(), Path(backup).resolve()
    if target.name != 'index.js' or target.parent.name != 'main':
        raise ValueError('只允许修改 .webpack/main/index.js')
    original = target.read_bytes()
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    patched = patch_main(original, (ROOT/'plasticity-javascript-payloads/init.js').read_text(encoding='utf-8'),
                         f'http://127.0.0.1:{config["server"]["http_port"]}/?embedded=1',
                         config['keymap'].get('show_panel_event_key_code','Tab'), profile)
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
        raise RuntimeError('Main 写入校验失败')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target')
    parser.add_argument('--backup', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--restore',action='store_true')
    args = parser.parse_args()
    if args.restore:
        restore(args.backup)
        print('已恢复原始 main 入口')
    elif args.target:
        print(json.dumps(install(args.target,args.backup,args.profile)))
    else:
        parser.error('安装需要 --target')
