import * as THREE from 'three';

// Endpoints and arc-length midpoints come from kernel edge polylines.
// They approximate curved edges; triangle centers are explicitly mesh centers.
export function snapCandidates(mesh) {
  const candidates=[], seen=new Set();
  const add=(point,type)=>{const key=type+':'+point.join(',');if(!seen.has(key)){seen.add(key);candidates.push({point,type});}};
  for(const part of mesh.parts) {
    for(let g=0;g<part.edge_groups.length;g+=2) {
      const start=part.edge_groups[g],count=part.edge_groups[g+1];
      if(count<6)continue;
      const points=[];for(let i=start;i<start+count;i+=3)points.push(part.edges.slice(i,i+3));
      add(points[0],'顶点');add(points.at(-1),'顶点');
      const lengths=points.slice(1).map((p,i)=>new THREE.Vector3().fromArray(p).distanceTo(new THREE.Vector3().fromArray(points[i])));
      let remaining=lengths.reduce((a,b)=>a+b,0)/2;
      for(let i=0;i<lengths.length;i++) {
        if(remaining<=lengths[i]){const t=lengths[i] ? remaining/lengths[i] : 0;add(points[i].map((v,a)=>v+(points[i+1][a]-v)*t),'边中点');break;}
        remaining-=lengths[i];
      }
    }
  }
  return candidates;
}

export function closestSnap(candidates,model,camera,rect,pointer,maxDepth=Infinity,depthTolerance=0.0001) {
  let best=null;
  for(const candidate of candidates) {
    const projected=model.localToWorld(new THREE.Vector3().fromArray(candidate.point)).project(camera);
    if(projected.z<-1 || projected.z>1 || projected.z>maxDepth+depthTolerance)continue;
    const distance=Math.hypot((projected.x+1)*rect.width/2-pointer.x,(1-projected.y)*rect.height/2-pointer.y);
    const priority=candidate.type==='顶点' ? 0 : 1;
    if(distance<=12 && (!best || priority<best.priority || priority===best.priority && distance<best.distance))best={...candidate,distance,priority};
  }
  return best;
}

export function normalOrientation(normal) {
  return new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,0,1),new THREE.Vector3().fromArray(normal).normalize()).toArray();
}
