// A narrow converter in Electron's preload context. No document commands,
// clipboard writes, selection changes, credentials, or viewport capture.
const nativeRequire = require;
const NativeBuffer = require('buffer').Buffer;
const kernelPath = require('path').join(process.resourcesPath, 'app', '.webpack', 'renderer', 'pk.node');
let context, operation, partitions;
let running = false;

// Independent snap coordinates from the original edges, never facet vertices.
// Kind 2 is a parameter midpoint, not an arc-length midpoint on a spline.
function kernelSnapPoints(body, reserve) {
  const points=[], seen=new Set();
  let edges;
  try {edges=body.GetEdges();} catch {return points;}
  const add=(point,kind)=>{
    const values=[point?.x,point?.y,point?.z];
    if(!values.every(v=>Number.isFinite(v) && Math.abs(v)<=1e12))return;
    const key=kind+':'+values.join(',');if(seen.has(key))return;
    if(reserve(4)===false)return;
    seen.add(key);points.push(...values,kind);
  };
  let count;
  try {count=edges.Size();} catch {return points;}
  if(!Number.isSafeInteger(count) || count<0 || count>500000)return points;
  for(let i=0;i<count;i++) {
    let edge;
    try {edge=edges.Get(i);} catch {continue;}
    for(const parameter of [0,1,.5]) {
      let point, kind;
      try {point=edge.GetPoint(parameter);kind=parameter===.5 ? (edge.IsLine()?1:2) : 0;}
      catch {continue;} // An unsupported edge must not disable ordinary previewing.
      add(point,kind);
    }
  }
  return points;
}

function wirePreview(body, reserve) {
  const part = {positions:[], normals:[], indices:[], edges:[], edge_groups:[]};
  const edges = body.GetEdges();
  const point = (edge, t) => {
    const p = edge.GetPoint(t), value = [p.x,p.y,p.z];
    if (!value.every(Number.isFinite)) throw new Error('曲线采样坐标无效');
    return value;
  };
  const distance = (a,b) => Math.hypot(...a.map((v,i)=>v-b[i]));
  const deviation = (p,a,b) => {
    const ab = b.map((v,i)=>v-a[i]), length2 = ab.reduce((n,v)=>n+v*v,0);
    const u = length2 ? Math.max(0,Math.min(1,p.reduce((n,v,i)=>n+(v-a[i])*ab[i],0)/length2)) : 0;
    return distance(p,a.map((v,i)=>v+u*ab[i]));
  };
  for (let index=0; index<edges.Size(); index++) {
    const edge=edges.Get(index), interval=edge.GetInterval();
    if (!Number.isFinite(interval.tmin) || !Number.isFinite(interval.tmax) || interval.tmax<=interval.tmin) throw new Error('曲线参数范围无效');
    // Edge.GetPoint takes normalized [0,1], unlike Curve.GetPoint and the
    // underlying trimmed parameter interval (which may even be negative).
    const tmin=0,tmax=1;
    const box=edge.GetBox();
    const scale=Math.hypot(box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z);
    const tolerance=Math.max(scale*0.0001,1e-7), start=part.edges.length;
    let points=0;
    const append = p => {
      if (++points>16384) throw new Error('曲线过于复杂，请拆分后预览');
      reserve(3);part.edges.push(...p);
    };
    const subdivide = (a,b,pa,pb,depth) => {
      const tm=(a+b)/2, pm=point(edge,tm);
      const quarter=point(edge,(a+tm)/2), threeQuarter=point(edge,(tm+b)/2);
      const error=Math.max(deviation(pm,pa,pb),deviation(quarter,pa,pb),deviation(threeQuarter,pa,pb));
      if (error<=tolerance) {append(pb);return;}
      if (depth>=12) throw new Error('曲线采样精度不足，请拆分后预览');
      subdivide(a,tm,pa,pm,depth+1);subdivide(tm,b,pm,pb,depth+1);
    };
    let a=tmin, pa=point(edge,a);append(pa);
    if (edge.IsLine()) append(point(edge,tmax));
    else for (let seed=1;seed<=16;seed++) {
      const b=tmin+(tmax-tmin)*seed/16, pb=point(edge,b);
      subdivide(a,b,pa,pb,0);a=b;pa=pb;
    }
    reserve(2);part.edge_groups.push(start,part.edges.length-start);
  }
  return part;
}

async function convert(parts) {
  if (running) throw new Error('预览转换正在运行');
  if (!Array.isArray(parts) || !parts.length || parts.length > 256) throw new Error('模型对象数量无效');
  const buffers = parts.map(encoded => {
    if (typeof encoded !== 'string' || !/^[A-Za-z0-9+/]*={0,2}$/.test(encoded)) throw new Error('模型编码无效');
    return NativeBuffer.from(encoded, 'base64');
  });
  const signature = NativeBuffer.from('PS\0\0\x003: TRANSMIT FILE');
  if (buffers.reduce((n, b) => n + b.length, 0) > 64 * 1024 * 1024 || buffers.some(b => !b.subarray(0, signature.length).equals(signature))) throw new Error('模型数据无效');
  running = true;
  let marks;
  try {
    const pk = nativeRequire(kernelPath);
    if (!context) {
      context = pk.Context.MakeContext();
      operation = new pk.Operation(context);
      partitions = context.MakePartitions(1);
    }
    // One partition per serialized body, retained empty between requests.
    if (partitions.length < buffers.length) {
      const extra = context.MakePartitions(buffers.length - partitions.length);
      partitions = new partitions.constructor([...partitions, ...extra]);
    }
    const current = partitions.subarray(0, buffers.length);
    marks = operation.MakePartitionMarks(current);
    const imported = await operation.ImportParts_async(buffers, current);
    if (!imported.ok || Array.from(imported.errors).some(Boolean)) throw new Error('内核无法读取组件几何');
    const bodies = Array.from(imported.parts, id => pk.Body.View(id));
    // Face faceting returns empty arrays for WireBody. Sample its trimmed
    // native edges separately; never create editor objects or use screenshots.
    const surfaces=bodies.filter(body=>body.constructor.name!=='WireBody');
    const facets = surfaces.length ? await pk.DisplayHelper.FacetFacesAndEdges_async(surfaces, new pk.FacetOptions(0.001, 0.15, 0.001, 0.15)) : [];
    let values = 0;
    const reserve = count => {
      values+=count;
      if (values>2_000_000) throw new Error('模型过于复杂，请拆分后预览');
    };
    let facetIndex=0;
    const mesh = {version: 1, parts: bodies.map(body => {
      if (body.constructor.name==='WireBody') return wirePreview(body,reserve);
      const facet=facets[facetIndex++];
      const part = {};
      for (const [key, property] of Object.entries({positions:'facePosition', normals:'faceNormal', indices:'faceIndex', edges:'edgePosition', edge_groups:'edgeGroup'})) {
        const array = facet[property];
        reserve(array.length);
        part[key] = Array.from(array);
      }
      return part;
    })};
    // Optional snap data uses only the remaining budget; never invalidate a
    // preview that already fits the original geometry limits.
    for(let i=0;i<bodies.length;i++)mesh.parts[i].kernel_snaps=kernelSnapPoints(bodies[i],count=>{
      if(values+count>2_000_000)return false;
      reserve(count);return true;
    });
    return mesh;
  } finally {
    try {
      if (marks) {
        const restored = await operation.GotoPartitionMarks_async(marks);
        if (!restored.ok || Array.from(restored.errors).some(Boolean)) throw new Error('临时预览分区清理失败');
      }
    } finally { running = false; }
  }
}

// The app uses a shared renderer world. Keep Node/module access in this closure.
globalThis.__plasticityAssetGeometry = Object.freeze({convert});
