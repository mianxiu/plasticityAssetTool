import * as THREE from 'three';

// Endpoints and arc-length midpoints come from kernel edge polylines.
// Planar face centers use connected coplanar triangles, weighted by area.
export function planarFaceCenters(part) {
  const positions=part.positions || [], indices=part.indices || [];
  if(!indices.length)return [];
  const vertices=Array.from({length:positions.length/3},(_,i)=>new THREE.Vector3().fromArray(positions,i*3));
  const scale=new THREE.Box3().setFromPoints(vertices).getSize(new THREE.Vector3()).length();
  const tolerance=Math.max(scale*1e-7,1e-9);
  const triangles=[], edges=new Map(), parent=[];
  const root=i=>{while(parent[i]!==i){parent[i]=parent[parent[i]];i=parent[i];}return i;};
  const key=v=>v.toArray().join(',');
  for(let i=0;i<indices.length;i+=3) {
    const points=indices.slice(i,i+3).map(index=>vertices[index]);
    const cross=points[1].clone().sub(points[0]).cross(points[2].clone().sub(points[0]));
    const area=cross.length()/2;if(!area)continue;
    const normal=cross.normalize(), id=triangles.length;
    const triangle={points,normal,area,center:points[0].clone().add(points[1]).add(points[2]).divideScalar(3)};
    triangles.push(triangle);parent.push(id);
    for(let side=0;side<3;side++) {
      const edgeKey=[key(points[side]),key(points[(side+1)%3])].sort().join('|');
      const neighbors=edges.get(edgeKey) || [];
      for(const neighbor of neighbors) {
        const previous=triangles[neighbor];
        if(normal.dot(previous.normal)>1-1e-10 && Math.abs(normal.dot(previous.points[0].clone().sub(points[0])))<=tolerance)
          parent[root(id)]=root(neighbor);
      }
      neighbors.push(id);edges.set(edgeKey,neighbors);
    }
  }
  const patches=new Map();
  triangles.forEach((triangle,i)=>{const id=root(i);if(!patches.has(id))patches.set(id,[]);patches.get(id).push(triangle);});
  const centers=[];
  for(const patch of patches.values()) {
    // Do not turn every facet of a curved surface into a snap target.
    if(patch.length<2)continue;
    const area=patch.reduce((sum,triangle)=>sum+triangle.area,0);
    const center=patch.reduce((sum,triangle)=>sum.addScaledVector(triangle.center,triangle.area),new THREE.Vector3()).divideScalar(area);
    // A concave face or a face with a hole can have its centroid outside the face.
    if(!patch.some(triangle=>new THREE.Triangle(...triangle.points).containsPoint(center)))continue;
    centers.push({point:center.toArray(),type:'面中心',normal:patch[0].normal.toArray()});
  }
  return centers;
}

export function snapCandidates(mesh) {
  const candidates=[], seen=new Set();
  const add=(point,type)=>{const key=type+':'+point.join(',');if(!seen.has(key)){seen.add(key);candidates.push({point,type});}};
  for(const part of mesh.parts) {
    candidates.push(...planarFaceCenters(part));
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

export function kernelSnapCandidates(mesh) {
  const candidates=[],seen=new Set(),types=['顶点','边中点','曲线参数中点'];
  for(const part of mesh.parts) {
    const values=part.kernel_snaps || [];
    for(let i=0;i<values.length;i+=4) {
      const point=values.slice(i,i+3),type=types[values[i+3]],key=type+':'+point.join(',');
      if(type && point.length===3 && point.every(Number.isFinite) && !seen.has(key)) {
        seen.add(key);candidates.push({point,type,kernel:true});
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
    const priority=(candidate.type==='顶点' ? 0 : candidate.type==='边中点' || candidate.type==='曲线参数中点' ? 1 : 2)*2+(candidate.kernel?0:1);
    if(distance<=12 && (!best || priority<best.priority || priority===best.priority && distance<best.distance))best={...candidate,distance,priority};
  }
  return best;
}

export function normalOrientation(normal) {
  return new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,0,1),new THREE.Vector3().fromArray(normal).normalize()).toArray();
}
