const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
let systemWrites=0;
const clipboard={writeBuffer(){systemWrites++;throw Error('OS clipboard write');}};
const write=clipboard.writeBuffer;
const sandbox={nativeRequire:()=>({clipboard}),NativeBuffer:Buffer,setTimeout,clearTimeout,globalThis:null};sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
const api=sandbox.__plasticityAssetTransport;
const model=Buffer.alloc(80);model.writeDoubleLE(1,48);
const point={x:12,y:24,z:36};
let originalArgs, restored=0;
const selected={size:1,solids:[{}],curves:[],saveToMemento(){return 'selection';},restoreFromMemento(value){assert.equal(value,'selection');restored++;}};
const editor={selection:{selected},executor:{isBusy:false},clipboard:{copy(...args){originalArgs=args;const data=Buffer.from(model);if(args.length)data.writeDoubleLE(args[0].x,0);clipboard.writeBuffer('application/vnd.plasticity.items',data);}},exec(command){this.executor.activeCommand=command;return command.execute().finally(()=>{this.executor.activeCommand=null;});}};
const copy=editor.clipboard.copy;
class Pick {constructor(editor){this.editor=editor;}async execute(){await new Promise(resolve=>setTimeout(resolve,5));this.editor.clipboard.copy(point);}}
(async()=>{
  const captured=await api.captureWithBasePoint(editor,Pick);
  assert.equal(Buffer.from(captured.model,'base64').readDoubleLE(0),12);
  assert.equal(originalArgs[0],point,'Forward the native point without guessed coordinates or units');
  assert.equal(captured.kind,'solid');assert.equal(systemWrites,0);
  assert.equal(editor.clipboard.copy,copy);assert.equal(clipboard.writeBuffer,write);assert.equal(restored,1);
  class Cancel {async execute(){throw Error('cancelled');}}
  await assert.rejects(api.captureWithBasePoint(editor,Cancel),/cancelled/);
  assert.equal(editor.clipboard.copy,copy);assert.equal(clipboard.writeBuffer,write);assert.equal(restored,2);
  class Empty {async execute(){}}
  await assert.rejects(api.captureWithBasePoint(editor,Empty),/取消/);
  class Bad {constructor(){throw Error('unsupported');}}
  await assert.rejects(api.captureWithBasePoint(editor,Bad),/unsupported/);
  assert.equal(editor.clipboard.copy,copy);
  // The native executor may return void while its interactive command is pending.
  const voidEditor={...editor,executor:{isBusy:false},exec(command){command.execute().catch(()=>{});}};
  assert.equal(Buffer.from((await api.captureWithBasePoint(voidEditor,Pick)).model,'base64').readDoubleLE(0),12);
  assert.equal(systemWrites,0);assert.equal(editor.clipboard.copy,copy);
  const realTimeout=sandbox.setTimeout;
  sandbox.setTimeout=(fn,ms)=>setTimeout(fn,ms===120000 ? 1 : ms);
  let cancelPicker;
  class Waiting {execute(){return new Promise((_,reject)=>{cancelPicker=()=>reject(Error('cancelled'));});}}
  const timedEditor={...editor,executor:{isBusy:false,cancelActiveCommand(){cancelPicker();}},exec(command){this.executor.activeCommand=command;command.execute().catch(()=>{});}};
  const waiting=api.captureWithBasePoint(timedEditor,Waiting);
  assert.throws(()=>api.captureSelection(editor),/尚未结束/,'Other model operations are locked during the picker');
  await assert.rejects(waiting,/cancelled|超时/);
  assert.equal(editor.clipboard.copy,copy);assert.equal(clipboard.writeBuffer,write);assert.equal(systemWrites,0);
  sandbox.setTimeout=realTimeout;
  class Solid {constructor(name){this.name=name;this.userData={versionId:1};}}
  const bodies=[new Solid('+ A'),new Solid('- B')];
  const groupSelected={groupIds:[2],size:1,saveToMemento(){return {size:this.size,groupIds:this.groupIds,body:this.body};},restoreFromMemento(value){Object.assign(this,value);},removeAll(){this.size=0;this.groupIds=[];},add(body){this.size=1;this.body=body;}};
  const block=value=>{const size=Buffer.alloc(4);size.writeUInt32LE(value.length);return Buffer.concat([size,value]);};
  const oneBody=name=>{const count=Buffer.alloc(4);count.writeUInt32LE(1);return Buffer.concat([model.subarray(0,56),block(Buffer.from('')),block(Buffer.from('[]')),count,block(Buffer.from('geometry-'+name)),block(Buffer.from(JSON.stringify({name})))]);};
  const groupEditor={executor:{isBusy:false},selection:{selected:groupSelected},groups:{lookupById:()=>({id:2}),getChildren:()=>[10,11]},db:{key2item:key=>bodies[key-10]},nodes:{item2key:()=>512,getName:key=>key===512?'group':bodies[key-10].name},clipboard:{copy(point){const data=oneBody(groupSelected.body?.name || 'group');if(point)data.writeDoubleLE(point.x,0);clipboard.writeBuffer('application/vnd.plasticity.items',data);}},exec:editor.exec};
  const signature=api.inspectGroup(groupEditor).signature;
  const originalGroup=api.captureGroup(groupEditor,signature);
  const pickedGroup=await api.captureGroupWithBasePoint(groupEditor,signature,Pick);
  const groupData=Buffer.from(pickedGroup.model,'base64');
  assert.equal(groupData.readDoubleLE(0),12);
  assert.deepEqual(groupData.subarray(56),Buffer.from(originalGroup.model,'base64').subarray(56),'All child geometry and order remain unchanged');
  assert.deepEqual(pickedGroup.recipe,originalGroup.recipe);
  assert.equal(groupSelected.groupIds[0],2);assert.equal(systemWrites,0);
  console.log('Native base point capture: arguments, void executor, cancellation and clipboard isolation verified');
})().catch(error=>{console.error(error);process.exitCode=1;});
