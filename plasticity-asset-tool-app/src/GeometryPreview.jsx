import {t} from "./i18n";
import { createEffect, createMemo, createSignal, onCleanup, onMount, Show, untrack } from 'solid-js';
import {Portal} from 'solid-js/web';
import {snapCandidates,closestSnap,normalOrientation} from './previewSnapping.mjs';
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
  const [expanded,setExpanded] = createSignal(false);
  const [snapping,setSnapping] = createSignal(true);
  const [alignNormal,setAlignNormal] = createSignal(false);
  const [snapLabel,setSnapLabel] = createSignal('');
  const [draftPoint,setDraftPoint] = createSignal(null);
  const [draftOrientation,setDraftOrientation] = createSignal(null);
  const [bounds,setBounds] = createSignal(null);
  let marker, ghost, candidates=[], pickObjects=[];
  const openExpanded=()=>{setDraftPoint([...props.basePoint]);setDraftOrientation([...(props.orientation || [0,0,0,1])]);setExpanded(true);};
  const closeExpanded=()=>setExpanded(false);
  const escape=event=>{if(expanded() && event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();closeExpanded();}};
  onMount(()=>window.addEventListener('keydown',escape,true));
  onCleanup(()=>window.removeEventListener('keydown',escape,true));
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
  const destroy = () => {controls?.dispose();view?.dispose();controls = null;view = null;marker=null;ghost=null;candidates=[];pickObjects=[];};
  const draw = () => {if(renderer && view){marker?.scale.setScalar(1/view.camera.zoom);ghost?.scale.setScalar(1/view.camera.zoom);renderer.render(view.scene,view.camera);}};
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
      dot.renderOrder=1001;marker.add(cross,dot);
      for(const [axis,color] of [[new THREE.Vector3(1,0,0),0xff6666],[new THREE.Vector3(0,1,0),0x66dd88],[new THREE.Vector3(0,0,1),0x66aaff]]){
        const arrow=new THREE.ArrowHelper(axis,new THREE.Vector3(),radius*3,color,radius*.6,radius*.35);
        for(const object of [arrow.line,arrow.cone]){object.material.depthTest=false;object.material.depthWrite=false;object.renderOrder=1002;}marker.add(arrow);
      }
      ghost=new THREE.Mesh(new THREE.SphereGeometry(radius*.22,12,8),new THREE.MeshBasicMaterial({color:0xffcc55,depthTest:false,depthWrite:false}));ghost.visible=false;ghost.renderOrder=1003;view.model.add(marker,ghost);
    }
    const point=props.basePoint;
    marker.visible=Array.isArray(point) && point.length===3 && point.every(Number.isFinite);
    if(marker.visible){marker.position.fromArray(point);marker.quaternion.fromArray(props.orientation || [0,0,0,1]).normalize();}
    draw();
  };
  createEffect(()=>{props.basePoint;props.orientation;updateMarker();});
  createEffect(()=>{if(!picking() && ghost){ghost.visible=false;draw();}});
  const pointerHit = event => {
    if(!picking() || props.disabled || !view)return null;
    const rect=renderer.domElement.getBoundingClientRect();
    const ray=new THREE.Raycaster();
    ray.params.Line.threshold=view.radius*0.018/view.camera.zoom;
    ray.setFromCamera(new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,1-(event.clientY-rect.top)/rect.height*2),view.camera);
    view.scene.updateMatrixWorld(true);view.camera.updateMatrixWorld(true);
    const hits=ray.intersectObjects(pickObjects,false);
    const hit=hits[0];
    const snap=snapping()?closestSnap(candidates,view.model,view.camera,rect,{x:event.clientX-rect.left,y:event.clientY-rect.top},hit?hit.point.clone().project(view.camera).z:Infinity,view.radius*.1/view.camera.zoom/(view.camera.far-view.camera.near)):null;
    if(!hit && !snap)return null;
    const surface=hits.find(h=>h.face && (!snap || h.point.distanceTo(view.model.localToWorld(new THREE.Vector3().fromArray(snap.point)))<view.radius*.08/view.camera.zoom));
    const normal=surface?.face.normal.clone().transformDirection(surface.object.matrixWorld);
    if(normal)normal.transformDirection(new THREE.Matrix4().copy(view.model.matrixWorld).invert());
    return {point:snap?.point || view.model.worldToLocal(hit.point.clone()).toArray(),type:snap?.type || (hit.face?'表面':'曲线'),normal};
  };
  const hoverPoint = event => {
    const hit=pointerHit(event);setSnapLabel(hit?.type || '');
    if(ghost){ghost.visible=!!hit;if(hit)ghost.position.fromArray(hit.point);draw();}
  };
  const pickPoint = event => {
    if(event.button!==0)return;
    const hit=pointerHit(event);
    if(hit){props.onBasePointChange?.(hit.point);if(alignNormal() && hit.normal)props.onOrientationChange?.(normalOrientation(hit.normal.toArray()));setPicking(false);if(ghost)ghost.visible=false;draw();}
  };
  const angles = ()=>new THREE.Euler().setFromQuaternion(new THREE.Quaternion().fromArray(props.orientation || [0,0,0,1]).normalize(),'XYZ').toArray().slice(0,3).map(THREE.MathUtils.radToDeg);
  const inputAngle=(axis,event)=>{
    if(!event.currentTarget.validity.valid || event.currentTarget.value==='')return;
    const values=angles();values[axis]=Number(event.currentTarget.value);
    props.onOrientationChange?.(new THREE.Quaternion().setFromEuler(new THREE.Euler(...values.map(THREE.MathUtils.degToRad),'XYZ')).toArray());
  };
  const preset = mode => {const point=presetBasePoint(bounds(),mode);if(point){props.onBasePointChange?.(point);setPicking(false);}};
  const inputCoordinate = (axis,event) => {
    if(!event.currentTarget.validity.valid || event.currentTarget.value===''){
      return;
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
      pickObjects=[...view.model.children];candidates=snapCandidates(mesh);setBounds(meshBounds(mesh));setPicking(!!props.fullscreen);updateMarker();
      controls=new OrbitControls(view.camera,renderer.domElement);
      controls.mouseButtons.LEFT=null;
      controls.mouseButtons.RIGHT=THREE.MOUSE.ROTATE;
      if(props.heldOrigin)controls.enabled=false;
      controls.enablePan=false;controls.minZoom=0.2;controls.maxZoom=20;
      controls.addEventListener('change',draw);fit();
    }).catch(e=>{if(current===revision)setError(e.message);}).finally(()=>{if(current===revision)setLoading(false);});
  });
  onCleanup(()=>{revision++;window.removeEventListener('pointermove',rotateHeld,true);resize?.disconnect();destroy();renderer?.dispose();renderer?.forceContextLoss();});
  return <><div class="geometry-viewer" title={props.heldOrigin ? t("按住右键移动旋转，松开恢复") : t("右键拖动旋转 · 滚轮缩放")}><div class="geometry-canvas" classList={{'base-point-picking':picking()}} ref={container} onClick={pickPoint} onPointerMove={hoverPoint} onPointerLeave={()=>{if(ghost){ghost.visible=false;draw();}setSnapLabel('');}}/><Show when={picking()}><span class="base-point-pick-status">{snapLabel()?t(snapLabel()):t("点击表面或曲线设置基点")}</span></Show><Show when={loading()}><p class="geometry-message">{t("正在生成几何预览…")}</p></Show><Show when={error()}><p class="geometry-message geometry-error" role="status">{error()}</p></Show></div>
    <Show when={props.editBasePoint}><fieldset class="preview-base-point" disabled={props.disabled || !props.basePoint}>
      <legend>{t("组件基点")}<span class="help-tip" tabindex="0" data-tip={t("黄色十字表示基点。修改后点击保存修改；坐标使用模型原生单位。表面拾取基于预览网格。")}>?</span></legend>
      <Show when={!props.fullscreen}><button type="button" class="secondary base-point-expand" disabled={!bounds()} onClick={openExpanded}>{t("放大编辑基点")}</button></Show><div class="base-point-presets"><button type="button" class="secondary" classList={{active:picking()}} disabled={!bounds()} onClick={()=>setPicking(!picking())}>{picking()?t("取消拾取"):t("预览拾取")}</button><button type="button" class="secondary" onClick={()=>preset('world')}>{t("世界原点")}</button><button type="button" class="secondary" disabled={!bounds()} onClick={()=>preset('center')}>{t("模型中心")}</button><button type="button" class="secondary" disabled={!bounds()} onClick={()=>preset('bottom')}>{t("底部中心")}</button></div>
      <div class="base-point-coordinates">{['X','Y','Z'].map((axis,i)=><label>{axis}<input type="number" step="any" min="-1e12" max="1e12" aria-label={t("基点坐标 ")+axis} value={props.basePoint?.[i] ?? ''} onInput={event=>inputCoordinate(i,event)}/></label>)}</div>
      <div class="base-point-options"><label><input type="checkbox" checked={snapping()} onChange={e=>setSnapping(e.currentTarget.checked)}/>{t("吸附端点 / 边中点")}</label><label><input type="checkbox" checked={alignNormal()} onChange={e=>setAlignNormal(e.currentTarget.checked)}/>{t("按面法线定向")}</label></div>
      <div class="base-point-coordinates">{['X','Y','Z'].map((axis,i)=><label>{axis}°<input type="number" step="1" aria-label={t("基点旋转 ")+axis} value={Number(angles()[i].toFixed(3))} onInput={event=>inputAngle(i,event)}/></label>)}</div>
      <button type="button" class="secondary" onClick={()=>props.onOrientationChange?.([0,0,0,1])}>{t("重置方向")}</button>
    </fieldset></Show>
    <Show when={expanded()}><Portal><div class="base-point-fullscreen component-first" role="dialog" aria-modal="true" aria-label={t("基点编辑器")} onClick={e=>e.stopPropagation()} onContextMenu={e=>e.preventDefault()}>
      <header><strong>{t("基点编辑器")}</strong><span>{t("右键拖动旋转 · 滚轮缩放")} · {t("方向：红 X / 绿 Y / 蓝 Z")}</span><button type="button" class="secondary" onClick={closeExpanded}>{t("取消")}</button></header>
      <GeometryPreview asset={props.asset} load={props.load} fullscreen editBasePoint basePoint={draftPoint()} orientation={draftOrientation()} onBasePointChange={setDraftPoint} onOrientationChange={setDraftOrientation} disabled={props.disabled}/>
      <footer><span>{t("确认后仍需保存修改")}</span><button type="button" class="secondary" onClick={closeExpanded}>{t("取消")}</button><button type="button" disabled={props.disabled} onClick={()=>{props.onBasePointChange?.(draftPoint());props.onOrientationChange?.(draftOrientation());closeExpanded();}}>{t("确认基点")}</button></footer>
    </div></Portal></Show></>;
}
