// Production UI updates reload this library document, never its CAD parent.
export function createUpdateController({currentRevision, loadBuild, canReload, beforeReload = () => {}, reload}) {
  let checking = false, disposed = false, reloading = false;
  return {
    async check() {
      if (checking || disposed || reloading) return;
      checking = true;
      try {
        const build = await loadBuild();
        if (!disposed && build?.ready && build.revision !== currentRevision && canReload()) {
          beforeReload();
          // beforeReload is synchronous so no new interaction can race this guard.
          if (!disposed && canReload()) {reloading = true; reload();}
        }
      } catch { /* Offline or partially written builds are retried, never reloaded. */ }
      finally {checking = false;}
    },
    stop() {disposed = true;},
  };
}

const stateKey = () => `pat.ui-reload:${location.pathname}${location.search}`;
export function takeUiReloadState() {
  try {
    const key = stateKey(), raw = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    const value = JSON.parse(raw);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch {return {};}
}
export function saveUiReloadState(value) {
  try {sessionStorage.setItem(stateKey(), JSON.stringify(value));} catch {}
}

export function installUiUpdates({canReload, beforeReload}) {
  // Vite's native HMR owns development mode; only built pages use this watcher.
  if (import.meta.env.DEV) return () => {};
  let lastInteraction = Date.now();
  const pointers = new Set(), keys = new Set(), abort = new AbortController();
  const activity = event => {
    lastInteraction = Date.now();
    if (event.type === 'pointerdown') pointers.add(event.pointerId);
    if (['pointerup','pointercancel'].includes(event.type)) pointers.delete(event.pointerId);
    if (event.type === 'keydown') keys.add(event.code);
    if (event.type === 'keyup') keys.delete(event.code);
  };
  const blur = () => {pointers.clear(); keys.clear(); lastInteraction = Date.now();};
  const events = ['pointerdown','pointerup','pointercancel','keydown','keyup','input','change','wheel'];
  for (const event of events) window.addEventListener(event, activity, {capture:true,passive:true});
  window.addEventListener('blur', blur);
  const request = (url, options = {}) => fetch(url, {
    ...options, cache:'no-store', signal:AbortSignal.any([abort.signal, AbortSignal.timeout(5000)]),
  });
  const controller = createUpdateController({
    currentRevision: __PAT_UI_BUILD__,
    canReload: () => !document.hidden && !pointers.size && !keys.size && Date.now()-lastInteraction >= 800 && canReload(),
    beforeReload,
    reload: () => window.location.reload(),
    async loadBuild() {
      const response = await request(`/ui-build.json?check=${Date.now()}`);
      if (!response.ok) return null;
      const build = await response.json();
      if (typeof build.revision !== 'string' || build.revision === __PAT_UI_BUILD__) return null;
      if (!Array.isArray(build.assets) || !build.assets.length || build.assets.some(name =>
        typeof name !== 'string' || !/^assets\/[A-Za-z0-9_./-]+\.(js|css)$/.test(name) || name.includes('..'))) return null;
      const html = await request(`/index.html?check=${Date.now()}`);
      if (!html.ok) return null;
      const page = new DOMParser().parseFromString(await html.text(), 'text/html');
      if (page.querySelector('meta[name="pat-ui-build"]')?.content !== build.revision) return null;
      const available = await Promise.all(build.assets.map(async name => {
        const asset = await request(`/${name}`, {method:'HEAD'});
        const type = asset.headers.get('content-type') || '';
        return asset.ok && (name.endsWith('.css') ? type.includes('text/css') : /(?:java|ecma)script/.test(type));
      }));
      return {...build, ready:available.every(Boolean)};
    },
  });
  const timer = setInterval(() => controller.check(), 3000);
  return () => {
    controller.stop(); abort.abort(); clearInterval(timer);
    for (const event of events) window.removeEventListener(event, activity, true);
    window.removeEventListener('blur', blur);
  };
}
