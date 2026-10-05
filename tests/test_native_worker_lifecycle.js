const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {EventEmitter}=require('node:events');
const source=fs.readFileSync('plasticity-javascript-payloads/native-worker.js','utf8');
const flush=async()=>{for(let i=0;i<25;i++)await Promise.resolve();};
function worker(target) {
  const requests=[],timers=[],calls=[];let destroyed=false,attached=false,hideHook;
  const debuggerAPI=new EventEmitter();
  debuggerAPI.isAttached=()=>attached;debuggerAPI.attach=()=>{attached=true;};
  debuggerAPI.sendCommand=async(method,params)=>{
    if(method==='Runtime.evaluate')return {result:{objectId:'fn'}};
    if(method==='Runtime.getProperties') {
      if(params.objectId==='fn')return {internalProperties:[{name:'[[Scopes]]',value:{objectId:'scopes'}}]};
      if(params.objectId==='scopes')return {result:[{value:{objectId:'closure',description:'Closure'}}]};
      return {result:['editor','PasteCommand','CopyWithPlacementCommand','Cancel','OperationType','BooleanFactory'].map(name=>({name,value:{objectId:name}}))};
    }
    if(method==='Runtime.callFunctionOn'){calls.push(params);return {result:{value:{started:true}}};}
    return {};
  };
  const webContents=new EventEmitter();webContents.debugger=debuggerAPI;
  webContents.executeJavaScript=async()=>{hideHook?.();};
  const win={webContents,isDestroyed:()=>destroyed,show(){},focus(){}};
  const http={request(_url,_options,callback){
    const req=new EventEmitter();req.setTimeout=()=>{};req.destroy=error=>req.emit('error',error);
    req.end=body=>requests.push({data:JSON.parse(body),reply(job,status=200){
      const response=new EventEmitter();response.statusCode=status;callback(response);
      response.emit('data',JSON.stringify({job,wait_supported:true}));response.emit('end');
    }});return req;
  }};
  const intervals=new Set();
  const context={setInterval(fn){intervals.add(fn);return fn;},clearInterval(fn){intervals.delete(fn);},URL,Buffer,require:name=>name==='http'?http:require(name),setTimeout:fn=>{timers.push(fn);return fn;},clearTimeout:fn=>{const i=timers.indexOf(fn);if(i>=0)timers.splice(i,1);}};
  vm.runInNewContext(source,context);context.startNativeWorker(win,'http://127.0.0.1:15150',target);
  return {requests,calls,intervals,async tick(){assert(timers.length);timers.shift()();await flush();},navigate(){webContents.emit('did-start-navigation',{},'url',false,true);},detach(){attached=false;debuggerAPI.emit('detach');},destroy(){destroyed=true;webContents.emit('destroyed');},onHide(fn){hideHook=fn;}};
}
const job=id=>({id:id.repeat(32),action:'insert',model:'payload',placement:true});
(async()=>{
  const first=worker('hwnd:42'),second=worker('hwnd:43');await flush();
  assert.equal(first.requests[0].data.target_id,'hwnd:42');assert.equal(second.requests[0].data.target_id,'hwnd:43');
  assert.notEqual(first.requests[0].data.token,second.requests[0].data.token);
  first.requests[0].reply(job('a'));second.requests[0].reply(job('b'));await flush();
  assert.equal(first.calls.length,1);assert.equal(second.calls.length,1);
  await first.tick();const receipt=first.requests[1].data.result;assert.equal(receipt.id,'a'.repeat(32));
  first.requests[1].reply(null,503);await flush();await first.tick();
  assert.deepEqual(first.requests[2].data.result,receipt,'Reconnect preserves the receipt');
  first.requests[2].reply(null);await flush();
  assert.equal(first.calls.length,1,'A lost receipt must never repeat the insertion');
  first.destroy();second.destroy();

  for(const transition of ['navigate','detach','destroy']) {
    const current=worker('hwnd:44');await flush();const oldToken=current.requests[0].data.token;
    current[transition]();current.requests[0].reply(job('c'));await flush();
    assert.equal(current.calls.length,0,`${transition}: stale HTTP replies cannot execute`);
    if(transition!=='destroy') {
      await current.tick();assert.notEqual(current.requests[1].data.token,oldToken);
      assert.equal(current.requests[1].data.result,null);current.destroy();
    }
  }
  const pointWorker=worker('hwnd:46');await flush();
  assert(pointWorker.requests[0].data.capabilities.includes('base-point-v1'));
  pointWorker.requests[0].reply({id:'e'.repeat(32),action:'capture',base_mode:'pick'});await flush();
  assert.equal(pointWorker.calls[0].arguments[0].value,true);
  assert.equal(pointWorker.calls[0].arguments[1].objectId,'CopyWithPlacementCommand');
  assert.equal(pointWorker.intervals.size,0,'Interactive heartbeat is cleaned after the command');pointWorker.destroy();
  const rebaseWorker=worker('hwnd:47');await flush();
  assert(rebaseWorker.requests[0].data.capabilities.includes('asset-base-point-v1'));
  rebaseWorker.requests[0].reply({id:'f'.repeat(32),action:'rebase',base_mode:'pick',model:'saved-model'});await flush();
  assert.equal(rebaseWorker.calls[0].arguments[0].value.model,'saved-model');
  assert.equal(rebaseWorker.calls[0].arguments[3].objectId,'Cancel');
  assert.equal(rebaseWorker.intervals.size,0);rebaseWorker.destroy();
  const changedDuringHide=worker('hwnd:45');await flush();
  changedDuringHide.onHide(()=>changedDuringHide.navigate());
  changedDuringHide.requests[0].reply(job('d'));await flush();
  assert.equal(changedDuringHide.calls.length,0,'Recheck context immediately before the native invocation');
  changedDuringHide.destroy();
  console.log('Native workers: window isolation, reconnect receipts and stale-context rejection verified');
})().catch(error=>{console.error(error);process.exitCode=1;});
