const fs=require('fs'),vm=require('vm'),assert=require('assert'),{EventEmitter}=require('events');
const source=fs.readFileSync(process.argv[2],'utf8');
async function scenario(kind) {
  const handlers={},results=[];let created,visible=false,probes=0;
  const win={isDestroyed:()=>false,webContents:{
    on:(name,fn)=>handlers[name]=fn,
    getURL:()=> 'file:///app/.webpack/renderer/app_window/index.html',
    executeJavaScript:async expression=>{
      if(expression.includes('isVisible()'))return visible;
      const match=expression.match(/toggle\((true|false)\)/);
      if(match){results.push(match[1]==='true');visible=!visible;return {visible};}
    }}};
  const http={get:(url,receive)=>{
    assert.strictEqual(url.pathname,'/api/health');probes++;
    const request=new EventEmitter();request.destroy=()=>request.emit('close');
    setImmediate(()=>{
      if(kind==='offline'){request.emit('error',new Error('connection refused'));request.emit('close');return;}
      const response=new EventEmitter();response.statusCode=200;receive(response);
      response.emit('data',JSON.stringify({app:kind==='valid'?'plasticity-asset-tool':'other-server'}));
      response.emit('end');request.emit('close');
    });return request;
  }};
  vm.runInNewContext(source,{URL,console,setTimeout,clearTimeout,module:{exports:{}},
    require:name=>name==='electron'?{app:{on:(event,fn)=>created=fn}}:name==='http'?http:{}});
  created({},win);
  let prevented=false;
  const key={type:'keyDown',key:'Tab',code:''};
  handlers['before-input-event']({preventDefault(){prevented=true}},key);
  await new Promise(resolve=>setTimeout(resolve,30));
  assert(prevented);assert.deepStrictEqual(results,[kind==='valid']);
  handlers['before-input-event']({preventDefault(){}},key);
  await new Promise(resolve=>setTimeout(resolve,30));
  assert.strictEqual(visible,false);assert.strictEqual(probes,1);
  handlers['before-input-event']({preventDefault(){throw Error('modifier must be ignored')}},{...key,shift:true});
}
async function previewScenario(fail=false) {
  let created, completed, captures=0;const handlers={};
  const win={isDestroyed:()=>false,webContents:{on:(name,fn)=>handlers[name]=fn,
    getURL:()=> 'file:///app/.webpack/renderer/app_window/index.html',
    executeJavaScript:async expression=>{
      if(expression.includes('previewRect'))return {x:200,y:50,width:800,height:650};
      if(expression.includes('completePreview'))completed=expression;
    },capturePage:async rect=>{
      captures++;assert.deepStrictEqual(JSON.parse(JSON.stringify(rect)),{x:200,y:50,width:800,height:650});
      if(fail)throw Error('capture unavailable');
      return {isEmpty:()=>false,resize:options=>{assert.strictEqual(options.width,512);return {toJPEG:quality=>{assert.strictEqual(quality,75);return Buffer.from([255,216,1]);}}}};
    }}};
  vm.runInNewContext(source,{URL,console,Buffer,setTimeout,clearTimeout,module:{exports:{}},require:name=>name==='electron'?{app:{on:(event,fn)=>created=fn}}:{}});
  created({},win);
  await handlers['console-message']({},0,'PAT_PREVIEW_REQUEST:preview-id');
  assert.strictEqual(captures,1);assert(completed.includes(fail?',null)': 'data:image/jpeg;base64,'));
  await handlers['console-message']({},0,'PAT_PREVIEW_REQUEST:invalid"id');assert.strictEqual(captures,1);
}
(async()=>{for(const kind of ['valid','offline','wrong-app'])await scenario(kind);await previewScenario();await previewScenario(true);console.log('MAIN_HEALTH_OK');})().catch(error=>{console.error(error);process.exitCode=1;});
