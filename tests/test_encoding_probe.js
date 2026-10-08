const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let osCalls=0;
const clipboard={writeBuffer(){osCalls++;throw Error('OS clipboard');}},originalWrite=clipboard.writeBuffer;
const sandbox={NativeBuffer:Buffer,setTimeout,nativeRequire:name=>name==='crypto'?require('node:crypto'):{clipboard}};sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/native-transport-preload.cjs','utf8'),sandbox);
class Vector3 {constructor(x,y,z){Object.assign(this,{x,y,z});}}
class Quaternion {constructor(x,y,z,w){Object.assign(this,{x,y,z,w});}}
const block=b=>{const n=Buffer.alloc(4);n.writeUInt32LE(b.length);return Buffer.concat([n,b]);};
for(const legacy of [false,true]) {
  let changeContent=false;
  const selected={size:1},editor={executor:{},selection:{selected},clipboard:{copy(point,orientation){
    if(legacy && !(orientation instanceof Vector3))throw Error('direction required');
    if(!legacy && !(orientation instanceof Quaternion))throw Error('quaternion required');
    const h=Buffer.alloc(legacy?60:70);
    if(legacy)h.writeUInt32LE(1);else {h.writeUInt32LE(2,60);h.write('[]',64);h.writeUInt32LE(1,66);}
    [point.x,point.y,point.z].forEach((n,i)=>h.writeDoubleLE(n,(legacy?8:0)+8*i));
    (legacy?[orientation.x,orientation.y,orientation.z]:[orientation.x,orientation.y,orientation.z,orientation.w]).forEach((n,i)=>h.writeDoubleLE(n,(legacy?32:24)+8*i));
    clipboard.writeBuffer('application/vnd.plasticity.items',Buffer.concat([h,block(Buffer.from('PS\0\0\x003: TRANSMIT FILE '+(changeContent?point.x:'synthetic'))),block(Buffer.from('{}'))]));
  }}};
  const report=sandbox.__plasticityAssetTransport.inspectEncoding(editor,Vector3,Quaternion);
  assert.equal(report.format,legacy?'count-first':'modern');
  assert.equal(report.layout.point,legacy?8:0);assert.equal(report.layout.orientation,legacy?32:24);
  assert.equal(report.layout.orientation_kind,legacy?'direction':'quaternion');
  assert.equal(report.probes.length,2);assert.equal(clipboard.writeBuffer,originalWrite);assert.equal(editor.selection.selected,selected);
  assert.equal(report.probes[0].model,undefined,'Normal diagnostics must not include raw geometry');
  const collected=sandbox.__plasticityAssetTransport.inspectEncoding(editor,Vector3,Quaternion,true);
  assert.equal(collected.test_inputs.orientation_kind,legacy?'direction':'quaternion');
  for(const probe of collected.probes){
    const bytes=Buffer.from(probe.model,'base64');
    assert.equal(bytes.length,probe.bytes);
    assert.equal(require('node:crypto').createHash('sha256').update(bytes).digest('hex'),probe.model_sha256);
    assert.equal(bytes.subarray(0,Buffer.from(probe.header,'base64').length).toString('base64'),probe.header);
  }
  changeContent=true;
  assert.equal(sandbox.__plasticityAssetTransport.inspectEncoding(editor,Vector3,Quaternion).layout,null,'Changing native geometry must not enable offline base point edits');
  editor.executor.activeCommand={};assert.throws(()=>sandbox.__plasticityAssetTransport.inspectEncoding(editor,Vector3,Quaternion),/建模操作/);
}
const bad={executor:{},selection:{selected:{size:1}},clipboard:{copy(){throw Error('encoding failed');}}};
assert.throws(()=>sandbox.__plasticityAssetTransport.inspectEncoding(bad,Vector3,Quaternion),/encoding failed/);
assert.equal(clipboard.writeBuffer,originalWrite);assert.equal(osCalls,0);
assert.throws(()=>sandbox.__plasticityAssetTransport.inspectEncoding({...bad,selection:{selected:{size:0}}},Vector3,Quaternion),/测试实体/);
console.log('Native encoding probe: two controlled inputs, quaternion/direction discovery, active-tool guard and clipboard isolation passed');

const futureEditor={executor:{},selection:{selected:{size:1}},clipboard:{copy(){clipboard.writeBuffer('application/vnd.plasticity.items',Buffer.alloc(600,7));}}};
const futureReport=sandbox.__plasticityAssetTransport.inspectEncoding(futureEditor,Vector3,Quaternion,true);
assert.equal(futureReport.format,'unknown');assert.equal(futureReport.layout,null);
assert.equal(futureReport.probes.length,2);assert.equal(Buffer.from(futureReport.probes[0].model,'base64').length,600);
const largeEditor={...futureEditor,clipboard:{copy(){clipboard.writeBuffer('application/vnd.plasticity.items',Buffer.alloc(4*1024*1024+1));}}};
assert.throws(()=>sandbox.__plasticityAssetTransport.inspectEncoding(largeEditor,Vector3,Quaternion,true),/4 MB/);
assert.equal(clipboard.writeBuffer,originalWrite);assert.equal(osCalls,0);
