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
