import { createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js";
import { WebsocketClient } from "./Websocketclient";

function Cube(props) {
  return <svg viewBox="0 0 80 80" fill="none" aria-hidden="true" class={props.class || "cube-icon"}>
    <path d="M40 9 68 25v31L40 72 12 56V25L40 9Z" fill="currentColor" fill-opacity=".08" stroke="currentColor" stroke-width="1.5"/>
    <path d="m12 25 28 16 28-16M40 41v31M26 17l28 16v31" stroke="currentColor" stroke-width="1.5"/>
  </svg>;
}

export function Home() {
  const api = location.origin;
  const wsUrl = (import.meta.env.DEV ? "http://127.0.0.1:15150" : api).replace(/^http/, "ws") + "/websocket";
  const embedded = window.parent !== window;
  const quickPanel = new URLSearchParams(location.search).has("quick");
  const [floatingPanel, setFloatingPanel] = createSignal(embedded || new URLSearchParams(location.search).get("panel") === "1");
  const pendingHost = new Map();
  const hostOrigin = document.referrer.startsWith("file:") || !document.referrer ? "*" : new URL(document.referrer).origin;
  function hidePanel() {
    if (embedded) window.parent.postMessage({type:"pat:hide"}, hostOrigin);
    else operate("panel.dismiss", {});
  }
  function hostMessage(event) {
    if (!embedded || event.source !== window.parent) return;
    if (event.data?.type === "pat:shown") focusSearch();
    if (event.data?.type === "pat:prepared") pendingHost.get(event.data.id)?.(event.data.ready);
  }
  function prepareHost() {
    if (!embedded) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const id = crypto.randomUUID();
      const timeout = setTimeout(() => {pendingHost.delete(id); reject(new Error("内嵌面板未能交回视口焦点，请重新唤起后重试"));}, 1500);
      pendingHost.set(id, ready => {clearTimeout(timeout);pendingHost.delete(id);ready ? resolve() : reject(new Error("Plasticity 视口尚未加载"));});
      window.parent.postMessage({type:"pat:prepare",id}, hostOrigin);
    });
  }
  const preferredTarget = new URLSearchParams(location.search).get("target");
  const [status, setStatus] = createSignal("connecting");
  const [assets, setAssets] = createSignal([]);
  const [libraries, setLibraries] = createSignal([]);
  const [libraryId, setLibraryId] = createSignal("default");
  const [folders, setFolders] = createSignal([]);
  const [formFolders, setFormFolders] = createSignal([]);
  const [foldersLoading, setFoldersLoading] = createSignal(false);
  const [folderId, setFolderId] = createSignal(null);
  const [kind, setKind] = createSignal("all");
  const [organizationDialog, setOrganizationDialog] = createSignal(null);
  const [organizationName, setOrganizationName] = createSignal("");
  const [launcherNote, setLauncherNote] = createSignal("");
  const [targets, setTargets] = createSignal([]);
  const [targetId, setTargetId] = createSignal(preferredTarget || "");
  const [note, setNote] = createSignal("");
  const [clipboardSupported, setClipboardSupported] = createSignal(false);
  const [query, setQuery] = createSignal("");
  const [category, setCategory] = createSignal("全部组件");
  const [archived, setArchived] = createSignal(false);
  const [selectedId, setSelectedId] = createSignal("");
  const [busy, setBusy] = createSignal(false);
  const [notice, setNotice] = createSignal(null);
  const [placementHint, setPlacementHint] = createSignal(false);
  const [dialog, setDialog] = createSignal(null);
  const [form, setForm] = createSignal({ name: "", category: "", tags: "", note: "", preview: "" });
  const [copySelection, setCopySelection] = createSignal(false);
  let importInput;
  let searchInput;
  let poll;
  let refreshPending = false;
  let refreshQueued = false;

  const selected = createMemo(() => assets().find(asset => asset.id === selectedId()));
  const target = createMemo(() => targets().find(item => item.id === targetId()));
  const categories = createMemo(() => [...new Set(assets().map(asset => asset.category))].sort());
  const kindNames = {solid:"Solid · 实体",curve:"Curve · 曲线",mixed:"混合组件",unknown:"未标注"};
  const currentLibrary = createMemo(() => libraries().find(item => item.id === libraryId()));
  const childFolders = createMemo(() => folders().filter(item => item.parent_id === folderId()));
  const orderedFolders = createMemo(() => {
    const rows = [];
    const visit = parent => { for(const item of folders().filter(row => row.parent_id === parent)) { rows.push(item); visit(item.id); } };
    visit(null); return rows;
  });
  const folderPath = (id, rows = folders()) => {
    const path = [];
    let item = rows.find(row => row.id === id);
    while (item && path.length < rows.length) { path.unshift(item); item = rows.find(row => row.id === item.parent_id); }
    return path;
  };
  const folderLabel = (id, rows = folders()) => folderPath(id, rows).map(item => item.name).join(" / ") || "库根目录";
  const filtered = createMemo(() => assets().filter(asset => {
    const text = [asset.name, asset.category, asset.tags, asset.note, folderLabel(asset.folder_id)].join(" ").toLowerCase();
    return (query().trim() || asset.folder_id === folderId()) && (kind() === "all" || asset.kind === kind()) && (category() === "全部组件" || asset.category === category()) && text.includes(query().trim().toLowerCase());
  }));
  const ready = () => status() === "connected" && !busy();
  const canInsert = () => ready() && !!target() && clipboardSupported() && !archived();
  const setField = (key, value) => setForm(current => ({ ...current, [key]: value }));
  const previewUrl = asset => `${api}/api/assets/${asset.id}/preview?v=${encodeURIComponent(asset.updated_at || asset.created_at)}`;
  const showNotice = (message, error = false) => setNotice({ message, error });

  const client = new WebsocketClient(wsUrl, value => {
    setStatus(value);
  }, event => {
    if (event.type === "connected" || event.type === "library_changed") refresh().catch(error => showNotice(error.message, true));
    if (event.type === "launcher_error") showNotice(event.message, true);
    if (event.type === "quick_launch") {
      if (event.target_id && targets().some(item => item.id === event.target_id)) setTargetId(event.target_id);
      focusSearch();
    }
  });

  async function refresh() {
    if (!ready() || refreshPending) { refreshQueued = true; return; }
    refreshPending = true;
    try {
      const requestedLibrary = libraryId();
      const requestedArchive = archived();
      const state = await client.request("state", { library_id: requestedLibrary });
      if (requestedLibrary !== libraryId() || requestedArchive !== archived()) { refreshQueued = true; return; }
      setLibraries(state.libraries || []);
      setFolders(state.folders || []);
      setLauncherNote(embedded ? "Tab 打开 / 关闭 · Esc 收起 · Ctrl+K 搜索" : state.launcher?.message || "Ctrl+K 搜索");
      if (quickPanel) setFloatingPanel(!!state.launcher?.frameless);
      if (folderId() && !state.folders?.some(item => item.id === folderId())) setFolderId(null);
      setTargets(state.targets);
      setNote(state.connection_note);
      setClipboardSupported(state.clipboard_supported);
      if (!state.targets.some(item => item.id === targetId())) {
        setTargetId(state.targets.length === 1 ? state.targets[0].id : "");
      }
      const rows = requestedArchive ? await client.request("library.list", { archived: true, library_id: requestedLibrary }) : state.assets;
      if (requestedLibrary !== libraryId() || requestedArchive !== archived()) { refreshQueued = true; return; }
      setAssets(rows);
      if (!rows.some(asset => asset.id === selectedId())) setSelectedId("");
    } finally {
      refreshPending = false;
      if (refreshQueued && ready()) { refreshQueued = false; queueMicrotask(() => refresh().catch(error => showNotice(error.message, true))); }
    }
  }

  function focusSearch() { if (dialog() || organizationDialog()) return; queueMicrotask(() => { searchInput?.focus(); searchInput?.select(); }); }
  async function changeFormLibrary(id) {
    setForm(current => ({...current,library_id:id,folder_id:null})); setFormFolders([]); setFoldersLoading(true);
    try {
      const rows = await client.request("folder.list", {library_id:id});
      if(form().library_id === id) setFormFolders(rows);
    } catch(error) {showNotice(error.message,true);}
    finally {if(form().library_id === id) setFoldersLoading(false);}
  }
  function onSearchKey(event) {
    if (embedded && (event.code === "Tab" || event.key === "Tab") && !event.repeat && !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey) {
      event.preventDefault();
      hidePanel();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); focusSearch(); }
    if (event.key === "Escape" && floatingPanel() && !dialog() && !organizationDialog() && ready()) {
      event.preventDefault();
      hidePanel();
    }
  }
  async function switchLibrary(id) {
    if (busy()) return;
    setLibraryId(id); setAssets([]); setFolders([]); setFolderId(null); setSelectedId(""); setArchived(false); setCategory("全部组件"); setQuery(""); setKind("all"); await refresh();
  }
  function enterFolder(id) { setFolderId(id); setSelectedId(""); setCategory("全部组件"); setQuery(""); }
  function openOrganization(type) {
    setOrganizationDialog(type);
    setOrganizationName(type === "rename-library" ? currentLibrary()?.name || "" : type === "rename-folder" ? folders().find(item => item.id === folderId())?.name || "" : "");
  }
  async function saveOrganization(event) {
    event.preventDefault();
    const type = organizationDialog();
    const action = {library:"collection.create","rename-library":"collection.rename",folder:"folder.create","rename-folder":"folder.rename"}[type];
    const result = await operate(action, {name:organizationName(), id:type === "rename-library" ? libraryId() : folderId(), library_id:libraryId(), parent_id:folderId()}, "已保存");
    if (result) { setOrganizationDialog(null); if(type === "library") await switchLibrary(result.id); else await refresh(); }
  }

  async function operate(action, args = {}, success) {
    if (!ready()) return;
    setBusy(true);
    setNotice(null);
    try {
      if (embedded && (action === "asset.insert" || action === "target.command" || (action === "library.capture" && args.copy_selection))) await prepareHost();
      const result = await client.request(action, args);
      showNotice(success || result?.message || "操作完成");
      return result;
    } catch (error) {
      showNotice(error.message, true);
      if (embedded) window.parent.postMessage({type:"pat:show"}, hostOrigin);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function insert(asset, placement = true) {
    setSelectedId(asset.id);
    const result = await operate("asset.insert", { id: asset.id, target_id: targetId(), placement });
    if (result) setPlacementHint(placement);
    if (result && embedded) hidePanel();
  }
  async function command(value) {
    const result = await operate("target.command", { target_id: targetId(), command: value });
    if (result && embedded) hidePanel();
  }
  function openCapture() {
    setFormFolders(folders()); setFoldersLoading(false);
    setForm({ name: "", category: category() === "全部组件" ? "" : category(), tags: "", note: "", preview: "", library_id:libraryId(),folder_id:folderId(),kind:kind() === "all" ? "unknown" : kind() });
    setCopySelection(false);
    setDialog("capture");
  }
  function openEdit() {
    setFormFolders(folders()); setFoldersLoading(false);
    const asset = selected();
    setForm({ name: asset.name, category: asset.category, tags: asset.tags, note: asset.note, preview: undefined,library_id:asset.library_id,folder_id:asset.folder_id,kind:asset.kind });
    setDialog("edit");
  }
  async function save(event) {
    event.preventDefault();
    const result = await operate(dialog() === "edit" ? "library.update" : "library.capture", {
      ...form(), id: selectedId(), target_id: targetId(), copy_selection: copySelection(),
    }, dialog() === "edit" ? "组件信息已更新" : "组件已保存，可重复置入");
    if (result) {
      if (dialog() === "capture") { setArchived(false); setCategory("全部组件"); setQuery(""); }
      setDialog(null);
      if (result.library_id !== libraryId()) await switchLibrary(result.library_id);
      enterFolder(result.folder_id); setKind("all"); setSelectedId(result.id); await refresh();
    }
  }
  async function readPreview(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.type !== "image/jpeg" || file.size > 5 * 1024 * 1024) {
      showNotice("请选择小于 5 MB 的 JPEG 预览图", true); event.target.value = ""; return;
    }
    const reader = new FileReader();
    reader.onload = () => setField("preview", reader.result);
    reader.readAsDataURL(file);
  }
  async function importPackage(event) {
    const file = event.target.files?.[0];
    if (!file || !ready()) return;
    setBusy(true);
    try {
      const body = new FormData(); body.append("file", file); body.append("library_id",libraryId()); body.append("folder_id",folderId() || "");
      const response = await fetch(api + "/api/import", { method: "POST", body });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "导入失败");
      setArchived(false); setCategory("全部组件"); setQuery(""); setSelectedId(result.data.id);
      showNotice("组件包已导入");
    } catch (error) { showNotice(error.message, true); }
    finally { setBusy(false); event.target.value = ""; await refresh(); }
  }
  async function toggleArchive(value) {
    setArchived(value); setCategory("全部组件"); setSelectedId(""); await refresh();
  }
  async function archiveSelected() {
    const result = await operate(archived() ? "library.restore" : "library.archive", { id: selectedId() }, archived() ? "组件已恢复" : "组件已归档，可在归档中恢复");
    if (result) await refresh();
  }

  onMount(() => {
    client.connect();
    poll = setInterval(() => { if (ready()) refresh().catch(() => {}); }, 10000);
    window.addEventListener("keydown",onSearchKey);
    window.addEventListener("message",hostMessage);
    if (embedded) window.parent.postMessage({type:"pat:ready"}, hostOrigin);
    if (new URLSearchParams(location.search).has("quick")) focusSearch();
  });
  onCleanup(() => { clearInterval(poll); client.disconnect(); window.removeEventListener("keydown",onSearchKey);window.removeEventListener("message",hostMessage); });

  return <div class={floatingPanel() ? "app-shell floating-panel" : "app-shell"}>
    <aside class="sidebar">
      <div class="brand"><Cube /><div><strong>Plasticity</strong><span>COMPONENT LIBRARY</span></div></div>
      <div class="sidebar-label">模型组件库</div>
      <button class={!archived() ? "nav-item active" : "nav-item"} onClick={() => toggleArchive(false)}>◇ 全部组件 <span>{!archived() ? assets().length : ""}</span></button>
      <div class="sidebar-label category-label">{currentLibrary()?.name || "资产库"} · 分组</div>
      <button class={!folderId() ? "nav-item active" : "nav-item"} onClick={() => enterFolder(null)}>⌂ 库根目录</button>
      <div class="folder-tree"><For each={orderedFolders()}>{item => <button class={folderId() === item.id ? "folder-nav active" : "folder-nav"} style={{"padding-left":`${10 + (folderPath(item.id).length-1)*12}px`}} onClick={() => enterFolder(item.id)} title={folderLabel(item.id)}>▱ {item.name}</button>}</For></div>
      <div class="sidebar-label category-label">分类</div>
      <For each={categories()}>{name => <button class={!archived() && category() === name ? "nav-item category active" : "nav-item category"} onClick={() => setCategory(name)}>▦ {name}<span>{assets().filter(asset => asset.category === name).length}</span></button>}</For>
      <button class={archived() ? "nav-item active archive-link" : "nav-item archive-link"} onClick={() => toggleArchive(true)}>▧ 已归档</button>
      <div class="sidebar-bottom"><span class={status() === "connected" ? "status-dot online" : "status-dot"}/><span>{status() === "connected" ? "本地服务已连接" : status() === "connecting" ? "连接服务中…" : "服务断开，正在重连"}</span></div>
    </aside>

    <main class="main-content">
      <header class="page-header"><div><div class="eyebrow">YOUR REUSABLE GEOMETRY</div><h1>{archived() ? "已归档" : "模型组件库"}</h1><p>保存一次，随时置入。在 Plasticity 里继续创作。</p></div>
        <div class="header-actions"><button class="secondary" disabled={!ready()} onClick={() => importInput.click()}>↓ 导入组件包</button><button class="primary" disabled={!ready() || !clipboardSupported()} onClick={openCapture}>＋ 保存组件</button><Show when={floatingPanel()}><button class="panel-dismiss" aria-label="收起面板" title="Esc 收起" disabled={!ready()} onClick={hidePanel}>×</button></Show></div>
      </header>
      <input ref={importInput} class="hidden-input" type="file" accept=".patasset" onChange={importPackage}/>

      <section class="target-bar" aria-label="目标窗口"><div class="target-label"><span class="small-square">↗</span><div><strong>置入目标</strong><span>{target()?.mode === "cdp" ? "调试接口 · 可嵌入面板" : "原生剪贴板 · Ctrl+Shift+V"}</span></div></div>
        <select aria-label="Plasticity 目标窗口" onChange={event => setTargetId(event.currentTarget.value)} disabled={busy()}><option value="" selected={!targetId()}>{targets().length ? "请选择 Plasticity 窗口" : "未发现 Plasticity 窗口"}</option><For each={targets()}>{item => <option value={item.id} selected={targetId() === item.id}>{item.title} · {item.mode === "cdp" ? "CDP" : "原生"} · {item.target_id?.slice(0, 6) || item.hwnd}</option>}</For></select>
        <button class="icon-button" aria-label="刷新窗口" disabled={!ready()} onClick={() => refresh().catch(error => showNotice(error.message, true))}>↻</button>
        <Show when={target()?.mode === "cdp"}><button class="secondary" disabled={!ready()} onClick={() => operate("target.embed", { target_id: targetId() }, "面板已嵌入，按反引号键切换显示")}>嵌入面板</button></Show>
        <Show when={embedded}><button class="secondary" onClick={hidePanel}>收起</button></Show>
      </section>

      <nav class="library-tabs" aria-label="资产库"><For each={libraries()}>{item => <button class={libraryId() === item.id ? "library-tab active" : "library-tab"} aria-pressed={libraryId() === item.id} disabled={busy()} onClick={() => switchLibrary(item.id)}>{item.name}<span>{item.count}</span></button>}</For><button class="library-tab add-library" disabled={!ready()} onClick={() => openOrganization("library")}>＋ 新建库</button></nav>
      <div class="folder-toolbar"><nav class="breadcrumbs" aria-label="分组路径"><button onClick={() => enterFolder(null)}>{currentLibrary()?.name || "资产库"}</button><For each={folderPath(folderId())}>{item => <><span> / </span><button onClick={() => enterFolder(item.id)}>{item.name}</button></>}</For></nav><div><button disabled={!ready()} onClick={() => openOrganization("rename-library")}>重命名库</button><Show when={folderId()}><button disabled={!ready()} onClick={() => openOrganization("rename-folder")}>重命名分组</button></Show><button disabled={!ready()} onClick={() => openOrganization("folder")}>＋ 新建分组</button></div></div>

      <Show when={placementHint()}><section class="placement-guide" aria-label="置入操作提示"><div><strong>在 Plasticity 视口完成置入</strong><p>先点击定位，再按 <kbd>S</kbd> 缩放、<kbd>A</kbd> 调整角度、<kbd>D</kbd> 偏移；<kbd>F</kbd> 翻转，<kbd>X / Y / Z</kbd> 设置朝向。数值调整按 Enter 确认，再按 Enter 置入。可继续定位重复置入，按 Esc 退出。</p></div><button class="icon-button" aria-label="关闭置入操作提示" onClick={() => setPlacementHint(false)}>×</button></section></Show>

      <Show when={notice()}><div class={notice().error ? "notice error" : "notice"} role={notice().error ? "alert" : "status"}><span>{notice().message}</span><button aria-label="关闭提示" onClick={() => setNotice(null)}>×</button></div></Show>
      <Show when={!target()}><div class="connection-hint">先打开 Plasticity，并选择要置入的模型窗口。组件库可以保持打开。</div></Show>

      <div class="library-toolbar"><div class="section-name">{category()}<span>{filtered().length} 个组件</span></div><label class="search-field"><span>⌕</span><input ref={searchInput} aria-label="搜索组件" placeholder="搜索此库 · Ctrl+K" title="Enter 置入第一项搜索结果" value={query()} onInput={event => setQuery(event.currentTarget.value)} onKeyDown={event => { if(event.key === "Enter" && filtered().length && canInsert()) {event.preventDefault();insert(filtered()[0]);} }}/></label></div>
      <div class="type-tabs" aria-label="组件类型"><For each={[["all","全部"],["solid","Solid"],["curve","Curve"],["mixed","混合"],["unknown","未标注"]]}>{item => <button class={kind() === item[0] ? "active" : ""} aria-pressed={kind() === item[0]} onClick={() => {setKind(item[0]);setSelectedId("");}}>{item[1]}</button>}</For><span>类型由保存时标注</span></div>
      <Show when={!query().trim() && !archived() && childFolders().length}><section class="folder-grid" aria-label="子分组"><For each={childFolders()}>{item => <button class="folder-card" onClick={() => enterFolder(item.id)}><span>▱</span><strong>{item.name}</strong><small>{assets().filter(asset => folderPath(asset.folder_id).some(parent => parent.id === item.id)).length} 个组件 · {folders().filter(row => row.parent_id === item.id).length} 个子分组</small><span>→</span></button>}</For></section></Show>

      <div class="library-layout">
        <section class="asset-grid" aria-label="组件列表">
          <Show when={filtered().length} fallback={<div class="empty-state"><div class="empty-cube"><Cube /></div><h2>{query() || category() !== "全部组件" || kind() !== "all" ? "没有匹配的组件" : archived() ? "没有归档组件" : folderId() || childFolders().length ? "当前分组没有直接保存的组件" : "从你的第一个组件开始"}</h2><p>{query() ? "换个关键词，或者查看全部组件。" : archived() ? "归档的组件会保留模型数据，随时可以恢复。" : "在 Plasticity 中选中模型并按 Ctrl+C，\n然后点击保存组件。以后只需一点，即可原生置入。"}</p><Show when={!archived() && !query()}><button class="primary" disabled={!ready() || !clipboardSupported()} onClick={openCapture}>＋ 保存组件</button></Show></div>}>
            <For each={filtered()}>{asset => <article class={selectedId() === asset.id ? "asset-card selected" : "asset-card"}>
              <button class="asset-preview" aria-label={"查看 " + asset.name} onClick={() => setSelectedId(asset.id)}><Show when={asset.has_preview} fallback={<div class="model-placeholder"><Cube /><span>原生模型</span></div>}><img src={previewUrl(asset)} alt={asset.name}/></Show><span class="asset-format">{kindNames[asset.kind]}</span></button>
              <div class="asset-body"><button class="asset-name" onClick={() => setSelectedId(asset.id)}>{asset.name}</button><div class="asset-meta">{asset.category}<span>{Math.max(1, Math.round(asset.bytes / 1024))} KB</span></div><div class="card-footer"><span>{asset.tags || "未添加标签"}</span><Show when={!archived()}><button class="insert-button" disabled={!canInsert()} onClick={() => insert(asset)}>置入 ↗</button></Show></div></div>
            </article>}</For>
          </Show>
        </section>
        <aside class="details-panel"><Show when={selected()} fallback={<div class="detail-placeholder"><Cube /><h3>组件详情</h3><p>选择一个组件，查看信息或置入到当前模型。</p></div>}>
          <div class="detail-heading"><span>组件详情</span><button class="icon-button" aria-label="取消选择" onClick={() => setSelectedId("")}>×</button></div>
          <h2>{selected().name}</h2><span class="category-pill">{selected().category}</span>
          <dl><dt>保存时间</dt><dd>{new Date(selected().created_at).toLocaleDateString("zh-CN")}</dd><dt>模型大小</dt><dd>{(selected().bytes / 1024).toFixed(1)} KB</dd><dt>来源版本</dt><dd>{selected().source_version === "unknown" ? "未记录" : selected().source_version}</dd><dt>标签</dt><dd>{selected().tags || "—"}</dd></dl>
          <p class="component-note">{kindNames[selected().kind]} · {folderLabel(selected().folder_id)}</p><p class="component-note">{selected().note || "暂无备注"}</p>
          <Show when={!archived()}><button class="primary full-width" disabled={!canInsert()} onClick={() => insert(selected())}>置入组件 <kbd>Ctrl ⇧ V</kbd></button><button class="secondary full-width" disabled={!canInsert()} onClick={() => insert(selected(), false)}>原位置粘贴 · Ctrl+V</button><button class="secondary full-width" disabled={!ready() || !clipboardSupported()} onClick={() => operate("asset.copy", { id: selectedId() })}>仅复制到剪贴板</button></Show>
          <div class="detail-actions"><button disabled={!ready()} onClick={openEdit}>编辑信息</button><a href={`${api}/api/assets/${selectedId()}/export`} download>导出组件包</a></div><button class="archive-button" disabled={!ready()} onClick={archiveSelected}>{archived() ? "恢复到组件库" : "归档组件"}</button>
        </Show></aside>
      </div>

      <section class="transform-bar" aria-label="原生模型操作"><div><strong>原生调整</strong><span>置入时在视口定位与确认；确认后选中组件再调整</span></div><div class="transform-actions"><For each={[["move", "移动", "G"], ["rotate", "旋转", "R"], ["scale", "缩放", "S"], ["focus", "聚焦", "Space"]]}>{item => <button disabled={!ready() || !target()} onClick={() => command(item[0])}>{item[1]}<kbd>{item[2]}</kbd></button>}</For><span class="tool-separator"/><button disabled={!ready() || !target()} onClick={() => command("undo")}>撤销</button><button disabled={!ready() || !target()} onClick={() => command("redo")}>重做</button></div></section>
      <footer class="page-footer"><span>组件数据保存在本机 · 使用 Plasticity 原生模型剪贴板</span><span>{launcherNote()}</span></footer>
    </main>

    <Show when={dialog()}><div class="modal-backdrop" onClick={event => { if (event.target === event.currentTarget && !busy()) setDialog(null); }}><section class="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div class="modal-heading"><h2 id="dialog-title">{dialog() === "edit" ? "编辑组件" : "保存组件"}</h2><button class="icon-button" disabled={busy()} aria-label="关闭对话框" onClick={() => setDialog(null)}>×</button></div><p class="modal-description">{dialog() === "edit" ? "更新名称、分类和备注，模型数据保持原样。" : "先选中需要保存的实体并按 Ctrl+C。组件将保留原生模型数据。"}</p>
      <form onSubmit={save}><label>组件名称<input required maxlength="120" autofocus placeholder="例如：六角螺栓 M8" value={form().name} onInput={event => setField("name", event.currentTarget.value)}/></label>
      <div class="form-row"><label>资产库<select aria-label="组件所属资产库" onChange={event => changeFormLibrary(event.currentTarget.value)}><For each={libraries()}>{item => <option value={item.id} selected={form().library_id === item.id}>{item.name}</option>}</For></select></label><label>组件类型<select aria-label="组件类型标注" onChange={event => setField("kind",event.currentTarget.value)}><For each={Object.entries(kindNames)}>{item => <option value={item[0]} selected={form().kind === item[0]}>{item[1]}</option>}</For></select></label></div>
      <label>分组<select aria-label="组件所属分组" disabled={foldersLoading()} onChange={event => setField("folder_id",event.currentTarget.value || null)}><option value="" selected={!form().folder_id}>{foldersLoading() ? "正在加载分组…" : "库根目录"}</option><For each={formFolders()}>{item => <option value={item.id} selected={form().folder_id === item.id}>{folderLabel(item.id,formFolders())}</option>}</For></select></label>
      <div class="form-row"><label>分类<input maxlength="80" placeholder="未分类" list="asset-categories" value={form().category} onInput={event => setField("category", event.currentTarget.value)}/></label><label>标签<input maxlength="300" placeholder="螺栓，紧固件" value={form().tags} onInput={event => setField("tags", event.currentTarget.value)}/></label></div><datalist id="asset-categories"><For each={categories()}>{name => <option value={name}/>}</For></datalist><label>备注<textarea maxlength="2000" rows="3" placeholder="尺寸、用途或使用说明" value={form().note} onInput={event => setField("note", event.currentTarget.value)}/></label>
      <Show when={dialog() === "capture"}><label class="check-label"><input type="checkbox" checked={copySelection()} disabled={!target()} onChange={event => setCopySelection(event.currentTarget.checked)}/><span>自动复制目标窗口当前选中的模型</span></label></Show>
      <label class="preview-picker">预览图（可选）<input type="file" accept="image/jpeg" onChange={readPreview}/></label>
      <Show when={form().preview || (dialog() === "edit" && form().preview === undefined && selected()?.has_preview)}><div class="preview-editor"><img class="form-preview" src={form().preview || previewUrl(selected())} alt="组件预览"/><button type="button" class="secondary" disabled={busy()} onClick={() => setField("preview", "")}>移除预览图</button></div></Show>
      <Show when={notice()?.error}><p class="form-error" role="alert">{notice().message}</p></Show><div class="modal-actions"><button type="button" class="secondary" disabled={busy()} onClick={() => setDialog(null)}>取消</button><button type="submit" class="primary" disabled={!ready() || foldersLoading() || !form().name.trim()}>{busy() ? "保存中…" : "保存组件"}</button></div></form>
    </section></div></Show>
    <Show when={organizationDialog()}><div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="organization-title"><h2 id="organization-title">{{library:"新建资产库",folder:"新建分组","rename-library":"重命名资产库","rename-folder":"重命名分组"}[organizationDialog()]}</h2><p class="modal-description">{organizationDialog() === "folder" ? `创建到：${folderLabel(folderId())}` : "库和分组用于组织已保存的组件。"}</p><form onSubmit={saveOrganization}><label>名称<input aria-label="库或分组名称" autofocus required maxlength="120" value={organizationName()} onInput={event => setOrganizationName(event.currentTarget.value)}/></label><Show when={notice()?.error}><p class="form-error" role="alert">{notice().message}</p></Show><div class="modal-actions"><button type="button" class="secondary" disabled={busy()} onClick={() => setOrganizationDialog(null)}>取消</button><button class="primary" type="submit" disabled={!ready() || !organizationName().trim()}>保存</button></div></form></section></div></Show>
  </div>;
}
