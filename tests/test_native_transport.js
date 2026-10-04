const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
let reads=0,writes=0;
const clipboard={availableFormats(){return ['image/png'];},has(){return false;},readBuffer(){reads++;throw Error('OS read');},writeBuffer(){writes++;throw Error('OS write');}};
const originalRead=clipboard.readBuffer,originalWrite=clipboard.writeBuffer;
const originalFormats=clipboard.availableFormats,originalHas=clipboard.has;
const sandbox={nativeRequire:()=>({clipboard}),NativeBuffer:Buffer,setTimeout,globalThis:null};sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
const api=sandbox.__plasticityAssetTransport;
const model=Buffer.alloc(80,1);
class Command {execute(){assert(clipboard.availableFormats().includes('application/vnd.plasticity.items'));assert(clipboard.has('application/vnd.plasticity.items'));const received=clipboard.readBuffer('application/vnd.plasticity.items');assert.deepEqual(received,model);return new Promise(()=>{});}}
const editor={executor:{isBusy:false},selection:{selected:{size:1}},commands:{PasteWithPlacementCommand:Command},clipboard:{copy(){clipboard.writeBuffer('application/vnd.plasticity.items',model);}},exec(cmd){const result=cmd.execute();assert.equal(clipboard.readBuffer,originalRead);return result;}};
(async()=>{
 assert.equal(api.captureSelection(editor).model,model.toString('base64'));
 assert.equal(clipboard.writeBuffer,originalWrite);
 assert.equal((await api.insertModel(editor,{model:model.toString('base64'),placement:true},Command)).started,true);
 assert.equal(clipboard.availableFormats,originalFormats);assert.equal(clipboard.has,originalHas);
 class RepeatPasteWithPlacementCommand {constructor(buffer){this.buffer=buffer;}}
 let cancelled=0;
 const ownEditor={...editor,executor:{isBusy:false,cancelActiveCommand(){cancelled++;this.activeCommand=null;}},exec(cmd){
   const original=clipboard.readBuffer;
   const result=cmd.execute();
   // Simulate native confirmation, retaining the same delivered buffer.
   this.executor.activeCommand=new RepeatPasteWithPlacementCommand(lastBuffer);
   assert.equal(clipboard.readBuffer,original);return result;
 }};
 let lastBuffer;
 class ConfirmCommand {execute(){lastBuffer=clipboard.readBuffer('application/vnd.plasticity.items');return new Promise(()=>{});}}
 ownEditor.commands={PasteWithPlacementCommand:ConfirmCommand};
 await api.insertModel(ownEditor,{model:model.toString('base64'),placement:true},ConfirmCommand);
 await new Promise(resolve=>setTimeout(resolve,30));
 assert.equal(cancelled,1);
 ownEditor.exec=function(cmd){const pending=cmd.execute();this.executor.activeCommand=new RepeatPasteWithPlacementCommand(Buffer.from(model));return pending;};
 await api.insertModel(ownEditor,{model:model.toString('base64'),placement:true},ConfirmCommand);
 await new Promise(resolve=>setTimeout(resolve,30));
 assert.equal(cancelled,1,'A foreign continuation must remain untouched');
 const targetA={id:'target-a'},targetB={id:'target-b'};
 const selected=new Set([targetA,targetB]);
 let factory;
 class PlaceFactory {constructor(){this.targets=[];this.operationType='new-body';this.keepTools=true;this.shells=[{}];}}
 class BooleanPlaceCommand {
   register(resource){return resource;}
   execute(){clipboard.readBuffer('application/vnd.plasticity.items');factory=new PlaceFactory();this.register(factory);selected.clear();return new Promise(()=>{});}
 }
 const booleanEditor={...editor,selection:{selected:{solids:selected}},commands:{PasteWithPlacementCommand:BooleanPlaceCommand}};
 class BooleanFactory {commit(){return [];}}
 const operations={Union:15903,Difference:15902,Intersection:15901};
 for(const [mode,type] of [['union',15903],['difference',15902],['intersection',15901]]) {
   selected.add(targetA);selected.add(targetB);
   const result=await api.insertModel(booleanEditor,{model:model.toString('base64'),placement:true,insert_mode:mode},null,operations,BooleanFactory);
   assert.equal(result.insert_mode,mode);assert.equal(factory.operationType,'new-body');
   assert.deepEqual(Array.from(factory.targets),[]);
 }
 await assert.rejects(api.insertModel(booleanEditor,{model:model.toString('base64'),placement:true,insert_mode:'difference'},null,operations),/选中布尔目标/);
 selected.add(targetA);
 await assert.rejects(api.insertModel(booleanEditor,{model:model.toString('base64'),placement:true,insert_mode:'difference'}),/更新内嵌插件/);
 await assert.rejects(api.insertModel(booleanEditor,{model:model.toString('base64'),placement:false,insert_mode:'difference'},null,operations),/定位置入/);
 editor.clipboard.copy=()=>{throw Error('encode failed');};
 assert.throws(()=>api.captureSelection(editor),/encode failed/);
 assert.equal(clipboard.writeBuffer,originalWrite);
 editor.executor.activeCommand={};
 await assert.rejects(api.insertModel(editor,{model:model.toString('base64'),placement:true},Command),/尚未结束/);
 assert.equal(reads,0);assert.equal(writes,0);
 console.log('Native transport: no OS clipboard calls, immediate restoration, error cleanup and active-tool guard passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
