import { createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js";
import { WebsocketClient } from "./Websocketclient";
import "./ComponentBrowser.css";
import { GeometryPreview, renderThumbnail } from './GeometryPreview';
import { chooseTarget } from './targetSelection';

export function Cube(props) {
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
    if (event.data?.type === "pat:shown") { if (preferredTarget) setTargetId(preferredTarget); refresh().catch(error => showNotice(error.message, true)); focusSearch(); }
    if (event.data?.type === "pat:prepared") pendingHost.get(event.data.id)?.(event.data);
  }
  function prepareHost(preview = false) {
    if (!embedded) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const id = crypto.randomUUID();
      const timeout = setTimeout(() => {pendingHost.delete(id); reject(new Error("内嵌面板未能交回视口焦点，请重新唤起后重试"));}, preview ? 2800 : 1500);
      pendingHost.set(id, data => {clearTimeout(timeout);pendingHost.delete(id);data.ready ? resolve(data.preview || null) : reject(new Error("Plasticity 视口尚未加载"));});
      window.parent.postMessage({type:"pat:prepare",id,preview}, hostOrigin);
    });
  }
  const preferredTarget = new URLSearchParams(location.search).get("target");
  const [status, setStatus] = createSignal("connecting");
  const [connectionLost, setConnectionLost] = createSignal(false);
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
  const [targets, setTargets] = createSignal([]);
  const [targetId, setTargetId] = createSignal(preferredTarget || "");
  const [followActive, setFollowActive] = createSignal(true);
  const [note, setNote] = createSignal("");
  const [clipboardSupported, setClipboardSupported] = createSignal(false);
  const [nativeTargets, setNativeTargets] = createSignal([]);
  const [modelEnabled,setModelEnabled] = createSignal(true);
  const [query, setQuery] = createSignal("");
  const [category, setCategory] = createSignal("全部组件");
  const [archived, setArchived] = createSignal(false);
  const [selectedId, setSelectedId] = createSignal("");
  const [detailsOpen, setDetailsOpen] = createSignal(false);
  const [heldPreview, setHeldPreview] = createSignal(null);
  function closeHeldPreview() { setHeldPreview(null); }
  function previewPointerDown(event, asset) {
    if (event.button !== 2) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const bounds = event.currentTarget.getBoundingClientRect();
    setHeldPreview({asset, origin:{x:event.clientX,y:event.clientY},
      left:Math.max(8, Math.min(bounds.left, window.innerWidth - 368)),
      top:Math.max(8, Math.min(bounds.top, window.innerHeight - 360))});
  }
  function previewPointerUp(event) { if (event.button === 2) closeHeldPreview(); }
  const [connectionSettings, setConnectionSettings] = createSignal(false);
  const [cardSize, setCardSize] = createSignal(184);
  const [sortMode, setSortMode] = createSignal("recent");
  const [busy, setBusy] = createSignal(false);
  const [notice, setNotice] = createSignal(null);
  const [dialog, setDialog] = createSignal(null);
  const [form, setForm] = createSignal({ name: "", category: "", tags: "", note: "", preview: "" });
  const [copySelection, setCopySelection] = createSignal(false);
  const [autoPreview, setAutoPreview] = createSignal(true);
  let importInput;
  let searchInput;
  let poll;
  let refreshPending = false;
  let refreshQueued = false;

  const selected = createMemo(() => assets().find(asset => asset.id === selectedId()));
  const target = createMemo(() => targets().find(item => item.id === targetId()));
  const categories = createMemo(() => [...new Set(assets().map(asset => asset.category))].sort());
  const insertModes = {"new-body":"独立对象",union:"布尔合并",difference:"布尔减去",intersection:"布尔相交"};
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
  }).sort((a,b) => sortMode() === "name" ? a.name.localeCompare(b.name, "zh-CN") : sortMode() === "oldest" ? a.created_at.localeCompare(b.created_at) : b.created_at.localeCompare(a.created_at)));
  const ready = () => status() === "connected" && !busy();
  const canInsert = () => ready() && modelEnabled() && nativeTargets().includes(targetId()) && !archived();
  const setField = (key, value) => setForm(current => ({ ...current, [key]: value }));
  const [previewRevision, setPreviewRevision] = createSignal(0);
  const previewUrl = asset => `${api}/api/assets/${asset.id}/${asset.has_preview ? 'preview' : 'geometry/preview'}?v=${encodeURIComponent(asset.updated_at || asset.created_at)}&render=${previewRevision()}`;
  const meshRequests = new Map();
  async function loadGeometry(asset, thumbnailRequired = false, refreshThumbnail = false) {
    if(meshRequests.has(asset.digest))return meshRequests.get(asset.digest);
    const request = (async()=>{
      const response = await fetch(`${api}/api/assets/${asset.id}/geometry`);
      let mesh;
      if(response.ok) mesh = await response.json();
      else {
        const generated=await client.request('asset.geometry',{id:asset.id,target_id:preferredTarget || targetId() || undefined});
        mesh=generated.mesh;
      }
      if(refreshThumbnail || !asset.has_geometry_preview) {
        try {
          const preview=renderThumbnail(mesh);
          await client.request('asset.geometry.thumbnail',{id:asset.id,digest:asset.digest,preview});
          setPreviewRevision(value=>value+1);
          setAssets(rows=>rows.map(row=>row.digest===asset.digest?{...row,has_geometry:true,has_geometry_preview:true}:row));
        }catch(error){
          if(thumbnailRequired)throw new Error('网格已保存，但缩略图生成失败：'+error.message);
          showNotice('网格已保存，当前浏览器未能生成缩略图。',true);
        }
      }
      return mesh;
    })();
    meshRequests.set(asset.digest,request);
    request.then(()=>meshRequests.delete(asset.digest),()=>meshRequests.delete(asset.digest));
    return request;
  }
  async function generatePreviews() {
    if(!ready())return;
    const rows=filtered();
    if(!rows.length){showNotice('当前没有需要生成预览的组件');return;}
    setBusy(true);
    let completed=0;
    try {
      for(const asset of rows){showNotice(`正在生成预览 ${completed+1}/${rows.length}：${asset.name}`);await loadGeometry(asset,true,true);completed++;}
      showNotice(`已生成 ${completed} 个组件的几何预览`);
    }catch(error){showNotice(`已完成 ${completed} 个。${error.message}`,true);}
    finally{setBusy(false);}
  }
  const showNotice = (message, error = false) => setNotice({ message, error });

  const client = new WebsocketClient(wsUrl, value => {
    setStatus(value);
    if (value === "disconnected") setConnectionLost(true);
    if (value === "connected") setConnectionLost(false);
  }, event => {
    if (["connected","library_changed","service_changed"].includes(event.type)) refresh().catch(error => showNotice(error.message, true));
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
      if (quickPanel) setFloatingPanel(!!state.launcher?.frameless);
      if (folderId() && !state.folders?.some(item => item.id === folderId())) setFolderId(null);
      setTargets(state.targets);
      setNote(state.connection_note);
      setClipboardSupported(state.clipboard_supported);
      setNativeTargets(state.native_targets || []);
      setModelEnabled(state.model_enabled !== false);
      if (embedded) window.parent.postMessage({type:"pat:panel-settings",settings:state.panel_settings}, hostOrigin);
      setTargetId(chooseTarget({embedded,preferredTarget,current:targetId(),followActive:followActive(),state}));
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
    if (heldPreview() && (event.key === "Escape" || event.key === "Tab")) closeHeldPreview();
    if (event.key === "Escape" && detailsOpen()) {event.preventDefault();setDetailsOpen(false);return;}
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
      if (embedded && (action === "asset.insert" || action === "target.command" || (action === "library.capture" && (args.copy_selection || args.auto_preview)))) {
        const preview = await prepareHost(false);
        if (preview) args = {...args,preview};
      }
      const result = await client.request(action, args);
      if (action !== "asset.insert") showNotice(success || result?.message || "操作完成");
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
    const result = await operate("asset.insert", { id: asset.id, target_id: embedded ? preferredTarget || targetId() : targetId(), follow_active:!embedded && followActive(), placement, transport:"native" });
    if (result) setDetailsOpen(false);
    if (result && embedded) hidePanel();
  }
  function openCapture() {
    setFormFolders(folders()); setFoldersLoading(false);
    setForm({ name: "", category: category() === "全部组件" ? "" : category(), tags: "", note: "", preview: "", library_id:libraryId(),folder_id:folderId(),insert_mode:"new-body",kind:kind() === "all" ? "unknown" : kind() });
    setCopySelection(!!target() && modelEnabled());
    setAutoPreview(true);
    setNotice(null);
    setDialog("capture");
  }
  function openEdit(asset = selected()) {
    setFormFolders(folders()); setFoldersLoading(false);
    setForm({ name: asset.name, category: asset.category, tags: asset.tags, note: asset.note, preview: undefined,library_id:asset.library_id,folder_id:asset.folder_id,kind:asset.kind,insert_mode:asset.insert_mode || "new-body" });
    setSelectedId(asset.id);setNotice(null);setDialog(null);setDetailsOpen(true);
  }
  async function save(event) {
    event.preventDefault();
    const capturing = dialog() === "capture";
    const generateGeometry = capturing && autoPreview() && !form().preview;
    if (capturing && copySelection() && (!target() || !modelEnabled())) {
      showNotice("请先连接目标 Plasticity 窗口，再直接保存选中的模型", true);
      return;
    }
    const result = await operate(capturing ? "library.capture" : "library.update", {
      ...form(), id: selectedId(), target_id: targetId(), copy_selection: copySelection(), auto_preview:autoPreview(), preview_mode:'geometry', transport:"native",
      follow_active:!embedded && followActive(),
    }, capturing ? "组件已保存，可重复置入" : "组件信息已更新");
    if (result) {
      if (dialog() === "capture") { setArchived(false); setCategory("全部组件"); setQuery(""); }
      setDialog(null);
      if (result.library_id !== libraryId()) await switchLibrary(result.library_id);
      enterFolder(result.folder_id); setKind("all"); setSelectedId(result.id); await refresh();
      if (!capturing) openEdit(result);
      if (result.preview_warning) showNotice(result.preview_warning);
      if (capturing && embedded) window.parent.postMessage({type:"pat:show"}, hostOrigin);
      if (generateGeometry) {
        setBusy(true);
        showNotice('组件已保存，正在生成几何预览…');
        try {await loadGeometry(result,true);showNotice('组件及几何预览已保存');}
        catch(error){showNotice('组件已保存。'+error.message,true);}
        finally{setBusy(false);}
      }
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
  onMount(() => {
    window.addEventListener("pointerup", previewPointerUp, true);
    window.addEventListener("pointercancel", closeHeldPreview, true);
    window.addEventListener("blur", closeHeldPreview);
  });
  onCleanup(() => { clearInterval(poll); client.disconnect(); window.removeEventListener("keydown",onSearchKey);window.removeEventListener("message",hostMessage);
    window.removeEventListener("pointerup", previewPointerUp, true);
    window.removeEventListener("pointercancel", closeHeldPreview, true);
    window.removeEventListener("blur", closeHeldPreview);
  });

  function AssetForm(props) {
    return <form class="asset-edit-form" onSubmit={save}><label>组件名称<input required maxlength="120" autofocus placeholder="例如：六角螺栓 M8" value={form().name} onInput={event => setField("name", event.currentTarget.value)}/></label>
      <div class="form-row"><label>资产库<select aria-label="组件所属资产库" onChange={event => changeFormLibrary(event.currentTarget.value)}><For each={libraries()}>{item => <option value={item.id} selected={form().library_id === item.id}>{item.name}</option>}</For></select></label><label>组件类型<select aria-label="组件类型标注" onChange={event => setField("kind",event.currentTarget.value)}><For each={Object.entries(kindNames)}>{item => <option value={item[0]} selected={form().kind === item[0]}>{item[1]}</option>}</For></select></label></div>
      <fieldset class="insert-mode-picker" title="布尔模式使用置入前选中的实体作为目标。原位置粘贴始终保持独立对象。"><legend>默认置入模式</legend><div class="insert-mode-options"><For each={Object.entries(insertModes)}>{item=><label><input type="radio" name="insert_mode" value={item[0]} checked={(form().insert_mode || "new-body") === item[0]} onChange={()=>setField("insert_mode",item[0])}/><span>{item[1]}</span></label>}</For></div></fieldset>
      <label>分组<select aria-label="组件所属分组" disabled={foldersLoading()} onChange={event => setField("folder_id",event.currentTarget.value || null)}><option value="" selected={!form().folder_id}>{foldersLoading() ? "正在加载分组…" : "库根目录"}</option><For each={formFolders()}>{item => <option value={item.id} selected={form().folder_id === item.id}>{folderLabel(item.id,formFolders())}</option>}</For></select></label>
      <div class="form-row"><label>分类<input maxlength="80" placeholder="未分类" list="asset-categories" value={form().category} onInput={event => setField("category", event.currentTarget.value)}/></label><label>标签<input maxlength="300" placeholder="螺栓，紧固件" value={form().tags} onInput={event => setField("tags", event.currentTarget.value)}/></label></div><datalist id="asset-categories"><For each={categories()}>{name => <option value={name}/>}</For></datalist><label>备注<textarea maxlength="2000" rows="3" placeholder="尺寸、用途或使用说明" value={form().note} onInput={event => setField("note", event.currentTarget.value)}/></label>
      <Show when={props.capture}><label class="check-label" title={copySelection() ? "直接读取选中模型，不占用系统剪贴板。" : "从剪贴板保存，请先手动复制模型。"}><input type="checkbox" checked={copySelection()} disabled={busy() || !target() || !modelEnabled()} onChange={event => setCopySelection(event.currentTarget.checked)}/><span>直接保存选中的模型</span></label></Show>
      <label class="preview-picker">预览图（可选）<input type="file" accept="image/jpeg" onChange={readPreview}/></label>
      <Show when={props.capture}><label class="check-label" title="从模型生成正交缩略图和三维预览，需要连接 Plasticity；上传的预览图优先使用。"><input type="checkbox" checked={autoPreview()} disabled={busy()} onChange={event=>setAutoPreview(event.currentTarget.checked)}/><span>自动生成几何预览</span></label></Show>
      <Show when={form().preview || (!props.capture && form().preview === undefined && selected()?.has_preview)}><div class="preview-editor"><img class="form-preview" src={form().preview || previewUrl(selected())} alt="组件预览"/><button type="button" class="secondary" disabled={busy()} onClick={() => setField("preview", "")}>移除预览图</button></div></Show>
      <Show when={notice()?.error}><p class="form-error" role="alert">{notice().message}</p></Show><div class="modal-actions"><button type="button" class="secondary" disabled={busy()} onClick={props.onCancel}>取消</button><button type="submit" class="primary" disabled={!ready() || foldersLoading() || !form().name.trim()}>{busy() ? "保存中…" : props.capture ? "保存组件" : "保存修改"}</button></div></form>;
  }

  return <div class={floatingPanel() ? "app-shell component-first floating-panel" : "app-shell component-first"} style={{"--asset-size":`${cardSize()}px`}}>
    <aside class="sidebar">
      <div class="brand"><Cube /><div><strong>Plasticity</strong><span>COMPONENT LIBRARY</span></div></div>
      <div class="sidebar-label">模型组件库</div>
      <button class={!archived() ? "nav-item active" : "nav-item"} onClick={() => toggleArchive(false)}>◇ 全部组件 <span>{!archived() ? assets().length : ""}</span></button>
      <div class="sidebar-label">资产库</div>
      <nav class="library-tabs" aria-label="资产库"><For each={libraries()}>{item => <button class={libraryId() === item.id ? "library-tab active" : "library-tab"} aria-pressed={libraryId() === item.id} disabled={busy()} onClick={() => switchLibrary(item.id)}>{item.name}<span>{item.count}</span></button>}</For><button class="library-tab add-library" disabled={!ready()} onClick={() => openOrganization("library")}>＋ 新建库</button></nav>
      <div class="sidebar-label category-label">分组</div>
      <button class={!folderId() ? "nav-item active" : "nav-item"} onClick={() => enterFolder(null)}>⌂ 库根目录</button>
      <div class="folder-tree"><For each={orderedFolders()}>{item => <button class={folderId() === item.id ? "folder-nav active" : "folder-nav"} style={{"padding-left":`${10 + (folderPath(item.id).length-1)*12}px`}} onClick={() => enterFolder(item.id)} title={folderLabel(item.id)}>▱ {item.name}</button>}</For></div>
      <div class="sidebar-label category-label">分类</div>
      <For each={categories()}>{name => <button class={!archived() && category() === name ? "nav-item category active" : "nav-item category"} onClick={() => setCategory(name)}>▦ {name}<span>{assets().filter(asset => asset.category === name).length}</span></button>}</For>
      <button class={archived() ? "nav-item active archive-link" : "nav-item archive-link"} onClick={() => toggleArchive(true)}>▧ 已归档</button>
      <div class="sidebar-bottom"><span class={status() === "connected" ? "status-dot online" : "status-dot"}/><span>{status() === "connected" ? "本地服务已连接" : status() === "connecting" ? "连接服务中…" : "服务断开，正在重连"}</span></div>
    </aside>

    <main class="main-content">
      <Show when={connectionLost() || (status() === "connected" && !modelEnabled())}><section class="connection-alert" role="alert"><span class="connection-alert-icon" aria-hidden="true">!</span><div><strong>{connectionLost() ? "后台连接已断开" : "模型连接已停止"}</strong><p>{connectionLost() ? "组件置入和保存暂不可用。请启动后台服务，连接恢复后可继续使用。" : "组件置入、自动复制和模型操作已停用。请在控制中心恢复模型连接。"}</p></div><Show when={status() === "connected"}><a href="/?control=1" target="_blank" rel="noopener noreferrer">打开控制中心</a></Show></section></Show>
      <Show when={ready() && modelEnabled() && !!target() && !nativeTargets().includes(targetId())}><section class="connection-alert" role="alert"><span class="connection-alert-icon" aria-hidden="true">!</span><div><strong>原生模型插件未连接</strong><p>请重新打开已安装插件的 Plasticity。直连恢复后，即可保存选中模型和置入组件。</p></div></section></Show><header class="page-header"><div><div class="eyebrow">YOUR REUSABLE GEOMETRY</div><h1>{archived() ? "已归档" : "模型组件库"}</h1><p>保存一次，随时置入。在 Plasticity 里继续创作。</p></div>
        <label class="search-field"><span>⌕</span><input ref={searchInput} aria-label="搜索组件" placeholder="搜索此库" value={query()} onInput={event => setQuery(event.currentTarget.value)} onKeyDown={event => { if(event.key === "Enter" && filtered().length && canInsert()) {event.preventDefault();insert(filtered()[0]);} }}/></label>
        <div class="header-actions"><button class="secondary connection-settings-toggle" aria-label="连接与分组设置" aria-expanded={connectionSettings()} onClick={()=>setConnectionSettings(!connectionSettings())}>⚙</button><button class="secondary" disabled={!ready() || !modelEnabled()} onClick={generatePreviews}>生成预览</button><button class="secondary" disabled={!ready()} onClick={() => importInput.click()}>↓ 导入组件包</button><button class="primary" disabled={!ready() || !clipboardSupported()} onClick={openCapture}>＋ 保存组件</button><Show when={floatingPanel()}><button class="panel-dismiss" aria-label="收起面板" title="收起面板" disabled={!ready()} onClick={hidePanel}>×</button></Show></div>
      </header>
      <input ref={importInput} class="hidden-input" type="file" accept=".patasset" onChange={importPackage}/>

      <Show when={connectionSettings()}><section class="target-bar" aria-label="目标窗口"><div class="target-label"><span class="small-square">↗</span><div><strong>置入目标</strong><span>{nativeTargets().includes(targetId()) ? "原生模型直连 · 不占用剪贴板" : "原生模型插件未连接"}</span></div></div>
        <select aria-label="Plasticity 目标窗口" onChange={event => {setTargetId(event.currentTarget.value);setFollowActive(false);}} disabled={busy() || (embedded && !!preferredTarget)}><option value="" selected={!targetId()}>{targets().length ? "请选择 Plasticity 窗口" : "未发现 Plasticity 窗口"}</option><For each={targets()}>{item => <option value={item.id} selected={targetId() === item.id}>{item.title} · {item.mode === "cdp" ? "CDP" : "原生"} · {item.target_id?.slice(0, 6) || item.hwnd}</option>}</For></select>
        <Show when={!embedded}><button class="secondary" disabled={!ready()} aria-pressed={followActive()} onClick={() => {setFollowActive(!followActive());refresh().catch(error => showNotice(error.message,true));}}>{followActive() ? "跟随激活窗口" : "固定所选窗口"}</button></Show>
        <button class="icon-button" aria-label="刷新窗口" disabled={!ready()} onClick={() => refresh().catch(error => showNotice(error.message, true))}>↻</button>
        <Show when={target()?.mode === "cdp"}><button class="secondary" disabled={!ready()} onClick={() => operate("target.embed", { target_id: targetId() }, "面板已嵌入")}>嵌入面板</button></Show>
        <Show when={embedded}><button class="secondary" onClick={hidePanel}>收起</button></Show>
      </section>

      <div class="folder-toolbar"><nav class="breadcrumbs" aria-label="分组路径"><button onClick={() => enterFolder(null)}>{currentLibrary()?.name || "资产库"}</button><For each={folderPath(folderId())}>{item => <><span> / </span><button onClick={() => enterFolder(item.id)}>{item.name}</button></>}</For></nav><div><button disabled={!ready()} onClick={() => openOrganization("rename-library")}>重命名库</button><Show when={folderId()}><button disabled={!ready()} onClick={() => openOrganization("rename-folder")}>重命名分组</button></Show><button disabled={!ready()} onClick={() => openOrganization("folder")}>＋ 新建分组</button></div></div>
      </Show>


      <Show when={notice()}><div class={notice().error ? "notice error" : "notice"} role={notice().error ? "alert" : "status"}><span>{notice().message}</span><button aria-label="关闭提示" onClick={() => setNotice(null)}>×</button></div></Show>
      <Show when={!target()}><div class="connection-hint" title="打开 Plasticity，在连接设置中选择目标窗口。">未连接 Plasticity 窗口</div></Show>

      <div class="library-toolbar"><div class="section-name">{category()}<span>{filtered().length} 个组件</span></div><div class="type-tabs" aria-label="组件类型"><For each={[["all","全部"],["solid","Solid"],["curve","Curve"],["mixed","混合"],["unknown","未标注"]]}>{item => <button class={kind() === item[0] ? "active" : ""} aria-pressed={kind() === item[0]} onClick={() => {setKind(item[0]);setSelectedId("");}}>{item[1]}</button>}</For><span>类型由保存时标注</span></div></div>
      <Show when={!query().trim() && !archived() && childFolders().length}><section class="folder-grid" aria-label="子分组"><For each={childFolders()}>{item => <button class="folder-card" onClick={() => enterFolder(item.id)}><span>▱</span><strong>{item.name}</strong><small>{assets().filter(asset => folderPath(asset.folder_id).some(parent => parent.id === item.id)).length} 个组件 · {folders().filter(row => row.parent_id === item.id).length} 个子分组</small><span>→</span></button>}</For></section></Show>

      <Show when={heldPreview()} keyed>{preview => <section class="held-model-preview" role="status" aria-label={"旋转预览 " + preview.asset.name} style={{left:`${preview.left}px`,top:`${preview.top}px`}}><strong>{preview.asset.name}</strong><GeometryPreview asset={preview.asset} load={loadGeometry} heldOrigin={preview.origin}/><span>按住右键移动旋转 · 松开恢复</span></section>}</Show>
      <div class="library-layout">
        <section class="asset-grid" aria-label="组件列表">
          <Show when={filtered().length} fallback={<div class="empty-state"><div class="empty-cube"><Cube /></div><h2>{query() || category() !== "全部组件" || kind() !== "all" ? "没有匹配的组件" : archived() ? "没有归档组件" : folderId() || childFolders().length ? "当前分组没有直接保存的组件" : "从你的第一个组件开始"}</h2><p>{query() ? "换个关键词，或者查看全部组件。" : archived() ? "归档的组件会保留模型数据，随时可以恢复。" : "在 Plasticity 中选中模型，\n点击保存组件即可直接读取并保存。以后只需一点，即可原生置入。"}</p><Show when={!archived() && !query()}><button class="primary" disabled={!ready() || !clipboardSupported()} onClick={openCapture}>＋ 保存组件</button></Show></div>}>
            <For each={filtered()}>{asset => <article data-insert-mode={asset.insert_mode || "new-body"} class={selectedId() === asset.id ? "asset-card selected" : "asset-card"}>
              <button class="asset-preview" data-insert-mode={asset.insert_mode || "new-body"} aria-label={"置入 " + asset.name} aria-disabled={!canInsert()} onClick={() => {if(canInsert())insert(asset);}} onPointerDown={event=>previewPointerDown(event,asset)} onContextMenu={event=>event.preventDefault()}><Show when={asset.has_geometry_preview || asset.has_preview} fallback={<div class="model-placeholder"><Cube /><span>原生模型</span></div>}><img classList={{"geometry-thumbnail":!asset.has_preview}} src={previewUrl(asset)} alt={asset.name} draggable="false"/></Show><span class="asset-format">{kindNames[asset.kind]}</span><Show when={asset.insert_mode && asset.insert_mode !== "new-body"}><span class="asset-insert-mode" title={"默认置入：" + insertModes[asset.insert_mode]}>{insertModes[asset.insert_mode]}</span></Show><span class="asset-hover-action">{archived() ? "右键按住旋转预览" : "点击置入 · 右键按住旋转"}</span></button>
              <div class="asset-body"><div class="asset-name">{asset.name}</div><div class="asset-meta" title={"默认置入：" + insertModes[asset.insert_mode || "new-body"]}>{asset.category}<span>{Math.max(1, Math.round(asset.bytes / 1024))} KB</span></div><div class="card-footer"><span title={asset.tags}>{asset.tags || ""}</span><button class="insert-button" aria-label={"编辑 " + asset.name} onClick={() => openEdit(asset)}>编辑</button></div></div>
            </article>}</For>
          </Show>
        </section>
        <Show when={detailsOpen() && selected()}><div class="asset-details-backdrop" onClick={()=>setDetailsOpen(false)}><aside class="details-panel" role="dialog" aria-modal="true" aria-label="组件详情" onClick={event=>event.stopPropagation()}><button class="details-dismiss" aria-label="关闭组件详情" onClick={()=>setDetailsOpen(false)}>×</button><Show when={selected()} fallback={<div class="detail-placeholder"><Cube /><h3>组件详情</h3><p>选择一个组件，查看信息或置入到当前模型。</p></div>}>
          <div class="detail-heading"><span>编辑组件</span></div>
          <h2>{selected().name}</h2><span class="category-pill">{selected().category}</span>
          <GeometryPreview asset={selected()} load={loadGeometry}/>
          <dl><dt>保存时间</dt><dd>{new Date(selected().created_at).toLocaleDateString("zh-CN")}</dd><dt>模型大小</dt><dd>{(selected().bytes / 1024).toFixed(1)} KB</dd><dt>来源版本</dt><dd>{selected().source_version === "unknown" ? "未记录" : selected().source_version}</dd><dt>标签</dt><dd>{selected().tags || "—"}</dd></dl>
          <AssetForm capture={false} onCancel={()=>setDetailsOpen(false)}/>
          <Show when={!archived()}><button class="primary full-width" disabled={!canInsert()} onClick={() => insert(selected())}>置入组件</button><button class="secondary full-width" disabled={!canInsert()} onClick={() => insert(selected(), false)}>原位置粘贴</button><button class="secondary full-width" disabled={!ready() || !modelEnabled() || !clipboardSupported()} onClick={() => operate("asset.copy", { id: selectedId() })}>仅复制到剪贴板</button></Show>
          <div class="detail-actions"><a href={`${api}/api/assets/${selectedId()}/export`} download>导出组件包</a></div><button class="archive-button" disabled={!ready()} onClick={archiveSelected}>{archived() ? "恢复到组件库" : "归档组件"}</button>
        </Show></aside></div></Show>
      </div>

      <footer class="page-footer component-browser-footer"><div class="browser-location"><span>{currentLibrary()?.name || "资产库"}</span><span> / </span><span>{folderLabel(folderId())}</span><button aria-label="新建资产库" title="新建资产库" disabled={!ready()} onClick={()=>openOrganization("library")}>＋</button></div><div class="browser-display"><select aria-label="组件排序" value={sortMode()} onChange={event=>setSortMode(event.currentTarget.value)}><option value="recent">最近保存</option><option value="oldest">最早保存</option><option value="name">名称排序</option></select><label>大小<input type="range" aria-label="组件卡片大小" min="136" max="260" step="12" value={cardSize()} onInput={event=>setCardSize(Number(event.currentTarget.value))}/></label><a href="/?control=1" target="_blank" rel="noopener noreferrer" title="控制中心">控制中心 ↗</a></div></footer>
    </main>

    <Show when={dialog()}><div class="modal-backdrop" onClick={event => { if (event.target === event.currentTarget && !busy()) setDialog(null); }}><section class="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div class="modal-heading"><h2 id="dialog-title">保存组件<span class="help-tip" tabindex="0" aria-label="保存帮助" data-tip={copySelection() ? "选中模型并完成当前工具后保存，无需系统剪贴板。" : "先在 Plasticity 复制模型，再保存剪贴板中的组件。"}>?</span></h2><button class="icon-button" disabled={busy()} aria-label="关闭对话框" onClick={() => setDialog(null)}>×</button></div>
      <AssetForm capture onCancel={()=>setDialog(null)}/>
    </section></div></Show>
    <Show when={organizationDialog()}><div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="organization-title"><h2 id="organization-title">{{library:"新建资产库",folder:"新建分组","rename-library":"重命名资产库","rename-folder":"重命名分组"}[organizationDialog()]}</h2><p class="modal-description">{organizationDialog() === "folder" ? `创建到：${folderLabel(folderId())}` : "库和分组用于组织已保存的组件。"}</p><form onSubmit={saveOrganization}><label>名称<input aria-label="库或分组名称" autofocus required maxlength="120" value={organizationName()} onInput={event => setOrganizationName(event.currentTarget.value)}/></label><Show when={notice()?.error}><p class="form-error" role="alert">{notice().message}</p></Show><div class="modal-actions"><button type="button" class="secondary" disabled={busy()} onClick={() => setOrganizationDialog(null)}>取消</button><button class="primary" type="submit" disabled={!ready() || !organizationName().trim()}>保存</button></div></form></section></div></Show>
  </div>;
}
