const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const sandbox={nativeRequire:()=>({clipboard:{}}),NativeBuffer:Buffer,setTimeout};
sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
class Solid {constructor(name,values){this.name=name;this.values=new Set(values);}}
const modes={Union:1,Difference:2,Intersection:3};
async function check(parts,expected,expectedIndependent=[],targetValues=[1,2]) {
  const prefix='unique-',placed=parts.map((p,i)=>new Solid(prefix+i,p.values));
  const calls=[],groups=[],registered=[];
  const editor={nodes:{getName:v=>v.name,setName(v,n){v.name=n;},item2key:v=>v},groups:{create(){const g={members:[]};groups.push(g);return g;},deleteMembership(){},addMembership(v,g,index){g.members.splice(index,0,v);}}};
  class BooleanFactory {
    async commit(){
      const t=new Set(this.targets.flatMap(v=>[...v.values])),tool=this.tools[0];
      calls.push([this.operationType,tool.name]);
      if(this.operationType===1) for(const n of tool.values)t.add(n);
      if(this.operationType===2) for(const n of tool.values)t.delete(n);
      if(this.operationType===3) for(const n of t)if(!tool.values.has(n))t.delete(n);
      return t.size ? [new Solid('result',t)] : [];
    }
  }
  const command={register(f){registered.push(f);}}; // Real native API returns void.
  const factory={shells:placed,async commit(){return placed;}};
  const recipe={version:1,name:'组名',parts:parts.map((p,i)=>({index:i,name:p.name,mode:p.mode}))};
  sandbox.configureGroupPlacement(editor,command,factory,recipe,targetValues?[new Solid('target',targetValues)]:[],modes,BooleanFactory,true);
  const result=await factory.commit();
  assert.deepEqual([...result[0].values].sort(),expected);
  assert.equal(groups[0].name,'组名');
  assert.equal(registered.length,parts.filter(p=>p.mode!=='new-body').length);
  assert.deepEqual(groups[0].members.slice(1).map(v=>v.name),expectedIndependent);
  return calls;
}
(async()=>{
  const calls=await check([{name:'+ A',mode:'union',values:[2,3]},{name:'- B',mode:'difference',values:[2]},{name:'^ C',mode:'new-body',values:[8]}],[1,3],['^ C']);
  assert.deepEqual(calls,[[1,'+ A'],[2,'- B']]);
  await check([{name:'+ 重名',mode:'union',values:[3]},{name:'+ 重名',mode:'union',values:[4]},{name:'& 截取',mode:'intersection',values:[2,4]}],[2,4]);
  await check([{name:'+ 基体',mode:'union',values:[1,2]},{name:'- 孔',mode:'difference',values:[2]}],[1],[],null);
  await assert.rejects(check([{name:'- 清空',mode:'difference',values:[1,2]}],[]),/结果为空/);
  const selected={groupIds:[2],size:1};
  const solid=new Solid('+ 子实体',[]),group={id:2};solid.userData={versionId:1};
  const editor={executor:{},selection:{selected},groups:{lookupById:()=>group,getChildren:()=>[10]},db:{key2item:()=>solid},geo:{body2version:new Map([[100,1]])},nodes:{item2key:()=>512,getName:key=>key===512?'组名称':key===10?solid.name:undefined}};
  const inspected=sandbox.__plasticityAssetTransport.inspectGroup(editor);
  assert.equal(inspected.recipe.name,'组名称');assert.equal(inspected.recipe.parts[0].mode,'union');
  solid.userData.versionId++;
  assert.throws(()=>sandbox.__plasticityAssetTransport.captureGroup(editor,inspected.signature),/模型已变化/);
  editor.db.key2item=()=>group;
  assert.throws(()=>sandbox.__plasticityAssetTransport.inspectGroup(editor),/直接子实体/);
  selected.size=2;assert.throws(()=>sandbox.__plasticityAssetTransport.inspectGroup(editor),/只选择一个/);
  console.log('Group recipes: ordered booleans, duplicate names, independent parts, empty results and group selection verified');
})().catch(error=>{console.error(error);process.exitCode=1;});
