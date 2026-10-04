function installAssetPanel(options) {
  const key = "__plasticityAssetToolPanel";
  const existing = window[key];
  if (existing) {
    existing.frame.src = options.url;
    existing.frame.hidden = false;
    return { installed: true, reused: true };
  }
  const frame = document.createElement("iframe");
  let frameReady = false;
  let disconnected = false;
  let positionMode = "fixed", pointer = null, openingPoint = null;
  const trackPointer = event => {
    if (Number.isFinite(event.clientX) && Number.isFinite(event.clientY)) pointer = {x:event.clientX,y:event.clientY};
  };
  const positionPanel = () => {
    const margin = Math.min(12, innerWidth / 4, innerHeight / 4);
    const width = Math.max(1, Math.min(1000, innerWidth - margin * 2));
    const height = Math.max(1, innerHeight - Math.min(100, innerHeight / 4));
    const clamp = (value, size, available) => Math.max(margin, Math.min(value, available - size - margin));
    const anchor = openingPoint || {x:innerWidth / 2,y:innerHeight / 2};
    frame.style.right = "auto";
    frame.style.left = clamp(positionMode === "cursor" ? anchor.x - width / 2 : innerWidth - width - 20, width, innerWidth) + "px";
    frame.style.top = clamp(positionMode === "cursor" ? anchor.y - height / 2 : 70, height, innerHeight) + "px";
    frame.style.boxSizing = "border-box";
    frame.style.width = width + "px";
    frame.style.height = height + "px";
  };
  const resizePanel = () => {if (!frame.hidden) positionPanel();};
  const previewRequests = new Map();
  const offline = document.createElement("section");
  offline.hidden = true;
  offline.setAttribute("role", "alert");
  offline.style.cssText = "position:fixed;left:50%;top:24%;transform:translateX(-50%);width:min(560px,calc(100vw - 48px));padding:32px;border:2px solid #f17979;border-top:6px solid #ff8585;border-radius:14px;z-index:10001;background:#351c24;color:#ffe9e9;font:15px 'Segoe UI','Microsoft YaHei',sans-serif;box-shadow:0 20px 100px #000b";
  const heading = document.createElement("h3");
  heading.textContent = "组件库后台未连接";
  heading.style.cssText = "margin:0 0 18px;font-size:26px;font-weight:700;color:#ffaaaa";
  const detail = document.createElement("p");
  detail.textContent = "组件置入和保存暂不可用。请先启动组件库后台，再重新打开面板。";
  detail.style.cssText = "line-height:1.8;margin:0 0 24px";
  const dismiss = document.createElement("button");
  dismiss.textContent = "关闭提示";
  dismiss.style.cssText = "padding:8px 16px;border:1px solid #526786;border-radius:6px;background:#25354b;color:#e8edf5;cursor:pointer";
  dismiss.onclick = () => hide();
  offline.append(heading, detail, dismiss);
  document.body.appendChild(offline);
  frame.id = "plasticity_asset_tool_panel";
  const show = () => {
    if (disconnected) {frame.hidden = true;offline.hidden = false;return;}
    if (frame.hidden) openingPoint = pointer ? {...pointer} : null;
    positionPanel();
    offline.hidden = true;
    if (!frame.hasAttribute("src")) frame.src = options.url;
    frame.hidden = false;
    if (frameReady) {
      frame.focus();
      frame.contentWindow?.postMessage({type:"pat:shown"}, new URL(options.url).origin);
    }
  };
  frame.title = "Plasticity 模型组件库";
  frame.hidden = !!options.hidden;
  frame.style.cssText = "position:fixed;right:20px;top:70px;width:min(1000px,calc(100vw - 40px));height:calc(100vh - 100px);border:1px solid #414958;border-radius:16px;z-index:10000;box-shadow:0 20px 80px #0008;background:#10151d";
  document.body.appendChild(frame);
  if (!options.hidden) show();
  const hide = () => {
    frame.hidden = true;
    offline.hidden = true;
    if (frameReady) frame.contentWindow?.postMessage({type:"pat:hidden"}, new URL(options.url).origin);
    document.activeElement?.blur();
    window.focus();
    const canvas = document.querySelector("plasticity-viewport canvas") || document.querySelector("canvas");
    if (canvas) { if (!canvas.hasAttribute("tabindex")) canvas.tabIndex = -1; canvas.focus(); }
    return canvas;
  };
  const togglePanel = connected => {
    if (window.__plasticityAssetTransport?.calculationStatus?.()) return {visible:false, calculating:true};
    if (!frame.hidden || !offline.hidden) hide();
    else {
      if (typeof connected === "boolean") {
        const reconnect = disconnected && connected;
        disconnected = !connected;
        if (reconnect) {frameReady = false;frame.src = options.url;}
      }
      show();
    }
    return {visible: !frame.hidden || !offline.hidden, connected: !disconnected};
  };
  const toggle = event => {
    if ((event.code !== options.key && event.key !== options.key) || event.repeat || event.ctrlKey || event.altKey || event.shiftKey || event.metaKey || /INPUT|TEXTAREA|SELECT/.test(event.target?.tagName) || event.target?.isContentEditable) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    togglePanel();
  };
  const receive = event => {
    if (event.source !== frame.contentWindow || event.origin !== new URL(options.url).origin) return;
    if (event.data?.type === "pat:panel-settings") {
      const mode = event.data.settings?.position;
      if (["fixed", "cursor"].includes(mode) && mode !== positionMode) {
        positionMode = mode;
        if (!frame.hidden) positionPanel();
      }
    }
    if (event.data?.type === "pat:ready") {
      frameReady = true;
      if (!frame.hidden) show();
    }
    if (event.data?.type === "pat:show") show();
    if (["pat:hide", "pat:prepare"].includes(event.data?.type)) {
      const canvas = hide();
      if (event.data.type === "pat:prepare") {
        requestAnimationFrame(() => {
          const ready = !!canvas && document.activeElement === canvas;
          if (ready && event.data.preview) {
            const id = event.data.id;
            const timer = setTimeout(() => completePreview(id, null), 1800);
            previewRequests.set(id, {canvas, timer});
            console.log("PAT_PREVIEW_REQUEST:" + id);
          } else frame.contentWindow.postMessage({type:"pat:prepared",id:event.data.id,ready}, new URL(options.url).origin);
        });
      }
    }
  };
  document.addEventListener("keydown", toggle, true);
  window.addEventListener("message", receive);
  window.addEventListener("pointermove", trackPointer, true);
  window.addEventListener("resize", resizePanel);
  const completePreview = (id, preview) => {
    const request = previewRequests.get(id);
    if (!request) return;
    clearTimeout(request.timer);previewRequests.delete(id);
    frame.contentWindow.postMessage({type:"pat:prepared",id,ready:document.activeElement === request.canvas,preview}, new URL(options.url).origin);
  };
  window[key] = { frame, offline, hide, isVisible: () => !frame.hidden || !offline.hidden, toggle: togglePanel,
    warmup() {
      if (!disconnected && !frame.hasAttribute("src")) frame.src = options.url;
      return {loaded:frame.hasAttribute("src"),visible:!frame.hidden};
    },
    previewRect(id) {
      const request = previewRequests.get(id);
      if (!request || !frame.hidden) return null;
      const rect = request.canvas.getBoundingClientRect();
      const x = Math.max(0, Math.ceil(rect.left)), y = Math.max(0, Math.ceil(rect.top));
      const width = Math.floor(Math.min(rect.right, innerWidth) - x), height = Math.floor(Math.min(rect.bottom, innerHeight) - y);
      return width > 0 && height > 0 ? {x,y,width,height} : null;
    }, completePreview, dispose() {
    for (const request of previewRequests.values()) clearTimeout(request.timer);
    previewRequests.clear();
    document.removeEventListener("keydown", toggle, true);
    window.removeEventListener("message", receive);
    window.removeEventListener("pointermove", trackPointer, true);
    window.removeEventListener("resize", resizePanel);
    frame.remove(); offline.remove(); delete window[key];
  }};
  return { installed: true, reused: false };
}
