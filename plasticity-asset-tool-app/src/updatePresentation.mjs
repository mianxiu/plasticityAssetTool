export function uiUpdateState(ui, revision, development=false) {
  if(development)return 'development';
  if(ui?.state!=='ready')return ui?.state || 'unknown';
  return ui.revision===revision ? 'current' : 'hot-update';
}

export function pluginUpdateState(plugins) {
  if(plugins?.check_error)return 'check-failed';
  const rows=plugins?.installations;
  if(!rows?.length)return 'not-detected';
  if(rows.some(row=>row.state==='update'))return 'install-required';
  if(rows.some(row=>row.state==='not-installed'))return 'not-installed';
  if(rows.some(row=>row.state!=='current'))return 'unverified';
  return 'current';
}

export function pluginRunningMessage(row) {
  if(!row.running)return '';
  return row.state==='update' || !row.installed ? '正在运行，请先保存并关闭此版本所有窗口' : '正在运行';
}

// Describe the next action, including states that must not look like success.
export function updateSummary(rows, plugins) {
  const states=rows.map(row=>row.state);
  if(plugins?.job?.state==='waiting')return '正在安装，请完成安装窗口中的确认';
  if(['failed','cancelled'].includes(plugins?.job?.state))return '上次操作未完成，请查看下方提示后重试';
  if(plugins?.check_error || states.some(state=>['unknown','check-failed'].includes(state)))return '检测尚未完成，请重新检测';
  if(states.includes('restart-required'))return '下一步：重启组件库后台';
  if(states.some(state=>['install-required','not-installed'].includes(state)))return '下一步：安装或更新下方对应版本的插件';
  if(states.some(state=>['unverified','not-detected'].includes(state)))return '下一步：检查下方的插件安装信息';
  if(states.some(state=>['not-built','building'].includes(state)))return '下一步：等待界面构建完成';
  if(states.includes('hot-update'))return '界面将在当前操作结束后自动更新';
  if(plugins?.job?.state==='complete' && ['install','update','reinstall'].includes(plugins.job.action))return '插件安装已完成，重新打开对应 Plasticity 版本后生效';
  return '本地文件已就绪，无需手动更新';
}
