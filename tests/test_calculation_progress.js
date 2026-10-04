const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const listeners=new Map(),elements=new Map();
const makeElement=()=>({style:{},setAttribute(){},append(){},remove(){elements.delete(this.id);}});
const clipboard={readBuffer(){throw Error('OS clipboard');}};
const sandbox={nativeRequire:()=>({clipboard}),NativeBuffer:Buffer,setTimeout,clearTimeout,console:{log(){}},
  document:{createElement:makeElement,querySelector(selector){return elements.get(selector.slice(1));},body:{append(el){elements.set(el.id,el);}}},
  window:{addEventListener(type,handler){listeners.set(type,handler);},removeEventListener(type,handler){if(listeners.get(type)===handler)listeners.delete(type);}}};
sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
const api=sandbox.__plasticityAssetTransport;
const wait=()=>new Promise(resolve=>setTimeout(resolve,0));
async function run(fail=false,emptyBoolean=false) {
  const confirm=deferred(),compute=deferred(),rollback=deferred();let factory,settled;
  class PlaceFactory {constructor(){this.shells=[{}];}commit(){return compute.promise;}}
  class BooleanFactory {async commit(){return [];}}
  class Command {
    register(){};
    async execute(){sandbox.nativeRequire().clipboard.readBuffer('application/vnd.plasticity.items');factory=new PlaceFactory();this.register(factory);await confirm.promise;return factory.commit();}
  }
  const editor={executor:{},selection:{selected:{size:1,solids:[{}]}},commands:{PasteWithPlacementCommand:Command},
    exec(cmd){settled=(async()=>{try{return await cmd.execute();}catch(error){await rollback.promise;throw error;}})();return settled;}};
  const transport=api;
  await transport.insertModel(editor,{model:Buffer.alloc(80,1).toString('base64'),placement:true,insert_mode:emptyBoolean?'difference':'new-body'},Command,{Difference:2},BooleanFactory);
  assert.equal(transport.calculationStatus(),null,'Positioning must remain interactive');
  confirm.resolve();await wait();
  assert(elements.has('pat-calculation-lock'));assert.equal(transport.calculationStatus().step,1);
  const snapshot=transport.calculationStatus();snapshot.step=999;assert.equal(transport.calculationStatus().step,1);
  let prevented=false,stopped=false;listeners.get('pointerdown')({preventDefault(){prevented=true;},stopImmediatePropagation(){stopped=true;}});
  assert(prevented&&stopped);assert(listeners.has('keydown'));
  assert.throws(()=>transport.captureSelection(editor),/正在计算/);
  if(fail || emptyBoolean) {
    if(fail)compute.reject(Error('kernel failed'));else compute.resolve([{}]);
    await wait();
    assert.match(transport.calculationStatus().label,/回滚/);
    assert(elements.has('pat-calculation-lock'),'Rollback must stay locked');
    rollback.resolve();await assert.rejects(settled,fail?/kernel failed/:/布尔结果为空/);
  } else {compute.resolve([]);await settled;}
  await wait();assert.equal(transport.calculationStatus(),null);assert(!elements.has('pat-calculation-lock'));assert.equal(listeners.size,0);
  if(fail || emptyBoolean) {assert(elements.has('pat-calculation-error'));elements.get('pat-calculation-error').remove();}
  assert.equal(elements.size,0);
}
(async()=>{
  await run();await run(true);await run(false,true);
  const updates=[],hold=deferred();
  class Solid {}
  const editor={nodes:{item2key:v=>v,setName(){}},groups:{create:()=>({}),deleteMembership(){},addMembership(){}}};
  class BooleanFactory {commit(){return hold.promise;}}
  const factory={shells:[new Solid(),new Solid()],async commit(){return this.shells;}};
  sandbox.configureGroupPlacement(editor,{register(){}},factory,{name:'组',parts:[{index:0,name:'^ 保留',mode:'new-body'},{index:1,name:'- 孔',mode:'difference'}]},[new Solid()],{Difference:2},BooleanFactory,true,(...args)=>updates.push(args));
  const pending=factory.commit();await wait();
  assert.deepEqual(updates,[[1,'保留独立实体：^ 保留',0],[2,'布尔减去：- 孔',1]]);
  hold.resolve([new Solid()]);await pending;
  console.log('Calculation progress: interactive placement, real step counts, input lock, rollback and cleanup verified');
})().catch(error=>{console.error(error);process.exitCode=1;});
