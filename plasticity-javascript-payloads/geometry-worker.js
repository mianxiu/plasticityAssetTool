function startGeometryWorker(win, baseURL, target) {
  const http = require('http');
  const token = require('crypto').randomUUID();
  let stopped = false, timer, result = null;
  const send = data => new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    const request = http.request(new URL('/api/geometry/worker', baseURL), {method:'POST', headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}}, response => {
      let text = '';
      response.on('data', chunk => {text += chunk;if(text.length > 96 * 1024 * 1024)request.destroy(new Error('预览任务过大'));});
      response.on('end', () => {try {if(response.statusCode !== 200)throw new Error('预览后台未连接');resolve(JSON.parse(text));}catch(e){reject(e);}});
      response.on('error', reject);
    });
    request.setTimeout(3000, () => request.destroy(new Error('预览后台超时')));
    request.on('error', reject);request.end(body);
  });
  async function poll() {
    if (stopped || win.isDestroyed()) return;
    try {
      const response = await send({target_id:target,token,result});
      result = null;
      if (response.job) {
        const job = response.job;
        if (!/^[a-f0-9]{32}$/.test(job.id) || !Array.isArray(job.parts)) throw new Error('无效的预览任务');
        try {
          const mesh = await win.webContents.executeJavaScript('window.__plasticityAssetGeometry.convert('+JSON.stringify(job.parts)+')');
          result = {id:job.id,mesh};
        } catch(error) {result = {id:job.id,error:error.message};}
      }
    } catch(error) { /* Backend may be stopped by the tray; reconnect quietly. */ }
    if (!stopped) timer = setTimeout(poll, result ? 10 : 750);
  }
  win.webContents.on('destroyed', () => {stopped = true;clearTimeout(timer);});
  poll();
}
