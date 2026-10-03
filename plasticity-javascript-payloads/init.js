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
  frame.id = "plasticity_asset_tool_panel";
  const show = () => {
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
    document.activeElement?.blur();
    window.focus();
    const canvas = document.querySelector("plasticity-viewport canvas") || document.querySelector("canvas");
    if (canvas) { if (!canvas.hasAttribute("tabindex")) canvas.tabIndex = -1; canvas.focus(); }
    return canvas;
  };
  const togglePanel = () => {
    if (frame.hidden) show(); else hide();
    return {visible: !frame.hidden};
  };
  const toggle = event => {
    if ((event.code !== options.key && event.key !== options.key) || event.repeat || event.ctrlKey || event.altKey || event.shiftKey || event.metaKey || /INPUT|TEXTAREA|SELECT/.test(event.target?.tagName) || event.target?.isContentEditable) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    togglePanel();
  };
  const receive = event => {
    if (event.source !== frame.contentWindow || event.origin !== new URL(options.url).origin) return;
    if (event.data?.type === "pat:ready") {
      frameReady = true;
      if (!frame.hidden) show();
    }
    if (event.data?.type === "pat:show") show();
    if (["pat:hide", "pat:prepare"].includes(event.data?.type)) {
      const canvas = hide();
      if (event.data.type === "pat:prepare") {
        requestAnimationFrame(() => frame.contentWindow.postMessage({type:"pat:prepared",id:event.data.id,ready:!!canvas && document.activeElement === canvas}, new URL(options.url).origin));
      }
    }
  };
  document.addEventListener("keydown", toggle, true);
  window.addEventListener("message", receive);
  window[key] = { frame, toggle: togglePanel, dispose() {
    document.removeEventListener("keydown", toggle, true);
    window.removeEventListener("message", receive);
    frame.remove(); delete window[key];
  }};
  return { installed: true, reused: false };
}
