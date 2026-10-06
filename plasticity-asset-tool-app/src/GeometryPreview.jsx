import {t} from "./i18n";
import { createEffect, createMemo, createSignal, onCleanup, onMount, Show, untrack } from 'solid-js';
import {Portal} from 'solid-js/web';
import {snapCandidates,kernelSnapCandidates,preferredSnapCandidates,closestSnap,normalOrientation} from './previewSnapping.mjs';
import * as THREE from 'three';
import {sceneFor} from './geometryScene.mjs';
import {directionMarker, basePointMarker, rotateBaseOrientation} from './previewOrientation.mjs';
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
  const [kernelCandidates,setKernelCandidates] = createSignal([]);
  const [kernelLoading,setKernelLoading] = createSignal(false);
  const [kernelError,setKernelError] = createSignal('');
  const [alignNormal,setAlignNormal] = createSignal(true);
  const [axisDirections,setAxisDirections] = createSignal([]);
  const [annotation,setAnnotation] = createSignal(null);
  const [snapLabel,setSnapLabel] = createSignal('');
  const [draftPoint,setDraftPoint] = createSignal(null);
  const [draftOrientation,setDraftOrientation] = createSignal(null);
  const [bounds,setBounds] = createSignal(null);
  let marker, ghost, editor, previousFocus, candidates=[], pickObjects=[];
  const openExpanded=()=>{setDraftPoint([...(props.basePoint || [0,0,0])]);setDraftOrientation([...(props.orientation || [0,0,0,1])]);setExpanded(true);previousFocus=document.activeElement;queueMicrotask(()=>editor?.querySelector('button')?.focus());};
  const closeExpanded=()=>{setExpanded(false);previousFocus?.focus();};
  const escape=event=>{
    if(!expanded())return;
    if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();closeExpanded();}
    if(event.key==='Tab'){
      event.stopImmediatePropagation();
      const inputs=[...editor.querySelectorAll('button:not(:disabled),input:not(:disabled),[tabindex="0"]')];
      const index=inputs.indexOf(document.activeElement);
      if(index<0 || !event.shiftKey && index===inputs.length-1 || event.shiftKey && index===0){
        event.preventDefault();inputs[event.shiftKey ? inputs.length-1 : 0]?.focus();
      }
    }
  };
  onMount(()=>window.addEventListener('keydown',escape,true));
  onCleanup(()=>window.removeEventListener('keydown',escape,true));
  const digest = createMemo(()=>props.asset?.digest);
  let revision = 0;
  const loadDefaultSnaps=async (asset,current)=>{
    if(!props.fullscreen || kernelCandidates().length || !props.loadKernel)return;
    setKernelLoading(true);
    try {
      const mesh=await props.loadKernel(asset);
      if(current!==revision || !renderer)return;
      const points=kernelSnapCandidates(mesh);
      if(!points.length)throw new Error(t('此组件暂无可用的内核捕捉点'));
      setKernelCandidates(points);
    }catch(error){if(current===revision)setKernelError(t('已回退到预览吸附：{reason}',{reason:error.message}));}
    finally {if(current===revision)setKernelLoading(false);}
  };
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
  const draw = () => {
    if(!renderer || !view)return;
    marker?.scale.setScalar(1/view.camera.zoom);ghost?.scale.setScalar(1/view.camera.zoom);
    renderer.render(view.scene,view.camera);
    const inverse=view.camera.quaternion.clone().invert();
    setAxisDirections([[1,0,0],[0,1,0],[0,0,1]].map(axis=>{
      const v=new THREE.Vector3().fromArray(axis).transformDirection(view.model.matrixWorld).applyQuaternion(inverse);
      return {x:44+v.x*27,y:44-v.y*27};
    }));
    const anchor=ghost?.visible ? ghost : marker?.visible ? marker : null;
    if(anchor){
      const point=anchor.getWorldPosition(new THREE.Vector3()).project(view.camera);
      setAnnotation(point.z>=-1 && point.z<=1 && Math.abs(point.x)<=1 && Math.abs(point.y)<=1 ? {
        x:Math.max(8,Math.min(container.clientWidth-100,(point.x+1)*container.clientWidth/2+14)),
        y:Math.max(8,Math.min(container.clientHeight-26,(1-point.y)*container.clientHeight/2+14)),
        hover:!!ghost?.visible
      } : null);
    }else setAnnotation(null);
  };
  const updateMarker = () => {
    if(!view)return;
    if(!marker){
      const radius=view.radius*0.045;
      marker=basePointMarker(radius);
      ghost=directionMarker(radius*2.3);ghost.visible=false;
      view.model.add(marker,ghost);
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
    const targets=snapping() ? preferredSnapCandidates(candidates,kernelCandidates()) : [];
    const snap=closestSnap(targets,view.model,view.camera,rect,{x:event.clientX-rect.left,y:event.clientY-rect.top},hit?hit.point.clone().project(view.camera).z:Infinity,view.radius*.1/view.camera.zoom/(view.camera.far-view.camera.near));
    if(!hit && !snap)return null;
    const surface=hits.find(h=>h.face && (!snap || h.point.distanceTo(view.model.localToWorld(new THREE.Vector3().fromArray(snap.point)))<view.radius*.08/view.camera.zoom));
    let normal=surface?.face.normal.clone().transformDirection(surface.object.matrixWorld);
    if(normal)normal.transformDirection(new THREE.Matrix4().copy(view.model.matrixWorld).invert());
    if(snap?.normal)normal=new THREE.Vector3().fromArray(snap.normal);
    return {point:snap?.point || view.model.worldToLocal(hit.point.clone()).toArray(),type:snap?.kernel ? '内核 · '+snap.type : snap?.type || (hit.face?'表面':'曲线'),normal};
  };
  const hoverPoint = event => {
    const hit=pointerHit(event);setSnapLabel(hit?.type || '');
    if(ghost){ghost.visible=!!hit;if(hit){ghost.position.fromArray(hit.point);ghost.quaternion.fromArray(alignNormal() && hit.normal ? normalOrientation(hit.normal.toArray()) : (props.orientation || [0,0,0,1]));}draw();}
  };
  const pickPoint = event => {
    if(event.button!==0 || event.buttons & 2)return;
    const hit=pointerHit(event);
    if(hit){props.onBasePointChange?.(hit.point);if(alignNormal() && hit.normal)props.onOrientationChange?.(normalOrientation(hit.normal.toArray()));setPicking(false);setSnapLabel('');if(ghost)ghost.visible=false;draw();}
  };
  const angles = ()=>new THREE.Euler().setFromQuaternion(new THREE.Quaternion().fromArray(props.orientation || [0,0,0,1]).normalize(),'XYZ').toArray().slice(0,3).map(THREE.MathUtils.radToDeg);
  const inputAngle=(axis,event)=>{
    if(!event.currentTarget.validity.valid || event.currentTarget.value==='')return;
    const value=Number(event.currentTarget.value);if(!Number.isFinite(value))return;
    const values=angles();values[axis]=value;
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
    destroy();setError('');setLoading(true);setKernelCandidates([]);setKernelError('');setKernelLoading(false);
    props.load(asset).then(mesh => {
      if(current !== revision || !renderer)return;
      view=sceneFor(mesh);
      setKernelCandidates(kernelSnapCandidates(mesh));
      pickObjects=[...view.model.children];candidates=snapCandidates(mesh);setBounds(meshBounds(mesh));setPicking(!!props.fullscreen);updateMarker();
      controls=new OrbitControls(view.camera,renderer.domElement);
      controls.mouseButtons.LEFT=null;
      controls.mouseButtons.RIGHT=THREE.MOUSE.ROTATE;
      if(props.heldOrigin)controls.enabled=false;
      controls.enablePan=false;controls.minZoom=0.2;controls.maxZoom=20;
      controls.addEventListener('change',draw);fit();
      void loadDefaultSnaps(asset,current);
    }).catch(e=>{if(current===revision)setError(e.message);}).finally(()=>{if(current===revision)setLoading(false);});
  });
  onCleanup(()=>{revision++;window.removeEventListener('pointermove',rotateHeld,true);resize?.disconnect();destroy();renderer?.dispose();renderer?.forceContextLoss();});
  return <><div class="geometry-viewer" title={props.heldOrigin ? t("按住右键移动旋转，松开恢复") : t("右键拖动旋转 · 滚轮缩放")}><div class="geometry-canvas" classList={{'base-point-picking':picking()}} ref={container} onClick={pickPoint} onPointerMove={hoverPoint} onPointerLeave={()=>{if(ghost){ghost.visible=false;draw();}setSnapLabel('');}}/><svg class="preview-direction-axes" viewBox="0 0 88 88" role="img" aria-label={t("方向：红 X / 绿 Y / 蓝 Z")}><circle cx="44" cy="44" r="3" fill="#ddd"/>{axisDirections().map((axis,i)=><g stroke={['#ff6666','#66dd88','#669fff'][i]}><line x1="44" y1="44" x2={axis.x} y2={axis.y}/><text x={axis.x} y={axis.y-5} fill={['#ff6666','#66dd88','#669fff'][i]} stroke="none" text-anchor="middle">{['X','Y','Z'][i]}</text></g>)}</svg><Show when={annotation()}>{label=><span class="preview-point-annotation" style={{left:`${label().x}px`,top:`${label().y}px`}}>{label().hover ? t(snapLabel() || '表面') : t('基点')} · Z</span>}</Show><Show when={picking()}><span class="base-point-pick-status">{snapLabel()?t(snapLabel()):t("点击表面或曲线设置基点")}</span></Show><Show when={loading()}><p class="geometry-message">{t("正在生成几何预览…")}</p></Show><Show when={error()}><p class="geometry-message geometry-error" role="status">{error()}</p></Show></div>
    <Show when={props.editBasePoint}><fieldset class="preview-base-point" disabled={props.disabled || !props.basePoint}>
      <legend>{t("组件基点")}<span class="help-tip" tabindex="0" data-tip={t("黄色十字表示基点。修改后点击保存修改；坐标使用模型原生单位。表面拾取基于预览网格。")}>?</span></legend>
      <Show when={props.fullscreen} fallback={<button type="button" class="secondary base-point-expand" disabled={!bounds()} onClick={openExpanded}>{t("编辑基点")}</button>}><div class="base-point-presets"><button type="button" class="secondary" classList={{active:picking()}} disabled={!bounds()} onClick={()=>setPicking(!picking())}>{picking()?t("取消拾取"):t("预览拾取")}</button><Show when={props.onNativePick}><button type="button" class="secondary" disabled={props.nativeDisabled} title={t("在 Plasticity 使用原生捕捉；确认后立即保存基点，Esc 取消。")} onClick={()=>props.onNativePick()}>{t("Plasticity 精确拾取")}</button></Show><button type="button" class="secondary" onClick={()=>preset('world')}>{t("世界原点")}</button><button type="button" class="secondary" disabled={!bounds()} onClick={()=>preset('center')}>{t("模型中心")}</button><button type="button" class="secondary" disabled={!bounds()} onClick={()=>preset('bottom')}>{t("底部中心")}</button></div>
      <div class="base-point-coordinates">{['X','Y','Z'].map((axis,i)=><label>{axis}<input type="number" step="any" min="-1e12" max="1e12" aria-label={t("基点坐标 ")+axis} value={props.basePoint?.[i] ?? ''} onInput={event=>inputCoordinate(i,event)}/></label>)}</div>
      <div class="base-point-options"><label><input type="checkbox" checked={snapping()} onChange={e=>setSnapping(e.currentTarget.checked)}/>{t("吸附端点 / 边中点 / 面中心")}</label><label><input type="checkbox" checked={alignNormal()} onChange={e=>setAlignNormal(e.currentTarget.checked)}/>{t("按面法线定向")}</label></div>
      <Show when={snapping() && (kernelLoading() || kernelCandidates().length)}><p class="kernel-snap-status" role="status">{kernelLoading()?t("正在加载内核捕捉点…"):t("内核捕捉已启用")}</p></Show>
      <Show when={kernelError()}><p class="kernel-snap-status" role="status">{kernelError()}</p></Show>
      <div class="base-point-coordinates">{['X','Y','Z'].map((axis,i)=><label>{axis}°<input type="number" step="1" aria-label={t("基点旋转 ")+axis} value={Number(angles()[i].toFixed(3))} onInput={event=>inputAngle(i,event)}/></label>)}</div>
      <div class="base-point-flips">{['X','Y','Z'].map((axis,i)=><button type="button" class="secondary" onClick={()=>props.onOrientationChange?.(rotateBaseOrientation(props.orientation,i,180))}>{t('绕 {axis} 反转 180°',{axis})}</button>)}</div>
      <button type="button" class="secondary" onClick={()=>props.onOrientationChange?.([0,0,0,1])}>{t("重置方向")}</button></Show>
    </fieldset></Show>
    <Show when={expanded()}><Portal><div class="base-point-editor-backdrop" onClick={e=>e.stopPropagation()}><div class="base-point-fullscreen component-first" ref={editor} role="dialog" aria-modal="true" aria-label={t("基点编辑器")} onClick={e=>e.stopPropagation()} onContextMenu={e=>e.preventDefault()}>
      <header><strong>{t("基点编辑器")}</strong><span>{t("右键拖动旋转 · 滚轮缩放")} · {t("方向：红 X / 绿 Y / 蓝 Z")}</span><button type="button" class="secondary" onClick={closeExpanded}>{t("取消")}</button></header>
      <GeometryPreview asset={props.asset} load={props.load} loadKernel={props.loadKernel} fullscreen editBasePoint basePoint={draftPoint()} orientation={draftOrientation()} onBasePointChange={setDraftPoint} onOrientationChange={setDraftOrientation} onNativePick={props.onNativePick ? ()=>{closeExpanded();props.onNativePick();} : undefined} nativeDisabled={props.nativeDisabled} disabled={props.disabled}/>
      <footer><span>{t("确认后仍需保存修改")}</span><button type="button" class="secondary" onClick={closeExpanded}>{t("取消")}</button><button type="button" disabled={props.disabled} onClick={()=>{props.onBasePointChange?.(draftPoint());props.onOrientationChange?.(draftOrientation());closeExpanded();}}>{t("确认基点")}</button></footer>
    </div></div></Portal></Show></>;
}
