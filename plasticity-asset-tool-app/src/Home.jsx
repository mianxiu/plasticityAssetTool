import {t, locale} from "./i18n";
import {supportsBoolean,componentMode} from "./componentModes.mjs";
import {VirtualAssetGrid} from "./VirtualAssetGrid";
import {mergeLibrary} from "./librarySync.mjs";
import { previewQueue } from "./previewQueue.mjs";
import { createMemo, createSignal, lazy, For, onCleanup, onMount, Show } from "solid-js";
import { WebsocketClient } from "./Websocketclient";
import "./ComponentBrowser.css";
const GeometryPreview = lazy(() => import('./GeometryPreview').then(module => ({default:module.GeometryPreview})));
import { geometryCache } from "./geometryCache.mjs";
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
  const [sidebarMode, setSidebarMode] = createSignal("fixed");
  const pendingHost = new Map();
  let panelVisible = !embedded;
  const hostOrigin = document.referrer.startsWith("file:") || !document.referrer ? "*" : new URL(document.referrer).origin;
  function hidePanel() {
    if (embedded) window.parent.postMessage({type:"pat:hide"}, hostOrigin);
    else operate("panel.dismiss", {});
  }
  function hostMessage(event) {
    if (!embedded || event.source !== window.parent) return;
    if (event.data?.type === "pat:hidden") panelVisible = false;
    if (event.data?.type === "pat:shown") { panelVisible = true; refreshConnection().catch(() => {}); if (preferredTarget) setTargetId(preferredTarget); window.dispatchEvent(new Event("pat:layout")); clearTimeout(shownTimer); shownTimer = setTimeout(() => refresh().catch(error => showNotice(error.message,true)), 150); focusSearch(); }
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
  let cardSizeTimer, cardSizePending = false, cardSizeVersion = 0;
  function changeCardSize(event) {
    setCardSize(Number(event.currentTarget.value));
    cardSizePending = true;cardSizeVersion++;
    clearTimeout(cardSizeTimer);
    cardSizeTimer = setTimeout(saveCardSize, 300);
  }
  async function saveCardSize() {
    clearTimeout(cardSizeTimer);
    if (!cardSizePending) return;
    const version = cardSizeVersion;
    try {await client.request("service.panel_settings", {card_size:cardSize()});}
    catch(error) {showNotice("大小设置未保存：" + error.message, true);}
    finally {if (version === cardSizeVersion) cardSizePending = false;}
  }
  const [sortMode, setSortMode] = createSignal("recent");
  const [exportMode, setExportMode] = createSignal(false);
  const [exportSelection, setExportSelection] = createSignal(new Set());
  const [exporting, setExporting] = createSignal(false);
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
  let libraryCursor = null, cursorView = null, libraryLoaded = false, shownTimer;

  const selected = createMemo(() => assets().find(asset => asset.id === selectedId()));
  const target = createMemo(() => targets().find(item => item.id === targetId()));
  const categories = createMemo(() => [...new Set(assets().map(asset => asset.category))].sort());
  const displayMode = componentMode;
  const modeLabel = asset => t(displayMode(asset) === "sequence" ? "连续布尔" : insertModes[displayMode(asset)]);
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
  const folderLabel = (id, rows = folders()) => folderPath(id, rows).map(item => item.name).join(" / ") || t("库根目录");
  const searchable = createMemo(() => {
    const labels = new Map(folders().map(row => [row.id, folderLabel(row.id)]));
    return assets().map(asset => ({asset, text:[asset.name,asset.category,asset.tags,asset.note,labels.get(asset.folder_id) || "库根目录"].join(" ").toLowerCase()}));
  });
  const filtered = createMemo(() => {
    const search = query().trim().toLowerCase();
    const rows = searchable().filter(({asset,text}) => (search || asset.folder_id === folderId()) &&
      (kind() === "all" || asset.kind === kind()) && (category() === "全部组件" || asset.category === category()) && text.includes(search)).map(row => row.asset);
    const mode = sortMode();
    return rows.sort((a,b) => mode === "name" ? a.name.localeCompare(b.name, "zh-CN") : mode === "oldest" ? a.created_at.localeCompare(b.created_at) : b.created_at.localeCompare(a.created_at));
  });
  const ready = () => status() === "connected" && !busy();
  const categoryExport = createMemo(() => assets().filter(asset => category() === "全部组件" || asset.category === category()));
  const selectedExport = createMemo(() => assets().filter(asset => exportSelection().has(asset.id)).map(asset => asset.id));
  function toggleExport(id) {
    setExportSelection(current => {const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next;});
  }
  function startExportSelection(event) {
    event.currentTarget.closest('details').open = false;
    setExportMode(true); setDetailsOpen(false);
  }
  async function exportComponents(ids) {
    if (!ids.length || exporting() || !ready()) return;
    setExporting(true);
    try {
      const response = await fetch(`${api}/api/export`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids})});
      if (response.status === 404) throw new Error(t("请先重启后台，启用批量导出"));
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || t("导出失败"));
      const link = document.createElement('a');
      link.href = `${api}${result.download_url}`;
      link.download = 'PlasticityAssetTool-components.zip';
      document.body.append(link); link.click(); link.remove();
      showNotice(t("已开始下载 {count} 个组件的 ZIP 包", {count:result.count}));
    } catch (error) {showNotice(error.message, true);}
    finally {setExporting(false);}
  }
  const canInsert = () => ready() && modelEnabled() && nativeTargets().includes(targetId()) && !archived();
  const setField = (key, value) => setForm(current => ({ ...current, [key]: value, ...(key === "kind" && !supportsBoolean({kind:value}) ? {insert_mode:"new-body"} : {}) }));
  const [previewRevision, setPreviewRevision] = createSignal({});
  const previewUrl = asset => `${api}/api/assets/${asset.id}/${asset.has_preview ? 'preview' : 'geometry/preview'}?v=${encodeURIComponent(asset.updated_at || asset.created_at)}&render=${previewRevision()[asset.digest] || 0}`;
  const meshRequests = new Map();
  const meshCache = geometryCache();
  async function loadGeometry(asset, thumbnailRequired = false, refreshThumbnail = false) {
    if(meshRequests.has(asset.digest))return meshRequests.get(asset.digest);
    const request = (async()=>{
      let mesh = meshCache.get(asset.digest);
      if (!mesh) {
      const response = await fetch(`${api}/api/assets/${asset.id}/geometry`);
      if(response.ok) mesh = await response.json();
      else {
        const generated=await previewClient.request('asset.geometry',{id:asset.id,target_id:preferredTarget || targetId() || undefined});
        mesh=generated.mesh;
      }
      meshCache.set(asset.digest,mesh);
      }
      if(refreshThumbnail || !asset.has_geometry_preview) {
        try {
          const {renderThumbnail} = await import('./GeometryPreview');
          const preview=renderThumbnail(mesh);
          await previewClient.request('asset.geometry.thumbnail',{id:asset.id,digest:asset.digest,preview});
          setPreviewRevision(value=>({...value,[asset.digest]:(value[asset.digest] || 0)+1}));
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
  const [previewPending, setPreviewPending] = createSignal(0);
  let previewConnected = false;
  const previewClient = new WebsocketClient(wsUrl, value => {previewConnected = value === "connected";}, () => {});
  const previewJobs = previewQueue({
    available: () => ready() && previewConnected && modelEnabled(),
    run: asset => loadGeometry(asset, true, !!asset.forceThumbnail),
    changed: setPreviewPending,
    failed: error => showNotice("模型已保存，预览失败："+error.message, true),
  });
  function generatePreviews() {
    if (!ready()) return;
    try { for (const asset of filtered()) previewJobs.add({...asset, forceThumbnail:true}); }
    catch (error) { showNotice(error.message, true); }
  }
  const showNotice = (message, error = false) => setNotice({ message, error });

  const client = new WebsocketClient(wsUrl, value => {
    setStatus(value);
    if (value === "disconnected") setConnectionLost(true);
    if (value === "connected") setConnectionLost(false);
  }, event => {
    if (["connected","library_changed","service_changed"].includes(event.type)) refresh().catch(error => showNotice(error.message, true));
    if (event.type === "service_changed") refreshConnection().catch(() => {});
    if (event.type === "launcher_error") showNotice(event.message, true);
    if (event.type === "quick_launch") {
      if (event.target_id && targets().some(item => item.id === event.target_id)) setTargetId(event.target_id);
      focusSearch();
    }
  });

  let connectionPending = false;
  const connectionClient = new WebsocketClient(wsUrl, value => {
    if (value === "connected") refreshConnection().catch(() => {});
  }, () => {});
  async function refreshConnection() {
    if (connectionPending) return;
    connectionPending = true;
    try {
      let state;
      try { state = await connectionClient.request("connection.state"); }
      catch (error) {
        if (!error.message.startsWith("未知操作")) throw error;
        state = await connectionClient.request("state", {library_id:libraryId()});
      }
      setTargets(state.targets);
      setNote(state.connection_note);
      setClipboardSupported(state.clipboard_supported);
      setNativeTargets(state.native_targets || []);
      setModelEnabled(state.model_enabled !== false);
      setTargetId(chooseTarget({embedded,preferredTarget,current:targetId(),followActive:followActive(),state}));
    } finally { connectionPending = false; }
  }

  async function refresh() {
    if (libraryLoaded && !panelVisible) { refreshQueued = true; return; }
    if (!ready() || refreshPending) { refreshQueued = true; return; }
    refreshQueued = false;
    refreshPending = true;
    try {
      const requestedLibrary = libraryId();
      const requestedArchive = archived();
      let state;
      try { state = await client.request("library.changes", {library_id:requestedLibrary, archived:requestedArchive, since:cursorView === requestedLibrary+":"+requestedArchive ? libraryCursor : null}); }
      catch (error) {
        if (!error.message.startsWith("未知操作")) throw error;
        state = await client.request("state", {library_id:requestedLibrary});
        if (requestedArchive) state.assets = await client.request("library.list", {library_id:requestedLibrary, archived:true});
      }
      if (requestedLibrary !== libraryId() || requestedArchive !== archived()) { refreshQueued = true; return; }
      setLibraries(previous => JSON.stringify(previous) === JSON.stringify(state.libraries || []) ? previous : state.libraries || []);
      setFolders(previous => JSON.stringify(previous) === JSON.stringify(state.folders || []) ? previous : state.folders || []);
      if (quickPanel) setFloatingPanel(!!state.launcher?.frameless);
      if (folderId() && !state.folders?.some(item => item.id === folderId())) setFolderId(null);
      setSidebarMode(state.panel_settings?.sidebar_mode || "fixed");
      if (!cardSizePending) setCardSize(state.panel_settings?.card_size || 184);
      if (embedded) window.parent.postMessage({type:"pat:panel-settings",settings:state.panel_settings}, hostOrigin);
      if (requestedLibrary !== libraryId() || requestedArchive !== archived()) { refreshQueued = true; return; }
      setAssets(previous => mergeLibrary(previous, state));
      libraryCursor = state.revision || null; cursorView = requestedLibrary+":"+requestedArchive; libraryLoaded = true;
      if (!assets().some(asset => asset.id === selectedId())) setSelectedId("");
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
    libraryCursor = null; cursorView = null; libraryLoaded = false;
    setExportMode(false); setExportSelection(new Set());
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
  async function openCapture() {
    if (!ready()) return;
    const id=embedded ? preferredTarget || targetId() : targetId();
    setBusy(true);
    try {
      let group=null;
      if (modelEnabled() && nativeTargets().includes(id)) {
        try {group=await client.request("selection.group",{target_id:id});}
        catch(error) {if (!error.message.includes('尚未加载组运算')) throw error;}
      }
      setFormFolders(folders()); setFoldersLoading(false);
      setForm({ name: group?.recipe?.name || "", recipe:group?.recipe || null, group_signature:group?.signature, capture_target:id, category: category() === "全部组件" ? "" : category(), tags: "", note: "", preview: "", library_id:libraryId(),folder_id:folderId(),insert_mode:"new-body",kind:group?.recipe ? "solid" : kind() === "all" ? "unknown" : kind() });
      setCopySelection(!!target() && modelEnabled());
      setAutoPreview(true);
      setNotice(null);
      setDialog("capture");
    } catch(error) {showNotice(error.message,true);}
    finally {setBusy(false);}
  }
  function openEdit(asset = selected()) {
    setFormFolders(folders()); setFoldersLoading(false);
    setForm({ name: asset.name, recipe:asset.recipe, category: asset.category, tags: asset.tags, note: asset.note, preview: undefined,library_id:asset.library_id,folder_id:asset.folder_id,kind:asset.kind,insert_mode:asset.insert_mode || "new-body" });
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
      ...form(), id: selectedId(), target_id: capturing && form().recipe ? form().capture_target || preferredTarget || targetId() : targetId(), copy_selection: copySelection(), auto_preview:autoPreview(), preview_mode:'geometry', transport:"native",
      follow_active:!embedded && followActive() && !form().recipe,
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
        try { previewJobs.add(result); }
        catch (error) { showNotice("组件已保存。"+error.message, true); }
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
    setExportMode(false); setExportSelection(new Set());
    setArchived(value); setCategory("全部组件"); setSelectedId(""); await refresh();
  }
  async function archiveSelected() {
    const result = await operate(archived() ? "library.restore" : "library.archive", { id: selectedId() }, archived() ? "组件已恢复" : "组件已归档，可在归档中恢复");
    if (result) await refresh();
  }

  onMount(() => {
    client.connect(); previewClient.connect(); connectionClient.connect();
    poll = setInterval(() => { if (panelVisible && ready()) {refresh().catch(() => {});refreshConnection().catch(() => {});} }, 10000);
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
  onCleanup(() => { clearInterval(poll); clearTimeout(cardSizeTimer); clearTimeout(shownTimer); client.disconnect(); previewClient.disconnect(); connectionClient.disconnect(); previewJobs.stop(); window.removeEventListener("keydown",onSearchKey);window.removeEventListener("message",hostMessage);
    window.removeEventListener("pointerup", previewPointerUp, true);
    window.removeEventListener("pointercancel", closeHeldPreview, true);
    window.removeEventListener("blur", closeHeldPreview);
  });

  function AssetForm(props) {
    return <form class="asset-edit-form" onSubmit={save}><label>{t("组件名称")}<input required maxlength="120" autofocus placeholder={t("例如：六角螺栓 M8")} value={form().name} onInput={event => setField("name", event.currentTarget.value)}/></label>
      <div class="form-row"><label>{t("资产库")}<select aria-label={t("组件所属资产库")} onChange={event => changeFormLibrary(event.currentTarget.value)}><For each={libraries()}>{item => <option value={item.id} selected={form().library_id === item.id}>{item.name}</option>}</For></select></label><label>{t("组件类型")}<select aria-label={t("组件类型标注")} disabled={!!form().recipe} title={form().recipe ? t("连续布尔组仅支持实体组件") : t("直接保存时按实际选择自动识别；剪贴板保存由此标注")} onChange={event => setField("kind",event.currentTarget.value)}><For each={Object.entries(kindNames)}>{item => <option value={item[0]} selected={form().kind === item[0]}>{t(item[1])}</option>}</For></select></label></div>
      <Show when={supportsBoolean(form())}><Show when={form().recipe} fallback={<fieldset class="insert-mode-picker" title={t("布尔模式使用置入前选中的实体作为目标。原位置粘贴始终保持独立对象。")}><legend>{t("默认置入模式")}</legend><div class="insert-mode-options"><For each={Object.entries(insertModes)}>{item=><label><input type="radio" name="insert_mode" value={item[0]} checked={(form().insert_mode || "new-body") === item[0]} onChange={()=>setField("insert_mode",item[0])}/><span>{t(item[1])}</span></label>}</For></div></fieldset>}><fieldset class="group-recipe"><legend>{t("组：")}{form().recipe?.name}{t(" · 按顺序执行")}</legend><ol><For each={form().recipe?.parts}>{part=><li><span>{part.name}</span><small>{t(insertModes[part.mode])}</small></li>}</For></ol></fieldset></Show></Show>
      <label>{t("分组")}<select aria-label={t("组件所属分组")} disabled={foldersLoading()} onChange={event => setField("folder_id",event.currentTarget.value || null)}><option value="" selected={!form().folder_id}>{foldersLoading() ? t("正在加载分组…") : t("库根目录")}</option><For each={formFolders()}>{item => <option value={item.id} selected={form().folder_id === item.id}>{folderLabel(item.id,formFolders())}</option>}</For></select></label>
      <div class="form-row"><label>{t("分类")}<input maxlength="80" placeholder={t("未分类")} list="asset-categories" value={form().category} onInput={event => setField("category", event.currentTarget.value)}/></label><label>{t("标签")}<input maxlength="300" placeholder={t("螺栓，紧固件")} value={form().tags} onInput={event => setField("tags", event.currentTarget.value)}/></label></div><datalist id="asset-categories"><For each={categories()}>{name => <option value={name}/>}</For></datalist><label>{t("备注")}<textarea maxlength="2000" rows="3" placeholder={t("尺寸、用途或使用说明")} value={form().note} onInput={event => setField("note", event.currentTarget.value)}/></label>
      <Show when={props.capture}><label class="check-label" title={copySelection() ? t("直接读取选中模型，不占用系统剪贴板。") : t("从剪贴板保存，请先手动复制模型。")}><input type="checkbox" checked={copySelection()} disabled={busy() || !target() || !modelEnabled() || !!form().recipe} onChange={event => setCopySelection(event.currentTarget.checked)}/><span>{form().recipe ? t("直接保存选中的组") : t("直接保存选中的部件")}</span></label></Show>
      <label class="preview-picker">{t("预览图（可选）")}<input type="file" accept="image/jpeg" onChange={readPreview}/></label>
      <Show when={props.capture}><label class="check-label" title={t("从模型生成正交缩略图和三维预览，需要连接 Plasticity；上传的预览图优先使用。")}><input type="checkbox" checked={autoPreview()} disabled={busy()} onChange={event=>setAutoPreview(event.currentTarget.checked)}/><span>{t("自动生成几何预览")}</span></label></Show>
      <Show when={form().preview || (!props.capture && form().preview === undefined && selected()?.has_preview)}><div class="preview-editor"><img class="form-preview" src={form().preview || previewUrl(selected())} alt={t("组件预览")}/><button type="button" class="secondary" disabled={busy()} onClick={() => setField("preview", "")}>{t("移除预览图")}</button></div></Show>
      <Show when={notice()?.error}><p class="form-error" role="alert">{notice().message}</p></Show><div class="modal-actions"><button type="button" class="secondary" disabled={busy()} onClick={props.onCancel}>{t("取消")}</button><button type="submit" class="primary" disabled={!ready() || foldersLoading() || !form().name.trim()}>{busy() ? t("保存中…") : props.capture ? t("保存组件") : t("保存修改")}</button></div></form>;
  }

  return <div class={floatingPanel() ? "app-shell component-first floating-panel" : "app-shell component-first"} classList={{"sidebar-hover":sidebarMode() === "hover"}} style={{"--asset-size":`${cardSize()}px`}}>
    <aside class="sidebar">
      <Show when={sidebarMode() === "hover"}><button class="sidebar-hover-trigger" aria-label={t("展开侧栏")} title={t("悬停展开侧栏")}>☰</button></Show>
      <div class="sidebar-content">
      <div class="brand"><Cube /><div><strong>Plasticity</strong><span>COMPONENT LIBRARY</span></div></div>
      <div class="sidebar-label">{t("模型组件库")}</div>
      <button class={!archived() ? "nav-item active" : "nav-item"} onClick={() => toggleArchive(false)}>{t("◇ 全部组件 ")}<span>{!archived() ? assets().length : ""}</span></button>
      <div class="sidebar-label">{t("资产库")}</div>
      <nav class="library-tabs" aria-label={t("资产库")}><For each={libraries()}>{item => <button class={libraryId() === item.id ? "library-tab active" : "library-tab"} aria-pressed={libraryId() === item.id} disabled={busy()} onClick={() => switchLibrary(item.id)}>{item.name}<span>{item.count}</span></button>}</For><button class="library-tab add-library" disabled={!ready()} onClick={() => openOrganization("library")}>{t("＋ 新建库")}</button></nav>
      <div class="sidebar-label category-label">{t("分组")}</div>
      <button class={!folderId() ? "nav-item active" : "nav-item"} onClick={() => enterFolder(null)}>{t("⌂ 库根目录")}</button>
      <div class="folder-tree"><For each={orderedFolders()}>{item => <button class={folderId() === item.id ? "folder-nav active" : "folder-nav"} style={{"padding-left":`${10 + (folderPath(item.id).length-1)*12}px`}} onClick={() => enterFolder(item.id)} title={folderLabel(item.id)}>▱ {item.name}</button>}</For></div>
      <div class="sidebar-label category-label">{t("分类")}</div>
      <For each={categories()}>{name => <button class={!archived() && category() === name ? "nav-item category active" : "nav-item category"} onClick={() => setCategory(name)}>▦ {name}<span>{assets().filter(asset => asset.category === name).length}</span></button>}</For>
      <button class={archived() ? "nav-item active archive-link" : "nav-item archive-link"} onClick={() => toggleArchive(true)}>{t("▧ 已归档")}</button>
      <div class="sidebar-bottom"><span class={status() === "connected" ? "status-dot online" : "status-dot"}/><span>{status() === "connected" ? t("本地服务已连接") : status() === "connecting" ? t("连接服务中…") : t("服务断开，正在重连")}</span></div>
      </div>
    </aside>

    <main class="main-content">
      <Show when={connectionLost() || (status() === "connected" && !modelEnabled())}><section class="connection-alert" role="alert"><span class="connection-alert-icon" aria-hidden="true">!</span><div><strong>{connectionLost() ? t("后台连接已断开") : t("模型连接已停止")}</strong><p>{connectionLost() ? t("组件置入和保存暂不可用。请启动后台服务，连接恢复后可继续使用。") : t("组件置入、自动复制和模型操作已停用。请在控制中心恢复模型连接。")}</p></div><Show when={status() === "connected"}><a href="/?control=1" target="_blank" rel="noopener noreferrer">{t("打开控制中心")}</a></Show></section></Show>
      <Show when={ready() && modelEnabled() && !!target() && !nativeTargets().includes(targetId())}><section class="connection-alert" role="alert"><span class="connection-alert-icon" aria-hidden="true">!</span><div><strong>{t("原生模型插件未连接")}</strong><p>{t("请重新打开已安装插件的 Plasticity。直连恢复后，即可保存选中模型和置入组件。")}</p></div></section></Show><header class="page-header"><div><div class="eyebrow">YOUR REUSABLE GEOMETRY</div><h1>{archived() ? t("已归档") : t("模型组件库")}</h1><p>{t("保存一次，随时置入。在 Plasticity 里继续创作。")}</p></div>
        <label class="search-field"><span>⌕</span><input ref={searchInput} aria-label={t("搜索组件")} placeholder={t("搜索此库")} value={query()} onInput={event => setQuery(event.currentTarget.value)} onKeyDown={event => { if(event.key === "Enter" && filtered().length && (exportMode() || canInsert())) {event.preventDefault();exportMode() ? toggleExport(filtered()[0].id) : insert(filtered()[0]);} }}/></label>
        <div class="header-actions"><button class="secondary connection-settings-toggle" aria-label={t("连接与分组设置")} aria-expanded={connectionSettings()} onClick={()=>setConnectionSettings(!connectionSettings())}>⚙</button><button class="secondary" disabled={!ready() || !modelEnabled()} onClick={generatePreviews} title={previewPending() ? t("预览在后台生成，仍可保存和置入") : t("生成几何预览")}>{previewPending() ? t("预览中 · {p0}",{p0:previewPending()}) : t("生成预览")}</button><details class="export-menu"><summary aria-label={t("批量导出")}>{t("↑ 导出")}</summary><div><button disabled={!ready() || exporting() || !assets().length} onClick={startExportSelection}>{t("多选组件导出")}</button><button disabled={!ready() || exporting() || !categoryExport().length} title={t("导出当前库中此分类的所有组件，不受搜索、类型或分组筛选影响")} onClick={event=>{event.currentTarget.closest('details').open=false;exportComponents(categoryExport().map(asset=>asset.id));}}>{category() === "全部组件" ? t("导出当前库全部组件") : t("导出当前分类")} · {categoryExport().length}</button></div></details><button class="secondary" disabled={!ready()} onClick={() => importInput.click()}>{t("↓ 导入组件包")}</button><button class="primary" disabled={!ready() || !clipboardSupported()} onClick={openCapture}>{t("＋ 保存组件")}</button><Show when={floatingPanel()}><button class="panel-dismiss" aria-label={t("收起面板")} title={t("收起面板")} disabled={!ready()} onClick={hidePanel}>×</button></Show></div>
      </header>
      <input ref={importInput} class="hidden-input" type="file" accept=".patasset" onChange={importPackage}/>

      <Show when={connectionSettings()}><section class="target-bar" aria-label={t("目标窗口")}><div class="target-label"><span class="small-square">↗</span><div><strong>{t("置入目标")}</strong><span>{nativeTargets().includes(targetId()) ? t("原生模型直连 · 不占用剪贴板") : t("原生模型插件未连接")}</span></div></div>
        <select aria-label={t("Plasticity 目标窗口")} onChange={event => {setTargetId(event.currentTarget.value);setFollowActive(false);}} disabled={busy() || (embedded && !!preferredTarget)}><option value="" selected={!targetId()}>{targets().length ? t("请选择 Plasticity 窗口") : t("未发现 Plasticity 窗口")}</option><For each={targets()}>{item => <option value={item.id} selected={targetId() === item.id}>{item.title} · {item.mode === "cdp" ? "CDP" : t("原生")} · {item.target_id?.slice(0, 6) || item.hwnd}</option>}</For></select>
        <Show when={!embedded}><button class="secondary" disabled={!ready()} aria-pressed={followActive()} onClick={() => {setFollowActive(!followActive());refreshConnection().catch(error => showNotice(error.message,true));}}>{followActive() ? t("跟随激活窗口") : t("固定所选窗口")}</button></Show>
        <button class="icon-button" aria-label={t("刷新窗口")} disabled={!ready()} onClick={() => refreshConnection().catch(error => showNotice(error.message, true))}>↻</button>
        <Show when={target()?.mode === "cdp"}><button class="secondary" disabled={!ready()} onClick={() => operate("target.embed", { target_id: targetId() }, "面板已嵌入")}>{t("嵌入面板")}</button></Show>
        <Show when={embedded}><button class="secondary" onClick={hidePanel}>{t("收起")}</button></Show>
      </section>

      <div class="folder-toolbar"><nav class="breadcrumbs" aria-label={t("分组路径")}><button onClick={() => enterFolder(null)}>{currentLibrary()?.name || t("资产库")}</button><For each={folderPath(folderId())}>{item => <><span> / </span><button onClick={() => enterFolder(item.id)}>{item.name}</button></>}</For></nav><div><button disabled={!ready()} onClick={() => openOrganization("rename-library")}>{t("重命名库")}</button><Show when={folderId()}><button disabled={!ready()} onClick={() => openOrganization("rename-folder")}>{t("重命名分组")}</button></Show><button disabled={!ready()} onClick={() => openOrganization("folder")}>{t("＋ 新建分组")}</button></div></div>
      </Show>


      <Show when={notice()}><div class={notice().error ? "notice error" : "notice"} role={notice().error ? "alert" : "status"}><span>{notice().message}</span><button aria-label={t("关闭提示")} onClick={() => setNotice(null)}>×</button></div></Show>
      <Show when={!target()}><div class="connection-hint" title={t("打开 Plasticity，在连接设置中选择目标窗口。")}>{t("未连接 Plasticity 窗口")}</div></Show>

      <div class="library-toolbar"><div class="section-name">{category() === "全部组件" ? t("全部组件") : category()}<span>{filtered().length}{t(" 个组件")}</span></div><div class="type-tabs" aria-label={t("组件类型")}><For each={[["all",t("全部")],["solid","Solid"],["curve","Curve"],["mixed",t("混合")],["unknown",t("未标注")]]}>{item => <button class={kind() === item[0] ? "active" : ""} aria-pressed={kind() === item[0]} onClick={() => {setKind(item[0]);setSelectedId("");}}>{item[1]}</button>}</For><span>{t("直接保存时自动识别类型")}</span></div></div>
      <Show when={exportMode() || exporting()}><div class="batch-export-toolbar" role="group" aria-label={t("批量导出选择")}><Show when={exportMode()}><span>{t("已选 {count} 个组件",{count:selectedExport().length})}</span><button class="secondary" onClick={()=>setExportSelection(current=>new Set([...current,...filtered().map(asset=>asset.id)]))}>{t("全选当前结果")}</button><button class="secondary" disabled={!selectedExport().length} onClick={()=>setExportSelection(new Set())}>{t("清空选择")}</button><button class="primary" disabled={!ready() || exporting() || !selectedExport().length} onClick={()=>exportComponents(selectedExport())}>{exporting() ? t("正在打包…") : t("导出所选")}</button><button class="secondary" onClick={()=>{setExportMode(false);setExportSelection(new Set());}}>{t("完成选择")}</button></Show><Show when={exporting() && !exportMode()}><span role="status">{t("正在打包…")}</span></Show></div></Show>
      <Show when={!query().trim() && !archived() && childFolders().length}><section class="folder-grid" aria-label={t("子分组")}><For each={childFolders()}>{item => <button class="folder-card" onClick={() => enterFolder(item.id)}><span>▱</span><strong>{item.name}</strong><small>{assets().filter(asset => folderPath(asset.folder_id).some(parent => parent.id === item.id)).length}{t(" 个组件 · ")}{folders().filter(row => row.parent_id === item.id).length}{t(" 个子分组")}</small><span>→</span></button>}</For></section></Show>

      <Show when={heldPreview()} keyed>{preview => <section class="held-model-preview" role="status" aria-label={t("旋转预览 ") + preview.asset.name} style={{left:`${preview.left}px`,top:`${preview.top}px`}}><strong>{preview.asset.name}</strong><GeometryPreview asset={preview.asset} load={loadGeometry} heldOrigin={preview.origin}/><span>{t("按住右键移动旋转 · 松开恢复")}</span></section>}</Show>
      <div class="library-layout">
        <section class="asset-grid" aria-label={t("组件列表")}>
          <Show when={filtered().length} fallback={<div class="empty-state"><div class="empty-cube"><Cube /></div><h2>{query() || category() !== "全部组件" || kind() !== "all" ? t("没有匹配的组件") : archived() ? t("没有归档组件") : folderId() || childFolders().length ? t("当前分组没有直接保存的组件") : t("从你的第一个组件开始")}</h2><p>{query() ? t("换个关键词，或者查看全部组件。") : archived() ? t("归档的组件会保留模型数据，随时可以恢复。") : t("在 Plasticity 中选中模型，\n点击保存组件即可直接读取并保存。以后只需一点，即可原生置入。")}</p><Show when={!archived() && !query()}><button class="primary" disabled={!ready() || !clipboardSupported()} onClick={openCapture}>{t("＋ 保存组件")}</button></Show></div>}>
            <VirtualAssetGrid items={filtered()} size={cardSize()}>{asset => <article data-insert-mode={displayMode(asset)} class={selectedId() === asset.id ? "asset-card selected" : "asset-card"} classList={{"export-selected":exportMode() && exportSelection().has(asset.id)}}>
              <button class="asset-preview" data-insert-mode={displayMode(asset)} aria-label={(exportMode() ? t("选择 ") : t("置入 ")) + asset.name} aria-pressed={exportMode() ? exportSelection().has(asset.id) : undefined} aria-disabled={exportMode() ? false : !canInsert()} onClick={() => {if(exportMode())toggleExport(asset.id);else if(canInsert())insert(asset);}} onPointerDown={event=>previewPointerDown(event,asset)} onContextMenu={event=>event.preventDefault()}><Show when={asset.has_geometry_preview || asset.has_preview} fallback={<div class="model-placeholder"><Cube /><span>{t("原生模型")}</span></div>}><img loading="lazy" decoding="async" classList={{"geometry-thumbnail":!asset.has_preview}} src={previewUrl(asset)} alt={asset.name} draggable="false"/></Show><span class="asset-format">{t(kindNames[asset.kind])}</span><Show when={displayMode(asset) !== "new-body"}><span class="asset-insert-mode" title={asset.recipe ? t("按组内子部件顺序执行") : t("默认置入：") + modeLabel(asset)}>{modeLabel(asset)}</span></Show></button>
              <Show when={exportMode()}><label class="asset-export-check"><input type="checkbox" aria-label={t("选择 ")+asset.name} checked={exportSelection().has(asset.id)} onChange={()=>toggleExport(asset.id)}/></label></Show><div class="asset-body"><div class="asset-name">{asset.name}</div><div class="asset-meta" title={asset.recipe ? t("连续布尔 · ") + asset.recipe.parts.length + t(" 个子部件") : t("默认置入：") + modeLabel(asset)}>{asset.category}<span>{Math.max(1, Math.round(asset.bytes / 1024))} KB</span></div><div class="card-footer"><span title={asset.tags}>{asset.tags || ""}</span><button class="insert-button" aria-label={t("编辑 ") + asset.name} onClick={() => openEdit(asset)}>{t("编辑")}</button></div></div>
            </article>}</VirtualAssetGrid>
          </Show>
        </section>
        <Show when={detailsOpen() && selected()}><div class="asset-details-backdrop" onClick={()=>setDetailsOpen(false)}><aside class="details-panel" role="dialog" aria-modal="true" aria-label={t("组件详情")} onClick={event=>event.stopPropagation()}><button class="details-dismiss" aria-label={t("关闭组件详情")} onClick={()=>setDetailsOpen(false)}>×</button><Show when={selected()} fallback={<div class="detail-placeholder"><Cube /><h3>{t("组件详情")}</h3><p>{t("选择一个组件，查看信息或置入到当前模型。")}</p></div>}>
          <div class="detail-heading"><span>{t("编辑组件")}</span></div>
          <h2>{selected().name}</h2><span class="category-pill">{selected().category}</span>
          <GeometryPreview asset={selected()} load={loadGeometry}/>
          <dl><dt>{t("保存时间")}</dt><dd>{new Date(selected().created_at).toLocaleDateString(locale())}</dd><dt>{t("模型大小")}</dt><dd>{(selected().bytes / 1024).toFixed(1)} KB</dd><dt>{t("来源版本")}</dt><dd>{selected().source_version === "unknown" ? t("未记录") : selected().source_version}</dd><dt>{t("标签")}</dt><dd>{selected().tags || "—"}</dd></dl>
          <AssetForm capture={false} onCancel={()=>setDetailsOpen(false)}/>
          <Show when={!archived()}><button class="primary full-width" disabled={!canInsert()} onClick={() => insert(selected())}>{t("置入组件")}</button><button class="secondary full-width" disabled={!canInsert() || !!selected()?.recipe} title={selected()?.recipe ? t("组组件使用定位置入，保留部件顺序与组信息") : ""} onClick={() => insert(selected(), false)}>{t("原位置粘贴")}</button><button class="secondary full-width" disabled={!ready() || !modelEnabled() || !clipboardSupported()} onClick={() => operate("asset.copy", { id: selectedId() })}>{t("仅复制到剪贴板")}</button></Show>
          <div class="detail-actions"><a href={`${api}/api/assets/${selectedId()}/export`} download>{t("导出组件包")}</a></div><button class="archive-button" disabled={!ready()} onClick={archiveSelected}>{archived() ? t("恢复到组件库") : t("归档组件")}</button>
        </Show></aside></div></Show>
      </div>

      <footer class="page-footer component-browser-footer"><div class="browser-location"><span>{currentLibrary()?.name || t("资产库")}</span><span> / </span><span>{folderLabel(folderId())}</span><button aria-label={t("新建资产库")} title={t("新建资产库")} disabled={!ready()} onClick={()=>openOrganization("library")}>＋</button></div><div class="browser-display"><select aria-label={t("组件排序")} value={sortMode()} onChange={event=>setSortMode(event.currentTarget.value)}><option value="recent">{t("最近保存")}</option><option value="oldest">{t("最早保存")}</option><option value="name">{t("名称排序")}</option></select><label title={t("{p0}px · 自动保存",{p0:cardSize()})}>{t("大小")}<input type="range" aria-label={t("组件卡片大小")} aria-valuetext={t("第 {p0} 档，共 37 档，{p1} 像素",{p0:(cardSize()-112)/8+1,p1:cardSize()})} min="112" max="400" step="8" value={cardSize()} disabled={status() !== "connected"} onInput={changeCardSize} onChange={saveCardSize}/><output class="size-level">{(cardSize()-112)/8+1}/37</output></label><a href="/?control=1" target="_blank" rel="noopener noreferrer" title={t("控制中心")}>{t("控制中心 ↗")}</a></div></footer>
    </main>

    <Show when={dialog()}><div class="modal-backdrop" onClick={event => { if (event.target === event.currentTarget && !busy()) setDialog(null); }}><section class="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div class="modal-heading"><h2 id="dialog-title">{form().recipe ? t("保存组组件") : t("保存普通组件")}<span class="help-tip" tabindex="0" aria-label={t("保存帮助")} data-tip={copySelection() ? t("选中模型并完成当前工具后保存，无需系统剪贴板。") : t("先在 Plasticity 复制模型，再保存剪贴板中的组件。")}>?</span></h2><button class="icon-button" disabled={busy()} aria-label={t("关闭对话框")} onClick={() => setDialog(null)}>×</button></div>
      <AssetForm capture onCancel={()=>setDialog(null)}/>
    </section></div></Show>
    <Show when={organizationDialog()}><div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="organization-title"><h2 id="organization-title">{t({library:"新建资产库",folder:"新建分组","rename-library":"重命名资产库","rename-folder":"重命名分组"}[organizationDialog()])}</h2><p class="modal-description">{organizationDialog() === "folder" ? t("创建到：{p0}",{p0:folderLabel(folderId())}) : t("库和分组用于组织已保存的组件。")}</p><form onSubmit={saveOrganization}><label>{t("名称")}<input aria-label={t("库或分组名称")} autofocus required maxlength="120" value={organizationName()} onInput={event => setOrganizationName(event.currentTarget.value)}/></label><Show when={notice()?.error}><p class="form-error" role="alert">{notice().message}</p></Show><div class="modal-actions"><button type="button" class="secondary" disabled={busy()} onClick={() => setOrganizationDialog(null)}>{t("取消")}</button><button class="primary" type="submit" disabled={!ready() || !organizationName().trim()}>{t("保存")}</button></div></form></section></div></Show>
  </div>;
}
