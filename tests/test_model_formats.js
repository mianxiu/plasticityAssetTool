const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const clipboard={writeBuffer(){throw Error('OS clipboard write');}};
const sandbox={NativeBuffer:Buffer,setTimeout,nativeRequire(name){
  if(name==='electron')return {clipboard};
  if(name==='crypto')return {randomUUID:()=> '12345678-1234-1234-1234-123456789abc'};
  throw Error(name);
}};
sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
const block=data=>{const n=Buffer.alloc(4);n.writeUInt32LE(data.length);return Buffer.concat([n,data]);};
const body=name=>Buffer.concat([block(Buffer.from('PS\0\0\x003: TRANSMIT FILE synthetic')),block(Buffer.from(JSON.stringify({name})))]);
function model(legacy,names) {
  const header=Buffer.alloc(legacy?60:70);
  if(legacy)header.writeUInt32LE(names.length,0);
  else {header.writeDoubleLE(1,48);header.writeUInt32LE(2,60);header.write('[]',64);header.writeUInt32LE(names.length,66);}
  return Buffer.concat([header,...names.map(body)]);
}
class Solid {constructor(name){this.name=name;this.userData={versionId:1};}}
for(const legacy of [false,true]) {
  const a=new Solid('+ A'),b=new Solid('- B'),keys=[10,11];
  const selected={groupIds:[2],size:1,solids:[],saveToMemento(){return {...this,groupIds:[...this.groupIds],solids:[...this.solids]};},
    removeAll(){this.groupIds=[];this.size=0;this.solids=[];},add(item){this.solids.push(item);this.size++;},
    restoreFromMemento(saved){Object.assign(this,saved);}};
  const editor={executor:{},selection:{selected},groups:{lookupById:()=>({}),getChildren:()=>keys},
    db:{key2item:key=>key===10?a:b},nodes:{item2key:()=>20,getName:key=>key===10?a.name:key===11?b.name:'Group'},
    clipboard:{copy(){clipboard.writeBuffer('application/vnd.plasticity.items',model(legacy,[selected.solids[0].name]));}}};
  const inspected=sandbox.__plasticityAssetTransport.inspectGroup(editor);
  const captured=sandbox.__plasticityAssetTransport.captureGroup(editor,inspected.signature);
  const bytes=Buffer.from(captured.model,'base64');
  assert.deepEqual(bytes,model(legacy,['+ A','- B']));
  assert.deepEqual(selected.groupIds,[2]);assert.equal(selected.size,1);
  const tagged=sandbox.labelGroupModel(bytes,captured.recipe);
  assert.equal(tagged.names.length,2);assert.notEqual(tagged.names[0],tagged.names[1]);
  const layout=sandbox.nativeModelLayout(tagged.data);
  assert.equal(tagged.data.readUInt32LE(layout.count),2);
  let cursor=layout.bodies;
  for(let i=0;i<2;i++) {
    const geometrySize=tagged.data.readUInt32LE(cursor);cursor+=4;
    assert.deepEqual(tagged.data.subarray(cursor,cursor+geometrySize),Buffer.from('PS\0\0\x003: TRANSMIT FILE synthetic'));cursor+=geometrySize;
    const metadataSize=tagged.data.readUInt32LE(cursor);cursor+=4;
    assert.equal(JSON.parse(tagged.data.subarray(cursor,cursor+metadataSize)).name,tagged.names[i]);cursor+=metadataSize;
  }
  assert.equal(cursor,tagged.data.length);
}
console.log('Native model formats: modern/count-first group capture, body identity and selection restoration passed');
