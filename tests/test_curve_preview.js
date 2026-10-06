const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const sandbox={require:name=>require(name),process:{resourcesPath:'.'}};sandbox.globalThis=sandbox;
vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/geometry-preload.cjs','utf8'),sandbox);
const edge=(fn,line=false)=>({GetPoint:t=>{const [x,y,z]=fn(t);return {x,y,z};},
  GetInterval:()=>({tmin:-7,tmax:-1}),GetBox:()=>({min:{x:-1,y:-1,z:0},max:{x:1,y:1,z:0}}),IsLine:()=>line});
const wire=edges=>({GetEdges:()=>({Size:()=>edges.length,Get:i=>edges[i]})});
const sample=edges=>sandbox.wirePreview(wire(edges),()=>{});
const line=sample([edge(t=>[t,0,0],true),edge(t=>[10+t,0,0],true)]);
assert.deepEqual(Array.from(line.edge_groups),[0,6,6,6]);
assert.deepEqual(Array.from(line.edges),[0,0,0,1,0,0,10,0,0,11,0,0]);
const circle=sample([edge(t=>[Math.cos(t*2*Math.PI),Math.sin(t*2*Math.PI),0])]);
assert(circle.edges.length>48,'Closed curves must not collapse to a zero-length chord');
for(let i=0;i+5<circle.edges.length;i+=3){
  const x=(circle.edges[i]+circle.edges[i+3])/2,y=(circle.edges[i+1]+circle.edges[i+4])/2;
  assert(1-Math.hypot(x,y)<0.0003,'Circle chords stay within the sampling tolerance');
}
const spline=sample([edge(t=>[t,Math.sin(t*4*Math.PI),0])]);
assert(Math.max(...spline.edges.filter((_,i)=>i%3===1))>0.99);
assert(Math.min(...spline.edges.filter((_,i)=>i%3===1))< -0.99);
assert.throws(()=>sample([edge(()=>[NaN,0,0])]),/坐标无效/);
assert.throws(()=>sandbox.wirePreview(wire([edge(t=>[t,0,0],true)]),()=>{throw Error('budget');}),/budget/);
console.log('Curve preview: disconnected lines, closed circles, oscillating curves and bounded sampling verified');

const kernelPoints=sampled=>Array.from(sandbox.kernelSnapPoints(wire(sampled),()=>{}));
assert.deepEqual(kernelPoints([edge(t=>[t,0,0],true)]),[0,0,0,0,1,0,0,0,.5,0,0,1]);
const parameterMidpoint=kernelPoints([edge(t=>[t*t,Math.sin(t*Math.PI),0])]);
assert.deepEqual(parameterMidpoint.slice(-4),[.25,1,0,2], 'Use the original curve evaluator; never substitute chord interpolation or call a parameter midpoint an arc midpoint');
assert.deepEqual(kernelPoints([edge(()=>[NaN,0,0])]),[]);
assert.deepEqual(kernelPoints([{GetPoint(){throw Error('unsupported');}}]),[]);
assert.deepEqual(kernelPoints([edge(t=>[t,0,0],true),edge(t=>[t,0,0],true)]),kernelPoints([edge(t=>[t,0,0],true)]),'Deduplicate kernel points');
assert.throws(()=>sandbox.kernelSnapPoints(wire([edge(t=>[t,0,0],true)]),()=>{throw Error('budget');}),/budget/);
assert.deepEqual(Array.from(sandbox.kernelSnapPoints(wire([edge(t=>[t,0,0],true)]),()=>false)),[],'Optional snap budget exhaustion must not invalidate an ordinary preview');
console.log('Kernel snapping: exact edge evaluation, parameter midpoint semantics, unsupported edges and budgets verified');

(async()=>{
  let restored=0;
  class Solid {GetEdges(){return wire([edge(t=>[t,0,0],true)]).GetEdges();}}
  class WireBody {GetEdges(){return wire([edge(t=>[t*t,t,0])]).GetEdges();}}
  const bodies=[new Solid(),new WireBody()];
  const fixture={
    Context:{MakeContext:()=>({MakePartitions:n=>new Uint32Array(n)})},
    Operation:class {
      MakePartitionMarks(){return [1];}
      async ImportParts_async(){return {ok:true,errors:[],parts:[0,1]};}
      async GotoPartitionMarks_async(){restored++;return {ok:true,errors:[]};}
    },
    Body:{View:id=>bodies[id]},FacetOptions:class {},
    DisplayHelper:{FacetFacesAndEdges_async:async()=>[{facePosition:[0,0,0,1,0,0,0,1,0],faceNormal:[0,0,1,0,0,1,0,0,1],faceIndex:[0,1,2],edgePosition:[0,0,0,1,0,0],edgeGroup:[0,6]}]},
  };
  const convertSandbox={require:name=>name.endsWith('pk.node')?fixture:require(name),process:{resourcesPath:'.'}};
  convertSandbox.globalThis=convertSandbox;
  vm.runInNewContext(fs.readFileSync('plasticity-javascript-payloads/geometry-preload.cjs','utf8'),convertSandbox);
  const encoded=Buffer.from('PS\0\0\x003: TRANSMIT FILE').toString('base64');
  const converted=await convertSandbox.__plasticityAssetGeometry.convert([encoded,encoded]);
  assert.deepEqual(Array.from(converted.parts[0].kernel_snaps),[0,0,0,0,1,0,0,0,.5,0,0,1]);
  assert.deepEqual(Array.from(converted.parts[1].kernel_snaps).slice(-4),[.25,.5,0,2]);
  assert.equal(restored,1,'Temporary partitions must be restored after attaching snap points');
  console.log('Kernel snap coordinates travel with both solid and wire previews; temporary partitions restored');
})().catch(error=>{console.error(error);process.exitCode=1;});
