function startNativeWorker(win, baseURL, target) {
  const http = require('http'), token = require('crypto').randomUUID();
  const debuggerAPI = win.webContents.debugger, group = 'pat-native-'+token;
  let editor, paste, operationType, booleanFactory, stopped=false, timer, result=null;
  const call = (method,params) => debuggerAPI.sendCommand(method,params);
  async function discover() {
    if (!debuggerAPI.isAttached()) debuggerAPI.attach('1.3');
    const fn = await call('Runtime.evaluate',{expression:'document.querySelector("command-log")?.handleCommandStarted',objectGroup:group});
    if (!fn.result?.objectId) throw new Error('原生命令接口不可用');
    const properties = await call('Runtime.getProperties',{objectId:fn.result.objectId,ownProperties:true});
    const scopes = properties.internalProperties?.find(p=>p.name==='[[Scopes]]')?.value.objectId;
    if (!scopes) throw new Error('原生命令上下文不可用');
    const rows = await call('Runtime.getProperties',{objectId:scopes,ownProperties:true});
    for (const row of rows.result) {
      if (!row.value?.objectId || !row.value.description?.startsWith('Closure')) continue;
      const values = await call('Runtime.getProperties',{objectId:row.value.objectId,ownProperties:true});
      for (const value of values.result) {
        if (value.name==='editor' && value.value?.objectId) editor=value.value.objectId;
        if (value.name==='PasteCommand' && value.value?.objectId) paste=value.value.objectId;
        if (value.name==='OperationType' && value.value?.objectId) operationType=value.value.objectId;
        if (value.name==='BooleanFactory' && value.value?.objectId) booleanFactory=value.value.objectId;
      }
    }
    if (!editor || !paste) {editor=null;throw new Error('当前版本不支持原生模型传输');}
  }
  const send = data => new Promise((resolve,reject)=>{
    const body=JSON.stringify(data);
    const request=http.request(new URL('/api/native/worker',baseURL),{method:'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}},response=>{
      let text='';response.on('data',chunk=>{text+=chunk;if(text.length>96*1024*1024)request.destroy(new Error('模型任务过大'));});
      response.on('end',()=>{try{if(response.statusCode!==200)throw new Error('后台未连接');resolve(JSON.parse(text));}catch(e){reject(e);}});
      response.on('error',reject);
    });
    request.setTimeout(5000,()=>request.destroy(new Error('后台超时')));
    request.on('error',reject);request.end(body);
  });
  async function poll() {
    if (stopped || win.isDestroyed()) return;
    try {
      if (!editor) await discover();
      const response=await send({target_id:target,token,result,capabilities:['boolean-placement-v1','group-recipe-v1']});result=null;
      if (response.job) {
        const job=response.job;
        if (!/^[a-f0-9]{32}$/.test(job.id) || !['capture','insert','inspect-group','capture-group'].includes(job.action)) throw new Error('无效模型任务');
        try {
          // Scope references can expire after a native command/frame lifecycle.
          // Discover afresh before execution; never retry an executed command.
          editor=null;paste=null;operationType=null;booleanFactory=null;
          await discover();
          const declarations={
            capture:'function(){return globalThis.__plasticityAssetTransport.captureSelection(this)}',
            'inspect-group':'function(){return globalThis.__plasticityAssetTransport.inspectGroup(this)}',
            'capture-group':'function(signature){return globalThis.__plasticityAssetTransport.captureGroup(this,signature)}',
            insert:'function(args,PasteCommand,OperationType,BooleanFactory){return globalThis.__plasticityAssetTransport.insertModel(this,args,PasteCommand,OperationType,BooleanFactory)}'
          };
          const declaration=declarations[job.action];
          const args=job.action==='insert'?[{value:{model:job.model,placement:job.placement,insert_mode:job.insert_mode,recipe:job.recipe}},{objectId:paste},operationType?{objectId:operationType}:{value:null},booleanFactory?{objectId:booleanFactory}:{value:null}]:job.action==='capture-group'?[{value:job.signature}]:[];
          if (job.action==='insert') {
            win.show();win.focus();
            await win.webContents.executeJavaScript('(()=>{window.__plasticityAssetToolPanel?.hide();return true})()');
          }
          const executed=await call('Runtime.callFunctionOn',{objectId:editor,functionDeclaration:declaration,arguments:args,returnByValue:true,awaitPromise:true,objectGroup:group});
          if (executed.exceptionDetails) {
            const details=executed.exceptionDetails;
            throw new Error((details.exception?.description || details.text).split('\n')[0].replace(/^Error: /,''));
          }
          result={id:job.id,value:executed.result.value};
        } catch(error) {result={id:job.id,error:error.message};}
      }
    } catch(error) { /* Reconnect after a backend stop. Never retry a sent command. */ }
    if (!stopped) timer=setTimeout(poll,result?10:750);
  }
  win.webContents.on('destroyed',()=>{stopped=true;clearTimeout(timer);});
  win.webContents.on('did-start-navigation',(_event,_url,_inPlace,isMainFrame)=>{
    if (isMainFrame) {editor=null;paste=null;call('Runtime.releaseObjectGroup',{objectGroup:group}).catch(()=>{});}
  });
  debuggerAPI.on('detach',()=>{editor=null;paste=null;});
  poll();
}
