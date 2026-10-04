// A narrow converter in Electron's preload context. No document commands,
// clipboard writes, selection changes, credentials, or viewport capture.
const nativeRequire = require;
const NativeBuffer = require('buffer').Buffer;
const kernelPath = require('path').join(process.resourcesPath, 'app', '.webpack', 'renderer', 'pk.node');
let context, operation, partitions;
let running = false;

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
    const facets = await pk.DisplayHelper.FacetFacesAndEdges_async(bodies, new pk.FacetOptions(0.001, 0.15, 0.001, 0.15));
    let values = 0;
    const mesh = {version: 1, parts: facets.map(facet => {
      const part = {};
      for (const [key, property] of Object.entries({positions:'facePosition', normals:'faceNormal', indices:'faceIndex', edges:'edgePosition', edge_groups:'edgeGroup'})) {
        const array = facet[property];
        values += array.length;
        if (values > 2_000_000) throw new Error('模型过于复杂，请拆分后预览');
        part[key] = Array.from(array);
      }
      return part;
    })};
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
