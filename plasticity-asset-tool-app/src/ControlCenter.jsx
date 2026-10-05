import {t, locale, setLocale} from "./i18n";
import { createSignal, For, onCleanup, onMount, Show } from "solid-js";
import { Cube } from "./Home";
import "./ControlCenter.css";

export function ControlCenter() {
  const [state,setState] = createSignal(null);
  const [online,setOnline] = createSignal(false);
  const [loaded,setLoaded] = createSignal(false);
  const [busy,setBusy] = createSignal(false);
  const [notice,setNotice] = createSignal("");
  const [quitting,setQuitting] = createSignal(false);
  const [confirmQuit,setConfirmQuit] = createSignal(false);
  const [plugins,setPlugins] = createSignal(null);
  const [detecting,setDetecting] = createSignal(false);
  const [installPath,setInstallPath] = createSignal("");
  const [confirmPlugin,setConfirmPlugin] = createSignal(null);
  const pluginPending=()=>plugins()?.job?.state === "waiting";
  const pluginLabels={"not-installed":()=>t("未安装"),current:()=>t("已是最新版"),update:()=>t("可更新"),"backup-missing":()=>t("已安装，但缺少可验证备份")};
  const operationLabels={install:()=>t("安装插件"),update:()=>t("更新插件"),restore:()=>t("恢复原始入口")};
  let timer, loading=false, disposed=false;
  async function refresh() {
    if (loading || quitting()) return;
    loading=true;
    try {
      const response=await fetch("/api/service",{cache:"no-store",signal:AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error("服务状态暂不可用");
      const data=await response.json();
      if (!disposed) {setState(data);setOnline(true);if(data.plugin_manager)setPlugins(data.plugin_manager);}
    } catch {if (!disposed) setOnline(false);}
    finally {loading=false;if (!disposed) setLoaded(true);}
  }
  async function command(action,args={}) {
    if (busy() || !online()) return;
    setBusy(true);setNotice("");
    try {
      const response=await fetch("/api/service",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,args}),signal:AbortSignal.timeout(10000)});
      const result=await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "操作失败");
      if (action === "service.quit") {setQuitting(true);setOnline(false);setConfirmQuit(false);}
      else {setNotice(result.data.message || "连接状态已更新");await refresh();}
    } catch(error) {setNotice(error.message);}
    finally {setBusy(false);}
  }
  async function pluginCommand(action,args={}) {
    const response=await fetch("/api/service",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,args}),signal:AbortSignal.timeout(30000)});
    const result=await response.json();
    if(!response.ok || !result.ok)throw new Error(result.error || t("操作失败"));
    if(!disposed)setPlugins(result.data);
  }
  async function detectPlugins(custom=false) {
    if(detecting() || pluginPending())return;
    setDetecting(true);
    try {await pluginCommand("service.plugin_detect",custom ? {path:installPath().trim()} : {});}
    catch(error) {if(!disposed)setNotice(error.message);}
    finally {if(!disposed)setDetecting(false);}
  }
  async function installPlugin() {
    const choice=confirmPlugin();
    if(!choice || busy() || pluginPending())return;
    setBusy(true);setNotice("");
    try {await pluginCommand("service.plugin_install",{id:choice.row.id,operation:choice.operation});setConfirmPlugin(null);}
    catch(error) {setNotice(error.message);}
    finally {setBusy(false);}
  }
  const enabled=()=>state()?.model_enabled !== false;
  const elapsed=()=>{const minutes=Math.floor((state()?.uptime_seconds || 0)/60);return minutes<60 ? t("{p0} 分钟",{p0:minutes}) : t("{p0} 小时 {p1} 分钟",{p0:Math.floor(minutes/60),p1:minutes%60});};
  const previousTitle=document.title;
  onMount(()=>{document.title="Plasticity Asset Tool — Control Center";refresh().then(()=>{if(state()?.plugin_manager)detectPlugins();});timer=setInterval(refresh,3000);});
  onCleanup(()=>{disposed=true;clearInterval(timer);document.title=previousTitle;});
  return <div class="control-shell">
    <aside class="control-sidebar">
      <div class="brand"><Cube/><div><strong>Plasticity</strong><span>COMPONENT LIBRARY</span></div></div>
      <div class="sidebar-label">{t("工作空间")}</div>
      <div class="nav-item active">{t("◈ 控制中心")}</div>
      <a class="nav-item" href="/">{t("◇ 模型组件库")}</a>
      <div class="control-sidebar-bottom"><span class={`status-dot ${online() ? "live" : "offline"}`}/>{quitting() ? t("后台已退出") : online() ? t("本地服务运行中") : loaded() ? t("服务未连接") : t("正在连接")}</div>
    </aside>
    <main class="control-main">
      <header class="control-heading"><div><span class="control-eyebrow">{t("后台服务")}</span><h1>{t("控制中心")}</h1><p>{t("查看模型连接，管理组件库的运行状态。")}</p><small class="control-version">{t("工具版本")} · {state()?.app_version ? `v${state().app_version}` : "—"}<Show when={state()?.app_version && !online()}> · {t("服务离线")}</Show></small></div><div class="control-actions"><button class="secondary-button" disabled={!online() || busy()} onClick={()=>command("service.open_control")}>{t("打开独立窗口")}</button><a class="primary-button" href="/">{t("打开组件库 ↗")}</a></div></header>
      <Show when={loaded() && (!online() || !enabled())}><section class="connection-alert" role="alert"><span class="connection-alert-icon" aria-hidden="true">!</span><div><strong>{quitting() ? t("后台服务已停止") : !online() ? t("后台连接已断开") : t("模型连接已停止")}</strong><p>{!online() ? t("组件置入和保存暂不可用。请重新启动后台服务。") : t("组件置入、自动复制和模型操作已停用；恢复连接后可继续使用。")}</p></div><Show when={online()}><button class="secondary-button" disabled={busy()} onClick={()=>command("service.connection",{enabled:true})}>{t("恢复模型连接")}</button></Show></section></Show>
      <Show when={notice()}><div class="control-banner" role="status">{notice()}</div></Show>
      <div class="control-stats">
        <section class="control-card"><span class="control-card-label">{t("本地服务")}</span><strong><span class={`status-dot ${online() ? "live" : "offline"}`}/>{quitting() ? t("已退出") : online() ? t("运行中") : loaded() ? t("未连接") : t("连接中")}</strong><small>{online() ? t("已运行 {p0}",{p0:elapsed()}) : t("服务就绪后自动连接")}</small></section>
        <section class="control-card"><span class="control-card-label">{t("Plasticity 窗口")}</span><strong>{online() ? state()?.targets.length || 0 : "—"}<em>{t("个可用窗口")}</em></strong><small>{enabled() ? t("原生剪贴板模式") : t("模型操作已暂停")}</small></section>
        <section class="control-card"><span class="control-card-label">{t("模型组件")}</span><strong>{online() ? state()?.component_count || 0 : "—"}<em>{t("个组件")}</em></strong><small>{state()?.libraries.length || 0}{t(" 个组件库 · 数据保存在本机")}</small></section>
      </div>
      <section class="control-section plugin-section">
        <div class="control-section-heading"><div><h2>{t("插件安装")}</h2><p>{t("检测版本和目录，安装后重新启动 Plasticity 即可使用 Tab 面板。")}</p></div><button class="secondary-button" disabled={!online() || detecting() || pluginPending()} onClick={()=>detectPlugins()}>{detecting() ? t("正在检测…") : t("检测安装")}</button></div>
        <Show when={plugins()} fallback={<p>{t("请重启后台，启用插件安装管理")}</p>}>
          <p class="plugin-supported">{t("支持自动安装：")}{plugins()?.supported_versions?.join(", ")}</p>
          <div class="plugin-directory"><input aria-label={t("Plasticity 安装目录")} placeholder={t("其他目录：输入 Plasticity 安装目录完整路径")} value={installPath()} onInput={event=>setInstallPath(event.currentTarget.value)} /><button class="secondary-button" disabled={!online() || detecting() || pluginPending() || !installPath().trim()} onClick={()=>detectPlugins(true)}>{t("检测目录")}</button></div>
          <Show when={plugins()?.installations?.length} fallback={<p>{detecting() ? t("正在检测…") : t("未检测到安装，可输入其他安装目录。")}</p>}>
            <div class="plugin-installations"><For each={plugins()?.installations}>{row=><article class="plugin-installation"><div><strong>Plasticity {row.version}</strong><small class="plugin-path">{row.path}</small><span class="plugin-status">{!row.supported ? t("此版本尚未支持自动安装") : pluginLabels[row.state]?.() || row.state}<Show when={row.running}> · {t("正在运行，请先保存并关闭此版本所有窗口")}</Show></span></div><div class="control-actions"><Show when={!row.installed}><button class="secondary-button" disabled={!row.can_install || busy() || detecting() || pluginPending()} onClick={()=>setConfirmPlugin({row,operation:"install"})}>{t("安装插件")}</button></Show><Show when={row.state === "update"}><button class="secondary-button" disabled={!row.can_update || busy() || detecting() || pluginPending()} onClick={()=>setConfirmPlugin({row,operation:"update"})}>{t("更新插件")}</button></Show><Show when={row.can_restore}><button class="secondary-button" disabled={busy() || detecting() || pluginPending()} onClick={()=>setConfirmPlugin({row,operation:"restore"})}>{t("恢复原始入口")}</button></Show></div></article>}</For></div>
          </Show>
          <Show when={plugins()?.job}><div class={`plugin-job plugin-job-${plugins()?.job.state}`} role="status"><strong>{plugins()?.job.state === "waiting" ? t("等待安装确认 / Windows 权限") : plugins()?.job.state === "complete" ? t("操作完成") : plugins()?.job.state === "cancelled" ? t("操作已取消") : t("操作失败")}</strong><span>{plugins()?.job.message}</span><small>{t("备份：")}{plugins()?.job.backup}</small></div></Show>
        </Show>
      </section>
      <section class="control-section">
        <div class="control-section-heading"><div><h2>{t("模型连接")}</h2><p>{enabled() ? t("打开模型窗口即可使用内嵌组件库。") : t("连接已暂停；浏览和整理组件仍然可用。")}</p></div><button class="secondary-button" onClick={refresh} disabled={!online() || busy()}>{t("↻ 刷新窗口")}</button></div>
        <Show when={online() && state()?.targets.length} fallback={<div class="control-empty"><Cube/><strong>{online() ? t("尚未发现 Plasticity 模型窗口") : t("等待服务连接")}</strong><p>{t("打开 Plasticity 后，这里会显示可用窗口。")}</p></div>}>
          <div class="model-window-list"><For each={state()?.targets}>{target=><article class="model-window-row"><Cube/><div><strong>{target.title}</strong><small>{target.mode === "desktop" ? t("原生模型窗口") : t("调试接口")} · {enabled() ? t("可进行模型操作") : t("模型操作暂停")}</small></div><button class="secondary-button" disabled={busy() || target.mode !== "desktop"} onClick={()=>command("service.focus",{target_id:target.id})}>{t("切换到窗口 ↗")}</button></article>}</For></div>
        </Show>
      </section>
      <section class="control-section control-panel-settings">
        <h2>{t("面板位置")}</h2><div class="control-position-options" role="group" aria-label={t("面板位置")}><For each={[["fixed",t("固定位置")],["cursor",t("鼠标位置")]]}>{item=><button class="secondary-button" aria-pressed={(state()?.panel_settings?.position || "fixed") === item[0]} disabled={!online() || busy()} onClick={()=>command("service.panel_settings",{position:item[0]})}>{item[1]}</button>}</For></div>
      </section>
      <section class="control-section control-panel-settings">
        <h2>{t("左侧导航")}</h2><div class="control-position-options" role="group" aria-label={t("左侧导航")}><For each={[["fixed",t("固定展开")],["hover",t("悬停展开")]]}>{item=><button class="secondary-button" aria-pressed={(state()?.panel_settings?.sidebar_mode || "fixed") === item[0]} disabled={!online() || busy()} onClick={()=>command("service.panel_settings",{sidebar_mode:item[0]})}>{item[1]}</button>}</For></div>
      </section>
      <section class="control-section control-management">
        <div><h2>{t("连接与运行")}</h2><p>{t("托盘图标始终保留后台入口，双击可打开此控制中心。")}</p><small>{online() ? t("{p0} 个面板连接",{p0:state()?.panel_clients || 0}) : t("服务离线")}</small><Show when={online() && !state()?.tray_available}><p class="control-warning">{t("托盘暂不可用：")}{state()?.tray_error || t("正在初始化")}</p></Show></div>
        <div class="control-actions"><button class="secondary-button" disabled={!online() || busy()} onClick={()=>command("service.connection",{enabled:!enabled()})}>{enabled() ? t("暂停模型连接") : t("恢复模型连接")}</button><button class="control-quit" disabled={!online() || busy()} onClick={()=>setConfirmQuit(true)}>{t("退出后台服务")}</button></div>
      </section>
      <section class="control-section control-panel-settings"><h2>{t("语言")}</h2><div class="control-position-options" role="group" aria-label={t("语言")}><For each={[["zh-CN",t("中文")],["en","English"]]}>{item=><button class="secondary-button" aria-pressed={locale() === item[0]} onClick={()=>setLocale(item[0])}>{item[1]}</button>}</For></div></section>
      <footer class="control-footer">{t("关闭此页面会保留后台服务。退出后台后，模型置入需重新启动服务。")}</footer>
    </main>
    <Show when={confirmPlugin()}><div class="dialog-backdrop"><section class="dialog control-quit-dialog" role="dialog" aria-modal="true" aria-labelledby="plugin-title"><h2 id="plugin-title">{operationLabels[confirmPlugin().operation]()}</h2><p>Plasticity {confirmPlugin().row.version}<br/><span class="plugin-path">{confirmPlugin().row.path}</span></p><p>{confirmPlugin().operation === "restore" ? t("将恢复已验证的原始入口，组件数据库保留。") : t("将修改此版本的内嵌入口，并自动保存可恢复备份。")}</p><p>{t("请先自行保存并关闭该版本所有窗口；继续后在安装窗口确认 Windows 权限。")}</p><div class="control-actions"><button class="secondary-button" disabled={busy()} onClick={()=>setConfirmPlugin(null)}>{t("取消")}</button><button class="primary-button" disabled={busy()} onClick={installPlugin}>{t("继续安装流程")}</button></div></section></div></Show>
    <Show when={confirmQuit()}><div class="dialog-backdrop"><section class="dialog control-quit-dialog" role="dialog" aria-modal="true" aria-labelledby="quit-title"><h2 id="quit-title">{t("退出组件库后台？")}</h2><p>{t("组件数据会保留。Plasticity 会继续运行，组件库置入功能将在重新启动后台后恢复。")}</p><div class="control-actions"><button class="secondary-button" onClick={()=>setConfirmQuit(false)}>{t("取消")}</button><button class="control-quit" disabled={busy()} onClick={()=>command("service.quit")}>{t("退出后台服务")}</button></div></section></div></Show>
  </div>;
}
