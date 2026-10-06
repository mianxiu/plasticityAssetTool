"""Reversible, post-load iframe hook for Plasticity's Electron main entry."""
import argparse
import json
from pathlib import Path
from .embedded_install import digest, restore

ROOT = Path(__file__).resolve().parent.parent
MARKER = '// plasticity-asset-tool:main-embedded'


def patch_main(original, script, url, key='Tab', profile=None, payload_root=None):
    payload_root = Path(payload_root) if payload_root is not None else ROOT
    source = original.decode('utf-8')
    if MARKER in source:
        raise ValueError('Main 入口已安装组件库，请先恢复备份')
    if './index.compiled.jsc' not in source:
        raise ValueError('不是预期的 Plasticity main 入口')
    options = json.dumps({'url':url, 'key':key, 'hidden':True})
    isolate = ''
    if profile:
        isolate = 'const p=' + json.dumps(str(Path(profile).resolve())) + ';require("fs").mkdirSync(p,{recursive:true});app.setPath("userData",p);app.setPath("logs",p+"/logs");'
    geometry = (payload_root/'plasticity-javascript-payloads/geometry-preload.cjs').read_text(encoding='utf-8')
    geometry += '\n' + (payload_root/'plasticity-javascript-payloads/native-transport-preload.cjs').read_text(encoding='utf-8')
    worker = (payload_root/'plasticity-javascript-payloads/geometry-worker.js').read_text(encoding='utf-8')
    worker += '\n' + (payload_root/'plasticity-javascript-payloads/native-worker.js').read_text(encoding='utf-8')
    preload_hook = '''
let geometryPreloadFile;
app.on("ready", () => {
  try {
    const source = ''' + json.dumps(geometry) + ''';
    const filename = require("path").join(app.getPath("temp"), "pat-geometry-"+require("crypto").createHash("sha256").update(source).digest("hex").slice(0,16)+".cjs");
    require("fs").writeFileSync(filename,source);
    geometryPreloadFile = filename;
    const session = require("electron").session.defaultSession;
    session.setPreloads([...session.getPreloads(),filename]);
  } catch(error) {console.error("PAT_GEOMETRY_PRELOAD",error.message);}
});
''' + worker + '\n'
    hook = MARKER + '\n;(() => {\nconst {app}=require("electron");\n' + isolate + preload_hook + '''
app.on("browser-window-created", (_event, win) => {
  // Secondary workspaces may use a different Electron session.
  if (geometryPreloadFile && win.webContents.session) {
    const session=win.webContents.session, preloads=session.getPreloads();
    if (!preloads.includes(geometryPreloadFile)) session.setPreloads([...preloads,geometryPreloadFile]);
  }
  let toggleRequest = 0, operationLocked = false;
    const probe = () => new Promise(resolve => {
      let done = false;
      const finish = value => {if (!done) {done = true;resolve(value);}};
      const check = require("http").get(new URL("/api/health", ''' + json.dumps(url) + '''), response => {
        let body = "";
        response.on("data", chunk => {body += chunk;if (body.length > 4096) {finish(false);check.destroy();}});
        response.on("end", () => {try {finish(response.statusCode === 200 && JSON.parse(body).app === "plasticity-asset-tool");} catch {finish(false);}});
        response.on("error", () => finish(false));
      });
      const timer = setTimeout(() => {finish(false);check.destroy();}, 1000);
      check.on("close", () => clearTimeout(timer));
      check.on("error", () => finish(false));
    });
  win.webContents.on("console-message", async (_event, _level, message) => {
    if (message === "PAT_OPERATION_LOCK:on" || message === "PAT_OPERATION_LOCK:off") {
      operationLocked = message.endsWith(":on");return;
    }
    if (!message.startsWith("PAT_PREVIEW_REQUEST:")) return;
    const id = message.slice("PAT_PREVIEW_REQUEST:".length);
    if (!/^[a-zA-Z0-9-]{1,64}$/.test(id) || !win.webContents.getURL().includes("/renderer/app_window/index.html")) return;
    let preview = null;
    try {
      const rect = await win.webContents.executeJavaScript("window.__plasticityAssetToolPanel?.previewRect("+JSON.stringify(id)+")");
      if (rect) {
        const image = await win.webContents.capturePage(rect);
        if (!image.isEmpty()) preview = "data:image/jpeg;base64,"+image.resize({width:512}).toJPEG(75).toString("base64");
      }
    } catch (error) {console.error("PAT_PREVIEW_ERROR",error.message);}
    if (!win.isDestroyed()) win.webContents.executeJavaScript("window.__plasticityAssetToolPanel?.completePreview("+JSON.stringify(id)+","+JSON.stringify(preview)+")").catch(()=>{});
  });
  win.webContents.on("before-input-event", (event, input) => {
    if (operationLocked) {event.preventDefault();return;}
    if (input.key === ''' + json.dumps(key) + ''' || input.code === ''' + json.dumps(key) + ''') console.log("PAT_EMBED_INPUT", JSON.stringify(input));
    if (!["keyDown","rawKeyDown"].includes(input.type) || (input.code !== ''' + json.dumps(key) + ''' && input.key !== ''' + json.dumps(key) + ''') || input.control || input.shift || input.alt || input.meta) return;
    const address = win.webContents.getURL();
    if (!address.includes("/renderer/app_window/index.html")) return;
    event.preventDefault();
    if (input.isAutoRepeat) return;
    const request = ++toggleRequest;
    win.webContents.executeJavaScript("window.__plasticityAssetToolPanel?.isVisible()")
      .then(async visible => {
        const connected = visible ? true : await probe();
        if (request !== toggleRequest || win.isDestroyed()) return;
        return win.webContents.executeJavaScript("window.__plasticityAssetToolPanel?.toggle("+JSON.stringify(connected)+")");
      })
      .then(result => console.log("PAT_EMBED_TOGGLE", JSON.stringify(result)))
      .catch(error => console.error("PAT_EMBED_ERROR", error.message));
  });
  win.webContents.on("did-finish-load", async () => {
    operationLocked = false;
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
      const geometryReady = await win.webContents.executeJavaScript("typeof window.__plasticityAssetGeometry?.convert === 'function'");
      if (geometryReady) startGeometryWorker(win, options.url, "hwnd:"+hwnd);
      const nativeReady = await win.webContents.executeJavaScript("typeof window.__plasticityAssetTransport?.captureSelection === 'function'");
      if (nativeReady) startNativeWorker(win, options.url, "hwnd:"+hwnd);
      // Prepare the hidden iframe only after the renderer is initialized and
      // the local service identity is confirmed. Never focus it during warmup.
      setTimeout(async () => {
        if (win.isDestroyed() || !await probe() || win.isDestroyed()) return;
        win.webContents.executeJavaScript("window.__plasticityAssetToolPanel?.warmup()")
          .catch(()=>{});
      }, 500);
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


def upgrade(target, previous_backup, backup, base_backup=None):
    """Replace only an exact, previously verified installation; retain rollback."""
    target, previous_backup, backup = Path(target).resolve(), Path(previous_backup).resolve(), Path(backup).resolve()
    saved = json.loads(previous_backup.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    original, current = previous_backup.read_bytes(), target.read_bytes()
    if target.name != 'index.js' or target.parent.name != 'main' or str(target) != saved['target']:
        raise ValueError('目标与备份不匹配')
    if digest(original) != saved['original_sha256'] or digest(current) != saved['patched_sha256']:
        raise ValueError('已安装入口或备份发生变化，停止升级')
    if base_backup:
        base_backup = Path(base_backup).resolve()
        base_saved = json.loads(base_backup.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        base = base_backup.read_bytes()
        if base_saved['target'] != str(target) or digest(base) != base_saved['original_sha256'] or not original.endswith(base):
            raise ValueError('原始入口备份不匹配')
        original = base
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    patched = patch_main(original, (ROOT/'plasticity-javascript-payloads/init.js').read_text(encoding='utf-8'),
                         f'http://127.0.0.1:{config["server"]["http_port"]}/?embedded=1',
                         config['keymap'].get('show_panel_event_key_code', 'Tab'))
    manifest = {'target':str(target), 'original_sha256':digest(current), 'patched_sha256':digest(patched)}
    if backup.exists() or backup.with_suffix('.manifest.json').exists():
        if backup.read_bytes() != current or json.loads(backup.with_suffix('.manifest.json').read_text(encoding='utf-8')) != manifest:
            raise ValueError('升级回滚备份不匹配')
    else:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(current)
        backup.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    target.write_bytes(patched)
    if target.read_bytes() != patched:
        raise RuntimeError('升级写入校验失败')
    return manifest


def validate_managed(target, expected_sha256, allow_unverified_version=False, restoring=False):
    from .discovery import inspect_directory, assert_closed, SUPPORTED_VERSIONS
    target = Path(target).resolve()
    if len(target.parents) < 5:
        raise ValueError('后台安装缺少有效目标入口')
    row = inspect_directory(target.parents[4])
    if Path(row['target']) != target or (row['version'] not in SUPPORTED_VERSIONS and not allow_unverified_version and not restoring):
        raise ValueError('此版本尚未验证自动安装')
    if not expected_sha256 or digest(target.read_bytes()) != expected_sha256:
        raise ValueError('入口在检测后发生变化，请重新检测')
    assert_closed(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target')
    parser.add_argument('--backup', required=True)
    parser.add_argument('--profile')
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--upgrade-from',help='经过验证的原始 main 备份路径')
    parser.add_argument('--base-backup',help='多次升级时使用的最初未修改入口备份')
    parser.add_argument('--managed', action='store_true', help='后台管理安装：重新检查版本、进程及入口摘要')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--allow-unverified-version', action='store_true', help='Explicitly opt in to testing an unverified Plasticity version')
    args = parser.parse_args()
    if args.managed:
        if not args.target:
            raise ValueError('后台安装缺少目标入口')
        validate_managed(args.target, args.expected_sha256, args.allow_unverified_version, args.restore)
    if args.restore:
        restore(args.backup)
        print('已恢复原始 main 入口')
    elif args.target:
        print(json.dumps(upgrade(args.target,args.upgrade_from,args.backup,args.base_backup) if args.upgrade_from else install(args.target,args.backup,args.profile)))
    else:
        parser.error('安装需要 --target')
