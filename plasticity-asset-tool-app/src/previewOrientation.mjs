import * as THREE from 'three';

// Rotate in the base point's local frame; X/Y reverse its Z normal.
export function rotateBaseOrientation(orientation, axis, degrees) {
  const direction = new THREE.Vector3();
  direction.setComponent(axis, 1);
  return new THREE.Quaternion().fromArray(orientation || [0,0,0,1]).normalize()
    .multiply(new THREE.Quaternion().setFromAxisAngle(direction, THREE.MathUtils.degToRad(degrees)))
    .normalize().toArray();
}

export function directionMarker(radius, color = 0x397cff) {
  const group = new THREE.Group();
  const material = new THREE.LineBasicMaterial({color, depthTest:false, depthWrite:false});
  const points = Array.from({length:65}, (_,i) => {
    const angle=i/64*Math.PI*2;
    return new THREE.Vector3(Math.cos(angle)*radius,Math.sin(angle)*radius,0);
  });
  const ring = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material);
  ring.renderOrder=1002;
  group.add(ring);
  for (const [axis, tint, length] of [[new THREE.Vector3(1,0,0),0xff6666,1.25],
    [new THREE.Vector3(0,1,0),0x66dd88,1.25],[new THREE.Vector3(0,0,1),color,1.8]]) {
    const arrow=new THREE.ArrowHelper(axis,new THREE.Vector3(),radius*length,tint,radius*.25,radius*.14);
    for (const object of [arrow.line,arrow.cone]) {
      object.material.depthTest=false;object.material.depthWrite=false;object.renderOrder=1003;
    }
    group.add(arrow);
  }
  return group;
}
