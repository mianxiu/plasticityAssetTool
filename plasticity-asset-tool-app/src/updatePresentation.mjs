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
