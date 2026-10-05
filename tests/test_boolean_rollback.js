// The test executor models the native transaction contract: all registered
// factories share one transaction, whose rollback finishes before exec settles.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
function context() {
  const elements=new Map(),listeners=new Map(),clipboard={readBuffer(){throw Error('OS clipboard must remain untouched');}};
  const element=()=>({style:{},append(){},setAttribute(){},remove(){elements.delete(this.id);}});
  const sandbox={NativeBuffer:Buffer,nativeRequire:name=>name==='crypto'?require('node:crypto'):{clipboard},setTimeout,clearTimeout,console:{log(){}},
    document:{createElement:element,querySelector:selector=>elements.get(selector.slice(1)),body:{append:el=>elements.set(el.id,el)}},
    window:{addEventListener:(type,fn)=>listeners.set(type,fn),removeEventListener:type=>listeners.delete(type)}};
  sandbox.globalThis=sandbox;vm.runInNewContext(source,sandbox);
  return {sandbox,api:sandbox.__plasticityAssetTransport,elements,listeners,clipboard};
}
class Solid {constructor(name,values){this.name=name;this.values=new Set(values);}}
const model=()=>{
  const block=value=>{const data=Buffer.from(value),header=Buffer.alloc(4);header.writeUInt32LE(data.length);return [header,data];};
  const header=Buffer.alloc(68);header.writeUInt32LE(2,64);
  return Buffer.concat([header,...block('geometry'),...block(JSON.stringify({name:'+ shell'})),...block('geometry'),...block(JSON.stringify({name:'- hole'}))]);
};
function names(buffer) {
  let offset=68;const result=[];
  for(let i=0;i<2;i++) {
    offset+=4+buffer.readUInt32LE(offset);
    const length=buffer.readUInt32LE(offset);offset+=4;
    result.push(JSON.parse(buffer.subarray(offset,offset+length)).name);offset+=length;
  }
  return result;
}
async function scenario(failure) {
  const current=context(),other=context(),confirm=deferred(),rollback=deferred();
  const target=new Solid('target',[1,2]),untouched=new Solid('other object',[9]);
  const state={bodies:[target,untouched],groups:[]},root={members:[]},resources=[];
  let settled,calls=0;
  class PlaceFactory {
    constructor(buffer){this.shells=names(buffer).map((name,index)=>new Solid(name,index?[2]:[3]));}
    async commit(){state.bodies.push(...this.shells);return this.shells.slice().reverse();}
  }
  class BooleanFactory {
    async commit(){
      calls++;assert.equal(this.keepTools,false);
      if(calls===2&&failure==='kernel')throw Error('kernel failure');
      const values=new Set(this.targets.flatMap(body=>[...body.values]));
      if(this.operationType===1)for(const value of this.tools[0].values)values.add(value);
      else for(const value of this.tools[0].values)values.delete(value);
      const result=new Solid('result',values);
      state.bodies=state.bodies.filter(body=>!this.targets.includes(body)&&!this.tools.includes(body));
      if(calls===2&&failure==='empty')return [];
      state.bodies.push(result);return [result];
    }
  }
  class Command {
    register(resource){resources.push(resource);}
    async execute(){
      const factory=new PlaceFactory(current.clipboard.readBuffer('application/vnd.plasticity.items'));
      this.register(factory);editor.selection.selected.solids=[];
      await confirm.promise;return factory.commit();
    }
  }
  const editor={executor:{},selection:{selected:{solids:[target]}},commands:{PasteWithPlacementCommand:Command},
    nodes:{item2key:body=>body,getName:body=>body.name,setName(body,name){body.name=name;}},
    groups:{root,create(){const group={members:[]};state.groups.push(group);return group;},deleteMembership(){},addMembership(body,group){
      if(failure==='group'&&body instanceof Solid)throw Error('group membership failure');group.members.push(body);
    }},exec(command){
      const before=state.bodies.slice();this.executor.activeCommand=command;
      settled=(async()=>{try{return await command.execute();}catch(error){
        await rollback.promise;state.bodies=before;state.groups=[];root.members=[];editor.selection.selected.solids=[target];throw error;
      }finally{this.executor.activeCommand=null;}})();return settled;
    }};
  await current.api.insertModel(editor,{model:model().toString('base64'),placement:true,recipe:{version:1,name:'recipe',parts:[
    {index:0,name:'+ shell',mode:'union'},{index:1,name:'- hole',mode:'difference'}]}},Command,{Union:1,Difference:2},BooleanFactory);
  if(failure==='cancel')confirm.reject(Error('user cancelled'));else confirm.resolve();
  await tick();
  assert.equal(other.api.calculationStatus(),null,'A separate window is never locked');
  assert.deepEqual(JSON.parse(JSON.stringify(other.api.inspectGroup({executor:{},selection:{selected:{groupIds:[]}}}))),{recipe:null});
  if(failure==='cancel') {
    assert.equal(calls,0);assert.equal(current.api.calculationStatus(),null);
  }else {
    assert.equal(calls,2);assert.equal(current.api.calculationStatus().step,2);
    assert.match(current.api.calculationStatus().label,/回滚/);
    assert(current.elements.has('pat-calculation-lock'));assert(current.listeners.has('keydown'));
    assert.throws(()=>current.api.inspectGroup(editor),/正在计算/);
  }
  assert.equal(resources.length,3,'Placement and both booleans belong to one command');
  rollback.resolve();await assert.rejects(settled,/kernel failure|结果为空|group membership failure|user cancelled/);await tick();
  assert.deepEqual(state.bodies,[target,untouched]);assert.deepEqual([...target.values],[1,2]);
  assert.deepEqual(state.groups,[]);assert.deepEqual(root.members,[]);assert.deepEqual(editor.selection.selected.solids,[target]);
  assert.equal(current.api.calculationStatus(),null);assert.equal(current.listeners.size,0);assert(!current.elements.has('pat-calculation-lock'));
}
(async()=>{
  for(const failure of ['kernel','empty','group','cancel'])await scenario(failure);
  const test=context();let committed=false;
  const factory={commit:async()=>{committed=true;}};
  assert.throws(()=>test.sandbox.configureGroupPlacement({}, {register(){}},factory,{parts:[{index:0,name:'+ bad',mode:'union'}]},[],{},class {},true),/不兼容/);
  assert.equal(committed,false,'Unsupported operations are rejected before geometry changes');
  console.log('Boolean transactions: second-step failure, empty result, group failure, cancellation and rollback lock verified');
})().catch(error=>{console.error(error);process.exitCode=1;});
