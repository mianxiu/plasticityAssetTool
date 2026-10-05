const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const model=Buffer.alloc(80);model.writeDoubleLE(1,48);
let systemCalls=0,focusCalls=0,failImport=false,cancelPick=false;
const clipboard={readBuffer(){systemCalls++;throw Error('OS read');},writeBuffer(){systemCalls++;throw Error('OS write');},availableFormats(){return [];},has(){return false;}};
const originals={...clipboard};
const original={id:1,view:{id:1}},items=new Map([[1,original]]);
const selected={values:[],get size(){return this.values.length;},get solids(){return this.values;},curves:[],removeAll(){this.values=[];},add(v){this.values.push(v);},saveToMemento(){return this.values.slice();},restoreFromMemento(v){this.values=v.slice();}};
const pk={Session:{GetPrimaryPartition:()=>({GetBodies:()=>[...items.keys()].map(id=>({Id:()=>id}))})}};
const sandbox={NativeBuffer:Buffer,setTimeout,clearTimeout,nativeRequire(name){if(name==='electron')return {clipboard};if(name==='process')return {resourcesPath:'fixture'};if(name==='path')return require('node:path');if(name.endsWith('pk.node'))return pk;throw Error(name);}};
sandbox.globalThis=sandbox;vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
const api=sandbox.__plasticityAssetTransport;
class Cancel extends Error {constructor(){super('Cancel');}}
class Paste {constructor(editor){this.editor=editor;}async execute(){assert.deepEqual(clipboard.readBuffer('application/vnd.plasticity.items'),model);await new Promise(r=>setTimeout(r,1));for(const id of [2,3])items.set(id,{id,view:{id}});if(failImport)throw Error('import failed');}}
class Copy {constructor(editor){this.editor=editor;}async execute(){assert.deepEqual(selected.values.map(v=>v.id),[2,3]);if(cancelPick)throw new Cancel();this.editor.clipboard.copy({x:12});}}
const editor={selection:{selected},viewports:[{focus(){focusCalls++;}}],db:{lookupByBodyId:id=>items.get(id),makeTransaction(){const removed=[];return {removed,delete(view){assert.notEqual(view.id,1,'Never delete an existing object');removed.push(view.id);}};},async commit(tx){for(const id of tx.removed)items.delete(id);}},clipboard:{copy(point){const data=Buffer.from(model);data.writeDoubleLE(point?.x||0,0);clipboard.writeBuffer('application/vnd.plasticity.items',data);}},executor:{},exec(command){this.executor.activeCommand=command;command.execute().catch(error=>{assert(error instanceof Cancel || error.message==='import failed');}).finally(()=>{this.executor.activeCommand=null;selected.removeAll();});}};
(async()=>{
 const run=mode=>api.rebaseModel(editor,{model:model.toString('base64'),base_mode:mode},Copy,Paste,Cancel);
 const picked=await run('pick');assert.equal(Buffer.from(picked.model,'base64').readDoubleLE(0),12);assert.equal(selected.size,0);assert.deepEqual([...items.keys()],[1]);assert.equal(focusCalls,1);
 selected.add(original.view);cancelPick=true;await assert.rejects(run('pick'),/Cancel/);assert.deepEqual(selected.values,[original.view]);assert.deepEqual([...items.keys()],[1]);
 cancelPick=false;const world=await run('world');assert.equal(Buffer.from(world.model,'base64').readDoubleLE(0),0);assert.deepEqual(selected.values,[original.view]);assert.deepEqual([...items.keys()],[1]);assert.equal(focusCalls,2,'World reset requires no point picker');
 failImport=true;await assert.rejects(run('pick'),/import failed/);assert.deepEqual([...items.keys()],[1]);assert.deepEqual(selected.values,[original.view]);
 assert.equal(systemCalls,0);for(const key of Object.keys(originals))assert.equal(clipboard[key],originals[key]);
 console.log('Automatic base point reference: empty selection, cleanup, cancellation, partial import failure and clipboard isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
