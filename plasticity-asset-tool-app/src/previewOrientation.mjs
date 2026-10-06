import * as THREE from 'three';

// Rotate in the base point's local frame; X/Y reverse its Z normal.
export function rotateBaseOrientation(orientation, axis, degrees) {
  const direction = new THREE.Vector3();
  direction.setComponent(axis, 1);
  return new THREE.Quaternion().fromArray(orientation || [0,0,0,1]).normalize()
    .multiply(new THREE.Quaternion().setFromAxisAngle(direction, THREE.MathUtils.degToRad(degrees)))
    .normalize().toArray();
}

// Meshes keep their thickness on WebGL implementations that only support 1px lines.
function overlayMesh(geometry, color, order) {
  const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color,depthTest:false,depthWrite:false}));
  mesh.renderOrder=order;
  return mesh;
}

function outlinedShaft(radius, length, color, order=1003) {
  const group=new THREE.Group();
  group.add(overlayMesh(new THREE.CylinderGeometry(radius*1.65,radius*1.65,length,12),0x111318,order-1),
    overlayMesh(new THREE.CylinderGeometry(radius,radius,length,12),color,order));
  return group;
}

export function directionMarker(radius, color = 0x669fff) {
  const group = new THREE.Group();
  const ring=new THREE.Group();
  ring.add(overlayMesh(new THREE.TorusGeometry(radius,radius*.045,12,64),0x111318,1002),
    overlayMesh(new THREE.TorusGeometry(radius,radius*.025,12,64),color,1003));
  group.add(ring);
  for (const [axis, tint, length] of [[new THREE.Vector3(1,0,0),0xff6666,1.25],
    [new THREE.Vector3(0,1,0),0x66dd88,1.25],[new THREE.Vector3(0,0,1),color,1.8]]) {
    const arrow=new THREE.Group();
    const headLength=radius*.34, shaftLength=radius*length-headLength;
    const shaft=outlinedShaft(radius*.035,shaftLength,tint);
    shaft.position.y=shaftLength/2;
    const outline=overlayMesh(new THREE.ConeGeometry(radius*.15,headLength,16),0x111318,1002);
    const head=overlayMesh(new THREE.ConeGeometry(radius*.11,headLength*.88,16),tint,1003);
    outline.position.y=shaftLength+headLength/2;
    head.position.y=outline.position.y;
    arrow.add(shaft,outline,head);
    arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),axis);
    group.add(arrow);
  }
  return group;
}

export function basePointMarker(radius) {
  const group=new THREE.Group();
  group.add(directionMarker(radius*2.3));
  for(const axis of [new THREE.Vector3(1,0,0),new THREE.Vector3(0,1,0),new THREE.Vector3(0,0,1)]) {
    const cross=outlinedShaft(radius*.055,radius*2,0xffcc55,1005);
    cross.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),axis);
    group.add(cross);
  }
  group.add(overlayMesh(new THREE.SphereGeometry(radius*.23,16,12),0x111318,1004),
    overlayMesh(new THREE.SphereGeometry(radius*.16,16,12),0xffcc55,1005));
  return group;
}
