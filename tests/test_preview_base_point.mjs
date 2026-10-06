import assert from 'node:assert/strict';
import * as THREE from '../plasticity-asset-tool-app/node_modules/three/build/three.module.js';
import {sceneFor} from '../plasticity-asset-tool-app/src/geometryScene.mjs';
import {meshBounds,presetBasePoint} from '../plasticity-asset-tool-app/src/previewBasePoint.mjs';
const mesh={parts:[{positions:[10,20,30,14,20,30,10,24,30],normals:[0,0,1,0,0,1,0,0,1],indices:[0,1,2],edges:[],edge_groups:[]}]};
const bounds=meshBounds(mesh);
assert.deepEqual(presetBasePoint(bounds,'world'),[0,0,0]);
assert.deepEqual(presetBasePoint(bounds,'center'),[12,22,30]);
const wire={parts:[{positions:[],edges:[-2,4,-8,6,10,12]}]};
assert.deepEqual(presetBasePoint(meshBounds(wire),'bottom'),[2,7,-8]);
const view=sceneFor(mesh);
view.scene.updateMatrixWorld(true);view.camera.updateMatrixWorld(true);
const original=new THREE.Vector3(11,21,30);
const world=view.model.localToWorld(original.clone());
const projected=world.clone().project(view.camera);
const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(projected.x,projected.y),view.camera);
const hit=ray.intersectObjects(view.model.children)[0];assert.ok(hit);
assert.ok(view.model.worldToLocal(hit.point.clone()).distanceTo(original)<1e-6,'Picking must undo preview centering and Z-up rotation');
view.camera.zoom=3;view.camera.updateProjectionMatrix();
const projectedZoom=world.clone().project(view.camera);ray.setFromCamera(new THREE.Vector2(projectedZoom.x,projectedZoom.y),view.camera);
assert.ok(view.model.worldToLocal(ray.intersectObjects(view.model.children)[0].point.clone()).distanceTo(original)<1e-6);
view.dispose();
console.log('Preview base point: world coordinates, Z-up presets and zoomed ray picking verified');

const {snapCandidates,closestSnap,normalOrientation}=await import('../plasticity-asset-tool-app/src/previewSnapping.mjs');
const snaps=snapCandidates({parts:[{edges:[0,0,0,2,0,0,2,6,0],edge_groups:[0,9]}]});
assert.deepEqual(snaps.map(s=>s.point),[[0,0,0],[2,6,0],[2,2,0]],'Midpoint must use arc length, not sample index');
const camera=new THREE.OrthographicCamera(-10,10,10,-10,.1,100);camera.position.z=20;camera.lookAt(0,0,0);camera.updateMatrixWorld(true);
const model=new THREE.Group();model.updateMatrixWorld(true);
assert.equal(closestSnap(snaps,model,camera,{width:200,height:200},{x:102,y:101}).type,'顶点');
assert.equal(closestSnap(snaps,model,camera,{width:200,height:200},{x:150,y:150}),null);
assert.equal(closestSnap(snaps,model,camera,{width:200,height:200},{x:100,y:100},-1),null,'Occluded snaps must be rejected');
const orientation=new THREE.Quaternion().fromArray(normalOrientation([1,0,0]));
assert.ok(new THREE.Vector3(0,0,1).applyQuaternion(orientation).distanceTo(new THREE.Vector3(1,0,0))<1e-8);
console.log('Snapping: endpoints, arc midpoint, screen threshold, depth rejection and native Z orientation verified');

const {rotateBaseOrientation,directionMarker,basePointMarker}=await import('../plasticity-asset-tool-app/src/previewOrientation.mjs');
const originalOrientation=normalOrientation([1,2,3]);
for(const axis of [0,1,2]) {
  const flipped=new THREE.Quaternion().fromArray(rotateBaseOrientation(originalOrientation,axis,180));
  const before=new THREE.Vector3(0,0,1).applyQuaternion(new THREE.Quaternion().fromArray(originalOrientation));
  const after=new THREE.Vector3(0,0,1).applyQuaternion(flipped);
  assert.ok(after.distanceTo(before.clone().multiplyScalar(axis===2?1:-1))<1e-8);
  const restored=new THREE.Quaternion().fromArray(rotateBaseOrientation(flipped.toArray(),axis,180));
  assert.ok(1-Math.abs(restored.dot(new THREE.Quaternion().fromArray(originalOrientation)))<1e-8);
}
const gizmo=directionMarker(2);
assert.equal(gizmo.children.length,4);
assert.equal(gizmo.children[0].children[1].geometry.type,'TorusGeometry');
for(const [index,axis] of [[1,[1,0,0]],[2,[0,1,0]],[3,[0,0,1]]]) {
  const arrow=gizmo.children[index];
  assert.ok(new THREE.Vector3(0,1,0).applyQuaternion(arrow.quaternion).distanceTo(new THREE.Vector3(...axis))<1e-8);
  const [outline,shaft]=arrow.children[0].children;
  assert.equal(shaft.geometry.type,'CylinderGeometry');
  assert.ok(outline.geometry.parameters.radiusTop>shaft.geometry.parameters.radiusTop);
  assert.ok(outline.renderOrder<shaft.renderOrder);
  assert.equal(arrow.children[2].geometry.type,'ConeGeometry');
}
gizmo.traverse(object=>{if(object.material){assert.equal(object.material.depthTest,false);assert.equal(object.material.depthWrite,false);}});
gizmo.traverse(object=>{object.geometry?.dispose();object.material?.dispose();});
const baseMarker=basePointMarker(1);
assert.equal(baseMarker.children.length,6);
baseMarker.traverse(object=>{if(object.material)assert.equal(object.material.depthTest,false);object.geometry?.dispose();object.material?.dispose();});
console.log('Outlined mesh arrows, base cross and local-axis flips verified for a tilted base frame');
