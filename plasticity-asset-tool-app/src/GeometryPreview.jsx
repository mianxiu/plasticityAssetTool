import {t} from "./i18n";
import { createEffect, createMemo, createSignal, onCleanup, onMount, Show, untrack } from 'solid-js';
import * as THREE from 'three';
import {sceneFor} from './geometryScene.mjs';
import {meshBounds, presetBasePoint} from './previewBasePoint.mjs';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let thumbnailRenderer;

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
  const [picking,setPicking] = createSignal(false);
  const [bounds,setBounds] = createSignal(null);
  let marker, pickObjects=[];
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
  const destroy = () => {controls?.dispose();view?.dispose();controls = null;view = null;marker=null;pickObjects=[];};
  const draw = () => {if(renderer && view){marker?.scale.setScalar(1/view.camera.zoom);renderer.render(view.scene,view.camera);}};
  const updateMarker = () => {
    if(!view || !props.editBasePoint)return;
    if(!marker){
      marker=new THREE.Group();
      const radius=view.radius*0.045;
      const geometry=new THREE.BufferGeometry();
      geometry.setAttribute('position',new THREE.Float32BufferAttribute([-radius,0,0,radius,0,0,0,-radius,0,0,radius,0,0,0,-radius,0,0,radius],3));
      const cross=new THREE.LineSegments(geometry,new THREE.LineBasicMaterial({color:0xffcc55,depthTest:false,depthWrite:false}));
      cross.renderOrder=1000;
      const dot=new THREE.Mesh(new THREE.SphereGeometry(radius*0.16,12,8),new THREE.MeshBasicMaterial({color:0xffcc55,depthTest:false,depthWrite:false}));
      dot.renderOrder=1001;marker.add(cross,dot);view.model.add(marker);
    }
    const point=props.basePoint;
    marker.visible=Array.isArray(point) && point.length===3 && point.every(Number.isFinite);
    if(marker.visible)marker.position.fromArray(point);
    draw();
  };
  createEffect(()=>{props.basePoint;updateMarker();});
  const pickPoint = event => {
    if(!picking() || props.disabled || event.button!==0 || !view)return;
    const rect=renderer.domElement.getBoundingClientRect();
    const ray=new THREE.Raycaster();
    ray.params.Line.threshold=view.radius*0.018/view.camera.zoom;
    ray.setFromCamera(new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,1-(event.clientY-rect.top)/rect.height*2),view.camera);
    view.scene.updateMatrixWorld(true);
    const hit=ray.intersectObjects(pickObjects,false)[0];
    if(hit){props.onBasePointChange?.(view.model.worldToLocal(hit.point.clone()).toArray());setPicking(false);}
  };
  const preset = mode => {const point=presetBasePoint(bounds(),mode);if(point){props.onBasePointChange?.(point);setPicking(false);}};
  const inputCoordinate = (axis,event) => {
    if(!event.currentTarget.validity.valid || event.currentTarget.value===''){
      event.currentTarget.value=props.basePoint[axis];return;
    }
    const value=Number(event.currentTarget.value);
    if(!Number.isFinite(value))return;
    const point=[...props.basePoint];point[axis]=value;props.onBasePointChange?.(point);
  };
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
      renderer.domElement.setAttribute('aria-label',t('右键拖动旋转 · 滚轮缩放'));
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
      pickObjects=[...view.model.children];setBounds(meshBounds(mesh));setPicking(false);updateMarker();
      controls=new OrbitControls(view.camera,renderer.domElement);
      controls.mouseButtons.LEFT=null;
      controls.mouseButtons.RIGHT=THREE.MOUSE.ROTATE;
      if(props.heldOrigin)controls.enabled=false;
      controls.enablePan=false;controls.minZoom=0.2;controls.maxZoom=20;
      controls.addEventListener('change',draw);fit();
    }).catch(e=>{if(current===revision)setError(e.message);}).finally(()=>{if(current===revision)setLoading(false);});
  });
  onCleanup(()=>{revision++;window.removeEventListener('pointermove',rotateHeld,true);resize?.disconnect();destroy();renderer?.dispose();renderer?.forceContextLoss();});
  return <><div class="geometry-viewer" title={props.heldOrigin ? t("按住右键移动旋转，松开恢复") : t("右键拖动旋转 · 滚轮缩放")}><div class="geometry-canvas" classList={{'base-point-picking':picking()}} ref={container} onClick={pickPoint}/><Show when={picking()}><span class="base-point-pick-status">{t("点击表面或曲线设置基点")}</span></Show><Show when={loading()}><p class="geometry-message">{t("正在生成几何预览…")}</p></Show><Show when={error()}><p class="geometry-message geometry-error" role="status">{error()}</p></Show></div>
    <Show when={props.editBasePoint}><fieldset class="preview-base-point" disabled={props.disabled || !props.basePoint}>
      <legend>{t("组件基点")}<span class="help-tip" tabindex="0" data-tip={t("黄色十字表示基点。修改后点击保存修改；坐标使用模型原生单位。表面拾取基于预览网格。")}>?</span></legend>
      <div class="base-point-presets"><button type="button" class="secondary" classList={{active:picking()}} disabled={!bounds()} onClick={()=>setPicking(!picking())}>{picking()?t("取消拾取"):t("预览拾取")}</button><button type="button" class="secondary" onClick={()=>preset('world')}>{t("世界原点")}</button><button type="button" class="secondary" disabled={!bounds()} onClick={()=>preset('center')}>{t("模型中心")}</button><button type="button" class="secondary" disabled={!bounds()} onClick={()=>preset('bottom')}>{t("底部中心")}</button></div>
      <div class="base-point-coordinates">{['X','Y','Z'].map((axis,i)=><label>{axis}<input type="number" step="any" min="-1e12" max="1e12" aria-label={t("基点坐标 ")+axis} value={props.basePoint?.[i] ?? ''} onChange={event=>inputCoordinate(i,event)}/></label>)}</div>
    </fieldset></Show></>;
}
