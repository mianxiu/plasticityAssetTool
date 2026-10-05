const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const timers=new Map(),sockets=[],states=[],events=[];let timerId=0;
class Socket {
  static OPEN=1;static CONNECTING=0;
  constructor(){this.readyState=0;this.listeners={};this.sent=[];sockets.push(this);}
  addEventListener(type,callback){this.listeners[type]=callback;}
  emit(type,data){this.listeners[type]?.(data);}
  send(data){this.sent.push(JSON.parse(data));}
  close(){this.readyState=3;}
}
const context={WebSocket:Socket,setTimeout:fn=>{const id=++timerId;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id)};
const source=fs.readFileSync('plasticity-asset-tool-app/src/Websocketclient.jsx','utf8').replace('export class WebsocketClient','globalThis.WebsocketClient = class WebsocketClient');
vm.runInNewContext(source,context);
(async()=>{
  const client=new context.WebsocketClient('ws://localhost',state=>states.push(state),event=>events.push(event));
  client.connect();const old=sockets[0];old.readyState=1;old.emit('open');
  const first=client.request('asset.insert',{target_id:'hwnd:42'});
  const rejected=assert.rejects(first,/结果未知/);
  old.close();old.emit('close');await rejected;
  assert.equal(client.pending.size,0);
  const reconnect=[...timers.values()][0];timers.clear();reconnect();
  const next=sockets[1];assert.equal(next.sent.length,0,'Reconnect never replays a model operation');
  const before=states.length;old.emit('open');old.emit('message',{data:JSON.stringify({type:'state'})});
  assert.equal(states.length,before);assert.equal(events.length,0,'Old connections cannot overwrite new state');
  next.readyState=1;next.emit('open');
  const second=client.request('capture',{}),id=next.sent[0].id;
  old.emit('message',{data:JSON.stringify({type:'response',id,ok:true,data:'wrong'})});
  assert.equal(client.pending.size,1);
  next.emit('message',{data:JSON.stringify({type:'response',id,ok:true,data:'correct'})});
  assert.equal(await second,'correct');
  const third=client.request('asset.insert',{}),cancelled=assert.rejects(third,/结果未知/);
  client.disconnect();await cancelled;
  assert.equal(client.pending.size,0);assert.equal(timers.size,0);
  next.emit('close');next.emit('open');assert.equal(states.at(-1),'disconnected');
  assert.equal(sockets.length,2);
  console.log('WebSocket: no replay, stale events ignored and immediate disconnect cleanup verified');
})().catch(error=>{console.error(error);process.exitCode=1;});
