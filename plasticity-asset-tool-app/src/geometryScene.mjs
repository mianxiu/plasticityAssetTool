import * as THREE from 'three';

export function sceneFor(mesh) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#262628');
  const model = new THREE.Group();
  model.rotation.x = -Math.PI / 2; // Plasticity uses Z up.
  for (const part of mesh.parts) {
    if (part.indices.length) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(part.positions, 3));
      geometry.setAttribute('normal', new THREE.Float32BufferAttribute(part.normals, 3));
      geometry.setIndex(part.indices);
      model.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color:0xbcbcbc, metalness:0.25, roughness:0.45, side:THREE.DoubleSide})));
    }
    // The kernel stores each edge as a separate polyline (offset/count in floats).
    const segments = [];
    for (let g = 0; g < part.edge_groups.length; g += 2) {
      const start = part.edge_groups[g], count = part.edge_groups[g + 1];
      for (let i = start; i + 5 < start + count; i += 3) segments.push(...part.edges.slice(i, i + 6));
    }
    if (segments.length) {
      const lines = new THREE.BufferGeometry();
      lines.setAttribute('position', new THREE.Float32BufferAttribute(segments, 3));
      model.add(new THREE.LineSegments(lines, new THREE.LineBasicMaterial({color:part.indices.length ? 0x555555 : 0xd4d4d4})));
    }
  }
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  model.position.sub(center);
  scene.add(model, new THREE.HemisphereLight(0xffffff, 0x333333, 2));
  const light = new THREE.DirectionalLight(0xffffff, 3);
  light.position.set(3, 5, 4);scene.add(light);
  const fill = new THREE.DirectionalLight(0xffffff, 1);
  fill.position.set(-3, 0, -4);scene.add(fill);
  const radius = Math.max(size.length() * 0.5, 1e-6);
  const extent = radius * 1.15;
  const camera = new THREE.OrthographicCamera(-extent, extent, extent, -extent, radius / 1000, radius * 100);
  camera.position.set(1.5, 1.1, 1.6).normalize().multiplyScalar(radius * 3.8);
  camera.lookAt(0, 0, 0);
  return {scene, camera, extent, model, radius, dispose:() => scene.traverse(object => {object.geometry?.dispose();object.material?.dispose();})};
}

