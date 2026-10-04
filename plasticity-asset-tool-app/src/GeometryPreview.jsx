import { createEffect, createMemo, createSignal, onCleanup, onMount, Show, untrack } from 'solid-js';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let thumbnailRenderer;

function sceneFor(mesh) {
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
  return {scene, camera, extent, dispose:() => scene.traverse(object => {object.geometry?.dispose();object.material?.dispose();})};
}

// All component thumbnails share one offscreen WebGL context.
export function renderThumbnail(mesh) {
  thumbnailRenderer ||= new THREE.WebGLRenderer({antialias:true, preserveDrawingBuffer:true});
  thumbnailRenderer.setSize(512, 512, false);
  thumbnailRenderer.setPixelRatio(1);
  const view = sceneFor(mesh);
  try {thumbnailRenderer.render(view.scene, view.camera);return thumbnailRenderer.domElement.toDataURL('image/jpeg', 0.86);}
  finally {view.dispose();thumbnailRenderer.renderLists.dispose();}
}

export function GeometryPreview(props) {
  let container, renderer, view, controls, resize;
  const [error, setError] = createSignal('');
  const [loading, setLoading] = createSignal(false);
  const digest = createMemo(()=>props.asset?.digest);
  let revision = 0;
  let pointer = props.heldOrigin;
  const rotateHeld = event => {
    if (!props.heldOrigin || !(event.buttons & 2)) return;
    const previous = pointer;
    pointer = {x:event.clientX,y:event.clientY};
    if (!view || !previous) return;
    const orbit = new THREE.Spherical().setFromVector3(view.camera.position);
    orbit.theta -= (pointer.x - previous.x) * 0.01;
    orbit.phi -= (pointer.y - previous.y) * 0.01;
    orbit.makeSafe();
    view.camera.position.setFromSpherical(orbit);
    view.camera.lookAt(0,0,0);draw();
  };
  const destroy = () => {controls?.dispose();view?.dispose();controls = null;view = null;};
  const draw = () => {if(renderer && view)renderer.render(view.scene,view.camera);};
  const fit = () => {
    if(!renderer || !view)return;
    const width = container.clientWidth, height = container.clientHeight;
    if(!width || !height)return;
    const aspect=width/height;
    const halfHeight=view.extent/Math.min(aspect,1);
    view.camera.left=-halfHeight*aspect;view.camera.right=halfHeight*aspect;
    view.camera.top=halfHeight;view.camera.bottom=-halfHeight;
    renderer.setSize(width,height,false);view.camera.updateProjectionMatrix();draw();
  };
  onMount(() => {
    if(props.heldOrigin)window.addEventListener('pointermove',rotateHeld,true);
    try {
      renderer = new THREE.WebGLRenderer({antialias:true});
      renderer.setPixelRatio(Math.min(devicePixelRatio,2));
      renderer.domElement.setAttribute('aria-label','组件三维预览，可拖动旋转及滚轮缩放');
      container.append(renderer.domElement);
      resize = new ResizeObserver(fit);resize.observe(container);
    }catch(e){setError('当前设备无法启用三维预览');}
  });
  createEffect(() => {
    if(!digest())return;
    const asset = untrack(()=>props.asset);
    if(!renderer)return;
    const current = ++revision;
    destroy();setError('');setLoading(true);
    props.load(asset).then(mesh => {
      if(current !== revision || !renderer)return;
      view=sceneFor(mesh);
      controls=new OrbitControls(view.camera,renderer.domElement);
      if(props.heldOrigin)controls.enabled=false;
      controls.enablePan=false;controls.minZoom=0.2;controls.maxZoom=20;
      controls.addEventListener('change',draw);fit();
    }).catch(e=>{if(current===revision)setError(e.message);}).finally(()=>{if(current===revision)setLoading(false);});
  });
  onCleanup(()=>{revision++;window.removeEventListener('pointermove',rotateHeld,true);resize?.disconnect();destroy();renderer?.dispose();renderer?.forceContextLoss();});
  return <div class="geometry-viewer" title={props.heldOrigin ? "按住右键移动旋转，松开恢复" : "拖动旋转 · 滚轮缩放"}><div class="geometry-canvas" ref={container}/><Show when={loading()}><p class="geometry-message">正在生成几何预览…</p></Show><Show when={error()}><p class="geometry-message geometry-error" role="status">{error()}</p></Show></div>;
}
